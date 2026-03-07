"""Business logic for the proposals module."""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.core.authorization import apply_ownership_filter, authorize_owner
from app.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from app.core.pagination import PaginationParams, build_pagination_meta
from app.proposals.models import (
    FollowUpRule,
    GhlSyncLog,
    Proposal,
    ProposalActivity,
    ProposalRecipient,
    ProposalStatus,
    ProposalTemplate,
    PaymentStatus,
    SyncDirection,
    SyncStatus,
)
from app.proposals.schemas import (
    FollowUpRuleCreate,
    ProposalCreate,
    ProposalFilter,
    ProposalUpdate,
    RecipientCreate,
    TemplateCreate,
    TemplateUpdate,
)


# ---------------------------------------------------------------------------
# Number generation
# ---------------------------------------------------------------------------

async def generate_proposal_number(db: AsyncSession) -> str:
    """Generate next sequential proposal number."""
    result = await db.execute(
        select(Proposal.proposal_number)
        .order_by(Proposal.proposal_number.desc())
        .limit(1)
        .with_for_update()
    )
    last = result.scalar()
    if last:
        num = int(last.split("-")[1]) + 1
    else:
        num = 1
    return f"PROP-{num:04d}"


# ---------------------------------------------------------------------------
# Proposal CRUD
# ---------------------------------------------------------------------------

async def create_proposal(db: AsyncSession, data: ProposalCreate, user: User) -> Proposal:
    """Create a new proposal with recipients."""
    max_retries = 5
    proposal = None
    for attempt in range(max_retries):
        proposal_number = await generate_proposal_number(db)
        proposal = Proposal(
            proposal_number=proposal_number,
            contact_id=data.contact_id,
            title=data.title,
            content_json=data.content_json,
            value=data.value,
            currency=data.currency,
            template_id=data.template_id,
            collect_payment=data.collect_payment,
            payment_mode=data.payment_mode,
            payment_frequency=data.payment_frequency,
            payment_status=PaymentStatus.UNPAID if data.collect_payment else None,
            follow_up_enabled=data.follow_up_enabled,
            follow_up_hours=data.follow_up_hours,
            created_by=user.id,
        )
        nested = await db.begin_nested()
        try:
            db.add(proposal)
            await db.flush()
            break
        except IntegrityError:
            await nested.rollback()
            if attempt == max_retries - 1:
                raise

    # Add recipients with unique signing tokens
    for r in data.recipients:
        recipient = ProposalRecipient(
            proposal_id=proposal.id,
            email=r.email,
            name=r.name,
            role=r.role,
            signing_order=r.signing_order,
            signing_token=secrets.token_urlsafe(32),
        )
        db.add(recipient)

    # Log activity
    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="created",
        actor_email=user.email,
        actor_name=user.full_name,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(proposal)
    return proposal


async def get_proposal(db: AsyncSession, proposal_id: uuid.UUID, user: User | None = None) -> Proposal:
    """Get a single proposal with all relationships."""
    result = await db.execute(
        select(Proposal)
        .options(
            selectinload(Proposal.contact),
            selectinload(Proposal.recipients),
            selectinload(Proposal.activities),
            selectinload(Proposal.template),
        )
        .where(Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise NotFoundError("Proposal", str(proposal_id))
    if user is not None:
        authorize_owner(proposal.created_by, user, "Proposal")
    return proposal


async def list_proposals(
    db: AsyncSession,
    filters: ProposalFilter,
    pagination: PaginationParams,
    user: User | None = None,
) -> tuple[list[Proposal], dict]:
    """List proposals with filtering and pagination."""
    query = select(Proposal).options(selectinload(Proposal.contact))

    # Ownership filter: non-admins only see their own proposals
    if user is not None:
        query = apply_ownership_filter(query, Proposal.created_by, user)

    if filters.search:
        search = f"%{filters.search}%"
        query = query.where(
            or_(
                Proposal.title.ilike(search),
                Proposal.proposal_number.ilike(search),
            )
        )
    if filters.status:
        query = query.where(Proposal.status == filters.status)
    if filters.contact_id:
        query = query.where(Proposal.contact_id == filters.contact_id)
    if filters.payment_status:
        query = query.where(Proposal.payment_status == filters.payment_status)
    if filters.date_from:
        query = query.where(Proposal.created_at >= datetime.combine(filters.date_from, datetime.min.time()))
    if filters.date_to:
        query = query.where(Proposal.created_at <= datetime.combine(filters.date_to, datetime.max.time()))
    if filters.value_min is not None:
        query = query.where(Proposal.value >= filters.value_min)
    if filters.value_max is not None:
        query = query.where(Proposal.value <= filters.value_max)

    # Count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Paginate
    query = query.order_by(Proposal.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    proposals = list(result.scalars().all())

    meta = build_pagination_meta(total, pagination)
    return proposals, meta


async def update_proposal(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    data: ProposalUpdate,
    user: User,
) -> Proposal:
    """Update a proposal (only drafts can be fully edited)."""
    proposal = await get_proposal(db, proposal_id, user)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(proposal, field, value)

    await db.commit()
    await db.refresh(proposal)
    return proposal


async def delete_proposal(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> None:
    """Delete a proposal."""
    proposal = await get_proposal(db, proposal_id, user)
    await db.delete(proposal)
    await db.commit()


async def clone_proposal(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> Proposal:
    """Clone a proposal as a new draft."""
    source = await get_proposal(db, proposal_id, user)

    new_data = ProposalCreate(
        contact_id=source.contact_id,
        title=f"{source.title} (Copy)",
        content_json=source.content_json,
        value=source.value,
        currency=source.currency,
        template_id=source.template_id,
        collect_payment=source.collect_payment,
        payment_mode=source.payment_mode,
        payment_frequency=source.payment_frequency,
        recipients=[
            RecipientCreate(
                email=r.email, name=r.name, role=r.role, signing_order=r.signing_order
            )
            for r in source.recipients
        ],
        follow_up_enabled=source.follow_up_enabled,
        follow_up_hours=source.follow_up_hours,
    )
    return await create_proposal(db, new_data, user)


# ---------------------------------------------------------------------------
# Proposal sending & status
# ---------------------------------------------------------------------------

async def send_proposal(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> Proposal:
    """Mark proposal as sent and generate public token + signing tokens."""
    proposal = await get_proposal(db, proposal_id, user)
    if proposal.status not in (ProposalStatus.DRAFT,):
        raise ValidationError(f"Cannot send proposal with status: {proposal.status.value}")

    proposal.status = ProposalStatus.SENT
    proposal.sent_at = datetime.now(timezone.utc)
    proposal.public_token = secrets.token_urlsafe(32)

    # Ensure all recipients have signing tokens
    for r in proposal.recipients:
        if not r.signing_token:
            r.signing_token = secrets.token_urlsafe(32)

    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="sent",
        actor_email=user.email,
        actor_name=user.full_name,
    )
    db.add(activity)

    await db.commit()
    await db.refresh(proposal)

    # Send emails to recipients (fire-and-forget)
    # This would be handled by the email service in production

    return proposal


async def mark_viewed(db: AsyncSession, proposal_id: uuid.UUID, ip_address: str | None = None, user_agent: str | None = None) -> Proposal:
    """Mark proposal as viewed (idempotent - only updates on first view)."""
    proposal = await get_proposal(db, proposal_id)

    if proposal.status == ProposalStatus.SENT:
        proposal.status = ProposalStatus.VIEWED
        proposal.viewed_at = datetime.now(timezone.utc)

        activity = ProposalActivity(
            proposal_id=proposal.id,
            action="viewed",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(activity)
        await db.commit()
        await db.refresh(proposal)

        # Send notification to proposal creator
        from app.notifications.service import create_notification
        await create_notification(
            db,
            user_id=proposal.created_by,
            type="proposal_viewed",
            title="Proposal Viewed",
            message=f'"{proposal.title}" has been viewed',
            resource_type="proposal",
            resource_id=str(proposal.id),
        )

    return proposal


async def mark_declined(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> Proposal:
    """Mark proposal as declined."""
    proposal = await get_proposal(db, proposal_id, user)
    proposal.status = ProposalStatus.DECLINED

    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="declined",
        actor_email=user.email,
        actor_name=user.full_name,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(proposal)
    return proposal


async def mark_completed(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> Proposal:
    """Manually mark proposal as signed/completed."""
    proposal = await get_proposal(db, proposal_id, user)
    proposal.status = ProposalStatus.SIGNED
    proposal.signed_at = datetime.now(timezone.utc)

    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="signed",
        actor_email=user.email,
        actor_name=user.full_name,
    )
    db.add(activity)
    await db.commit()
    await db.refresh(proposal)
    return proposal


# ---------------------------------------------------------------------------
# E-Signature
# ---------------------------------------------------------------------------

async def get_signing_data(db: AsyncSession, signing_token: str) -> dict:
    """Get proposal data for a signing page using the recipient's unique token."""
    result = await db.execute(
        select(ProposalRecipient)
        .where(ProposalRecipient.signing_token == signing_token)
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise NotFoundError("SigningToken", signing_token)

    proposal = await get_proposal(db, recipient.proposal_id)

    if proposal.status not in (ProposalStatus.SENT, ProposalStatus.VIEWED, ProposalStatus.WAITING_SIGNATURE):
        raise ValidationError(f"Proposal is not available for signing (status: {proposal.status.value})")

    all_signed = all(r.signed_at is not None for r in proposal.recipients if r.role == "signer")

    return {
        "proposal_id": proposal.id,
        "proposal_title": proposal.title,
        "content_json": proposal.content_json,
        "recipient_name": recipient.name,
        "recipient_email": recipient.email,
        "recipient_role": recipient.role,
        "recipient_id": recipient.id,
        "already_signed": recipient.signed_at is not None,
        "all_signed": all_signed,
        "contact_name": proposal.contact.contact_name if proposal.contact else None,
        "company_name": proposal.contact.company_name if proposal.contact else None,
        "collect_payment": proposal.collect_payment,
        "value": str(proposal.value),
        "currency": proposal.currency,
    }


async def sign_proposal(
    db: AsyncSession,
    signing_token: str,
    recipient_id: uuid.UUID,
    signature_data: str,
    signature_type: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    """Sign a proposal as a recipient."""
    result = await db.execute(
        select(ProposalRecipient).where(
            ProposalRecipient.signing_token == signing_token,
            ProposalRecipient.id == recipient_id,
        )
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise NotFoundError("Recipient", str(recipient_id))

    if recipient.signed_at is not None:
        raise ValidationError("This recipient has already signed")

    proposal = await get_proposal(db, recipient.proposal_id)

    if proposal.status not in (ProposalStatus.SENT, ProposalStatus.VIEWED, ProposalStatus.WAITING_SIGNATURE):
        raise ValidationError(f"Proposal cannot be signed (status: {proposal.status.value})")

    # Generate document hash (SHA-256 of content at signing time)
    content_hash = hashlib.sha256(proposal.content_json.encode("utf-8")).hexdigest()

    # Record signature
    recipient.signed_at = datetime.now(timezone.utc)
    recipient.signature_data = signature_data
    recipient.signature_type = signature_type
    recipient.document_hash = content_hash
    recipient.ip_address = ip_address
    recipient.user_agent = user_agent

    # Log activity
    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="signed",
        actor_email=recipient.email,
        actor_name=recipient.name,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata_json=json.dumps({
            "document_hash": content_hash,
            "signature_type": signature_type,
        }),
    )
    db.add(activity)

    # Flush so the recipient update is visible to subsequent queries
    await db.flush()

    # Check if all signers have signed
    await db.refresh(proposal)
    signers = [r for r in proposal.recipients if r.role == "signer"]
    all_signed = all(r.signed_at is not None for r in signers)

    if all_signed:
        proposal.status = ProposalStatus.SIGNED
        proposal.signed_at = datetime.now(timezone.utc)

        # Notify proposal creator
        from app.notifications.service import create_notification
        await create_notification(
            db,
            user_id=proposal.created_by,
            type="proposal_signed",
            title="Proposal Signed",
            message=f'"{proposal.title}" has been signed by all recipients',
            resource_type="proposal",
            resource_id=str(proposal.id),
        )
    else:
        proposal.status = ProposalStatus.WAITING_SIGNATURE

    await db.commit()
    await db.refresh(proposal)

    return {
        "signed": True,
        "all_signed": all_signed,
        "redirect_to_payment": all_signed and proposal.collect_payment,
        "proposal_id": str(proposal.id),
    }


# ---------------------------------------------------------------------------
# Payment integration
# ---------------------------------------------------------------------------

async def create_proposal_checkout(
    db: AsyncSession,
    proposal_id: uuid.UUID,
    settings,
    base_url: str = "",
) -> dict:
    """Create a Stripe checkout session for a signed proposal."""
    import stripe as stripe_lib

    proposal = await get_proposal(db, proposal_id)

    if proposal.status != ProposalStatus.SIGNED:
        raise ValidationError("Proposal must be signed before payment")
    if not proposal.collect_payment:
        raise ValidationError("This proposal doesn't require payment")
    if not settings.stripe_secret_key:
        raise ValidationError("Stripe is not configured")

    stripe_lib.api_key = settings.stripe_secret_key
    amount_cents = int(proposal.value * 100)
    origin = base_url.rstrip("/") if base_url else settings.public_base_url

    session_params = {
        "payment_method_types": ["card"],
        "line_items": [{
            "price_data": {
                "currency": proposal.currency.lower(),
                "product_data": {
                    "name": f"Proposal: {proposal.title}",
                    "description": f"Payment for proposal {proposal.proposal_number}",
                },
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        "success_url": f"{origin}/proposals/{proposal.id}?payment=success",
        "cancel_url": f"{origin}/proposals/{proposal.id}?payment=cancelled",
        "metadata": {
            "proposal_id": str(proposal.id),
            "proposal_number": proposal.proposal_number,
        },
    }

    if proposal.payment_mode == "recurring" and proposal.payment_frequency:
        interval_map = {
            "weekly": ("week", 1),
            "biweekly": ("week", 2),
            "monthly": ("month", 1),
            "quarterly": ("month", 3),
            "yearly": ("year", 1),
        }
        interval, count = interval_map.get(proposal.payment_frequency, ("month", 1))
        session_params["mode"] = "subscription"
        session_params["line_items"] = [{
            "price_data": {
                "currency": proposal.currency.lower(),
                "product_data": {
                    "name": f"Proposal: {proposal.title}",
                },
                "unit_amount": amount_cents,
                "recurring": {
                    "interval": interval,
                    "interval_count": count,
                },
            },
            "quantity": 1,
        }]
    else:
        session_params["mode"] = "payment"

    session = stripe_lib.checkout.Session.create(**session_params)

    proposal.stripe_checkout_session_id = session.id
    proposal.payment_status = PaymentStatus.PROCESSING

    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="payment_initiated",
        metadata_json=json.dumps({"checkout_session_id": session.id}),
    )
    db.add(activity)

    await db.commit()

    return {"checkout_url": session.url, "session_id": session.id}


async def handle_proposal_payment_webhook(
    db: AsyncSession,
    proposal_id_str: str,
    payment_intent_id: str | None = None,
) -> None:
    """Handle Stripe webhook for proposal payment completion."""
    proposal_id = uuid.UUID(proposal_id_str)
    proposal = await get_proposal(db, proposal_id)

    proposal.payment_status = PaymentStatus.PAID
    proposal.status = ProposalStatus.PAID
    proposal.paid_at = datetime.now(timezone.utc)

    activity = ProposalActivity(
        proposal_id=proposal.id,
        action="paid",
        metadata_json=json.dumps({"payment_intent_id": payment_intent_id}),
    )
    db.add(activity)

    # Create income record in cashbook
    from app.income.models import Income, IncomeCategory
    from datetime import date as date_type
    income = Income(
        contact_id=proposal.contact_id,
        category=IncomeCategory.SERVICE,
        description=f"Proposal payment: {proposal.title} ({proposal.proposal_number})",
        amount=proposal.value,
        currency=proposal.currency,
        date=date_type.today(),
        payment_method="stripe",
        reference=payment_intent_id or proposal.stripe_checkout_session_id,
        created_by=proposal.created_by,
    )
    db.add(income)

    await db.commit()

    # Notify creator
    from app.notifications.service import create_notification
    await create_notification(
        db,
        user_id=proposal.created_by,
        type="payment_received",
        title="Payment Received",
        message=f'Payment received for "{proposal.title}" - ${proposal.value}',
        resource_type="proposal",
        resource_id=str(proposal.id),
    )


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

async def get_proposal_stats(db: AsyncSession) -> dict:
    """Get proposal dashboard statistics."""
    result = await db.execute(select(Proposal))
    proposals = list(result.scalars().all())

    stats = {
        "total_proposals": len(proposals),
        "draft_count": sum(1 for p in proposals if p.status == ProposalStatus.DRAFT),
        "sent_count": sum(1 for p in proposals if p.status == ProposalStatus.SENT),
        "viewed_count": sum(1 for p in proposals if p.status == ProposalStatus.VIEWED),
        "signed_count": sum(1 for p in proposals if p.status == ProposalStatus.SIGNED),
        "declined_count": sum(1 for p in proposals if p.status == ProposalStatus.DECLINED),
        "paid_count": sum(1 for p in proposals if p.status == ProposalStatus.PAID),
        "total_value": sum((p.value for p in proposals), Decimal("0")),
        "signed_value": sum((p.value for p in proposals if p.status in (ProposalStatus.SIGNED, ProposalStatus.PAID)), Decimal("0")),
        "paid_value": sum((p.value for p in proposals if p.status == ProposalStatus.PAID), Decimal("0")),
    }
    return stats


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

async def create_template(db: AsyncSession, data: TemplateCreate, user: User) -> ProposalTemplate:
    """Create a proposal template."""
    template = ProposalTemplate(
        title=data.title,
        description=data.description,
        content_json=data.content_json,
        created_by=user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_templates(db: AsyncSession, pagination: PaginationParams) -> tuple[list[ProposalTemplate], dict]:
    """List all templates."""
    count_result = await db.execute(
        select(func.count()).select_from(ProposalTemplate)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ProposalTemplate)
        .order_by(ProposalTemplate.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    templates = list(result.scalars().all())
    meta = build_pagination_meta(total, pagination)
    return templates, meta


async def get_template(db: AsyncSession, template_id: uuid.UUID) -> ProposalTemplate:
    """Get a single template."""
    result = await db.execute(
        select(ProposalTemplate).where(ProposalTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise NotFoundError("ProposalTemplate", str(template_id))
    return template


async def update_template(db: AsyncSession, template_id: uuid.UUID, data: TemplateUpdate, user: User) -> ProposalTemplate:
    """Update a template."""
    template = await get_template(db, template_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template_id: uuid.UUID) -> None:
    """Delete a template."""
    template = await get_template(db, template_id)
    await db.delete(template)
    await db.commit()


async def convert_to_template(db: AsyncSession, proposal_id: uuid.UUID, user: User) -> ProposalTemplate:
    """Convert an existing proposal into a reusable template."""
    proposal = await get_proposal(db, proposal_id, user)
    template = ProposalTemplate(
        title=f"Template: {proposal.title}",
        description=f"Created from proposal {proposal.proposal_number}",
        content_json=proposal.content_json,
        created_by=user.id,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


# ---------------------------------------------------------------------------
# Add/update recipients
# ---------------------------------------------------------------------------

async def add_recipient(db: AsyncSession, proposal_id: uuid.UUID, data: RecipientCreate) -> ProposalRecipient:
    """Add a recipient to a proposal."""
    proposal = await get_proposal(db, proposal_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise ValidationError("Can only add recipients to draft proposals")

    recipient = ProposalRecipient(
        proposal_id=proposal_id,
        email=data.email,
        name=data.name,
        role=data.role,
        signing_order=data.signing_order,
        signing_token=secrets.token_urlsafe(32),
    )
    db.add(recipient)
    await db.commit()
    await db.refresh(recipient)
    return recipient


async def remove_recipient(db: AsyncSession, proposal_id: uuid.UUID, recipient_id: uuid.UUID) -> None:
    """Remove a recipient from a draft proposal."""
    proposal = await get_proposal(db, proposal_id)
    if proposal.status != ProposalStatus.DRAFT:
        raise ValidationError("Can only remove recipients from draft proposals")

    result = await db.execute(
        select(ProposalRecipient).where(
            ProposalRecipient.id == recipient_id,
            ProposalRecipient.proposal_id == proposal_id,
        )
    )
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise NotFoundError("ProposalRecipient", str(recipient_id))

    await db.delete(recipient)
    await db.commit()


# ---------------------------------------------------------------------------
# GHL Sync
# ---------------------------------------------------------------------------

async def log_ghl_sync(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    direction: SyncDirection,
    status: SyncStatus,
    ghl_entity_id: str | None = None,
    error_message: str | None = None,
    user_id: uuid.UUID | None = None,
) -> GhlSyncLog:
    """Log a GHL sync event."""
    log = GhlSyncLog(
        entity_type=entity_type,
        entity_id=entity_id,
        ghl_entity_id=ghl_entity_id,
        direction=direction,
        status=status,
        error_message=error_message,
        created_by=user_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_ghl_sync_logs(
    db: AsyncSession,
    pagination: PaginationParams,
    entity_type: str | None = None,
) -> tuple[list[GhlSyncLog], dict]:
    """List GHL sync logs."""
    query = select(GhlSyncLog)
    if entity_type:
        query = query.where(GhlSyncLog.entity_type == entity_type)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    query = query.order_by(GhlSyncLog.synced_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    logs = list(result.scalars().all())
    meta = build_pagination_meta(total, pagination)
    return logs, meta


async def get_ghl_settings(db: AsyncSession, settings) -> dict:
    """Get GHL connection status."""
    count_result = await db.execute(
        select(func.count()).select_from(GhlSyncLog)
    )
    sync_count = count_result.scalar() or 0

    last_result = await db.execute(
        select(GhlSyncLog.synced_at)
        .order_by(GhlSyncLog.synced_at.desc())
        .limit(1)
    )
    last_sync = last_result.scalar()

    return {
        "connected": bool(getattr(settings, "ghl_api_key", "")),
        "ghl_location_id": getattr(settings, "ghl_location_id", None),
        "last_sync_at": last_sync,
        "sync_count": sync_count,
    }


# ---------------------------------------------------------------------------
# Follow-up rules
# ---------------------------------------------------------------------------

async def create_follow_up_rule(db: AsyncSession, data: FollowUpRuleCreate, user: User) -> FollowUpRule:
    """Create a follow-up rule."""
    rule = FollowUpRule(
        resource_type=data.resource_type,
        resource_id=data.resource_id,
        trigger_event=data.trigger_event,
        delay_hours=data.delay_hours,
        message_template=data.message_template,
        channel=data.channel,
        created_by=user.id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_follow_up_rules(
    db: AsyncSession,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
) -> list[FollowUpRule]:
    """List follow-up rules with optional filters."""
    query = select(FollowUpRule).where(FollowUpRule.is_active.is_(True))
    if resource_type:
        query = query.where(FollowUpRule.resource_type == resource_type)
    if resource_id:
        query = query.where(FollowUpRule.resource_id == resource_id)

    result = await db.execute(query.order_by(FollowUpRule.created_at.desc()))
    return list(result.scalars().all())


async def toggle_follow_up_rule(db: AsyncSession, rule_id: uuid.UUID, is_active: bool) -> FollowUpRule:
    """Enable or disable a follow-up rule."""
    result = await db.execute(
        select(FollowUpRule).where(FollowUpRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("FollowUpRule", str(rule_id))

    rule.is_active = is_active
    await db.commit()
    await db.refresh(rule)
    return rule


async def process_pending_follow_ups(db: AsyncSession, settings) -> int:
    """Process all pending follow-ups (called by a scheduler/cron)."""
    now = datetime.now(timezone.utc)
    count = 0

    # Get active rules
    result = await db.execute(
        select(FollowUpRule).where(FollowUpRule.is_active.is_(True))
    )
    rules = list(result.scalars().all())

    for rule in rules:
        if rule.resource_type == "proposal":
            proposal_result = await db.execute(
                select(Proposal).where(Proposal.id == rule.resource_id)
            )
            proposal = proposal_result.scalar_one_or_none()
            if not proposal:
                continue

            # Check if follow-up is due
            if rule.trigger_event == "not_signed" and proposal.sent_at:
                hours_since_sent = (now - proposal.sent_at).total_seconds() / 3600
                if hours_since_sent >= rule.delay_hours and proposal.status in (ProposalStatus.SENT, ProposalStatus.VIEWED):
                    # Check if we already sent recently
                    if rule.last_sent_at:
                        hours_since_last = (now - rule.last_sent_at).total_seconds() / 3600
                        if hours_since_last < rule.delay_hours:
                            continue

                    # TODO: Send follow-up email/SMS via email service
                    rule.last_sent_at = now
                    rule.send_count += 1

                    activity = ProposalActivity(
                        proposal_id=proposal.id,
                        action="follow_up_sent",
                        metadata_json=json.dumps({
                            "channel": rule.channel,
                            "send_count": rule.send_count,
                        }),
                    )
                    db.add(activity)
                    count += 1

    await db.commit()
    return count
