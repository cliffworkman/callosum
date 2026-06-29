"""SP3a — the E2E sync crypto layer (local, no egress).

A random **data-encryption key (DEK)** encrypts each syncable record with **AES-256-GCM**; the DEK is **wrapped**
(sealed) under two key-encryption keys — one derived from the user's **passphrase**, one from a generated **recovery
code** — via **scrypt** (`cryptography.hazmat`, already a dep via `PyJWT[crypto]` → no new dependency). The keyring
(the two wrapped-DEK blobs + their salts) is the only thing persisted locally (SP3c); it contains **no key, no
passphrase, no recovery code, and no plaintext**, so it is safe at rest and would be safe even if it leaked. The DEK,
passphrase, and recovery code **never leave the machine** and are never sent to any endpoint — that is the E2E
guarantee. A wrong passphrase/code → GCM auth fails → we **raise** (`SyncCryptoError`), never return garbage.

Two-KEK design lets the passphrase be rotated (re-wrap the DEK) without re-encrypting data, and gives the recovery
code as an independent unlock. There is **no server-side reset** — the recovery code is the only non-passphrase path.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# scrypt work factors — interactive-grade (~32 MB). Sound for a per-vault, on-unlock derivation.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32  # AES-256
_NONCE_LEN = 12  # AES-GCM standard nonce
_SALT_LEN = 16


class SyncCryptoError(Exception):
    """A crypto failure (wrong passphrase/recovery code, or tampered ciphertext). Always fails closed."""


def _derive_kek(secret: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=_KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return kdf.derive(secret.encode("utf-8"))


def _seal(key: bytes, plaintext: bytes) -> bytes:
    """nonce(12) || AES-256-GCM(key, plaintext). The nonce is fresh-random per call (GCM nonce-reuse is the footgun)."""
    nonce = os.urandom(_NONCE_LEN)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, None)


def _open(key: bytes, blob: bytes) -> bytes:
    if len(blob) <= _NONCE_LEN:
        raise SyncCryptoError("ciphertext too short")
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    try:
        return AESGCM(key).decrypt(nonce, ct, None)
    except InvalidTag as exc:  # wrong key or tampered → fail closed
        raise SyncCryptoError("decryption failed (wrong key or tampered data)") from exc


def generate_recovery_code() -> str:
    """A high-entropy, human-copyable recovery code — 25 base32 chars in 5 groups (~115 bits)."""
    raw = base64.b32encode(os.urandom(15)).decode("ascii").rstrip("=")  # 24 chars
    return "-".join(raw[i : i + 5] for i in range(0, len(raw), 5))


def _normalize_code(code: str) -> str:
    """Recovery codes compare case-insensitively, ignoring spaces/dashes."""
    return code.replace("-", "").replace(" ", "").upper()


@dataclass(frozen=True)
class SyncKeyring:
    """Locally-stored, plaintext-free key material: the DEK sealed under the passphrase AND the recovery code.
    Contains no key/passphrase/recovery-code/plaintext. Persisted via app_settings (SP3c); never synced."""

    salt_pass: bytes
    wrapped_pass: bytes
    salt_recovery: bytes
    wrapped_recovery: bytes

    def to_dict(self) -> dict:
        b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
        return {
            "v": 1,
            "salt_pass": b64(self.salt_pass),
            "wrapped_pass": b64(self.wrapped_pass),
            "salt_recovery": b64(self.salt_recovery),
            "wrapped_recovery": b64(self.wrapped_recovery),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SyncKeyring:
        d = lambda k: base64.b64decode(data[k])  # noqa: E731
        return cls(d("salt_pass"), d("wrapped_pass"), d("salt_recovery"), d("wrapped_recovery"))


def create_keyring(passphrase: str) -> tuple[SyncKeyring, str]:
    """Make a fresh random DEK, seal it under ``passphrase`` + a freshly-generated recovery code. Returns the keyring
    (store locally) + the recovery code (show ONCE — it is not recoverable later)."""
    if not passphrase or not passphrase.strip():
        raise SyncCryptoError("a non-empty passphrase is required")
    dek = os.urandom(_KEY_LEN)
    recovery = generate_recovery_code()
    salt_p, salt_r = os.urandom(_SALT_LEN), os.urandom(_SALT_LEN)
    keyring = SyncKeyring(
        salt_pass=salt_p,
        wrapped_pass=_seal(_derive_kek(passphrase, salt_p), dek),
        salt_recovery=salt_r,
        wrapped_recovery=_seal(_derive_kek(_normalize_code(recovery), salt_r), dek),
    )
    return keyring, recovery


def unlock_with_passphrase(keyring: SyncKeyring, passphrase: str) -> bytes:
    """The DEK, or raise ``SyncCryptoError`` on a wrong passphrase (fails closed)."""
    return _open(_derive_kek(passphrase or "", keyring.salt_pass), keyring.wrapped_pass)


def unlock_with_recovery(keyring: SyncKeyring, code: str) -> bytes:
    return _open(_derive_kek(_normalize_code(code or ""), keyring.salt_recovery), keyring.wrapped_recovery)


def rewrap_passphrase(keyring: SyncKeyring, current_passphrase: str, new_passphrase: str) -> SyncKeyring:
    """Rotate the passphrase: unlock the DEK with the current one, re-seal under the new one. The recovery wrap is
    untouched, and the data is NOT re-encrypted (the DEK is unchanged)."""
    if not new_passphrase or not new_passphrase.strip():
        raise SyncCryptoError("a non-empty passphrase is required")
    dek = unlock_with_passphrase(keyring, current_passphrase)
    salt_p = os.urandom(_SALT_LEN)
    return SyncKeyring(
        salt_pass=salt_p,
        wrapped_pass=_seal(_derive_kek(new_passphrase, salt_p), dek),
        salt_recovery=keyring.salt_recovery,
        wrapped_recovery=keyring.wrapped_recovery,
    )


# --- record encryption (the opaque blob the endpoint would store; it never sees the DEK or any plaintext) ---


def encrypt_payload(dek: bytes, payload: dict) -> str:
    """A syncable record's payload → an opaque base64 blob (nonce||AES-GCM ct). Canonical JSON so the same payload
    always encrypts to the same plaintext input (deterministic hashing happens separately in changeset.py)."""
    plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return base64.b64encode(_seal(dek, plaintext)).decode("ascii")


def decrypt_payload(dek: bytes, blob: str) -> dict:
    """Inverse of ``encrypt_payload``; raises ``SyncCryptoError`` on a wrong key / tampered blob."""
    data = json.loads(_open(dek, base64.b64decode(blob)).decode("utf-8"))
    if not isinstance(data, dict):
        raise SyncCryptoError("decrypted payload was not an object")
    return data
