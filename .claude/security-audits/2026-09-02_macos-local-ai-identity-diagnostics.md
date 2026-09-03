# Security Audit: macOS Local AI and identity diagnostics

Date: 2026-09-02
Status: CONDITIONAL PASS — live Apple Silicon acceptance is release-blocking

## Scope

Extend the existing one-model managed Local AI Preview from Windows x64 to the already-shipped Apple Silicon
macOS application, make ORCID a first-class local identity independent of OpenAlex enrichment, and provide
privacy-safe copy/paste diagnostics for both affected onboarding flows.

## Invariants preserved

- The macOS installer accepts one immutable official llama.cpp b10516 arm64 archive and the existing immutable
  publisher-owned Qwen artifact. Host allowlisting, exact byte counts, SHA-256 verification, partial paths, and
  atomic promotion remain mandatory.
- Tar extraction accepts one pinned archive root and only `llama-server` plus adjacent `.dylib` runtime files.
  Nested/traversal paths, non-file/non-symlink entries, unallowlisted link targets, and links resolving outside the
  private runtime root fail closed.
- The runtime binds only to literal `127.0.0.1`, uses the existing random per-launch bearer token outside argv,
  publishes no descriptor before authenticated readiness and execution observation match, and retains Unix
  process-group cleanup.
- Selecting Local AI still cannot trigger cloud fallback.
- An ORCID is validated locally with ISO 7064 MOD 11-2, canonicalized, and saved before any OpenAlex request.
  Provider absence, timeout, or no-result cannot invalidate that identity.
- Copyable diagnostics are allowlisted structured fields. They contain no credentials, raw provider exception,
  full ORCID, scholarly text, or filesystem path.

## New egress and privacy surface

There is no new host or data class. Apple Silicon setup uses the same narrow runtime/model download hosts as the
Windows setup, with an additional immutable official GitHub release artifact. OpenAlex continues to receive only
the public name/ORCID identifiers the user explicitly supplies for publication enrichment. Diagnostic copying is
local and user-initiated; Callosum does not transmit the report.

## Validation boundary

Windows compilation, complete Rust tests (38 passed, 5 opt-in live tests ignored), the complete Python suite
(2763 passed, 3 skipped), focused identity/API/frontend tests, Ruff, and the line budget pass
locally. The macOS workflow now blocks on a live test that downloads and verifies both artifacts, starts the
managed runtime, exercises Overview/primary-synthesis/Help provider contracts without cloud credentials, shuts
down, and proves the descriptor/token were removed. This audit must be promoted to PASS only after that Apple
Silicon job succeeds; no release tag may be created before then.
