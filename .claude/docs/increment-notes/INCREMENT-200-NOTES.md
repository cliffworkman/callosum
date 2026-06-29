# Increment 200 — accounts SP3b cont.: the link-table model (paper_tags)

## Implemented

Extends the sync engine to the **composite-PK link table** `paper_tags` (tag assignments) — completing the
user-authored relational data (papers · tags · notes · annotations · **tag assignments**). A link has no own `id`, so
its **identity is derived from its endpoints**: the sync key is the joined endpoint sync_uids, identical on every
device. **No migration, no new endpoint, no egress, no dependency.**

- **`app/backend/sync/changeset.py`**
  - `SyncableCollection.pk` is now **`str | None`** — `pk=None` marks a **link table** (identity = its endpoints).
  - `SYNCABLE` += **paper_tags** (`pk=None`, `fks={"paper_id":"papers","tag_id":"tags"}`), last (referenced-first).
  - `ensure_identities` **skips** link tables (no own identity to assign).
  - the new `_outbound(c, row, maps)` helper (shared by both shapes) returns `(record_id, payload)`: for a normal
    collection, record_id = the row's own sync_uid; **for a link, record_id = the joined translated endpoint uids**
    (`"<paper_uid>|<tag_uid>"`) and the payload = the translated endpoints. `collect_local` now just calls it.
  - Also recorded: **`summaries` is explicitly NOT synced** (a regeneratable synthesis whose verification is keyed to
    device-local chunk/embedding versions — like embeddings/signals), and manual `cluster_node_papers` stays deferred
    (needs an axis-membership identity, since `cluster_nodes` are derived).
- **`app/backend/sync/engine.py`**
  - `_apply_link(conn, c, r, by_name)` — split `record_id` on `|` → resolve each endpoint uid → this device's local
    id (`local_id_for_uid`); **INSERT-OR-IGNORE** the link (existence-checked composite PK) / **DELETE** on a
    tombstone; returns **False (skip, retry)** if an endpoint isn't local yet. `_apply_record` dispatches to it when
    `c.pk is None`.
  - the push-tombstone `forget_identity` is guarded (`pk is not None`) — a link has no own identity to forget.

## Key technical detail

**Why a link table needs a different identity:** a composite-PK link (paper_id, tag_id) has no own autoincrement id to
hang a `sync_uid` on, and assigning it a *random* per-device uid wouldn't converge (each device would invent a
different uid for the same logical link → duplicates). The fix is that a link's identity is **derived** from its
endpoints' (global) uids: `record_id = "<paper sync_uid>|<tag sync_uid>"` is computed identically on every device, so
the same tag-on-paper assignment keys the same everywhere. The payload carries the two endpoint uids; apply resolves
them back to each device's local ids and INSERT-OR-IGNOREs the link (a tombstone deletes it). uuid4 hex contains no
`|`, so splitting the record_id is unambiguous.

## Manual verification script

No UI / no endpoint — the hermetic engine tests:
`HF_HUB_OFFLINE=1 python -m pytest tests/test_sync_engine.py -q` → 6 passed, including
`test_link_table_paper_tags_sync` (a paper↔tag link syncs to a device with offset ids and lands on its local
`(paper_id, tag_id)` [`bpid != pid`]; a converged re-sync is a no-op; un-tagging on one device propagates as a
tombstone that removes the link on the other while leaving the paper + tag intact).

## Gates

- **pytest:** full suite green — **690 passed, 1 skipped** (+1 engine test).
- **ruff** check + format clean.
- **QA surface unchanged** — 132/132 API + 661/661 FE, 0 uncovered (engine-only; no new route).
- **Audit:** addendum 2 to `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` **PASS** (device-independent link
  identity, skip-not-dangling apply, idempotent insert / tombstone delete, referenced-first ordering).
- **Principles/A-A:** the SP3 gate ran in SP3a → non-triggering beyond honoring it (no egress; conflicts surfaced).
- **No migration, no new dependency, no egress, no UI.**
- **Known limitation (recorded):** `tags.name` is UNIQUE → two devices independently creating a same-named tag
  (different uids) before first sync would collide on apply — a pre-existing inc-198 tags concern (the link path is
  unaffected); the fix is natural-key reconciliation on apply, a follow-on before the live server.

## NEXT

This completes the **client sync engine's collection coverage** (papers · tags · axes · notes · annotations ·
paper_tags). Deferred-with-rationale: `summaries` (not synced — derived), manual `cluster_node_papers` (axis-membership
identity redesign). The next real step is the **reference sync-server** (the slice where ciphertext actually leaves
the machine → its own audit) + the `app_settings` cursor wiring + natural-key tag reconciliation, then **SP3c** (the
opt-in Settings → Sync UI + conflict review).
