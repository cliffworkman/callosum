# Increment 73 Notes — Import author/index keywords as first-order tags (Crossref `subject`)

Privilege the concept work authors/indexers already did: capture **Crossref `subject` categories** as
**first-order tags** (the inc-72 c-TF-IDF suggester is the second-order gap-filler; Zotero tags already
import via inc 71). **No migration, no new endpoint, no new dependency.**

## Implemented
- **`integrations/crossref/adapter.py`** — `_crossref_message_to_csl` now captures `message["subject"]` into
  `csl["subject"]` (stripped, non-empty, case-insensitively de-duped, order-preserving via `_subject_list`).
  So `subject` lands in the canonical `papers.csl_json` AND in `CrossrefResolution.csl_json` for the hook.
- **`app/backend/persistence/tags_repo.py`** — `add_tag_to_paper(..., import_source="user")` keyword param
  (set only on **create**; an existing tag keeps its source — a user tag is never relabeled) + a batch
  `add_tags_to_paper(conn, paper_id, names, *, import_source)`.
- **`app/backend/metadata/enrichment.py`** — `CROSSREF_KEYWORD_SOURCE = "keyword:crossref"` +
  `apply_crossref_subject_tags(conn, paper_id, csl_json)` (additive, idempotent, **never touches metadata**),
  called inside `enrich_paper_metadata_from_crossref` after `update_paper_metadata` — so the existing
  **🔎 re-resolve** and batch enrich auto-tag.
- **`tools/backfill_keyword_tags.py`** (new) — `backfill_keyword_tags(engine, client)`: for each live DOI'd
  paper, `resolve_doi` (cache-first; fetches public Crossref only when uncached — the "full" backfill) →
  `apply_crossref_subject_tags`. **Tag-only** (no metadata clobber), per-paper commit (resumable),
  idempotent, prints a cache/network/tagged summary. (Added to the CLAUDE.md Commands table.)
- **`app/frontend/js/25_detail.jsx` (bugfix)** — `TagsRow` now re-syncs its local tags from `initialTags`
  when the parent refetches the detail (`useEffect([initialTags])`), so **🔎 re-resolve** (same paper id →
  no key-remount) surfaces the new keyword chips immediately. Optimistic add/remove is preserved (p.tags
  identity only changes on a real server refetch). Rebuilt `callosum-app.html`. *(No other UI change —
  keyword tags render as the inc-71 chips; the inc-49 "More" section already hides the list-valued `subject`
  via its `isScalarValue` filter.)*

## Verification
- **pytest 256** (+5): adapter captures/dedupes subject; re-resolve imports subjects as tags + idempotent +
  user-provenance preserved + filterable; `add_tags_to_paper` provenance set-on-create-and-preserved; backfill
  tags from cache **without fetching** (a raising fetcher proves it) + fetches uncached + idempotent +
  metadata-safe.
- **Live E2E** (`.local/keyword_tags_e2e/`, injected fake Crossref returning subjects): 🔎 re-resolve →
  Neuroscience / Vision Science chips appear → click → "Filtered to tag …". **0 console errors.**
- Audit `.claude/security-audits/2026-06-20_keyword-tags.md` — **PASS** (DOI-only to public Crossref, NOT the
  egress gate; tag-only/non-destructive; bound-param; plain-text rendering).

## Manual verification script
1. Open a DOI'd paper → Details → Identifiers → **🔎** → its Crossref subject categories appear as tag chips;
   click one to filter the library.
2. Run `python tools/backfill_keyword_tags.py` over a DB → existing papers gain keyword tags (cache-first;
   re-run is a no-op). Subjects also persist in `csl_json` (canonical record).

## Deferred (the provenance follow-on)
- **Provenance UI:** surface `source` on the tag response; style/group "author keywords" vs "your tags" vs
  system facts; "show only author keywords"; protect imported tags from clobber (likely needs per-link
  provenance). This increment **stores** `import_source` but doesn't surface it.
- Richer sources: **OpenAlex `concepts`**, **PubMed MeSH** (with those adapters). The **tags ↔ findings /
  system-facts** cross-cut (RETRACTED etc.) — see `INCREMENT-BACKLOG.md` + the future-tracks "Tags hook" notes.
