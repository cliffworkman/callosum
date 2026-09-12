# Increment 595 — Reader "Find referenced paper…" (transient selection → resolve → add)

Select the text of a cited reference in the PDF reader, click **🔎 find paper**, and Callosum resolves it to a
scholarly record, shows the candidate(s) for confirmation, and — on an explicit click — adds it through the
**existing** canonical Library ingestion + OA-acquisition path. Deliberately transient: no highlight, no
annotation, no new reference DB, no parallel add pipeline. Built as a thin vertical slice after a Phase-1 code
trace confirmed the primitives already compose (cost gate PASS).

## Implemented
- **`app/backend/discovery/crossref_provider.py`** — `bibliographic_search(query, limit)` + `_httpx_bibliographic`:
  Crossref `query.bibliographic` (tuned for full-citation strings, unlike the general `query=` the discovery
  provider uses), reusing `message_to_item`, `bounded_get(METADATA_RESPONSE_CAP)`. Transport stays **inside the
  provider boundary**; errors PROPAGATE so the resolver can tell "no match" from "lookup failed".
- **`app/backend/metadata/reference_resolver.py`** (new, pure composition) — `normalize_reference_text` (NFKC +
  whitespace collapse + trailing-punct strip + 2000-char bound; no dehyphenation/reconstruction),
  `resolve_reference` (DOI-first via `find_doi_in_text` + injected `CrossrefClient.resolve_doi`; else
  `bibliographic_search` gated by `_plausible`), dedup via `find_existing_paper_by_identity`. Read-only; injects
  `crossref_client` + `bib_search` for hermetic tests.
- **`app/backend/api/routers/reference_lookup.py`** (new) — `POST /references/resolve` (mounted in `app.py`).
  Composes the resolver; creates nothing.
- **`app/frontend/js/30h_reference_finder.jsx`** (new) — `ReferenceFinderModal` + `ReferenceCandidateRow`.
  Snapshots the selected text at open, editable + re-lookup, renders the four states, and on confirm calls the
  existing `POST /discovery/save` then `POST /papers/{id}/acquire-oa`.
- **`app/frontend/js/30g_pdf_selection.jsx`** — extracted the `hl-picker` popover into a `SelectionPicker`
  component (rule #1: freed the line the new button needed in the at-cap `30_viewer.jsx`) and added the
  **🔎 find paper** action.
- **`30_viewer.jsx`** (wire only: `refFinder` state, `SelectionPicker`, `ReferenceFinderModal`, `onOpenPdf`
  threaded), **`30c_frame.jsx`** (pass `onOpenPdf` to `PdfViewer`), **`styles.css`** (`hl-find-ref` shares the
  `hl-note-add` recipe; a small `reffind-*` block reusing the `axis-modal`/`gap-row`/`--verified`/`--flag`
  vocabulary).

## Key technical detail — four inspectable states, not a confidence score
`classification ∈ {identifier_match, one_candidate, multiple_candidates, none}` (+ a separate `error` for a
lookup that couldn't COMPLETE). A DOI in the selection = the exact `identifier_match` route. Free-text results
are gated by **inspectable component agreement** (`_plausible`): a title-token overlap (≥2 significant tokens or
≥50% of the candidate title), OR both an author surname AND the year appearing in the selection (so bare
"Author (year)" selections, which carry no title, can still resolve). This suppresses obviously-unrelated
Crossref hits (Crossref returns *something* for any query) without a synthetic score and without ever
auto-picking — the actual candidate(s) are always shown; the human confirms.

## Amendment-driven design decisions (all 10 folded in)
- **No repurposed provenance / one canonical add path (1, 6):** confirm unifies on `POST /discovery/save`
  (`discovery-import`, deduped in `run_write`, then background-enriched from the DOI). No new/overloaded
  `imported_source` value; no change to `save_item`.
- **Minimal candidate contract (5):** title/authors/year/venue/doi/url/in_library/existing_paper_id — **no
  abstract** (background enrichment fills the full record from the DOI).
- **Transport in the provider boundary (3);** **conservative normalization only (4);** **snapshot + stale-response
  guard (7)** (modal holds its own text; `reqRef` token discards a superseded response); **recoverable extraction
  (8)** (editable text + Look-up-again); **explicit egress (9)** (resolve fires only on the click, never on
  selection; the modal states it queries Crossref).

## Reused primitives (no new subsystem)
`find_doi_in_text`/`DOI_PATTERN`/`normalize_doi`, `CrossrefClient.resolve_doi`, `message_to_item`,
`find_existing_paper_by_identity`, `save_item`/`/discovery/save` (+ its background enrich), `acquire_oa_start`
(`/papers/{id}/acquire-oa`), `bounded_get`, the `axis-modal`/`gap-row` CSS recipes, the `onOpenPdf` tab-open.

## Principles gate (rule #9)
Produces a **candidate, not a fact** ("facts ≠ candidates"): the resolver is deterministic (Crossref match, not
an LLM), never silently chooses (`multiple_candidates` = a chooser with no pre-selection; `none` says so),
always shows the candidate for the human to confirm ("the human is the filter / the AI is the funnel"), carries
provenance (Crossref; `discovery-import`), and surfaces **no** opaque composite score. Egress posture matches
the existing Discover → Search (public bibliographic lookup, not the Gemini gate). The misaligned easy path —
auto-adding the top Crossref hit — is declined by design.

## Experience pass (rule #11) — inline
- **Reception:** the action lives in the selection popover the user already uses for highlighting; the modal
  states plainly that it queries Crossref and then adds via the normal import.
- **Intended use (the "deadline citer" vetting/collecting a cited reference):** select → find → confirm → added
  with OA started; a bad PDF extraction is editable in place; an already-held reference is surfaced with **Open**
  (no duplicate); a no-match says so and invites a refined lookup.
- **Owed:** a live persona-grounded run against the packaged reader (native window, not scriptable here) — see
  Manual verification. A vigilance check: the flow only *adds* legitimately-resolved records + legitimate OA; it
  introduces no accusation, paywall circumvention, or opaque score.

## Manual verification script
1. `python tools/run_dev.py` (or the packaged app); open a paper in the reader.
2. Select a full reference from the bibliography → confirm the popover shows **🔎 find paper**; confirm selecting
   alone issues **0** `/references/resolve` requests (network panel).
3. Click it → the modal opens and runs one lookup. A DOI-bearing selection → one exact candidate; a full
   citation → one/multiple candidates; ordinary prose → "No defensible match".
4. Confirm a novel candidate → it appears in the Library (`discovery-import`) and OA acquisition starts; confirm
   an OA failure still leaves the record. An already-held reference shows **✓ In your library** + **Open**.
5. Edit a garbled selection in the modal and **Look up** again → resolves.

## Gates
- **Pytest:** `tests/test_reference_lookup.py` — **15 passed, 1 skipped** (the real-Crossref smoke is
  developer/manual, non-gating). `tests/test_discovery.py` + `tests/test_acquisition.py` + the new file:
  **59 passed, 1 skipped**. `tests/test_frontend_assembly.py`: **87 passed**.
- **QA (rule #10):** `route_94_reference_lookup.md`; `build_surface_map.py check` → API 440/440 covered (the
  `POST /references/resolve` hard gate passes).
- **Security audit:** `.claude/security-audits/2026-09-12_reference-lookup.md` — **PASS**.
- **Line budget:** all files under the 600 cap (`30_viewer.jsx` 599 after the picker extraction). Ruff check +
  format clean.

## Not built (deliberate scope boundary)
No persistent highlight/anchor, no reference-list reconstruction, no multi-provider fallback (Crossref only),
no citation graph. Whether this graduates into the reference-extraction/citation-graph tracks (legacy #23/#25)
is left as a follow-up recommendation, not built here.
