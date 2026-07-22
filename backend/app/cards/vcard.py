"""RFC 6350 vCard 3.0 builder for the digital business card.

Pure-Python port of Arivio's vcard.ts. Deliberately minimal: the fields
a phone contact app actually imports (FN/N/ORG/TITLE/TEL/EMAIL/URL),
correct escaping, CRLF line endings, UTF-8. No PHOTO in v1 — base64
photos bloat the .vcf and Android's importer is flaky with them.
"""


def _esc(value: str) -> str:
    """Escape per RFC 6350 §3.4: backslash, newline, comma, semicolon."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_vcard(
    *,
    display_name: str,
    job_title: str | None = None,
    company_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    card_url: str | None = None,
) -> str:
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{_esc(display_name)}",
    ]

    # N is structured (family;given;middle;prefix;suffix). Best-effort
    # split: last word as family name, rest as given — same heuristic
    # Arivio uses; contact apps mostly display FN anyway.
    parts = display_name.strip().split()
    if len(parts) >= 2:
        family = parts[-1]
        given = " ".join(parts[:-1])
    else:
        family = ""
        given = display_name.strip()
    lines.append(f"N:{_esc(family)};{_esc(given)};;;")

    if company_name:
        lines.append(f"ORG:{_esc(company_name)}")
    if job_title:
        lines.append(f"TITLE:{_esc(job_title)}")
    if phone:
        lines.append(f"TEL;TYPE=CELL:{_esc(phone)}")
    if email:
        lines.append(f"EMAIL;TYPE=INTERNET:{_esc(email)}")
    if website:
        lines.append(f"URL:{_esc(website)}")
    if card_url and card_url != website:
        lines.append(f"URL:{_esc(card_url)}")

    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"
