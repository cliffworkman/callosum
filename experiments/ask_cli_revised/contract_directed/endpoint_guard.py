"""Mechanical endpoint isolation for live stages, and a refuse-everything mode for offline test runs.

`isolated_only()` lets a process reach exactly one loopback endpoint (the isolated Ollama, 127.0.0.1:11435) and refuses every
other connection, in particular the SHARED Ollama at :11434 and any non-loopback host, so the shared endpoint is unreachable
rather than merely not-used. `refuse_all()` is the offline variant for test suites. Both patch the socket layer of THIS
process only; they make no claim about other processes.
"""

from __future__ import annotations

import socket
from contextlib import contextmanager

ISOLATED = ("127.0.0.1", 11435)
_LOOPBACK_NAMES = {"127.0.0.1", "localhost", "::1"}


class EndpointRefused(RuntimeError):
    pass


def _host_port(address) -> tuple[str | None, int | None]:
    try:
        return address[0], address[1]
    except (TypeError, IndexError):
        return None, None


@contextmanager
def _patched(allowed: tuple[str, int] | None):
    real_connect, real_connect_ex, real_getaddrinfo = (
        socket.socket.connect,
        socket.socket.connect_ex,
        socket.getaddrinfo,
    )

    def permitted(address) -> bool:
        host, port = _host_port(address)
        return (
            allowed is not None
            and host in _LOOPBACK_NAMES
            and (host, port) in ((allowed[0], allowed[1]), ("localhost", allowed[1]))
        )

    def connect(self, address):
        if not permitted(address):
            raise EndpointRefused(f"connection to {address!r} refused by the endpoint guard")
        return real_connect(self, address)

    def connect_ex(self, address):
        if not permitted(address):
            raise EndpointRefused(f"connection to {address!r} refused by the endpoint guard")
        return real_connect_ex(self, address)

    def getaddrinfo(host, port, *args, **kwargs):
        if allowed is None or host not in _LOOPBACK_NAMES:
            raise EndpointRefused(f"name resolution for {host!r} refused by the endpoint guard")
        return real_getaddrinfo(host, port, *args, **kwargs)

    socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = connect, connect_ex, getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = (
            real_connect,
            real_connect_ex,
            real_getaddrinfo,
        )


def isolated_only():
    """Allow only the isolated Ollama endpoint (127.0.0.1:11435)."""
    return _patched(ISOLATED)


def refuse_all():
    """Refuse every connection (offline test runs)."""
    return _patched(None)
