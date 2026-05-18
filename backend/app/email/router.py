
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .models import EmailTemplateOverride
from .renderer import get_override, render_email
from .schemas import (
    SendInvoiceEmailRequest,
    SendReminderEmailRequest,
    SmtpConfigCreate,
    SmtpConfigResponse,
    SmtpConfigUpdate,
    TestEmailRequest,
)
from .template_schemas import TEMPLATES, get_schema, template_keys

router = APIRouter()


# ---------------------------------------------------------------------------
# SMTP Config CRUD
# ---------------------------------------------------------------------------


@router.post("/configs", response_model=dict)
async def create_smtp_config(
    data: SmtpConfigCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    config = await service.create_smtp_config(db, data, user)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.get("/configs", response_model=dict)
async def list_smtp_configs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    configs = await service.list_smtp_configs(db, user)
    return {
        "data": [SmtpConfigResponse.model_validate(c) for c in configs],
    }


@router.get("/configs/{config_id}", response_model=dict)
async def get_smtp_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    config = await service.get_smtp_config(db, config_id, user)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.put("/configs/{config_id}", response_model=dict)
async def update_smtp_config(
    config_id: uuid.UUID,
    data: SmtpConfigUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    config = await service.update_smtp_config(db, config_id, data, user)
    return {"data": SmtpConfigResponse.model_validate(config)}


@router.delete("/configs/{config_id}", response_model=dict)
async def delete_smtp_config(
    config_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    await service.delete_smtp_config(db, config_id, user)
    return {"data": {"detail": "SMTP config deleted"}}


# ---------------------------------------------------------------------------
# Email actions
# ---------------------------------------------------------------------------


@router.post("/test", response_model=dict)
async def send_test_email(
    data: TestEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    from datetime import datetime, timezone

    smtp_config = await service.get_smtp_config(db, data.smtp_config_id, user)
    html_body = service.render_template(
        "test_email.html",
        company_name=smtp_config.from_name,
        year=datetime.now(timezone.utc).year,
    )

    await service.send_email(
        smtp_config,
        to=data.to_email,
        subject="Test Email — Accountant",
        html_body=html_body,
    )
    return {"data": {"detail": f"Test email sent to {data.to_email}"}}


@router.post("/send-invoice", response_model=dict)
async def send_invoice_email(
    data: SendInvoiceEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    result = await service.send_invoice_email(
        db=db,
        invoice_id=data.invoice_id,
        smtp_config_id=data.smtp_config_id,
        recipient_email=data.recipient_email,
        subject=data.subject,
        message=data.message,
        user=user,
    )
    return {"data": result}


@router.post("/send-reminder", response_model=dict)
async def send_payment_reminder(
    data: SendReminderEmailRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN, Role.TEAM_MEMBER, Role.ACCOUNTANT])),
):
    result = await service.send_payment_reminder(
        db=db,
        invoice_id=data.invoice_id,
        smtp_config_id=data.smtp_config_id,
        user=user,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Editable email templates (admin-only)
# ---------------------------------------------------------------------------


class TemplateOverrideBody(BaseModel):
    subject_override: str | None = Field(None, max_length=255)
    body_override: str | None = None


class TemplateTestBody(BaseModel):
    to_email: EmailStr
    # Allow the admin to test an UNSAVED override by passing the draft
    # directly. If omitted, we use whatever's persisted (or system default).
    subject_override: str | None = Field(None, max_length=255)
    body_override: str | None = None


def _system_body(template_key: str) -> str:
    """Read the system template source so the editor can pre-fill with
    "Reset to default" content. The Jinja2 file is the source of truth."""
    from pathlib import Path

    tpl_dir = Path(__file__).parent / "templates"
    tpl_file = tpl_dir / f"{template_key}.html"
    if not tpl_file.exists():
        return ""
    return tpl_file.read_text(encoding="utf-8")


def _serialize(
    key: str, override: EmailTemplateOverride | None
) -> dict:
    schema = TEMPLATES[key]
    return {
        "template_key": key,
        "label": schema.get("label", key),
        "description": schema.get("description", ""),
        "default_subject": schema.get("default_subject", ""),
        "variables": schema.get("variables", []),
        "allows_body_override": schema.get("allows_body_override", True),
        "warnings": schema.get("warnings", []),
        "subject_override": override.subject_override if override else None,
        "body_override": override.body_override if override else None,
        "is_customized": bool(
            override is not None
            and (override.subject_override or override.body_override)
        ),
        "system_body": _system_body(key),
    }


@router.get("/templates", response_model=dict)
async def list_email_templates(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    """Return every editable template + the admin's override (if any)
    + schema metadata (variables, warnings, allows_body_override)."""
    rows = await db.execute(
        select(EmailTemplateOverride).where(
            EmailTemplateOverride.user_id == user.id
        )
    )
    by_key = {r.template_key: r for r in rows.scalars().all()}
    return {
        "data": [_serialize(k, by_key.get(k)) for k in template_keys()]
    }


@router.get("/templates/{template_key}", response_model=dict)
async def get_email_template(
    template_key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    if get_schema(template_key) is None:
        raise HTTPException(status_code=404, detail=f"Unknown template: {template_key}")
    override = await get_override(db, user.id, template_key)
    return {"data": _serialize(template_key, override)}


@router.put("/templates/{template_key}", response_model=dict)
async def upsert_email_template(
    template_key: str,
    body: TemplateOverrideBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    """Save (or update) an override row. Empty strings are treated as
    'unset' so the admin can clear one field without deleting the row."""
    schema = get_schema(template_key)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Unknown template: {template_key}")

    if body.body_override and not schema.get("allows_body_override", True):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Template '{template_key}' does not allow body overrides "
                "(structured content). Use subject_override only."
            ),
        )

    subject_clean = (body.subject_override or "").strip() or None
    body_clean = (body.body_override or "").strip() or None

    override = await get_override(db, user.id, template_key)
    if override is None:
        override = EmailTemplateOverride(
            id=uuid.uuid4(),
            user_id=user.id,
            template_key=template_key,
            subject_override=subject_clean,
            body_override=body_clean,
        )
        db.add(override)
    else:
        override.subject_override = subject_clean
        override.body_override = body_clean

    await db.commit()
    await db.refresh(override)
    return {"data": _serialize(template_key, override)}


@router.delete("/templates/{template_key}", response_model=dict)
async def reset_email_template(
    template_key: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    """Drop the override row → next render falls back to system Jinja2."""
    if get_schema(template_key) is None:
        raise HTTPException(status_code=404, detail=f"Unknown template: {template_key}")
    override = await get_override(db, user.id, template_key)
    if override is not None:
        await db.delete(override)
        await db.commit()
    return {"data": {"detail": "Override removed; system default restored."}}


@router.post("/templates/{template_key}/test", response_model=dict)
async def send_template_test(
    template_key: str,
    body: TemplateTestBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ADMIN])),
):
    """Render the template (using the admin's saved override OR a draft
    passed in this request) with realistic sample data and send to the
    given address. Sample data is enough to make every placeholder visible
    in the preview — admins can sanity-check spelling, layout, branding."""
    schema = get_schema(template_key)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Unknown template: {template_key}")

    smtp_config = await service.resolve_smtp_config(db, user, None)
    sample = _sample_variables(template_key, smtp_config.from_name)

    # If the request carried draft override fields, temporarily persist
    # them so render_email picks them up. We restore prior state after.
    existing = await get_override(db, user.id, template_key)
    transient = None
    if body.subject_override is not None or body.body_override is not None:
        if existing is None:
            transient = EmailTemplateOverride(
                id=uuid.uuid4(),
                user_id=user.id,
                template_key=template_key,
                subject_override=(body.subject_override or "").strip() or None,
                body_override=(body.body_override or "").strip() or None,
            )
            db.add(transient)
        else:
            # Snapshot current values so we can roll back.
            prev = {
                "subject": existing.subject_override,
                "body": existing.body_override,
            }
            existing.subject_override = (body.subject_override or "").strip() or None
            existing.body_override = (body.body_override or "").strip() or None
        await db.commit()

    try:
        if not schema.get("allows_body_override", True):
            # Structured templates (invoice, payment_reminder, estimate)
            # can't render without a real domain object. For test sends
            # we only verify SUBJECT + chrome — body becomes a preview
            # notice rather than a Jinja2 crash on None.invoice_number.
            subject, _ = await render_email(
                db, template_key, user.id, **sample
            )
            from .renderer import _render_override_in_chrome
            html_body = _render_override_in_chrome(
                "<p>This is a preview. Actual emails will include the "
                "full invoice or estimate details rendered here.</p>",
                company_name=smtp_config.from_name,
                year=2026,
            )
        else:
            subject, html_body = await render_email(
                db, template_key, user.id, **sample
            )
        await service.send_email(
            smtp_config,
            to=str(body.to_email),
            subject=f"[TEST] {subject}",
            html_body=html_body,
        )
    finally:
        # Roll back the transient draft so the saved override is unchanged.
        if transient is not None:
            await db.delete(transient)
            await db.commit()
        elif (
            existing is not None
            and (body.subject_override is not None or body.body_override is not None)
        ):
            existing.subject_override = prev["subject"]
            existing.body_override = prev["body"]
            await db.commit()

    return {"data": {"detail": f"Test sent to {body.to_email}"}}


def _sample_variables(template_key: str, company_name: str) -> dict:
    """Realistic sample values for every placeholder so the admin sees a
    rendered preview, not a wall of {token} text."""
    common = {"company_name": company_name, "year": 2026}
    if template_key == "password_reset":
        return {
            **common,
            "user_name": "Jane Smith",
            "reset_url": "https://accountant.example.com/auth/password-reset/confirm/sample-token",
            "expires_in": "1 hour",
        }
    if template_key == "invite":
        return {
            **common,
            "full_name": "Jane Smith",
            "invite_link": "https://accountant.example.com/invite?token=sample",
        }
    if template_key == "notification":
        return {
            **common,
            "title": "New SMS message",
            "message": "Sarah from Acme Corp: 'Can we move our 3pm to Thursday?'",
            "link_url": "https://accountant.example.com/contacts/123",
            "link_label": "Open in app",
            "type_label": "New SMS message",
            "type": "sms_inbound",
            "preferences_url": "https://accountant.example.com/settings?tab=notif-prefs",
        }
    if template_key == "payment_confirmation":
        return {
            **common,
            "invoice_number": "INV-1042",
            "amount": 1650.00,
            "currency": "USD",
            "payment_date": "2026-05-18",
            "payment_method": "bank_transfer",
        }
    if template_key in {"invoice", "payment_reminder", "estimate"}:
        # For structured templates, the body comes from Jinja2 which
        # needs the full object. Build a tiny stub. The admin's body
        # override is disallowed for these, so only the subject matters.
        return {
            **common,
            "invoice_number": "INV-1042",
            "estimate_number": "EST-0042",
            "total": 1500.00,
            "currency": "USD",
            "due_date": "2026-06-15",
            "days_overdue": 5,
            "contact_name": "Sarah Adams",
            "view_url": "https://accountant.example.com/p/sample-token",
            "custom_message": None,
            # No real invoice/estimate object — system template will be
            # missing fields. That's OK; admin is testing subject only.
            "invoice": None,
            "estimate": None,
        }
    return common
