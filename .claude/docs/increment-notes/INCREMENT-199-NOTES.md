# Increment 199 — accounts SP3b cont.: the FK-translation layer + the child tables (notes, annotations)

## Implemented

Extends the inc-198 sync engine to the **FK-bearing child tables** — **notes** + **annotations** (the user's notes +
highlights, the high-value relational data) — via a generic **FK-translation layer**. A row's foreign-key columns are
carried as the *referenced row's* `sync_uid` (device-independent) and translated back to each device's local id on
apply. **No migration, no new endpoint, no egress, no dependency** — `sync_identity` + the engine already exist.

- **`app/backend/sync/changeset.py`**
  - `SyncableCollection` gains **`fks: dict[str,str]`** (`{fk_column: referenced collection}`) + **`drop: tuple[...]`**
    (device-local columns omitted from the synced payload).
  - `SYNCABLE` extended, in **referenced-first dependency order**: papers, tags, axes, **notes** (`fks={"paper_id":
    "papers"}`), **annotations** (`fks={"paper_id":"papers"}`, `drop=("attachment_id",)`).
  - `collect_local` now builds every collection's `uid_map` once, then per row: drops `pk` + `drop` columns, and
    **translates each FK column local-id → the referenced row's sync_uid**; a row whose FK target has no identity yet
    is skipped (defensive).
- **`app/backend/sync/engine.py`**
  - `_apply_record(conn, c, r, by_name) → bool` — translates each FK column **referenced sync_uid → this device's
    local id** (`local_id_for_uid`); returns **False** (skip, don't advance `sync_state`) if a target isn't local yet.
  - the apply loop runs **referenced-collections-first** (sorted by `SYNCABLE` rank), so a record's FK targets are
    written before it; `SyncRunResult.applied` is now the actually-applied count.

## Key technical detail

**Why FK-translation:** an FK column holds a *device-local* int id that means nothing on another device. So the
synced payload carries the **referenced row's `sync_uid`** instead; the content (and its hash) are then identical on
every device, and on apply the engine resolves that uid → the local id the referenced row has *on this device*.
Combined with **referenced-first apply ordering**, a note/annotation's `paper_id` always lands on the right local
paper. The same uid-form payload is what's hashed for `sync_state`, so a converged pair re-syncs to 0 push / 0 apply.

**Device-local columns are dropped, not translated:** `annotations.attachment_id` points at a per-device linked PDF
(attachments aren't synced), so it's declared in `drop` — omitted from the payload entirely and applied as NULL on
the far device. The highlight still renders (it's keyed on paper + page + bboxes, the inc-30 overlay model).

## Manual verification script

No UI / no endpoint — exercised by the hermetic engine tests:
`HF_HUB_OFFLINE=1 python -m pytest tests/test_sync_engine.py -q` → 5 passed, including
`test_child_tables_fk_translate_across_devices` (a note + an annotation sync to a device with offset local ids; their
`paper_id` re-points to that device's local paper; `attachment_id` drops to NULL; a converged re-sync is a no-op).

## Gates

- **pytest:** full suite green — **689 passed, 1 skipped** (+1 engine test).
- **ruff** check + format clean.
- **QA surface unchanged** — 132/132 API + 661/661 FE, 0 uncovered (engine-only; no new route).
- **Audit:** addendum to `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` **PASS** (FK-translation safety,
  referenced-first ordering, device-local-column drop, hash round-trip, unchanged egress posture).
- **Principles/A-A:** the SP3 gate was run in SP3a; this slice adds no new claim/signal → non-triggering beyond
  honoring it (E2E held; no egress; conflicts still surfaced).
- **No migration, no new dependency, no egress, no UI.**

## NEXT

The remaining FK-bearing collections that need a distinct shape: **`paper_tags`** (a composite-PK link table — identity
is its endpoint-uid pair, no own id), then **`summaries`** (JSON-embedded scope refs + device-local
version-keyed verification — possibly snapshot-only or not-synced) + **manual `cluster_node_papers`** (depends on
un-synced `cluster_nodes` → needs an axis-membership identity strategy). Then the **reference sync-server** (the slice
where ciphertext actually leaves → its own audit) + the `app_settings` cursor wiring, then **SP3c** (the opt-in
Settings → Sync UI + conflict review).
