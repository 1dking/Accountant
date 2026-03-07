"""KYC API router."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.core.exceptions import NotFoundError, ValidationError
from app.dependencies import get_current_user, get_db, require_role
from app.kyc.models import KycStatus, KycVerification
from app.kyc.schemas import KycReviewRequest, KycResponse, KycSubmitRequest

router = APIRouter()


def _kyc_to_response(kyc: KycVerification) -> KycResponse:
    """Convert a KycVerification ORM instance to a KycResponse."""
    return KycResponse(
        id=str(kyc.id),
        status=kyc.status,
        business_name=kyc.business_name,
        business_type=kyc.business_type,
        business_phone=kyc.business_phone,
        full_name=kyc.full_name,
        review_notes=kyc.review_notes,
        reviewed_at=kyc.reviewed_at.isoformat() if kyc.reviewed_at else None,
        created_at=kyc.created_at.isoformat(),
        updated_at=kyc.updated_at.isoformat(),
    )


@router.get("/status")
async def get_kyc_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Get the current user's KYC status."""
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        return {"data": {"status": "not_started"}}
    return {"data": _kyc_to_response(kyc)}


@router.post("/submit")
async def submit_kyc(
    data: KycSubmitRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Submit or update KYC verification."""
    result = await db.execute(
        select(KycVerification).where(KycVerification.user_id == user.id)
    )
    kyc = result.scalar_one_or_none()

    if kyc and kyc.status == KycStatus.APPROVED.value:
        raise ValidationError("KYC already approved. Cannot resubmit.")

    if not kyc:
        kyc = KycVerification(id=uuid.uuid4(), user_id=user.id)
        db.add(kyc)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(kyc, field, value)

    kyc.status = KycStatus.SUBMITTED.value
    await db.commit()
    await db.refresh(kyc)

    return {"data": _kyc_to_response(kyc)}


@router.get("/admin/list")
async def admin_list_kyc(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_role([Role.ADMIN]))],
):
    """Admin: list all KYC submissions."""
    result = await db.execute(
        select(KycVerification).order_by(KycVerification.created_at.desc())
    )
    submissions = result.scalars().all()
    return {"data": [_kyc_to_response(kyc) for kyc in submissions]}


@router.post("/admin/review/{kyc_id}")
async def admin_review_kyc(
    kyc_id: uuid.UUID,
    data: KycReviewRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_role([Role.ADMIN]))],
):
    """Admin: approve or reject a KYC submission."""
    result = await db.execute(
        select(KycVerification).where(KycVerification.id == kyc_id)
    )
    kyc = result.scalar_one_or_none()
    if not kyc:
        raise NotFoundError("KycVerification", str(kyc_id))

    if data.status not in ("approved", "rejected"):
        raise ValidationError("Status must be 'approved' or 'rejected'.")

    kyc.status = data.status
    kyc.review_notes = data.review_notes
    kyc.reviewed_by = admin.id
    kyc.reviewed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(kyc)

    return {"data": _kyc_to_response(kyc)}
