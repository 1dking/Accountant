
import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.exceptions import NotFoundError, ValidationError
from app.cards.models import BusinessCard
from app.cards.schemas import CardUpdate, PublicCardResponse

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
    return card


async def get_public_card(db: AsyncSession, slug: str) -> BusinessCard:
    result = await db.execute(
        select(BusinessCard).where(BusinessCard.slug == slug, BusinessCard.is_published.is_(True))
    )
    card = result.scalar_one_or_none()
    if card is None:
        raise NotFoundError("Card", slug)
    return card


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
        # Wallet passes land in Phase 3b — is_configured() checks slot in here.
        wallet_available={"apple": False, "google": False},
    )
