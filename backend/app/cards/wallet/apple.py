"""Apple Wallet .pkpass builder — generate-and-serve only.

A .pkpass is a ZIP of pass.json + icons + a SHA-1 manifest + a detached
PKCS#7 signature over the manifest, signed with the admin-uploaded Pass
Type ID certificate and Apple's WWDR intermediate. Built entirely with
the already-present `cryptography` and Pillow — no new dependencies.

Deliberately NOT implemented: Apple's live-update loop (PassKit Web
Service + device registration + APNs). A saved pass is a snapshot until
the visitor re-adds it.
"""

import base64
import hashlib
import io
import json
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate

REQUIRED_FIELDS = (
    "team_id",
    "pass_type_identifier",
    "p12_certificate_base64",
    "p12_password",
    "wwdr_certificate_base64",
)


def is_configured(config: dict | None) -> bool:
    return bool(config) and all(config.get(f) for f in REQUIRED_FIELDS)


def _hex_to_rgb(hex_color: str, fallback: str) -> str:
    """'#1A2B3C' -> 'rgb(26, 43, 60)' (the format pass.json requires)."""
    value = (hex_color or fallback).lstrip("#")
    if len(value) != 6:
        value = fallback.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


def _solid_icon(hex_color: str, size: int) -> bytes:
    """Minimal solid-color pass icon. Wallet requires icon.png to exist;
    a brand-colored square is a clean placeholder until real art exists."""
    from PIL import Image

    value = (hex_color or "#2563eb").lstrip("#")
    if len(value) != 6:
        value = "2563eb"
    rgb = tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGB", (size, size), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _load_certificate(pem_or_der: bytes):
    try:
        return load_pem_x509_certificate(pem_or_der)
    except ValueError:
        return load_der_x509_certificate(pem_or_der)


def build_pkpass(
    config: dict,
    *,
    serial_number: str,
    display_name: str,
    job_title: str | None,
    company_name: str | None,
    email: str | None,
    phone: str | None,
    website: str | None,
    card_url: str,
    bg_color: str,
    text_color: str,
    accent_color: str,
) -> bytes:
    pass_json = {
        "formatVersion": 1,
        "passTypeIdentifier": config["pass_type_identifier"],
        "serialNumber": serial_number,
        "teamIdentifier": config["team_id"],
        "organizationName": company_name or display_name,
        "description": f"{display_name} — business card",
        "foregroundColor": _hex_to_rgb(text_color, "#111827"),
        "backgroundColor": _hex_to_rgb(bg_color, "#ffffff"),
        "labelColor": _hex_to_rgb(accent_color, "#2563eb"),
        "barcodes": [
            {
                "format": "PKBarcodeFormatQR",
                "message": card_url,
                "messageEncoding": "iso-8859-1",
            }
        ],
        "generic": {
            "primaryFields": [{"key": "name", "label": "", "value": display_name}],
            "secondaryFields": [
                field
                for field in (
                    {"key": "title", "label": "TITLE", "value": job_title} if job_title else None,
                    {"key": "company", "label": "COMPANY", "value": company_name} if company_name else None,
                )
                if field is not None
            ],
            "backFields": [
                field
                for field in (
                    {"key": "email", "label": "Email", "value": email} if email else None,
                    {"key": "phone", "label": "Phone", "value": phone} if phone else None,
                    {"key": "website", "label": "Website", "value": website} if website else None,
                    {"key": "card", "label": "Digital card", "value": card_url},
                )
                if field is not None
            ],
        },
    }

    files: dict[str, bytes] = {
        "pass.json": json.dumps(pass_json, ensure_ascii=False).encode("utf-8"),
        "icon.png": _solid_icon(accent_color, 29),
        "icon@2x.png": _solid_icon(accent_color, 58),
    }

    # Manifest: SHA-1 of every file (Apple's spec still mandates SHA-1 here).
    manifest = json.dumps(
        {name: hashlib.sha1(data).hexdigest() for name, data in files.items()}
    ).encode("utf-8")
    files["manifest.json"] = manifest

    key, cert, _extra = pkcs12.load_key_and_certificates(
        base64.b64decode(config["p12_certificate_base64"]),
        config["p12_password"].encode("utf-8"),
    )
    if key is None or cert is None:
        raise ValueError("The .p12 certificate is missing its key or certificate")
    wwdr = _load_certificate(base64.b64decode(config["wwdr_certificate_base64"]))

    signature = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        .sign(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
        )
    )
    files["signature"] = signature

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
