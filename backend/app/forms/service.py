
import json
import logging
import secrets
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.contacts.models import ActivityType, Contact, ContactType
from app.contacts.service import log_contact_activity
from app.core.exceptions import NotFoundError, ValidationError
from app.forms.models import Form, FormSubmission
from app.forms.schemas import FormCreate, FormUpdate

logger = logging.getLogger(__name__)


# Common field-name aliases an external site / form builder might send. The raw
# payload is always stored in full; this only decides which keys populate the
# Contact. Matching is case-insensitive and ignores spaces/underscores/hyphens.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "email": ("email", "emailaddress", "e-mail", "youremail", "workemail", "contactemail"),
    "name": ("name", "fullname", "yourname", "contactname", "firstname", "customername"),
    "last_name": ("lastname", "surname", "familyname"),
    "phone": ("phone", "phonenumber", "telephone", "mobile", "cell", "contactnumber"),
    "company": ("company", "companyname", "organization", "organisation", "business", "businessname"),
    "message": ("message", "notes", "comments", "comment", "enquiry", "inquiry", "details"),
}


def _norm(key: str) -> str:
    return key.lower().replace(" ", "").replace("_", "").replace("-", "")


def map_lead_fields(data: dict) -> dict:
    """Pull standard Contact fields out of an arbitrary submission payload.

    Returns a dict with any of: email, name, phone, company, message. Unmapped
    keys are ignored here but the caller still stores the full raw payload.
    """
    normalized = { _norm(k): v for k, v in data.items() if isinstance(k, str) }
    out: dict = {}
    for target, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in normalized and normalized[alias] not in (None, ""):
                out[target] = normalized[alias]
                break
    # Stitch a full name from first + last if no single name field was found.
    if "name" not in out and "last_name" in out:
        out["name"] = out["last_name"]
    if "name" in out and "last_name" in out and out["last_name"] not in str(out["name"]):
        out["name"] = f"{out['name']} {out['last_name']}".strip()
    out.pop("last_name", None)
    return out


async def create_form(
    db: AsyncSession, data: FormCreate, user: User
) -> Form:
    form = Form(
        id=uuid.uuid4(),
        name=data.name,
        description=data.description,
        fields_json=data.fields_json,
        thank_you_type=data.thank_you_type,
        thank_you_config_json=data.thank_you_config_json,
        style_json=data.style_json,
        created_by=user.id,
    )
    db.add(form)
    await db.commit()
    await db.refresh(form)
    return form


async def list_forms(
    db: AsyncSession, page: int = 1, page_size: int = 25
) -> tuple[list[dict], int]:
    """Return forms with computed submission_count and last_submission_at."""
    # Count total forms
    total = (await db.execute(select(func.count(Form.id)))).scalar() or 0

    # Subquery for submission stats per form
    sub_q = (
        select(
            FormSubmission.form_id,
            func.count(FormSubmission.id).label("submission_count"),
            func.max(FormSubmission.submitted_at).label("last_submission_at"),
        )
        .group_by(FormSubmission.form_id)
        .subquery()
    )

    query = (
        select(
            Form,
            func.coalesce(sub_q.c.submission_count, 0).label("submission_count"),
            sub_q.c.last_submission_at,
        )
        .outerjoin(sub_q, Form.id == sub_q.c.form_id)
        .order_by(Form.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    rows = result.all()

    items = []
    for form, submission_count, last_submission_at in rows:
        items.append(
            {
                "id": form.id,
                "name": form.name,
                "is_active": form.is_active,
                "submission_count": submission_count,
                "last_submission_at": last_submission_at,
                "created_at": form.created_at,
            }
        )

    return items, total


async def get_form(db: AsyncSession, form_id: uuid.UUID) -> Form:
    result = await db.execute(select(Form).where(Form.id == form_id))
    form = result.scalar_one_or_none()
    if form is None:
        raise NotFoundError("Form", str(form_id))
    return form


async def update_form(
    db: AsyncSession, form_id: uuid.UUID, data: FormUpdate
) -> Form:
    form = await get_form(db, form_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(form, key, value)
    await db.commit()
    await db.refresh(form)
    return form


async def delete_form(db: AsyncSession, form_id: uuid.UUID) -> None:
    form = await get_form(db, form_id)
    await db.delete(form)
    await db.commit()


async def get_public_form(db: AsyncSession, form_id: uuid.UUID) -> Form:
    """Return form data for public rendering (only if active)."""
    result = await db.execute(
        select(Form).where(Form.id == form_id, Form.is_active == True)  # noqa: E712
    )
    form = result.scalar_one_or_none()
    if form is None:
        raise NotFoundError("Form", str(form_id))
    return form


async def _ingest_submission(
    db: AsyncSession,
    form: Form,
    data: dict,
    ip_address: str | None,
    user_agent: str | None,
    source: str,
) -> FormSubmission:
    """Shared lead-ingestion core for both the native form and the webhook.

    Match-or-create a Contact from the payload (owned by the form's creator, so
    it lands in their private book), store the full raw payload as a submission,
    log the timeline entry, and fire the FORM_SUBMITTED automation.
    """
    fields = map_lead_fields(data)

    contact_id = None
    email = fields.get("email")
    if email and isinstance(email, str):
        contact = (
            await db.execute(select(Contact).where(Contact.email == email))
        ).scalar_one_or_none()

        if contact:
            contact_id = contact.id
        else:
            company_name = fields.get("company") or fields.get("name") or email
            contact = Contact(
                id=uuid.uuid4(),
                type=ContactType.CLIENT,
                company_name=company_name,
                contact_name=fields.get("name"),
                email=email,
                phone=fields.get("phone"),
                lead_source=source,
                created_by=form.created_by,
            )
            db.add(contact)
            await db.flush()
            contact_id = contact.id

    submission = FormSubmission(
        id=uuid.uuid4(),
        form_id=form.id,
        contact_id=contact_id,
        data_json=json.dumps(data),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.NOTE_ADDED,
            title=f"Form submitted: {form.name}",
            description=f"Lead captured via {form.name} ({source})",
            reference_type="form_submission",
            reference_id=submission.id,
        )

    # Fire the FORM_SUBMITTED automation. Isolated: a workflow failure (or a slow
    # send) must never fail the lead capture — the contact + submission are
    # already committed above.
    try:
        from app.workflows.models import TriggerType
        from app.workflows.service import dispatch_event

        await dispatch_event(
            db,
            TriggerType.FORM_SUBMITTED,
            event_data={"form_id": str(form.id), "form_name": form.name, **data},
            contact_id=contact_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("form_submitted automation failed for form %s", form.id)

    return submission


async def submit_form(
    db: AsyncSession,
    form_id: uuid.UUID,
    data: dict,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> FormSubmission:
    """Public submit for a form hosted BY the app (the /public/{id}/submit page)."""
    form = await get_public_form(db, form_id)
    return await _ingest_submission(db, form, data, ip_address, user_agent, "form")


async def submit_via_webhook(
    db: AsyncSession,
    webhook_key: str,
    data: dict,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> FormSubmission:
    """Inbound webhook for a form hosted ELSEWHERE (an external website posts its
    lead JSON to /api/forms/webhook/{key})."""
    form = (
        await db.execute(
            select(Form).where(
                Form.webhook_key == webhook_key,
                Form.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if form is None:
        # 404, not 401 — never reveal whether a key "exists but is inactive".
        raise NotFoundError("Webhook", "unknown")
    return await _ingest_submission(db, form, data, ip_address, user_agent, "webhook")


async def generate_webhook_key(db: AsyncSession, form_id: uuid.UUID) -> Form:
    """Create or rotate the form's inbound-webhook secret.

    Rotating invalidates the old URL immediately — the point of a rotate is to cut
    off a leaked key. Gated at the router (require_role), like the rest of forms.
    """
    form = await get_form(db, form_id)
    form.webhook_key = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(form)
    return form


async def list_submissions(
    db: AsyncSession, form_id: uuid.UUID, page: int = 1, page_size: int = 25
) -> tuple[list[FormSubmission], int]:
    # Ensure form exists
    await get_form(db, form_id)

    count_q = select(func.count()).where(FormSubmission.form_id == form_id)
    total = (await db.execute(count_q)).scalar() or 0

    query = (
        select(FormSubmission)
        .where(FormSubmission.form_id == form_id)
        .order_by(FormSubmission.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    submissions = list(result.scalars().all())

    return submissions, total
