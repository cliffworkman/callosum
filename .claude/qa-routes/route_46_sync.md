<!-- qa-coverage
api: /sync/status, /sync/setup, /sync/settings, /sync/run, /sync/conflicts, /sync/conflicts/{conflict_id}/resolve
fe: 35c_sync.jsx
-->

# ROUTE 46 - Opt-in E2E sync (accounts SP3b) + the Settings → Sync UI + conflict review (SP3c)

**Tier:** 1 local-stateful
**Goal:** Exhaust the opt-in `/sync/*` surface (set up a vault, toggle on, status, run, list/resolve conflicts) and
its safety boundaries WITHOUT a live sync-server or Authentik. The live deploy + live-token round-trip is the
maintainer's MANUAL check (see the design spec). Steps 1-8 are direct-API (no UI); **steps 9-13 exercise the
Settings → Sync UI** (`35c_sync.jsx`, inc 311) — browser-verified with Playwright this increment (setup, the
one-time recovery-code reveal, the sequential enable gate, run + its error paths, and the conflict-review panel).

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** The instance is **not signed in** (no OIDC
session) and sync is **unconfigured** by default. Register console/pageerror/request listeners if any page is opened.

## Standing assertions

- **Default-OFF egress (the core SP3 promise).** On a clean instance `GET /sync/status` →
  `{enabled:false, configured:false, signed_in:false, server_url:null, last_cursor:0}`. Sync must **never** run
  unless explicitly enabled. Any record leaving the machine without the user enabling sync is **Critical**.
- **End-to-end encryption — opaque blobs only.** Anything the client sends to a sync-server is AES-GCM ciphertext;
  the server never receives plaintext library text or the DEK. (The Gemini library-text egress gate, #3, is a
  *separate* channel and is untouched — with egress unset, any request to a `generativelanguage`/genai host on a
  sync action is **Critical**.)
- **Lockout-safe enable.** `PUT /sync/settings {enabled:true}` is refused (**422**) unless sync is *configured*
  (a keyring exists) AND *signed in* AND a *server URL* is given. Enabling a half-configured sync is **High**.
- **Run is fully gated.** `POST /sync/run` → **409** when off / not-set-up / not-signed-in / no-server-URL; **422**
  on a wrong passphrase (deliberately not 401 — the frontend's `api*` fetch helpers treat *any* 401 as the
  unrelated remote-access lockout, inc 254, and would fire the wrong recovery overlay); and a wrong passphrase must
  cause **no egress** (nothing reaches the server). A run that proceeds while any precondition is unmet is
  **Critical**; a wrong passphrase that returns 401 (and so trips the lockout overlay) is **High**.
- **A local SQLite write-lock collision (e.g. a concurrent watched-folder rescan) surfaces as a clean 503**, not a
  raw 500/traceback — deliberately not auto-retried (retrying a mixed local+egress run risks a duplicate push);
  the response tells the user to run sync again. An unhandled 500 here is **Medium**.
- **The recovery code is shown ONCE.** `POST /sync/setup` returns `recovery_code` exactly once; it must **never**
  appear in `GET /sync/status` (or any later response). A recovery code re-exposed by status is **High**.
- **No silent re-key.** A second `POST /sync/setup` on an already-configured instance → **409** (re-keying would
  orphan existing encrypted data).
- **Conflicts are surfaced, never silently resolved (value A4).** `GET /sync/conflicts` lists only *unresolved*
  rows; nothing auto-picks a side. `POST /sync/conflicts/{conflict_id}/resolve` requires an explicit `side` ("mine" or
  "theirs") — there is no default. Resolving `"theirs"` never touches the domain row (the remote value already
  won on apply); resolving `"mine"` restores the kept losing payload through the same collection-dispatch apply
  path a remote winner takes (`engine.apply_conflict_resolution`) — never a raw/arbitrary write. Resolving an
  unknown or already-resolved conflict id → **409** (fails closed, doesn't silently no-op as success). A resolve
  endpoint that writes without an explicit side, or that lets a request body inject fields beyond what
  `losing_payload` already held, is **Critical**.
- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **Signal not verdict / coordinate honesty.** Unchanged here (no claims/coordinates on this surface).
- **The passphrase is never redisplayed** (setup and run both use a plain, write-only password input that clears
  on success) and **the recovery code is a distinct, explicit one-time reveal** with "no server-side reset" copy —
  the `RemoteAccessSettings` token-reveal pattern, not a bespoke one. A passphrase echoed back anywhere is
  **Critical**.
- **Enable reads as a sequential checklist** (choose a passphrase → sign in → set a server URL → enable), matching
  the backend's own gate order — never a bare toggle that just shows a 422 after the fact. The enable switch is
  disabled until a server URL is present.

## Steps

Steps 1-8 are direct-API (no UI). Steps 9-13 exercise the Settings → Sync UI (`35c_sync.jsx`) — Playwright-driven
this increment (against an isolated `CALLOSUM_SETTINGS_PATH` + `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`
scratch instance, so the check never touches a real stored keyring/passphrase).

1. `GET /sync/status` on the clean instance → assert the default-OFF shape above.
2. `POST /sync/setup {passphrase:"correct horse battery"}` → 200 + a non-empty `recovery_code`; re-GET `/sync/status`
   → `configured:true`, and the body has **no** `recovery_code`. A second `/sync/setup` → **409**.
3. `POST /sync/setup {passphrase:""}` (fresh instance) → **422** (blank passphrase rejected).
4. `PUT /sync/settings {enabled:true, server_url:"https://s"}` while not-signed-in → **422**; with no server URL →
   **422**. (Sign-in + a configured keyring are required to flip it on.)
5. `POST /sync/run {passphrase:"x"}` while disabled → **409**. (The full happy-path run needs a sync-server +
   sign-in — exercised by `tests/test_sync_endpoints.py` against an in-process server; not Playwright-drivable.)
6. `GET /sync/conflicts` on a clean instance with no conflicts → `[]`. (Producing a real conflict needs two
   simulated devices sharing a fake transport — not something a single running instance can do; exercised by
   `tests/test_sync_endpoints.py::test_list_conflicts_shows_mine_and_current` et al. A pre-seeded scratch instance
   with one manufactured `sync_conflicts` row can be used to drive steps 7-8 manually if a live check is wanted.)
7. Against a seeded conflict: `GET /sync/conflicts` → one row with `losing_payload` (mine) and `current` (theirs,
   the live domain value) both present and *different* — confirm the response never contains a `resolved` field
   implying it might list resolved rows (it doesn't; only unresolved rows are ever returned).
8. `POST /sync/conflicts/{conflict_id}/resolve {side:"theirs"}` → 200 `{resolved:true}`; the row drops out of the next
   `GET /sync/conflicts`; the domain value is unchanged. On a **fresh** seeded conflict, `POST
   /sync/conflicts/{conflict_id}/resolve {side:"mine"}` → 200; the domain value now reads back as the *losing* payload.
   `POST /sync/conflicts/999999/resolve {side:"theirs"}` (unknown id) → **409**; resolving the same id twice →
   **409** the second time.
9. **Setup (`35c_sync.jsx`, unconfigured instance):** Settings → Cross-device sync shows "1. Choose a passphrase"
   with a plain + a confirm password field, submit disabled until they match. Submitting shows the one-time
   recovery-code reveal (a read-only, select-on-focus input, "no server-side reset" copy); dismissing it removes
   the passphrase fields (now configured) and, if not yet signed in, shows "2. Sign in (see Account, below)."
10. **Enable (signed in):** "2. Sync server URL" + "3. Enable sync" appear; the enable switch is disabled until a
    URL is saved. Saving the URL, then enabling, flips the switch and reveals "Run sync now."
11. **Run — the honest error paths (no live sync-server needed to check these):** an unreachable/misconfigured
    server URL gives a clean **502** ("sync server error: …"), never a raw 500. A **wrong passphrase** gives a
    clean **422** ("wrong passphrase") shown inline in the Sync section — confirm this does **NOT** trigger the
    app-wide `AccessLockOverlay` lockout-recovery overlay (the historical risk this route's 401→422 change guards
    against). A concurrent local write-lock collision (rare; e.g. a watched-folder rescan mid-run) gives a clean
    **503**, never a raw 500/traceback.
12. **Conflict review:** with ≥1 unresolved conflict (seed one directly into `sync_conflicts` for a scratch
    instance — see the note below), the "N conflict(s) to review →" link appears near the top of the section
    regardless of whether sync is currently enabled. Opening it lists a collapsible card per conflict (collection
    + timestamp); expanding one shows a generic field-by-field table ("Mine" vs "Current (theirs)") — reuses the
    `cr-matrix` bordered-table recipe (08y_critical_set.jsx), not a bespoke style. **Keep theirs** leaves the
    domain value unchanged and removes the card; **Keep mine** restores the local value. Either action refreshes
    the standing "N conflicts" count/link.
13. **Responsive/console:** confirm zero console errors across steps 9-12 (the browser's own "non-2xx fetch" log
    line for step 11's expected error responses is the one standing exception, per the same convention every
    other Settings section's error handling already accepts — not a JS exception).

## Notes for the runner

The reference sync-server lives in `sync_server/` (a separate deployable, outside the app surface map — like the
adapters). Its endpoints (`/sync/records`, `/health`) are covered by `tests/test_sync_server.py`, not this route.

Seeding a conflict for step 12 without two real devices: insert a row directly —
`insert(schema.sync_conflicts).values(collection="papers", record_id="<any string>", losing_version=1,
losing_payload={"title": "...", ...}, resolved=0)` against the scratch instance's DB. `current` reads back `None`
for a `record_id` with no real `sync_identity` mapping — confirm the diff table still renders cleanly (every field
shows "—" on the Current side) instead of erroring.
