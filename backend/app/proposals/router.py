"""FastAPI router for the proposals module."""

import uuid
from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.pagination import PaginationParams, get_pagination
from app.core.idempotency import IdempotencyResult, require_idempotency_key
from app.dependencies import get_current_user, get_db, require_role
from app.proposals.models import ProposalStatus, PaymentStatus
from app.proposals.schemas import (
    ActivityResponse,
    FollowUpRuleCreate,
    FollowUpRuleResponse,
    GhlManualSyncRequest,
    GhlSettingsResponse,
    GhlSyncLogResponse,
    ProposalCreate,
    ProposalDashboardStats,
    ProposalFilter,
    ProposalListItem,
    ProposalResponse,
    ProposalUpdate,
    RecipientCreate,
    RecipientResponse,
    SignProposalRequest,
    SigningPageData,
    TemplateCreate,
    TemplateListItem,
    TemplateResponse,
    TemplateUpdate,
)
from app.proposals import service

router = APIRouter()


# ---------------------------------------------------------------------------
# Proposal CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_proposals(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    search: str | None = Query(None),
    status: ProposalStatus | None = Query(None),
    contact_id: uuid.UUID | None = Query(None),
    payment_status: PaymentStatus | None = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    value_min: float | None = Query(None),
    value_max: float | None = Query(None),
) -> dict:
    """List proposals with filtering and pagination."""
    from decimal import Decimal
    filters = ProposalFilter(
        search=search,
        status=status,
        contact_id=contact_id,
        payment_status=payment_status,
        date_from=date_from,
        date_to=date_to,
        value_min=Decimal(str(value_min)) if value_min is not None else None,
        value_max=Decimal(str(value_max)) if value_max is not None else None,
    )
    proposals, meta = await service.list_proposals(db, filters, pagination)
    return {"data": [ProposalListItem.model_validate(p) for p in proposals], "meta": meta}


@router.get("/stats")
async def proposal_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get proposal dashboard statistics."""
    stats = await service.get_proposal_stats(db)
    return {"data": ProposalDashboardStats(**stats)}


@router.post("", status_code=201)
async def create_proposal(
    data: ProposalCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    idempotency: Annotated[IdempotencyResult, Depends(require_idempotency_key)],
) -> dict:
    """Create a new proposal."""
    if idempotency.cached_response is not None:
        return idempotency.cached_response
    proposal = await service.create_proposal(db, data, current_user)
    result = {"data": ProposalResponse.model_validate(proposal)}
    await idempotency.save(result, status_code=201)
    return result


@router.get("/templates")
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
) -> dict:
    """List proposal templates."""
    templates, meta = await service.list_templates(db, pagination)
    return {"data": [TemplateListItem.model_validate(t) for t in templates], "meta": meta}


@router.post("/templates", status_code=201)
async def create_template(
    data: TemplateCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a proposal template."""
    template = await service.create_template(db, data, current_user)
    return {"data": TemplateResponse.model_validate(template)}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single template."""
    template = await service.get_template(db, template_id)
    return {"data": TemplateResponse.model_validate(template)}


@router.put("/templates/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update a template."""
    template = await service.update_template(db, template_id, data, _)
    return {"data": TemplateResponse.model_validate(template)}


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Delete a template."""
    await service.delete_template(db, template_id)
    return {"data": {"message": "Template deleted"}}


# ---------------------------------------------------------------------------
# GHL Sync
# ---------------------------------------------------------------------------


@router.get("/ghl/settings")
async def ghl_settings(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get GHL connection status."""
    settings = request.app.state.settings
    data = await service.get_ghl_settings(db, settings)
    return {"data": GhlSettingsResponse(**data)}


@router.get("/ghl/logs")
async def ghl_sync_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    entity_type: str | None = Query(None),
) -> dict:
    """List GHL sync logs."""
    logs, meta = await service.list_ghl_sync_logs(db, pagination, entity_type)
    return {"data": [GhlSyncLogResponse.model_validate(l) for l in logs], "meta": meta}


@router.post("/ghl/sync")
async def manual_ghl_sync(
    body: GhlManualSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Trigger manual GHL sync (placeholder - needs GHL API key)."""
    # In production, this would call the actual GHL API
    from app.proposals.models import SyncDirection, SyncStatus
    log = await service.log_ghl_sync(
        db,
        entity_type=body.entity_type,
        entity_id=uuid.uuid4(),  # placeholder
        direction=SyncDirection(body.direction),
        status=SyncStatus.PENDING,
        user_id=current_user.id,
    )
    return {"data": GhlSyncLogResponse.model_validate(log)}


# ---------------------------------------------------------------------------
# Follow-up rules
# ---------------------------------------------------------------------------


@router.get("/follow-ups")
async def list_follow_ups(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    resource_type: str | None = Query(None),
    resource_id: uuid.UUID | None = Query(None),
) -> dict:
    """List active follow-up rules."""
    rules = await service.list_follow_up_rules(db, resource_type, resource_id)
    return {"data": [FollowUpRuleResponse.model_validate(r) for r in rules]}


@router.post("/follow-ups", status_code=201)
async def create_follow_up(
    data: FollowUpRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Create a follow-up rule."""
    rule = await service.create_follow_up_rule(db, data, current_user)
    return {"data": FollowUpRuleResponse.model_validate(rule)}


@router.put("/follow-ups/{rule_id}/toggle")
async def toggle_follow_up(
    rule_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
    active: bool = Query(True),
) -> dict:
    """Enable or disable a follow-up rule."""
    rule = await service.toggle_follow_up_rule(db, rule_id, active)
    return {"data": FollowUpRuleResponse.model_validate(rule)}


# ---------------------------------------------------------------------------
# Signing (public - no auth required)
# ---------------------------------------------------------------------------


@router.get("/sign/{signing_token}")
async def get_signing_page(
    signing_token: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get proposal data for public signing page (no auth required)."""
    # Track view
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    data = await service.get_signing_data(db, signing_token)

    # Mark as viewed
    await service.mark_viewed(db, data["proposal_id"], ip_address=ip, user_agent=ua)

    return {"data": data}


@router.post("/sign/{signing_token}")
async def sign_proposal(
    signing_token: str,
    body: SignProposalRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Sign a proposal (public - no auth required)."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    result = await service.sign_proposal(
        db,
        signing_token=signing_token,
        recipient_id=body.recipient_id,
        signature_data=body.signature_data,
        signature_type=body.signature_type,
        ip_address=ip,
        user_agent=ua,
    )
    return {"data": result}


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------


@router.post("/{proposal_id}/checkout")
async def create_checkout(
    proposal_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create Stripe checkout session for a signed proposal (public or authenticated)."""
    settings = request.app.state.settings
    base_url = str(request.base_url).rstrip("/")
    result = await service.create_proposal_checkout(db, proposal_id, settings, base_url)
    return {"data": result}


# ---------------------------------------------------------------------------
# Proposal detail endpoints (must come AFTER /templates, /sign, etc.)
# ---------------------------------------------------------------------------


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Get a single proposal with all details."""
    proposal = await service.get_proposal(db, proposal_id)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.put("/{proposal_id}")
async def update_proposal(
    proposal_id: uuid.UUID,
    data: ProposalUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Update a proposal."""
    proposal = await service.update_proposal(db, proposal_id, data, current_user)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.delete("/{proposal_id}")
async def delete_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ADMIN]))],
) -> dict:
    """Delete a proposal."""
    await service.delete_proposal(db, proposal_id, current_user)
    return {"data": {"message": "Proposal deleted"}}


@router.post("/{proposal_id}/send")
async def send_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Send a proposal to recipients."""
    proposal = await service.send_proposal(db, proposal_id, current_user)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.post("/{proposal_id}/clone")
async def clone_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Clone a proposal as a new draft."""
    proposal = await service.clone_proposal(db, proposal_id, current_user)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.post("/{proposal_id}/decline")
async def decline_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Mark proposal as declined."""
    proposal = await service.mark_declined(db, proposal_id, current_user)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.post("/{proposal_id}/complete")
async def complete_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Manually mark proposal as completed/signed."""
    proposal = await service.mark_completed(db, proposal_id, current_user)
    return {"data": ProposalResponse.model_validate(proposal)}


@router.post("/{proposal_id}/convert-template")
async def convert_to_template(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Convert a proposal into a reusable template."""
    template = await service.convert_to_template(db, proposal_id, current_user)
    return {"data": TemplateResponse.model_validate(template)}


# Recipients
@router.post("/{proposal_id}/recipients", status_code=201)
async def add_recipient(
    proposal_id: uuid.UUID,
    data: RecipientCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Add a recipient to a proposal."""
    recipient = await service.add_recipient(db, proposal_id, data)
    return {"data": RecipientResponse.model_validate(recipient)}


@router.delete("/{proposal_id}/recipients/{recipient_id}")
async def remove_recipient(
    proposal_id: uuid.UUID,
    recipient_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ACCOUNTANT, Role.ADMIN]))],
) -> dict:
    """Remove a recipient from a draft proposal."""
    await service.remove_recipient(db, proposal_id, recipient_id)
    return {"data": {"message": "Recipient removed"}}
