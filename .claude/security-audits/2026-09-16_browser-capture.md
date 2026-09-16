# Security audit — browser capture (issue #61, Phase 1)

**Status: Stage 1 COMPLETE (PASS). Stage 2 — host, installer, extension — pending.** Opened at task start per `CLAUDE.md`'s kickoff rule, filled as
the work proceeds. Stage 2 (connector host, installer registration, extension identity, uninstall
behavior) is appended before this audit is closed.

**Gate triggers:** item 1 (new API endpoints), item 3 (new file-write + file-ingestion path),
item 4 (new authorization logic), item 5 (net-new feature spanning 3+ files / 300+ LOC).

---

## Scope of Stage 1

The bounded `/capture/*` HTTP boundary and its authorization. **No** connector host, **no** installer
registration, **no** browser extension yet — those carry their own threats and are audited in Stage 2.

## Trust model

**What is being protected:** the user's Library. A capture request can create a paper, surface an
existing one, and attach PDF bytes. It cannot read the Library, cannot reach the rest of the API, and
cannot alter Remote Access.

**Adversaries considered:**

| Adversary | Can it obtain capture authority? |
|---|---|
| Ordinary hostile webpage | **No.** Cannot read a local file; cannot reach the native host (not in `allowed_origins`); cannot read the session token. |
| Unapproved / malicious extension | **No.** The native-messaging manifest allowlists extension IDs and cannot contain wildcards (Stage 2). |
| Remote caller over the cloudflared tunnel | **No.** `/capture/*` is not in `_EXEMPT_PATHS`, Host/forwarded-header validation rejects relayed requests, and the capture credential is separate from the Remote Access token. |
| Sibling backend (Word-HTTPS, tunnel-target) | **No.** `/capture/*` refuses unless `reported_instance_role() == "ui"`. Reinforced structurally: `CALLOSUM_APP_DATA_DIR` is set only on the UI child (`backend.rs:211`). |
| Local process running as the user | **Yes — and out of scope.** Such a process can read any local secret store *and* can call the API directly. No local-only mechanism can defend against the user's own privileges. |

**Why not the Remote Access token:** it gates the entire API and is deliberately reachable through the
tunnel. Reusing it would make a capture compromise into a full remote-access compromise. Capture
authority is therefore separate, narrower, and independently revocable.

## Secret storage — and why NOT the OS keychain

The pairing secret lives in an owner-only JSON file beside the settings file
(`capture-pairing.json`), **not** in the OS keychain. This is a deliberate deviation, decided before
implementation:

- The Stage 2 connector host is **Rust**, and the secret is written by **Python**. Python's `keyring`
  on Windows stores through `WinVaultKeyring`, whose target-name scheme carries a `username@service`
  *compound-name fallback* — a library-internal, version-dependent detail. Re-implementing it in Rust
  would be an unstable cross-language contract.
- A plain file is language-neutral and matches an **already-audited precedent**: `access_recovery`
  proves local-machine possession with "a one-time code the server writes to a local file only a local
  user can open", and deliberately places it beside the settings file "so `CALLOSUM_SETTINGS_PATH`
  keeps it hermetic under tests and outside the repo/synced folder in production."
- The threat model is unchanged by the choice: the adversaries that matter (hostile webpage,
  unapproved extension) can read **neither** store, and the adversary that could read the file (a
  local process as the user) could equally read the keychain or bypass both.

The keychain remains correct for secrets only Python reads (Gemini key, Remote Access token). It is
the wrong tool for an inter-process handshake.

## Authorization lifetime vs. replay — stated precisely

These are **two different mechanisms** and the audit does not conflate them:

- The session token is a **bearer token and is intentionally reusable until it expires.** A replayed
  request within its TTL **does** succeed at the transport layer. This audit does not claim replayed
  requests inherently fail closed.
- Duplicate *mutation* is prevented by the **`Idempotency-Key`**, not by the token: a bounded, TTL'd
  key → outcome map returns the original result for a retry after a lost response, instead of
  admitting the paper a second time.
- Expiry is the token's security property. Idempotency is the duplicate-mutation property.

## Controls implemented (Stage 1) — with the test that proves each

Every row is asserted by a named test in `tests/test_capture.py`. **34 passed**, plus **135**
regression tests across health, CORS boundary, access control, admission indexing, persistence core,
registration references, annotations, discovery and DOI add.

| Control | Concrete result | Test |
|---|---|---|
| Role gate: `ui` only | 403 for `word-https` and `tunnel-target` | `test_sibling_backends_refuse_capture` |
| Undeclared role never passes for `ui` | 403 | `test_undeclared_instance_refuses_capture` |
| Session required | 401 without a token | `test_capture_requires_a_session_token` |
| Forged token refused | 401 | `test_capture_rejects_a_wrong_token` |
| Session expiry enforced | 401 past TTL | `test_capture_rejects_an_expired_session` |
| Wrong pairing secret yields nothing | 401 | `test_wrong_pairing_secret_yields_no_session` |
| Rotation revokes live sessions immediately | 401 after rotate | `test_rotating_the_pairing_secret_revokes_live_sessions` |
| Non-safelisted action header required | 403 | `test_capture_requires_the_action_header` |
| Host-header validation (DNS rebinding) | 403 for `evil.example` | `test_capture_rejects_a_foreign_host_header` |
| Relayed/tunnelled request refused | 403 on `x-forwarded-for` | `test_capture_rejects_a_relayed_request` |
| Independent rate limit | 429, with Remote Access OFF | `test_capture_returns_429_when_the_budget_is_exhausted` |
| Body cap enforced by streaming | 413 before parse | `test_oversized_envelope_is_refused_before_parsing` |
| Bounded list cardinality | 422 at 600 creators | `test_envelope_rejects_unbounded_creator_cardinality` |
| Envelope version pinned | 422 for v2 | `test_envelope_version_must_be_pinned` |
| PDF magic | 422 | `test_pdf_upload_rejects_bad_magic` |
| PDF really parses | 422 on malformed | `test_pdf_upload_rejects_a_malformed_pdf` |
| PDF size cap | 413 | `test_pdf_upload_rejects_an_oversized_declared_length` |
| Temp file always cleaned up | no leak on the failure path | `test_pdf_upload_cleans_up_its_temp_file` |
| Trash: no write, no restore, no collision | `in_trash`; `deleted_at` intact; zero live rows | `test_capture_reports_a_trashed_paper_without_writing_or_restoring` |
| No silent first-match on non-unique fields | `unresolved_review_required` | `test_capture_refuses_to_guess_when_identity_rests_on_non_unique_fields` |
| Unresolvable DOI creates nothing | `paper_id is None` | `test_capture_reports_unresolved_for_a_doi_crossref_cannot_resolve` |
| Existing attachment refuses bytes | `attachment_review_required`; still 1 attachment; **no upload slot issued** | `test_existing_paper_with_a_pdf_refuses_capture_bytes` |
| Existing annotation refuses bytes | `attachment_review_required` | `test_existing_paper_with_annotations_refuses_capture_bytes` |
| Failed upload leaves the paper intact | paper alive, zero attachments | `test_failed_pdf_upload_leaves_the_admitted_paper_intact` |
| Retry replays, never double-admits | identical response, one paper row | `test_a_retried_capture_replays_the_original_outcome` |
| Indexing invariant holds for capture | 1 paper embedding; chunk embeddings after attach | `test_capture_admits_a_new_paper_and_indexes_it` |

**No extension-supplied filesystem paths:** the managed filename derives from Callosum's own
`capture_id` (`capture-<id>.pdf`), never from client input. **No backend-fetches-this-URL
instruction:** the envelope carries `pdf_bytes_from_active_tab: bool` and no fetchable attachment URL,
so capture is structurally incapable of becoming an acquisition path.

**Error text:** validation failures report a problem *count* — never Pydantic's messages (which echo
submitted values), never an exception string.

**Attachment refusal is decided before any bytes move:** eligibility is evaluated during
`/capture/item`, and a refused capture is issued **no `capture_id` at all**, so there is no upload slot
to call and nothing is partially mutated to discover the refusal.

## Findings

**F1 — PyMuPDF leaks an OS file handle on Windows when `fitz.open(path)` fails to parse.**
Found by `test_pdf_upload_rejects_a_malformed_pdf`: temp-file cleanup died with
`PermissionError [WinError 32]`, and an explicit `document.close()` did not help because the call
raises before the handle is ever bound. Fixed in capture by validating from **bytes**
(`fitz.open(stream=..., filetype="pdf")`) — which is what `acquisition/fetch.download_oa_pdf` already
does. *Severity: low (temp-file leak; no data exposure).*
**Deliberately not fixed here:** `api/routers/transparency.py`'s registration upload uses the
path-based `with fitz.open(temp_path)` form and is very likely to carry the same latent leak on
Windows. Flagged for the maintainer as a separate small change rather than an unrelated refactor
inside this increment.

**F2 — the viewer's annotation filter is the wrong question for a safety gate.**
`list_annotations_for_paper` filters to native sources plus translated Zotero rows, so an
imported-but-untranslated annotation would have read as "no annotations" and capture would have
attached over a paper that does carry user work. Closed before shipping by adding
`count_all_annotations_for_paper`, which counts every row and documents why it does not reuse the
viewer's rule. *Severity: would have been medium.*

**F3 — Stage 2 will introduce the first registry write in Callosum's history.** Not yet implemented.
Mitigated by `installMode: currentUser` (HKCU only, no elevation). Reversibility will be proven by
extending the existing CI silent-install job to assert key-present → uninstall → key-absent, and that
third-party `NativeMessagingHosts` entries are untouched. *Carried forward.*

## Residual risk accepted for Stage 1

- A **local process running as the user** can read the pairing file and obtain capture authority. Out
  of scope by construction: such a process can equally read the OS keychain and call the API directly.
- A **session token is reusable until it expires** (15 min). Stated plainly rather than papered over;
  duplicate *mutation* is prevented separately, by the idempotency key.
- `/capture/*` is **not reachable by any extension yet** — no host, no installer registration, no
  extension identity exists. Those threats are audited in Stage 2, before anything can call this.

---

**Security Audit (Stage 1): PASS** — no unresolved critical or high findings. F1 is fixed in the new
code and flagged where it remains latent elsewhere; F2 was closed before shipping; F3 is a Stage 2
carry-forward. This audit is re-opened and closed again for Stage 2.
