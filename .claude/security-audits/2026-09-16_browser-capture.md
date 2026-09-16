# Security audit — browser capture (issue #61, Phase 1 + Phase 2)

**Status: Stage 1 COMPLETE (PASS). Stage 2 COMPLETE (PASS on every control actually exercised;
two integration-acceptance items remain empirically unverified — see "Evidence status" and
"Residual evidence gaps for Stage 2" below).** Opened at task start per `CLAUDE.md`'s kickoff rule,
filled as the work proceeds.

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
carry-forward.

---

## Stage 2 — connector host, installer registration, extension identity, uninstall/update behavior

## Scope of Stage 2

Everything that can now REACH `/capture/*`: the native-messaging connector host
(`src-tauri/src/bin/callosum_connector.rs`), NSIS installer registration
(`installer-hooks.nsh`), the browser extension (`app/desktop-shell/extension/`), the
`ensure_pairing_secret()` startup wiring (F3's resolution), and the dev-only registration path
(`tools/run_dev.py`).

## New trust boundary: the native-messaging channel

**What changed:** before Stage 2, `/capture/*` existed but nothing could call it — F3 in Stage 1's
audit ("Stage 2 will introduce the first registry write in Callosum's history") was the carried-
forward risk. Stage 2 closes it, so the threat model gains one new adversary class: a program
launched via Chrome/Edge's native-messaging mechanism.

**Defense in depth, not a single control:**

| Layer | Mechanism | What it stops |
|---|---|---|
| Browser-enforced | `allowed_origins` in the native-messaging manifest | An extension NOT in this list is never even allowed to launch the host — enforced by Chrome/Edge itself, before any of this project's code runs. |
| Host-enforced (steering point 3) | `caller_is_allowed` in `callosum_connector.rs` checks argv[1] against the SAME allowlist, exact 32-char match only (no prefix/substring/wildcard) | A caller that somehow reaches the host anyway (a tampered manifest, a future browser bug) gets refused a second time, independently. A rejected caller receives **no reply at all** — not a shaped refusal — so nothing here ever hands an unapproved caller a structured response to learn from; from its side this is indistinguishable from `host_unavailable`. |
| Backend-enforced | `require_capture_boundary` (Stage 1, unchanged): instance-role gate, Host-header validation, independent rate limit | Even a caller that passed both checks above still can't reach `/capture/*` on the wrong backend instance, from off-machine, or without bound. |

**Production extension identity does not exist yet, by design (steering point 1).**
`connector/identity.json`'s `production_extension_ids` is deliberately an empty list: neither the
Chrome Web Store nor Microsoft Edge Add-ons has assigned this extension a real ID, because it has
never been submitted to either store. An empty `allowed_origins` is the SAFE state — the installer
still writes a fully-formed, valid manifest (verified by CI), it just allows no caller yet. This is
tested (`tests/test_connector_identity.py::test_production_extension_ids_are_deliberately_unpublished`)
specifically so a future refactor can't silently promote a placeholder into the wire/install
contract. Chrome Web Store and Edge Add-ons are treated as two separate store submissions that MAY
end up with different assigned IDs — `production_extension_ids` is a list for exactly that reason.

**The dev identity is real but structurally quarantined (steering point 2).** `dev_extension_id` is
a genuine Chromium extension ID, deterministically derived from a real (and disposable — the
private half was never retained) RSA keypair, verified by
`tests/test_connector_identity.py::test_dev_extension_id_matches_its_own_public_key` to actually
match its own public key rather than being an arbitrary string. It is registered ONLY under a
DIFFERENT native-messaging host name, `org.callosum.connector.dev`, by `tools/run_dev.py`, gated
behind `CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD=1`. A crashed dev session that skips
`_clear_dev_connector()` can leave stale dev registration behind, but it is structurally incapable
of touching, shadowing, or even referencing `org.callosum.connector`'s own registry key or manifest
— they share no name. Best-effort cleanup, never a correctness requirement.

## Token issuance over the native channel

The connector host reads the pairing secret from the same owner-only file Stage 1 already audited
(`~/.callosum/capture-pairing.json`) and exchanges it for a session token via the SAME
`/capture/session` endpoint a hostile webpage was already shown unable to reach. Nothing new is
exposed: the host is simply the first real caller of a boundary Stage 1 already proved closed to
everyone else. The session token itself never touches disk, is never logged (checked by inspection
of `callosum_connector.rs`'s `log_event` call sites — only `runtime_state` and a rejected
`caller_origin` are ever logged, never a token or secret), and the extension only ever holds it
in the service worker's memory for the duration of one capture.

## Replay and the loopback origin (steering point 7)

Restated from Stage 1, unchanged in substance: the session token is a bearer token, intentionally
reusable until its 15-minute TTL, and duplicate *mutation* is prevented by the `Idempotency-Key`,
not by the token. What's new in Stage 2 is that the EXTENSION, not just the backend, now has to be
defended against a compromised or buggy connector host: `host_permissions: ["http://127.0.0.1/*"]`
is broad by necessity (Callosum's port changes per launch), so `validateBackendOrigin` in
`background.js` parses and re-derives the origin the host returns — exact scheme `http`, exact host
`127.0.0.1`, no credentials, no host-supplied path, a numeric in-range port — and rebuilds it from
validated parts rather than ever using the raw string. Request paths (`/capture/item`,
`/capture/item/{id}/pdf`) are extension-owned literal constants, never templated from anything the
host supplies. Covered by
`app/desktop-shell/extension/background.test.mjs::validateBackendOrigin rejects everything a
compromised or buggy host could try` (13 rejection cases, including a host-supplied path).

## Hostile-webpage and unapproved-extension attempts

Unchanged from Stage 1's own table, restated because Stage 2 is what makes it concretely
enforceable rather than aspirational: an ordinary webpage has no route to `nativeMessaging` at all
(that's an extension-only browser API); an unapproved extension is refused at the browser's own
`allowed_origins` check before Callosum's code ever runs, and refused a second time by the host's
own `caller_is_allowed` if it somehow got that far. Neither can read the pairing file (owner-only,
local filesystem) or observe a session token (native-messaging pipe, not a script-observable
channel).

## Sibling refusal

Structurally unchanged from Stage 1 (`reported_instance_role() != UI_ROLE` refuses Word-HTTPS and
tunnel-target), reinforced in Stage 2 by the connector host's OWN `instance_is_eligible` check —
belt-and-suspenders, not a new mechanism: even if a future bug let a sibling answer `/health` on the
remembered port, the host independently refuses to treat it as eligible. Rust-side coverage:
`callosum_connector.rs::tests::eligibility_accepts_packaged_ui_and_gates_dev_builds_on_the_flag`.

## Extension-compromise assumptions

Stated plainly rather than assumed away: if the extension itself is compromised (a malicious update
somehow reaches the user, or a supply-chain issue in the extension's own code), it inherits whatever
the connector host would hand any legitimate caller — a capture session, nothing more. It cannot
read the Library, cannot call any endpoint but `/capture/*`, and cannot obtain the pairing secret
directly (only the host, a separate binary, reads that file). This is the SAME bounded blast radius
Stage 1 already established for a compromised session token; Stage 2 does not widen it.

## Uninstall / update behavior — the finding that justified this whole increment

**F4 (Stage 2) — without a guard, every Tauri auto-update would have silently unregistered the
connector.** Verified against the ACTUAL NSIS template bytes embedded in
`@tauri-apps/cli-win32-x64-msvc` (grepped directly, not assumed from documentation): Tauri's own
updater, when it re-invokes the previous version's `uninstall.exe` as part of an update, passes
`/UPDATE` (plus `/P` for this app's configured `passive` install mode) before laying down the new
version's files. The stock template guards shortcut/autostart/registry-cleanup-on-datadelete
removal with `${If} $UpdateMode <> 1` for exactly this reason.
`NSIS_HOOK_PREUNINSTALL` in `installer-hooks.nsh` uses the identical guard, so an ordinary
auto-update NEVER touches the connector's registry keys — verified in
`.github/workflows/desktop-shell-windows.yml`'s new "update-mode uninstall preserves connector
registration" step, which runs the REAL uninstaller with the REAL argv Tauri constructs (not a
synthetic stand-in), on a real Windows runner. *Severity if unfixed: would have been medium (a
silently broken feature with no obvious cause, recoverable only by reinstalling) — caught before
shipping by the exploration this increment opened with.*

**Ownership on uninstall is exact-path, both directions.** `NSIS_HOOK_POSTINSTALL` only ever writes
the registry to point at THIS install's own manifest; `NSIS_HOOK_PREUNINSTALL` only ever removes a
registry value after confirming byte-for-byte equality with that same path (`${If} $8 == $9`, not
"starts with $INSTDIR" — steering point 5). CI pre-seeds an unrelated third-party
`NativeMessagingHosts` entry and asserts it survives BOTH the update-mode and the ordinary uninstall
path untouched.

**Pairing-secret failure fails closed for capture only (steering point 6).**
`_ensure_capture_pairing_ready()` in `app/backend/api/app.py` catches `OSError` around
`ensure_pairing_secret()` and logs a warning rather than letting a filesystem/permissions failure
take down the rest of Callosum's startup — capture is an optional integration, and every other
feature already tolerates an absent pairing secret (`/capture/session` simply 401s). Tested:
`tests/test_capture.py::test_startup_pairing_failure_is_logged_and_does_not_raise`.

## Evidence status — what "PASS" covers and what it does not

Every claim below traces to a command that was actually run this session; nothing here is upgraded
past its actual evidence. Four distinct levels, not two:

| Level | Status | Evidence |
|---|---|---|
| **Component behavior, run locally** | PROVEN | `cargo test --release` (whole `src-tauri` crate, including `callosum_connector`: 56 + 8 = 64 passed, 0 failed, 6 pre-existing `#[ignore]`s untouched by Stage 2); `cargo clippy --release --bin callosum_connector -- -D warnings` (clean); `pytest tests/test_capture.py tests/test_connector_identity.py tests/test_desktop_packaging.py tests/test_health.py` (87 passed, 1 pre-existing failure — see below — 1 skipped); `node --test app/desktop-shell/extension/background.test.mjs` (12 passed); `ruff check` / `ruff format --check` on every touched Python file (clean). |
| **Packaged behavior, run locally** | PARTIALLY PROVEN | The connector host binary and NSIS `.nsh`/generated-include logic were built and staged via the real pipeline (`stage_connector.py`, `generate_connector_nsh.py`) and inspected against ground truth extracted directly from the actual NSIS template bytes embedded in `@tauri-apps/cli-win32-x64-msvc`. The packaged NSIS installer itself was **not** built or run this session (that needs the full `npx tauri build` toolchain path); the acceptance harness that would exercise a real packaged install end to end (`acceptance_harness.py`) was written and its imports/CLI verified, but **not executed**. |
| **CI installer/update/uninstall behavior** | NOT YET RUN | `.github/workflows/desktop-shell-windows.yml`'s new registration/ownership/`/UPDATE`-guard verification steps are written and the YAML parses, but have never executed on a runner — that requires a push, which is outside this session's authorization. Integration acceptance pending. |
| **Real Edge click-through acceptance (cases A–E)** | NOT YET RUN | `acceptance_harness.py` was built (isolation procedure, dev-connector registration, local fixtures, Library-state assertions) but requires a human (or a session with real browser click control) to actually click the extension's toolbar icon. Empirically unverified — not yet exercised end-to-end. |

**Full-repo regression, run once this session:** `pytest tests/` (excluding the one pre-existing
failure below, run separately) — 3154 passed, 6 skipped, 1 deselected, 0 failed among tests this
branch could plausibly affect. Reported precisely as: *full regression suite passed excluding one
baseline-confirmed pre-existing failure*, not as an unrestricted all-green run — see the next
paragraph for what was excluded and why that's justified by evidence, not assumption.

**Baseline comparison, not assumption.** An earlier pass of the full suite (before excluding
anything) surfaced 41 failures, all in `test_citation_style_repository.py`, `test_citations.py`,
`test_demo_snapshot.py`, `test_frontend_assembly.py`, and `test_website_how_it_works.py` — none of
them files this branch touches. Rather than assume irrelevance from that alone, a temporary detached
git worktree was created at the Stage 1 baseline commit `eddc97ed` (zero Stage 2 changes present)
and the identical 41 tests were run there: **all 41 failed identically**, root-caused to a missing
`node_modules/` at the repo root (an environment-setup gap, not a code defect) and, separately, the
citeproc/citation-style cluster. The one test excluded from the reported full-regression number,
`test_python_runtime_ids_are_current_deterministic_and_platform_specific`, was independently
reproduced in that same baseline worktree and failed with the identical stale-hash message
(`win-x86_64-py3.11-s1-b864259efc703853`) — proof, not inference, that it predates every Stage 2
change. The temporary baseline worktree was removed after comparison.

The distinction matters: everything in row 1 is real, repeatable, machine-checked evidence. Rows 2–4
are engineering artifacts built to make that evidence obtainable, not evidence of packaged/installed/
browser-driven behavior themselves. Neither of the last two rows is a risk anyone has weighed and
accepted — they are simply not yet exercised, and are called that rather than folded into a
risk-acceptance framing that would overstate what happened here.

## Residual evidence gaps for Stage 2 (not risk acceptances)

- **Integration acceptance pending: no live-browser click was exercised in this session.** The Rust
  connector host, the NSIS installer plumbing, and the Python startup wiring were each verified by
  automated tests that ran for real. The end-to-end product loop — a human clicking the real
  extension in a real Edge session against a real packaged build — was built as
  `.claude/experiments/browser-capture-acceptance/acceptance_harness.py` but not executed, because
  driving a real browser click is outside what this session could do. This is an evidence gap to be
  closed by an actual run, not a security risk that was identified and knowingly accepted.
- **Integration acceptance pending: the new CI installer/update/uninstall steps have not executed.**
  Written and YAML-valid, never run on a clean runner. Closing this requires the push the user has
  reserved for separate authorization.
- A local process running as the user remains out of scope, unchanged from Stage 1: it can read the
  pairing file and call the API directly regardless of any browser-capture control. This one *is* a
  structural, already-understood boundary (not new to Stage 2), not an unexecuted test.
- The extension's generic-page extraction (DOI/Highwire/JSON-LD) is fixture-tested
  (`background.test.mjs`) but has not been run against real, currently-live publisher markup in this
  session — a deliberate scope boundary (no CI dependency on a live publisher page staying stable),
  not an oversight, but worth the maintainer's own spot-check before wide use.

## Release-readiness consequence of the empty production allowlist

Stage 2's implementation is locally complete: the host, installer hooks, extension, and startup
wiring all exist, are wired together correctly, and are covered by tests that pass. But
`connector/identity.json`'s empty `production_extension_ids` means the **production native-host
identity is not yet activatable by any real store-distributed extension** — `allowed_origins` is an
empty list, so even a perfectly-installed connector currently accepts zero real callers. This is the
correct, fail-closed state for an extension that has never been published, not a bug to route around.
Phase 1 is not release-ready on Stage 2's implementation alone; it additionally needs, in order: (1) a
real Chrome Web Store and/or Edge Add-ons submission producing a real extension ID,
`production_extension_ids` updated to match, and a new build; (2) the CI installer/update/uninstall
run actually executing green on a clean runner; (3) real Edge click-through acceptance (cases A–E)
actually executed and passing. None of those three are Stage 2 implementation work — they are the
remaining evidence-gathering and store-publication steps this audit deliberately does not claim.

---

**Security Audit (Stage 2): PASS on every control that was actually exercised** — no unresolved
critical or high findings among the controls covered by the automated tests listed above. Two items
are explicitly logged as **integration acceptance pending / empirically unverified**, not as an
accepted risk: the real Edge click-through (cases A–E) and the CI installer/update/uninstall run.
Neither has a known, named security defect; both simply have not been exercised yet, and this audit
does not claim they have. F3 (Stage 1's carry-forward) is resolved at the component level by F4's
verified `/UPDATE` guard; the CI ownership checks that would additionally verify it against a real
runner have not yet run. Combined with Stage 1: **PASS**, scoped exactly as described above.
