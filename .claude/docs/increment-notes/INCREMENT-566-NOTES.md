# Increment 566 Notes — macOS Local AI and first-class researcher identity

## User-reported regressions

An early macOS user saw Local AI as unavailable and could not establish My Publications identity by surname,
full name, or ORCID. The investigation used the concrete regression identity Vasiliki Meletaki,
ORCID `0000-0002-3521-7707`, OpenAlex `A5085857730`.

## Root causes and fixes

- Local AI was not suffering an Ollama/PATH/race issue: production setup was explicitly compiled as Windows-only,
  despite Callosum shipping an Apple Silicon app. The managed installer now supports the exact official llama.cpp
  b10516 macOS arm64 archive, safely extracts an allowlisted flat runtime bundle, verifies its launcher and bundle
  manifest, and otherwise preserves the existing managed lifecycle/security model.
- The identity UI conflated a saved researcher identity with successful OpenAlex enrichment. A valid ORCID is now
  normalized, check-digit validated, and persisted as the canonical Callosum identity independently of OpenAlex.
- OpenAlex resolution now records machine-readable matched/not-found/unavailable/rejected linkage states, verifies
  returned ORCID equality, searches up to ten name candidates, tolerates ordinary Unicode/punctuation variation,
  and rejects ambiguous surnames. An ambiguous weak name no longer prevents a later exact name variant.
- The Settings refresh previously continued after a failed profile save, so it could query stale/blank identity
  while the typed values remained visible. Save now returns success and refresh stops on failure.
- Settings and dashboard refresh failures no longer disappear into generic copy or console-only state. Both flows,
  and Local AI setup/status, expose actionable one-click Slack diagnostics with stable codes and sanitized details.

## Concrete Vasiliki result

At investigation time, live OpenAlex exact-ORCID, author-ID, full-name, and surname requests all returned
`A5085857730`; the current pre-change backend also resolved the live exact ORCID. The exact historical rejection
point cannot be recovered because the old UI discarded it. The regression fixture now proves that the ORCID URL
and bare forms establish identity, the known OpenAlex record links, provider no-result/timeout do not undo
identity, a full-name variant survives an ambiguous surname, and surname-only ambiguity fails safely.

## Validation before remote macOS acceptance

- Focused My Publications/identity/API suite: 63 passed.
- Frontend assembly plus focused identity suite: 149 passed.
- Rust suite: 37 passed, 5 opt-in live tests ignored.
- Rust `cargo check` and formatting: passed.
- Ruff format/check on touched Python: passed.
- 600-line budget: passed after separating identity/enrichment from axis persistence.
- Git diff whitespace check: passed.
- Full serial Python suite: **2763 passed, 3 skipped** in 1306.64 seconds.
- The `pre-commit` executable/module is absent from the active Anaconda environment; all configured hooks were
  run directly instead (including YAML/TOML syntax, Ruff, line budget, Bandit, Tach, whitespace, merge-marker,
  and added-file-size checks).

The updated macOS workflow adds a release-blocking live managed-install/provider-contract/cleanup acceptance test.
Its result will be recorded before the release version/tag is created.
