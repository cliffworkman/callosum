# Increment 445 — local exact-snapshot critical reading for WIP

## Outcome

Backlog #48's WIP Critique backbone is complete. With an unpublished manuscript active, an author can open
**Synthesize → Critique**, explicitly start a local read of the registered primary-file checkpoint, inspect current
method coverage and bounded claims, and follow any locally surfaced contrasting Library passage to its exact paper,
attachment, and page.

This is a skeptical reading aid, never a manuscript score, defect finding, correctness decision, or author judgment.
An empty/no-model/no-contrast state remains explicit and never becomes a clean bill of health.

## Architecture

- `POST /wip/manuscripts/{id}/critical-read` prepares the exact primary-file identity synchronously, reuses an active
  job for that manuscript, then runs through a dedicated `wip_critical_review_jobs` store. Polling is local-only at
  `GET /wip/critical-read/{job_id}`. Immediately before persistence it re-resolves the current registered primary
  file and requires the same file/whole/extracted hashes; a mid-job change produces a fixed retry state and no run.
- Shared critical-review domain code now supports a detailed bounded search report, block-based WIP claim extraction,
  matching-model article-fulltext corpus selection, and paper-title/attachment source resolution. Existing paper
  critical reading delegates to the same search core without changing its API.
- At most 12 claim sentences are embedded as transient queries; each searches at most five server-selected eligible
  embeddings. Only local-NLI contrast ≥0.55 is retained, one best passage per claim.
- `wip_critical_review_repo.py` stores one version-1 exact-snapshot receipt in generic `tool_runs` / `wip_tool_runs`.
  It composes only same-hash statcheck/transparency/LMM/Bayesian/meta-analysis receipts. It writes no WIP finding.
- Status maps the separate job to **Local AI**, Synthesize → Critique, and a typed manuscript id only. The client can
  reopen that WIP without Status ever seeing the job result.
- The frontend branches on manuscript context, preserves the last receipt after recoverable failure, shows exact
  claim/method/retrieval/model coverage, and opens paired Library evidence at the stored attachment/page.
- No migration, new table, dependency, outbox, paper-row shim, persisted draft embedding, or provider path exists.

## Privacy, security, and principles

The Principles gate aligns with evidence-first inspection, bounded disagreement, silence-not-certificate, and
human judgment. The declined implementation would infer a bibliography, index unpublished text as a Library paper,
reuse stale method results, persist draft vectors, or label model contrast as a flaw.

Only the explicitly selected registered primary file is read. Model/version/normalization, live-paper state, chunk
target, and canonical article-fulltext role constrain the Library corpus; returned vector hits are rechecked against
the allowlist. Query vectors are never stored. No provider, network client, secret, telemetry, device id, external
request, automatic run, retry loop, or arbitrary path exists. Unexpected errors and Status output contain no draft,
passage, local path, model exception, or result body. The completed audit is
`.claude/security-audits/2026-08-03_wip-critical-read.md`.

## Experience pass

Persona: an author doing a skeptical pre-submission read without disclosing unpublished prose. The WIP context makes
the local-only scope explicit, the action is deliberate, current vs unavailable method coverage is legible, paired
evidence is one click from the other Library source, and model provenance/limits sit beside the result. Missing corpus
or local model remains useful, truthful state. The prior receipt survives failure; a rerun control is available; the
provider option is replaced by a concrete future-consent explanation. The assembled desktop and 375 px paths fit.

## Verification

- Initial WIP/domain/Status suite: **40 passed in 75.67 s**. After adding the out-of-scope-vector and mid-job source-
  change regressions plus documentation/build changes, the final focused WIP/paper-Critique/Status/provenance/
  frontend aggregate passed **110 tests in 96.36 s**.
- Frontend assembly after rebuild: **64 passed in 10.64 s**.
- Focused Chromium WIP checklist + Critique route: **1 passed, 10 deselected in 52.41 s**. Earlier iterations exposed
  one case-sensitive rendered-label assertion and an async launch-rescan race in the test; the final bounded test
  confirms the real job through the API before inspecting its UI receipt.
- Frontend rebuild: `uv run python tools/build_frontend.py` → **20,510 lines / 2,092,963 bytes**.
- Full root suite after the final source-identity race guard: `uv run pytest -n auto -q` →
  **1853 passed, 1 skipped in 817.88 s**. The earlier pre-guard full pass also succeeded with 1852 passed / 1 skipped.
- Final full opt-in Chromium suite after the source-identity guard: **11 passed in 216.65 s**. The earlier full
  pre-guard browser pass also succeeded with 11 passed in 194.05 s.
- Full Ruff lint passed; full format check reported **632 files already formatted**.
- Strict QA surface map: **359/359 API** and **1593/1593 frontend** surfaces covered. Its first run correctly found
  the router-local POST alias missing from Route 75's machine-readable claim; the documented route then made it green.
- Line budget: **469/469 application source files ≤ 600 lines**. `40_app.jsx` remains exactly 600 lines;
  `wip_critical_review.py` and `wip_critical_review_repo.py` are below the cap. Bandit's baseline-ratcheted scan passed.
- Migration suite: **5 passed in 14.35 s**. `uv lock --check` resolved **161 packages** without drift.
- Runtime `pip-audit -r requirements.txt --strict`: **no known vulnerabilities**. The first parallel audit attempt
  received a transient invalid PyPI content type for scikit-learn; the clean retry completed successfully. The dev
  audit reports only the documented accepted `pytest 8.4.2 / PYSEC-2026-1845` item fixed in pytest 9.0.3, outside
  the current `<9` band.
- `git diff --check` passed. The credential-pattern scan matched only the documented example/fake Slack webhook
  values in `feedback_relay/example.env` and `tests/test_feedback_*`; the new WIP critical-read files import no
  network/provider client and contain no credential. `gitleaks` was unavailable and is not claimed as run.
- Staged pre-commit gate passed: whitespace/EOF/conflict/large-file hygiene, Ruff format/lint, line budget, and
  Bandit. Its first run removed trailing spaces from the new audit header; the cleanup was restaged and every hook
  passed on rerun. The four pre-existing untracked handoff/video files remained untouched and unstaged.

## Scope left open

Backlog #48 now retains only the feasible explicitly-linked WIP Meta-Reference slice. Provider/LLM WIP Critique,
inferred draft bibliography/citation context, persistent draft embeddings, adjudication, and Slack relay activation
remain separate. Inc 446 will use only user-confirmed WIP ↔ Library reference links and will not pretend an
unpublished manuscript has an indexed incoming-citation graph.

## Rollback

Remove the WIP critical-read router/store, shared WIP-specific domain helpers, job/status/UI branch, tests, and
documentation, then rebuild `callosum-app.html`. Generic WIP tables and Library-paper critical reading require no
data rollback.
