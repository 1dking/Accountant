
import json
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


async def submit_form(
    db: AsyncSession,
    form_id: uuid.UUID,
    data: dict,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> FormSubmission:
    """Validate form exists and is active, create/update contact from email field, log submission."""
    # Check form exists and is active
    form = await get_public_form(db, form_id)

    # Try to match or create contact from submitted data
    contact_id = None
    email = data.get("email")
    if email and isinstance(email, str):
        # Search for existing contact by email
        result = await db.execute(
            select(Contact).where(Contact.email == email)
        )
        contact = result.scalar_one_or_none()

        if contact:
            contact_id = contact.id
        else:
            # Create a new contact from form data
            company_name = (
                data.get("company_name")
                or data.get("company")
                or data.get("name")
                or email
            )
            contact = Contact(
                id=uuid.uuid4(),
                type=ContactType.CLIENT,
                company_name=company_name,
                contact_name=data.get("name") or data.get("contact_name"),
                email=email,
                phone=data.get("phone"),
                created_by=form.created_by,
            )
            db.add(contact)
            await db.flush()
            contact_id = contact.id

    # Create submission
    submission = FormSubmission(
        id=uuid.uuid4(),
        form_id=form_id,
        contact_id=contact_id,
        data_json=json.dumps(data),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # Log activity on contact timeline
    if contact_id:
        await log_contact_activity(
            db,
            contact_id=contact_id,
            activity_type=ActivityType.NOTE_ADDED,
            title=f"Form submitted: {form.name}",
            description=f"Form submission received via {form.name}",
            reference_type="form_submission",
            reference_id=submission.id,
        )

    return submission


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
