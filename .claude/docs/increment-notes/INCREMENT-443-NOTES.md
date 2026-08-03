# Increment 443 — WIP Bayesian reporting audit

## Outcome

Backlog #48's third Checklists integration is complete. An author can explicitly recompute supported inline default
Bayes factors and audit prior/convergence/sensitivity reporting in the registered primary WIP manuscript, then inspect
the same exact-snapshot receipt in the manuscript's **Checks** tab and **Methods → Checklists → Bayesian statistics**.

The combined result remains a review aid, not a correctness judgment. Each default-prior mismatch,
`not-found`/`coherence-flag` checklist row, and conservative advisory becomes its own reviewable `info` candidate.
Reproduced, present, and not-applicable rows remain in the receipt without becoming findings. If the Bayesian text
gate does not trigger, Callosum records that no checklist was applied, creates no findings, and denies that this proves
the manuscript has no Bayesian analysis.

## Architecture

- `POST /wip/manuscripts/{id}/checks/bayes` reuses the local-only WIP checks router, registered-primary content
  identity, exact snapshot recorder, generic `tool_runs` / `wip_tool_runs` / `wip_findings`, and existing pure
  `run_bayes` + `audit_completeness` functions.
- `BAYES_VERSION = "1"` makes the detector version explicit. The new narrow `wip_bayes_repo.py` persistence adapter
  keeps the shared WIP repository under the 600-line cap while mapping Bayesian-specific results into existing tables.
- The receipt stores the exact file/snapshot/hash, Callosum/tool versions, JZS prior scale, correlation-prior kappa,
  log10 tolerance, every recomputation, every checklist row, every advisory, and fixed coverage.
- Candidate mapping is method-specific and conservative: mismatch, checklist prompt, and advisory rows are separate
  `info` candidates. The gate prevents a bare false match from creating WIP review state outside Bayesian context.
- PDF evidence retains real page/region precision. Non-PDF synthetic page 1 is cleared before persistence.
- `WipBayesResult` reuses the existing Bayes recomputation/checklist/advisory renderers inside the shared
  `WipChecklistSection`. The Library batch, paper audit, filters, paper findings, and lineage credit are unchanged.
- No schema change, table, dependency, provider abstraction, result queue, paper-row shim, or migration was needed.

## Principles, privacy, and security

The Principles gate touched 1/2/3/4/5/6/7/8/10 and most closely matches worked example 3. The easier misaligned path
would label a BF mismatch “wrong,” convert every detector miss into a defect, or collapse them into a Bayesian-quality
score. The aligned implementation retains evidence and fixed assumptions, calls every row a review prompt, states
coverage/silence limits, and leaves judgment with the author.

Only the registered local primary file is read after explicit action. No HTTP client, provider, LLM, telemetry,
clipboard, secret, environment value, device identifier, arbitrary user path, or automatic retry is involved. Errors
and activity failures use bounded/fixed language. See
`.claude/security-audits/2026-08-03_wip-bayesian-reporting.md` for the completed PASS review.

## Experience pass

Persona: a deadline author checking Bayesian reporting before submission. A higher-priority collaboration constraint
prevented dispatching a subagent, so the persona path was driven directly through the assembled Chromium app. The
author can discover the audit beside the other Checklists tools, see the default assumptions and exact matched BF,
open the registered source, review each distinct prompt in Checks, disposition it, edit, and rerun. Both desktop and
375 px layouts fit; the path produced no console/page errors or outbound request. No blocked next action or cheap UX
follow-up remained.

## Verification

- Baseline focused suite before implementation:
  `uv run pytest tests/test_bayes.py tests/test_wip_checks.py tests/test_frontend_assembly.py -q` →
  **105 passed in 58.55 s**.
- Final focused Bayesian/WIP/frontend suite after rebuilding the assembled artifact →
  **108 passed in 63.63 s**. The first post-frontend-edit run correctly reported only the stale built artifact;
  rebuilding resolved it.
- Backend-focused post-module-split suite: **45 passed in 60.96 s**.
- Focused assembled Chromium WIP checklist route: **1 passed, 10 deselected in 43.21 s**.
- Full root suite: `uv run pytest -n auto -q` with offline model flags → **1840 passed, 1 skipped in 774.50 s**.
- Full opt-in Chromium suite: **11 passed in 190.48 s**.
- Frontend rebuild: `uv run python tools/build_frontend.py` → **20,396 lines / 2,079,928 bytes**.
- Full Ruff lint passed; full format check reported **628 files already formatted** after formatting the changed files.
- Strict QA surface map: **357/357 API** and **1585/1585 frontend** surfaces covered.
- Line budget: **466/466 application source files ≤ 600 lines**. The first Windows run hit only console cp1252's
  inability to print `≤`; rerunning with `PYTHONUTF8=1` passed. `wip_checks_repo.py` is 420 lines and the new
  `wip_bayes_repo.py` is 203.
- Bandit's baseline-ratcheted runtime scan passed. Migration suite: **5 passed in 13.13 s**. `uv lock --check`
  resolved **161 packages** without drift.
- Runtime `pip-audit -r requirements.txt --strict`: **no known vulnerabilities**. The dev audit reports only the
  documented accepted `pytest 8.4.2 / PYSEC-2026-1845` item fixed in pytest 9.0.3, outside the current `<9` band.
- `git diff --check` passed. The targeted credential/private-key/webhook scan found only documentation sentences
  stating that no secret exists; no credential-shaped value or implementation network client matched. The complete
  staged pre-commit gate passed after its first run mechanically removed two Markdown hard-break trailing spaces:
  whitespace/EOF/conflict/large-file hygiene, Ruff format/lint, line budget, and Bandit. The staged allowlist contains
  only Increment 443's 17 code/test/documentation files; four pre-existing untracked handoff/video files remain
  untouched. `gitleaks` was unavailable and is not claimed as run.

## Scope left open

Backlog #48 remains open for WIP meta-analysis reporting, local grounded Critique, and the feasible explicitly-linked
portion of Meta-Reference. Provider/LLM WIP Critique, inferred draft bibliography/citation context, and Slack relay
activation remain deliberately separate. This increment does not fit a Bayesian model, inspect data/tables, infer an
author's actual prior, assign objective severity, or change Library-paper Bayesian persistence.

## Rollback

Remove the Bayesian WIP route, persistence adapter, UI branches, tests, and documentation, then rebuild
`callosum-app.html`. Existing generic WIP tables and Library Bayesian behavior require no schema or user-data rollback.
