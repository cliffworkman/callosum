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


class ShareForbiddenError(SyncServerError):
    """SP4c: the server 403'd `GET /shares/{id}` — a share that exists but isn't addressed to the caller. A
    distinct subclass (not the generic 502 path) so the local router can surface a clean 403, since this is an
    expected/meaningful outcome (the defense-in-depth recipient check), not an unexpected server condition."""


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

    def register_identity(self, public_key: str, display_name: str | None) -> None:
        """SP4a: register/rotate the caller's own current sharing public key. Fails closed on any non-2xx."""
        try:
            resp = self._client.post(
                f"{self._base}/identity/register",
                json={"public_key": public_key, "display_name": display_name},
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise SyncServerError(f"identity registration failed: {exc}") from exc
        if resp.status_code != 204:
            raise SyncServerError(f"identity registration failed: HTTP {resp.status_code}: {resp.text[:500]}")

    def lookup_identity(self, sub: str) -> dict | None:
        """SP4a: `{public_key, display_name}` for exactly this `sub`, or None if nothing is registered."""
        try:
            resp = self._client.get(f"{self._base}/identity/lookup", params={"sub": sub}, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SyncServerError(f"identity lookup failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise SyncServerError(f"identity lookup failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
            return {"public_key": data["public_key"], "display_name": data.get("display_name")}
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed identity lookup response: {exc}") from exc

    def create_share(self, recipient_sub: str, wrapped_key: str, ciphertext: str) -> int:
        """SP4b: create a share addressed to `recipient_sub`. Fails closed on any non-2xx. Returns the new
        share's server-assigned id."""
        try:
            resp = self._client.post(
                f"{self._base}/shares",
                json={"recipient_sub": recipient_sub, "wrapped_key": wrapped_key, "ciphertext": ciphertext},
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise SyncServerError(f"share creation failed: {exc}") from exc
        if resp.status_code != 200:
            raise SyncServerError(f"share creation failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            return int(resp.json()["share_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed share creation response: {exc}") from exc

    def list_shares(self) -> list[dict]:
        """SP4c: the caller's own inbox -- ``[{id, sender_sub, created_at}]``, newest first. Never includes
        ciphertext (see `get_share` for that)."""
        try:
            resp = self._client.get(f"{self._base}/shares", headers=self._headers())
        except httpx.HTTPError as exc:
            raise SyncServerError(f"share list request failed: {exc}") from exc
        if resp.status_code != 200:
            raise SyncServerError(f"share list failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            return [
                {"id": int(s["id"]), "sender_sub": s["sender_sub"], "created_at": s["created_at"]}
                for s in resp.json()["shares"]
            ]
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed share list response: {exc}") from exc

    def get_share(self, share_id: int) -> dict | None:
        """SP4c: the full share row, or None if it doesn't exist. A 403 (a share that exists but isn't
        addressed to the caller) is NOT the same as "doesn't exist" -- it fails closed with `SyncServerError`
        rather than being silently treated as a 404, since it should never happen for a legitimate caller (the
        local app only ever fetches ids its own `list_shares()` just returned)."""
        try:
            resp = self._client.get(f"{self._base}/shares/{share_id}", headers=self._headers())
        except httpx.HTTPError as exc:
            raise SyncServerError(f"share fetch failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code == 403:
            raise ShareForbiddenError("this share is not addressed to you")
        if resp.status_code != 200:
            raise SyncServerError(f"share fetch failed: HTTP {resp.status_code}: {resp.text[:500]}")
        try:
            data = resp.json()
            return {
                "id": int(data["id"]),
                "sender_sub": data["sender_sub"],
                "recipient_sub": data["recipient_sub"],
                "wrapped_key": data["wrapped_key"],
                "ciphertext": data["ciphertext"],
                "created_at": data["created_at"],
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncServerError(f"malformed share fetch response: {exc}") from exc

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
