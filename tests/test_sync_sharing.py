"""SP4b — the sharing content-key wrap (local, no egress) — hermetic tests.

Covers the security-critical core: an ECDH+HKDF+AES-GCM "sealed" wrap/unwrap round-trip, fail-closed on a
wrong recipient private key / tampered envelope / malformed dict, and that repeated wraps never reuse an
ephemeral key or nonce (no replay/correlation signal).
"""

from __future__ import annotations

import dataclasses
import os

import pytest
from cryptography.hazmat.primitives.asymmetric import x25519

from app.backend.sync.crypto import SyncCryptoError
from app.backend.sync.sharing import WrappedKey, unwrap_content_key, wrap_content_key


def _keypair() -> tuple[x25519.X25519PrivateKey, bytes]:
    priv = x25519.X25519PrivateKey.generate()
    return priv, priv.public_key().public_bytes_raw()


def test_wrap_unwrap_roundtrip() -> None:
    recipient_priv, recipient_pub = _keypair()
    content_key = os.urandom(32)
    wrapped = wrap_content_key(content_key, recipient_pub)
    assert unwrap_content_key(wrapped, recipient_priv) == content_key


def test_wrong_recipient_private_key_fails_closed() -> None:
    _recipient_priv, recipient_pub = _keypair()
    wrong_priv, _wrong_pub = _keypair()
    wrapped = wrap_content_key(os.urandom(32), recipient_pub)
    with pytest.raises(SyncCryptoError):
        unwrap_content_key(wrapped, wrong_priv)


def test_tampered_ciphertext_fails_closed() -> None:
    recipient_priv, recipient_pub = _keypair()
    wrapped = wrap_content_key(os.urandom(32), recipient_pub)
    flipped = bytearray(wrapped.ciphertext)
    flipped[-1] ^= 0x01
    tampered = dataclasses.replace(wrapped, ciphertext=bytes(flipped))
    with pytest.raises(SyncCryptoError):
        unwrap_content_key(tampered, recipient_priv)


def test_tampered_ephemeral_public_key_fails_closed() -> None:
    """The ephemeral public key is bound as AES-GCM AAD -- swapping it (even to another valid X25519 key)
    must invalidate the auth tag, not silently derive a different (wrong) shared secret and decrypt garbage."""
    recipient_priv, recipient_pub = _keypair()
    wrapped = wrap_content_key(os.urandom(32), recipient_pub)
    _other_priv, other_pub = _keypair()
    swapped = dataclasses.replace(wrapped, ephemeral_public_key=other_pub)
    with pytest.raises(SyncCryptoError):
        unwrap_content_key(swapped, recipient_priv)


def test_wrap_rejects_wrong_length_inputs() -> None:
    _recipient_priv, recipient_pub = _keypair()
    with pytest.raises(SyncCryptoError):
        wrap_content_key(b"too-short", recipient_pub)
    with pytest.raises(SyncCryptoError):
        wrap_content_key(os.urandom(32), b"not-a-real-key")


def test_repeated_wraps_never_reuse_ephemeral_key_or_nonce() -> None:
    _recipient_priv, recipient_pub = _keypair()
    content_key = os.urandom(32)
    a = wrap_content_key(content_key, recipient_pub)
    b = wrap_content_key(content_key, recipient_pub)
    assert a.ephemeral_public_key != b.ephemeral_public_key
    assert a.nonce != b.nonce
    assert a.ciphertext != b.ciphertext


def test_wrapped_key_dict_roundtrip() -> None:
    _recipient_priv, recipient_pub = _keypair()
    wrapped = wrap_content_key(os.urandom(32), recipient_pub)
    assert WrappedKey.from_dict(wrapped.to_dict()) == wrapped


def test_wrapped_key_from_dict_rejects_malformed_data() -> None:
    with pytest.raises(SyncCryptoError):
        WrappedKey.from_dict({"v": 1, "nonce": "not-base64!!", "ciphertext": "x", "ephemeral_public_key": "y"})
    with pytest.raises(SyncCryptoError):
        WrappedKey.from_dict({"v": 1})
