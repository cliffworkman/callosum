# Security audit — Sync SP4d: revoke pending shares + blocked senders (round 3, item #4, stage D of 4 — closes the arc)

**Date:** 2026-08-13
**Status:** COMPLETE.
**Feature:** SP4a-c's closing stage — a sender-only `revoked_at` soft-revoke on the existing `shares` table
(`sync_server/`), plus a local-only, client-enforced blocked-senders list (`app_settings.py`) that filters
`GET /sync/shares` and refuses import (403) as defense in depth. Design:
`.claude/backups/plans/2026-08-13_sync-sp4d-revoke-block.md`.
**Audit triggers:** 2 new server endpoints + 1 schema change on `sync_server`; 5 new local endpoints; a new
local-only preference surface (net new LOC ~350 across 6 files).

## Threat review

- **Sender-ownership enforcement on revoke — PASS.** `POST /shares/{share_id}/revoke` fetches the row first
  (`get_share`) and checks `row["sender_sub"] == ident.sub` (the authenticated bearer token's subject, never a
  client-supplied field) before writing `revoked_at` — mirrors the existing recipient-ownership check on
  `GET /shares/{id}` exactly. `test_revoke_by_a_non_sender_is_403` confirms a non-sender's attempt is refused
  AND leaves `revoked_at` unchanged (not a partial/silent effect).
- **Soft-revoke, not data loss — PASS.** `revoke_share`'s SQL is an `UPDATE ... WHERE revoked_at IS NULL`, never
  a `DELETE`. The row (and its ciphertext) remains exactly as before; only the one new column changes. This
  matters because a soft-revoke is inspectable/reversible-in-principle at the DB level, unlike a hard delete.
- **No read-receipt leak — PASS.** `list_shares_for_sender`'s SELECT has no join against any recipient-side
  state (there is none server-side; `received_shares` lives only in the recipient's own local SQLite,
  never synced or reported). Structurally, the sent-list response model (`SentShareListItem`) has no field that
  could carry import status. `test_revoke_after_import_does_not_undo_the_import` proves the disclosed limit
  behaviorally, not just by the model's absence of a field.
- **Blocked-senders data never reaches the sync server — PASS.** `app_settings.block_sender`/`unblock_sender`/
  `stored_blocked_senders` write only to the local settings file (`_write`/`load_settings`, the same plain-JSON
  mechanism as `contact_email`/`openurl_resolver_base`) — no call to `HttpSyncTransport` anywhere in their
  bodies or in the three new `/sync/blocked-senders*` router functions. `test_blocked_senders_needs_no_sync_setup_at_all`
  confirms these endpoints work against a `sync_transport=None` app instance (no egress path even exists to
  accidentally use).
- **Import-time enforcement is defense in depth, not the only gate — PASS.** Blocking is enforced twice: at list
  time (rows filtered out, so the UI never offers them) and again at import time (`row["sender_sub"] in
  blocked` → 403) — `test_import_from_a_blocked_sender_is_403` proves the second gate holds even when a share id
  is used directly, bypassing the list. Mirrors the same two-layer discipline SP4c's own `recipient_sub`
  re-check already established.
- **Import-after-revoke fails closed — PASS.** `row.get("revoked_at") is not None` is checked before any
  decrypt attempt in `import_share`, raising 410 before `unwrap_content_key`/`decrypt_payload` ever run.
  `test_revoke_before_import_then_import_returns_410` confirms nothing is merged and no `received_shares` row is
  written.
- **Rate limiting reuse — PASS.** Both new `sync_server` endpoints (`POST /shares/{id}/revoke`, `GET
  /shares/sent`) run through the existing `_rate_limited` dependency, same as every other share endpoint — no
  new, unreviewed limiting logic.
- **Server input validation — PASS.** `share_id`/`sub` path params are FastAPI-typed (`int`, `str`); the
  `BlockSenderBody.sub` field is capped at 255 chars (matching the `sender_sub`/`recipient_sub` column widths).
  Bound-param SQLAlchemy Core throughout (rule #3) — the new `update(shares).where(...)` call uses column
  comparisons, never string interpolation.
- **No new crypto, no new dependency — PASS.** Confirmed by inspection: `sync/sharing.py`, `sync/identity.py`,
  and `sync/crypto.py` are untouched by this stage. No import of any new package anywhere in the diff.
- **Migration — PASS.** `revoked_at` is added via the same idempotent-ALTER pattern as `updated_at`
  (`ensure_revoked_at_column`, tested for idempotency against a simulated already-deployed table in
  `test_ensure_revoked_at_column_is_idempotent`) — safe on both a fresh `sync_server` deploy (created WITH the
  column via `metadata.create_all`) and an already-running one (the defensive ALTER fires once, no-ops after).

## Negative-path checks (concrete results)

- non-sender attempts revoke → 403, `revoked_at` unchanged — **PASS** (`test_revoke_by_a_non_sender_is_403`).
- revoke an unknown share id → 404 — **PASS** (`test_revoke_unknown_share_404`,
  `tests/test_sync_endpoints.py::test_revoke_unknown_share_404`).
- revoke without a sharing identity set up → 409 — **PASS** (`test_revoke_refused_without_identity`).
- double-revoke → 204/200 both times, not an error, timestamp not re-stamped — **PASS**
  (`test_revoke_is_idempotent`).
- import a revoked share → 410, nothing merged — **PASS** (`test_revoke_before_import_then_import_returns_410`).
- revoke after a successful import → recipient's already-merged paper is untouched — **PASS**
  (`test_revoke_after_import_does_not_undo_the_import`).
- import from a blocked sender (direct id, bypassing the filtered list) → 403, nothing merged — **PASS**
  (`test_import_from_a_blocked_sender_is_403`).
- blocked-senders endpoints require no sync configuration at all → 200 on a bare instance — **PASS**
  (`test_blocked_senders_needs_no_sync_setup_at_all`).
- `sync_server` schema migration is idempotent on an already-deployed table lacking the column — **PASS**
  (`test_ensure_revoked_at_column_is_idempotent`).
- live browser check (isolated scratch instance): Revoke updates the Sent Shares row without a reload; Block
  Sender removes a row from "Shared with me" immediately; zero console exceptions beyond the expected non-2xx
  fetch log line for the seeded-unreachable-server sub-case — confirmed via Playwright, not assumed from a
  static read.

## Result

**Security Audit: PASS.** Revoke is sender-owned, soft, and idempotent; it never leaks read-receipt information
back to a sender because no such data path exists server-side. Blocking is structurally local-only — no code
path sends it to `sync_server`, verified both by inspection and by a test asserting the endpoints work with no
transport configured at all. This closes the SP4 sharing arc (identity → share → receive → revoke/block);
no further audit-triggering slice is planned under backlog #15's SP4.
