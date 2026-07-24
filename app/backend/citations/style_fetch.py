"""Bounded HTTPS fetching for user-requested CSL imports."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx

MAX_URL_LENGTH = 2_048


class StyleFetchError(RuntimeError):
    """A remote style catalog or CSL file could not be fetched safely."""


class BytesFetcher(Protocol):
    def __call__(self, url: str, *, timeout: float, max_bytes: int) -> bytes: ...


HostResolver = Callable[[str, int], list[str]]


def _default_resolver(host: str, port: int) -> list[str]:
    try:
        return sorted({item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise StyleFetchError(f"Could not resolve the style URL host: {host}") from exc


def require_public_https(url: str, *, resolver: HostResolver | None = None) -> None:
    if len(str(url or "")) > MAX_URL_LENGTH:
        raise ValueError(f"The style URL is too long (max {MAX_URL_LENGTH} characters)")
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https":
        raise ValueError("Citation style URLs must use https")
    if not parsed.hostname:
        raise ValueError("The citation style URL needs a host")
    if parsed.username or parsed.password:
        raise ValueError("Citation style URLs may not include credentials")
    if parsed.fragment:
        raise ValueError("Citation style URLs may not include a fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("The citation style URL has an invalid port") from exc
    if port not in {None, 443}:
        raise ValueError("Citation style URLs must use the standard https port")
    host = parsed.hostname
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        addresses = (resolver or _default_resolver)(host, 443)
    if not addresses:
        raise StyleFetchError(f"Could not resolve the style URL host: {host}")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise StyleFetchError(f"The style URL host resolved to an invalid address: {address}") from exc
        if not ip.is_global:
            raise ValueError("Citation style URLs may not resolve to a private or local address")


def _require_public_response_peer(response: httpx.Response) -> None:
    """Verify the connected peer when httpcore exposes it, closing the DNS-rebinding gap."""
    stream = response.extensions.get("network_stream")
    if stream is None or not hasattr(stream, "get_extra_info"):
        return
    server = stream.get_extra_info("server_addr")
    address = server[0] if isinstance(server, tuple) and server else server
    if not address:
        return
    try:
        peer = ipaddress.ip_address(str(address).split("%", 1)[0])
    except ValueError as exc:
        raise StyleFetchError("The style download connected to an invalid network address") from exc
    if not peer.is_global:
        raise ValueError("Citation style URLs may not connect to a private or local address")


def httpx_fetcher(
    url: str,
    *,
    timeout: float,
    max_bytes: int,
    guard: Callable[[str], None],
    client: httpx.Client | None = None,
    require_public_peer: bool = False,
) -> bytes:
    current = url
    owned_client = client is None
    http = client or httpx.Client(timeout=timeout, follow_redirects=False)
    try:
        for _ in range(5):
            guard(current)
            try:
                with http.stream(
                    "GET",
                    current,
                    headers={"Accept": "application/vnd.citationstyles.style+xml, application/json;q=0.9, */*;q=0.1"},
                ) as response:
                    if require_public_peer:
                        _require_public_response_peer(response)
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise StyleFetchError("The style download redirected without a Location header")
                        current = urljoin(current, location)
                        continue
                    if response.status_code != 200:
                        raise StyleFetchError(f"The style download returned HTTP {response.status_code}")
                    declared = response.headers.get("content-length")
                    if declared:
                        try:
                            if int(declared) > max_bytes:
                                raise StyleFetchError(f"The style download exceeds the {max_bytes}-byte limit")
                        except ValueError:
                            pass
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise StyleFetchError(f"The style download exceeds the {max_bytes}-byte limit")
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.HTTPError as exc:
                raise StyleFetchError(f"Could not download the citation style: {exc}") from exc
        raise StyleFetchError("The style download redirected too many times")
    finally:
        if owned_client:
            http.close()
