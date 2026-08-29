"""Reusable boundary for API actions that read arbitrary files from this machine."""

from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request

from app.backend import app_settings

_FORWARDED_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-real-ip", "forwarded")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def _require_local(request: Request, detail: str) -> None:
    if app_settings.read_only_mode() or any(request.headers.get(name) for name in _FORWARDED_HEADERS):
        raise HTTPException(status_code=403, detail=detail)
    hostname = (request.url.hostname or "").casefold()
    client_host = (request.client.host if request.client else "").casefold()
    if hostname and hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail=detail)
    if client_host == "testclient":
        return
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            raise HTTPException(status_code=403, detail=detail)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=detail) from exc


def require_local_file_access(request: Request) -> None:
    _require_local(request, "Local file attachment is available only on this machine.")


def require_local_machine_action(request: Request) -> None:
    """Gate trust-store/process-adjacent actions that must never arrive through a relay or hosted surface."""
    _require_local(request, "This system action is available only on this machine.")
    # A cross-origin HTML form can issue a "simple" localhost POST even when CORS blocks reading its result.
    # Requiring a non-safelisted header forces browser preflight, which Callosum's GET-only localhost CORS policy
    # denies to every foreign origin. This is deliberate CSRF resistance, not a secret/authentication token.
    if request.method not in {"GET", "HEAD"} and request.headers.get("x-callosum-local-action") != "settings-ui-v1":
        raise HTTPException(status_code=403, detail="Confirm this system action from Callosum Settings.")
