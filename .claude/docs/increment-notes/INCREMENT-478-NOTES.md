# Increment 478 — Sync SP4d: revoke pending shares + blocked senders (round 3, item #4, stage D of 4 — closes the SP4 arc)

## Implemented

The fourth and final stage of round 3 item #4. SP4a (inc 475) shipped sharing *identity*, SP4b (inc 476) shipped
the *sender* side, and SP4c (inc 477) closed the send→receive loop. SP4d closes the arc with the two
capabilities the original design sketch called "roles": a sender can withdraw a share before it's imported, and
a recipient can locally refuse future shares from a sender — scoped narrower than "roles" once design work found
the shipped one-shot-snapshot share architecture (a share is a single encrypted blob, not a live-updating
grant) had no real target for role-based permissions.

- **`sync_server/schema.py`** — a new nullable `revoked_at` column on the existing `shares` table (NULL = still
  live; set once, never cleared). `ensure_revoked_at_column()` is the same idempotent defensive-ALTER pattern as
  the existing `ensure_updated_at_column()` — safe on both a fresh deploy (created WITH the column via
  `metadata.create_all`) and an already-running one (the ALTER fires once, no-ops after). Called from the
  `lifespan` startup hook alongside its `updated_at` sibling.
- **`sync_server/share_store.py`** — `revoke_share()` (an `UPDATE ... WHERE revoked_at IS NULL`, never a
  `DELETE` — a soft revoke, inspectable at the DB level) and `list_shares_for_sender()` (the sender's own
  sent-list: id/recipient/timestamp/revoked only, deliberately no `imported`/`status` field — the server has no
  way to know whether a recipient has decrypted a share, since that state lives only in the recipient's own
  local `received_shares` table and is never reported back).
- **`sync_server/app.py`** — two new endpoints, both through the existing `_rate_limited` dependency (no new
  limiting logic): `GET /shares/sent` (the sender's own list) and `POST /shares/{id}/revoke` (fetches the row,
  checks `sender_sub == ident.sub` before writing — mirrors the existing recipient-ownership check on
  `GET /shares/{id}` exactly; 403 for a non-sender, 404 for an unknown id).
- **`app/backend/sync/transport.py`** — `HttpSyncTransport.revoke_share()`/`list_sent_shares()`, plus
  `list_shares()`/`get_share()` now also surface the existing `revoked_at` field.
- **`app/backend/api/routers/sync_shares.py`** — `GET /sync/shares/sent`, `POST /sync/shares/{id}/revoke`
  (local-only bookkeeping, no passphrase needed — revoke never touches ciphertext/DEK), and three new
  local-only blocked-senders endpoints (`GET`/`POST /sync/blocked-senders`, `DELETE
  /sync/blocked-senders/{sub}`) that read/write straight to `app_settings` with **no egress gate at all** — a
  pure local preference, working even on a completely unconfigured instance. `list_shares()` now filters out
  any row whose `sender_sub` is blocked (silently absent, not shown-but-marked); `import_share()` gained two new
  fail-closed checks ahead of any decrypt attempt: `revoked_at is not None` → **410**, and `sender_sub in
  blocked` → **403** (defense in depth — the second check still holds even for a share id fetched directly,
  bypassing the filtered list).
- **`app/backend/app_settings.py`** — `stored_blocked_senders()`/`block_sender()`/`unblock_sender()`, written to
  the same plain-JSON local settings file as every other preference (`contact_email`, etc.) — never touching
  `HttpSyncTransport` anywhere in their bodies. **A pre-existing, unrelated 600-line-cap pressure point was
  cleared while landing this**: the module's superuser-ORCID-allowlist block moved verbatim to a new
  `app/backend/superuser.py` leaf module and is re-exported (`from app.backend.superuser import
  is_superuser_orcid, superuser_orcids`) so every existing call site keeps working unchanged — the inc-137/220/
  262/264 leaf-module split pattern, not a new refactor invented for this increment.
- **`app/frontend/js/35c_sync.jsx`** — two new panels under Settings → Sync, both gated on `status.enabled`:
  `SentSharesPanel` (a row per sent share, "to \<sub\>" + date, a **Revoke** button that flips the row to
  "· Withdrawn" in place with no reload) and `BlockedSendersPanel` (a plain sub-paste input + Block button, each
  blocked row with an Unblock action, an explicit "No one is blocked" empty state).
- **`app/frontend/js/28d_shared_with_me.jsx`** — an inline **Block sender** action alongside the existing
  Import/Dismiss on every pending row (immediate, no confirmation dialog — matching Dismiss's own immediacy);
  a revoked share's meta line now reads "· Withdrawn by sender" and hides its Import button (Dismiss and Block
  sender remain available).

## Key technical detail

**No read receipts is a structural fact, not a UI choice.** The temptation with a "sent shares" list is to also
show whether the recipient has acted on it — but the sync-server has no code path that could know this: import
state lives exclusively in the *recipient's own local* `received_shares` table (SP4c) and nothing ever reports
it back. `SentShareOut`/`SentShareListItem` simply have no field for it, so the honest behavior falls out of the
data model rather than needing an explicit rule to enforce. The one place this needed active verification (not
just an absent field) is the specific case of revoking a share *after* the recipient already imported it — that
must change nothing for the recipient, proven by a dedicated test
(`test_revoke_after_import_does_not_undo_the_import`) rather than assumed from the model's shape alone. The
Settings-panel copy states this limit plainly ("Sharing has no read receipts — if they've already imported it,
revoking here won't undo that") rather than implying revoke is a successful "undo."

**Blocking is local-only by construction, not by policy.** `block_sender`/`unblock_sender`/
`stored_blocked_senders` never call `HttpSyncTransport` — there is no code path in their bodies that could reach
the sync server, and the three router functions built on them don't gate on egress-readiness at all (they work
identically on a completely unconfigured instance). This means a blocked sender's `POST /shares` to the server
still nominally succeeds — the ciphertext is stored, just never surfaced to the blocker's `GET /sync/shares`
(filtered) or importable (403'd as defense in depth even via a direct share id). Blocking a sender never becomes
server-side policy; it is exactly a personal, revisable, always-inspectable local filter, matching the project's
minimal-server-trust posture (the server can't read share content; it doesn't need to hold "who blocks whom"
either).

**Soft-revoke over hard-delete.** `revoke_share`'s SQL is an `UPDATE ... WHERE revoked_at IS NULL`, never a
`DELETE` — the row and its ciphertext remain exactly as they were, with only the new column changing. This keeps
a revoked share inspectable/reversible-in-principle at the DB level (an operator could clear the column) rather
than destroying evidence, and it's what makes the WHERE-guarded update idempotent for free (a second revoke call
is a harmless no-op, never re-stamping the timestamp) — no separate "already revoked" branch needed.

## Manual verification script

1. Two real machines/accounts, both with SP4a sharing identities and an SP4b/c share already sent and either
   pending or imported (see `INCREMENT-475/476/477-NOTES.md`'s own manual scripts for those halves).
2. On the sender's device: Settings → Cross-device sync → "Shares I've sent" shows the row. Click **Revoke**
   before the recipient imports it; confirm the row updates in place to "· Withdrawn" with no page reload.
3. On the recipient's device: open "Shared with me…" and confirm the same row now shows "· Withdrawn by sender"
   with no Import button (Dismiss + Block sender remain).
4. On a **separate** share: let the recipient import it successfully first, then revoke from the sender's
   device — confirm the recipient's already-imported paper is untouched (the disclosed limit, proven for real).
5. On the recipient's device, click **Block sender** on a still-pending row from "Shared with me…"; confirm the
   row disappears immediately and Settings → "Blocked senders" now lists that sender's id. Confirm any further
   share from that sender never reappears in "Shared with me" until unblocked.

Not run this increment — flagged as Cliff's own follow-up (needs two real accounts against his live self-hosted
Authentik + `sync_server`), same disclosed limit as SP4a/b/c. The automated substitute (a full two-device round
trip covering sender-only revoke enforcement, revoke-before-import's 410, revoke-after-import's proven no-op,
blocked-sender list filtering + import-time 403 as defense in depth, and blocked-senders CRUD needing no sync
configuration at all) is the primary proof — see `tests/test_sync_endpoints.py` and `tests/test_sync_server.py`
(the specific test names are cited in the security audit's negative-path table,
`.claude/security-audits/2026-08-13_sync-sharing-sp4d.md`). The live Playwright check (isolated scratch
instance) additionally proved the UI wiring — `SentSharesPanel`/`BlockedSendersPanel` render and update in
place, the inline Block-sender action on `SharedWithMeModal`, and the revoked-share display state — with zero
JS exceptions beyond the expected non-2xx fetch log line for the seeded-unreachable-server sub-case.

## Pytest

Full suite: `pytest -n 4 -q` — **2202 passed, 2 skipped in 2078.48s (0:34:38)**, exit code 0, no failures (up
from the pre-SP4d baseline of 2169 passing recorded in CLAUDE.md — the difference reflects the tests added
across all of round 3 item #4's SP4a-d stages, not just this task's own housekeeping pass, which added no new
tests). The run was materially slower than this suite's usual ~10-15 min parallel time because of documented
heavy I/O contention on the machine this session, not a regression. See this task's own report
(`.superpowers/sdd/2026-08-13_sync-sp4d-implementation-plan/task-8-report.md`) for the full raw command output.

- `ruff format .` / `ruff check .` — clean on every file this increment touches.
- `python tools/check_line_budget.py` — clean on every file this increment touches; the repo-wide run reports
  one pre-existing violation, `app/frontend/js/40_app.jsx` (603 lines), which is unrelated Codex "static demo"
  contamination in the shared working tree, not SP4d's own ~6-line addition (the same situation inc 477's own
  notes recorded and resolved via clean git-blob-staging, never by touching the other session's file).
- `python -m tach check` — clean, all modules validated.
- `python tools/qa/build_surface_map.py check` — 0 uncovered API/frontend surfaces (416/416 API, 1730/1730
  frontend) after extending `.claude/qa-routes/route_46_sync.md` with steps 29-33.
