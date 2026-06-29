"""The callosum reference sync-server (accounts SP3b) — a self-hostable, multi-tenant store of OPAQUE AES-GCM blobs.

A separate deployable (its own ``requirements.txt``), fenced from ``app/`` — the local callosum app never imports it.
It is an OIDC **resource server**: it validates the Authentik access token on each request and scopes every row to the
token's ``sub``. It stores only ciphertext it cannot read (the client encrypts before push / decrypts after pull) and
never sees the DEK — the end-to-end guarantee. Deploys on Postgres; the dialect-portable SQLAlchemy Core schema also
runs on SQLite for in-process tests. See ``.claude/docs/specs/2026-06-29-sync-server-design.md``.
"""
