# Increment 131 — Retraction producer (SP1: Crossref + OpenAlex), the first findings producer

## Implemented

The first real producer feeding the inc-130 findings contract. For each library paper's DOI, query **multiple
sources** (Crossref + OpenAlex in SP1) for a retraction / correction / expression-of-concern, **merge** them,
and persist a **FACT** (the Review-pane FactMark + the ◆-fact card mark) plus an honest per-paper **check status**
(silence ≠ clean) that also powers a library **"Retracted" filter**. The user asked for *all three* sources
("critical to know before citing"); SP1 ships the per-DOI two-source core via the existing audited adapters, SP2
(inc 132) adds the Retraction Watch DB bulk source as a third checker.

- **Core (`app/backend/methods/retraction.py`, new — pure, testable):** `RetractionSignal` (one source's verdict),
  `merge_signals` (escalate `concern < correction < retracted`, keep the richest non-null detail, list **all**
  flagging sources, derive `notice_url` from `notice_doi`), `RetractionOutcome`, `detect_retraction` (no DOI →
  `unchecked` and **no source is consulted**; else run each checker **best-effort** — a source raising is skipped,
  never aborts — and merge), `apply_retraction` (write the FACT via `upsert_findings` when flagged, else
  `upsert_findings(...,[])` to **supersede** a stale FACT; always a check-status row). Checkers are injected
  (`RetractionChecker(source, fetch)`) → hermetic.
- **Source checkers:** `CrossrefClient.lookup_retraction` parses the **raw** `message.update-to` (the
  Retraction-Watch-fed relation a retracted item carries pointing at its notice) → `{status, nature, date,
  notice_doi, notice_url}`; `OpenAlexClient.lookup_retraction` reads the work's `is_retracted` boolean
  (corroboration). The type→status map lives **locally in each adapter** (no import from `methods` → no cycle).
- **Persistence:** `signals_repo` gains `store_retraction_status` / `count_retraction_flagged` /
  `get_retraction_status` on the existing `open_science_signals` table (`signal_type="retraction"`; status ∈
  retracted/correction/concern/none/unchecked; sources + checked_at in `evidence_snippet`). **No migration** (the
  FACT reuses inc-130's `paper_findings`; the status reuses inc-97's `open_science_signals`).
- **Endpoints (`routers/methods.py`):** `GET /papers/{id}/retraction` (read the stored status — read-only, no
  network), async `POST`/`GET /methods/retraction/run` (batch over `list_live_paper_ids` via
  `app.state.retraction_checkers`), `GET /methods/retraction/summary` (the chip count). `app.state` gains
  `retraction_jobs` + `retraction_checkers` (the defaults are the real Crossref+OpenAlex wrappers; tests/headed
  runs override them → offline).
- **Library filter:** `repository.SIGNAL_FILTERS["retraction-retracted"] = ("retraction", "retracted")` →
  `GET /papers?signal=retraction-retracted` (one allowlist line; bound IN-subquery; reuses the inc-97 mechanism).
- **Frontend:** a retraction-aware **FactMark** (status label + a **notice** link, red for retracted / amber for
  correction/concern) in the METHODS "Review" section; a library-wide **"Check all papers for retractions"** batch
  + a per-paper **status line** ("checked — none found" / "unchecked — no DOI" / "not yet checked"); an inc-100-
  style **"⚠ N retracted"** header chip + the **Retracted** filter view + banner. Tokens-only CSS.

## Key technical detail

**Two homes, complementary (mirrors statcheck's dual nature).** The FACT in `paper_findings` is the rich
reviewable surface (FactMark + ◆ card mark); the status row in `open_science_signals` is the **honesty record** +
the filter. A clean paper has a `none` status and **no** finding; a no-DOI paper has an `unchecked` status and no
finding; only a flagged paper gets a FACT. This is what makes *silence ≠ clean* expressible — findings alone
can't say "checked and clean" (there's no row when there's nothing to find).

**No accusation, by construction.** A retraction is relayed verbatim from the registry (no LLM, no inference);
the FACT links the **notice** + names the flagging `sources`; the chip is a **filter** count, never a rank or an
author-level signal. The declined easy paths (an "author has N retractions" reputation score; treating unchecked
as clean) are recorded in the audit. Principles gate run — aligned with #1/#2/#3/#4/#6/#7/#8 + the A-A
no-accusation veto.

**`notice_url` is derived-only** (`https://doi.org/<notice_doi>`), never a URL taken verbatim from the response
and never server-fetched — so there's no SSRF surface; it's a client-side link (`target=_blank rel=noopener`).

## Manual verification script

1. Seed three papers' outcomes via the real `apply_retraction` (offline — build the outcomes by hand): A
   retracted (notice + 2 sources), B `none`, C `unchecked`. (See `.local/visual/drive_inc131_retraction.py`.)
2. Start the app (egress unset), open `/`. A red **"⚠ 1 retracted"** chip shows; A's card has the ◆-fact mark.
3. Click the chip → the library filters to A (banner "verify before citing"); clear restores.
4. Open A → METHODS → **Review**: the **retraction FactMark** ("⚠ Retracted") with a working **notice** link.
5. Open B → "Retraction: checked — none found (crossref, openalex)". Open C → "Retraction: unchecked — no DOI".

Automated equivalent: `.local/visual/drive_inc131_retraction.py` — **PASS**, 0 console/page errors, **0 genai
hits** (fully offline; the batch button's network path is unit-tested with injected checkers instead).

## Pytest

**493** (478 → +15 `test_retraction.py`: merge [3], detect [4: no-DOI/clean/one-flag/raising-skip], apply [4:
retracted/clean/un-retraction-supersede/unchecked], the Crossref + OpenAlex checkers [3], the endpoints+filter
[1]; route-surface extended in `test_health.py`). `ruff` clean. QA surface **98/98 API + 504/504 FE, 0 uncovered**
(`route_39_retraction.md`). Audit `.claude/security-audits/2026-06-26_retraction.md` **PASS**.

## Next

**SP2 (inc 132): the Retraction Watch DB** as the third checker — a `retraction_records` table + a download/index
"refresh database" job + `RetractionWatchChecker` (the merge layer already accepts it as another checker, so SP2
is additive). Also deferred: an on-import auto-check (piggyback the enrich's cached Crossref response) and
automatic TTL expiry (SP1 = explicit refresh, with `checked_at` recorded). Then statcheck/p-curve/GRIM can
optionally emit candidates into the same findings store.
