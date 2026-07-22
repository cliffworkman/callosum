# Increment 341 — Backlog #15: sync_server hardening (rate limiting, retention, backup runbook)

## Context
Next in the 12-item decision queue. Cliff: "yes, build the hardening code" — three of the four pre-public-deploy
follow-ons the 2026-06-29 sync-server audit originally recorded (per-user rate-limiting, blob retention, a
backup runbook); a storage quota and a general migration tool stay explicitly out of scope. The live deploy on
Cliff's own "juno" box stays entirely his infra — this increment touches only `sync_server/` code and its own
docs, never his running instance.

## Implemented
- **Rate limiting** (`sync_server/rate_limit.py`, new): a standalone reimplementation of the main app's
  `access_control.RateLimiter` sliding-window shape — deliberately not imported cross-package, since
  `sync_server` is a fenced, independently-deployable service (the original audit's own invariant). Keyed by
  the caller's OIDC `sub` (the only identity available; there's no per-device claim in the token). Wired into
  both `/sync/records` routes via a `_rate_limited` FastAPI dependency composing on top of the existing
  `_identity` check. Over the limit → `429` + a `Retry-After` header. Defaults (60 req/60s) are env-tunable.
- **Retention** (`sync_server/store.py::prune_tombstones`, new): tombstones older than
  `CALLOSUM_SYNC_RETENTION_DAYS` (default 90, Cliff's chosen policy) become eligible for removal. Shipped as a
  plain CLI (`python -m sync_server.prune_tombstones`, `--dry-run` supported) for Cliff's own cron/systemd timer
  — not an in-process background scheduler, keeping the request-serving process simple and the job
  independently retryable. Fails toward preservation in every ambiguous case: a live (non-tombstone) record is
  never touched regardless of age, and a tombstone with no recorded age (a pre-migration NULL `updated_at`) is
  never assumed old enough to prune.
- **Schema + defensive migration:** `sync_records` gained an `updated_at` column (stamped on every push).
  Since `metadata.create_all()` never alters an already-existing table, `schema.ensure_updated_at_column` is a
  single, targeted, idempotent `ALTER TABLE` that runs on every startup — explicitly not a general migration
  tool (that stays its own separate, un-scoped follow-on), just a one-time self-heal for this one addition.
- **Backup runbook** (`sync_server/OPERATIONS.md`, new): `pg_dump`/`pg_restore` procedure, the retention cron
  entry, rate-limit tuning notes, and — the honesty point worth restating — what a sync-server backup actually
  protects (opaque ciphertext + routing metadata only; never a user's plaintext library, since the server never
  holds a DEK and each device's own local DB remains that user's actual source of truth).
- `sync_server/README.md` updated: new env vars documented, the "Not yet" section split into what this pass
  closed vs. what's still genuinely open (a per-user quota, a real migration tool).

## Key technical detail
The retention trade-off is the one genuinely hard design point here, surfaced to Cliff before building rather
than assumed: pruning a tombstone is only fully safe once every device has pulled it, but the server has no
per-device read-cursor (only a per-user write high-water mark, `sync_cursor`) to confirm that. A time-based
grace period (90 days, Cliff's choice) accepts a bounded, explicitly-documented risk — a device offline longer
than the window could resurrect an already-pruned deleted record on its next push — rather than either never
pruning (the status quo) or guessing at a "safe" mechanism that doesn't actually exist with today's schema.

## Principles/A-A gate (rule #9)
This doesn't touch a literature claim/signal/judgment surface, so the primary gate doesn't trigger. It does
touch operational trust (A-A-adjacent): the retention trade-off is stated plainly in three places (the
`prune_tombstones` docstring, the README, `OPERATIONS.md`) rather than buried — the same "silence is not a
certificate" instinct the charter applies to literature signals applies here too, to an infrastructure
trade-off Cliff (and anyone else who ever self-hosts this) needs to actually see.

## Tests
- `tests/test_sync_server.py` (+8): per-user rate-limit isolation (Bob's traffic never counts against Alice's
  bucket — mirrors the existing `test_tenant_isolation` pattern) on both GET and POST; the generous default
  doesn't trip on ordinary traffic; tombstone pruning removes only old tombstones, never live records, never a
  NULL-age row; `ensure_updated_at_column` is idempotent against a table built without the column; the CLI
  script's dry-run/real-run/second-run-finds-nothing-left sequence.
- Full suite: **1396 passed, 1 skipped** (`pytest -n auto -q`, ~8.5 min).
- Line budget: 351/351 (unaffected — `sync_server/` isn't under `app/`/`integrations/`, exempt per rule #1, but
  every new file is small regardless). QA surface map: unaffected (sync_server isn't part of the two source
  trees the tool walks — it's a separate deployable, same as before this increment).

## Gates
- **Security audit:** extended `.claude/security-audits/2026-06-29_sync-server.md` with a new addendum — PASS.
  Closes 3 of the 4 pre-public-deploy items that audit originally recorded.

## Backlog
**#15 closed** for the three items Cliff asked for (rate-limiting, retention, backup runbook). The per-user
storage quota and the general migration tool remain open, named explicitly in `sync_server/README.md`'s "Not
yet" section — not silently dropped, just genuinely out of this pass's scope.

## Next
Remaining in the 12-item queue: #20 remainder (uv, pre-commit config, CI gates one at a time, a
staged-harnesses registry, branch protection — the last needs the exact ruleset shown to Cliff before applying)
and #21 (packaging/distribution exploration, Tauri desktop shell).
