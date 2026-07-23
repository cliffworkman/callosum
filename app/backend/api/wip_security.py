"""Local-only boundary for unpublished WIP data."""

from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request

from app.backend import app_settings

_FORWARDED_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-real-ip", "forwarded")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def require_local_wip(request: Request) -> None:
    """Deny WIP over remote/read-only companion paths, even for authenticated callers."""
    if app_settings.read_only_mode():
        raise HTTPException(status_code=403, detail="WIP is available only on the local Callosum instance.")
    if any(request.headers.get(header) for header in _FORWARDED_HEADERS):
        raise HTTPException(status_code=403, detail="WIP is available only on the local Callosum instance.")
    host_header = (request.url.hostname or "").casefold()
    client_host = (request.client.host if request.client else "").casefold()
    if host_header and host_header not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="WIP is available only on the local Callosum instance.")
    if client_host == "testclient":
        return
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            raise HTTPException(status_code=403, detail="WIP is available only on the local Callosum instance.")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="WIP is available only on the local Callosum instance.") from exc
