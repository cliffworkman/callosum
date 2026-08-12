# Increment 476 — Sync SP4b: share (round 3, item #4, stage B of 4)

## Implemented

Round 3 item #4's second stage. SP4a (inc 475) shipped sharing *identity* — a per-account X25519 keypair and a
fingerprint-verification flow, but no record could actually be shared. SP4b closes that gap for the **sender
side only**: an ad-hoc picked set of Library papers can now be end-to-end encrypted and sent to one collaborator
resolved via SP4a's existing lookup. There is deliberately no receiving/importing capability yet (SP4c).

**A major reuse discovery narrowed this stage's real scope**: callosum already has a complete, audited,
portable-payload subsystem — the B2 library bundle (`app/backend/metadata/library_bundle.py`, inc 234–236,
audit `2026-07-01_library-bundle.md`). `build_bundle(scope="selection", paper_ids=[...])` already produces
exactly the right content (papers' CSL-JSON + tags + annotations + any fully-contained native synthesis, no
PDFs), and `import_bundle()` already does the additive, non-destructive merge SP4c will eventually need. So
SP4b's genuinely new work is narrow: the crypto envelope + the sync-server transport that gets an encrypted
`build_bundle()` output addressed to a specific looked-up recipient.

- **`app/backend/sync/sharing.py`** (new) — `wrap_content_key`/`unwrap_content_key`: a "sealed" hybrid
  encryption (X25519 ECDH + HKDF-SHA256 + AES-256-GCM — the same construction shape as libsodium's
  `crypto_box_seal` / an HPKE base-mode ciphersuite) that wraps a fresh, one-time 32-byte content key to a
  recipient's long-term public key. The ephemeral public key is bound as AES-GCM associated data, so tampering
  with it invalidates the auth tag rather than silently deriving a wrong shared secret. No sender
  authentication in the envelope itself (matching `crypto_box_seal`'s own posture) — the sync-server's
  `sender_sub` column is authenticated by the bearer token, not the envelope.
- **The actual content** reuses `crypto.py`'s existing `encrypt_payload`/`decrypt_payload` (AES-256-GCM)
  unmodified, keyed by the fresh content key instead of the sync DEK — no new content-crypto code.
- **`sync_server/`** — a new `shares` table (`schema.py`, indexed on `recipient_sub` for SP4c's future "list
  mine" query); `share_store.py::create_share` (mirrors `identity_store.py`'s pure-`Connection`-function
  style — deliberately no `list`/`get` function yet); one new endpoint `POST /shares` in `app.py`, reusing the
  exact existing `_identity`/`_rate_limited` dependency chain.
- **`app/backend/sync/transport.py`** — `HttpSyncTransport.create_share`, fail-closed like `push`/`register_identity`.
- **`app/backend/api/routers/sync.py`** — `POST /sync/share`: body `{recipient_sub, paper_ids, passphrase}`,
  capped at `MAX_SHARE_PAPERS = 200` (an "ad-hoc picked set," not a whole-library handoff). Gated identically to
  `/sync/identity/setup` **plus** requiring a sharing identity already exists. Sequence: validate locally
  (cheap) → unlock the DEK with the passphrase → look up the recipient fresh (never cached) →
  `build_bundle(scope="selection", ...)` → generate a content key → encrypt → wrap → `create_share`. Returns
  `{share_id, recipient_fingerprint}`.
- **`app/frontend/js/28c_share.jsx`** (new) — `ShareModal`: paste a recipient sharing ID → "Look up" (reuses
  SP4a's own `/sync/identity/lookup` endpoint and its exact "confirm this matches what they told you" copy) →
  passphrase + "Share N papers." A new bulk-bar "share…" button (`03_library.jsx`'s `bulkSharePapers`,
  `10_pdf_layer.jsx`'s button) mirrors the existing `bulkMergePapers`/`mergeIds` modal-state pattern exactly;
  mounted in `40_app.jsx` alongside the other bulk-action modals.
- **`.claude/qa-routes/route_46_sync.md`** — extended with `POST /sync/share`, new standing assertions
  (identical+stronger egress gate, fresh recipient re-resolution, resource caps, no-PDF content, single-use
  content keys), and steps 18-22 (direct-API + a live Playwright pass over the Share modal).

## Key technical detail

**The wrap construction is a standard, reviewed shape, not novel cryptography** — X25519 ECDH between a fresh
ephemeral keypair and the recipient's long-term key, HKDF-SHA256 to derive a symmetric key (ECDH output is not
uniformly random and must never be used directly), then AES-256-GCM. This is the same shape as libsodium's
`crypto_box_seal` and an RFC 9180 HPKE base-mode ciphersuite (DHKEM(X25519)+HKDF-SHA256+AES-GCM) — verified
empirically against the actual `cryptography` package APIs (a real ECDH exchange between two independently
generated keypairs produces a symmetric shared secret), not assumed from memory.

**A real design question resolved deliberately, not by default**: should the envelope itself authenticate the
sender? No — `crypto_box_seal` doesn't either, for the same reason: the transport layer (the sync-server's
bearer-token-derived `sender_sub` column) already authenticates who created a share far more robustly than an
envelope-embedded signature could, so duplicating that in the crypto layer would be redundant complexity, not
added security. `test_share_sender_sub_comes_from_token_not_body` proves an attacker-supplied `sender_sub` in
the request body is silently ignored by Pydantic — structurally unspoofable, not just policy.

**Scope discipline, re-confirmed against the originally-approved 4-stage plan**: despite discovering that most
of the "receive" mechanics (import, provenance, even re-verification of a shared synthesis) already exist via
B2's `import_bundle` + the existing "Re-verify against my library" action, SP4b stayed sender-only, matching
Cliff's own approved SP4a→SP4b→SP4c→SP4d split. Tempting as it was to fold SP4c in given how little new code
it would need, expanding scope mid-increment without checking in would violate "minimal diffs, do what was
approved" — SP4c remains its own future increment.

## Manual verification script

1. Two real machines/accounts, both with SP4a sharing identities already set up (see `INCREMENT-475-NOTES.md`'s
   own manual script for that half) and ORCID-signed-in.
2. On device A: select ≥1 paper in the Library, click the bulk-bar's "share…" button. Paste device B's sharing
   ID, confirm the shown fingerprint matches what B read aloud/sent through a different channel, enter the sync
   passphrase, click "Share N papers." Confirm the success message shows B's fingerprint.
3. On device B (once SP4c exists): confirm the share appears and decrypts correctly. Until then, confirm via a
   direct server-side row inspection that the share landed addressed to B with a genuinely encrypted payload.

Not run this increment — flagged as Cliff's own follow-up (needs two real accounts against his live self-hosted
Authentik + `sync_server`), same disclosed limit as SP4a. The automated substitute (a full crypto round trip —
alice shares a real paper with bob, bob's real X25519 private key unwraps the content key and decrypts the
bundle back to the exact original title) is the primary proof and is fully covered by
`tests/test_sync_endpoints.py::test_share_happy_path_creates_a_decryptable_share`.

## Pytest

- `tests/test_sync_sharing.py` (new): 8 passed.
- `tests/test_sync_server.py` (+7 share tests): 37 passed.
- `tests/test_sync_endpoints.py` (+7 share tests): 29 passed.
- Full suite (`pytest -n 4 -q`): green (see `CLAUDE.md`'s counter for the exact total).
- `ruff check` / `ruff format --check` / `python tools/check_line_budget.py` / `python -m tach check` — all
  clean on every touched file (the new `app.backend.api.routers.sync` → `app.backend.metadata.library_bundle`
  import was specifically verified against `tach.toml`'s module boundaries, not assumed).
- `python tools/qa/build_surface_map.py check` — 0 uncovered API/frontend surfaces (407/407, 1702/1702).
- Live browser check (Playwright, isolated scratch instance, same `PYTHON_KEYRING_BACKEND`-matched pattern
  SP4a's own check used): selecting papers and clicking "share…" opens the modal with the correct paper count;
  the recipient lookup reuses SP4a's real endpoint and fails cleanly (502) against an unreachable server URL,
  with the exact inline error copy and zero console exceptions beyond the expected non-2xx fetch log line; the
  passphrase/Share button correctly never renders until a recipient is resolved.

## A real mid-session mistake, caught and fully recovered

While rebuilding `callosum-app.html` for a clean commit, an isolated-worktree build step's final copy-back
step overwrote the **live, hand-authored** `app/frontend/js/40_app.jsx` directly with a clean-HEAD-plus-my-
change version — destroying a concurrent Claude Code session (working on an unrelated static-demo/website
feature, per Cliff's own earlier heads-up) 's real uncommitted source changes in that file (not just a
regenerable build artifact, which is what the equivalent SP4a-stage rebuild had safely touched). Caught
immediately by noticing the file's line count dropped from 597 to 587. Recovered with **zero data loss**: the
full `git diff` against HEAD had been saved to a scratch file *before* the destructive write, and re-applying
that exact diff to a freshly-restored HEAD copy reconstructed the file byte-for-byte identical to its
pre-mistake state (confirmed via a `diff` of the two diffs). The lesson: for any file confirmed to carry
*concurrent hand-authored* changes (not just a generated artifact), always snapshot the exact diff before any
overwrite-based recovery technique, even one that has worked safely before on a different kind of file.

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md`: `#15`'s SP4 breakdown updated — SP4b closed, SP4c/d still open.
- `.claude/security-audits/2026-08-12_sync-sharing-sp4b.md`: PASS.
- Memory `callosum-next5-backlog-roadmap-round3`: item 4 now "SP4b shipped (inc 476), SP4c next."
