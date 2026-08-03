# Increment 442 — WIP mixed-model reporting audit

## Outcome

Backlog #48's second Checklists integration is complete. An author can explicitly audit the registered primary WIP
manuscript for the existing seven mixed-model reporting prompts, then inspect the same exact-snapshot receipt in the
manuscript's **Checks** tab and **Methods → Checklists → Mixed-model reporting**.

The result is a review aid, not a manuscript judgment. Each detector `not-found` row becomes one reviewable
`info`-level candidate; present and not-applicable rows remain only in the full receipt. If the initial text gate does
not detect mixed-model language, Callosum records that no checklist was applied, creates no findings, and explicitly
denies that this proves no mixed model is present.

## Architecture

- `POST /wip/manuscripts/{id}/checks/lmm` reuses the local-only WIP checks router, primary-file content identity,
  snapshot recorder, generic `tool_runs` / `wip_tool_runs` / `wip_findings`, and existing pure `audit_lmm` detector.
- `LMM_VERSION = "1"` makes the previously implicit detector version explicit. `store_lmm_run` persists the version,
  exact file/snapshot/hash, fixed coverage, gate state, counts, and all seven serialized rows.
- The persistence mapping is deliberately method-specific: one open candidate for each `not-found` row, no finding
  for present or n/a, and no findings when the gate is off. Candidate dispositions use the existing WIP review path.
- PDF evidence retains real page/region precision; non-PDF synthetic page 1 is cleared.
- The frontend factors the inc-441 Transparency wrapper into one shared `WipChecklistSection`, then supplies separate
  Transparency and LMM labels/result renderers. The Library-paper LMM batch, cached findings, and lineage credit are
  unchanged.
- No database migration, new table, provider abstraction, queue, dependency, or result cache was needed.

## Principles, privacy, and security

The design follows Principles 1/2/5/6/7/8 and the statcheck-like worked example: inspectable evidence and bounded
coverage feed a human decision; silence is never a certificate. The tempting misaligned version—convert every miss
into an objective deficiency or aggregate score—was rejected. Candidates are low-weight review prompts, no author or
analysis accusation is made, and the detector never runs a model.

Only the registered local primary file is read after explicit action. Text and results remain local; no HTTP, AI,
registry, telemetry, secret, arbitrary path, or device identifier is involved. Activity failures use fixed messages.
See `.claude/security-audits/2026-08-03_wip-lmm-reporting.md` for the completed PASS review.

## Experience pass

Persona: a deadline author who used a linear mixed model and wants a pre-submission reporting reminder without
turning Callosum into an automated reviewer. The assembled Chromium path showed the run in both expected locations,
made unresolved prompts actionable in the WIP Checks history, kept the full seven-row receipt in Methods, named its
snapshot/coverage, provided a source action, and preserved the no-verdict/no-score boundary. The 375 px layout had no
document or tool-pane overflow. The natural next action is edit/open the primary source, disposition a prompt, and
rerun; no blocking experience issue remained.

## Verification

- Baseline focused suite before implementation: **91 passed in 63.55 s**.
- Final focused WIP/LMM/frontend suite after all negative-path assertions: **94 passed in 51.39 s**.
- Focused assembled Chromium WIP checklist route: **1 passed, 10 deselected in 35.14 s**.
- Root suite, deterministic four-worker filename partitions: A–C **398 passed in 270.14 s**, D–F **251 passed in
  100.07 s**, G–M **441 passed in 191.79 s**, N–S **585 passed in 404.06 s**, and T–Z **162 passed in 151.68 s** —
  **1837/1837 passed** in total.
- Full opt-in Chromium suite: **11 passed in 180.25 s**.
- Frontend rebuild: `uv run python tools/build_frontend.py` — **20,335 lines / 2,074,772 bytes**. (`npm run build`
  was attempted first but this repository intentionally defines no npm build alias; the documented Python builder
  succeeded.)
- Full Ruff lint passed; full format check reported **626 files already formatted**. Bandit's baseline-ratcheted
  runtime scan passed. The line budget reported **465/465 application source files** under 600 lines. `uv lock
  --check` resolved **161 packages** with no drift.
- Strict QA surface map: **356/356 API** and **1581/1581 frontend** surfaces covered. Its first run correctly failed
  on the missing machine-readable LMM endpoint token in route 75; adding both prefixed and router-relative forms made
  the final strict run pass.
- Runtime `pip-audit --strict`: **no known vulnerabilities**. The dev audit reports only the documented accepted
  `pytest 8.4.2 / PYSEC-2026-1845` item fixed in pytest 9.0.3.
- `git diff --check` passed. Targeted added-line credential/private-key/webhook patterns and production network-import
  patterns returned no matches. `gitleaks` was unavailable and is not claimed as run.
- The complete staged pre-commit gate passed: whitespace/EOF/conflict/large-file hygiene, Ruff format/lint, line
  budget, and Bandit.

## Scope left open

Backlog #48 remains open for two distinct WIP Checklists builds (Bayesian and meta-analysis), WIP Critique, and the
feasible portion of Meta-Reference. This increment does not run a mixed model, inspect data, infer objective severity,
change Library-paper LMM persistence, or add any model/provider path. Backlog #52 separately retains the Slack relay
activation runbook.

## Rollback

Remove the LMM WIP route/store/UI branches, tests, and documentation, then rebuild `callosum-app.html`. Existing
generic WIP data tables and Library LMM behavior require no schema or user-data rollback.
