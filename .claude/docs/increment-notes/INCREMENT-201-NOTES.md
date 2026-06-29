# Increment 201 — accounts SP3b cont.: natural-key identity for tags (the cross-device-collision fix)

## Implemented

Closes the one real correctness gap left in the sync engine: the **`tags.name` UNIQUE collision**. Without this, the
*first* real sync between two established libraries that each have a same-named tag (a `to-read`, a `review`) would
crash with an `IntegrityError` — apply would try to INSERT a duplicate-named tag. **Local, no-egress, no migration,
no new dependency.**

- **`app/backend/sync/changeset.py`**
  - `SyncableCollection` gains **`natural_key: str | None`** — a UNIQUE column whose value derives a **deterministic**
    `sync_uid` (vs the default random uuid).
  - New `_natural_uid(collection, value)` = `sha256(f"{collection}\x00{value}").hexdigest()` (fits `String(64)`;
    collection-scoped so a tag and an axis named the same don't collide).
  - `ensure_identities` selects the natural-key column when set and assigns `_natural_uid(...)` instead of `_new_uid()`
    for those rows.
  - `SYNCABLE`: **tags** now `natural_key="name"`. (papers/axes/notes/annotations keep random uids — their
    titles/labels aren't UNIQUE; paper_tags is a link table.)

## Key technical detail

**Why deterministic-from-name beats reconcile-on-apply:** a tag's app-level identity *is* its UNIQUE name (the inc-71
get-or-create-by-name model). If both devices derive the tag's `sync_uid` from that name, they independently pick the
**same** uid for `"topic"` — so the same logical tag is the same sync record from the start. On apply, the engine's
existing `local_id_for_uid` finds device B's own `"topic"` (same deterministic uid) and **UPDATEs** it rather than
INSERTing a duplicate → no UNIQUE violation, automatic convergence. The alternative (random uids + reconcile-by-name
on apply) would need a tie-break + re-keying the loser across `sync_identity` + `sync_state` — far churnier. The whole
fix lives in `ensure_identities`; collect/apply/merge are untouched, and paper_tags links converge for free (both
devices reference the same tag uid).

## Manual verification script

No UI / no endpoint — the hermetic engine tests:
`HF_HUB_OFFLINE=1 python -m pytest tests/test_sync_engine.py -q` → 8 passed, including
`test_tags_converge_by_name_not_collide` (two devices independently create tag `"topic"`; after sync each has exactly
one `"topic"` with the same sync_uid; no crash; re-sync is a no-op) + `test_natural_uid_is_deterministic_and_scoped`.

## Gates

- **pytest:** full suite green — **692 passed, 1 skipped** (+2 engine tests).
- **ruff** check + format clean.
- **QA surface unchanged** — 132/132 API + 661/661 FE, 0 uncovered (engine-only; no new route).
- **Audit:** addendum 3 to `.claude/security-audits/2026-06-29_sync-engine-sp3b.md` **PASS** (resolves the
  addendum-2 known limitation).
- **Principles/A-A:** the SP3 gate ran in SP3a → non-triggering beyond honoring it (no egress; conflicts surfaced).
- **No migration, no new dependency, no egress, no UI.**

## NEXT

With this, the client sync engine is **robust + collection-complete** (papers · tags · axes · notes · annotations ·
tag-assignments; summaries deferred-as-not-synced; manual cluster membership a later redesign). The next real step is
the **reference sync-server** — the slice where ciphertext actually leaves the machine → its own security audit + the
maintainer standing up infra + a hosting decision (a pause-and-plan-together step, not a solo build). Then the
`app_settings` cursor wiring + **SP3c** (the opt-in Settings → Sync UI + conflict review).
