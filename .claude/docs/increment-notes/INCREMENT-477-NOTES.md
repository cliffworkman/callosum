# Increment 477 — Sync SP4c: receive (round 3, item #4, stage C of 4)

## Implemented

Round 3 item #4's third stage. SP4a (inc 475) shipped sharing *identity*; SP4b (inc 476) shipped the *sender*
side — an ad-hoc picked set of papers could be encrypted and addressed to a fingerprint-confirmed recipient,
but no one could receive anything. SP4c closes the loop: list shares addressed to me, decrypt one with my own
identity's private key, and merge it into my library.

**A second large reuse discovery, same shape as SP4b's**: once a share is decrypted, its plaintext is *exactly*
a B2 library bundle dict (SP4b built it with `build_bundle()`) — so importing it is `import_bundle()`, almost
completely unmodified, running through the near-identical background-job + per-paper-embedding pattern
`POST /library/bundle/import` already uses. "Independent re-verification on import" needed **zero new code** —
`reverify_imported_summary` (B2 SP3) already re-verifies *any* synthesis with `summaries.imported_json` set,
regardless of whether it arrived via a bundle file or a live share, since both write that column the same way.

- **`sync_server/`** — `share_store.py` gained `list_shares_for_recipient`/`get_share` (the two reads SP4b's own
  docstring had explicitly deferred to "when SP4c actually needs them"); `app.py` gained `GET /shares`
  (metadata-only inbox listing, capped at `MAX_SHARES_LISTED = 200`) and `GET /shares/{share_id}` (the full
  row, **403'd to the addressed recipient only** — defense in depth even though the content is already
  ciphertext).
- **`app/backend/sync/transport.py`** — `list_shares()`/`get_share()`, the latter raising a new
  `ShareForbiddenError` (a `SyncServerError` subclass) on a 403 so the local router can surface a clean, honest
  403 rather than lumping an *expected* outcome (the recipient check) into the generic "unexpected server
  error" 502 path.
- **`app/backend/metadata/library_bundle.py`** — `import_bundle()` gained one backward-compatible keyword,
  `source: str = BUNDLE_SOURCE`, threaded to the single `create_paper(...)` call for newly-created rows only (a
  merged/pre-existing paper's own prior provenance is never touched). SP4c passes `source="share-import"` — a
  distinct value from the file-bundle's `"bundle-import"`, so a paper's provenance honestly records *how* it
  arrived. `library.py`'s own call site is unaffected (uses the unchanged default).
- **`app/backend/persistence/schema_sync.py`** — a new `received_shares` table (migration `0073_received_shares`):
  the cross-user provenance log, one row per share the local user has acted on (`status` CHECK-constrained to
  `imported`/`dismissed`, unique on `share_id`, `summary_json` mirroring `BundleImportSummary`'s own shape).
  New `persistence/received_shares_repo.py` (mirrors `sync_conflicts_repo.py`'s small pure-function style).
- **`app/backend/api/routers/sync_shares.py`** (new sibling router, mirroring the `paper_enrich.py`/
  `methods_retraction.py` precedent rather than growing `sync.py` in place):
  - `GET /sync/shares` — list-only, gated on egress-readiness + `has_identity` alone, **no passphrase** (sender +
    timestamp only, cross-referenced against the local `received_shares` log so already-handled shares don't
    keep nagging).
  - `POST /sync/shares/{id}/dismiss` — local-only bookkeeping, no passphrase, never touches ciphertext.
  - `POST /sync/shares/{id}/import` — the passphrase-gated action: unlock DEK → unlock my own identity's
    private key (SP4a's `unlock_private_key`) → fetch the share (403/404 handled cleanly) → re-check
    `recipient_sub` locally as defense in depth → `unwrap_content_key` → `decrypt_payload` → re-validate
    through `parse_bundle` (a malformed/foreign decrypted payload fails closed *before* any merge logic runs)
    → hand off to a new `share_import_jobs` background job (a near-verbatim copy of `library.py`'s
    `_run_bundle_import_job`) that runs `import_bundle(..., source="share-import")`, embeds new papers, and
    logs one `received_shares` row on success.
  - `GET /sync/shares/{id}/import/{job_id}` — the poll endpoint.
  - Registered `share_import_jobs` in `app.py`; extended `status.py`'s `JOB_NAV_DEFAULTS`/`JOB_COMPUTE_KINDS`/
    `JOB_LABELS` (`workspace: "library", modal: "shared-with-me"`, "Local AI") so a share import is visible and
    click-navigable in the Status popover like every other tracked job family (invariant #5).
- **`app/frontend/js/28d_shared_with_me.jsx`** (new) — `SharedWithMeModal`, modeled directly on
  `28b_bundle.jsx`'s `BundleImportModal`: on open, lists pending/handled shares (no passphrase); per-row
  **Import** (reveals a row-scoped passphrase field, polls the job, shows the same summary shape
  `BundleImportModal` already uses) / **Dismiss** (immediate, no passphrase). An inline "Verify identities in
  Sync settings →" link switches to the Settings workspace (closing the modal) rather than inventing a new
  verification UI — reuses SP4a's own `SharingIdentityPanel` lookup entirely. Reuses the existing `.gap-row`/
  `.gap-row-info`/`.gap-row-actions` CSS recipe (from `36c_beyond_library_saved.jsx`'s precedent) — **no new
  CSS** needed. Wired into the Library "+ Add" menu (`10b_libmenus.jsx`) right after "Import bundle…", mirroring
  `bundleImportOpen`'s exact state/prop/modal-mount shape in `40_app.jsx`.

## Key technical detail

**Recipient-side trust, named explicitly rather than left implicit.** SP4a's fingerprint dance protects the
*sender* — confirming the public key they're addressing a share to really belongs to the person they think.
It does **not** by itself tell the *recipient* who `sender_sub` really is; that's just the OIDC subject the
token holder authenticated as. The design's answer is deliberately minimal: show the sender's raw `sub`
plainly on every listed share, and link straight to the **existing** fingerprint-lookup tool rather than
building a second verification mechanism. No allow-list/block-list exists — SP4d's explicitly-deferred "roles"
territory.

**A 403 is not a 404, and it is not a 502.** The sync-server's `GET /shares/{id}` 403s a non-recipient (an
*expected*, meaningful outcome — the whole point of the defense-in-depth check) rather than 404ing (which
would conflate "doesn't exist" with "isn't yours" — a minor information-shape choice, but the honest one) or
letting it fall into the generic "unexpected server error" 502 path every other transport failure uses. This
needed one small addition mid-implementation: a dedicated `ShareForbiddenError(SyncServerError)` subclass in
`transport.py`, caught distinctly in the router — caught and fixed while writing the 403 test, not assumed
correct from the design doc alone.

**Cross-user provenance without a second write pass.** The first implementation draft used a
decrypt-then-import-then-UPDATE dance to retag newly-created papers with `share-import` provenance. Threading
a backward-compatible `source=` keyword through `import_bundle()` itself instead avoids the second write pass
entirely and is more obviously correct (no "is this row still `bundle-import`" filter to reason about) — caught
and simplified during implementation, before any test was written against the clunkier version.

## Manual verification script

1. Two real machines/accounts, both with SP4a sharing identities already set up and an SP4b share already sent
   between them (see `INCREMENT-475/476-NOTES.md`'s own manual scripts for those halves).
2. On the receiving device: open the Library "+ Add" menu → "Shared with me…". Confirm the pending share shows
   the sender's id and received date. Click "Verify identities in Sync settings →" and confirm the sender's
   fingerprint (read aloud or sent a different way) before proceeding.
3. Back in "Shared with me…", click **Import**, enter the sync passphrase, confirm the summary line shows the
   expected paper/tag/annotation counts and the paper appears in the Library with the correct metadata.
4. Confirm Settings → Your usage / Status popover shows the import as a completed "Local AI" job (Status
   invariant #5).

Not run this increment — flagged as Cliff's own follow-up (needs two real accounts against his live self-hosted
Authentik + `sync_server`), same disclosed limit as SP4a/b. The automated substitute (a full crypto+merge round
trip — alice shares a real paper with bob via alice's own full local flow, bob's own separate local device
lists, wrong-passphrase-fails-closed, then successfully decrypts and merges it, with the paper landing in bob's
own library carrying the correct provenance) is the primary proof:
`tests/test_sync_endpoints.py::test_import_happy_path_decrypts_and_merges` and its sibling gating/403/wrong-
passphrase tests. The live Playwright check (isolated scratch instance) additionally proved the UI wiring —
Add-menu entry, modal open, clean error-path rendering against an unreachable sync-server URL, and the
Settings-navigation link — with zero JS exceptions.

## Pytest

- `tests/test_sync_server.py` (+7 SP4c tests): 44 passed.
- `tests/test_sync_endpoints.py` (+12 SP4c tests): 51 passed.
- `tests/test_sync_sharing.py` / `tests/test_library_bundle.py` (unaffected by the new `source=` kwarg, default
  unchanged): both green.
- `tests/test_migrations.py` (the new `0073_received_shares` migration, including the drift-check against the
  live SQLAlchemy metadata): 9/9 passed.
- `ruff format` / `ruff check` / `python tools/check_line_budget.py` / `python -m tach check` — all clean on
  every touched file. (`app/frontend/js/40_app.jsx` showed a transient 600+-line count during development —
  confirmed via diff inspection to be entirely a concurrent, uncommitted, unrelated Codex session's "demo mode"
  work mixed into the shared live working tree, not this increment's own ~6-line addition; handled at commit
  time via the same clean git-blob-staging technique established in inc 476, never by touching that other
  session's code.)
- `python tools/qa/build_surface_map.py check` — 0 uncovered API/frontend surfaces (411/411, 1720/1720).
- Live browser check (Playwright, isolated scratch instance) — see Manual verification script above.
