# Increment 464 — Zotero citation conversion for the LibreOffice adapter (backlog #33/#34, P2 item #22 — the final item in this track)

## Implemented

Sixth and last item in the confirmed P2-leapfrog roadmap (#19 → #17 → #20 → #21 → #18 → **#22**; memory
`callosum-p2-leapfrog-roadmap`, now updated to mark the track fully closed). Roadmap #22's checklist names
Zotero/Mendeley/EndNote/Word-native/plain-text detection; the competitive-review doc confirmed only **Zotero**
has documented first-party LibreOffice integration (Mendeley Cite is Word-only; EndNote's LibreOffice support
is undocumented) — Cliff confirmed narrowing v1 to **Zotero only**.

**Format verified from Zotero's own open-source `zotero-libreoffice-integration` repo** (`Document.java`/
`ReferenceMark.java`) plus its KB docs, per Cliff's explicit direction to research before building rather than
reverse-engineer a sample file (his own non-default choice among the two options offered):

- Zotero's default LibreOffice storage is a Writer **ReferenceMark** whose **name** (not content) is
  `ZOTERO_ITEM CSL_CITATION {json} RND<10-char-random>` — the full CSL-JSON citation-cluster payload is
  self-contained in the name; no live Zotero connection is needed to read it. This exactly matches the literal
  `"ZOTERO_ITEM CSL_CITATION {}"` this codebase's own `test_decode_rejects_foreign_and_malformed` test already
  assumed as "another tool's mark" — independent corroboration the assumption was right.
- `citationItems[].itemData` is the **full CSL-JSON bibliographic record** (title/author/issued/DOI/
  container-title/type), not a stub requiring a live Zotero lookup. `locator`/`label`/`prefix`/`suffix`/
  `suppress-author`/`author-only` are the exact same key names callosum's own `_ITEM_DEFAULTS` uses.
- The **fallback** is Bookmarks (`ZOTERO_BREF_<opaque>`), used only when a document format can't hold reference
  marks or the user explicitly switches Zotero's preference. The observed bookmark names are short/opaque — the
  data isn't self-contained in the name the way ReferenceMarks are, and the real storage mechanism isn't
  corroborated from public sources. **Declared out of scope for v1** — detected and reported, never parsed.
- Zotero's bibliography is a Writer **TextSection** named with the same scheme: `ZOTERO_BIBL <data>
  RND<random>`.

### New backend endpoint: `POST /citations/zotero/resolve`

New router `app/backend/api/routers/zotero_citations.py` (`citations.py` was already at 595/600 — no room, and
this is a distinct concern: resolving/creating papers from *embedded document metadata*, not rendering). Takes
a list of `{item_data, uris}` (bounded `MAX_ZOTERO_DISTINCT_WORKS=300`); for each, matches an existing library
paper via the unchanged `find_existing_paper_by_identity` (DOI → zotero-key parsed from a `zotero.org/.../
items/<key>` URI → title/year/first-author), or creates a metadata-only paper via a new
`normalize_zotero_csl_item` (`app/backend/importers/zotero.py`, sibling to the existing `normalize_zotero_item`
— simpler, since `itemData` is already CSL vocabulary, no `ZOTERO_TYPE_TO_CSL` translation needed). Auto-added
papers get `imported_source="zotero"`/`processing_tier="metadata-only"` — the exact trust posture the existing
Zotero *library* importer already uses for the same self-asserted metadata. **No egress** — every match/create
is a local SQLite read/write over data already embedded in the open document.

### Adapter: `adapters/libreoffice/callosum_cite.py`

`_decode_zotero_mark_name` — the inverse of Zotero's naming scheme, defensive like `decode_mark_name` (any
parse failure → `None`, never raises). `_zotero_citations_in_order` mirrors `scan_citations_in_order`, reusing
the already mark-agnostic `_citation_context` to classify inline vs. note-style placement. `_zotero_bookmark_count`
and `_zotero_bibliography_section` detect the two other Zotero-authored artifacts.

`zotero_conversion_scan` (read-only) + `convert_zotero_citations_interactive`: scan → an explicit confirm
dialog naming exactly what will happen (citations to convert, note-style/Bookmark-mode counts left unconverted
and why, whether the bibliography will be replaced) → one `POST /citations/zotero/resolve` call for every
distinct cited work (deduped by a JSON fingerprint of `itemData`) → for each inline Zotero mark (processed by
held object reference, in document order): remove it and its wrapped text (the exact
`mark.getAnchor().getText().removeTextContent(mark); cursor.setString("")` pattern already used for callosum's
own marks during placement conversion), then `insert_citation_items` at that position with the resolved
`paper_id` plus any locator/label/prefix/suffix/suppress-author/author-only carried straight over (same CSL key
names, no renaming). If a Zotero bibliography TextSection is found, its content is cleared and the section
removed, then `refresh(doc, base, bib_cursor=..., update_citations=False, update_bibliography=True)` — the exact
engine call `insert_bibliography_here_interactive` already uses — creates a callosum-managed bibliography at
that position. Registered as `_ACTIONS["convertZoteroCitations"]`, macro `CallosumConvertZoteroCitations`, and
a new Addons.xcu menu node "Convert Zotero citations…".

## Key technical detail

**Grouped Zotero citations convert as one grouped callosum citation, not N separate ones.** A Zotero cluster's
`citationItems` can hold more than one work (e.g., `(Smith 2020; Jones 2019)`); the conversion loop builds one
`items_payload` list per Zotero mark covering every one of its items and passes the whole list to a single
`insert_citation_items` call, so the resulting callosum citation preserves the grouping rather than exploding it
into separate adjacent citations.

**A resolve item that fails to match any distinct work is skipped, not partially inserted.** If any single item
in a Zotero cluster can't be resolved (shouldn't happen in practice, since every distinct fingerprint sent gets
a response, but defensively checked), the whole cluster's mark is left untouched rather than inserting a
citation missing one of its sources.

**A real fixture gap, not a code bug, was caught by the first real-UNO run.** The spike's first draft tried to
prove the "matches an existing library paper" path against the shared `p1` fixture paper (`run_roundtrip.py`'s
`seed_db()`), fetching its DOI via `fetch_csl` and expecting the resolve call to find it. It didn't — instead
of matching, it created two brand-new papers. The root cause: `seed_db()` calls `create_paper(conn,
title=VASWANI["title"], csl_json=VASWANI)`, passing only `title=`/`csl_json=`, never the separate `doi=`/
`year=`/`first_author_family_name=` keyword params `create_paper` also accepts — so `papers.doi` (and `year`/
`first_author_family_name`) are **NULL** for both shared fixture papers even though their `csl_json` blob
happens to carry a DOI. `find_existing_paper_by_identity` matches against the real DB **columns**, not the
`csl_json` blob, so it correctly found no match — the resolve logic was right; the test's assumption about the
fixture was wrong. Rather than touching the shared seed fixture (used by 25+ other spikes, out of scope for a
minimal diff), the spike was redesigned into two independent, fixture-independent documents: doc A cites a
brand-new work and must auto-add it; doc B, a wholly separate document, independently cites the *same* work and
must resolve to the exact paper doc A just created rather than creating a duplicate. This proves the real
`find_existing_paper_by_identity` DOI-match path end-to-end without depending on the shared fixture's
incompletely-populated columns — and is arguably a more realistic proof anyway (two separate authoring
sessions citing the same source, the real scenario the match path exists to handle).

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-08-09_zotero-citation-conversion.md` — new endpoint, zero
  egress (statically confirmed by grep), unreachable via the cite-only cloudflared tunnel allowlist (confirmed
  against the real `adapters/googledocs/cloudflared-config.yml` regex), bounded (300 distinct works
  server-side, 500 marks client-side, both disclosed on truncation), defensive decode/normalize on untrusted
  document content (rule #4).
- **QA route**: `.claude/qa-routes/route_34_citations_engine.md`'s existing `/citations*` wildcard already
  covered the new endpoint (confirmed via `build_surface_map.py check`, 387→388 surfaces, 0 uncovered) — added
  a standing-assertion bullet + a new manual Writer step (#22) naming the real end-to-end caller
  (`run_roundtrip.py`), the route_39/route_42/route_51 precedent.
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #22 marked **✅ CLOSED inc 464** — the whole P2-leapfrog track is
  now closed (all 6 items, inc 459 through inc 464).
- Memory `callosum-p2-leapfrog-roadmap` updated: item #22 closed, track marked complete, "how to apply" no
  longer names a standing next item.
- `.claude/CLAUDE.md`: counter bumped to 464; pytest count updated to the actual measured total.

## Manual verification script

1. In Writer, hand-build (or use a real Zotero-cited document, if one becomes available) a document with a few
   `ZOTERO_ITEM CSL_CITATION {...}`-named ReferenceMarks — some carrying a DOI that matches an existing library
   paper, some carrying a brand-new DOI/title — plus a `ZOTERO_BIBL ...`-named TextSection and (optionally) a
   `ZOTERO_BREF_...` bookmark to prove the disclosed boundary.
2. Run **Convert Zotero citations…**. Confirm the pre-mutation dialog names exact counts before anything
   changes.
3. Confirm the matched citation keeps the existing paper's identity (no duplicate created), the unmatched one
   creates a new metadata-only library paper from its embedded metadata, and Bookmark-mode/note-style citations
   (if present) are left untouched and named in the summary.
4. Confirm Zotero's bibliography is replaced with a callosum-managed one, and every existing command (refresh,
   edit citation, Citations in this document, etc.) still works unchanged on the converted document.
5. Cancel the confirm dialog on a second run and verify nothing in the document changes.

## Verification

- `pytest tests/test_zotero_citations.py tests/test_libreoffice_adapter.py tests/test_zotero_importer.py -q` →
  **196 passed** (8 new backend resolve/normalize tests, 9 new adapter decode/scan/orchestration tests, all
  UNO-free via monkeypatching).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: all 502 application-source files within the 600-line cap (new router
  file `zotero_citations.py` is well under it).
- `python tools/qa/build_surface_map.py check`: `API surfaces: 388 | covered: 388 | uncovered: 0`.
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — `spike_zotero_citation_conversion` builds two real
  Zotero-shaped documents (no live Zotero install was available, so both are hand-built directly from the
  verified naming/payload scheme). **Doc A** (one new citation + a malformed mark + a Bookmark-mode anchor + a
  Zotero bibliography) proved: the scan found exactly 1 convertible citation / 1 malformed / 1 Bookmark-mode /
  1 bibliography; conversion created library paper **4** from the citation's own embedded CSL-JSON, correctly
  reported the skipped Bookmark-mode citation, and replaced Zotero's bibliography with a callosum-managed one.
  **Doc B** (a separate document citing the identical work) proved the match path: it resolved to the *same*
  paper 4 (`"0 newly added"`), not a duplicate. `SELFTEST OK`, exit 0. (The run's first attempt caught the real
  fixture-gap finding above before this final, passing form.)

## Rollback

Revert the new router (`app/backend/api/routers/zotero_citations.py`, its mount in `app.py`), the new
`normalize_zotero_csl_item` in `app/backend/importers/zotero.py`, the new adapter functions/action/macro in
`adapters/libreoffice/callosum_cite.py`, and the new Addons.xcu menu node to their pre-464 state. All changes
are additive/backward-compatible; no schema/migration; nothing about the existing Zotero *library* importer or
any other citation command was touched.
