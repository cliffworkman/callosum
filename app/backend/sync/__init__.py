"""Accounts SP3 — end-to-end-encrypted multi-device sync.

SP3a (this slice): the **local, no-egress** foundation — `crypto.py` (passphrase/recovery → key → AES-GCM record
encryption) + `changeset.py` (content-hash change-tracking + the last-write-wins, conflict-surfacing merge core).
See the design spec `.claude/docs/specs/2026-06-29-accounts-sync-design.md`. The sync endpoint + push/pull loop is
SP3b; the opt-in Settings UI + conflict review is SP3c.
"""
