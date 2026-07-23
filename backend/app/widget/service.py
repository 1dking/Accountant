
import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.forms import service as forms_service
from app.forms.models import Form
from app.forms.schemas import FormCreate
from app.widget.models import WidgetConfig
from app.widget.schemas import WidgetConfigUpdate, WidgetSubmitRequest

DEFAULTS = {
    "button_color": "#2563eb",
    "bg_color": "#ffffff",
    "text_color": "#111827",
    "greeting_title": "Let's talk",
    "greeting_message": "Leave your details and we'll get back to you shortly.",
    "success_message": "Thanks! We'll be in touch soon.",
}

_WIDGET_FIELDS_JSON = json.dumps(
    [
        {"name": "name", "label": "Name", "type": "text", "required": True},
        {"name": "email", "label": "Email", "type": "email", "required": True},
        {"name": "phone", "label": "Phone", "type": "text", "required": False},
        {"name": "message", "label": "Message", "type": "textarea", "required": False},
    ]
)


async def get_or_create_config(db: AsyncSession, user: User) -> WidgetConfig:
    result = await db.execute(select(WidgetConfig).where(WidgetConfig.user_id == user.id))
    config = result.scalar_one_or_none()
    if config:
        return config

    # Hidden Form this widget rides on — never listed on the Forms page,
    # only reachable via the widget's own submit path.
    form = Form(
        name=f"Website Widget — {user.full_name}",
        fields_json=_WIDGET_FIELDS_JSON,
        created_by=user.id,
    )
    db.add(form)
    await db.flush()
    form.webhook_key = secrets.token_urlsafe(32)

    config = WidgetConfig(
        user_id=user.id,
        widget_key=secrets.token_urlsafe(24),
        form_id=form.id,
        **DEFAULTS,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def update_config(db: AsyncSession, user: User, data: WidgetConfigUpdate) -> WidgetConfig:
    config = await get_or_create_config(db, user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)
    return config


async def rotate_key(db: AsyncSession, user: User) -> WidgetConfig:
    config = await get_or_create_config(db, user)
    config.widget_key = secrets.token_urlsafe(24)
    await db.commit()
    await db.refresh(config)
    return config


async def get_public_config(db: AsyncSession, widget_key: str) -> WidgetConfig:
    result = await db.execute(
        select(WidgetConfig).where(
            WidgetConfig.widget_key == widget_key, WidgetConfig.is_enabled.is_(True)
        )
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise NotFoundError("Widget", "unknown")
    return config


async def submit(
    db: AsyncSession,
    widget_key: str,
    data: WidgetSubmitRequest,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    if data.website:  # honeypot tripped — silently accept, submit nothing
        return

    config = await get_public_config(db, widget_key)
    form = await db.get(Form, config.form_id)
    if form is None or not form.webhook_key:
        raise ValidationError("This widget is not fully configured")

    payload = {"name": data.name, "email": data.email}
    if data.phone:
        payload["phone"] = data.phone
    if data.message:
        payload["message"] = data.message

    # Rides the exact same lead pipeline as an external-site form webhook:
    # contact match-or-create, activity log, FORM_SUBMITTED dispatch.
    await forms_service.submit_via_webhook(db, form.webhook_key, payload, ip_address, user_agent)
