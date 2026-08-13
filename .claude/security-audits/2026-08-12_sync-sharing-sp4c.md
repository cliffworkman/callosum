# Security audit — Sync SP4c: receive (round 3, item #4, stage C of 4)

**Date:** 2026-08-12
**Status:** COMPLETE.
**Feature:** the recipient side of backlog #15's SP4 sharing — list shares addressed to me
(`sync_server`'s new `GET /shares`), fetch one (`GET /shares/{id}`, 403'd to the addressed recipient only),
decrypt it locally with my own SP4a identity's private key (`unlock_private_key` + `unwrap_content_key` +
`decrypt_payload`, all reused unmodified), and merge it via the already-audited B2 `import_bundle()` (extended
with a backward-compatible `source=` kwarg, default unchanged). A new local table `received_shares` is the
cross-user provenance log. Design: `.claude/backups/plans/2026-08-12_sync-sp4c-receive.md`.
**Audit triggers:** 3 new API endpoints across two services (`GET /shares`, `GET /shares/{id}` on the
sync-server; `GET /sync/shares`, `POST /sync/shares/{id}/dismiss`, `POST /sync/shares/{id}/import` +
its job-status endpoint locally); a new local table + migration; a new background-job import path that
decrypts and merges server-delivered ciphertext for the first time (SP4b only ever sent).

## Threat review

- **A share is never fetchable by a non-recipient — PASS.** The sync-server's `GET /shares/{share_id}` 403s
  unless `row.recipient_sub == ident.sub` (the authenticated caller) — enforced server-side even though a
  share's `wrapped_key`/`ciphertext` are already opaque; this is defense in depth, not reliance on encryption
  alone to gate who can even attempt to fetch a row. The local `POST /sync/shares/{id}/import` endpoint
  propagates a 403 as a distinct, honest signal (`ShareForbiddenError`, a `SyncServerError` subclass — not
  lumped into the generic 502 "unexpected server error" path) and separately re-checks `row["recipient_sub"]`
  against the caller's own `sub` as defense in depth. Tested end-to-end: a third simulated identity ("carol")
  attempting to import a share addressed to "bob" → **403**
  (`test_import_share_addressed_to_someone_else_is_403`), and directly at the server layer
  (`test_get_share_detail_403s_for_a_non_recipient`).
- **Listing needs no passphrase and never decrypts; importing needs one every time — PASS.** `GET /sync/shares`
  is gated on egress-readiness + `has_identity` alone (sender + timestamp only, matching the server's own
  metadata-only list response — no `wrapped_key`/`ciphertext` field). `POST /sync/shares/{id}/import` requires
  the sync passphrase on every call (never remembered) to unlock the DEK, then the identity's private key, then
  fetch/unwrap/decrypt — a wrong passphrase → **422** and reaches the network **not at all** for that call (no
  `get_share`/decrypt happens before the passphrase check). `POST /sync/shares/{id}/dismiss` needs no
  passphrase and never touches ciphertext (a local bookkeeping-only write) — verified the dismissed share's
  row never appears in `papers`/`received_shares.summary_json`.
- **A decrypted, malformed, or foreign payload fails closed before ever reaching `import_bundle` — PASS.** The
  decrypted bundle is re-validated through B2's own `parse_bundle()` (unmodified — version check, `papers` list
  shape check, the same byte-size cap) before any merge logic runs. A `WrappedKey.from_dict`/JSON-decode
  failure on a corrupt `wrapped_key`, an `unwrap_content_key`/`decrypt_payload` `SyncCryptoError` (wrong key,
  tampered ciphertext), and a `parse_bundle` `BundleError` (not a bundle, wrong version, oversized) are each
  caught and surfaced as a clean 502 with a specific detail message — never an unhandled 500, never a partial
  merge.
- **Cross-user provenance is honest, additive, and never overwrites existing provenance — PASS.**
  `import_bundle()` gained one new backward-compatible keyword (`source: str = BUNDLE_SOURCE`), threaded to the
  single `create_paper(...)` call for **newly-created** rows only; a merged (pre-existing) paper's own prior
  `imported_source` is never touched (unchanged behavior, verified by the existing `test_library_bundle.py`
  suite still passing unmodified). SP4c's job passes `source="share-import"`, a value distinct from the
  file-bundle's `"bundle-import"` — confirmed via `test_import_happy_path_decrypts_and_merges`, which asserts
  the newly-merged paper's `imported_source == "share-import"`. `received_shares` records exactly one row per
  share acted on (`status` CHECK-constrained to `'imported'`/`'dismissed'`, unique on `share_id` so a share
  can't be double-logged), with the real `sender_sub` and, for an import, the same summary shape
  `POST /library/bundle/import` already returns.
- **Independent re-verification needed no new code, and none was added — PASS.** `reverify_imported_summary`
  (B2 SP3) operates on any `summaries.imported_json` row regardless of how it arrived (file bundle or live
  share) — SP4c's import writes that column through the exact same `_import_syntheses` path `import_bundle`
  already used unmodified. No share-specific re-verification code exists anywhere; confirmed by inspection, not
  merely by absence of a new file.
- **No new sender-verification mechanism, no allow-list — PASS (by design, confirmed against the plan).** A
  listed share shows the sender's raw `sub` and a link into the existing Settings → Sync fingerprint-lookup
  tool (`SharingIdentityPanel`'s own lookup, unmodified) — live-verified via Playwright that the link switches
  to the Settings workspace correctly. There is no accept/block list gating who can address a share to the
  recipient (SP4d's explicitly-deferred "roles" territory) and no new trust UI was built.
- **Resource caps — PASS.** The server's `GET /shares` list caps at `MAX_SHARES_LISTED = 200` (matching
  `MAX_SHARE_PAPERS`'s own spirit). The share-fetch/decrypt/import path inherits every cap already audited in
  SP4b (`MAX_SHARE_CIPHERTEXT_LEN`, `MAX_WRAPPED_KEY_LEN`, `parse_bundle`'s own `MAX_BUNDLE_BYTES` re-check
  post-decrypt) — no new unbounded input is introduced.
- **The background import job follows the existing Status-popover invariant (#5) — PASS.** `share_import_jobs`
  is a real `JobStore`, registered in `app.py`, with `JOB_NAV_DEFAULTS`/`JOB_COMPUTE_KINDS`/`JOB_LABELS` entries
  mirroring `library_bundle_import_jobs` exactly (`workspace: "library", modal: "shared-with-me"`, labeled
  "Local AI" for the embedding step) — a share import is visible and click-navigable in Status like every other
  tracked job family, not a silent background operation.
- **Server input validation — PASS.** `ShareListItem`/`ShareDetailResponse` Pydantic models bound every field;
  no interpolated SQL (bound-param SQLAlchemy Core throughout `share_store.py`'s new `list_shares_for_recipient`/
  `get_share`). The new `received_shares` table has a `CHECK` constraint on `status` and a `UNIQUE` constraint
  on `share_id`.
- **Supply chain — PASS.** No new third-party dependency — reuses `cryptography` (already present since SP4a/b)
  and stdlib `json`.
- **Migration — PASS.** `0073_received_shares` is a new, additive table (idempotent `if "received_shares" not
  in ... get_table_names()` guard, no down-migration content, matching the established 0070-0072 pattern);
  verified via the full `tests/test_migrations.py` suite (9/9 passing, including the drift-check against the
  live SQLAlchemy metadata) and a direct scratch-DB apply.
- **Module boundary (tach) — PASS.** `python -m tach check` passes with the new `sync_shares.py` router
  cross-importing `sync.py`'s private gate helpers (`_fresh_access_token`/`_require_egress_ready`) and
  `library.py`'s private embedding/job helpers (`_embedding_model`/`_vector_store`/`_progress_out`) — the same
  established sibling-router cross-import pattern `paper_enrich.py` already uses for `papers.py`'s
  `_detail_for`, verified structurally unrestricted by `tach.toml` (neither module pair is tach-fenced against
  the other).

## Negative-path checks (concrete results)

- **Server:** `GET /shares` returns only the caller's own inbox, metadata-only (no `wrapped_key`/`ciphertext`
  field) — **PASS** (`test_list_shares_returns_only_the_caller_own_inbox`). Empty inbox → `[]` — **PASS**.
  Both list and detail endpoints require auth (401 unauthenticated) — **PASS**. `GET /shares/{id}` for the
  correct recipient returns the full row — **PASS**; for a non-recipient → **403** — **PASS**; for an unknown
  id → **404** — **PASS**.
- **Local — list:** refused (409) without a sharing identity — **PASS**.
- **Local — dismiss:** marks `status:"dismissed"` with no passphrase, no papers ever merged — **PASS**; an
  unknown share id → **404** — **PASS**.
- **Local — import happy path:** a real end-to-end decrypt-and-merge proof — alice shares a real paper with
  bob (via alice's own full local `/sync/share` flow, not a bypass), bob (a genuinely separate simulated local
  device — its own settings file, its own local DB) lists it, imports it with his real passphrase, and the
  paper lands in bob's own library with the correct title and `imported_source="share-import"`; a
  `received_shares` row records the real sender — **PASS** (`test_import_happy_path_decrypts_and_merges`).
- **Local — wrong passphrase:** **422**, zero papers merged, zero `received_shares` rows written (no partial
  state) — **PASS** (`test_import_wrong_passphrase_fails_closed`).
- **Local — gating:** refused (409) when sync isn't ready or no identity exists — **PASS**. Unknown share id →
  **404** — **PASS**. A share addressed to someone else → **403** — **PASS** (see the threat-review item
  above).
- **Live UI (Playwright, isolated scratch instance):** the Library "+ Add" menu's "Shared with me…" entry opens
  the modal with the correct disclosure copy; pointed at an unreachable sync-server URL, the list call resolves
  to a clean inline error ("Couldn't check for shares: HTTP 502 on /sync/shares") — **zero JS exceptions**, the
  only console entry being the expected non-2xx fetch log line (the same standing exception every other
  Settings/modal error path in this route already accepts); the "Verify identities in Sync settings →" link
  correctly closes the modal and switches to the Settings workspace, confirmed via a live DOM assertion
  (`Account & sync` heading visible, modal overlay gone).

## Result

**Security Audit: PASS.** A non-recipient can never fetch a share's content (server-enforced + locally
re-checked, distinct honest 403); listing never decrypts and never needs a passphrase, importing always does;
a malformed/foreign decrypted payload fails closed through the existing bundle validator before any merge
logic runs; cross-user provenance is additive and never overwrites a merged paper's own prior provenance;
independent re-verification needed zero new code (the existing B2 SP3 action already covers it); no new
sender-trust mechanism or allow-list was introduced; every new input is bounded; the background import job
follows the existing Status-popover visibility invariant; no new dependency; no migration risk; no tach
violation. **The SP4 sharing arc's sender→receive loop is now complete** — SP4d (revoke/roles, with
revocation's real limits disclosed honestly) is the next and final stage, not covered here.
