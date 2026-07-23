# Increment 353 — Snapshot-bound WIP checks and reviewable findings

## Context

WIP checkpoints could identify exact manuscript content, but no tool result could yet name the checkpoint it
examined, preserve its coverage, or remain reviewable after the draft changed. This increment implements WIP-8 from
the approved manuscript-workspace plan with one deterministic local checker end to end.

## Implemented

- Migration `0051` adds generic `tool_runs`, exact WIP run associations, and WIP findings with candidate
  dispositions. The migration is guarded for the repository's fresh-DB `metadata.create_all` architecture and
  explicitly tested as a real `0050 -> 0051` upgrade.
- WIP extraction now retains normalized, in-memory content blocks with honest section/page metadata for the
  duration of a run. Full manuscript text remains absent from SQLite.
- **Run statcheck** examines the current primary file locally and synchronously, recording Statcheck/Callosum
  versions, exact checkpoint/file/text hash, parameters, structured result, summary, coverage, and execution time.
- Each surfaced possible inconsistency is a **candidate**, never a verdict. It carries the matched report, bounded
  context, reported and recomputed p-values, null coordinate precision where no exact anchor exists, and a
  user-controlled disposition.
- Run validity is derived from current content identity plus unresolved candidate state:
  `current-with-findings`, `current`, `potentially-stale`, or `stale`. A zero-finding run still states the check's
  limits and explicitly refuses to call the manuscript clean.
- The Checks view exposes progress, evidence, dispositions, and **Open source file** so a signal leads directly
  back to the draft. Tool-run status uses neutral/amber semantics, never WIP teal, verified green, or destructive
  red.

## Principles gate

Principles 1, 2, 3, 4, 6, 8, and 10 apply; this most closely resembles Example 3's deterministic effect-size path.
The deterministic recomputation is the substrate, but a possible reporting inconsistency remains a candidate
because rounding, adjusted values, and reporting conventions require human judgment. The rejected shortcut was a
bare “passed/failed” or “clean” manuscript label detached from exact content, evidence, coverage, and review.

## Experience pass

A submission-stage manuscript author was used as the concrete persona: they see a possible inconsistency and need
to judge and fix it without hunting through the workspace. The first browser pass exposed a dead end from finding
to draft, so **Open source file** was added in the same increment. The result now supports evidence review,
source return, and disposition without implying an exact text coordinate the extractor does not possess.

## Manual verification

1. Add a WIP folder containing a supported primary file with `t(18) = 2.10, p = .90`; make it primary.
2. Open the manuscript workspace, choose **Checks**, and click **Run statcheck**.
3. Confirm the run shows `current with findings`, tool version, checkpoint, time, stated inline-APA coverage,
   quote/context, reported p, and recomputed p.
4. Confirm **Open source file** targets the registered primary file. Mark the candidate resolved and confirm the
   run becomes neutral `current` without disappearing.
5. Edit the draft and rescan: the old run becomes `potentially stale`. Rerun after extraction: the new run is
   current and the old run is stale.
6. Run against a draft with no supported inline result and confirm the empty output says only that nothing was
   surfaced within the stated coverage, never that the manuscript is clean.

## Verification

- `pytest -n auto -q` — **1453 passed, 1 skipped**.
- Focused WIP/provenance/frontend/help/health/migration suites — **80 passed** before the final gate.
- Ruff, frontend rebuild, 600-line budget, fresh migration/model drift, and explicit `0050 -> 0051` upgrade pass.
- QA surface map — **292/292 API surfaces**, zero uncovered; 21 pre-existing frontend checklist entries remain.
- Headless Chromium at 1440x900 dark and 375x812 light: finding evidence, direct source action, disposition
  transition, and coverage boundary pass with zero console/page errors, egress requests, or horizontal overflow.

## Next slice

WIP-9 completeness and graduation: remaining filters/sorts and context actions, explicit moved-folder relinking,
reverse paper-to-WIP visibility, accessibility/keyboard review, and the full acceptance-criteria matrix.
