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

Tables are created on startup (v1; a migration is a follow-on). Unset OIDC env → the server refuses every request
(default-closed). Without `CALLOSUM_SYNC_DB_URL` it falls back to a local `sqlite:///sync-server.sqlite` (dev only).

## Authentik setup

Register the callosum client so its **access token** carries an audience this server checks
(`CALLOSUM_SYNC_OIDC_AUDIENCE`), then point clients at this server's URL (callosum: **Settings → Sync**). See
`ops/accounts-authentik-setup.md`.

## Not yet (pre-public hardening)

Per-user rate-limiting, blob retention/quota, a backup runbook, and a real migration tool — deepened before any
public multi-tenant deploy. This slice targets the maintainer's own self-host (a few accounts, a few devices each).
