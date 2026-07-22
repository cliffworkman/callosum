# callosum sync-server (accounts SP3b)

A small, self-hostable, **end-to-end-encrypted** sync backend for callosum. It is a **separate deployable** — the
local callosum app never imports it — and it stores only **opaque AES-GCM blobs** it cannot read (the client encrypts
before push and decrypts after pull; the server never holds the DEK). It authenticates every request with an
**Authentik access token** (the same account platform accounts SP1 made callosum a client of) and scopes all storage
to the token's `sub`.

> Design: `.claude/docs/specs/2026-06-29-sync-server-design.md`. Security audit:
> `.claude/security-audits/2026-06-29_sync-server.md`.

## What it does

- `GET /sync/records?since=<n>` → the caller's records with server-seq `> n`, plus the caller's current high seq.
- `POST /sync/records` → upsert each record (last-write-wins by version), stamping each stored one the next per-user
  seq; returns the new high seq.
- `GET /health` → liveness (no auth).

Exactly the `pull(since)/push` contract the client engine (`app/backend/sync/engine.py`) already speaks.

## Run it (self-host)

```bash
cd sync_server
python -m venv .venv && . .venv/bin/activate      # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt

# Postgres (prod) + the Authentik audience/issuer for token validation:
export CALLOSUM_SYNC_DB_URL="postgresql+psycopg://user:pass@host:5432/callosum_sync"
export CALLOSUM_SYNC_OIDC_ISSUER="https://auth.example.org/application/o/callosum/"
export CALLOSUM_SYNC_OIDC_AUDIENCE="<the callosum client_id registered in Authentik>"
# optional: CALLOSUM_SYNC_OIDC_JWKS_URL (defaults to <issuer>/jwks/)

uvicorn sync_server.app:app --host 0.0.0.0 --port 8770   # behind TLS in production
```

Tables are created on startup (v1; a general migration TOOL is still a follow-on — see "Not yet" below). A single
targeted, idempotent `ALTER TABLE` also runs on startup to add the backlog-#15 `updated_at` column to an
already-deployed table (see `schema.ensure_updated_at_column`) — this is not that general tool, just a one-time
self-heal for this specific release. Unset OIDC env → the server refuses every request (default-closed). Without
`CALLOSUM_SYNC_DB_URL` it falls back to a local `sqlite:///sync-server.sqlite` (dev only).

**Rate limiting (backlog #15):** per-user (keyed by OIDC `sub`), a sliding window — `429` + `Retry-After` past the
limit. Tune via `CALLOSUM_SYNC_RATE_LIMIT_MAX` (default 60 requests) / `CALLOSUM_SYNC_RATE_LIMIT_WINDOW_SECONDS`
(default 60).

**Retention (backlog #15):** tombstones (deleted-record markers) older than `CALLOSUM_SYNC_RETENTION_DAYS`
(default 90) are eligible for removal via `python -m sync_server.prune_tombstones` — **not** auto-scheduled inside
this process; run it from your own cron/systemd timer. See `OPERATIONS.md` for the trade-off this makes and the
cron entry, and `store.prune_tombstones`'s docstring for the mechanics.

## Authentik setup

Register the callosum client so its **access token** carries an audience this server checks
(`CALLOSUM_SYNC_OIDC_AUDIENCE`), then point clients at this server's URL (callosum: **Settings → Sync**). See
`ops/accounts-authentik-setup.md`.

## Backup & recovery

See `OPERATIONS.md` — a Postgres `pg_dump`/restore runbook, plus what a sync-server backup actually protects (and,
importantly, what it can't: the server never holds a DEK, so a backup here restores *sync state*, not anyone's
plaintext library — the local app's own DB remains each user's actual source of truth).

## Not yet (pre-public hardening)

**Done (backlog #15, this pass):** per-user rate-limiting, tombstone retention, a backup runbook (see above).

**Still open:** a per-user storage **quota** (nothing caps how many live — non-tombstone — records or how much
ciphertext one account can accumulate) and a **real migration tool** (today's schema changes are handled by
`create_all` for new tables plus one-off targeted `ALTER`s like `ensure_updated_at_column` for existing ones — fine
for the maintainer's own self-host, not a general solution). Both deepened before any public multi-tenant deploy.
This slice targets the maintainer's own self-host (a few accounts, a few devices each).
