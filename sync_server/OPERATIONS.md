# sync-server operations runbook (backlog #15)

A maintainer-facing runbook for the self-hosted sync server — backup/restore, retention, and rate-limit tuning.
Companion to `README.md` (what it does, how to run it) and `.claude/security-audits/2026-06-29_sync-server.md`
(the threat model). This doc describes procedures you run on your own infrastructure; nothing here is something
Claude/Codex executes on your behalf.

## What a backup here actually protects (read this first)

`sync_server`'s database holds **only opaque AES-GCM ciphertext** plus routing metadata (`user_id`, `collection`,
`record_id`, `version`, a per-user `seq`) — it never holds the DEK, and it never decrypts anything. That means:

- **A sync-server backup restores *sync state* — not anyone's library.** Each client's own local callosum
  database (its own SQLite file) is the actual source of truth for that user's papers, notes, and axes. Losing
  the sync server (with no backup) doesn't destroy anyone's library; it just means every device does a fresh
  full push next time it syncs, and any *cross-device* history/conflict record is gone.
- **A backup is worth taking anyway** so a server-side outage/corruption doesn't force every user's device to
  redo a full push (`push()`'s upsert-by-version and `pull(since=0)` fallback both make this recoverable, just
  slower and more bandwidth-heavy than restoring a recent dump).
- **The backup file itself is still meaningful ciphertext** — it can't be read without each record's own DEK
  (which lives only on the devices that encrypted it), but treat it with the same handling care as any other
  database dump: don't publish it, and restrict who can read the file on disk.

## Backup (Postgres)

```bash
# A plain logical dump — portable, human-inspectable table structure, easy to restore selectively if needed.
pg_dump --format=custom --file="callosum_sync_$(date +%Y%m%d).dump" "$CALLOSUM_SYNC_DB_URL_WITHOUT_DRIVER_PREFIX"

# e.g. if CALLOSUM_SYNC_DB_URL is postgresql+psycopg://user:pass@host:5432/callosum_sync, pg_dump wants:
pg_dump --format=custom --file="callosum_sync_$(date +%Y%m%d).dump" \
  --host=host --port=5432 --username=user --dbname=callosum_sync
```

Run this on a schedule that matches how much resync pain you're willing to risk (daily is a reasonable starting
point for a personal/small-team deploy — the tables are tiny: opaque blobs capped at ~2MB each,
`MAX_RECORDS_PER_PUSH` = 1000 per push, no file storage). Keep a handful of recent dumps, not just the latest —
a corrupted or mid-write dump is a real (if rare) failure mode you want to be able to roll back past.

## Restore

```bash
# Restore into a FRESH, empty database — never restore over a live one you still need (this is destructive to
# whatever's currently there).
createdb callosum_sync_restored
pg_restore --dbname=callosum_sync_restored callosum_sync_20260722.dump

# Point the server at it (temporarily, to verify) before cutting over CALLOSUM_SYNC_DB_URL for real:
CALLOSUM_SYNC_DB_URL="postgresql+psycopg://user:pass@host:5432/callosum_sync_restored" \
  uvicorn sync_server.app:app --host 127.0.0.1 --port 8771
curl http://127.0.0.1:8771/health   # {"status": "ok", "configured": true}
```

Verify at least one real account's `GET /sync/records?since=0` returns the expected row count before treating
the restore as good and repointing the real `CALLOSUM_SYNC_DB_URL` at it.

## Retention (tombstone pruning)

Deleted records are stored as **tombstones** (`deleted=1`, `ciphertext=NULL`) rather than removed immediately —
every syncing device needs to see the tombstone at least once so it knows to delete its own local copy too. Left
alone, tombstones accumulate forever. `python -m sync_server.prune_tombstones` removes tombstones older than
`CALLOSUM_SYNC_RETENTION_DAYS` (default 90).

**The trade-off, stated plainly:** a device that hasn't synced in longer than the retention window, and still
holds a local copy of a since-deleted record, can "resurrect" that record by pushing an update to it *after* its
tombstone has already been pruned server-side — the server has no way to confirm every device actually saw a
given tombstone before removing it (there's a per-user write high-water mark, `sync_cursor`, but no per-device
*read* cursor to check against). This is a real, understood, and accepted trade-off for a personal/small-team
tool — not a bug, but worth remembering if a device goes offline for months at a time.

Run it manually to see what would happen first:

```bash
python -m sync_server.prune_tombstones --dry-run
```

Then wire it into cron (adjust the path/venv to your actual deploy):

```cron
# Prune sync-server tombstones daily at 03:17 (an off-peak minute, avoids the top-of-hour pile-up).
17 3 * * * cd /path/to/callosum/sync_server && /path/to/venv/bin/python -m sync_server.prune_tombstones >> /var/log/callosum-sync-prune.log 2>&1
```

Widen `--older-than-days` (or `CALLOSUM_SYNC_RETENTION_DAYS`) if your devices routinely go offline longer than
the default 90-day window — the cost of a wider window is only disk space (tombstone rows carry no ciphertext).

## Rate limiting

`CALLOSUM_SYNC_RATE_LIMIT_MAX` (default 60) requests per `CALLOSUM_SYNC_RATE_LIMIT_WINDOW_SECONDS` (default 60),
**per user** (keyed by the OIDC `sub` — every device a given account syncs from shares one bucket, since the
token carries no per-device identity to key more finely). A request over the limit gets `429` with a
`Retry-After` header naming how many seconds until the next request would be allowed. Raise the limit if a
legitimate multi-device household is tripping it during normal use; the default is generous for typical
periodic-poll sync traffic, not for a tight interactive polling loop.

## What's genuinely still open (not covered by this pass)

- **Per-user storage quota** — nothing today caps how many *live* (non-tombstone) records or how much total
  ciphertext one account can accumulate. Not built in this pass; a real concern only once this moves beyond a
  single-maintainer or small-team self-host.
- **A real migration tool** — schema changes today are handled by `metadata.create_all()` for new tables, plus
  one-off targeted `ALTER`s (`schema.ensure_updated_at_column`) for columns added to an already-deployed table.
  Fine at this scale; not a general Alembic-style tool. The next schema change will need its own similar targeted
  helper unless this gets built first.
