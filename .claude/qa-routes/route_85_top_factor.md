<!-- qa-coverage
api: /methods/top-factor/database, /methods/top-factor/database/refresh, /methods/top-factor/database/refresh/{job_id}
fe: 35e_maintenance.jsx, 08e_methods_publishers.jsx
-->

# ROUTE 85 — TOP Factor DB (the periodic bulk-mirror legitimacy source)

**Tier:** 1 local-stateful
**Goal:** Exhaust the TOP Factor local-mirror surface (backlog #40 slice, inc 448) — Settings → **Local
maintenance**'s TOP Factor row, the Refresh-database action, and the fact that the mirror feeds PUBLISHERS
(Discover → Journals, route 60)'s per-journal `top_factor` fact — while preserving the no-opaque-score honesty
contract: the `Total` is COS's own defined sum and must **never** render as a bare per-journal score, only inside
an expanded "show the basis" block alongside its category sub-scores + justifications. Public bulk CC0-adjacent
OSF-hosted metadata (Center for Open Science); **never** the Gemini gate. Unlike Retraction Watch (route 74), TOP
Factor needs no contact email/mailto — the OSF download URL is unauthenticated.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Register console/pageerror/request
listeners before navigation.

**Seed note:** `_seed_library` ships no TOP Factor data, and the real download is a ~4MB CSV fetched from OSF — so
do NOT trigger the live download in an automated run. Instead seed the mirror directly (offline), mirroring
`tests/test_top_factor.py`:

```python
from app.backend.persistence.database import make_engine
from app.backend.persistence.top_factor_repo import replace_top_factor_records
from integrations.top_factor.adapter import parse_top_factor_csv

engine = make_engine(db_url)
with engine.begin() as conn:
    replace_top_factor_records(conn, parse_top_factor_csv(FAKE_CSV), retrieved_at="2026-03-12T00:00:00Z")
```

where `FAKE_CSV` has the real confirmed header (`Journal,Issn,Eissn,Description,Publisher,Societies,Author
guideline url,<Category> score,<Category> justification,...,Total` for the 9-10 named TOP categories) and at least
one row whose ISSN matches a live seeded paper's journal, so a subsequent PUBLISHERS run (route 60) can surface it.

To exercise the **refresh** path offline, inject `app.state.top_factor_client = TopFactorClient(fetcher=lambda
url, **k: FAKE_CSV)` on the running app.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed is a bug.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (TOP Factor is public
  bulk metadata only, unauthenticated, no library text involved).
- **No opaque composite score (Principles #7, veto-level).** The `Total` figure must never render standalone on a
  Local Maintenance row, a status line, or a PUBLISHERS profile card — it is a database-status **count of journals**
  (`N journals · as of <date>`) here, and (in route 60) only ever shown inside the expanded "show the basis" block
  next to its category sub-scores. A bare per-journal `Total` number anywhere in the UI is **Critical**.
- **Fail-closed on malformed rows.** A CSV row with a malformed category-score cell omits that category (never
  fabricates a 0); a malformed `Total` cell is derived from the summed category scores rather than dropped or
  crashing the parse. A row with neither ISSN nor EISSN is skipped, never inserted with a null key.
- **No contact-email requirement.** Unlike Retraction Watch, Refresh must NOT show a "set a contact email" error —
  the OSF download needs no mailto/auth. A refresh failing on that basis is a regression (High).
- **Not a per-journal judgment.** TOP Factor measures a journal's stated transparency/openness policies, not the
  quality of individual articles or authors; the UI must not reframe it as a journal "grade" or "predatory" signal.

## Adversarial checklist

- double-click Refresh → at most one download
- a journal with no TOP Factor row → no fabricated `top_factor` on its PUBLISHERS profile card, journal still
  appears unchanged (route 60's own gate-the-boost-never-the-listing rule)
- a CSV row with a malformed score cell → that category omitted, not coerced to `0`
- a CSV row with a malformed `Total` cell → derived from summed category scores, not silently dropped
- resize to `375x812` → no horizontal overflow

## Steps

1. Open **Settings → Local maintenance**. Confirm a **"TOP Factor database: N journals · as of <date>"** line (or
   "Not downloaded — refresh to include TOP Factor in Where-to-submit results" when empty) + a **Refresh database**
   button, beside the existing Retraction Watch and "Repair synthesis cache" rows.
2. Trigger **Refresh database** with an injected fake client → it completes and the as-of line updates to the new
   count/date. No contact-email prompt appears at any point (confirms the no-mailto standing assertion).
3. With the mirror seeded (offline, matching a live paper's journal ISSN), run PUBLISHERS (Discover → Journals,
   route 60) for that paper. Confirm its profile card exposes a "show the basis" block; expand it and confirm every
   category name + sub-score + `/max` + justification renders, and the `Total` appears ONLY inside this expanded
   block — never as a standalone chip elsewhere on the card.
4. With the mirror never downloaded (fresh seeded instance, skip step 2), run PUBLISHERS for any topic. Confirm the
   results view's report-level footer note states TOP Factor hasn't been downloaded yet (route 60's own honesty
   assertion) rather than every card silently omitting the section.
5. (Real-download check — the user's, optional, not automated:) Refresh with live network access → the count/as-of
   line update from the real OSF-hosted CSV. This verifies the live URL + CSV schema (the one thing the hermetic
   tests assume).
6. Adversarial: double-click Refresh → one download; mobile viewport has no overflow.

## Pass criteria

- The as-of line + Refresh action render and work (offline with an injected client), inside Settings → Local
  maintenance, with no contact-email requirement.
- A malformed CSV row degrades honestly (omitted category / derived Total / skipped no-ISSN row) rather than
  crashing or fabricating data.
- The `Total` never renders as a bare per-journal score anywhere in the UI — only inside the expanded per-category
  basis block on a PUBLISHERS profile card.
- The never-downloaded state is an explicit report-level note in PUBLISHERS' results, not silent per-card omission.
- 0 console/page errors; **0 genai-host requests**; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_85_top_factor.md` + `screenshots/` (see `_TEMPLATE.md`) — capture the
Local Maintenance TOP Factor row and the expanded "show the basis" block on a real profile card.
