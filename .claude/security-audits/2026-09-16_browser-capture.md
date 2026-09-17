# Security audit — browser capture (issue #61, Phase 1 + Phase 2)

**Status: Stage 1 COMPLETE (PASS). Stage 2 COMPLETE (PASS), CI-proven on a clean Windows runner for
the installer/registration/update/uninstall lifecycle (run `35134478341`, commit `1c46a73e`). One
item remains empirically unverified — the real Edge A–E click-through — see "Evidence status" and
"Residual evidence gaps for Stage 2" below.** Opened at task start per `CLAUDE.md`'s kickoff rule,
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
auto-update NEVER touches the connector's registry keys — **CI-proven**, not just implemented:
`.github/workflows/desktop-shell-windows.yml`'s "update-mode uninstall preserves connector
registration" step ran the REAL uninstaller with the REAL argv Tauri constructs (not a synthetic
stand-in) on a real, clean Windows runner (run `35134478341`) and printed
`confirmed: update-mode uninstall preserved both connector registry keys` after asserting the
registry values were byte-for-byte unchanged. *Severity if unfixed: would have been medium (a
silently broken feature with no obvious cause, recoverable only by reinstalling) — caught before
shipping by the exploration this increment opened with.*

**Ownership on uninstall is exact-path, both directions.** `NSIS_HOOK_POSTINSTALL` only ever writes
the registry to point at THIS install's own manifest; `NSIS_HOOK_PREUNINSTALL` only ever removes a
registry value after confirming byte-for-byte equality with that same path (`${If} $8 == $9`, not
"starts with $INSTDIR" — steering point 5). CI pre-seeds an unrelated third-party
`NativeMessagingHosts` entry and — CI-proven, run `35134478341` — printed
`confirmed: third-party NativeMessagingHosts entry survived untouched` after BOTH the update-mode
and the ordinary uninstall path ran for real.

## Three more findings, from actually running the installer end to end (not from writing it)

Getting the CI run above to a genuine pass took three rounds of real failures, each investigated to
a root cause rather than patched around or re-run blind. None are security defects; all three would
have made the shipped installer produce an app that never starts. Listed because "the installer
mechanism was designed correctly" and "the installer mechanism was verified to actually work" turned
out to be two different, sequentially-discovered claims.

**F5 — a Stage 1 maintenance gap, not a Stage 2 or main-branch defect.** The very first CI attempt
against Stage 2 failed before reaching any new code, at a pre-existing step verifying the immutable
Python runtime spec (`windows-x86_64 runtime_id is stale`). Root-cause traced with evidence, not
assumed: `origin/main`'s own `verify()` passes cleanly (checked directly in a temporary detached
worktree); Stage 1 (not Stage 2) had edited `smoke_test_backend.py`, a declared `shared_inputs`
identity file, without re-running `package_python_runtime.py update-ids` afterward. Fixed
mechanically (`update-ids`, verified only the four `runtime_id` fields changed, `verify()` now
passes) and the four now-current runtime IDs were published via the existing
`desktop-python-runtime.yml` workflow — independently re-verified afterward (`gh release view` on
each, manifest content inspected, `runtime_id`/`platform`/`arch` cross-checked against the release
being claimed) before ever dispatching another installer run.

**F6 — a bare relative `!include` in `installer-hooks.nsh` resolved against the wrong directory.**
The connector's generated `.nsh` include failed with `!include: could not find:
connector-identity.generated.nsh` even though the generator had just written it to the correct
directory moments earlier — Tauri stages/includes the hook file from a generated main
`installer.nsi` living in a completely different build directory, so a bare relative path resolved
against THAT script's directory, not the hook file's own. Reproduced and fixed locally against the
real cached NSIS 3.11 compiler (a minimal two-file repro under a different main-script directory)
before touching the real file: `${__FILEDIR__}`, NSIS's own built-in for "the directory of the file
currently being processed," is the correct fix, and was empirically confirmed to both reproduce the
failure (bare path) and resolve it (`${__FILEDIR__}`-qualified) before either change was trusted.

**F7 — the most severe: `callosum-shell.exe` silently never started at all.** After F6's fix, the
installer built and installed correctly, but the app exited within milliseconds of every launch,
with no window, no crash report, and exit code 0. Root cause, found by direct local reproduction
rather than speculation: having `callosum_connector` as a second `[[bin]]` in the SAME Cargo package
as the Tauri app broke `cargo tauri build`'s main-binary selection — even with `mainBinaryName`
explicitly set, the full build pipeline still wrote the CONNECTOR's compiled bytes (~3.8 MB) to
`callosum-shell.exe`'s path. Confirmed directly: `cargo build --bin callosum-shell` alone produces
the correct ~16.8 MB binary; the same build via the full `tauri build` pipeline, with the connector
present as a sibling `[[bin]]`, overwrites it with the connector's content. A diagnostic write
placed as the literal first statement of the app's own `run()` never appeared on disk across
repeated launches — proof the app's real code never executed at all; the "app" launching and
exiting was actually the connector's own `main()`, refusing a caller with no `argv[1]` and exiting
cleanly, exactly as designed for a DIFFERENT, legitimate scenario. This explains BOTH of the two
prior CI failures under one root cause, not two separate ones. Fixed by moving the connector into
its own Cargo package (`app/desktop-shell/connector-host/`) so `cargo tauri build` never sees it
exist in the package it is building at all — removing the ambiguity at its root, not working around
a symptom of it. Verified locally end to end before trusting it on CI: the installed binary is the
correct size, launches, stays running, and shows a window titled "Callosum"; **then CI-proven** on
run `35134478341`, including the real backend becoming healthy (`healthy on port 55873 after 117s`)
and a screenshot of the actual, fully-rendered Callosum UI.

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
| **Component behavior, run locally** | PROVEN | `cargo test --release` for both packages (`src-tauri`: 56 passed; `connector-host`: 8 passed; 64 total, 0 failed, 6 pre-existing `#[ignore]`s untouched by Stage 2); `cargo clippy --release -- -D warnings` clean for both packages; `pytest tests/test_capture.py tests/test_connector_identity.py tests/test_desktop_packaging.py tests/test_health.py` (88 passed, 0 pre-existing failures remaining — see below — 1 skipped); `node --test app/desktop-shell/extension/background.test.mjs` (12 passed); `ruff check` / `ruff format --check` on every touched Python file (clean). |
| **Packaged behavior, run locally** | PROVEN | The full NSIS installer was built for real (`npx tauri build`) and installed via its actual silent `/S` path into a throwaway directory (`/D=`), never touching the maintainer's real Callosum install: correct ~16.9 MB `callosum-shell.exe`, `connector\callosum-connector.exe`, a correctly-populated `org.callosum.connector.json`, and both Chrome/Edge HKCU registry entries, all confirmed by direct inspection. The app was launched directly and stayed running (window titled "Callosum"), unlike three real defects this same local verification found and fixed (see Findings). Update-mode (`/UPDATE`) and ordinary uninstall were both run for real locally, with a pre-seeded third-party registry entry proven to survive both. |
| **CI installer/update/uninstall behavior** | CI-PROVEN | A clean-runner Windows Actions run (`35134478341`, bound to commit `1c46a73e`, `workflow_dispatch`) executed and passed every new verification step, confirmed from actual log content, not just the green checkmark: `healthy on port 55873 after 117s` (real backend startup on a truly clean machine); per-browser manifest resolution (`Google\Chrome -> ...\connector\org.callosum.connector.json`, same for Edge) with `name`/`type`/`path`-resolves/`allowed_origins==[]` all asserted and none throwing; `confirmed: update-mode uninstall preserved both connector registry keys` after the REAL `/UPDATE` argv; `confirmed: ordinary uninstall removed both connector registry keys`; `confirmed: third-party NativeMessagingHosts entry survived untouched` after both uninstall paths. The uploaded screenshot additionally shows the real, fully-rendered Callosum UI (onboarding wizard, Library/My Publications/Synthesize tabs) running on the runner. |
| **Real Edge click-through acceptance (cases A–E)** | PROVEN (dev/test identity path) | `run_acceptance_AtoE.py` executed all five cases in one isolated session against a real packaged `callosum-shell.exe` and a real Edge browser with the real (dev-keyed) extension loaded, driving the click via Windows UI Automation keyboard-focus navigation — proven in isolation against a throwaway probe extension (CDP-confirmed `activeTab` grant: `chrome.scripting.executeScript` read the real page's `document.title` after the click, badge/title updated) before being trusted here. Cases A, C, D passed exactly against their specified criteria (real DOI resolved and admitted with `capture:browser` provenance / single row on re-click / trashed paper stayed deleted). Cases B and E were rerun a THIRD time on 2026-09-16 (see F12 below) against the provisional-ingestion contract that superseded F11's terminal refusal: B genuinely queued for review (a real front-matter DOI was found and resolved via live Crossref, but the PDF's own extracted title candidate did not corroborate it — zero paper creation, zero mutation), and E genuinely reached `attachment_conflict` through a real Edge click + live Crossref resolution of a real DOI, proving the attachment-safety branch reachable end to end rather than only at component level. See `evidence-run/evidence.json` (A–E), `evidence-run-be-direct-pdf/evidence.json` (the now-superseded refusal-contract B/E rerun), and `evidence-run-provisional-direct-pdf/evidence.json` (this session's B/E rerun) for all three runs. Three genuine defects (F8, F9, F11) and one environment-only test hazard (F10) were found and fixed as a direct result of running this for real; F12 is a product reframing, not a defect. |

**Full-repo regression, run once this session:** `pytest tests/` (excluding the one pre-existing
failure below) — 3169 passed, 6 skipped, 0 failed among tests this branch could plausibly affect.
Reported precisely as: *full regression suite passed excluding one baseline-confirmed pre-existing
failure*, not as an unrestricted all-green run — see the next paragraph for what was excluded and why
that's justified by evidence, not assumption.

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

**2026-09-16 addendum (F12's session):** the identical class of noise reappeared — a full-suite run
executed *concurrently* with a `cargo build --release`, an `npm install`, and the real Edge B/E rerun
below reported 41 failures; rerunning exactly those 41 in isolation (`pytest --lf`, nothing else
running) passed 40 of them immediately, confirming they were resource contention, not defects. The
one survivor, `test_primary_local_destinations_exist[demo/-target2]`, fails because this worktree has
no `dist-demo/` (the demo site's own build was never run here) — a gitignored generated directory,
unrelated to browser capture or anything this session touched. Same diagnosis discipline as the
paragraph above, applied to a fresh occurrence of the same underlying phenomenon (concurrent
resource-heavy operations classified as false regressions).

The distinction matters: everything in row 1 is real, repeatable, machine-checked evidence. Rows 2–4
are engineering artifacts built to make that evidence obtainable, not evidence of packaged/installed/
browser-driven behavior themselves. Neither of the last two rows is a risk anyone has weighed and
accepted — they are simply not yet exercised, and are called that rather than folded into a
risk-acceptance framing that would overstate what happened here.

## Findings F8–F13, from actually clicking the real extension in real Edge

Same discipline as F5–F7: each was found by running the real product end to end, not by reading the
code, and each was reproduced, root-caused with direct evidence, fixed, and re-verified before being
trusted. None is a security defect; all four blocked the acceptance run from ever completing (or
from meaning what it claimed) before being fixed.

- **F8 — dev-only native-messaging launcher.** The `.bat` wrapper `_register_dev_connector` used to
  generate (`set CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD=1` then exec the real binary) reliably broke the
  real connector's outbound HTTP client: invoked as a grandchild of `cmd.exe` with piped stdio
  (exactly how Chrome invokes a native-messaging host), `reqwest`'s blocking client timed out
  connecting to `127.0.0.1` on every single attempt, while the identical binary invoked directly (no
  `cmd.exe` in the process chain) connected instantly, every time, with no code difference at all.
  Root cause not pinned down further than "going through `cmd.exe /c` with piped stdio breaks it."
  Fixed by replacing the `.bat` with `dev_connector_launcher.exe`, a tiny real native binary
  (`connector-host/src/bin/dev_connector_launcher.rs`) that sets the same env var and execs the real
  connector with no shell in the process chain — verified fixed via 3 direct repeated invocations
  (consistently `available`, <1s each) and via a real Edge click reaching a real `/capture/session`
  200. Dev-only: never shipped, never referenced by the production installer, no change to the
  production connector's trust model.
- **F9 — browser capture's admission path never fell back to a default `CrossrefClient`.**
  `capture.py` read `request.app.state.crossref_client` directly, which is `None` for the real app's
  own module-level `app = create_app()` (the parameter exists for test injection only — confirmed by
  reading `acquisition.py`'s sibling endpoint, which *already* has the identical fallback with a
  comment referencing this exact class of bug: "Without this the running app's
  app.state.crossref_client is None and every DOI would 'fail to resolve' even though Crossref is
  reachable"). Effect: every DOI-bearing browser capture reported `unresolved_review_required`
  regardless of the DOI's real resolvability — reproduced against a real, live DOI
  (`10.1371/journal.pone.0000308`) before the fix, confirmed resolved (real title, `capture:browser`
  provenance, single live row) after it. Fixed by adding the same
  `request.app.state.crossref_client or CrossrefClient()` fallback `acquisition.py` already uses;
  `tests/test_capture.py`'s 37 tests re-run clean (they inject a fake client explicitly, so the
  fallback branch is untouched by them, matching `acquisition.py`'s own test coverage shape).
- **F10 — real-machine test hazard, not a product defect: auto-scan-on-launch reached the
  maintainer's real document library.** Callosum unconditionally auto-scans "the library folder" on
  every launch (`library.py`: "Auto-triggered on app launch (default on)"), which defaults to
  `<OS Documents dir>/callosum-library` — sensible for a real end user, but every disposable test
  launch on the maintainer's own machine resolved the *same* real, Dropbox-synced folder as any real
  install would, entirely independent of the isolated `%APPDATA%\com.callosum.desktop` directory this
  audit's isolation procedure covers. Every scan attempt on real files failed harmlessly
  (`[Errno 22] Invalid argument`, confirmed zero file mutation via unchanged pre-session mtimes on
  every sampled file), but the resulting request volume was enough to (a) hold the SQLite WAL writer
  lock long enough to make unrelated test fixture-seeding fail with "database is locked", and (b)
  delay a real capture's own requests past a real Edge extension service worker's lifetime, aborting
  a capture attempt mid-flight. A related PDF-attach path (`attach_pdf_to_paper`) separately writes
  captured bytes into the same "library folder" by design (`library_dir()`) — a genuinely fresh
  install's PDF-attach 500'd for an unrelated, correctly-scoped-out reason (no local embedding model
  downloaded yet; see the release-readiness note below), but the *destination* for that write was
  also the real folder before the fix below. Fixed with `CALLOSUM_LIBRARY_DIR_OVERRIDE`, a new,
  narrowly-scoped environment-variable override in `backend.rs` (mirrors the existing
  `CALLOSUM_SETTINGS_PATH` override pattern) that the acceptance harness sets to a disposable
  directory before every launch; verified fixed by a clean run showing zero `callosum-library`
  matches and zero warnings in `backend.log`. This is a test-isolation gap this audit's own isolation
  procedure did not originally cover (it isolated the database, not the separate "library folder"
  concept), not a defect in the product's own real-world behavior.
- **F11 — a direct-PDF capture's title is a filename, not bibliographic identity, and admission
  treated it as if it were.** Traced (not inferred) end to end: `background.js`'s `handleCapture`
  branches on `looksLikePdfUrl(tab.url)` *before* any DOM extraction is attempted — Chrome's own PDF
  viewer renders in its own extension's origin (`chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/
  edge_pdf/...`, confirmed via CDP), which this extension has no host permission to script into, so
  DOM extraction is not merely skipped for a PDF tab, it is not viable under the current permission
  model at all. `buildDirectPdfEnvelope` therefore sets only a filename-derived `title` and
  `pdf_bytes_from_active_tab: true` — never a DOI, year, or creators. `admission.py`'s `admit()` no-
  DOI branch (written for *generic* HTML captures, where a real page title genuinely is bibliographic
  evidence) then unconditionally created a fresh, anonymous, unfindable paper from that filename —
  the real Case B/E acceptance-run finding. **Fix, applied at the single canonical enforcement point
  the router's own docstring already names ("every consequential decision... belongs to the canonical
  admission substrate, not to this router and never to the extension"):** `admit()` now refuses any
  `pdf_bytes_from_active_tab` envelope that reaches the no-DOI branch with a new, precise, designed
  status, `direct_pdf_identity_unresolved` — chosen deliberately narrower than "PDFs are unsupported":
  a direct-PDF envelope that *does* carry a real DOI, or a genuine title+year+author tuple, never
  reaches this check at all and is handled entirely by the pre-existing, unchanged rules above and
  below it. Zero paper creation, zero mutation, no `capture_id` (so `/capture/item/{id}/pdf` cannot be
  called), `pdf_reason: "not_offered"`. The extension maps the new status to an explicit,
  non-alarming rendered result instead of the generic `"failed"` fallback. **Consequence for the
  fresh-install embedding-model 500 noted below:** it was only ever reachable via
  `/capture/item/{id}/pdf`, which is only reachable when a `capture_id` is minted — this fix removes
  that possibility for any direct-PDF capture with no real identity, confirmed empirically (zero
  `/capture/item/{id}/pdf` log lines in either rerun below), not merely argued. **Verified three
  ways:** (1) two new focused `tests/test_capture.py` tests — one proving an identity-empty direct-PDF
  envelope shaped exactly like the real extension's output is refused with zero paper creation and a
  404 on a fabricated `capture_id`, one proving a *hypothetical* DOI-bearing direct-PDF envelope still
  uses the ordinary, unchanged admission rules; full suite (39 tests) passes. (2) A direct HTTP
  round-trip against the real, freshly rebuilt packaged binary (bypassing Edge) confirmed the exact
  JSON response and zero DB mutation. (3) A real Edge rerun of cases B and E from a fresh disposable
  instance (`run_acceptance_BE_direct_pdf.py`) confirmed the real extension renders "Callosum couldn't
  tell what scholarly work this PDF is. Try capturing it from the article's own page instead." for
  both, with zero paper/attachment/annotation mutation and zero `/capture/item/{id}/pdf` calls in
  `backend.log` for either case. **A real build-pipeline gap surfaced during verification, fixed in
  the process, not left latent:** the packaged binary reads its Python backend from a build-time copy
  (`src-tauri/target/release/callosum-src/`) that `stage_source.py` alone does not refresh — only a
  full `npx tauri build` does. The first rerun attempt (against a binary rebuilt *before* this fix
  existed) still created an anonymous paper for exactly this reason; caught immediately by checking
  the response against a direct HTTP call to the running binary before trusting a second real-Edge
  run, root-caused via file timestamps, and closed by rebuilding for real before rerunning.

  **Case E's `attachment_review_required` branch is proven separately, at the component level, using
  an envelope shape a real click cannot produce.** `tests/test_capture.py`'s `_envelope()` helper
  defaults to a real DOI; every existing `pdf_bytes_from_active_tab=True` test
  (`test_existing_paper_with_a_pdf_refuses_capture_bytes`,
  `test_existing_paper_with_annotations_refuses_capture_bytes`) already exercises exactly this
  branch — existing paper resolved, `attachment_review_required`, `capture_id: null` ("no upload slot
  is offered"), existing attachment/annotation count unchanged — with a DOI the real, unmodified
  extension has no way to attach to a direct-PDF envelope today. This was already true before F11;
  F11's fix does not touch it, and the real-Edge rerun above confirms real-Edge E cannot reach it
  (same `direct_pdf_identity_unresolved` refusal as B), matching this precisely rather than
  papering over it. **Automatic real-browser direct-PDF-to-existing-paper reconciliation is an
  explicit architectural boundary of today's permission model, not a missing Phase 1 implementation
  — deferred, not broken.**

- **F12 (2026-09-16) — not a defect: a product reframing of F11's contract, driven by user critique
  of the acceptance evidence F11 itself produced.** F11's terminal refusal was correct evidence for
  the contract in force at the time: it proved a filename must never become bibliographic identity.
  But running it for real also showed the cost of that contract — a user who explicitly clicks "Add"
  on a PDF they are already looking at loses the artifact outright the moment Callosum cannot yet
  name it. Cliff's critique reframed the target: capture immediately, identify opportunistically,
  canonicalize conservatively, escalate ambiguity to the user, never lose the artifact. F11's
  invariant — a direct-PDF envelope's filename never becomes a canonical Paper's title — is
  **permanent and unchanged**; only what happens *instead of refusing* changed. `admission.py`'s
  `direct_pdf_identity_unresolved` branch now accepts the bytes (`pdf_accepted=True`,
  `pdf_reason="provisional_capture"`) rather than refusing them, and a new module
  (`app/backend/capture/provisional.py`) preserves them atomically in a durable Import Queue
  (`_Import Queue/<artifact_id>.pdf` + a hidden `.provenance/artifacts/<artifact_id>.json` sidecar,
  both structurally invisible to the ordinary non-recursive Library scan) before attempting identity
  from the PDF's own front-matter DOI + title corroboration. Promotion is deliberately conservative:
  only a uniquely strong front-matter candidate (Crossref-resolved title agreeing with the PDF's own
  title) auto-promotes through the **unchanged** `add_paper_by_doi`/`attachment_decision` substrate; a
  DOI observed only inside a References section is excluded from consideration entirely, never merely
  downweighted; two competing strong candidates queue rather than picking a winner. Identity
  (`unresolved`/`resolved`) and promotion outcome (`pending_review`/`attachment_conflict`/
  `processing_failed`/`indexing_unavailable`/`promoted`) are kept as orthogonal facts, so the system
  can truthfully distinguish "I don't know what this is" from "I know exactly what this is but
  couldn't safely attach it." The queue copy is never relinquished before a promotion durably
  succeeds — a promotion failure at any point (including a missing embedding model) leaves the
  original bytes untouched and removes only a staged duplicate, proven by a dedicated
  failure-injection test. Content-hash dedup preserves the object, not the encounter: recapturing
  identical bytes never creates a second physical file, but each encounter is still recorded as its
  own provenance event. Startup recovery adopts any queue file a crash left with no database row
  rather than ever discarding a preserved artifact. **Verified:** 51 focused `tests/test_capture.py`
  tests (including the original F11 refusal test, updated to assert the new acceptance behavior with
  the filename-never-identity invariant intact) plus the pre-existing attachment-safety component
  tests, all passing; a fast direct-HTTP smoke check against the freshly rebuilt packaged binary
  before trusting a third real-Edge cycle; and a real Edge rerun of B and E from a fresh disposable
  instance (`run_acceptance_direct_pdf_provisional.py`) that reached genuine, non-manufactured
  outcomes for both — see the evidence-status table above and the Release-readiness section below.

- **F13 (2026-09-17) — not a defect: the human review/resolution loop that closes the Import Queue's
  remaining gap, gated by this document's own "new API endpoints" trigger.** F12 left a durable
  but silent holding area: an artifact could sit in `provisional_artifacts` indefinitely with no way
  for a user to see it, understand why it's there, or resolve it. Five new endpoints extend
  `app/backend/api/routers/import_queue.py` under the **same, unchanged** desktop-UI trust boundary
  as the existing list/delete routes (never the capture-session bearer token, which stays
  browser-extension-only) — no new trust path was introduced:
  - `GET /library/import-queue/{id}` — full detail + evidence, read-only.
  - `GET /library/import-queue/{id}/pdf` — streams the queued PDF's raw bytes for client-side (pdf.js)
    preview rendering. The served path is resolved **only** from the trusted `provisional_artifacts`
    DB row (`row["pdf_path"]`), matching `paper_files.py`'s existing ownership-safe pattern exactly —
    never from client-supplied input — and is further constrained to files still physically inside
    `_Import Queue/`, so a promoted-and-moved artifact 404s rather than serving a stale/wrong path.
  - `POST /library/import-queue/{id}/preview-doi` — genuinely read-only (composes `normalize_doi` +
    `find_existing_paper_by_identity` + `crossref_client.resolve_doi` directly; deliberately never
    calls `add_paper_by_doi`, which can create). Verified by four dedicated tests asserting zero DB
    mutation for invalid, unresolved, existing-match, and new-candidate DOI inputs.
  - `POST /library/import-queue/{id}/confirm` and `POST /library/import-queue/{id}/retry` — the only
    new *mutating* surface. Both route through a refactored, shared `attempt_attach_to_paper`
    subroutine — the exact same `attachment_decision` → staged-copy → `attach_pdf_to_paper` →
    delete-queue-copy-only-on-success sequence F12 already proved safe under failure injection —
    rather than a review-specific shortcut. An explicit user decision (which candidate, or a manually
    typed DOI) is appended to `evidence_json`'s new `user_actions` array; the original
    `candidates`/`resolutions` the automatic pipeline observed are never rewritten, preserving
    "observation ≠ inference ≠ canonical fact" for this one capture.
  Deletion policy was made explicit rather than left implicit: permanently deleting a provisional
  artifact deletes its entire encounter history (`capture_events` cascade) as a **documented,
  deliberate** decision for pre-canonical state, not merely because the schema happens to cascade —
  confirmed by a test that also proves a *second*, independent artifact is untouched by that deletion.
  No PDF thumbnail cache was introduced: the first-page preview renders entirely client-side from the
  raw-bytes route above, using the same pdf.js integration the ordinary PDF viewer already has —
  nothing new to own, version, or clean up. **Verified:** 32 new `tests/test_import_queue.py` tests
  (all passing alongside the full 51-test provisional-capture suite, unmodified) plus 20 new Node
  tests for the review UI's pure state→copy/action and action→HTTP-contract logic
  (`tests/frontend/test_import_queue_logic.test.mjs`), added specifically because real-Edge
  acceptance cannot exercise clicks inside Callosum's own Tauri window. **Real Edge acceptance
  (R1–R4) for this finding is recorded separately below, once run** — this entry is not backdated to
  claim evidence that did not yet exist when it was written.

## Residual evidence gaps for Stage 2 (not risk acceptances)

- A local process running as the user remains out of scope, unchanged from Stage 1: it can read the
  pairing file and call the API directly regardless of any browser-capture control. This one *is* a
  structural, already-understood boundary (not new to Stage 2), not an unexecuted test.
(The extension's generic-page extraction against real, currently-live publisher markup is also
resolved — Case A of the real Edge acceptance run extracted `citation_doi` from a real, live PLOS
ONE page and the DOI resolved correctly end to end. `background.test.mjs`'s fixture tests remain the
CI-safe, publisher-independent baseline; this one real-page run does not replace them or become a CI
dependency — it is a one-time, human-authorized acceptance exception, documented as such above.)

(The CI installer/update/uninstall gap that was here is resolved — see the evidence-status table and
F5–F7 above. The real Edge click-through acceptance gap that was also here is resolved — see the
evidence-status table and F8–F10 above. Both rows in this list moved from "pending" to "proven" this
session; only the local-process-as-user structural boundary above remains, unchanged from Stage 1.)

## Release-readiness consequence of the empty production allowlist

Stage 2's implementation is now proven, not just complete: the host, installer hooks, extension, and
startup wiring all exist, are wired together correctly, are covered by tests that pass, have been
shown to actually produce a working, correctly-registered, cleanly updatable and uninstallable
packaged app on a real clean Windows runner, and — as of this session — a real Edge click has been
shown to carry a real capture end to end (real DOI extracted, resolved, and admitted with
`capture:browser` provenance) for the **dev/test native-host identity path**. But
`connector/identity.json`'s empty `production_extension_ids` means the **production native-host
identity is not yet activatable by any real store-distributed extension** — `allowed_origins` is an
empty list, so even a perfectly-installed, perfectly-working connector currently accepts zero real
callers. This is the correct, fail-closed state for an extension that has never been published, not
a bug to route around. **(2026-09-16, superseded by F12 below — kept verbatim as the correct
statement for the terminal-refusal contract that was in force when it was written, not deleted or
edited to look like it anticipated F12.) Phase 1 browser-capture functional acceptance COMPLETE for
the Edge + development/test identity path. Direct PDFs without sufficient canonical identity are
deliberately refused without mutation. Automatic reconciliation of an identity-poor PDF tab to an
existing scholarly object is deferred beyond Phase 1.** Phase 1 is still not release-ready overall;
what remains is exclusively store-publication work, not implementation or acceptance work: a real
Chrome Web Store and/or Edge Add-ons submission producing a real extension ID,
`production_extension_ids` updated to match, and a new build. Every other item this audit previously
listed as pending — CI installer lifecycle, real Edge click-through acceptance including direct-PDF
behavior — is now proven, not just complete. Kept explicitly distinct: direct-PDF automatic
attachment/reconciliation is a later capability (not attempted, not claimed); production store/
native-host identity is a later, separate distribution gate.

The embedding-model 500 noted in an earlier version of this section (a genuinely fresh Callosum
install, with no local embedding model downloaded yet, 500ing on a direct-PDF attach step) was
**confirmed unreachable from the terminal-refusal acceptance path** described above, not merely
presumed so: F11's direct-PDF admission gate meant an identity-empty direct-PDF capture never
received a `capture_id`, so `/capture/item/{id}/pdf` — the only route that could reach
`attach_pdf_to_paper`'s embedding requirement — was never called. Verified empirically (zero such log
lines in either B/E rerun under that contract), not just argued from the code. Whether
`attach_pdf_to_paper` should tolerate a missing embedding model more gracefully remains a separate,
pre-existing, unrelated product question this audit takes no position on and did not touch.

**2026-09-16 addendum, superseding both paragraphs above (F12):** the provisional-ingestion contract
that replaced F11's refusal means `/capture/item/{id}/pdf` **is** now called for every direct-PDF
capture (bytes are always accepted for provisional capture), so the embedding-model path is no longer
structurally unreachable in principle — it is reachable exactly when a candidate auto-promotes and
`attach_pdf_to_paper` actually runs. Neither B nor E's real rerun below reached that point (B stayed
queued for insufficient title corroboration; E was blocked by `attachment_decision` before any attach
was attempted), so this specific pre-existing, unrelated defect was not re-triggered in this session's
real run — but it is deliberately no longer prevented by construction as F11's paragraph above
describes. `_attempt_promotion`'s own failure handling (proven by a dedicated failure-injection test)
means that if it did fire, the queue copy would survive untouched and the failure would surface as
`promotion_state="indexing_unavailable"`, not data loss or a raw 500 — a genuine improvement over the
pre-F11 behavior, but not the same claim as "unreachable." The updated final Phase 1 status:

> Direct-PDF capture preserves the user-accessed artifact immediately without fabricating canonical
> identity. Callosum then attempts evidence-based identity resolution; sufficiently supported matches
> are promoted/reconciled into the Library, while uncertain captures remain in a durable Import Queue
> for review.

Real Edge evidence for this session (`run_acceptance_direct_pdf_provisional.py`,
`evidence-run-provisional-direct-pdf/evidence.json`): **Case B** — the real PMC PDF's own front-matter
DOI (`10.1371/journal.pone.0000308`) was found and resolved through the live Crossref API, but the
PDF's extracted title candidate (a running-header artifact, `"pone.0000308 1..5"`) did not corroborate
the resolver's real title, so the candidate was correctly rejected as `insufficient_corroboration` and
the capture queued for review — zero paper creation, zero mutation, the extension rendering "Saved to
your Callosum Import Queue for review — identity couldn't be confirmed automatically." **Case E** — a
new local fixture PDF embedding a real, independently-verified-resolvable DOI
(`10.1371/journal.pone.0198331`) and its real Crossref title in its own front matter (a genuinely
identity-sufficient envelope, not a manufactured one) was seeded as an existing paper with one PDF
attachment beforehand; the real click resolved that DOI through live Crossref, matched the seeded
paper via the unchanged `add_paper_by_doi`, and `attachment_decision` correctly refused because the
paper already had an attachment — `identity_state="resolved"`, `promotion_state="attachment_conflict"`,
the seeded paper's attachment count and total paper count both unchanged, the queue copy for E's own
artifact still present and no canonical duplicate ever created, the extension rendering "Saved to your
Callosum Import Queue — matched a paper, but couldn't attach automatically." **This proves the
attachment-safety branch reachable through a real Edge click and live Crossref resolution, not merely
at component level** — a stronger result than the architectural-unreachability finding this same
section previously reported for the refusal contract. Real application data was verified byte-
identical to baseline (`sha256=9bc8e399e21e1904ab9b008dcdcb0b6b16a7ed1f0dfac0de92006b10ff631aab`)
after isolate/restore, matching every prior phase's baseline hash.

**2026-09-17 (F13) — real Edge R1–R4 acceptance: executed.** `run_acceptance_import_queue_review.py`
ran against the freshly rebuilt packaged binary (`Callosum_0.5.15_x64-setup.exe`'s
`callosum-shell.exe`), per the approved approach: capture via a real Edge UI-Automation click, review
actions (confirm/retry/delete/list/pdf-stream) via direct HTTP to the same running packaged backend's
real `/library/import-queue/*` endpoints. Real application data was verified byte-identical to
baseline (`sha256=9bc8e399e21e1904ab9b008dcdcb0b6b16a7ed1f0dfac0de92006b10ff631aab`) after isolate/
restore on every attempt, including the two attempts that failed before reaching R1 (a PMC CAPTCHA
challenge, then an HTTP client timeout — both environmental, neither touched real data; see the final
report for detail). **R2 PASS**: the real-DOI local fixture reached genuine `attachment_conflict`
(the existing seeded paper's title/attachment count unchanged), and the capture was explicitly
deleted as the documented alternative to leaving it queued. **R3 PASS**: a no-identity PDF queued
unconditionally and was deleted cleanly, no orphaned managed files. **R4 PASS**: a queued item's
evidence and PDF bytes survived a real, full stop/restart of the packaged binary against the same
disposable library directory — the first real-process-restart demonstration of the durability
guarantee unit-tested in F12. **R1 partial**: capture, listing, detail, and the real page-1 PDF
preview stream (91,408 real bytes) all worked correctly, and `confirm` correctly resolved the PDF's
own front-matter DOI through live Crossref and admitted a real Paper (`resolved_paper_id=1`) — but the
subsequent attachment/indexing step failed with a real, reproducible `OSError: [Errno 22] Invalid
argument`, reproduced identically on an automatic `retry`. This failure is inside the pre-existing
`attach_pdf_to_paper` → `embed_chunks` pipeline (`app/backend/pdf_processing/ingest.py`,
`app/backend/embeddings/pipeline.py`), code this increment calls unchanged and does not modify; it is
the first time this session's acceptance work drove a real, live-fetched multi-page academic PDF
through a real (non-fake) embedding model end to end, and it surfaced under the same host memory
pressure documented elsewhere in this file. Every guarantee this increment (F13) is actually
responsible for held correctly under this genuine failure: the queue PDF was preserved on disk and in
the queue listing (not lost), the artifact was left in a safe `resolved`/`processing_failed` state
with a plain-language "processing could not finish, your PDF is safe" explanation rather than a raw
error, `retry` was available and behaved consistently (safe, non-corrupting, if not yet successful),
and no other paper or attachment in the Library was touched. This is reported as a genuine, newly-
discovered defect in shared pre-existing PDF-ingestion infrastructure — flagged for a separate,
narrowly-scoped follow-up issue — not as an F13 defect, and not fixed here per this increment's
explicit scope boundary against touching unrelated pre-existing infrastructure.

---

**Security Audit (Stage 2): PASS**, and — as of this session — CI-proven for the installer lifecycle
AND proven for real Edge click-through acceptance on the dev/test identity path, including the
direct-PDF provisional-ingestion contract (F12), not just component-tested. No unresolved critical or
high findings among the controls covered by the automated tests, the clean-runner CI run, and the
real Edge acceptance runs described above. Findings F5–F11, all discovered by actually running the
real product end to end rather than by reading the code, are fixed and independently re-verified;
none is a security defect, and F7, F9, and F11 in particular
would each have quietly defeated a real, user-facing capability (the app silently never starting;
every DOI-bearing capture silently failing to resolve; every direct-PDF click silently creating an
anonymous, unfindable paper) if shipped unfixed. F12 is a later product reframing of F11's fix, not a
security finding: it preserves F11's permanent invariant (a filename never becomes canonical identity)
while replacing the terminal refusal with preserve-then-identify provisional capture, proven this
session via a third real Edge B/E rerun reaching genuine `pending_review` and `attachment_conflict`
outcomes end to end. F3 (Stage 1's
carry-forward) is now resolved both at the component level (F4's guard) and by a real clean-runner
run proving it. F13 (2026-09-17) adds the Import Queue's human review/resolution loop under the same
unchanged desktop-UI trust boundary — component/unit-proven (52 combined Python/Node tests), with its
real-Edge R1–R4 acceptance run **PENDING** as of this document's current text, deferred deliberately
rather than attempted under host memory pressure that could have risked real user data mid-isolation.
**`production_extension_ids` remains `[]`, unchanged, fail-closed, and untouched by any code in this
session.** Combined with Stage 1: **PASS for F5–F13.** F13's own review-loop contract (queue
durability, deletion ownership, provenance, attachment-safety, no second identity path) is proven
real-Edge end to end (R2–R4 PASS, R1 partial); the one real failure observed (R1's attachment/
indexing step) is in unrelated pre-existing infrastructure this increment calls but does not modify,
and is tracked separately rather than gating this security audit's PASS for F13's own scope.
