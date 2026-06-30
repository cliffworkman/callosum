<!-- qa-coverage
api: /papers/{paper_id}/retraction, /methods/retraction/run, /methods/retraction/run/{job_id}, /methods/retraction/summary
fe: 08_methods_findings.jsx
-->

# ROUTE 39 — Retraction producer (Crossref + OpenAlex → a FACT)

**Tier:** 1 local-stateful
**Goal:** Exhaust the retraction findings producer — the library-wide check, the "N retracted" chip + filter,
the retraction FactMark + notice link, and the per-paper check status — while preserving FACT-not-candidate,
silence≠clean, no-accusation, and evidence-carried. Sources are **public DOI metadata** (Crossref + OpenAlex),
never the Gemini gate.

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
- **FACT not candidate.** A retraction renders as a neutral **FactMark** (status + notice link), never a
  reviewable card with Confirmed/Accepted/Noted.
- **Silence ≠ clean.** A checked-clean paper shows "checked — none found"; a no-DOI paper shows "unchecked — no
  DOI"; neither is ever presented as "clean / verified". A never-checked paper says so.
- **No accusation / not a verdict.** The chip is a **filter** count of papers a registry records retracted —
  never a score, rank, or author judgment; the framing says "verify before citing".
- **Evidence carried.** The FactMark links the **notice** (a doi.org URL) + names the flagging source(s).
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
   /methods/retraction/summary`); a retracted paper's card carries the ◆-fact mark.
2. Click the chip → the library filters to the retracted paper(s) (`?signal=retraction-retracted`) with a
   non-accusatory banner ("verify before citing"); **clear** restores the full library.
3. Open the retracted paper → **METHODS → Review**. Confirm the **retraction FactMark** ("⚠ Retracted") with a
   **notice** link (opens doi.org in a new tab) and a Source(s) tooltip — NOT a reviewable card.
4. Open a checked-clean paper → Review → "Retraction: checked — none found (…)". Open a no-DOI paper → Review →
   "Retraction: unchecked — no DOI". (`GET /papers/{id}/retraction`.)
5. In the Review section, run **Check all papers for retractions** (`POST /methods/retraction/run`, with injected
   deterministic checkers) → it completes, reports "N retracted", and refreshes the chip.
6. Adversarial: a 404 on an unknown paper's retraction; double-click the batch; mobile viewport has no overflow.

## Pass criteria

- The producer's read surfaces render: chip + filter, FactMark + notice link, per-paper status (none/unchecked).
- FACT-not-candidate; silence≠clean; chip is a filter, not a verdict; the notice link + sources are shown.
- 0 console/page errors; **0 genai-host requests**.
- Bad inputs fail closed (404); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_39_retraction.md` + `screenshots/` (see `_TEMPLATE.md`).
