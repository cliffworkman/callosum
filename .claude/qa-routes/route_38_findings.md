<!-- qa-coverage
api: /papers/{paper_id}/findings, /findings/overview, /findings/{finding_id}/review
fe: 08_methods_findings.jsx
-->

# ROUTE 38 - Findings: FACT-vs-CANDIDATE review surface (METHODS "Review")

**Tier:** 1 local-stateful
**Goal:** Exhaust the findings review surface (the METHODS "Review" section + the library work-state badge) while
preserving FACT-vs-CANDIDATE, signal-not-verdict, and no-accusation framing. Findings are local data; **no LLM,
no egress.**

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (findings are local — assert no
genai-host request regardless). Register console/pageerror/request listeners before navigation.

**Seed note:** `_seed_library` ships **no findings**, so the unseeded surface is the honest empty state. To
exercise FACTs + CANDIDATEs, seed two rows directly on the throwaway DB *before* starting the server (the same
contract a real producer uses) — there is no UI/endpoint that *creates* findings yet (the first producer,
retraction, is the next increment):

```python
from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.schema import paper_findings
engine = make_engine(DB_URL)
paper_findings.create(engine, checkfirst=True)  # only needed if the copy predates migration 0016
with engine.begin() as conn:
    upsert_findings(conn, PAPER_ID, "demo", [
        {"kind": "fact", "payload": {"label": "retracted (demo)"}},
        {"kind": "candidate", "tier": "primary", "payload": {"desc": "reported t(28)=2.10, p=.02 (demo)", "page": 4}},
    ])
```

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** Findings are local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **FACT vs CANDIDATE.** A FACT (e.g. retracted) renders as a **neutral persistent mark**, never a reviewable
  card; a CANDIDATE renders as a card with **Confirmed / Accepted / Noted**. Confusing the two is a bug.
- **Signal not verdict / no accusation.** The library badge reads as the user's **work state** ("N to review"),
  **never** a quality/score/"bad paper" verdict; zero unreviewed shows **no** badge. "Accepted" requires a reason
  (the human's judgment is recorded, not invented).

## Adversarial checklist

- click **Accepted...** then **save** with an empty reason -> rejected (the save control disabled / 422-class), no crash
- double-click a review button; rapid-click -> at most one review applied, no console error
- POST `/findings/{id}/review` for a non-existent id -> 404-class, graceful
- POST a review with an unknown `state` -> 422-class
- select a paper with **no** findings -> honest "No findings for this paper yet." (not an error/spinner-forever)
- resize to `375x812`, hard refresh -> no horizontal overflow

## Steps

1. Baseline screenshot of the library. A paper with a seeded fact + unreviewed candidate shows **"&#9670; fact"** +
   an **"N to review"** badge in its card foot; a paper with none shows neither.
2. Select that paper -> open the **METHODS** pane -> **Review** section (`GET /papers/{id}/findings`). Confirm the
   **FactMark** (&#9670; retracted (demo)) renders separately from the **candidate card** (the t-test description +
   a **show in paper - p.4** anchor + Confirmed / Accepted... / Noted).
3. Click the **show in paper** anchor -> the page opens at **region** precision (scroll + note, **no exact rect** —
   the finding carries a page, not a bbox). Coordinate-honesty holds.
4. Click **Confirmed** (`POST /findings/{id}/review`). The card flips to **reviewed** ("&#10003; confirmed") and the
   library **"N to review"** badge **drops** (the `/findings/overview` count refetched). The **fact mark stays**.
5. Reload -> the review **persists** (no "to review" badge; the section shows the candidate reviewed).
6. Adversarial: **Accepted...** with empty reason is not saveable; a review on a bad/old id fails closed; a
   no-findings paper shows the honest empty state.

## The unified review queue (inc 133)

A producer that emits CANDIDATEs (statcheck — run its batch in the METHODS "Statistics check" section, or seed a
candidate via `upsert_findings`) populates a library-wide **"📋 N to review"** chip + filter:

- The chip counts papers with ≥1 **unreviewed candidate** (from `/findings/overview`); it is a **work-state
  queue** ("have I looked?"), never a quality rank/score, and it disappears at zero.
- Click it → the library filters to those papers (`GET /papers?finding=needs-review`) with a banner; **clear**
  restores. Open a paper → its candidate card → **Confirm / Note** → it drops from the chip + the filtered view
  **live** (the view re-narrows).
- A statcheck candidate **coexists** with the statcheck **signal** (the "⚠ N flagged" chip): the signal is a fact
  about the paper (persists after review); the candidate is the user's review work. Reviewing the candidate
  removes the paper from the "to review" queue but **not** from the statcheck-flagged filter. Confusing the two —
  or treating the queue as a quality ranking — is a bug.

## Pass criteria

- FACTs render as neutral marks; CANDIDATEs as reviewable cards; the three review actions work and persist.
- The library badge + the "N to review" chip are work-state only (drop to nothing at zero unreviewed), never a verdict/score.
- Anchors open the page at region precision (no fabricated exact highlight).
- 0 console/page errors; **0 genai-host requests** (local).
- Bad inputs fail closed (404/422-class); mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_38_findings.md` + `screenshots/` (see `_TEMPLATE.md`).
