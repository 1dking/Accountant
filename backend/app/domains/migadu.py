"""Migadu API client — email hosting.

Docs: https://www.migadu.com/api/

Auth: HTTP Basic. Username = Migadu account email, password = API key.
Both live in Platform Admin → API Keys → Migadu, encrypted, mapped to
settings.migadu_admin_email / .migadu_api_key at Settings load.

Flat-rate pricing: Migadu bills per domain (Micro ~$19/yr, Mini ~$90/yr)
regardless of mailbox count, so we can honestly promise "unlimited
mailboxes on your domain" as a plan perk once a domain is provisioned.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.migadu.com/v1"


class MigaduError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class MigaduClient:
    def __init__(self, admin_email: str, api_key: str, *, timeout: float = 30.0):
        if not admin_email or not api_key:
            raise MigaduError("Migadu credentials are not configured")
        self._auth = (admin_email, api_key)
        self._timeout = timeout

    async def _req(self, method: str, path: str, **kwargs) -> dict:
        url = _BASE + path
        async with httpx.AsyncClient(timeout=self._timeout, auth=self._auth) as c:
            r = await c.request(method, url, **kwargs)
        if r.status_code == 204 or not r.content:
            return {}
        try:
            data = r.json()
        except ValueError:
            raise MigaduError(f"Migadu returned non-JSON ({r.status_code})",
                              status=r.status_code, body=r.text[:500])
        if r.status_code >= 400:
            msg = (data.get("error") if isinstance(data, dict) else None) or f"HTTP {r.status_code}"
            raise MigaduError(f"Migadu {method} {path} failed: {msg}",
                              status=r.status_code, body=data)
        return data if isinstance(data, dict) else {"data": data}

    # Domains
    async def list_domains(self) -> list[dict]:
        r = await self._req("GET", "/domains")
        return list(r.get("domains") or [])

    async def add_domain(self, name: str) -> dict:
        return await self._req("POST", "/domains", json={"name": name})

    async def delete_domain(self, name: str) -> dict:
        return await self._req("DELETE", f"/domains/{name}")

    async def get_domain(self, name: str) -> dict:
        return await self._req("GET", f"/domains/{name}")

    # Mailboxes
    async def list_mailboxes(self, domain: str) -> list[dict]:
        r = await self._req("GET", f"/domains/{domain}/mailboxes")
        return list(r.get("mailboxes") or [])

    async def create_mailbox(
        self, domain: str, *, local_part: str, name: str, password: str,
        is_internal: bool = False,
    ) -> dict:
        return await self._req("POST", f"/domains/{domain}/mailboxes", json={
            "local_part": local_part,
            "name": name,
            "password": password,
            "is_internal": is_internal,
        })

    async def delete_mailbox(self, domain: str, local_part: str) -> dict:
        return await self._req("DELETE", f"/domains/{domain}/mailboxes/{local_part}")

    async def update_mailbox_password(self, domain: str, local_part: str,
                                      password: str) -> dict:
        return await self._req(
            "PUT", f"/domains/{domain}/mailboxes/{local_part}",
            json={"password": password},
        )


def build_client(settings) -> MigaduClient:
    return MigaduClient(
        getattr(settings, "migadu_admin_email", "") or "",
        getattr(settings, "migadu_api_key", "") or "",
    )


# ---------------------------------------------------------------------------
# DNS records Migadu needs on every hosted domain. Values from Migadu's
# public docs, current 2026. Applied via the Porkbun DNS API in one shot
# when the customer enables email on a domain.
# ---------------------------------------------------------------------------

def migadu_dns_records(domain: str) -> list[dict]:
    """Return the DNS records to create at the registrar to make Migadu
    email work on `domain`. Each dict is (name, type, content, ttl,
    priority) — matches our porkbun.dns_create signature."""
    return [
        # Inbound mail
        {"type": "MX", "name": "", "content": "aspmx1.migadu.com", "ttl": 3600, "priority": 10},
        {"type": "MX", "name": "", "content": "aspmx2.migadu.com", "ttl": 3600, "priority": 20},
        # SPF — authorises Migadu to send on our behalf
        {"type": "TXT", "name": "", "content": "v=spf1 include:spf.migadu.com -all", "ttl": 3600},
        # DKIM — signing keys (published per-account at these names)
        {"type": "CNAME", "name": "key1._domainkey", "content": f"key1.{domain}._domainkey.migadu.com", "ttl": 3600},
        {"type": "CNAME", "name": "key2._domainkey", "content": f"key2.{domain}._domainkey.migadu.com", "ttl": 3600},
        {"type": "CNAME", "name": "key3._domainkey", "content": f"key3.{domain}._domainkey.migadu.com", "ttl": 3600},
        # DMARC — quarantine so anything that fails goes to spam not inbox,
        # but rejections don't hard-bounce until the domain is warm.
        {"type": "TXT", "name": "_dmarc", "content": "v=DMARC1; p=quarantine;", "ttl": 3600},
        # Autoconfig / autodiscover so Thunderbird / Outlook clients self-configure
        {"type": "CNAME", "name": "autoconfig", "content": "autoconfig.migadu.com", "ttl": 3600},
        {"type": "SRV", "name": "_autodiscover._tcp", "content": "0 443 autodiscover.migadu.com", "ttl": 3600, "priority": 0},
    ]
