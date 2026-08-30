# Increment 534 — packaged Word closure: protected trust UI + explicit Tauri ACL

**Date:** 2026-08-29
**Scope:** close two defects found during the final Word/Docs parity-arc audit and index the already-accumulated
manual editor-host work. No citation/document semantics, provider/model behavior, tunnel behavior, schema,
AppSource distribution, or Mendeley/EndNote conversion policy changes.

## Defects closed

1. **Windows trust install/removal could not complete.** Increment 532 correctly chose fixed-script
   `Import-Certificate` over `certutil`, targeted `Cert:\CurrentUser\Root`, verified the exact thumbprint, and
   failed closed. The first real store mutation in this increment proved that `-NonInteractive` prevents the
   protected-Root confirmation and returns `UI is not allowed in this operation`. `-Confirm:$false` does not
   bypass that OS boundary, and a .NET `X509Store.Add` experiment blocks on the same confirmation. A
   `CurrentUser\TrustedPeople` experiment imported silently but did not make Windows' TLS stack trust the
   self-signed server leaf, so it was rejected rather than weakening the validation claim.
2. **Word Tauri commands lacked explicit ACL grants.** `start_word_https_companion` and
   `stop_word_https_companion` were registered and used by packaged Settings, but Increment 532 omitted their
   named `permissions/default.toml` entries and `capabilities/default.json` grants. That violated the explicit
   two-axis invariant established by Increments 421/423 even where current Tauri default behavior happened to
   permit registered commands.

## Fix

Only exact Windows certificate add/remove omits PowerShell's `-NonInteractive` flag, allowing the normal
protected-store confirmation. Both operations have a 120-second bound. Decline, timeout, or OS failure returns a
privacy-safe `WordHttpsError`; enable still publishes state only after exact trust verification, while disable
still preserves trust/files/opt-in for retry unless removal is verified. ACL mutation, lookup, and every other
PowerShell operation remain noninteractive with child-environment argument passing.

Word companion start/stop now each have one named permission, both are included in the default permission set,
and both are granted to the existing `main`/`splash` capability under its existing literal-loopback remote URL
scope. A parsed TOML/JSON regression test pins both axes for Word and Quick Tunnel commands.

The final affected serial run also exposed an older test-harness leak: `test_run_https` deleted an absent
`CALLOSUM_DISABLE_REMOTE_ACCESS` key before production `main()` assigned it directly, so pytest had no prior value
to restore and later tunnel tests correctly failed closed. The test now seeds a sentinel through `monkeypatch`,
which restores the original environment after the direct production mutation. The exact minimal reproducer and
the original 181-test serial order both pass.

## Live Windows trust receipt

Using an isolated settings directory and fresh random localhost-only leaf:

- clean precondition: certificate not trusted;
- enable displayed **Security Warning**; no `consent.exe` process existed;
- after confirmation, exact-thumbprint CurrentUser Root lookup returned trusted and enabled state was true;
- disable displayed **Root Certificate Store** confirmation; again no `consent.exe` process existed;
- after confirmation, exact trust lookup was false, enabled state was false, and certificate/key files were gone;
- total clean lifecycle wall time, including deliberate dialog observation/confirmation: 50.294s;
- the isolated directory was moved to the Recycle Bin after verifying it contained only the 35-byte settings
  receipt and empty Word directory.

The empirical result is therefore: Windows requires ordinary certificate confirmations for protected Root
add/remove, but not a UAC/elevation prompt. Actual Word/Office.js behavior is still not agent-driven and remains
in the consolidated manual pass. macOS trust behavior also remains hardware QA.

## Consolidated manual pass

Route 34 now opens with a compact index dividing the remaining host work into Writer note integrity, Writer
links/organization, Word desktop/web parity features, Writer metadata/conversion, and Route 35 packaged Word
connectivity. This changes no test criteria; it makes the eventual one-sitting maintainer pass executable.

## Verification

- Live Windows CurrentUser Root lifecycle: enable trusted, disable untrusted/deleted; no `consent.exe`; 50.294s.
- Minimal environment-leak reproducer: **4 passed**.
- Full affected serial order: **181 passed** in 194.81s.
- Fresh full Python suite: **2590 passed, 3 skipped** in 1808.00s (30m08s). The previously reported 40-minute
  harness timeout and isolated `test_summary_overview.py` collection-order issue did not reproduce.
- Rust: `cargo check` and `cargo clippy --all-targets --all-features -- -D warnings` passed; serial `cargo test`
  **29 passed, 4 ignored**. `cargo fmt --check` still reports only the pre-existing untouched `src/updater.rs`
  formatting drift; this increment changes no Rust source and deliberately does not absorb that unrelated diff.
- Ruff format/check, Bandit, Tach, 571-file line budget, QA surface map (435/435 gated API surfaces), demo
  experience coverage, reviewed/refreshed website coverage, and frontend assembly all passed.
- Changed-file pre-commit, `git diff --check`, and added-line secret/private-path scans passed. An exploratory
  all-files pre-commit run found and auto-fixed unrelated historical whitespace/EOF drift; every such drive-by
  edit was restored exactly and is absent from this increment.
- Remote CI: recorded after push.
- No actual Word or LibreOffice host behavior is claimed live-verified here.

## Revert

Revert this increment commit. The old Windows path remains fail-closed but unusable for protected-Root mutation;
the explicit Word command grants and manual-route index are removed. No migration or persisted application data
is involved.
