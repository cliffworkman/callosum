"""SP3a — sync crypto + local change-tracking/merge foundation (local, no egress) — hermetic tests.

Covers the security-critical core: E2E key round-trips (passphrase + recovery), fail-closed on a wrong key /
tampered blob, the **opaque-blob guarantee** (no plaintext in the ciphertext), passphrase rotation; and the
change-tracking hash-diff (add/edit/delete) + the last-write-wins, **conflict-surfacing** merge.
"""

from __future__ import annotations

import base64

import pytest
from sqlalchemy import create_engine, delete, insert, select, update

from app.backend.persistence import schema
from app.backend.sync import changeset
from app.backend.sync.crypto import (
    SyncCryptoError,
    SyncKeyring,
    create_keyring,
    decrypt_payload,
    encrypt_payload,
    rewrap_passphrase,
    unlock_with_passphrase,
    unlock_with_recovery,
)
from tests.api_helpers import _seed_library

# --- crypto ---


def test_keyring_passphrase_and_recovery_unlock_same_dek() -> None:
    keyring, recovery = create_keyring("correct horse battery staple")
    dek = unlock_with_passphrase(keyring, "correct horse battery staple")
    assert isinstance(dek, bytes) and len(dek) == 32
    assert unlock_with_recovery(keyring, recovery) == dek  # the recovery code is an independent unlock
    # recovery codes compare case/format-insensitively (dashes + case ignored)
    assert unlock_with_recovery(keyring, recovery.lower().replace("-", "")) == dek


def test_wrong_passphrase_and_recovery_fail_closed() -> None:
    keyring, _ = create_keyring("right")
    with pytest.raises(SyncCryptoError):
        unlock_with_passphrase(keyring, "wrong")
    with pytest.raises(SyncCryptoError):
        unlock_with_recovery(keyring, "AAAAA-BBBBB-CCCCC-DDDDD-EEEEE")


def test_empty_passphrase_rejected() -> None:
    with pytest.raises(SyncCryptoError):
        create_keyring("   ")


def test_record_encrypt_roundtrip_and_opaque_blob() -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    payload = {"title": "SECRET-TITLE-XYZ", "doi": "10.1/secret", "year": 2026}
    blob = encrypt_payload(dek, payload)
    # the opaque-blob guarantee: the plaintext appears nowhere — not in the b64 string, not in the raw bytes
    assert "SECRET-TITLE-XYZ" not in blob
    assert b"SECRET-TITLE-XYZ" not in base64.b64decode(blob)
    assert decrypt_payload(dek, blob) == payload


def test_tampered_blob_fails_closed() -> None:
    keyring, _ = create_keyring("pw")
    dek = unlock_with_passphrase(keyring, "pw")
    raw = bytearray(base64.b64decode(encrypt_payload(dek, {"a": 1})))
    raw[-1] ^= 0x01  # flip a ciphertext bit
    with pytest.raises(SyncCryptoError):
        decrypt_payload(dek, base64.b64encode(bytes(raw)).decode("ascii"))


def test_decrypt_with_other_keyrings_dek_fails() -> None:
    k1, _ = create_keyring("pw")
    k2, _ = create_keyring("pw")  # independent DEK
    blob = encrypt_payload(unlock_with_passphrase(k1, "pw"), {"a": 1})
    with pytest.raises(SyncCryptoError):
        decrypt_payload(unlock_with_passphrase(k2, "pw"), blob)


def test_rewrap_passphrase_keeps_dek_and_recovery() -> None:
    keyring, recovery = create_keyring("old")
    dek = unlock_with_passphrase(keyring, "old")
    blob = encrypt_payload(dek, {"x": "y"})
    kr2 = rewrap_passphrase(keyring, "old", "new")
    assert unlock_with_passphrase(kr2, "new") == dek  # same DEK → existing data still decrypts
    assert decrypt_payload(unlock_with_passphrase(kr2, "new"), blob) == {"x": "y"}
    with pytest.raises(SyncCryptoError):
        unlock_with_passphrase(kr2, "old")  # the old passphrase no longer works
    assert unlock_with_recovery(kr2, recovery) == dek  # recovery wrap preserved across rotation


def test_keyring_dict_roundtrip() -> None:
    keyring, _ = create_keyring("pw")
    assert SyncKeyring.from_dict(keyring.to_dict()) == keyring


# --- change-tracking (hash-diff against sync_state) ---


def _record_state(conn, changes) -> None:
    """Simulate a completed sync: write sync_state for the given (non-deleted) local changes."""
    for c in changes:
        if c.deleted:
            continue
        conn.execute(
            insert(schema.sync_state).values(
                collection=c.collection,
                record_id=c.record_id,
                content_hash=changeset.record_hash(c.payload),
                version=c.new_version,
                deleted=0,
            )
        )


def test_local_changeset_tracks_add_edit_delete(temp_db_url: str) -> None:
    _seed_library(temp_db_url)
    engine = create_engine(temp_db_url)

    with engine.begin() as conn:
        initial = changeset.local_changeset(conn)
        assert initial, "seeded rows should be 'new' when sync_state is empty"
        assert any(c.collection == "papers" for c in initial)
        assert all(c.new_version == 1 and not c.deleted for c in initial)
        _record_state(conn, initial)

    with engine.begin() as conn:
        assert changeset.local_changeset(conn) == [], "nothing changed since the recorded state"

    # edit one paper → exactly that record is a change, version bumped to 2
    with engine.begin() as conn:
        pid = conn.execute(select(schema.papers.c.id)).scalars().first()
        conn.execute(update(schema.papers).where(schema.papers.c.id == pid).values(abstract="changed abstract"))
    with engine.begin() as conn:
        changes = changeset.local_changeset(conn)
        assert [(c.collection, c.record_id, c.new_version, c.deleted) for c in changes] == [
            ("papers", str(pid), 2, False)
        ]

    # delete the seeded tag (+ its link) → tombstones for the now-missing rows
    with engine.begin() as conn:
        conn.execute(delete(schema.paper_tags))
        conn.execute(delete(schema.tags))
    with engine.begin() as conn:
        deletes = [c for c in changeset.local_changeset(conn) if c.deleted]
        assert any(c.collection == "tags" for c in deletes)
        assert all(c.payload is None for c in deletes)

    engine.dispose()


def test_record_hash_is_stable_and_content_sensitive() -> None:
    a = {"title": "x", "year": 2026}
    assert changeset.record_hash(a) == changeset.record_hash({"year": 2026, "title": "x"})  # key order irrelevant
    assert changeset.record_hash(a) != changeset.record_hash({"title": "x", "year": 2027})


# --- the LWW + conflict-surfacing merge ---


def test_merge_remote_newer_applies_no_conflict() -> None:
    remote = [changeset.RemoteRecord("papers", "1", version=2, deleted=False, payload={"t": "remote"})]
    result = changeset.merge_remote(
        local_versions={("papers", "1"): 1}, local_payloads={}, locally_changed=set(), remote=remote
    )
    assert result.to_apply == remote and result.conflicts == []


def test_merge_remote_concurrent_change_surfaces_conflict() -> None:
    key = ("papers", "1")
    remote = [changeset.RemoteRecord("papers", "1", version=2, deleted=False, payload={"t": "remote"})]
    result = changeset.merge_remote(
        local_versions={key: 1},
        local_payloads={key: {"t": "local-edit"}},
        locally_changed={key},  # the same record changed on this device since the last sync
        remote=remote,
    )
    assert result.to_apply == remote  # remote (higher version) wins
    assert len(result.conflicts) == 1
    c = result.conflicts[0]
    assert (c.collection, c.record_id) == key and c.losing_payload == {"t": "local-edit"}  # local loser kept (A4)


def test_merge_remote_older_or_equal_is_skipped() -> None:
    remote = [
        changeset.RemoteRecord("papers", "1", version=1, deleted=False, payload={"t": "older"}),  # equal
        changeset.RemoteRecord("papers", "2", version=1, deleted=False, payload={"t": "stale"}),  # older than local
    ]
    result = changeset.merge_remote(
        local_versions={("papers", "1"): 1, ("papers", "2"): 3},
        local_payloads={},
        locally_changed=set(),
        remote=remote,
    )
    assert result.to_apply == [] and result.conflicts == []


def test_merge_remote_tombstone_applies() -> None:
    remote = [changeset.RemoteRecord("tags", "5", version=4, deleted=True, payload=None)]
    result = changeset.merge_remote(
        local_versions={("tags", "5"): 2}, local_payloads={}, locally_changed=set(), remote=remote
    )
    assert result.to_apply == remote and result.to_apply[0].deleted is True
