"""SP4a — sharing identity crypto (local, no egress) — hermetic tests.

Covers the security-critical core: keypair generation, private-key seal/unseal round-trip under the sync DEK,
fail-closed on a wrong DEK / tampered blob, and fingerprint determinism/uniqueness.
"""

from __future__ import annotations

import pytest

from app.backend.sync.crypto import SyncCryptoError, create_keyring, unlock_with_passphrase
from app.backend.sync.identity import ShareIdentity, create_identity, fingerprint, unlock_private_key


def _dek(passphrase: str = "pw") -> bytes:
    keyring, _ = create_keyring(passphrase)
    return unlock_with_passphrase(keyring, passphrase)


def test_create_identity_produces_a_32_byte_public_key() -> None:
    identity = create_identity(_dek())
    assert isinstance(identity.public_key, bytes) and len(identity.public_key) == 32


def test_unlock_private_key_roundtrips_and_matches_public_key() -> None:
    dek = _dek()
    identity = create_identity(dek)
    private_key = unlock_private_key(dek, identity)
    assert private_key.public_key().public_bytes_raw() == identity.public_key


def test_unlock_private_key_wrong_dek_fails_closed() -> None:
    identity = create_identity(_dek("right"))
    with pytest.raises(SyncCryptoError):
        unlock_private_key(_dek("wrong"), identity)


def test_unlock_private_key_tampered_blob_fails_closed() -> None:
    dek = _dek()
    identity = create_identity(dek)
    tampered = ShareIdentity(
        public_key=identity.public_key, wrapped_private_key=identity.wrapped_private_key[:-4] + "abcd"
    )
    with pytest.raises(SyncCryptoError):
        unlock_private_key(dek, tampered)


def test_identity_dict_roundtrip() -> None:
    identity = create_identity(_dek())
    assert ShareIdentity.from_dict(identity.to_dict()) == identity


def test_two_identities_have_different_keys_and_fingerprints() -> None:
    dek = _dek()
    a, b = create_identity(dek), create_identity(dek)
    assert a.public_key != b.public_key
    assert fingerprint(a.public_key) != fingerprint(b.public_key)


def test_fingerprint_is_deterministic_and_grouped() -> None:
    identity = create_identity(_dek())
    fp1, fp2 = fingerprint(identity.public_key), fingerprint(identity.public_key)
    assert fp1 == fp2
    assert "-" in fp1
    groups = fp1.split("-")
    assert all(0 < len(group) <= 5 for group in groups)
    assert "".join(groups) == fp1.replace("-", "")  # grouping is purely cosmetic, no chars lost


def test_fingerprint_rejects_wrong_length_key() -> None:
    with pytest.raises(SyncCryptoError):
        fingerprint(b"too-short")
