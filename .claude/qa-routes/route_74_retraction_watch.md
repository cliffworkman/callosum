<!-- qa-coverage
api: /methods/retraction/database, /methods/retraction/database/refresh, /methods/retraction/database/refresh/{job_id}
fe: 35_settings.jsx, 08x_methods_critical.jsx
-->

# ROUTE 74 — Retraction Watch DB (the bulk third source)

**Tier:** 1 local-stateful
**Goal:** Exhaust the Retraction Watch database surface — now **Settings → Local maintenance** (moved from the
retired left-pane Review accordion, 2026-07-20; the library-wide check itself lives as a Library-header button,
route 39) — the as-of line, the Refresh-database action, and the fact that the RW source (the richest:
reason/date/notice) feeds the producer's merge, surfaced via **Synthesize → Critique**'s Tier-1 backbone — while
preserving the retraction honesty invariants. Public bulk CC0 metadata; **never** the Gemini gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Register console/pageerror/request
listeners before navigation.

**Seed note:** `_seed_library` ships no RW data, and the **real download needs a contact email (Settings →
Metadata access, or the `CALLOSUM_CROSSREF_MAILTO` env var) + a ~tens-of-MB fetch** — so do NOT trigger the live
download in an automated run. Instead seed the mirror + a
matching paper's FACT directly (offline), mirroring `.local/visual/drive_inc132_retraction_watch.py`:

```python
from app.backend.methods.retraction import RETRACTION_WATCH_CHECKER, apply_retraction, detect_retraction
from app.backend.persistence.retraction_repo import replace_retraction_records
from app.backend.persistence.schema import paper_findings, retraction_records
paper_findings.create(engine, checkfirst=True); retraction_records.create(engine, checkfirst=True)
with engine.begin() as conn:
    replace_retraction_records(conn, [{"original_doi": <a live paper's doi, lower>, "status": "retracted",
        "nature": "Retraction", "date": "2021-03-15", "reason": "+Falsification", "notice_doi": "10.1/notice",
        "notice_url": "https://doi.org/10.1/notice"}], retrieved_at="2026-06-26T12:00:00Z")
    apply_retraction(conn, PID, detect_retraction(conn, get_paper(conn, PID), checkers=[RETRACTION_WATCH_CHECKER]))
```

To exercise the **refresh** path offline, inject `app.state.retraction_watch_client =
RetractionWatchClient(fetcher=lambda url, **k: FAKE_CSV, mailto="x@y.z")` on the running app.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed is a bug.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (RW is public bulk
  metadata only).
- **Fail-closed.** With no contact email (neither Settings → Metadata access nor `CALLOSUM_CROSSREF_MAILTO`), a
  real Refresh reports a **clear error** ("Set a contact email in Settings → Metadata access …"), never a 500 or
  a silent hang. Setting the contact email in Settings enables the download with no env var.
- **No accusation / FACT not candidate / reinstatements not flagged.** RW only adds coverage + richer detail
  (reason/date/notice) to the SP1 producer; it never introduces an author signal, and a **Reinstatement** is
  never surfaced as a finding.

## Adversarial checklist

- click Refresh with no mailto → a clear error, no crash
- double-click Refresh → at most one download
- a paper with no DOI → no RW match, honestly no retraction signal row surfaced (unchanged from SP1)
- resize to `375x812` → no horizontal overflow

## Steps

1. Open **Settings → Local maintenance**. Confirm the **"Retraction Watch database: N records · as of <date>"**
   line (or "Not downloaded — refresh to enable the richest source" when empty, `> 30 days old — refresh
   recommended` amber cue when stale) + a **Refresh database** button, beside the existing "Repair synthesis
   cache" action.
2. With the mirror seeded, open the matching paper → **Synthesize → Critique** → its Tier-1 "Retraction status"
   row shows the retracted detail + a **notice** link, sourced from the RW-enriched fact (reason + sources incl.
   `retraction-watch`).
3. Trigger **Refresh database** with an injected fake client → it completes and the as-of line updates; the
   Library header's "N retracted" chip refreshes too (`onRetractionRan`, threaded from `40_app.jsx` into
   `SettingsView` → `LocalMaintenanceSettings`).
4. (Real-download check — the user's, optional, not automated:) with a mailto set, Refresh → the count + a
   known-retracted library DOI flags. This verifies the live URL + CSV schema (the one thing the hermetic tests
   assume).
5. Adversarial: Refresh with no mailto → clear error; mobile viewport has no overflow.

## Pass criteria

- The as-of line + Refresh action render and work (offline with an injected client), inside Settings → Local
  maintenance.
- The RW source contributes the richest detail to a flagged paper's Critique signal row; reinstatements never
  flagged.
- 0 console/page errors; **0 genai-host requests**.
- Fail-closed on mailto-absent; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_74_retraction_watch.md` + `screenshots/` (see `_TEMPLATE.md`).
