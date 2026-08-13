<!-- qa-coverage
api: /sync/status, /sync/setup, /sync/settings, /sync/run, /sync/conflicts, /sync/conflicts/{conflict_id}/resolve, /sync/identity/status, /sync/identity/setup, /sync/identity/lookup, /sync/share, /sync/shares, /sync/shares/{share_id}/dismiss, /sync/shares/{share_id}/import, /sync/shares/{share_id}/import/{job_id}, /sync/shares/sent, /sync/shares/{share_id}/revoke, /sync/blocked-senders, /sync/blocked-senders/{sub}
fe: 35c_sync.jsx, 28c_share.jsx, 28d_shared_with_me.jsx
-->

# ROUTE 46 - Opt-in E2E sync (accounts SP3b) + the Settings → Sync UI + conflict review (SP3c) + sharing identity (SP4a) + share (SP4b) + receive (SP4c) + revoke/block (SP4d)

**Tier:** 1 local-stateful
**Goal:** Exhaust the opt-in `/sync/*` surface (set up a vault, toggle on, status, run, list/resolve conflicts,
set up/look up a sharing identity, share a selection, receive a share) and its safety boundaries WITHOUT a live
sync-server or Authentik. The live deploy + live-token round-trip is the maintainer's MANUAL check (see the
design spec). Steps 1-8 are direct-API (no UI); **steps 9-13 exercise the Settings → Sync UI** (`35c_sync.jsx`,
inc 311) — browser-verified with Playwright (setup, the one-time recovery-code reveal, the sequential enable
gate, run + its error paths, and the conflict-review panel). **Steps 14-17 (SP4a, inc "sync-identity-sp4a")
cover the sharing-identity surface** — direct-API (setup/status/lookup, gating, no-private-key-exposure) plus a
Playwright pass over the "Sharing identity" subsection, browser-verified against an isolated scratch instance.
**Steps 18-22 (SP4b, inc "sync-sharing-sp4b") cover the sender-only share surface** — direct-API
(`POST /sync/share`'s gating, resource caps, and unknown-recipient handling) plus a Playwright pass over the
new `28c_share.jsx` `ShareModal` (opened from the Library bulk-bar's "share…" action). **Steps 23-28 (SP4c, inc
"sync-sharing-sp4c") cover the recipient side** — list/dismiss/import gating, the 403 cross-recipient defense-
in-depth check, a full decrypt-and-import round trip, and a Playwright pass over the new `28d_shared_with_me.jsx`
`SharedWithMeModal` (opened from the Library "+ Add" menu's "Shared with me…" entry). **Steps 29-33 (SP4d, inc
"sync-sharing-sp4d") cover revoke + blocked senders** — direct-API (sender-only revoke, import-after-revoke's 410,
blocked-sender list filtering and import refusal, blocked-senders CRUD) plus a Playwright pass over the new
`SentSharesPanel`/`BlockedSendersPanel` (Settings → Sync) and the inline "Block sender" action in
`SharedWithMeModal`.

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
- **SP4a — sharing identity rides the same egress gate as a sync run.** `POST /sync/identity/setup` and
  `GET /sync/identity/lookup` both refuse (**409**) unless sync is enabled AND configured AND signed-in AND a
  server URL is set — identical preconditions to `/sync/run`. A wrong passphrase on setup → **422** (not 401,
  same reasoning as `/sync/run`'s own wrong-passphrase handling) and registers nothing server-side (no egress on
  a failed unlock). Setup on an already-set-up instance → **409** (no silent re-key, mirroring `/sync/setup`).
  Any of these gates missing or bypassed is **Critical**.
- **No endpoint ever returns the private key.** `GET /sync/identity/status` and the `POST /sync/identity/setup`
  response body both carry only `{fingerprint, own_sub}` (plus `has_identity` on status) — never a raw or wrapped
  private key, never the raw public key bytes. A private key (wrapped or not) appearing in any response is
  **Critical**.
- **Lookup is exact-id only.** `GET /sync/identity/lookup?sub=<id>` matches only an exact registered id — a
  near-miss (case/whitespace/substring) or an unregistered id → **404**, never a partial/fuzzy match and never a
  list of other registered ids. There is no listing/search endpoint on the local surface or the sync-server
  (`sync_server`'s own `/identity/*` — covered by `tests/test_sync_server.py`, outside this route's surface map,
  same convention as `/sync/records`). A listing/search capability appearing anywhere is **Critical** (backlog
  #15's own divergence fence — see `.claude/APPROACH-AVOIDANCE.md`).
- **The fingerprint is computed locally, never trusted as a value the server asserts.** `sync_identity_lookup`
  decodes the server's returned public key and computes the fingerprint client-side (`identity_fingerprint`) —
  it never forwards a server-supplied fingerprint value (the server doesn't send one). A malformed/wrong-length
  public key from the server → a clean **502**, never a raw 500.
- **SP4b — share rides the same egress gate, PLUS requires a sharing identity already exists.** `POST
  /sync/share` refuses (**409**) unless sync is enabled+configured+signed-in+server-URL'd **and** the caller has
  already run `/sync/identity/setup` — an unset-up sender can never create a share. A wrong passphrase → **422**
  and creates **no** share row anywhere (no egress on a failed local unlock — same discipline as `/sync/run`
  and `/sync/identity/setup`). Any of these gates missing or bypassed is **Critical**.
- **The recipient is always resolved fresh, never a stale/cached lookup.** `/sync/share` calls
  `/sync/identity/lookup` itself server-side on every share — an unregistered `recipient_sub` → **404**, never
  a share silently created addressed to nobody. A share created for an unresolved recipient is **Critical**.
- **Resource caps.** `paper_ids` is bounded to 1–200 (empty or >200 → **422**, mirroring the existing library-
  bundle "select at least one paper" behavior); a selection that resolves to zero actual shareable papers
  (e.g. all ids nonexistent/trashed) → **422**, never a share of an empty bundle. The server's own `ciphertext`/
  `wrapped_key` caps (`sync_server/app.py`) are covered by `tests/test_sync_server.py`, outside this route's
  surface map, same convention as every other server-side body cap.
- **No PDFs; the same portable, no-PDF payload the audited library bundle already uses.** A share's content is
  `build_bundle(scope="selection", ...)` unmodified — metadata + tags + annotations only. A PDF byte or an
  `attachment` file path appearing in a share's plaintext bundle is **Critical**.
- **The content key is single-use and never reused across shares.** Each `/sync/share` call generates a fresh
  random content key and a fresh ephemeral wrap — verified at the crypto-unit level
  (`tests/test_sync_sharing.py`); this route's own steps confirm the *endpoint* wiring (a second share to the
  same recipient succeeds independently, never erroring as a duplicate/replay).
- **SP4c — listing needs no passphrase; importing does.** `GET /sync/shares` (sender + timestamp only, no
  content) is gated on egress-readiness + `has_identity` alone — no passphrase, no decrypt. Decrypting a
  specific share (`POST /sync/shares/{id}/import`) is gated identically to `/sync/share` PLUS requires the
  passphrase every time (never remembered). A wrong passphrase → **422** and merges **nothing** into the
  library and writes **no** `received_shares` row (no partial state). Any of these gates missing or bypassed is
  **Critical**.
- **A share is never fetchable by a non-recipient, even though its content is already ciphertext.** The
  sync-server 403s `GET /shares/{id}` for anyone but the addressed `recipient_sub`; the local endpoint
  propagates this as a clean **403**, distinct from the generic 502 "sync server error" path, and separately
  re-checks `recipient_sub` against the caller's own `sub` as defense in depth. A share importable by (or even
  distinguishably-erroring-differently-for) a non-recipient is **Critical**.
- **Dismiss never touches ciphertext or asks for a passphrase.** `POST /sync/shares/{id}/dismiss` is local-only
  bookkeeping — a share dismissed without ever being decrypted must show **zero** new rows in the local
  `papers`/`received_shares.summary_json` state beyond the one `received_shares` row recording the dismissal.
  A dismiss that triggers any egress beyond the one list-lookup it needs, or that decrypts anything, is
  **Critical**.
- **Cross-user provenance is honest and separate from ordinary bundle-import provenance.** A paper newly
  created via a share import carries `imported_source="share-import"` — never silently reusing the file-bundle's
  `"bundle-import"` value, and never overwriting an existing (merged) paper's own prior provenance. The
  `received_shares` log records exactly one row per share acted on (`imported` or `dismissed`, never both) with
  the real sender `sub` and, for an import, the same summary shape `POST /library/bundle/import` already
  returns. A share import that can't be traced back to its sender afterward is **High**.
- **Independent re-verification needs no new code and none is added.** A relayed synthesis that arrives via a
  share lands with `summaries.imported_json` set exactly like a file-bundle import does — the existing
  "Re-verify against my library" action (B2 SP3, `reverify_imported_summary`) already works on it unmodified. A
  share-specific re-verification code path appearing anywhere is a **Medium** finding (unnecessary duplication,
  not a security issue) — the reuse is the point.
- **No new sender-*verification* mechanism** (SP4a's fingerprint dance + lookup tool remains the only identity
  proof) — but **SP4d adds a local-only block list**, not a server-side allow-list. Blocking is enforced
  entirely client-side: a blocked sender's shares are silently omitted from `GET /sync/shares` and refused
  (403) at import, but their `POST /shares` to the sync-server still nominally succeeds (harmless stored
  ciphertext the blocker will simply never see) — blocking never becomes server-side policy. Blocked-senders
  data appearing in any request to the sync-server is **Critical**.
- **Revoke is soft and sender-only.** `POST /sync/shares/{id}/revoke` stamps `revoked_at` (never deletes the
  row); it succeeds only for the original sender (**403** otherwise, **404** for an unknown id), and is
  idempotent (revoking twice is not an error). A revoked share fails closed at import (**410**, distinct from
  the generic 502/404 paths). A non-sender able to revoke, or a revoke that hard-deletes evidence, is
  **Critical**.
- **No read receipts.** `GET /sync/shares/sent` never reports whether a recipient has imported a share — there
  is structurally no field for it (the server has no way to know). Revoking an already-imported share must not
  change anything for the recipient (proven by `test_revoke_after_import_does_not_undo_the_import`) — the UI
  copy must disclose this limit plainly, not imply a successful "undo." Any new mechanism that reports import
  status back to a sender is a **Medium** finding (an unrequested new signal, not itself a vulnerability, but a
  deliberate scope/values decision this route should catch if it silently appears).

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
14. **Identity status defaults to none.** On a clean instance, `GET /sync/identity/status` →
    `{has_identity:false, fingerprint:null, own_sub:null}`.
15. **Identity setup gating + fail-closed (direct-API, needs an injected `sync_transport` bound to an in-process
    fake sync-server — see `tests/test_sync_endpoints.py::test_identity_setup_happy_path_registers_and_returns_fingerprint`
    for the exact harness shape).** `POST /sync/identity/setup` before sync is ready → **409**. Once
    ready (setup + signed-in + server URL + enabled): a **wrong** passphrase → **422**, and the fake server's own
    `/identity/lookup` confirms **nothing** was registered (no egress on a failed unlock). The **correct**
    passphrase → **200** `{fingerprint, own_sub}` only (assert no other keys, no private key of any kind);
    `GET /sync/identity/status` now reports `has_identity:true` with the **same** fingerprint; the fake server's
    `/identity/lookup` for that `sub` now returns a real public key. A second setup call → **409**.
16. **Lookup proxy.** Against an identity registered directly on the fake server for a second id, `GET
    /sync/identity/lookup?sub=<that id>` → **200** with `{public_key, display_name, fingerprint}`, the fingerprint
    computed from the raw key (not asserted by the server). An unknown `sub` → **404**. Before sync is ready →
    **409**.
17. **Sharing identity UI (`35c_sync.jsx`'s `SharingIdentityPanel`) — Playwright-driven against an isolated
    scratch instance** (`CALLOSUM_SETTINGS_PATH` + `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`, a
    seeded keyring/oauth-session/enabled-sync state — see the note below): with sync enabled, "Sharing identity"
    appears right after "Run sync now" with a passphrase field and a **disabled** "Set up your sharing identity"
    button until a passphrase is entered. Submitting against a server URL with no real listener behind it shows a
    clean inline error (`settings-note-err`, "Couldn't set up your sharing identity: sync server error: …") —
    **no console error beyond the expected non-2xx fetch log line, no crash.** "Look up a collaborator" stays
    **hidden** until `has_identity` is true (confirmed: it does not appear after a failed setup attempt).
18. **Share gating (direct-API, an injected `sync_transport` bound to an in-process fake sync-server).**
    `POST /sync/share` before sync is ready → **409**; sync ready but no sharing identity set up yet → **409**.
    Once both are true: a **wrong** passphrase → **422**, and the fake server's own store shows **zero** rows
    (no egress). An unregistered `recipient_sub` → **404**.
19. **Share happy path + real decrypt proof.** With a real X25519 identity registered for a second id directly
    on the fake server, `POST /sync/share {recipient_sub, paper_ids:[<a real paper>], passphrase}` → **200**
    `{share_id, recipient_fingerprint}`. Reading the row back from the fake server directly: `recipient_sub`
    matches, `sender_sub` matches the caller — never swapped. Unwrapping `wrapped_key` with the **real**
    recipient private key (not the sender's) recovers a usable content key that decrypts `ciphertext` back to
    the exact `build_bundle` payload (paper title round-trips byte-for-byte).
20. **Resource caps.** `paper_ids: []` → **422**; 201 ids → **422** (`MAX_SHARE_PAPERS = 200`); `paper_ids`
    pointing only at nonexistent/trashed papers → **422** ("none of the selected papers could be shared") —
    never a share of an empty bundle.
21. **Share UI (`28c_share.jsx`'s `ShareModal`) — Playwright-driven against an isolated scratch instance,
    same seeding pattern as step 17 plus ≥1 real paper in the library.** Selecting papers in the Library and
    clicking the bulk-bar's "share…" button opens the modal showing "Share N papers." Pasting a recipient id
    and clicking "Look up" reuses the SAME `/sync/identity/lookup` endpoint step 16 already covers — a found
    identity shows its fingerprint with the SAME "confirm this matches" copy as `SharingIdentityPanel`'s own
    lookup (not a duplicated/divergent wording); an unknown id shows a clean inline error. Only once a recipient
    is resolved does the passphrase field + "Share N papers" button appear.
22. **Share UI error path + console.** Submitting against a server URL with no real listener shows a clean
    inline error ("Couldn't share: …"), no crash, no console error beyond the expected non-2xx fetch log line
    (the same standing exception every other Settings/modal error path in this route already accepts).
23. **List gating + shape (direct-API, two simulated devices sharing one in-process fake sync-server — see
    `tests/test_sync_endpoints.py::_alice_shares_with_bob` for the exact two-device harness: a second
    `CALLOSUM_SETTINGS_PATH` + a second local DB simulate "bob's" own device within one test process).**
    `GET /sync/shares` before sync is ready → **409**; sync ready but no sharing identity → **409**. Once both
    are true and alice has shared a real paper with bob: bob's `GET /sync/shares` → one row,
    `sender_sub:"alice"`, `status:null` (pending) — no `wrapped_key`/`ciphertext` in the list body.
24. **Dismiss.** `POST /sync/shares/{id}/dismiss` with **no** passphrase in the body → **200**
    `{dismissed:true}`; the same share now lists with `status:"dismissed"`; bob's `papers` table is still empty
    (nothing was ever decrypted). `POST /sync/shares/999999/dismiss` (unknown id) → **404**.
25. **Import happy path + real decrypt proof.** `POST /sync/shares/{id}/import {passphrase}` → **202**
    `{job_id, status:"pending"}`; `GET /sync/shares/{id}/import/{job_id}` → `status:"done"`,
    `summary.papers_created:1`. Reading bob's own local `papers` table directly: the new row's title matches
    exactly what alice shared, and `imported_source == "share-import"` (not `"bundle-import"`). Reading bob's
    local `received_shares` table: one row, `share_id` matches, `sender_sub:"alice"`, `status:"imported"`. The
    same share now lists (`GET /sync/shares`) with `status:"imported"`.
26. **Wrong passphrase fails closed.** `POST /sync/shares/{id}/import {passphrase:"WRONG"}` → **422**; bob's
    `papers` table is still empty; bob's `received_shares` table has no row for this share.
27. **Gating + the 403 cross-recipient check.** `POST /sync/shares/{id}/import` before sync is ready → **409**;
    sync ready but no identity → **409**; an unknown share id → **404**. A third simulated device ("carol," her
    own settings + DB, her own registered identity) attempting to import a share addressed to bob →
    **403** — confirms the defense-in-depth check holds even against a guessed/enumerated share id she has no
    legitimate way to have learned (her own list never shows it).
28. **"Shared with me" UI (`28d_shared_with_me.jsx`'s `SharedWithMeModal`) — Playwright-driven against an
    isolated scratch instance, same seeding pattern as steps 17/21 plus a share seeded server-side addressed to
    the scratch instance's own identity.** The Library "+ Add" menu's "Shared with me…" entry opens the modal
    listing the seeded share (sender id + received date, no passphrase prompt yet). Clicking **Import** reveals
    a passphrase field scoped to that row only (the rest of the list stays interactive); submitting shows the
    same summary line shape `BundleImportModal` already uses. Clicking **Dismiss** on a different (or the same,
    in a separate seeded scratch instance) pending row removes it from the actionable list immediately, with
    **no** passphrase prompt at any point. The "Verify identities in Sync settings →" link switches to the
    Settings workspace (closing the modal) — confirm it does **not** silently no-op. Zero console errors beyond
    the expected non-2xx fetch log line for the error-path sub-case below.
    - **Error path:** submitting Import against a server URL with no real listener shows a clean inline error
      ("Couldn't import: …"), no crash.
29. **Sent-list + revoke gating (direct-API, the two-device harness from steps 23-28).** `GET /sync/shares/sent`
    before sync is ready → **409**; sync ready but no identity → **409**. Once alice has shared a paper with
    bob, her own `GET /sync/shares/sent` shows one row (`recipient_sub:"bob"`, `revoked:false`) — no
    `wrapped_key`/`ciphertext` in the body. `POST /sync/shares/{id}/revoke` before sync is ready → **409**; an
    unknown id → **404**; a third device (carol) attempting to revoke a share she didn't send → **403**
    (confirms sender-only enforcement, not just recipient-only like the existing 403 check).
30. **Revoke → import fails closed; revoke after import changes nothing.** Alice revokes her own pending share
    (`POST /sync/shares/{id}/revoke` → **200** `{revoked:true}`); bob's `GET /sync/shares` now shows
    `revoked:true` for that row; bob's `POST /sync/shares/{id}/import` → **410**, nothing merged. On a
    **separate** fresh share: bob imports successfully first, *then* alice revokes — confirm bob's already-
    imported paper is untouched (the disclosed limit, proven for real, not just in copy).
31. **Blocked-senders CRUD + enforcement (direct-API).** `GET/POST/DELETE /sync/blocked-senders` work on a
    completely unconfigured instance (no sync setup at all) — confirms this is a pure local preference, not
    gated by egress-readiness. After bob blocks alice's sub, alice's pending share disappears from bob's `GET
    /sync/shares` entirely (not shown-but-marked — actually absent from the response body); a direct `POST
    /sync/shares/{id}/import` against that share_id still **403**s even though the row no longer appears in the
    list (defense in depth against a stale UI). Unblocking restores visibility on the next `GET /sync/shares`.
32. **Sent Shares + Blocked Senders UI (`35c_sync.jsx`) — Playwright-driven against an isolated scratch
    instance, same seeding pattern as steps 17/21.** With sync enabled, "Shares I've sent" and "Blocked senders"
    both appear below "Sharing identity." A seeded sent share shows "to \<sub\>" + date; clicking **Revoke**
    updates the row to show "· Withdrawn" and removes the Revoke button, with no page reload. Blocked Senders
    shows an empty state ("No one is blocked") plus a paste-a-sub-to-block input; adding one shows it in the
    list with an Unblock action; unblocking removes it. Zero console errors beyond the expected non-2xx fetch
    log line for any seeded-unreachable-server sub-case.
33. **Inline "Block sender" on `28d_shared_with_me.jsx` — Playwright-driven, same scratch instance plus a share
    seeded server-side.** A pending row shows Import/Dismiss/**Block sender**. Clicking **Block sender** removes
    the row immediately (no confirmation dialog, matching Dismiss's own immediacy) and — confirmed via a
    follow-up `GET /sync/blocked-senders` direct-API call in the same check — the sender's id is now present in
    the blocked list. A **revoked** seeded share (server-side `revoked_at` set directly before the page loads)
    shows "· Withdrawn by sender" in its meta line and has **no** Import button, only Dismiss + Block sender.

## Notes for the runner

The reference sync-server lives in `sync_server/` (a separate deployable, outside the app surface map — like the
adapters). Its endpoints (`/sync/records`, `/health`, `/identity/register`, `/identity/lookup`, `/shares`,
`/shares/{id}`) are covered by `tests/test_sync_server.py`, not this route.

Step 21's scratch instance additionally needs a real paper in the library (create one via a direct
`create_paper` call, or import a fixture PDF) — the Share modal's "Share N papers" flow needs at least one
real, non-trashed `paper_ids` entry for `build_bundle` to produce a non-empty bundle.

Steps 23-27 need a genuine **second local device** simulated within the check, not just a second identity —
`app_settings` reads `CALLOSUM_SETTINGS_PATH` fresh on every call (no caching), so re-pointing it to a second
temp path mid-run (with its own local DB) is enough to give "bob" his own independent keyring/identity/
oauth-session state, exactly the trick `tests/test_sync_endpoints.py::_alice_shares_with_bob` already uses —
reuse that helper's shape rather than re-deriving it. Step 28's scratch instance needs a share seeded
server-side (register a real X25519 identity for the scratch instance's own `sub` directly against the fake
server, matching step 17/19's own real-identity seeding, then have a second simulated sender share a real
paper to it) so the modal has something pending to show.

Seeding a conflict for step 12 without two real devices: insert a row directly —
`insert(schema.sync_conflicts).values(collection="papers", record_id="<any string>", losing_version=1,
losing_payload={"title": "...", ...}, resolved=0)` against the scratch instance's DB. `current` reads back `None`
for a `record_id` with no real `sync_identity` mapping — confirm the diff table still renders cleanly (every field
shows "—" on the Current side) instead of erroring.

Seeding an isolated scratch instance for step 17 without a live sync-server or Authentik: seed
`app_settings.set_sync_keyring(...)` (from `create_keyring`), `set_oauth_session({"access_token": "fake",
"sub": "<id>", "display_name": "<name>"})`, and `set_sync_settings(enabled=True, server_url="https://…")`
directly (Python, same process env as the server) before starting uvicorn — matching the isolation this route's
steps 9-13 already use. **`PYTHON_KEYRING_BACKEND` must be set identically for both the seeding process and the
server process**, or the seeded keyring silently won't unlock (a real OS-keychain-vs-file-fallback mismatch
between two separate process invocations — caught live while writing this step, not assumed).

Steps 30-31's "revoke after import" and "blocked-sender import refusal" sub-cases both need the same two-device
harness steps 23-28 already establish (`tests/test_sync_endpoints.py::_alice_shares_with_bob`) — no new harness
shape, just new assertions layered onto it.
