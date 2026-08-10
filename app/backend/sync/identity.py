"""SP4a — sharing identity: a per-account X25519 keypair, used to prove *who a collaborator is* before any
data is ever shared with them (SP4b+). No record is shared here; this stage only makes identity answerable.

The private key rides the SAME sync DEK every syncable record already uses — sealed via `crypto.py`'s existing
`encrypt_payload`/`decrypt_payload` (AES-256-GCM, unmodified), never a second passphrase/KEK. A sync-configured
user already has this key material available; sharing identity doesn't ask for anything new to unlock it.

The **fingerprint** (SHA-256 of the raw public key, grouped like `generate_recovery_code`'s own format) is what
two collaborators compare out-of-band before trusting a lookup result — the same "safety number" discipline
Signal uses for exactly this problem: a server-relayed public key is only as trustworthy as the side-channel
that confirms it.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import x25519

from app.backend.sync.crypto import SyncCryptoError, decrypt_payload, encrypt_payload

_PUBLIC_KEY_LEN = 32
_PRIVATE_KEY_LEN = 32


@dataclass(frozen=True)
class ShareIdentity:
    """Locally-stored identity material: the public key in the clear (it's public) + the private key sealed
    under the sync DEK. Contains no plaintext private key. Persisted via app_settings; never synced as a
    record (SP4a has no share-record concept yet)."""

    public_key: bytes
    wrapped_private_key: str  # encrypt_payload's opaque blob

    def to_dict(self) -> dict:
        return {
            "v": 1,
            "public_key": base64.b64encode(self.public_key).decode("ascii"),
            "wrapped_private_key": self.wrapped_private_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ShareIdentity:
        return cls(
            public_key=base64.b64decode(data["public_key"]),
            wrapped_private_key=data["wrapped_private_key"],
        )


def create_identity(dek: bytes) -> ShareIdentity:
    """Generate a fresh X25519 keypair and seal the private key under `dek`. The public key is returned
    unsealed (it's meant to be registered with the sync server)."""
    private_key = x25519.X25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes_raw()
    private_bytes = private_key.private_bytes_raw()
    wrapped = encrypt_payload(dek, {"private_key": base64.b64encode(private_bytes).decode("ascii")})
    return ShareIdentity(public_key=public_bytes, wrapped_private_key=wrapped)


def unlock_private_key(dek: bytes, identity: ShareIdentity) -> x25519.X25519PrivateKey:
    """The identity's private key, or raise `SyncCryptoError` on a wrong DEK / tampered blob (fails closed —
    same guarantee `unlock_with_passphrase` gives the sync DEK itself)."""
    payload = decrypt_payload(dek, identity.wrapped_private_key)
    try:
        raw = base64.b64decode(payload["private_key"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SyncCryptoError("identity payload missing a valid private_key") from exc
    if len(raw) != _PRIVATE_KEY_LEN:
        raise SyncCryptoError("identity private key has the wrong length")
    return x25519.X25519PrivateKey.from_private_bytes(raw)


def fingerprint(public_key: bytes) -> str:
    """A human-comparable fingerprint for out-of-band verification — SHA-256 of the raw public key, grouped
    like `generate_recovery_code`'s own 5-char-group format. Deterministic: the same key always fingerprints
    the same way, so two collaborators can read it aloud/copy-paste and confirm a match."""
    if len(public_key) != _PUBLIC_KEY_LEN:
        raise SyncCryptoError("public key has the wrong length")
    digest = hashlib.sha256(public_key).hexdigest().upper()
    return "-".join(digest[i : i + 5] for i in range(0, len(digest), 5))
