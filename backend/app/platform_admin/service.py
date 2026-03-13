"""Business logic for platform administration."""

import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import RefreshToken, Role, User
from app.collaboration.models import ActivityLog
from app.platform_admin.models import (
    ErrorLog,
    FeatureFlag,
    OrgFeatureOverride,
    OrgSettingOverride,
    Organization,
    PlatformSetting,
)

# Track app start time for uptime calculation
_start_time = time.time()

# ── Default feature flags ────────────────────────────────────────────────

DEFAULT_FEATURE_FLAGS = [
    {"key": "ai_page_builder", "name": "AI Page Builder", "category": "content", "enabled": True,
     "description": "AI-powered landing page generation and editing"},
    {"key": "obrain", "name": "O-Brain AI Assistant", "category": "ai", "enabled": True,
     "description": "AI chat assistant with tool use capabilities"},
    {"key": "smart_import", "name": "Smart Import", "category": "ai", "enabled": True,
     "description": "AI-powered document and data import"},
    {"key": "calendar", "name": "Calendar & Scheduling", "category": "productivity", "enabled": True,
     "description": "Calendar events, booking pages, and scheduling"},
    {"key": "meetings", "name": "Video Meetings", "category": "communication", "enabled": True,
     "description": "LiveKit-powered video meetings and recordings"},
    {"key": "client_portal", "name": "Client Portal", "category": "client", "enabled": True,
     "description": "Self-service portal for clients to view invoices, proposals, files"},
    {"key": "invoicing", "name": "Invoicing", "category": "accounting", "enabled": True,
     "description": "Invoice creation, sending, and payment tracking"},
    {"key": "proposals", "name": "Proposals & Estimates", "category": "sales", "enabled": True,
     "description": "Proposal and estimate creation with e-signatures"},
    {"key": "email_campaigns", "name": "Email Campaigns", "category": "communication", "enabled": True,
     "description": "Bulk email campaigns and templates"},
    {"key": "sms", "name": "SMS Messaging", "category": "communication", "enabled": True,
     "description": "Twilio-powered SMS sending and receiving"},
    {"key": "expense_tracking", "name": "Expense Tracking", "category": "accounting", "enabled": True,
     "description": "Expense logging, categorization, and receipt scanning"},
    {"key": "booking_pages", "name": "Booking Pages", "category": "scheduling", "enabled": True,
     "description": "Public booking pages for appointment scheduling"},
    {"key": "workflows", "name": "Workflow Automation", "category": "automation", "enabled": True,
     "description": "Automated workflows and triggers"},
    {"key": "forms", "name": "Form Builder", "category": "content", "enabled": True,
     "description": "Custom form creation and submission tracking"},
    {"key": "kyc", "name": "KYC Verification", "category": "compliance", "enabled": True,
     "description": "Know Your Customer identity verification"},
    {"key": "split_testing", "name": "A/B Split Testing", "category": "content", "enabled": True,
     "description": "Split testing for landing pages"},
    {"key": "custom_domains", "name": "Custom Domains", "category": "content", "enabled": True,
     "description": "Custom domain support for published pages"},
    {"key": "plaid_banking", "name": "Plaid Banking", "category": "accounting", "enabled": True,
     "description": "Bank account connection and transaction import via Plaid"},
]

DEFAULT_PRICING_SETTINGS = [
    {"key": "plan_starter_price", "value": "0", "category": "pricing",
     "description": "Starter plan monthly price ($)", "value_type": "number"},
    {"key": "plan_pro_price", "value": "29", "category": "pricing",
     "description": "Pro plan monthly price ($)", "value_type": "number"},
    {"key": "plan_business_price", "value": "79", "category": "pricing",
     "description": "Business plan monthly price ($)", "value_type": "number"},
    {"key": "plan_enterprise_price", "value": "199", "category": "pricing",
     "description": "Enterprise plan monthly price ($)", "value_type": "number"},
    {"key": "obrain_free_messages", "value": "50", "category": "pricing",
     "description": "Free O-Brain messages per month", "value_type": "number"},
    {"key": "obrain_pro_messages", "value": "500", "category": "pricing",
     "description": "Pro O-Brain messages per month", "value_type": "number"},
    {"key": "obrain_unlimited_price", "value": "19", "category": "pricing",
     "description": "Unlimited O-Brain add-on monthly price ($)", "value_type": "number"},
    {"key": "addon_sms_price", "value": "15", "category": "pricing",
     "description": "SMS add-on monthly price ($)", "value_type": "number"},
    {"key": "addon_sms_credits", "value": "500", "category": "pricing",
     "description": "SMS credits per month with add-on", "value_type": "number"},
    {"key": "addon_custom_domain_price", "value": "9", "category": "pricing",
     "description": "Custom domain add-on monthly price ($)", "value_type": "number"},
    {"key": "addon_whitelabel_price", "value": "49", "category": "pricing",
     "description": "White-label add-on monthly price ($)", "value_type": "number"},
    {"key": "max_pages_starter", "value": "3", "category": "limits",
     "description": "Max pages for Starter plan", "value_type": "number"},
    {"key": "max_pages_pro", "value": "25", "category": "limits",
     "description": "Max pages for Pro plan", "value_type": "number"},
    {"key": "max_pages_business", "value": "100", "category": "limits",
     "description": "Max pages for Business plan", "value_type": "number"},
    {"key": "max_storage_starter_gb", "value": "1", "category": "limits",
     "description": "Max storage for Starter plan (GB)", "value_type": "number"},
    {"key": "max_storage_pro_gb", "value": "10", "category": "limits",
     "description": "Max storage for Pro plan (GB)", "value_type": "number"},
    {"key": "max_storage_business_gb", "value": "50", "category": "limits",
     "description": "Max storage for Business plan (GB)", "value_type": "number"},
    # Annual plan pricing ($/mo billed yearly)
    {"key": "plan_starter_annual_price", "value": "81", "category": "pricing",
     "description": "Starter plan annual price ($/mo billed yearly)", "value_type": "number"},
    {"key": "plan_pro_annual_price", "value": "164", "category": "pricing",
     "description": "Pro plan annual price ($/mo billed yearly)", "value_type": "number"},
    {"key": "plan_business_annual_price", "value": "331", "category": "pricing",
     "description": "Business plan annual price ($/mo billed yearly)", "value_type": "number"},
    {"key": "plan_enterprise_annual_price", "value": "499", "category": "pricing",
     "description": "Enterprise plan annual price ($/mo billed yearly)", "value_type": "number"},
    # O-Brain tier pricing (monthly)
    {"key": "obrain_essential_price", "value": "49", "category": "pricing",
     "description": "O-Brain Essential monthly price ($)", "value_type": "number"},
    {"key": "obrain_pro_price", "value": "99", "category": "pricing",
     "description": "O-Brain Pro monthly price ($)", "value_type": "number"},
    {"key": "obrain_coach_price", "value": "199", "category": "pricing",
     "description": "O-Brain Coach monthly price ($)", "value_type": "number"},
    # O-Brain tier pricing (annual $/mo billed yearly)
    {"key": "obrain_essential_annual_price", "value": "41", "category": "pricing",
     "description": "O-Brain Essential annual price ($/mo billed yearly)", "value_type": "number"},
    {"key": "obrain_pro_annual_price", "value": "83", "category": "pricing",
     "description": "O-Brain Pro annual price ($/mo billed yearly)", "value_type": "number"},
    {"key": "obrain_coach_annual_price", "value": "166", "category": "pricing",
     "description": "O-Brain Coach annual price ($/mo billed yearly)", "value_type": "number"},
]


# ── Seed defaults ────────────────────────────────────────────────────────

async def seed_defaults(db: AsyncSession) -> int:
    """Seed default feature flags and settings if they don't exist."""
    count = 0

    for flag_data in DEFAULT_FEATURE_FLAGS:
        existing = await db.execute(
            select(FeatureFlag).where(FeatureFlag.key == flag_data["key"])
        )
        if not existing.scalar_one_or_none():
            db.add(FeatureFlag(**flag_data))
            count += 1

    for setting_data in DEFAULT_PRICING_SETTINGS:
        existing = await db.execute(
            select(PlatformSetting).where(PlatformSetting.key == setting_data["key"])
        )
        if not existing.scalar_one_or_none():
            db.add(PlatformSetting(**setting_data))
            count += 1

    if count:
        await db.commit()
    return count


# ── Dashboard metrics ────────────────────────────────────────────────────

async def get_dashboard_metrics(db: AsyncSession) -> dict:
    """Gather platform-wide metrics for the admin dashboard."""
    from app.documents.models import Document
    from app.invoicing.models import Invoice
    from app.contacts.models import Contact
    from app.proposals.models import Proposal
    from app.accounting.models import Expense
    from app.pages.models import Page

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # User counts
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    )).scalar() or 0

    # Users by role
    role_counts = (await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )).all()
    users_by_role = {str(r.value) if hasattr(r, 'value') else str(r): c for r, c in role_counts}

    # Pages
    total_pages = (await db.execute(select(func.count(Page.id)))).scalar() or 0
    published_pages = (await db.execute(
        select(func.count(Page.id)).where(Page.status == "published")
    )).scalar() or 0

    # Documents
    total_documents = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    storage_used = (await db.execute(
        select(func.coalesce(func.sum(Document.file_size), 0))
    )).scalar() or 0

    # Invoices & revenue
    total_invoices = (await db.execute(select(func.count(Invoice.id)))).scalar() or 0
    total_revenue = float((await db.execute(
        select(func.coalesce(func.sum(Invoice.total), 0))
    )).scalar() or 0)

    # Contacts
    total_contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0

    # Proposals
    total_proposals = (await db.execute(select(func.count(Proposal.id)))).scalar() or 0

    # Expenses
    total_expenses = float((await db.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
    )).scalar() or 0)

    # Registrations by day (last 30 days)
    reg_by_day = (await db.execute(
        select(
            func.date(User.created_at).label("day"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= thirty_days_ago)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )).all()
    registrations_by_day = [{"date": str(d), "count": c} for d, c in reg_by_day]

    # Activity by day (last 30 days)
    act_by_day = (await db.execute(
        select(
            func.date(ActivityLog.created_at).label("day"),
            func.count(ActivityLog.id).label("count"),
        )
        .where(ActivityLog.created_at >= thirty_days_ago)
        .group_by(func.date(ActivityLog.created_at))
        .order_by(func.date(ActivityLog.created_at))
    )).all()
    activity_by_day = [{"date": str(d), "count": c} for d, c in act_by_day]

    # Recent activity (last 20)
    recent_rows = (await db.execute(
        select(ActivityLog, User.full_name, User.email)
        .join(User, ActivityLog.user_id == User.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(20)
    )).all()
    recent_activity = [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "user_name": name,
            "user_email": email,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, name, email in recent_rows
    ]

    # Split tests
    try:
        from app.pages.models import SplitTest
        active_split_tests = (await db.execute(
            select(func.count(SplitTest.id)).where(SplitTest.status == "running")
        )).scalar() or 0
    except Exception:
        active_split_tests = 0

    # Meetings
    try:
        from app.meetings.models import Meeting
        total_meetings = (await db.execute(select(func.count(Meeting.id)))).scalar() or 0
    except Exception:
        total_meetings = 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_pages": total_pages,
        "published_pages": published_pages,
        "total_documents": total_documents,
        "storage_used_bytes": storage_used,
        "total_invoices": total_invoices,
        "total_revenue": total_revenue,
        "total_contacts": total_contacts,
        "total_proposals": total_proposals,
        "total_expenses": total_expenses,
        "total_meetings": total_meetings,
        "active_split_tests": active_split_tests,
        "users_by_role": users_by_role,
        "registrations_by_day": registrations_by_day,
        "activity_by_day": activity_by_day,
        "recent_activity": recent_activity,
    }


# ── Feature flags ────────────────────────────────────────────────────────

async def list_feature_flags(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(
        select(FeatureFlag).order_by(FeatureFlag.category, FeatureFlag.name)
    )
    return list(result.scalars().all())


async def update_feature_flag(
    db: AsyncSession, key: str, data: dict, user_id: uuid.UUID
) -> FeatureFlag | None:
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    flag = result.scalar_one_or_none()
    if not flag:
        return None
    for field, value in data.items():
        if value is not None:
            setattr(flag, field, value)
    flag.updated_by = user_id
    await db.commit()
    await db.refresh(flag)
    return flag


async def create_feature_flag(db: AsyncSession, data: dict, user_id: uuid.UUID) -> FeatureFlag:
    flag = FeatureFlag(**data, updated_by=user_id)
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag


async def delete_feature_flag(db: AsyncSession, key: str) -> bool:
    result = await db.execute(delete(FeatureFlag).where(FeatureFlag.key == key))
    await db.commit()
    return result.rowcount > 0


# ── Platform settings ────────────────────────────────────────────────────

async def list_platform_settings(
    db: AsyncSession, category: str | None = None
) -> list[PlatformSetting]:
    stmt = select(PlatformSetting).order_by(PlatformSetting.category, PlatformSetting.key)
    if category:
        stmt = stmt.where(PlatformSetting.category == category)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_platform_setting(
    db: AsyncSession, key: str, data: dict, user_id: uuid.UUID
) -> PlatformSetting | None:
    result = await db.execute(select(PlatformSetting).where(PlatformSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting:
        return None
    for field, value in data.items():
        if value is not None:
            setattr(setting, field, value)
    setting.updated_by = user_id
    await db.commit()
    await db.refresh(setting)
    return setting


async def create_platform_setting(
    db: AsyncSession, data: dict, user_id: uuid.UUID
) -> PlatformSetting:
    setting = PlatformSetting(**data, updated_by=user_id)
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


# ── System health ────────────────────────────────────────────────────────

async def get_system_health(db: AsyncSession, settings) -> dict:
    """Check system health across all integrations."""
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)

    # Error counts
    error_count = (await db.execute(
        select(func.count(ErrorLog.id)).where(
            ErrorLog.created_at >= twenty_four_hours_ago,
            ErrorLog.level == "error",
        )
    )).scalar() or 0

    warning_count = (await db.execute(
        select(func.count(ErrorLog.id)).where(
            ErrorLog.created_at >= twenty_four_hours_ago,
            ErrorLog.level == "warning",
        )
    )).scalar() or 0

    # Integration checks
    integrations = []

    # Anthropic
    integrations.append({
        "name": "Anthropic AI",
        "configured": bool(settings.anthropic_api_key),
        "status": "healthy" if settings.anthropic_api_key else "unconfigured",
    })

    # Gemini
    integrations.append({
        "name": "Gemini AI",
        "configured": bool(settings.gemini_api_key),
        "status": "healthy" if settings.gemini_api_key else "unconfigured",
    })

    # OpenAI
    integrations.append({
        "name": "OpenAI",
        "configured": bool(settings.openai_api_key),
        "status": "healthy" if settings.openai_api_key else "unconfigured",
    })

    # Stripe
    integrations.append({
        "name": "Stripe",
        "configured": bool(settings.stripe_secret_key),
        "status": "healthy" if settings.stripe_secret_key else "unconfigured",
    })

    # Twilio
    integrations.append({
        "name": "Twilio SMS",
        "configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "status": "healthy" if settings.twilio_account_sid else "unconfigured",
    })

    # Plaid
    integrations.append({
        "name": "Plaid Banking",
        "configured": bool(settings.plaid_client_id and settings.plaid_secret),
        "status": "healthy" if settings.plaid_client_id else "unconfigured",
    })

    # Google OAuth
    integrations.append({
        "name": "Google OAuth",
        "configured": bool(settings.google_client_id and settings.google_client_secret),
        "status": "healthy" if settings.google_client_id else "unconfigured",
    })

    # LiveKit
    integrations.append({
        "name": "LiveKit Video",
        "configured": bool(settings.livekit_api_key and settings.livekit_api_secret),
        "status": "healthy" if settings.livekit_api_key else "unconfigured",
    })

    # SMTP
    integrations.append({
        "name": "SMTP Email",
        "configured": bool(settings.smtp_host and settings.smtp_username),
        "status": "healthy" if settings.smtp_host else "unconfigured",
    })

    # Cloudflare R2
    integrations.append({
        "name": "Cloudflare R2 Storage",
        "configured": bool(settings.r2_access_key_id),
        "status": "healthy" if settings.r2_access_key_id else "unconfigured",
    })

    # Overall status
    configured_count = sum(1 for i in integrations if i["configured"])
    overall = "healthy"
    if error_count > 10:
        overall = "degraded"
    if error_count > 50:
        overall = "down"

    uptime = int(time.time() - _start_time)

    return {
        "status": overall,
        "database": "healthy",
        "storage": "healthy",
        "uptime_seconds": uptime,
        "integrations": integrations,
        "error_count_24h": error_count,
        "warning_count_24h": warning_count,
    }


# ── Error logs ───────────────────────────────────────────────────────────

async def list_error_logs(
    db: AsyncSession,
    level: str | None = None,
    resolved: bool | None = None,
    page: int = 1,
    page_size: int = 50,
    endpoint: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[ErrorLog], int]:
    stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc())
    count_stmt = select(func.count(ErrorLog.id))

    if level:
        stmt = stmt.where(ErrorLog.level == level)
        count_stmt = count_stmt.where(ErrorLog.level == level)
    if resolved is not None:
        stmt = stmt.where(ErrorLog.resolved == resolved)
        count_stmt = count_stmt.where(ErrorLog.resolved == resolved)
    if endpoint:
        filt = ErrorLog.request_path.ilike(f"%{endpoint}%")
        stmt = stmt.where(filt)
        count_stmt = count_stmt.where(filt)
    if date_from:
        stmt = stmt.where(ErrorLog.created_at >= date_from)
        count_stmt = count_stmt.where(ErrorLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(ErrorLog.created_at <= date_to + " 23:59:59")
        count_stmt = count_stmt.where(ErrorLog.created_at <= date_to + " 23:59:59")

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def resolve_error(db: AsyncSession, error_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        update(ErrorLog)
        .where(ErrorLog.id == error_id)
        .values(resolved=True, resolved_by=user_id)
    )
    await db.commit()
    return result.rowcount > 0


async def log_error(
    db: AsyncSession,
    source: str,
    message: str,
    traceback: str | None = None,
    level: str = "error",
    user_id: uuid.UUID | None = None,
    request_path: str | None = None,
    request_method: str | None = None,
) -> ErrorLog:
    error = ErrorLog(
        source=source,
        message=message,
        traceback=traceback,
        level=level,
        user_id=user_id,
        request_path=request_path,
        request_method=request_method,
    )
    db.add(error)
    await db.commit()
    await db.refresh(error)
    return error


# ── Enhanced user management ─────────────────────────────────────────────

async def get_users_list(
    db: AsyncSession,
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list, int]:
    """Get paginated user list with optional filters."""
    stmt = select(User).order_by(User.created_at.desc())
    count_stmt = select(func.count(User.id))

    if search:
        search_filter = User.email.ilike(f"%{search}%") | User.full_name.ilike(f"%{search}%")
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    if role:
        stmt = stmt.where(User.role == role)
        count_stmt = count_stmt.where(User.role == role)

    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
        count_stmt = count_stmt.where(User.is_active == is_active)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    # Get last login for each user from activity logs
    user_list = []
    for user in users:
        last_login_result = await db.execute(
            select(ActivityLog.created_at)
            .where(ActivityLog.user_id == user.id, ActivityLog.action == "user_login")
            .order_by(ActivityLog.created_at.desc())
            .limit(1)
        )
        last_login = last_login_result.scalar_one_or_none()

        user_list.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
            "auth_provider": user.auth_provider,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": last_login.isoformat() if last_login else None,
        })

    return user_list, total


async def get_user_detail(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Get detailed user info including activity stats."""
    from app.documents.models import Document
    from app.invoicing.models import Invoice
    from app.pages.models import Page

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    # Stats
    page_count = (await db.execute(
        select(func.count(Page.id)).where(Page.created_by == user_id)
    )).scalar() or 0

    doc_count = (await db.execute(
        select(func.count(Document.id)).where(Document.uploaded_by == user_id)
    )).scalar() or 0

    invoice_count = (await db.execute(
        select(func.count(Invoice.id)).where(Invoice.created_by == user_id)
    )).scalar() or 0

    activity_count = (await db.execute(
        select(func.count(ActivityLog.id)).where(ActivityLog.user_id == user_id)
    )).scalar() or 0

    # Last login
    last_login_result = await db.execute(
        select(ActivityLog.created_at)
        .where(ActivityLog.user_id == user_id, ActivityLog.action == "user_login")
        .order_by(ActivityLog.created_at.desc())
        .limit(1)
    )
    last_login = last_login_result.scalar_one_or_none()

    # Recent activity
    recent_rows = (await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == user_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(20)
    )).scalars().all()

    recent_activity = [
        {
            "id": str(a.id),
            "action": a.action,
            "resource_type": a.resource_type,
            "resource_id": a.resource_id,
            "details": a.details,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in recent_rows
    ]

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_active": user.is_active,
        "auth_provider": user.auth_provider,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "last_login": last_login.isoformat() if last_login else None,
        "page_count": page_count,
        "document_count": doc_count,
        "invoice_count": invoice_count,
        "activity_count": activity_count,
        "recent_activity": recent_activity,
    }


async def generate_impersonation_token(
    db: AsyncSession, target_user_id: uuid.UUID, admin_user: User
) -> str | None:
    """Generate a short-lived access token for the target user (impersonation)."""
    from app.auth.utils import create_access_token
    from app.collaboration.service import log_activity

    result = await db.execute(select(User).where(User.id == target_user_id))
    target = result.scalar_one_or_none()
    if not target or not target.is_active:
        return None

    # Log the impersonation
    await log_activity(
        db,
        user_id=admin_user.id,
        action="user_impersonation",
        resource_type="user",
        resource_id=str(target_user_id),
        details={
            "admin_email": admin_user.email,
            "target_email": target.email,
        },
    )

    # Use standard access token (30 min default)
    token = create_access_token(
        user_id=target.id,
        role=target.role.value if hasattr(target.role, 'value') else str(target.role),
    )
    return token


# ── Activity log queries ─────────────────────────────────────────────────

async def get_activity_log(
    db: AsyncSession,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    stmt = (
        select(ActivityLog, User.full_name, User.email)
        .join(User, ActivityLog.user_id == User.id)
        .order_by(ActivityLog.created_at.desc())
    )
    count_stmt = select(func.count(ActivityLog.id))

    if user_id:
        stmt = stmt.where(ActivityLog.user_id == user_id)
        count_stmt = count_stmt.where(ActivityLog.user_id == user_id)
    if action:
        stmt = stmt.where(ActivityLog.action == action)
        count_stmt = count_stmt.where(ActivityLog.action == action)
    if resource_type:
        stmt = stmt.where(ActivityLog.resource_type == resource_type)
        count_stmt = count_stmt.where(ActivityLog.resource_type == resource_type)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    logs = [
        {
            "id": str(log.id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "user_name": name,
            "user_email": email,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, name, email in result.all()
    ]
    return logs, total


# ── Active sessions ──────────────────────────────────────────────────────

async def get_active_sessions(db: AsyncSession) -> list[dict]:
    """Get all non-revoked, non-expired refresh tokens (active sessions)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(RefreshToken, User.full_name, User.email)
        .join(User, RefreshToken.user_id == User.id)
        .where(RefreshToken.revoked == False, RefreshToken.expires_at > now)  # noqa: E712
        .order_by(RefreshToken.created_at.desc())
    )

    sessions = [
        {
            "id": str(token.id),
            "user_id": str(token.user_id),
            "user_name": name,
            "user_email": email,
            "created_at": token.created_at.isoformat() if token.created_at else None,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }
        for token, name, email in result.all()
    ]
    return sessions


async def revoke_session(db: AsyncSession, session_id: uuid.UUID) -> bool:
    """Revoke a specific refresh token (force logout)."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == session_id)
        .values(revoked=True)
    )
    await db.commit()
    return result.rowcount > 0


async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke all refresh tokens for a user."""
    result = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
        .values(revoked=True)
    )
    await db.commit()
    return result.rowcount


# ── Organization management ─────────────────────────────────────────


async def list_organizations(
    db: AsyncSession,
    search: str | None = None,
    plan: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[dict], int]:
    """List organizations with member counts."""
    stmt = (
        select(Organization, User.full_name, User.email)
        .join(User, Organization.owner_id == User.id)
        .order_by(Organization.created_at.desc())
    )
    count_stmt = select(func.count(Organization.id))

    if search:
        search_filter = Organization.name.ilike(f"%{search}%") | Organization.slug.ilike(f"%{search}%")
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)
    if plan:
        stmt = stmt.where(Organization.plan == plan)
        count_stmt = count_stmt.where(Organization.plan == plan)
    if is_active is not None:
        stmt = stmt.where(Organization.is_active == is_active)
        count_stmt = count_stmt.where(Organization.is_active == is_active)

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()

    org_list = []
    for org, owner_name, owner_email in rows:
        member_count = (await db.execute(
            select(func.count(User.id)).where(User.org_id == org.id)
        )).scalar() or 0
        org_list.append({
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "is_active": org.is_active,
            "plan": org.plan,
            "member_count": member_count,
            "owner_name": owner_name,
            "owner_email": owner_email,
            "created_at": org.created_at.isoformat() if org.created_at else None,
        })

    return org_list, total


async def get_organization(db: AsyncSession, org_id: uuid.UUID) -> dict | None:
    """Get organization detail with overrides and members."""
    result = await db.execute(
        select(Organization, User.full_name, User.email)
        .join(User, Organization.owner_id == User.id)
        .where(Organization.id == org_id)
    )
    row = result.one_or_none()
    if not row:
        return None

    org, owner_name, owner_email = row

    member_count = (await db.execute(
        select(func.count(User.id)).where(User.org_id == org.id)
    )).scalar() or 0

    # Feature overrides
    fo_rows = (await db.execute(
        select(OrgFeatureOverride).where(OrgFeatureOverride.org_id == org.id)
    )).scalars().all()
    feature_overrides = [
        {
            "id": str(fo.id),
            "org_id": str(fo.org_id),
            "feature_key": fo.feature_key,
            "enabled": fo.enabled,
            "created_at": fo.created_at.isoformat() if fo.created_at else None,
            "updated_at": fo.updated_at.isoformat() if fo.updated_at else None,
        }
        for fo in fo_rows
    ]

    # Setting overrides
    so_rows = (await db.execute(
        select(OrgSettingOverride).where(OrgSettingOverride.org_id == org.id)
    )).scalars().all()
    setting_overrides = [
        {
            "id": str(so.id),
            "org_id": str(so.org_id),
            "setting_key": so.setting_key,
            "value": so.value,
            "created_at": so.created_at.isoformat() if so.created_at else None,
            "updated_at": so.updated_at.isoformat() if so.updated_at else None,
        }
        for so in so_rows
    ]

    # Members
    members_result = (await db.execute(
        select(User).where(User.org_id == org.id).order_by(User.full_name)
    )).scalars().all()
    members = [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value if hasattr(u.role, "value") else str(u.role),
            "is_active": u.is_active,
        }
        for u in members_result
    ]

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "owner_id": str(org.owner_id),
        "is_active": org.is_active,
        "plan": org.plan,
        "max_users": org.max_users,
        "max_storage_gb": org.max_storage_gb,
        "logo_url": org.logo_url,
        "primary_color": org.primary_color,
        "secondary_color": org.secondary_color,
        "custom_domain": org.custom_domain,
        "notes": org.notes,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "updated_at": org.updated_at.isoformat() if org.updated_at else None,
        "feature_overrides": feature_overrides,
        "setting_overrides": setting_overrides,
        "member_count": member_count,
        "members": members,
        "owner_name": owner_name,
        "owner_email": owner_email,
    }


async def create_organization(db: AsyncSession, data: dict) -> Organization:
    """Create a new organization and assign owner."""
    org = Organization(**data)
    db.add(org)
    await db.flush()

    # Assign owner to this org
    await db.execute(
        update(User).where(User.id == org.owner_id).values(org_id=org.id)
    )

    await db.commit()
    await db.refresh(org)
    return org


async def update_organization(
    db: AsyncSession, org_id: uuid.UUID, data: dict
) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        return None
    for field, value in data.items():
        if value is not None:
            setattr(org, field, value)
    await db.commit()
    await db.refresh(org)
    return org


async def delete_organization(db: AsyncSession, org_id: uuid.UUID) -> bool:
    """Delete org, unlink members first."""
    await db.execute(update(User).where(User.org_id == org_id).values(org_id=None))
    result = await db.execute(delete(Organization).where(Organization.id == org_id))
    await db.commit()
    return result.rowcount > 0


async def set_org_feature_override(
    db: AsyncSession, org_id: uuid.UUID, feature_key: str, enabled: bool
) -> OrgFeatureOverride:
    """Set or update a per-org feature override."""
    result = await db.execute(
        select(OrgFeatureOverride).where(
            OrgFeatureOverride.org_id == org_id,
            OrgFeatureOverride.feature_key == feature_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.enabled = enabled
    else:
        existing = OrgFeatureOverride(org_id=org_id, feature_key=feature_key, enabled=enabled)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def delete_org_feature_override(
    db: AsyncSession, org_id: uuid.UUID, feature_key: str
) -> bool:
    """Remove a per-org feature override (revert to global default)."""
    result = await db.execute(
        delete(OrgFeatureOverride).where(
            OrgFeatureOverride.org_id == org_id,
            OrgFeatureOverride.feature_key == feature_key,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def set_org_setting_override(
    db: AsyncSession, org_id: uuid.UUID, setting_key: str, value: str
) -> OrgSettingOverride:
    """Set or update a per-org setting override."""
    result = await db.execute(
        select(OrgSettingOverride).where(
            OrgSettingOverride.org_id == org_id,
            OrgSettingOverride.setting_key == setting_key,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.value = value
    else:
        existing = OrgSettingOverride(org_id=org_id, setting_key=setting_key, value=value)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def delete_org_setting_override(
    db: AsyncSession, org_id: uuid.UUID, setting_key: str
) -> bool:
    """Remove a per-org setting override (revert to global default)."""
    result = await db.execute(
        delete(OrgSettingOverride).where(
            OrgSettingOverride.org_id == org_id,
            OrgSettingOverride.setting_key == setting_key,
        )
    )
    await db.commit()
    return result.rowcount > 0


async def add_org_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Add a user to an organization."""
    result = await db.execute(
        update(User).where(User.id == user_id).values(org_id=org_id)
    )
    await db.commit()
    return result.rowcount > 0


async def remove_org_member(db: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Remove a user from an organization."""
    result = await db.execute(
        update(User).where(User.id == user_id, User.org_id == org_id).values(org_id=None)
    )
    await db.commit()
    return result.rowcount > 0
