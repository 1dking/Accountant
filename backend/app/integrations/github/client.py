"""Minimal GitHub REST client — only what de-provisioning needs.

Today that is exactly one call: remove a departing user as a collaborator on a
repository. Kept deliberately small and dependency-light (httpx, already a
project dependency) so it is easy to test and reason about.

Auth: a personal access token (or fine-grained token) with admin rights on the
target repo — required to DELETE a collaborator. Read from
``settings.github_token``; the repo list from ``settings.github_repos``.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.github.com"
_TIMEOUT = 10.0


def parse_repos(raw: str | None) -> list[str]:
    """Split the comma-separated ``owner/repo`` config into a clean list."""
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip() and "/" in r]


async def remove_collaborator(
    token: str,
    repo: str,
    username: str,
    *,
    api_base: str = DEFAULT_API_BASE,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Remove ``username`` as a collaborator on ``owner/repo``.

    Returns a structured result dict (never raises) so the caller can record the
    outcome of each repo independently and keep going:

        {"repo", "username", "status": "removed"|"not_collaborator"|"error",
         "http_status": int|None, "detail": str|None}

    GitHub semantics:
      * 204 No Content -> collaborator removed (this is the success we want).
      * 404 Not Found  -> not a collaborator on this repo (already gone) —
                          treated as success-equivalent, not an error.
      * anything else  -> recorded as an error, with the status + body snippet.
    """
    owner_repo = repo.strip()
    url = f"{api_base.rstrip('/')}/repos/{owner_repo}/collaborators/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        resp = await client.request("DELETE", url, headers=headers)
    except Exception as exc:  # noqa: BLE001 — network/DNS/timeout: record, don't crash the deprovision
        logger.warning("github: remove_collaborator failed repo=%s user=%s: %s", owner_repo, username, exc)
        return {"repo": owner_repo, "username": username, "status": "error",
                "http_status": None, "detail": str(exc)}
    finally:
        if owns_client:
            await client.aclose()

    if resp.status_code == 204:
        result = {"status": "removed", "detail": None}
    elif resp.status_code == 404:
        result = {"status": "not_collaborator", "detail": "not a collaborator (already removed)"}
    else:
        body = ""
        try:
            body = resp.text[:200]
        except Exception:  # noqa: BLE001
            pass
        result = {"status": "error", "detail": body or f"HTTP {resp.status_code}"}
    return {"repo": owner_repo, "username": username, "http_status": resp.status_code, **result}
