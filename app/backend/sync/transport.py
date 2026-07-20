"""The client side of sync egress — an ``HttpSyncTransport`` implementing the inc-198 ``SyncTransport`` Protocol over
httpx against the reference sync-server. It carries the Authentik access token (accounts SP1) as a bearer, sends/
receives only **opaque ciphertext** (the engine encrypts before push / decrypts after pull — the DEK never leaves),
sets timeouts, and **fails closed** (a transport error or a non-200 / malformed response raises ``SyncServerError``,
never silently drops a record).

The httpx client is injectable so tests bind it to the in-process server's ASGI app (real HTTP semantics, no socket).
The local app gains no new dependency — httpx is already present.
"""

from __future__ import annotations

import httpx

from app.backend.sync.engine import PullResult, SyncBlob


class SyncServerError(Exception):
    """A sync transport/protocol failure (network, non-200, or malformed response) — fail closed."""


class HttpSyncTransport:
    def __init__(self, base_url: str, token: str, *, client: httpx.Client | None = None, timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def pull(self, since: int) -> PullResult:
        try:
            resp = self._client.get(f"{self._base}/sync/records", params={"since": since}, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SyncServerError(f"pull request failed: {exc}") from exc
        if resp.status_code != 200:
            raise SyncServerError(f"pull failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
            records = [
                SyncBlob(
                    collection=r["collection"],
                    record_id=r["record_id"],
                    version=int(r["version"]),
                    deleted=bool(r["deleted"]),
                    ciphertext=r.get("ciphertext"),
                )
                for r in data["records"]
            ]
            return PullResult(records=records, seq=int(data["seq"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed pull response: {exc}") from exc

    def push(self, records: list[SyncBlob]) -> int:
        body = {
            "records": [
                {
                    "collection": b.collection,
                    "record_id": b.record_id,
                    "version": b.version,
                    "deleted": b.deleted,
                    "ciphertext": b.ciphertext,
                }
                for b in records
            ]
        }
        try:
            resp = self._client.post(f"{self._base}/sync/records", json=body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SyncServerError(f"push request failed: {exc}") from exc
        if resp.status_code != 200:
            raise SyncServerError(f"push failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            return int(resp.json()["seq"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed push response: {exc}") from exc

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
