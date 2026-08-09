# Increment 466 — Credit-the-lineage backfill (item #3 of the post-P2 backlog sequence)

## Implemented

Third item in the confirmed post-P2 backlog sequence (memory `callosum-next5-backlog-roadmap`). The proposing
future-tracks doc turned out to be **stale** — a full audit (not assumed) found most of it already built in a
prior session: statcheck, GRIM/GRIMMER, the Bayesian/LMM/meta-analysis/transparency auditors, the effect-size
converter, citation-context (scite), PUBLISHERS (DOAJ/SciELO/TOP Factor/AJOL/NLM), and overlooked-work
(Merton 1968) all already had real in-app `MethodCreditButton` blocks (`05_method_credit.jsx`, inc 293), a
comprehensive `THIRD-PARTY-NOTICES.md`, and help-doc coverage.

### Genuine gaps closed

1. **Retraction Watch** — powers retraction detection everywhere (Library Integrity, Meta-Reference, LibreOffice's
   Citation integrity preflight) but was credited nowhere. No canonical citable paper exists for it (verified via
   search — same situation already handled honestly for SciELO), so this is a **text-only credit acknowledgment**
   in Settings → Local Maintenance (`35e_maintenance.jsx`, where the mirror itself lives — confirmed with Cliff as
   the one canonical home rather than repeating it on every retraction-badge surface), plus a matching
   `THIRD-PARTY-NOTICES.md` subsection and a help-doc sentence.
2. **Daniel Lakens' automated-review catalog** — already had a full citable entry in the static NOTICES file (a
   real peer-reviewed paper about it: Crone & Green 2025, DOI `10.1177/09593543241311861`, verified via search)
   but was only ever passing italic sub-text in 7 tool panels. New shared `LakensCredit()` component
   (`05_method_credit.jsx`, sibling to `MethodCreditButton`) replaces the plain text in all 7 panels
   (`06_methods_statcheck.jsx`, `07_methods_grim.jsx`, `08d_methods_bayes.jsx`, `08f_methods_lmm.jsx`,
   `08g_methods_metaanalysis.jsx`, `08h_methods_transparency.jsx`, `29_pcurve.jsx`) with a real, clickable,
   library-addable citation. One component, not 7 copies of the same citation data.
3. **`THIRD-PARTY-NOTICES.md` Lane B gaps**: added `pyjwt` and the optional `keyring` extra (both real
   `pyproject.toml` runtime deps, previously absent from the license-grouped list); fixed the file's own stale
   header (still said "currently documents... the citation & bibliography engine... a fuller NOTICE is a tracked
   follow-up," no longer true given how comprehensive the file already was).

## Key technical detail

**A real, pre-existing bug was found and fixed while verifying, not shipped alongside a known-broken button.**
Manually testing the new Crone & Green credit block in a live browser session revealed that `MethodCreditButton`
(the shared component every one of these credit blocks — and ~12 tool panels app-wide — depends on) was
**lying about success**: `POST /library/import` is an async job endpoint (`202 Accepted` + `job_id`, with a
companion `GET /library/import/{job_id}` to poll), but `addMissing()` only ever checked that the initial POST
returned `ok: true` — i.e., that a job was successfully *queued* — and immediately showed "✓ added to library"
regardless of whether the import actually succeeded. Concrete repro: a real click showed success, but
`POST /library/credit/status` afterward reported `present: false` — the paper was never added. Root cause of
that specific failure: a legitimate, currently-running watched-folder rescan (auto-triggered on server startup,
processing 111 PDFs) held sustained write locks, and `import_citations`'s per-record `except Exception: failed
+= 1` swallowed the resulting `sqlite3.OperationalError: database is locked` with no logging at all.

Confirmed with Cliff (a scope check, since this bug pre-dates and is broader than this increment) to fix it now
rather than defer: `MethodCreditButton` now polls the job to completion (mirroring `GapsModal`'s own job-polling
pattern) and only shows "✓ added to library" once `summary.failed === 0`; a real failure shows "add failed —
retry" (clickable again, matching `BeyondSaveButton`'s own `error` state label pattern from inc 465). Verified
live: the fixed button correctly showed "add failed — retry" during the real lock contention (rather than lying),
and `POST /library/credit/status` confirmed the DOI was genuinely absent both times — proving the fix reports the
truth rather than merely "looking fixed."

**Not fixed, filed to the backlog** (a deeper, separate concern than the button's own honesty, and out of scope
for this pass): `import_citations`'s swallowed exception (`app/backend/metadata/citation_import.py`'s bare
`except Exception: failed += 1`) logs nothing, making a real failure like this one very hard to diagnose from the
server's own console — worth a small follow-up to at least log the exception, but this touches shared import
logic used by several other call sites (BibTeX/RIS import, etc.), not just this button.

## Housekeeping / gates

- No security audit triggered (docs/attribution-only for the credit content; the `MethodCreditButton` fix is a
  correctness fix to an existing, already-audited write path — no new endpoint, no new egress, no new
  ingestion path).
- QA: `python tools/qa/build_surface_map.py check` — coverage unaffected (no new uncovered surfaces; the new
  `<a>`/button elements live inside already-covered panel files).
- `.claude/docs/INCREMENT-BACKLOG.md`: the credit-help-backfill future-track item marked closed; a new small
  entry added for the `import_citations` silent-exception-logging follow-up.
- Memory `callosum-next5-backlog-roadmap` updated: item #3 closed, item #4 (RegCheck DEBIT/z-curve) next.
- `.claude/CLAUDE.md`: counter bumped to 466; pytest count updated to the actual measured total.

## Manual verification script

1. Open Settings → Local Maintenance — confirm the Retraction Watch credit line renders with working links to
   retractionwatch.com and the Crossref CC0 dataset.
2. Select a paper, open Methods → Statistics (or any of the other 6 Lakens-credited panels) — confirm the
   `LakensCredit` block renders with a working link to the catalog and a "＋ add missing to library" button for
   Crone & Green (2025).
3. Click the button — confirm it shows "adding…" then either "✓ added to library" (verify via
   `POST /library/credit/status`) or, under real write contention, "add failed — retry" (never a false "added").
4. Retry after any contention clears and confirm it succeeds and the button becomes disabled with "✓ added to
   library".

## Verification

- Frontend-only change (no backend Python touched). `python tools/build_frontend.py` — clean build both times
  (before and after the `MethodCreditButton` fix).
- `pytest tests/test_frontend_assembly.py -q` → 64 passed.
- `python tools/qa/build_surface_map.py check` → clean, 0 uncovered (both API and FE).
- Manual, live-browser verification (Playwright): confirmed the Retraction Watch credit block renders correctly;
  confirmed the Lakens/Crone-&-Green credit block renders correctly in the statcheck panel; confirmed the
  `MethodCreditButton` fix correctly reports a real failure rather than a false success under genuine write
  contention (root-caused, not just observed).

## Rollback

Revert `05_method_credit.jsx` (both the `LakensCredit` addition and the `MethodCreditButton` polling fix),
`35e_maintenance.jsx`, the 7 method-panel files' Lakens-credit swap, `THIRD-PARTY-NOTICES.md`, and
`help_content.md` to their pre-466 state. All changes additive/backward-compatible; no schema, no backend
Python, no existing endpoint contract changed.
