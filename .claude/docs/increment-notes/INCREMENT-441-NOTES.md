# Increment 441 — WIP Transparency disclosure checks

## Outcome

Backlog #48's first Checklists integration is complete. A WIP author can explicitly run the existing deterministic
Transparency detector against the manuscript's registered primary file and inspect the same persisted result from
the WIP **Checks** tab or **Methods → Checklists → Transparency**. Every run is bound to an exact file/hash snapshot;
changed source makes the prior run visibly potentially stale.

This is disclosure detection, not a transparency grade. Positive quoted detections persist as non-reviewable FACTs.
`not-found` and `not-applicable` remain detector-coverage states in the run receipt and never become negative
findings, candidates, accusations, or a score.

## Architecture

- `POST /wip/manuscripts/{id}/checks/transparency` reuses the local-only WIP checks router, primary-file resolver,
  content-identity extraction, snapshot recorder, generic `tool_runs` / `wip_tool_runs`, and existing pure
  `detect_transparency` detector. No migration, dependency, provider, queue, or parallel persistence system was added.
- `store_transparency_run` records detector version 1, all seven structured statuses, coverage/caveats, exact
  snapshot/file/hash provenance, and positive evidence-backed `wip_findings(kind="fact")` rows.
- The findings repository now enforces the pre-existing epistemic boundary: only `candidate` findings can receive a
  review disposition. FACTs cannot be converted into review work by a direct PATCH.
- PDF detections retain honest page/region precision. Synthetic page 1 from non-paginated document extractors is
  cleared at the WIP persistence boundary.
- Both frontend entry points render the same `TransparencyChecklist`; manuscript context suppresses the Library
  paper registration-reference workflow and keeps registration discovery/acquisition out of WIP.

## Privacy and security

- The endpoint accepts only an integer manuscript id and no detector options, file path, payload structure,
  destination, provider, or URL. It inherits `require_local_wip`; remote/read-only calls are denied.
- Only the registered primary manuscript is read. Text, evidence, snapshots, and results remain local; there is no
  HTTP, LLM, registry, telemetry, retry, or background publication path.
- Failure activity records only a fixed tool message, not parser exceptions, manuscript content, or paths. Successful
  activity records counts/version/snapshot id, never the evidence body.
- The UI renders evidence as React text and opens only the existing manuscript/file-scoped local source action.
- Existing 256 MiB WIP primary-file and 32 MiB plain-text limits bound extraction. Fixed server-owned patterns return
  one bounded evidence snippet per category. The remaining risk is local CPU/memory cost for a complex maximum-size
  PDF, equivalent to existing WIP checkpoint/statcheck extraction.
- Full review: `.claude/security-audits/2026-08-02_wip-transparency.md` — PASS.

## Experience pass

A deadline author preparing a manuscript was driven through the fresh Chromium workflow using only visible controls:
open WIP, open Checklists, run Transparency, inspect the seven disclosure rows and caveat, open the source, then visit
the manuscript's Checks history. The result is discoverable in both natural locations, names the exact checkpoint,
shows the next action (open/edit source and check again), and never asks the author to interpret a number as quality.
The same path at 375 px had no document or tool-pane horizontal overflow. No blocking friction remained; external
source opening plus the visible PDF page/evidence quote is consistent with the current WIP source-navigation model.

## Verification

- Focused baseline before implementation: `uv run pytest tests/test_wip_checks.py tests/test_transparency.py
  tests/test_transparency_findings.py tests/test_frontend_assembly.py -q` — **87 passed in 37.05 s**.
- Final focused regression command over the same files — **91 passed in 55.89 s**.
- Root suite, deterministic four-worker filename partitions: A–C **398 passed**, D–F **251 passed**, G–M
  **441 passed**, N–S **585 passed**, T–Z **159 passed** — **1834/1834 passed** in total. After the final fixed failure-
  receipt hardening, the complete collection passed again with the same counts (278.10 s / 101.87 s / 195.37 s /
  382.64 s / 143.74 s respectively).
- Focused Chromium WIP workflow — **1 passed in 43.58 s**. The initial iteration exposed only a premature test
  assertion during the shared refresh and was corrected to wait for the persisted run.
- Full opt-in Chromium suite: two initial sequence runs reached **10 passed / 1 setup timeout** because the new test
  followed a server-busy feedback scenario; moving the independent WIP scenario before feedback removed that
  cross-test contention. Final `CALLOSUM_RUN_E2E=1 pytest tests/e2e -q` — **11 passed in 174.36 s**.
- Ruff focused format/check — **passed**; one test file was formatted and all six changed Python files lint clean.
- Frontend rebuild — **20,268 lines / 2,071,048 bytes**.
- Line budget — **465/465 application source files** within the 600-line cap.
- Strict QA surface map — **355/355 API** and **1579/1579 frontend** surfaces covered.
- Bandit baseline-ratcheted runtime scan — **passed**. `uv lock --check` — **161 packages current**. Runtime
  `pip-audit --strict` — **no known vulnerabilities**. Dev audit retains the documented, accepted
  `pytest 8.4.2 / PYSEC-2026-1845` finding fixed only in pytest 9.0.3.
- `git diff --check` passed. Targeted added-line secret patterns and production network-client searches returned no
  matches. `gitleaks` was unavailable and is not claimed as run. Unrelated pre-existing handoff/video files remained
  untouched and unstaged.

## Scope left open

Backlog #48 remains open for three separate Checklists builds (Bayesian, mixed-model, meta-analysis), WIP Critique,
and the feasible portion of Meta-Reference. They require their own evidence/coverage and persistence designs; they
were deliberately not bundled into this increment. Citation-context remains inapplicable to an unpublished WIP as
recorded in the backlog. Backlog #52 separately preserves the user-controlled Slack relay activation runbook.

## Rollback

Remove the transparency WIP route/store/UI branches/tests/docs and rebuild the frontend. Existing statcheck and
Library-paper Transparency behavior remain unchanged. There is no schema or user-data migration to reverse; locally
created transparency tool runs use the existing generic WIP run/finding tables.
