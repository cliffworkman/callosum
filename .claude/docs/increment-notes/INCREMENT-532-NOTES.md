# Increment 532 — packaged Word HTTPS companion (backlog #33/#34 phase 2)

**Date:** 2026-08-29
**Scope:** opt-in Windows/macOS certificate lifecycle plus a Tauri-owned fixed-port HTTPS companion for the
existing desktop Word add-in. No Word document semantics, tunnel behavior, provider behavior, or normal app
startup path changes while disabled.

## Product outcome

Packaged-app users no longer need Node, `office-addin-dev-certs`, or a terminal to make desktop Word reach
Callosum. Settings now offers **Enable Word Support**. The explicit action generates and trusts one local leaf
certificate for the current OS account; Tauri starts a second Uvicorn child at `127.0.0.1:8443` against the same
DB/library/version configuration as the main backend. Disable stops the child first, removes trust and files,
then clears the opt-in. Source-checkout users retain the existing developer-certificate workflow, and Word on
the web remains the separate Remote-access/tunnel workflow.

Sideloading the manifest remains a one-time Word operation. Per the user's instruction, actual Word/Office.js
verification is deferred to the consolidated manual checklist at the end of the wider adapter arc; this
increment does not claim it.

## Architecture

- `app/backend/word_https_lifecycle.py` owns certificate generation, current-user trust-store mutation,
  verification, persistence, and privacy-safe status. The certificate is an RSA-2048 self-signed end entity,
  valid for `localhost` and literal `127.0.0.1`, with server-auth use, `ca=false`, and no certificate-signing use.
- Windows uses fixed PowerShell scripts with values in a child-only environment (never interpolated command
  text). `Import-Certificate` targets `Cert:\CurrentUser\Root`; trust lookup/removal uses the certificate
  thumbprint. Private-key DACL replacement is fail-closed and verifies exactly one protected current-user rule.
  The child pins the inbox Windows PowerShell module root so a PowerShell 7 parent cannot poison Windows
  PowerShell 5 module loading—an issue discovered by the live smoke.
- macOS uses `security add-trusted-cert` against the login keychain without `-d`, and
  `remove-trusted-cert`. It is statically tested but awaits macOS hardware QA.
- `app/backend/api/routers/word_https.py` exposes status/enable/disable. Mutations require literal loopback,
  reject forwarding headers/read-only mode, and require the non-safelisted
  `X-Callosum-Local-Action: settings-ui-v1` header. This closes simple-form cross-origin request forgery;
  the header is proof of the Callosum Settings request path, not a secret.
- Tauri is the sole companion process owner. It uses direct argv, fixed `127.0.0.1:8443`, the exact generated
  cert/key, the main backend's DB/library/version, and a child-only `CALLOSUM_DISABLE_REMOTE_ACCESS=1`. Readiness
  pins the generated leaf in reqwest rather than accepting invalid TLS. Windows Job Object / Unix process-group
  cleanup reuses the main backend's process-tree contract. An atomic start owner prevents launch/UI races.
- Tauri and Python derive certificate storage from the same settings location, including the existing
  `CALLOSUM_SETTINGS_PATH` test/developer override. The status API returns no path, token, or key material.

## Security and failure semantics

Enable is persisted only after the OS trust store verifies the exact generated certificate. Disable stops the
child first in the packaged UI; Python then removes and rechecks trust before deleting the key/certificate and
clearing the opt-in. Failure leaves a diagnosable retry state rather than claiming cleanup. Normal users see no
new listener until they explicitly enable it. The companion has no cloud fallback and does not alter the main
backend's Remote-access setting.

The detailed threat/disposition record is
`.claude/security-audits/2026-08-29_tauri-word-https.md` (**PASS**, with honest manual-platform limits).

## Experience review

The first Settings draft used one boolean busy flag for both lifecycle and folder actions, which could label
the folder button “Opening…” while certificate work was running. It also based Enable/Disable on fully healthy
state, making a persisted-but-broken opt-in impossible to clean up. The final UI uses action-specific busy state,
disables lifecycle mutation until status loads, and uses the persisted opt-in to preserve the Disable/recovery
path. Disable stops the companion before removing trust. The popover stays compact and distinguishes packaged,
source/developer, and Word-web workflows without exposing certificate paths.

## Live isolated smoke

On the Windows development host, without installing any trust-store entry, the real lifecycle generated a leaf
and owner-only key; real Uvicorn started with that pair at literal `127.0.0.1:8443`; an HTTPS `/health` request
validated using the exact leaf; and termination left no listening socket. The Windows ACL was then independently
observed as protected with one current-user FullControl rule. The live pass found both the missing PowerShell
parameter binding and inherited PowerShell-7 module-path problems; both were fixed and the smoke rerun cleanly.
Its temporary script was removed and its `.local` directory was moved to the Recycle Bin.

## Verification

- Focused Word lifecycle/frontend/Word/access suite: **118 passed**. Earlier lifecycle/frontend-only final
  isolation: **94 passed**.
- Full Python suite: **2584 passed, 3 skipped** in 1261.80s (1267.48s harness wall time), normal
  `pytest -n auto -q --tb=short` mode, no retries.
- Rust: touched-file rustfmt clean; `cargo check` clean; strict all-target Clippy clean; complete serial suite
  **27 passed, 3 ignored**. The parallel suite twice reproduced the pre-existing managed-local readiness-test
  race; that exact test passed twice alone, and the complete serial suite passed. No new Word test failed.
- Bandit, Tach, 571-file line budget, QA surface map (435/435 gated API surfaces), and website review: clean.
  Targeted pre-commit, secret/private-path scan, and `git diff --check`: recorded in the final commit receipt.
- Actual current-user trust installation/removal, macOS trust behavior, and Word-host behavior: **not yet
  live-verified**; carry into the consolidated manual adapter checklist.

## Revert

Revert the increment commit. No schema migration is involved. Existing source/dev Word HTTPS and Word-web
flows remain independent of this additive packaged-app opt-in.
