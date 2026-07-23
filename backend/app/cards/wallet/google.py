"""Google Wallet generic pass — Save-to-Wallet JWT + live object updates.

The save URL embeds the full class+object in a signed JWT ("skinny JWT"
flow), so issuing a pass needs zero REST calls. `push_update` PATCHes
the object after a card edit so already-saved passes refresh — Google
caps its own update notifications at 3/24h per pass; beyond that the
pass still updates silently.
"""

import asyncio
import json
import logging
import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("issuer_id", "service_account_json")

CLASS_SUFFIX = "obrain_card"
WALLET_SCOPE = "https://www.googleapis.com/auth/wallet_object.issuer"
OBJECTS_URL = "https://walletobjects.googleapis.com/walletobjects/v1/genericObject"


def is_configured(config: dict | None) -> bool:
    return bool(config) and all(config.get(f) for f in REQUIRED_FIELDS)


def object_id(config: dict, card_id: uuid.UUID) -> str:
    return f"{config['issuer_id']}.{card_id.hex}"


def _localized(value: str) -> dict:
    return {"defaultValue": {"language": "en-US", "value": value}}


def build_generic_object(
    config: dict,
    *,
    card_id: uuid.UUID,
    display_name: str,
    job_title: str | None,
    company_name: str | None,
    email: str | None,
    phone: str | None,
    card_url: str,
    bg_color: str,
) -> dict:
    obj: dict = {
        "id": object_id(config, card_id),
        "classId": f"{config['issuer_id']}.{CLASS_SUFFIX}",
        "state": "ACTIVE",
        "cardTitle": _localized(company_name or "Business Card"),
        "header": _localized(display_name),
        "hexBackgroundColor": bg_color or "#2563eb",
        "barcode": {"type": "QR_CODE", "value": card_url},
        "linksModuleData": {
            "uris": [{"uri": card_url, "description": "View digital card", "id": "card"}]
        },
    }
    if job_title:
        obj["subheader"] = _localized(job_title)
    text_modules = [
        {"id": mod_id, "header": header, "body": body}
        for mod_id, header, body in (
            ("email", "Email", email),
            ("phone", "Phone", phone),
        )
        if body
    ]
    if text_modules:
        obj["textModulesData"] = text_modules
    return obj


def build_save_url(config: dict, generic_object: dict) -> str:
    """Sign a Save-to-Wallet JWT embedding the class + object."""
    from google.auth import crypt, jwt as google_jwt

    sa_info = json.loads(config["service_account_json"])
    signer = crypt.RSASigner.from_service_account_info(sa_info)
    claims = {
        "iss": sa_info["client_email"],
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "origins": [],
        "payload": {
            "genericClasses": [{"id": generic_object["classId"]}],
            "genericObjects": [generic_object],
        },
    }
    token = google_jwt.encode(signer, claims).decode("utf-8")
    return f"https://pay.google.com/gp/v/save/{token}"


def _sync_patch(sa_info: dict, obj_id: str, body: dict) -> int:
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=[WALLET_SCOPE]
    )
    session = AuthorizedSession(creds)
    resp = session.patch(f"{OBJECTS_URL}/{obj_id}", json=body, timeout=10)
    return resp.status_code


async def push_update(db: AsyncSession, card, payload) -> None:
    """Fire-and-forget: PATCH the saved pass after a card edit. Never
    raises — an unreachable Google API must not break saving a card."""
    try:
        from app.cards.wallet import GOOGLE_WALLET, load_wallet_config

        config = await load_wallet_config(db, GOOGLE_WALLET)
        if not is_configured(config):
            return

        obj = build_generic_object(
            config,
            card_id=card.id,
            display_name=card.display_name,
            job_title=card.job_title,
            company_name=card.company_name,
            email=card.email,
            phone=card.phone,
            card_url=payload_card_url(payload, card),
            bg_color=payload.bg_color,
        )
        sa_info = json.loads(config["service_account_json"])
        status = await asyncio.to_thread(
            _sync_patch, sa_info, object_id(config, card.id), obj
        )
        if status == 404:
            # Nobody has saved this pass yet — nothing to update.
            logger.debug("Google Wallet object for card %s not found (never saved)", card.id)
        elif status >= 400:
            logger.warning("Google Wallet PATCH for card %s returned %s", card.id, status)
    except Exception:  # noqa: BLE001
        logger.exception("Google Wallet push_update failed for card %s", card.id)


def payload_card_url(payload, card) -> str:
    from app.config import Settings

    base = Settings().public_base_url.rstrip("/")
    return f"{base}/c/{card.slug}"
