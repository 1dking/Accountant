
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.cards.models import BusinessCard, CardAnalyticsEvent, CardEventType
from app.cards.schemas import CardUpdate, PublicCardResponse

logger = logging.getLogger(__name__)

# Slugs that must never become someone's card URL — either they collide
# with real routes or invite impersonation.
RESERVED_SLUGS = {
    "admin", "api", "app", "book", "booking", "c", "card", "cards", "contact",
    "dashboard", "embed", "f", "help", "login", "logout", "m", "me", "meetings",
    "p", "portal", "register", "settings", "signup", "support", "www",
}

DEFAULT_PALETTE = {
    "bg_color": "#ffffff",
    "text_color": "#111827",
    "accent_color": "#2563eb",
    "button_color": "#2563eb",
    "button_text_color": "#ffffff",
    "font": "Inter",
}


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:80] or "card"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    candidate = base
    suffix = 1
    while True:
        if candidate not in RESERVED_SLUGS:
            existing = await db.execute(
                select(BusinessCard.id).where(BusinessCard.slug == candidate)
            )
            if existing.scalar_one_or_none() is None:
                return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def get_or_create_card(db: AsyncSession, user: User) -> BusinessCard:
    result = await db.execute(select(BusinessCard).where(BusinessCard.user_id == user.id))
    card = result.scalar_one_or_none()
    if card:
        return card

    from app.settings.models import CompanySettings

    company = (await db.execute(select(CompanySettings))).scalars().first()

    card = BusinessCard(
        user_id=user.id,
        created_by=user.id,
        slug=await _unique_slug(db, _slugify(user.full_name)),
        display_name=user.full_name,
        email=user.email,
        company_name=company.company_name if company else None,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def update_card(db: AsyncSession, user: User, data: CardUpdate) -> BusinessCard:
    card = await get_or_create_card(db, user)

    updates = data.model_dump(exclude_unset=True)

    if "slug" in updates and updates["slug"]:
        new_slug = _slugify(updates["slug"])
        if new_slug != card.slug:
            if new_slug in RESERVED_SLUGS:
                raise ValidationError(f"'{new_slug}' is a reserved URL")
            existing = await db.execute(
                select(BusinessCard.id).where(
                    BusinessCard.slug == new_slug, BusinessCard.id != card.id
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise ValidationError(f"The URL '{new_slug}' is already taken")
            card.slug = new_slug
        updates.pop("slug")

    for field, value in updates.items():
        setattr(card, field, value)

    await db.commit()
    await db.refresh(card)

    # Live-refresh any Google Wallet passes saved from this card. Apple has
    # no cheap equivalent (needs the full PassKit Web Service + APNs loop,
    # deliberately deferred) — a saved Apple pass is a snapshot.
    if card.is_published:
        try:
            from app.cards.wallet import google as google_wallet

            payload = await build_public_payload(db, card)
            await google_wallet.push_update(db, card, payload)
        except Exception:  # noqa: BLE001 — never break a card save over a pass refresh
            logger.exception("Google Wallet refresh failed for card %s", card.id)

    return card


async def get_public_card(db: AsyncSession, slug: str) -> BusinessCard:
    result = await db.execute(
        select(BusinessCard).where(BusinessCard.slug == slug, BusinessCard.is_published.is_(True))
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise NotFoundError("Card", slug)
    return card


async def record_card_view(
    db: AsyncSession,
    card: BusinessCard,
    event_type: CardEventType,
    ip_address: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
) -> None:
    """Log a public-card event and fire the matching workflow trigger.

    The analytics write is unconditional (the log stays honest); the
    CARD_VIEWED dispatch is deduped per card+visitor to one fire per
    hour — a card has no state machine, so without this a single person
    refreshing the page would spam every "card viewed" automation.
    CARD_CONTACT_SAVED always dispatches: an explicit save is a
    deliberate act worth reacting to every time.
    """
    visitor_hash = (
        hashlib.sha256(ip_address.encode()).hexdigest()[:16] if ip_address else None
    )

    recently_seen = False
    if event_type == CardEventType.VIEW and visitor_hash:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = await db.execute(
            select(CardAnalyticsEvent.id)
            .where(
                CardAnalyticsEvent.card_id == card.id,
                CardAnalyticsEvent.event_type == CardEventType.VIEW.value,
                CardAnalyticsEvent.visitor_hash == visitor_hash,
                CardAnalyticsEvent.created_at >= cutoff,
            )
            .limit(1)
        )
        recently_seen = recent.scalar_one_or_none() is not None

    db.add(
        CardAnalyticsEvent(
            card_id=card.id,
            event_type=event_type.value,
            visitor_hash=visitor_hash,
            referrer=(referrer or None) and referrer[:500],
            user_agent=(user_agent or None) and user_agent[:500],
        )
    )
    await db.commit()

    if event_type == CardEventType.VIEW and recently_seen:
        return

    from app.workflows.models import TriggerType
    from app.workflows.service import safe_dispatch

    trigger = (
        TriggerType.CARD_VIEWED
        if event_type == CardEventType.VIEW
        else TriggerType.CARD_CONTACT_SAVED
    )
    # Curated, template-placeholder-friendly event_data — deliberately no
    # IP/user-agent here (raw metadata stays in the analytics row; this
    # dict gets substituted into emails and forwarded to webhooks).
    await safe_dispatch(
        db,
        trigger,
        event_data={
            "card_slug": card.slug,
            "card_display_name": card.display_name,
            "referrer": referrer or "",
        },
        contact_id=None,
    )


async def get_card_analytics(db: AsyncSession, card_id: uuid.UUID) -> dict:
    """Live aggregates — no rollup table; card traffic is light."""

    async def _count(*where) -> int:
        result = await db.execute(
            select(func.count(CardAnalyticsEvent.id)).where(
                CardAnalyticsEvent.card_id == card_id, *where
            )
        )
        return result.scalar() or 0

    unique_result = await db.execute(
        select(func.count(func.distinct(CardAnalyticsEvent.visitor_hash))).where(
            CardAnalyticsEvent.card_id == card_id,
            CardAnalyticsEvent.event_type == CardEventType.VIEW.value,
            CardAnalyticsEvent.visitor_hash.is_not(None),
        )
    )

    return {
        "total_views": await _count(
            CardAnalyticsEvent.event_type == CardEventType.VIEW.value
        ),
        "unique_visitors": unique_result.scalar() or 0,
        "total_vcard_downloads": await _count(
            CardAnalyticsEvent.event_type == CardEventType.VCARD_DOWNLOAD.value
        ),
    }


async def build_public_payload(db: AsyncSession, card: BusinessCard) -> PublicCardResponse:
    """Resolve palette fallbacks, booking URL, logo, and wallet
    availability into a single public payload."""
    from app.branding.service import get_public_branding
    from app.settings.models import CompanySettings

    branding = await get_public_branding(db)

    palette = dict(DEFAULT_PALETTE)
    if branding is not None:
        palette["accent_color"] = branding.primary_color or palette["accent_color"]
        palette["button_color"] = branding.primary_color or palette["button_color"]
        if branding.font_body:
            palette["font"] = branding.font_body
    for key in palette:
        own = getattr(card, key, None)
        if own:
            palette[key] = own

    # Org logo: brand logo URL first, else the public company-logo stream.
    logo_url = None
    if card.show_org_logo:
        if branding is not None and branding.logo_url:
            logo_url = branding.logo_url
        else:
            company = (await db.execute(select(CompanySettings))).scalars().first()
            if company is not None and company.logo_storage_path:
                logo_url = "/api/settings/company/logo"

    # Booking URL: linked SchedulingCalendar's public slug, else the
    # legacy free-text User.booking_link.
    booking_url = None
    if card.show_booking:
        if card.scheduling_calendar_id:
            from app.scheduling.models import SchedulingCalendar

            cal = await db.get(SchedulingCalendar, card.scheduling_calendar_id)
            if cal is not None and cal.is_active:
                booking_url = f"/book/{cal.slug}"
        if booking_url is None:
            owner = await db.get(User, card.user_id)
            if owner is not None and owner.booking_link:
                booking_url = owner.booking_link

    social_links: dict[str, str] = {}
    if card.social_links_json:
        try:
            parsed = json.loads(card.social_links_json)
            if isinstance(parsed, dict):
                social_links = {str(k): str(v) for k, v in parsed.items() if v}
        except (json.JSONDecodeError, TypeError):
            pass

    from app.cards.wallet import APPLE_WALLET, GOOGLE_WALLET, load_wallet_config
    from app.cards.wallet import apple as apple_wallet
    from app.cards.wallet import google as google_wallet

    wallet_available = {
        "apple": apple_wallet.is_configured(await load_wallet_config(db, APPLE_WALLET)),
        "google": google_wallet.is_configured(await load_wallet_config(db, GOOGLE_WALLET)),
    }

    return PublicCardResponse(
        slug=card.slug,
        template=card.template,
        display_name=card.display_name,
        job_title=card.job_title,
        company_name=card.company_name,
        tagline=card.tagline,
        email=card.email,
        phone=card.phone,
        website=card.website,
        social_links=social_links,
        avatar_url=f"/api/cards/public/{card.slug}/avatar" if card.avatar_storage_path else None,
        logo_url=logo_url,
        bg_color=palette["bg_color"],
        text_color=palette["text_color"],
        accent_color=palette["accent_color"],
        button_color=palette["button_color"],
        button_text_color=palette["button_text_color"],
        font=palette["font"],
        booking_url=booking_url,
        wallet_available=wallet_available,
    )
