# Increment 475 — Sync SP4a: sharing identity (round 3, item #4, stage A of 4)

## Implemented

Round 3's item #4 (memory `callosum-next5-backlog-roadmap-round3`): backlog #15's last genuinely undesigned
sync thread, SP4 sharing ("= B2 collaboration, a live-shared-library layer"). Its origin doc
(`opus4.8_future-tracks_benchmarkrevisions.md`, B2) called it "deferred, not declined... a scope +
architecture-weight question" — the account infrastructure it was waiting on (ORCID sign-in, E2E sync, the
self-hosted `sync_server`) is now live, so this increment is the scoping session that backlog note flagged,
followed by SP4a's own implementation.

Two architecture questions were resolved with Cliff via `AskUserQuestion` before planning: **crypto/identity
model = per-user public-key ACLs** (real keypairs, per-item re-wrapped content keys, fine-grained roles, real
revocation — the bigger build, over a simpler shared-passphrase-vault alternative), and **share unit = an
ad-hoc picked set each time** (not a curated axis or the whole library). Given the size, the work is staged
like the original sync feature itself (SP1→SP3c): **SP4a (this increment) — Identity.** No record is shared in
this stage; it only makes "who is this collaborator, cryptographically" answerable. SP4b (share: wrap a
per-share content key under a looked-up public key), SP4c (receive: a "Shared with me" panel, decrypt-on-fetch,
cross-user provenance), and SP4d (revoke/roles) remain open.

- **`app/backend/sync/identity.py`** (new) — `ShareIdentity` (public key in the clear + the private key sealed
  under the **existing sync DEK**, reusing `crypto.py`'s `encrypt_payload`/`decrypt_payload` unmodified — no new
  KEK, no second passphrase), `create_identity`, `unlock_private_key`, and `fingerprint` (SHA-256 of the raw
  public key, grouped like the recovery code's own format).
- **`app/backend/app_settings.py`** — `set_share_identity`/`stored_share_identity`, mirroring
  `set_sync_keyring`/`stored_sync_keyring` exactly (same `_set_secret` OS-keychain-or-file-fallback path).
- **`sync_server/`** — a new `share_identities` table (`schema.py`); `identity_store.py` (`register_public_key`/
  `lookup_public_key`, pure `Connection`-taking functions mirroring `store.py`'s style — **structurally no
  listing/search function exists**, backlog #15's own divergence fence); two new endpoints in `app.py`
  (`POST /identity/register`, `GET /identity/lookup`) reusing the exact existing `_identity`/`_rate_limited`
  dependency chain — no new auth mechanism.
- **`app/backend/sync/transport.py`** — `HttpSyncTransport.register_identity`/`lookup_identity`, fail-closed
  like `pull`/`push`.
- **`app/backend/api/routers/sync.py`** — three new endpoints: `GET /sync/identity/status`,
  `POST /sync/identity/setup` (gated identically to `/sync/run` — enabled+configured+signed-in+server-URL, plus
  409 on a second call, "no silent re-key"), `GET /sync/identity/lookup` (a thin authenticated proxy; the
  fingerprint is always computed **locally** from the raw key bytes, never trusted as a value the server
  asserts).
- **`app/frontend/js/35c_sync.jsx`** — a new `SharingIdentityPanel`: "Set up your sharing identity" (passphrase
  gate, mirrors the Run flow), then your own sharing ID + fingerprint (copyable), then "Look up a collaborator"
  (paste their id → see their fingerprint) — explicit copy that a lookup alone is never trusted, confirm the
  fingerprint out-of-band first (Signal's "safety number" pattern).
- **`.claude/qa-routes/route_46_sync.md`** — extended with the 3 new local endpoints, new standing assertions
  (identical egress gate, exact-id-only lookup, no endpoint ever returns the private key, locally-computed
  fingerprint), and steps 14-17 (direct-API + a live Playwright pass).

## Key technical detail

**The real architecture decision, and why it's bigger than it looks:** a per-user public-key directory is
structurally a small social/discovery feature (look someone up by an id). The divergence risk — flagged during
planning via the APPROACH-AVOIDANCE gate, before any code — is that it drifts into a general "find other
Callosum users" directory, which nothing in this project's values calls for. The fence is structural, not just
documented: `identity_store.py` has no function that iterates `share_identities` at all, only exact-`user_id`
lookup — there is no code path to enumerate. `test_lookup_never_lists_or_fuzzy_matches` proves near-misses
(case/whitespace/substring) all 404 and that no `/identity`/`/identity/list` endpoint exists.

**A second value-level decision, threaded through the whole design:** registering/looking up identity is real
egress, but it is a *materially different* consent event than syncing to your own second device — sharing your
identity with another human is a bigger trust step than syncing between machines you own. Rather than silently
riding the existing sync-enabled toggle, it requires the identical four preconditions `/sync/run` already
enforces **plus** its own explicit action (a dedicated button + passphrase entry), so enabling sync alone never
implicitly shares anything.

**The fingerprint is always computed client-side**, never trusted as a value the server sends. `sync_identity_lookup`
decodes the server's returned public key and calls `identity_fingerprint` on the raw bytes locally — the server
doesn't even send a fingerprint field. A malformed/wrong-length key from the server fails closed with a clean
502, never a raw 500 or a silently-wrong fingerprint.

## Manual verification script

1. Two real machines/accounts, both with sync configured+enabled and signed in via ORCID.
2. On device A: Settings → Cross-device sync → "Set up your sharing identity" (enter the sync passphrase). Note
   the shown fingerprint and sharing ID.
3. On device B: paste device A's sharing ID into "Look up a collaborator." Confirm the shown fingerprint matches
   what A read aloud/sent through a different channel (email, chat) than the sharing ID itself.
4. Confirm `GET /sync/identity/status` on each device never returns a private key of any kind, and that pasting
   a near-miss id (extra whitespace, wrong case, a truncated id) into the lookup always 404s.

Not run this increment — flagged as Cliff's own follow-up (needs a second real ORCID account against his live
self-hosted Authentik + `sync_server`, per inc 312's own precedent for exactly this kind of two-account proof).
The automated substitute (two fake identities registered against an in-process `sync_server` test app, exact-id
lookup proven for both plus a 404 for a third) is the primary proof and is fully covered by
`tests/test_sync_server.py`.

## Pytest

- `tests/test_sync_identity.py` (new): 8 passed.
- `tests/test_sync_server.py` (+6 identity tests): 23 passed.
- `tests/test_sync_endpoints.py` (+8 identity tests): 22 passed.
- `tests/test_frontend_assembly.py`: 65 passed (unaffected by this increment; a concurrent session's own
  unrelated addition was already present).
- Full suite (`pytest -n 4 -q`): **2128 passed, 2 skipped** in 30m15s. (First attempt hit the documented
  pytest-xdist worker-crash flakiness on this machine at 20% — `node down: Not properly terminated`, a known
  environment issue per prior sessions, not a regression; a retry completed cleanly end to end.)
- `ruff check` / `ruff format --check` / `python tools/check_line_budget.py` / `python -m tach check` — all
  clean on every touched file.
- `python tools/qa/build_surface_map.py check` — 0 uncovered API/frontend surfaces (406/406, 1683/1683 at the
  time of this run — coverage across the whole app, not just this increment's surface).
- Live browser check (Playwright, isolated scratch instance — `CALLOSUM_SETTINGS_PATH` +
  `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`, seeded keyring/oauth-session/enabled-sync state): the
  "Sharing identity" panel renders correctly after "Run sync now," the setup button is correctly disabled with
  an empty passphrase, and a setup attempt against an unreachable server URL fails with a clean inline error and
  zero console exceptions. Caught and fixed a real environment gotcha in the process (not a product bug): the
  seed script and the server process must set `PYTHON_KEYRING_BACKEND` identically, or the seeded keyring
  silently won't unlock (a real OS-keychain-vs-file-fallback mismatch between two separate process
  invocations) — now documented in the QA route's own "Notes for the runner."

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md`: `#15`'s "SP4 sharing [gated, its own design]" line replaced with the
  4-stage breakdown; SP4a closed, SP4b–d still open.
- `.claude/security-audits/2026-08-10_sync-identity-sp4a.md`: PASS.
- Memory `callosum-next5-backlog-roadmap-round3`: item 4 now "SP4a shipped (inc 475), SP4b next" — the whole
  SP4 arc isn't done until SP4d.
