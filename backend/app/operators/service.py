"""Operator (agency) service — provision client sub-accounts, toggle their
modules, unlock/lock the books, invite their users.

An OPERATOR is an admin User who is not themselves inside a sub-account. The
operator's own row carries operator_id == its own id (set lazily on first
provision, per the models docstring); sub-account members carry the
operator's id plus their sub_account_id, which is what
core.authorization partitions on. Nothing here touches ledgers.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.features import ALL_FEATURES
from app.auth.models import Role, User
from app.auth.service import create_user
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.operators import presets
from app.operators.models import OnboardingTemplate, SubAccount, SubAccountFeature, SubAccountStatus
from app.core.exceptions import ValidationError
from app.operators.schemas import (
    MemberInvite,
    MemberOut,
    SubAccountCreate,
    SubAccountOut,
    SubAccountUpdate,
    TemplateInfo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Who may operate
# ---------------------------------------------------------------------------


def require_operator(user: User) -> None:
    """Admin at the agency level — not a user living inside a client tenant."""
    if user.role != Role.ADMIN:
        raise ForbiddenError("Only an admin can manage client accounts.")
    if user.sub_account_id is not None:
        raise ForbiddenError("Client accounts are managed from the agency level, not from inside a client.")


async def _ensure_operator_id(db: AsyncSession, user: User) -> uuid.UUID:
    """The operator's own row must point at itself so its staff and sub-accounts
    can be grouped under it. Legacy root users (NULL/NULL) get promoted on first
    provision — their existing data stays in the legacy tenant partition, which
    is exactly the pre-Phase-2 behaviour, so nothing they already see changes."""
    if user.operator_id is None:
        user.operator_id = user.id
        await db.flush()
    return user.operator_id


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:100] or uuid.uuid4().hex[:8]


async def _to_out(db: AsyncSession, sa: SubAccount) -> SubAccountOut:
    denies = {f.feature_key: f.enabled for f in sa.features}
    features = {k: denies.get(k, True) for k in ALL_FEATURES}
    member_count = (await db.execute(
        select(func.count(User.id)).where(User.sub_account_id == sa.id)
    )).scalar_one()
    # Explicit column copy — `model_validate(sa)` would read the ORM `features`
    # relationship (a list of deny rows) into the dict field and 500.
    computed = {"features", "books_enabled", "member_count"}
    cols = {k: getattr(sa, k) for k in SubAccountOut.model_fields if k not in computed}
    return SubAccountOut(
        **cols,
        features=features,
        books_enabled=all(features.get(k, True) for k in presets.BOOKS_FEATURES),
        member_count=int(member_count or 0),
    )


async def list_sub_accounts(db: AsyncSession, operator: User) -> list[SubAccountOut]:
    require_operator(operator)
    stmt = (
        select(SubAccount)
        .options(selectinload(SubAccount.features))
        .where(SubAccount.operator_user_id == operator.id)
        .order_by(SubAccount.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().unique().all()
    return [await _to_out(db, sa) for sa in rows]


async def _get(db: AsyncSession, operator: User, sub_account_id: uuid.UUID) -> SubAccount:
    require_operator(operator)
    stmt = (
        select(SubAccount)
        .options(selectinload(SubAccount.features))
        .where(SubAccount.id == sub_account_id, SubAccount.operator_user_id == operator.id)
    )
    sa = (await db.execute(stmt)).scalar_one_or_none()
    if sa is None:
        raise NotFoundError("SubAccount", str(sub_account_id))
    return sa


async def get_sub_account(db: AsyncSession, operator: User, sub_account_id: uuid.UUID) -> SubAccountOut:
    return await _to_out(db, await _get(db, operator, sub_account_id))


def templates() -> list[TemplateInfo]:
    return [
        TemplateInfo(key=t, label=presets.TEMPLATE_LABELS[t][0], description=presets.TEMPLATE_LABELS[t][1],
                     denies=list(presets.TEMPLATE_DENIES[t]))
        for t in OnboardingTemplate
    ]


# ---------------------------------------------------------------------------
# Provision
# ---------------------------------------------------------------------------


async def create_sub_account(db: AsyncSession, operator: User, data: SubAccountCreate) -> SubAccountOut:
    require_operator(operator)
    op_id = await _ensure_operator_id(db, operator)

    name = data.name.strip()
    if not name:
        raise ValidationError("Client name is required")
    # (operator_user_id, name) is UNIQUE — check first so a repeat is a clean
    # 4xx with a message the agency can act on, not an IntegrityError 500.
    if (await db.execute(
        select(SubAccount.id).where(SubAccount.operator_user_id == operator.id, SubAccount.name == name)
    )).scalar_one_or_none():
        raise ValidationError(f"You already have a client account named '{name}'")

    slug = data.slug or _slugify(name)
    if (await db.execute(select(SubAccount.id).where(SubAccount.slug == slug))).scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"

    sa = SubAccount(
        operator_user_id=operator.id, name=name, slug=slug,
        status=SubAccountStatus.ACTIVE, data_entry_mode=data.data_entry_mode,
        crm_style=data.crm_style, template=data.template, notes=data.notes,
        created_by=operator.id,
    )
    db.add(sa)
    await db.flush()

    # Seed the preset: only denies are rows (absence = allowed).
    for key in presets.TEMPLATE_DENIES.get(data.template, ()):
        db.add(SubAccountFeature(sub_account_id=sa.id, feature_key=key, enabled=False))

    if data.client_email:
        await _invite(db, operator, sa, MemberInvite(
            email=data.client_email, full_name=data.client_name or data.client_email.split("@")[0], role="admin",
        ), op_id)

    await db.commit()
    return await get_sub_account(db, operator, sa.id)


async def update_sub_account(db: AsyncSession, operator: User, sub_account_id: uuid.UUID, data: SubAccountUpdate) -> SubAccountOut:
    sa = await _get(db, operator, sub_account_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sa, k, v)
    await db.commit()
    return await get_sub_account(db, operator, sa.id)


# ---------------------------------------------------------------------------
# Features / books
# ---------------------------------------------------------------------------


async def _set_feature_row(db: AsyncSession, sa: SubAccount, key: str, enabled: bool) -> None:
    if key not in ALL_FEATURES:
        raise ValidationError(f"Unknown feature: {key}")
    row = next((f for f in sa.features if f.feature_key == key), None)
    if enabled:
        # Allowed = no row. Delete the deny if present.
        if row is not None:
            await db.delete(row)
            sa.features.remove(row)
    else:
        if row is None:
            row = SubAccountFeature(sub_account_id=sa.id, feature_key=key, enabled=False)
            db.add(row)
            sa.features.append(row)
        else:
            row.enabled = False


async def set_feature(db: AsyncSession, operator: User, sub_account_id: uuid.UUID, key: str, enabled: bool) -> SubAccountOut:
    sa = await _get(db, operator, sub_account_id)
    await _set_feature_row(db, sa, key, enabled)
    await db.commit()
    return await get_sub_account(db, operator, sa.id)


async def set_books(db: AsyncSession, operator: User, sub_account_id: uuid.UUID, enabled: bool) -> SubAccountOut:
    """Unlock (or lock) the whole accounting bundle in one action — what a
    client's accountant asks the agency for when they take the books on."""
    sa = await _get(db, operator, sub_account_id)
    for key in presets.BOOKS_FEATURES:
        await _set_feature_row(db, sa, key, enabled)
    await db.commit()
    logger.info("operators: books %s for sub-account %s by %s", "unlocked" if enabled else "locked", sa.id, operator.id)
    return await get_sub_account(db, operator, sa.id)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def list_members(db: AsyncSession, operator: User, sub_account_id: uuid.UUID) -> list[MemberOut]:
    sa = await _get(db, operator, sub_account_id)
    rows = (await db.execute(
        select(User).where(User.sub_account_id == sa.id).order_by(User.created_at)
    )).scalars().all()
    return [MemberOut(id=u.id, email=u.email, full_name=u.full_name or "", role=u.role.value, is_active=u.is_active) for u in rows]


async def _invite(db: AsyncSession, operator: User, sa: SubAccount, data: MemberInvite, op_id: uuid.UUID) -> User:
    if sa.status != SubAccountStatus.ACTIVE:
        raise ConflictError("This client account is not active.")
    try:
        role = Role(data.role)
    except ValueError as e:
        raise ValidationError(f"Unknown role: {data.role}") from e
    user = await create_user(db, email=data.email, password=data.password, full_name=data.full_name, role=role)
    user.sub_account_id = sa.id
    user.operator_id = op_id
    await db.flush()
    return user


async def invite_member(db: AsyncSession, operator: User, sub_account_id: uuid.UUID, data: MemberInvite) -> MemberOut:
    sa = await _get(db, operator, sub_account_id)
    op_id = await _ensure_operator_id(db, operator)
    user = await _invite(db, operator, sa, data, op_id)
    await db.commit()
    return MemberOut(id=user.id, email=user.email, full_name=user.full_name or "", role=user.role.value, is_active=user.is_active)
