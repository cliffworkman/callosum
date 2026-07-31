"""Reusable boundary for API actions that read arbitrary files from this machine."""

from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request

from app.backend import app_settings

_FORWARDED_HEADERS = ("cf-connecting-ip", "x-forwarded-for", "x-real-ip", "forwarded")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "testserver"}


def require_local_file_access(request: Request) -> None:
    if app_settings.read_only_mode() or any(request.headers.get(name) for name in _FORWARDED_HEADERS):
        raise HTTPException(status_code=403, detail="Local file attachment is available only on this machine.")
    hostname = (request.url.hostname or "").casefold()
    client_host = (request.client.host if request.client else "").casefold()
    if hostname and hostname not in _LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="Local file attachment is available only on this machine.")
    if client_host == "testclient":
        return
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            raise HTTPException(status_code=403, detail="Local file attachment is available only on this machine.")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Local file attachment is available only on this machine.") from exc
