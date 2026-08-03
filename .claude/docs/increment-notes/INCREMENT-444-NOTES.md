# Increment 444 — WIP meta-analysis reporting audit

## Outcome

Backlog #48's Checklists group is complete. An author can explicitly audit the registered primary WIP manuscript for
the existing seven meta-analysis reporting items, then inspect the same exact-snapshot receipt in the manuscript's
**Checks** tab and **Methods → Checklists → Meta-analysis reporting**.

The result remains a reading and review aid, not a correctness judgment. Each `not-found` row becomes its own
reviewable `info` candidate. Present and not-applicable rows remain in the receipt without becoming findings. If the
meta-analysis text gate does not trigger, Callosum records that no checklist was applied, creates no findings, and
denies that this proves the manuscript contains no meta-analysis.

## Architecture

- `POST /wip/manuscripts/{id}/checks/meta-analysis` reuses the local-only WIP checks router, registered-primary
  content identity, exact snapshot recorder, generic `tool_runs` / `wip_tool_runs` / `wip_findings`, and existing
  pure `audit_meta_analysis` function.
- `META_ANALYSIS_VERSION = "1"` makes the detector version explicit. The narrow
  `wip_meta_analysis_repo.py` adapter maps method-specific statuses into existing generic WIP provenance tables.
- The receipt stores exact file/snapshot/hash, Callosum/tool versions, all seven checks, counts, and fixed coverage.
- Candidate mapping is conservative: one separate `info` candidate per gate-on `not-found` row. Present,
  not-applicable, and every gate-off state creates no finding.
- PDF evidence retains real page/region precision. Non-PDF synthetic page 1 is cleared before persistence.
- `WipMetaAnalysisResult` reuses `MetaChecklist` inside the shared `WipChecklistSection`. Library batch/paper audits,
  filter, paper findings, and lineage credit are unchanged.
- No schema change, table, dependency, provider abstraction, result queue, paper-row shim, or migration was needed.

## Principles, privacy, and security

The Principles gate touched 1/2/3/4/5/6/7/8/10 and most closely matches worked example 3. A misaligned implementation
would call a detector miss “missing,” infer methodological quality, or collapse the checks into a completeness score.
This implementation retains every status and its basis, calls misses review prompts, states tables/figures and gate
limits, and leaves judgment with the author.

Only the registered local primary file is read after explicit action. No HTTP client, provider, LLM, telemetry,
clipboard, secret, environment value, device identifier, arbitrary user path, or automatic retry is involved. See
`.claude/security-audits/2026-08-03_wip-meta-analysis-reporting.md` for the completed PASS review.

## Experience pass

Persona: a deadline author checking synthesis reporting before submission. A higher-priority collaboration constraint
prevented dispatching a subagent, so the persona path was driven directly through the assembled Chromium app. The
author can discover the audit beside the other Checklists tools, inspect all seven statuses and evidence, open the
registered source, disposition each separate prompt in Checks, edit, and rerun. Both desktop and 375 px layouts fit;
the path produced no console/page errors or outbound request. No blocked next action or cheap UX follow-up remained.

## Verification

- Focused meta-analysis/WIP/frontend suite after rebuilding the assembled artifact: **97 passed in 81.37 s**. The
  first post-edit run correctly reported only the stale built artifact plus one import-order lint item; both were
  corrected before the passing rerun.
- Focused assembled Chromium WIP checklist route: **1 passed, 10 deselected in 47.51 s**. The first run exposed only
  a copy/assertion mismatch; visible copy was strengthened to say detector silence is “never proof of omission,” and
  the rerun passed.
- Frontend rebuild: `uv run python tools/build_frontend.py` → **20,438 lines / 2,083,177 bytes**.
- Full root suite: `uv run pytest -n auto -q` → **1843 passed, 1 skipped in 793.65 s**.
- Full opt-in Chromium suite: **11 passed in 195.48 s**.
- Full Ruff lint passed; full format check reported **629 files already formatted** after Ruff mechanically formatted
  two changed test files.
- Strict QA surface map: **358/358 API** and **1587/1587 frontend** surfaces covered. Its first run correctly found
  the new route missing from Route 75's machine-readable claim; adding the already-documented route made it green.
- Line budget: **467/467 application source files ≤ 600 lines**. `wip_checks.py` is 281 lines and the new
  `wip_meta_analysis_repo.py` is 112. Bandit's baseline-ratcheted runtime scan passed.
- Migration suite: **5 passed in 14.98 s**. `uv lock --check` resolved **161 packages** without drift.
- Runtime `pip-audit -r requirements.txt --strict`: **no known vulnerabilities**. The dev audit reports only the
  documented accepted `pytest 8.4.2 / PYSEC-2026-1845` item fixed in pytest 9.0.3, outside the current `<9` band.
- `git diff --check` passed. The credential-pattern scan matched only pre-existing explicitly fake Slack webhook
  fixtures under `tests/test_feedback_*`; no real credential or new network client was found. `gitleaks` was
  unavailable and is not claimed as run.
- The staged pre-commit gate passed: whitespace/EOF/conflict/large-file hygiene, Ruff format/lint, line budget, and
  Bandit. An initial all-files invocation touched only legacy trailing-whitespace/EOF issues outside this increment;
  those hook-created changes were removed, the 17-file allowlist was restored, and the staged-only rerun passed.
  Four pre-existing untracked handoff/video files remain untouched.

## Scope left open

Backlog #48 remains open for local grounded Critique and the feasible explicitly-linked portion of Meta-Reference.
Provider/LLM WIP Critique, inferred draft bibliography/citation context, and Slack relay activation remain separate.
This increment does not pool studies, calculate an effect, inspect tables/figures completely, adjudicate reporting,
assign objective severity, or change Library-paper meta-analysis persistence.

## Rollback

Remove the meta-analysis WIP route, persistence adapter, UI branches, tests, and documentation, then rebuild
`callosum-app.html`. Existing generic WIP tables and Library meta-analysis behavior need no data rollback.
