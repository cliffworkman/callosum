<!-- qa-coverage
api: /sync/status, /sync/setup, /sync/settings, /sync/run
fe:
-->

# ROUTE 46 - Opt-in E2E sync (accounts SP3b)

**Tier:** 1 local-stateful
**Goal:** Exhaust the opt-in `/sync/*` surface (set up a vault, toggle on, status, run) and its safety boundaries
WITHOUT a live sync-server or Authentik. The live deploy + live-token round-trip is the maintainer's MANUAL check
(see the design spec); this route verifies everything around the consent gate. There is **no frontend yet** (the
Settings → Sync UI + conflict-review screen is SP3c) — this route is API-only.

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
- **Run is fully gated.** `POST /sync/run` → **409** when off / not-set-up / not-signed-in / no-server-URL; **401**
  on a wrong passphrase; and a wrong passphrase must cause **no egress** (nothing reaches the server). A run that
  proceeds while any precondition is unmet is **Critical**.
- **The recovery code is shown ONCE.** `POST /sync/setup` returns `recovery_code` exactly once; it must **never**
  appear in `GET /sync/status` (or any later response). A recovery code re-exposed by status is **High**.
- **No silent re-key.** A second `POST /sync/setup` on an already-configured instance → **409** (re-keying would
  orphan existing encrypted data).
- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High (n/a until SP3c adds UI).
- **Signal not verdict / coordinate honesty.** Unchanged here (no claims/coordinates on this surface).

## Steps (direct-API; no UI yet)

1. `GET /sync/status` on the clean instance → assert the default-OFF shape above.
2. `POST /sync/setup {passphrase:"correct horse battery"}` → 200 + a non-empty `recovery_code`; re-GET `/sync/status`
   → `configured:true`, and the body has **no** `recovery_code`. A second `/sync/setup` → **409**.
3. `POST /sync/setup {passphrase:""}` (fresh instance) → **422** (blank passphrase rejected).
4. `PUT /sync/settings {enabled:true, server_url:"https://s"}` while not-signed-in → **422**; with no server URL →
   **422**. (Sign-in + a configured keyring are required to flip it on.)
5. `POST /sync/run {passphrase:"x"}` while disabled → **409**. (The full happy-path run needs a sync-server +
   sign-in — exercised by `tests/test_sync_endpoints.py` against an in-process server; not Playwright-drivable.)

## Notes for the runner

The reference sync-server lives in `sync_server/` (a separate deployable, outside the app surface map — like the
adapters). Its endpoints (`/sync/records`, `/health`) are covered by `tests/test_sync_server.py`, not this route.
