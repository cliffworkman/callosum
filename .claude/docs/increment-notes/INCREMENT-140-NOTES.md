# Increment 140 — The end-user experience pass (a 4th gate) + its first dogfood

## Implemented

Codifies a new standing orientation the user asked for: **before any user-facing change is "done," make a pass
inhabiting the end user of the thing you touched** — does it actually *serve* them? This is the 4th gate, beside
DESIGN (#8, looks right), PRINCIPLES (#9, honest), QA (#10, works + covered).

- **New `.claude/EXPERIENCE-PASS.md`** — the charter for the pass:
  - **The two questions:** (1) **reception** — discoverable, legible, is the next step obvious; (2) **intended
    use** — what does the user reach for next, does the built thing support it or dead-end. Q2 is **bounded by our
    commitments** (a desire that conflicts with the ethics — accusation/leaderboard, paywall circumvention, an
    opaque score — is *declined* per PRINCIPLES + APPROACH-AVOIDANCE, not served).
  - **The mechanism (the user's upgrade):** *persona-grounded experience agents* — dispatch a subagent **in
    character** as a concrete persona pursuing a **goal in the moment** (the deadline citer, the corpus builder,
    the skeptical synthesizer), to drive the feature end-to-end and report what's left to be desired. Grounding in
    a persona + task makes "is the UX good?" a checkable "can *this* person, doing *this*, get where they're
    going?" Prefer driving the built feature headed; fall back to a code-+help-grounded walkthrough.
  - **An extensible persona/scenario library** (a persona = a *goal-in-the-moment*, not a demographic).
  - The statcheck **worked example** + the trigger/deliverable (reflective pause → a finding: fix-cheap or
    backlog, tagged to the persona it blocks).
- **CLAUDE.md rule #11** points at it (+ a reference-docs row + the "4 gates" framing); the inc-121 decision-log
  row + footer note the gate.

## The first dogfood (the pass, applied to itself)

Dispatched the **deadline-citer** persona agent against the live statcheck flow (its goal: vet a paper's stats
before citing a result from it). **Finding:** the per-paper drill-down — METHODS → **Statistics check** → "This
paper" → Check statistics → per-test rows (reported vs recomputed *p* + page) — **exists and is excellent**, but
the *path to it is hidden*: the METHODS pane defaults to **Details**, and clicking a flagged paper (from the
"⚠ N flagged" chip → filter) lands on **Details**, not Statistics check, and ignores the flagged state. So
"this paper is flagged" and "here is the specific result that doesn't recompute" are two good halves that **don't
link**. Verdict: a deadline-pressed citer could succeed only by accident.

**Triage (per the pass: human decides; I filed rather than re-wiring a deliberately-designed flow):** filed to
`INCREMENT-BACKLOG.md` as a **▲ BUILD FIRST** callout with 5 sub-findings, simplest-first — (a) open the
**Statistics check** section when the user activates the flagged view *(the cheap, highest-value fix)*; (b) a
"Check statistics" entry point on the paper itself **[design]**; (c) pre-run/cache the per-paper detail; (d)
deep-link the flagged chip to the specific test + page; (e) clarify the "⚠ flagged" vs "📋 to review" duality
**[design]**.

## Manual verification

Docs-only governance change — no app code, no build, no surface change. The dogfood agent's transcript is the
artifact; sub-finding (a) is queued as the first concrete UX fix.

## Pytest

**519 passed, 1 skipped** — unchanged (no app/test code touched). `ruff` clean (nothing to lint).

## Next (queued)

- **Build-first:** statcheck flagged → per-test path, sub-finding (a) — open the Statistics check section from the
  flagged view (a few lines; the highest-value cheap fix the dogfood surfaced).
- Gap-finder followed-authors / similarity ranking; a cadence auto-refresh.
- **Watch (rule #1):** `clustering/my_publications.py` at **594/600**.
