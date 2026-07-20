# Increment 311 — Sync UI (SP3c), Increment B: the Settings → Sync UI + conflict review (frontend)

## Context
Increment A (inc 310) closed the backend gap (list/resolve conflicts). This increment builds the actual UI the
maintainer asked for: a Settings section to set up, enable, run, and review conflicts for the opt-in E2E sync arc
(incs 194–202). Per the approved plan, this is the first real frontend caller of `/sync/run` — and building it
surfaced two genuine, previously-invisible backend bugs (below), fixed in the same increment rather than filed,
since they directly affect whether the UI just built actually works correctly.

## Implemented

**New `app/frontend/js/35c_sync.jsx`** (`35_settings.jsx` was already at 552/600 — no room for a full section;
split from the start, the inc-256 `35b_providers.jsx` precedent). `<SyncSettings />` added to `SettingsView`'s
render list, right after `<AccountSettings />` (sync depends on being signed in).

- **`SyncSettings`**: reads `GET /sync/status` + `GET /sync/conflicts` (for a standing conflict count) on mount.
  Renders the flow as a **sequential checklist**, matching the backend's own gate order exactly — nothing is a
  bare toggle that just shows an error after the fact:
  1. **Setup** (shown only while `!configured`): a passphrase + confirm field (BYOK-style `type="password"`,
     write-only, cleared on submit) → `POST /sync/setup` → the recovery code, shown exactly once in a read-only,
     select-on-focus input (the `RemoteAccessSettings` access-token reveal pattern) with explicit "no server-side
     reset — save this now" copy.
  2. **Sign in** (shown while `configured && !signed_in`): points at the existing Account section rather than
     duplicating a sign-in control.
  3. **Server URL + Enable** (shown once signed in): a URL field + Save, and the enable switch — disabled until a
     URL is present, `PUT /sync/settings`.
  4. **Run sync now** (shown once enabled): a passphrase field re-entered on every run (no session-remember — the
     design spec flags that as a possible future add, explicitly not this slice) → `POST /sync/run` → a transient
     `{pushed, applied}` note, with a "N new conflicts →" link when `conflicts > 0`.
  A standing "N conflicts to review →" link appears near the top of the section whenever any are outstanding,
  independent of the run flow or whether sync is currently enabled (mirrors the backend's own un-gated design).
- **`ConflictReviewPanel` + `ConflictCard`**: modeled on `35b_providers.jsx`'s `AiSettings`/`ProviderRow` —
  a list-owner fetching `GET /sync/conflicts`, each conflict a collapsible card (collection + timestamp). Expanding
  shows a **generic field-by-field diff** (the union of keys across `losing_payload`/`current`) using the
  `cr-matrix` bordered-table recipe from `08y_critical_set.jsx` (reused, not reinvented) — deliberately no
  per-collection-bespoke rendering for this first cut. **Keep mine** / **Keep theirs** call
  `POST /sync/conflicts/{id}/resolve`; success removes the card and refreshes the standing count.
- **CSS: zero new classes.** Every control reuses an existing token/recipe (`.settings-*`, `.provider-*`,
  `.cr-matrix*`) — DESIGN.md rule #3 ("reuse a recipe") fully satisfied.

**Two backend bugs found and fixed while browser-testing the UI (`app/backend/api/routers/sync.py`):**

1. **`/sync/run`'s wrong-passphrase case used 401 → fires the wrong app-wide overlay.** Every `api*` fetch helper
   in `00_lib.jsx` treats **any** 401, from **any** endpoint, as "the remote-access bearer token is invalid" and
   calls `_notifyAuthRequired()`, which the app renders as a full-screen `AccessLockOverlay` (inc 254's lockout
   recovery). A user who mistypes their **local sync passphrase** would have been shown that unrelated, alarming
   "you're locked out" screen instead of a simple inline message. Reproduced live (typed a wrong passphrase against
   a real running instance, watched the overlay almost fire) before fixing. Changed to **422**, matching
   `sync_setup`'s own `SyncCryptoError` handling for the equivalent failure at setup time — the two endpoints were
   inconsistent with each other before this fix. Updated `test_run_refused_when_off_or_wrong_passphrase` +
   `test_run_with_wrong_passphrase_does_not_egress` (422, not 401) and the audit addendum below.
2. **An unhandled SQLite write-lock collision surfaced as a raw 500.** Reproduced by accident: running a real sync
   against an unreachable test server collided with the app's own background watched-folder rescan (a per-item,
   but still momentarily lock-holding, job) mid-write inside `ensure_identities`/`bind_identity`, raising
   `sqlalchemy.exc.OperationalError: database is locked`, uncaught, surfacing as a raw 500 with no useful message.
   `sync.py`'s `/sync/run` is deliberately exempt from the inc-281 `run_write` short-write retry sweep (retrying a
   mixed local+egress operation risks re-pushing already-pushed records to the remote server) — so the fix is
   **not** a retry, just an honest response: catch `OperationalError`, check `sqlite_retry.is_sqlite_locked`, and
   return a clean **503** ("couldn't get a write lock — try again in a moment") instead of a crash trace. The
   user's own retry (a fresh `/sync/run`) remains the safe recovery path.

## Key technical detail
Testing the "not yet configured" step required a genuinely clean `sync_configured()` state — but `sync_keyring`
is stored via the OS keychain first (`_get_secret`, service name `"callosum"`, fixed regardless of
`CALLOSUM_SETTINGS_PATH`), so an isolated settings-file scratch instance still read the **real** stored keyring
from a past session and reported `configured: true`. Rather than touch that real secret, used `keyring`'s own
`PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring` env var for the scratch instance only — this makes
`_keyring()` fall through to the (empty, isolated) settings file, with **zero risk to the real stored secret**.
This is the same effective isolation `tests/conftest.py`'s autouse fixture achieves via `monkeypatch` for pytest;
there's no equivalent for a live manual/Playwright check, so this is the reusable recipe for next time.

## Manual verification (Playwright, this session, against the isolated scratch instance above)
1. Fresh/unconfigured: Settings → Cross-device sync shows "1. Choose a passphrase"; mismatched confirm keeps
   submit disabled; submitting shows the recovery code once (a real generated code, e.g.
   `XSFKS-LFXIL-EA5XS-EYL2V-3BUO`), zero console errors.
2. Dismissing the recovery-code reveal → step 1 gone (now configured); "2. Sign in" shown (faked via a direct
   `app_settings.set_oauth_session` write to the scratch settings file only).
3. Reload → server URL field appears (step 2) → Save → "3. Enable sync" switch enables → toggling on reveals
   "Run sync now."
4. Run against an unreachable test URL (`https://sync.example.test`) → clean 502 ("sync server error: … getaddrinfo
   failed"), shown inline, zero uncaught JS errors (the console DOES log the non-2xx fetch itself, per the same
   convention every other Settings error path already accepts).
5. Run with a **wrong passphrase** → clean 422 ("wrong passphrase") shown inline — confirmed **no**
   `AccessLockOverlay` fired (this was the actual bug-catch moment).
6. Seeded a fake `sync_conflicts` row directly (no real second device needed) → "1 conflict to review →" appeared
   near the top of the section; opened the panel, expanded the card, saw a clean Field/Mine/Current(theirs) table
   (with "—" for the unresolvable current value, rendering gracefully); clicked **Keep theirs** → 200, card
   removed, count returned to 0, zero console errors throughout.

## Pytest
`tests/test_sync_endpoints.py` **12 passed** (2 status-code assertions updated for the 401→422 fix).
`tests/test_frontend_assembly.py` **36 passed** (+1 new, `test_sync_settings_ui_wired_and_honest`).
`ruff check .` + `ruff format --check .` clean; `python tools/check_line_budget.py` clean (347 files).
`python tools/qa/build_surface_map.py check` → **250/250 API, 1188/1188 FE, 0 uncovered**
(`.claude/qa-routes/route_46_sync.md` extended with FE steps 9–13).

## Gates
- **Security:** addendum to `.claude/security-audits/2026-06-29_sync-server.md` (the 401→422 change — no
  security-relevant behavior changed, only the HTTP status/frontend-integration). No new audit needed for the
  UI itself (no new endpoint; the 503 fix is a pure error-handling improvement, not a new write path).
- **QA (#10):** route_46 extended; FE surface map 0 uncovered.
- **DESIGN.md (#8):** zero new CSS classes — every control reuses an existing recipe.
- **Principles (#9):** conflicts remain surfaced, never auto-picked (A4); the passphrase is never transmitted
  anywhere but the two local `/sync/*` endpoints, never logged, never redisplayed; the recovery code is shown
  exactly once; PDFs never sync (stated plainly in both the UI copy and the help corpus).
- **Help docs:** new "Cross-device sync" section; corrected the stale "sync doesn't exist yet" note under Account.

## Next
Backlog #15's remaining pieces are all yours: the maintainer's live `sync_server/` deploy (Postgres + Authentik
audience), pre-public server hardening (rate-limiting, retention, backup runbook, a migration tool), and SP4
sharing (a live shared library) — see `INCREMENT-BACKLOG.md` §3.
