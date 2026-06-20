# Security Audit — Import Crossref subjects as keyword tags (increment 73)

**Date:** 2026-06-20
**Trigger:** A change to the external-fetch **data-capture** path (the Crossref adapter now stores `subject`)
+ a new `tools/` **backfill** that fetches from public Crossref over the library. **No new endpoint, no
migration, no new dependency.**

## What changed
The Crossref adapter now captures `message.subject` into the CSL record; `enrich_paper_metadata_from_crossref`
mirrors those subjects into `keyword:crossref` tags (so the existing **🔎 re-resolve** + batch enrich
auto-tag). A `tools/backfill_keyword_tags.py` applies it across the existing library (cache-first;
re-resolves the rest), tag-only.

## Threat review
- **No new attack surface (no endpoint).** Tags reach the UI via the already-audited inc-71 `tags` field on
  the paper detail. The backfill is a local dev tool, not a request handler.
- **Egress posture (the key point):** the backfill sends **only the DOI** to **public Crossref** for
  bibliographic metadata — exactly as import/re-resolve already do (inc-49 decision). It is **not** the
  library-text egress gate (`CALLOSUM_ALLOW_DATA_EGRESS`, which guards Gemini); no paper text, abstract, or
  user content leaves the machine. Cache-first means most papers incur no network at all.
- **Non-destructive:** `apply_crossref_subject_tags` and the backfill **never call `update_paper_metadata`**
  — they only add `paper_tags`/`tags` rows, so a hand-edited library is safe (additive, idempotent). (The
  re-resolve path does refresh metadata, but that is its existing, user-initiated behavior — unchanged.)
- **SQL injection (rule #3):** all tag inserts/reads are bound-param SQLAlchemy Core; the cache lookup +
  the work-list query are bound-param. Subject strings are bound values.
- **Input/output:** subject strings are trimmed + capped to 100 (the tag layer) and rendered as **plain text**
  React chips (no `dangerouslySetInnerHTML`) — a hostile category string can't inject. The adapter de-dupes
  + drops blanks.
- **Provenance:** `tags.import_source="keyword:crossref"` is set only when a tag is **created**; an existing
  tag keeps its original source (a user tag is never relabeled). Provenance is **per-tag**, not per-link — an
  accepted v1 limitation (per-link provenance is the deferred provenance-UI increment).
- **Resource:** the backfill is sequential, cache-first, per-paper-committed (resumable), bounded by the
  library size; polite to Crossref via the client timeout.

## Negative-path checks (results)
- Adapter de-dupes (case-insensitive) + drops blanks; absent subject → no key
  (`test_crossref_adapter_captures_and_dedupes_subject`). **PASS.**
- Re-resolve imports subjects as tags; idempotent on re-run; a pre-existing user tag of the same name keeps
  `user` provenance (`test_reresolve_imports_crossref_subjects_as_keyword_tags`,
  `test_import_source_provenance_set_on_create_and_preserved`). **PASS.**
- Backfill tags **from cache without fetching** (a fetcher that raises if called proves it); fetches when
  uncached; idempotent; **paper metadata untouched** (`test_backfill_keyword_tags.py`). **PASS.**
- **Live E2E** (`.local/keyword_tags_e2e/`, injected fake Crossref): 🔎 re-resolve → keyword chips appear →
  filter the library. **0 console errors.** **PASS.**

Full suite: **256 passed** (+5). No new dependency; no migration; no new endpoint.

**Security Audit: PASS.**
