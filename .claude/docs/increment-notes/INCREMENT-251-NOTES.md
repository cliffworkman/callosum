# Increment 251 — Persist transparency signals (backlog #44 increment 1b)

Turns the inc-250 ephemeral transparency panel into **persistent, library-wide signal**: a batch run persists each
paper's *detected-present* disclosures as **findings-FACTs** + its per-disclosure **check status**, powering **7
review-queue library filters** + a Library-header **review chip**. The consumer-side statcheck-persist (inc 97) /
retraction-FACT (inc 131) pattern, applied to transparency.

## Implemented

- **`app/backend/methods/transparency_findings.py` (NEW):** `persist_transparency(conn, paper_id, chunks)` runs
  `detect_transparency` (inc 250) and writes:
  - **present-disclosure FACTs** → `upsert_findings(conn, paper_id, "transparency", facts)` (inc 130): one
    `{kind:"fact", payload:{key,label,desc,evidence,page,basis}}` per **present** disclosure. **No FACT for
    not-found / not-applicable** — the load-bearing A-A move (an absence is never a fact).
  - **per-disclosure check status** → `store_transparency_status(conn, paper_id, report)`.
  - Returns `{present, checks}`.
- **`app/backend/persistence/signals_repo.py`:** `TRANSPARENCY_SIGNAL` + `_TRANSPARENCY_STATUS` (present→detected /
  not-found→not-detected / not-applicable→not-applicable); `store_transparency_status` (OR-REPLACE one
  `open_science_signals` row per disclosure, `source=<disclosure_key>`, `evidence_snippet` on present rows — idempotent
  on the unique `(paper, signal_type, source)`); `count_transparency_review(disclosure_key)` (# papers with a
  `not-detected` status → the chip count).
- **`app/backend/api/routers/transparency.py`:** `POST /methods/transparency/run` (202, JobStore over
  `list_live_paper_ids`) + `GET /methods/transparency/run/{job_id}` + `GET /methods/transparency/summary` →
  `{data_not_detected}`. `_run_transparency_all_job` opens one `engine.begin()`, persists per paper, `mark_progress`.
- **`app/backend/api/app.py`:** `api.state.transparency_jobs = JobStore()`.
- **`app/backend/persistence/repository.py`:** `SIGNAL_FILTERS` values generalized `(signal_type, status)` →
  `(signal_type, source|None, status)`; the query adds `open_science_signals.c.source == :bound` only when the tuple
  pins a source (back-compat: statcheck/retraction pass `source=None`). Added 7 transparency review queues:
  `transparency-{data,code,coi,funding,registration,preregistration}-not-detected` +
  `transparency-upon-request` (the *present* case).
- **Frontend:** `08h_methods_transparency.jsx` — a **Whole library → Check all papers** batch (`TransparencyLibrary`,
  the statcheck-library pattern) + 7 review-queue links + `TRANSPARENCY_QUEUES`. `03_library.jsx` (`useLibrary`) —
  `transparencyReview` count + `showTransparencyReview(signalKey)` + `refreshTransparencyChip` + a mount effect.
  `10_pdf_layer.jsx` — the **🔎 N · open data not detected** chip (indigo `.transparency-chip` work-queue color).
  `40_app.jsx` + `05_panes.jsx` paneCtx — `onTransparencyRan` / `onShowTransparencyReview`. `styles.css` —
  `.transparency-chip` + `.transparency-queues`, tokens only.

## Key technical detail

**The A-A no-accusation boundary is enforced structurally, not by copy:**
- **Present-only FACTs.** FACTs are built only for `status == "present"`; an absence is never a fact. A re-run that
  detects fewer supersedes the stale FACT (via `upsert_findings` content_key) + flips the status row to `not-detected`.
- **Status rows are check results, not claims.** `open_science_signals` records that the auditor *ran and did/didn't
  find* the disclosure in the text — the review-queue chip/links/banner are worded "not detected — go look", never
  "hides data / no open data".
- **Precondition scoping for free.** The registration review queue matches `not-detected` only; a non-trial paper
  stores `not-applicable` → excluded (no registration flag on every paper). upon_request is the *present* case (its
  absence is the norm, so never a "not detected" queue).
- **No migration** — `paper_findings` (inc 130) + `open_science_signals` (inc 97, unique `(paper, signal_type,
  source)`) already exist. No egress / LLM / new dependency.

## Manual verification script

`.local/visual/drive_inc251_transparency_persist.py` (headed, no egress): seeds an OPEN paper (data@OSF / code@GitHub /
COI / funding) + a BARE paper (nothing disclosed) → open METHODS → Transparency signals → **Whole library → Check all
papers** → the summary reads "2 papers checked · 1 with ≥1 disclosure detected" + 7 review-queue links → the Library
header shows **🔎 1 · open data not detected** → click → the library narrows to the BARE paper only (the OPEN one, which
has a data FACT, is excluded) → `GET /findings/overview` shows only the open paper has FACTs (the bare has none — the
absence-is-never-a-fact pin). 0 console/page/genai. **PASS.**

## Gates

- **Audit `.claude/security-audits/2026-07-02_transparency-persist.md` PASS** (local read-only persisted to existing
  tables with bound-param SQL; no external fetch / egress / LLM / migration / new dependency; the no-accusation boundary
  structural + test-pinned).
- **Principles + A-A (rule #9) — aligned** (the statcheck-persist / retraction-FACT class; the declined path — a
  "transparency score / no-open-data verdict / persist-an-absence-as-a-fact" — is refused structurally).
- **QA (rule #10):** `route_63_methods_transparency.md` extended (the 3 batch endpoints + the review-queue chip/filter +
  the present-only-FACT / review-queue-not-verdict assertions); surface **182/182 API + 814/814 FE, 0 uncovered**.
- **Experience pass (rule #11, open-science-vetter, inline):** delivers the inc-250 F1/F4 findings (library-wide
  surfacing + a review queue + on-card FACTs). Residual: the batch trigger stays behind the METHODS panel (the standing
  F1 "buried panel" finding, already filed cross-method to #23) — no new cheap fix.

## Pytest

**963 + 8** hermetic `tests/test_transparency_findings.py` (full-suite count stamped after the run). The 8: present →
FACTs + detected status; a bare paper → **no absence facts** + not-detected status (the A-A pin); re-run supersedes a
now-absent disclosure; re-run idempotent (one status row per disclosure); `count_transparency_review`; facts-are-facts-
only; the batch endpoint 202→poll→done + the review-queue filter (data queue excludes a present-data paper; both papers
in the preregistration queue) + summary + 404; registration filter excludes n/a (non-trial) + upon-request is the
present case.

## NEXT (within #44)

Increment 1b's remaining thread: `system:transparency:*` **tags** from the detected-present disclosures (the tags↔
system-facts cross-cut, #19) — deferred (the tag-provenance model is an open design problem; FACTs + filter deliver the
value). Then increments 2–5: a `DocumentTextProvider` for JATS/DOCX/HTML full text (so the detectors see the whole
paper, not just PDF chunks); a registration-consistency check; a CRediT parser; a reported-vs-registered consistency
registry.
