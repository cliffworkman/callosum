"""SP4b — the sharing content-key wrap: reaches a DIFFERENT person's key material, unlike everything else in
`sync/` (which only ever decrypts on the SAME device that encrypted). A live share's actual content (a
`build_bundle()` payload) is encrypted with `crypto.py`'s existing `encrypt_payload`/`decrypt_payload`
unmodified, keyed by a fresh random 32-byte **content key** instead of the sync DEK — no new content-crypto
code needed. This module's only job is wrapping that content key so the recipient (and only the recipient)
can recover it.

**The construction** — a "sealed" hybrid encryption, the same shape as libsodium's `crypto_box_seal` and an
HPKE (RFC 9180) base-mode ciphersuite built from DHKEM(X25519) + HKDF-SHA256 + AES-256-GCM (all already
available via the `cryptography` dependency SP4a already uses for identity keys — no new package):

1. A **fresh ephemeral X25519 keypair**, generated per wrap and never reused or stored.
2. ECDH between the ephemeral private key and the recipient's long-term public key (`crypto.py`'s
   `identity.py` keypair) → a raw shared secret.
3. HKDF-SHA256 over that secret (a fixed, versioned `info` string, `b"callosum-share-v1"`) → a 32-byte
   wrapping key. HKDF turns a raw ECDH secret (which is NOT uniformly random and must never be used directly
   as a symmetric key) into one that is.
4. AES-256-GCM(wrapping_key) encrypts the content key, with a fresh random nonce.

The envelope carries the ephemeral public key + nonce + ciphertext — nothing else is needed to unwrap, since
the recipient already holds their own long-term private key locally (SP4a). **No sender authentication is
built into the envelope** (deliberate, matching `crypto_box_seal`'s own documented posture): the sync-server
row this envelope travels in already carries an authenticated `sender_sub`, verified by the bearer token at
write time — the envelope's only job is confidentiality, not re-proving who sent it.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.backend.sync.crypto import SyncCryptoError

_KEY_LEN = 32  # AES-256 / X25519 key length
_NONCE_LEN = 12  # AES-GCM standard nonce
_HKDF_INFO = b"callosum-share-v1"


@dataclass(frozen=True)
class WrappedKey:
    """An opaque envelope wrapping one content key to exactly one recipient's public key."""

    ephemeral_public_key: bytes
    nonce: bytes
    ciphertext: bytes

    def to_dict(self) -> dict:
        b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
        return {
            "v": 1,
            "ephemeral_public_key": b64(self.ephemeral_public_key),
            "nonce": b64(self.nonce),
            "ciphertext": b64(self.ciphertext),
        }

    @classmethod
    def from_dict(cls, data: dict) -> WrappedKey:
        try:
            d = lambda k: base64.b64decode(data[k])  # noqa: E731
            return cls(
                ephemeral_public_key=d("ephemeral_public_key"),
                nonce=d("nonce"),
                ciphertext=d("ciphertext"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SyncCryptoError("malformed wrapped-key envelope") from exc


def _derive_wrapping_key(shared_secret: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=_KEY_LEN, salt=None, info=_HKDF_INFO).derive(shared_secret)


def wrap_content_key(content_key: bytes, recipient_public_key: bytes) -> WrappedKey:
    """Seal `content_key` (must be exactly 32 bytes, e.g. `os.urandom(32)`) so only the holder of the private
    key matching `recipient_public_key` can recover it. A fresh ephemeral keypair + nonce every call — two
    wraps of the same content key to the same recipient never produce the same ciphertext."""
    if len(content_key) != _KEY_LEN:
        raise SyncCryptoError("content key must be 32 bytes")
    if len(recipient_public_key) != _KEY_LEN:
        raise SyncCryptoError("recipient public key must be 32 bytes")
    ephemeral_private = x25519.X25519PrivateKey.generate()
    ephemeral_public = ephemeral_private.public_key().public_bytes_raw()
    try:
        recipient_key = x25519.X25519PublicKey.from_public_bytes(recipient_public_key)
        shared_secret = ephemeral_private.exchange(recipient_key)
    except ValueError as exc:
        raise SyncCryptoError("invalid recipient public key") from exc
    wrapping_key = _derive_wrapping_key(shared_secret)
    nonce = os.urandom(_NONCE_LEN)
    ciphertext = AESGCM(wrapping_key).encrypt(nonce, content_key, ephemeral_public)
    return WrappedKey(ephemeral_public_key=ephemeral_public, nonce=nonce, ciphertext=ciphertext)


def unwrap_content_key(wrapped: WrappedKey, recipient_private_key: x25519.X25519PrivateKey) -> bytes:
    """The original content key, or raise `SyncCryptoError` on a wrong private key / tampered envelope (fails
    closed — the same guarantee `crypto.py`'s own `unlock_with_passphrase` gives the sync DEK)."""
    try:
        ephemeral_public = x25519.X25519PublicKey.from_public_bytes(wrapped.ephemeral_public_key)
        shared_secret = recipient_private_key.exchange(ephemeral_public)
    except ValueError as exc:
        raise SyncCryptoError("invalid ephemeral public key in envelope") from exc
    wrapping_key = _derive_wrapping_key(shared_secret)
    try:
        return AESGCM(wrapping_key).decrypt(wrapped.nonce, wrapped.ciphertext, wrapped.ephemeral_public_key)
    except InvalidTag as exc:
        raise SyncCryptoError("could not unwrap content key (wrong key or tampered envelope)") from exc
