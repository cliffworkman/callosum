<!-- qa-coverage
api: /papers/{paper_id}/retraction, /methods/retraction/run, /methods/retraction/run/{job_id}, /methods/retraction/summary
fe: 10_pdf_layer.jsx, 10b_libmenus.jsx, 08x_methods_critical.jsx
-->

# ROUTE 39 — Retraction producer (Crossref + OpenAlex → a FACT)

**Tier:** 1 local-stateful
**Goal:** Exhaust the retraction findings producer — the library-wide check (a Library-header button,
`RetractionCheckButton`), the "N retracted" chip + filter, the retraction fact + its notice link (now inside
**Synthesize → Critique**'s Tier-1 backbone, since the 2026-07-20 retirement of the left-pane Review accordion —
its dedicated `FactMark` component is gone, but the same fact + evidence link render via Critique's generic
method-signal list), and the per-paper check status — while preserving FACT-not-candidate, silence≠clean,
no-accusation, and evidence-carried. Sources are **public DOI metadata** (Crossref + OpenAlex), never the Gemini
gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET** (retraction is public-metadata, not the
library gate — but the library-text gate must never fire; assert no genai-host request). Register
console/pageerror/request listeners before navigation.

**Seed note:** `_seed_library` ships no retraction state and the seed papers won't resolve against the live
registries deterministically, so do NOT rely on a live batch flagging anything. To exercise the read surfaces
deterministically + offline, seed outcomes directly via the real `apply_retraction` *before* starting the server
(no network — build the outcomes by hand), mirroring `.local/visual/drive_inc131_retraction.py`:

```python
from app.backend.methods.retraction import MergedRetraction, RetractionOutcome, apply_retraction
from app.backend.persistence.schema import paper_findings
paper_findings.create(engine, checkfirst=True)  # only if the DB predates migration 0016
with engine.begin() as conn:
    apply_retraction(conn, A, RetractionOutcome("retracted", MergedRetraction(
        "retracted", "Retraction", "2021-03-15", None, "10.1/notice", "https://doi.org/10.1/notice",
        ["crossref", "openalex"]), ["crossref", "openalex"]))
    apply_retraction(conn, B, RetractionOutcome("none", sources_checked=["crossref", "openalex"]))
    apply_retraction(conn, C, RetractionOutcome("unchecked"))
```

To exercise the **live batch** path, inject deterministic checkers on the running app
(`app.state.retraction_checkers = [RetractionChecker("crossref", fake)]`) so the run stays offline.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed through the UI is a bug.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (retraction is
  public-metadata only; the library-text gate must not fire).
- **FACT not candidate.** A retraction renders as a neutral method-signal row in Critique's Tier-1 backbone
  (label "Retraction status" + a status/reason detail), never a reviewable card with Confirmed/Accepted/Noted.
- **Silence ≠ clean.** A paper with nothing surfaced shows Tier-1's honest "nothing surfaced by these checks —
  read on your own judgment" message; a never-checked/no-DOI paper is never presented as "clean / verified".
- **No accusation / not a verdict.** The chip is a **filter** count of papers a registry records retracted —
  never a score, rank, or author judgment; the framing says "verify before citing".
- **Evidence carried.** A retracted paper's signal row links the **notice** (a doi.org URL, `notice_url` passed
  through verbatim from the stored fact payload — `critical_review.py::_stored_method_signals`, never re-derived)
  and its detail names the flagging source(s).
- **On-import lifecycle (inc 134/224).** The FACT can also land *without* a manual batch — on scan + citation
  import (134), and on the DOI-bearing enrich/acquire paths (224: OA-acquire, `re-resolve`, `fill-metadata`).
  These auto-checks are best-effort (a source error never breaks the import/enrich), reuse the same
  public-metadata checkers (no Gemini gate), and add no new endpoint/surface.

## Adversarial checklist

- click the batch run twice / rapidly → at most one run, no console error
- `GET /papers/{nonexistent}/retraction` → 404-class, graceful
- a paper with no DOI → "unchecked — no DOI", never "clean"
- resize to `375x812`, hard refresh → no horizontal overflow

## Steps

1. Baseline screenshot. The library header shows a red **"⚠ N retracted"** chip (from `GET
   /methods/retraction/summary`) and a **"Retractions ↻"** button (`RetractionCheckButton`, `10b_libmenus.jsx`);
   a retracted paper's card carries the ◆-fact mark.
2. Click the chip → the library filters to the retracted paper(s) (`?signal=retraction-retracted`) with a
   non-accusatory banner ("verify before citing"); **clear** restores the full library.
3. Open the retracted paper → **Synthesize → Critique**. Confirm the Tier-1 backbone's method-signal list shows a
   **"Retraction status"** row (label + a status/reason detail) with a **notice** link (opens doi.org in a new
   tab, `notice_url` passed through from the stored fact) — a plain signal row, NOT a reviewable card.
4. Click the Library header's **Retractions ↻** button (`POST /methods/retraction/run`, with injected
   deterministic checkers) → it completes, its tooltip reports "N checked · M retracted", and the chip refreshes.
5. Adversarial: a 404 on an unknown paper's retraction (`GET /papers/{id}/retraction` — still exposed and tested,
   though no longer called by the frontend post-merge; kept as a minimal, low-risk leftover rather than an
   unplanned backend deletion); double-click the batch button; mobile viewport has no overflow.

## Pass criteria

- The producer's read surfaces render: chip + filter, the Library header's batch button, and Critique's
  Tier-1 signal row (label + detail + notice link) for a retracted paper.
- FACT-not-candidate; silence≠clean (Tier-1's honest-null message covers a paper with nothing surfaced); chip is
  a filter, not a verdict; the notice link + sources are shown.
- 0 console/page errors; **0 genai-host requests**.
- Bad inputs fail closed (404); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_39_retraction.md` + `screenshots/` (see `_TEMPLATE.md`).
