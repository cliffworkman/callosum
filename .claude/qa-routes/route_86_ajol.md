<!-- qa-coverage
api: /methods/ajol/database, /methods/ajol/database/refresh, /methods/ajol/database/refresh/{job_id}
fe: 35e_maintenance.jsx, 08e_methods_publishers.jsx
-->

# ROUTE 86 — AJOL DB (the one-time third-party regional-index snapshot)

**Tier:** 1 local-stateful
**Goal:** Exhaust the AJOL (African Journals Online) local-mirror surface (backlog #40 slice, inc 451) — Settings
→ **Local maintenance**'s AJOL row, the Download-database action, and the fact that the mirror feeds PUBLISHERS
(Discover → Journals, route 60)'s per-journal `ajol_status` fact — while preserving two honesty contracts distinct
from TOP Factor (route 85): (1) this is a **third-party CC-BY-4.0 compilation** (Alonso-Álvarez 2025, Zenodo DOI
`10.5281/zenodo.14899380`), not an AJOL-official feed; (2) it is a **one-time, immutable, February-2024-dated
academic snapshot** with no update guarantee — the button reads "Download database," never "Refresh," and the UI
must keep the fixed `snapshot_date` and the local `retrieved_at` timestamp visibly separate. AJOL's own official
`jpps_status` quality rating (Journal Publishing Practices and Standards: `1/2/3 Stars`, `No Stars`, `New Title`,
`Pending`, `Inactive Title`, `Ceased`, `NA`) ranges from positive to cautionary and must render **plainly** —
never filtered, softened, or hidden for a `Ceased`/`Inactive Title` journal. Public CC-BY-4.0 Zenodo-hosted data;
**never** the Gemini gate.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). **Egress UNSET.** Register console/pageerror/request
listeners before navigation.

**Seed note:** `_seed_library` ships no AJOL data, and the real download is a Zenodo-hosted CSV — do NOT trigger
the live download in an automated run. Instead seed the mirror directly (offline), mirroring `tests/test_ajol.py`:

```python
from app.backend.persistence.database import make_engine
from app.backend.persistence.ajol_repo import replace_ajol_records
from integrations.ajol.adapter import parse_ajol_csv

engine = make_engine(db_url)
with engine.begin() as conn:
    replace_ajol_records(conn, parse_ajol_csv(FAKE_CSV), retrieved_at="2026-08-05T00:00:00Z")
```

where `FAKE_CSV` has the real confirmed header (`source_id,source_url,source_title,eissn,issn_print,is_diamond,
jjps_status,country` — note the source file's own typo, `jjps_status`, double-j) and at least one row whose ISSN
matches a live seeded paper's journal (Nigeria/South Africa/Ethiopia are the best-represented countries in the
real 739-row dataset), plus one row with a cautionary `jpps_status` (`Ceased` or `Inactive Title`) so the
plain-display assertion below can be exercised.

To exercise the **download** path offline, inject `app.state.ajol_client = AjolClient(fetcher=lambda url, **k:
FAKE_CSV)` on the running app.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed is a bug.
- **Egress gate.** ANY request to a `generativelanguage`/Gemini/genai host is **Critical** (AJOL is public
  CC-BY-4.0 bulk metadata only, no library text involved).
- **No opaque composite score (Principles #7, veto-level).** AJOL exposes no numeric score at all (unlike TOP
  Factor's `Total`) — `jpps_status` is a categorical label, always shown with its own plain-language gloss, never
  reduced to a bare number or folded into any composite.
- **Fail-closed on malformed rows.** The real CSV encodes a missing ISSN as the literal string `"NA"`, not an
  empty cell — a row where BOTH `eissn`/`issn_print` are `"NA"` must be skipped entirely, never stored as a bogus
  matchable ISSN key shared across every such row (this was a real bug caught before ship, inc 451). A malformed
  `is_diamond` cell parses to unknown/`None`, never fabricated `False`. A `source_url` outside the
  `https://www.ajol.info/` prefix is dropped, never rendered as a clickable link to an untrusted host.
- **"Download," never "Refresh."** The Local Maintenance button and any related UI copy must never claim to
  "refresh" or "update" AJOL data — this is a fixed, one-time academic snapshot. "Refresh" appearing anywhere on
  this row is **High** (a false freshness claim).
- **Snapshot-date vs. download-date stay visibly distinct.** The status line must show both the fixed data
  vintage (`snapshot_date`, e.g. "February 2024") and the local download timestamp (`retrieved_at`) as two
  separate values — collapsing them into one date, or omitting `snapshot_date` entirely, is **Medium**.
  `snapshot_date` must be present even before any download has ever happened (`GET /methods/ajol/database`
  returns it unconditionally).
- **`jpps_status` renders plainly, including cautionary values (veto-level, Principles #6 + A-A's individuals-only
  no-accusation scope).** A journal whose AJOL status is `Ceased` or `Inactive Title` must render that status
  exactly as reported, with no filtering, no downgrade to silence, and no editorializing — this is an
  institutional/venue operational fact, not a judgment of a person. Hiding, filtering, or softening a cautionary
  `jpps_status` is **Critical** (a silence-as-certificate failure, worse than showing the plain fact).
- **Elevate, don't denigrate — extended to AJOL.** Only `1/2/3 Stars` may appear in `elevated_for`
  (`f"AJOL {status} rating"`); `Inactive Title`/`Ceased`/`Pending`/`NA`/`No Stars` must NEVER contribute an
  elevation string, even at full open-science weighting. Any of those five values appearing in `elevated_for` is
  **Critical** (a cautionary/neutral status silently read as a boost).
- **Not a per-journal judgment.** AJOL's `jpps_status` measures the journal's own reported publishing practices,
  not the quality of individual articles or authors; the UI must not reframe it as a "grade" or "predatory" signal.
- **Third-party attribution, not AJOL-official.** The credit block must cite both Zenodo DOIs
  (`10.5281/zenodo.14899380` the dataset, `10.5281/zenodo.14900054` the companion methods report) and state this
  is a third-party CC-BY-4.0 compilation — presenting it as AJOL's own official feed is **Medium**.

## Adversarial checklist

- double-click Download → at most one download
- a CSV row where both `eissn` and `issn_print` are the literal string `"NA"` → skipped entirely, no row with
  `issn == "NA"` or `eissn == "NA"` ever stored
- a journal with no AJOL row → no fabricated `ajol_status` on its PUBLISHERS profile card, journal still appears
  unchanged (route 60's own gate-the-boost-never-the-listing rule)
- a journal with `jpps_status: "Ceased"` → status renders plainly on its profile card; does NOT appear in
  `elevated_for` even at full weighting
- a `source_url` outside `https://www.ajol.info/` → dropped, not rendered as a link
- resize to `375x812` → no horizontal overflow

## Steps

1. Open **Settings → Local maintenance**. Confirm an **"AJOL database: N journals · <snapshot_date> snapshot,
   downloaded <date>"** line (or "Not downloaded — download to include AJOL in Where-to-submit results" when
   empty) + a **Download database** button (never "Refresh"), beside the existing Retraction Watch and TOP Factor
   rows. Confirm the sub-text states this is a third-party CC-BY-4.0 compilation and that re-downloading will not
   fetch newer data than the fixed snapshot.
2. Trigger **Download database** with an injected fake client → it completes and the status line updates with the
   new count + `retrieved_at`, while `snapshot_date` stays fixed at its constant value.
3. With the mirror seeded (offline, matching a live paper's journal ISSN, including one `Ceased`/`Inactive Title`
   row), run PUBLISHERS (Discover → Journals, route 60) for that paper/topic. Confirm a matched card shows an
   "Indexed in AJOL" signal plus a plain always-visible `jpps_status` / country / diamond-OA line with a
   plain-language tooltip; confirm a `Ceased`/`Inactive Title` status (if surfaced) renders identically — no
   filtering, no warning chrome beyond the plain tooltip gloss.
4. Re-run with full open-science weighting. Confirm a `1/2/3 Stars` journal's `elevated_for` carries
   `"AJOL <N> Star(s) rating"`; confirm a `Ceased`/`Inactive Title`/`Pending`/`NA`/`No Stars` journal's
   `elevated_for` never contains an AJOL string.
5. With the mirror never downloaded (fresh seeded instance, skip step 2), run PUBLISHERS for any topic. Confirm
   the results view's report-level footer note states AJOL hasn't been downloaded yet, rather than every card
   silently omitting the section.
6. Confirm the credit block (near the AJOL row or on the PUBLISHERS panel) cites both Zenodo DOIs and states the
   third-party/non-official nature.
7. (Real-download check — the user's, optional, not automated:) Download with live network access → the count/
   downloaded-date update from the real Zenodo-hosted CSV.
8. Adversarial: double-click Download → one download; mobile viewport has no overflow.

## Pass criteria

- The status line + Download action render and work (offline with an injected client), inside Settings → Local
  maintenance, always reading "Download" never "Refresh," with `snapshot_date` and `retrieved_at` visibly distinct.
- The `"NA"`-marker row is skipped entirely, never stored as a bogus ISSN key; malformed `is_diamond` parses to
  unknown, never fabricated `False`; an untrusted `source_url` is dropped.
- `jpps_status` renders plainly for every value including `Ceased`/`Inactive Title` — never filtered or hidden;
  only `1/2/3 Stars` ever appears in `elevated_for`.
- The never-downloaded state is an explicit report-level note in PUBLISHERS' results, not silent per-card omission.
- The credit block cites both Zenodo DOIs and frames this as third-party, not AJOL-official.
- 0 console/page errors; **0 genai-host requests**; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_86_ajol.md` + `screenshots/` (see `_TEMPLATE.md`) — capture the Local
Maintenance AJOL row (showing "Download database" + both dates) and a PUBLISHERS profile card showing a plain
`jpps_status` line (ideally a cautionary one, to prove the no-filtering assertion).
