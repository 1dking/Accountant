"""Porkbun API client — thin async wrapper over their JSON REST v3.

Docs: https://porkbun.com/api/json/v3/documentation

Every call takes `apikey` + `secretapikey` in the JSON body (no
Authorization header). The reseller creds live in
IntegrationConfig(integration_type='porkbun') and are decrypted into
`settings.porkbun_api_key` / `.porkbun_secret_api_key` at Settings load.

We intentionally do NOT catch httpx errors here — the service layer
decides whether a failure is user-visible or should retry.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.porkbun.com/api/json/v3"


class PorkbunError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class PorkbunClient:
    def __init__(self, api_key: str, secret_key: str, *, timeout: float = 30.0):
        if not api_key or not secret_key:
            raise PorkbunError("Porkbun credentials are not configured")
        self._api_key = api_key
        self._secret = secret_key
        self._timeout = timeout

    def _auth(self, extra: dict | None = None) -> dict:
        body = {"apikey": self._api_key, "secretapikey": self._secret}
        if extra:
            body.update(extra)
        return body

    async def _post(self, path: str, extra: dict | None = None) -> dict:
        url = _BASE + path
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.post(url, json=self._auth(extra))
        try:
            data = r.json()
        except ValueError:
            raise PorkbunError(f"Porkbun returned non-JSON ({r.status_code})", status=r.status_code, body=r.text[:500])
        if r.status_code >= 400 or (isinstance(data, dict) and data.get("status") == "ERROR"):
            msg = (data.get("message") if isinstance(data, dict) else None) or f"HTTP {r.status_code}"
            raise PorkbunError(f"Porkbun {path} failed: {msg}", status=r.status_code, body=data)
        return data if isinstance(data, dict) else {"data": data}

    async def ping(self) -> dict:
        return await self._post("/ping")

    async def check_domain(self, domain: str) -> dict:
        """Availability + retail price. Returns Porkbun's raw payload —
        service.check() normalises into cents.
        """
        return await self._post(f"/domain/checkDomain/{domain}")

    async def pricing_all(self) -> dict:
        """All TLDs and their retail/renewal/transfer prices.
        Public endpoint but we hit it authed for consistency.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as c:
            r = await c.get(_BASE + "/pricing/get")
        return r.json()

    async def register(self, domain: str, *, cost_cents: int,
                       whois_privacy: bool = True, dry_run: bool = False,
                       coupon: str | None = None) -> dict:
        """Register a domain. Porkbun's API takes:
         - cost: exact price in CENTS (must match checkDomain price)
         - agreeToTerms: "yes"
         - whoisPrivacy: bool (default enabled where TLD supports it)
         - dryRun: validate without charging
        Always 1-year (registry minimum). Multi-year renewals happen separately.
        Premium names cannot be registered through the API."""
        extra: dict[str, Any] = {
            "cost": int(cost_cents),
            "agreeToTerms": "yes",
            "whoisPrivacy": bool(whois_privacy),
        }
        if dry_run:
            extra["dryRun"] = True
        if coupon:
            extra["coupon"] = coupon
        return await self._post(f"/domain/create/{domain}", extra)

    async def list_domains(self, *, start: int = 0) -> dict:
        return await self._post("/domain/listAll", {"start": start})

    async def get_nameservers(self, domain: str) -> dict:
        return await self._post(f"/domain/getNs/{domain}")

    async def set_nameservers(self, domain: str, nameservers: list[str]) -> dict:
        return await self._post(f"/domain/updateNs/{domain}", {"ns": nameservers})

    # DNS
    async def dns_list(self, domain: str) -> dict:
        return await self._post(f"/dns/retrieve/{domain}")

    async def dns_create(self, domain: str, *, type: str, content: str,
                         name: str = "", ttl: int = 600,
                         priority: int | None = None) -> dict:
        body: dict[str, Any] = {"type": type, "content": content, "name": name, "ttl": ttl}
        if priority is not None:
            body["prio"] = str(priority)
        return await self._post(f"/dns/create/{domain}", body)

    async def dns_edit(self, domain: str, record_id: str, *, type: str, content: str,
                       name: str = "", ttl: int = 600,
                       priority: int | None = None) -> dict:
        body: dict[str, Any] = {"type": type, "content": content, "name": name, "ttl": ttl}
        if priority is not None:
            body["prio"] = str(priority)
        return await self._post(f"/dns/edit/{domain}/{record_id}", body)

    async def dns_delete(self, domain: str, record_id: str) -> dict:
        return await self._post(f"/dns/delete/{domain}/{record_id}")


def build_client(settings) -> PorkbunClient:
    api = getattr(settings, "porkbun_api_key", "") or ""
    sec = getattr(settings, "porkbun_secret_api_key", "") or ""
    return PorkbunClient(api, sec)
