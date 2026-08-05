# Security audit: beyond-library citation suggestions

Date: 2026-07-11

## Scope

`POST /citations/suggest` gained an opt-in `include_beyond_library` mode used by the in-app Cite pane's
**Also search beyond my library** checkbox. The default library-only path remains local.

Changed surfaces:

- `app/backend/citations/beyond_library.py`
- `app/backend/api/routers/citations.py`
- `app/frontend/js/37_cite.jsx`
- `app/backend/help/help_content.md`

## Data egress

Default state: no external metadata search. The existing local embedding/NLI Cite path is unchanged.

Opt-in state: Callosum sends the bounded draft sentence or research description pasted into Cite to public metadata
providers through the existing discovery registry plus OpenAlex work search. It also sends DOI identifiers for the top
local Cite matches to OpenAlex to fetch bounded reference/cited-by/related-work graph neighborhoods. It does not send
PDFs, full manuscript text, notes, private annotations, library excerpts, or generated summaries.

This is metadata-provider egress, not LLM egress. The local stance classifier remains local. If outside-library
stance is shown, it is computed against public abstract text and labeled abstract-level.

## Provider boundary

Providers are allowlisted code adapters, not arbitrary URLs. OpenAlex work search uses the existing
`OPENALEX_BASE_URL` constant; graph-neighborhood expansion reuses the existing `OpenAlexClient`, identifier
validation, and cache-backed bounded methods. Provider failures are isolated into source-coverage rows and do not fail
the local library suggestions.

No commercial provider scraping or licensed-data path was added.

## Write boundary

Outside-library cards do not modify the library by default. **Add to library** reuses the existing `/discovery/save`
endpoint and creates/returns a normal metadata-only library record. There is no auto-insert into manuscripts and no
automatic citation selection.

## Product / judgment boundary

The UI separates **In your library** from **Outside your library**. Outside-library candidates are described as public
metadata candidates; when OpenAlex graph evidence surfaced an item, the card shows the relationship to the local
anchor paper. Metadata overlap is visible as a ranking aid, not a correctness score or recommendation.

No hidden paper confidence score, funding/citation probability, "verified good", or "best citation" language was
introduced.

## Checks

- `pytest -q tests/test_citations_suggest.py` -> 13 passed
- `ruff check app/backend/citations/beyond_library.py app/backend/api/routers/citations.py app/backend/api/app.py tests/test_citations_suggest.py` -> passed
- `python -m compileall -q app/backend/citations/beyond_library.py app/backend/api/routers/citations.py app/backend/api/app.py` -> passed
- `python tools/build_frontend.py` -> passed

Result: PASS.

## Addendum — Semantic Scholar recommendations (backlog #30 Track C), inc 449

### Trigger

A third beyond-library source: Semantic Scholar's `/recommendations/v1/papers/forpaper/DOI:{doi}` endpoint,
anchored on the same up-to-3 top local Cite matches the existing OpenAlex-neighborhood expansion already uses.
One new external fetch path → the audit gate.

### Scope

Changed surfaces (in addition to the ones above, which stay accurate):

- `integrations/semantic_scholar/adapter.py` — new `fetch_recommendations()` method + `RecommendedPaper`
  dataclass + a second injectable fetcher seam (`recommendations_fetcher`, targeting a different base URL,
  `recommendations/v1` vs the existing client's `graph/v1`).
- `app/backend/citations/beyond_library.py` — new `_s2_recommendation_items()` channel + a `semantic_scholar_client`
  param on `suggest_beyond_library`.
- `app/backend/api/routers/citations.py` — one line threading `request.app.state.semantic_scholar_client` (already
  existed on `app.state` since inc 232; no `app.py` change needed) through to `suggest_beyond_library`.
- `THIRD-PARTY-NOTICES.md`, `app/backend/help/help_content.md`.

### Threat review

- **Egress class unchanged.** Identical posture to the existing S2 citation-context feature (already audited,
  `2026-07-01`-adjacent) and to this doc's own existing "Data egress" section above: public bibliographic metadata
  only (a DOI leaves; a recommended paper's title/abstract/authors/venue/url/external-ids return). No PDFs, full
  manuscript text, notes, annotations, or generated summaries. Bounded to at most 3 live calls per beyond-library
  run — one per anchor, each independently cached by DOI, so a repeat run against the same anchors makes zero new
  requests.
- **Input validation / SSRF.** Reuses the existing `_DOI_RE`-backed validator (now factored into a shared
  `_valid_doi()` helper used by both the citation-context edges and the new recommendations method) — a non-DOI
  anchor id makes zero requests. The DOI is fully URL-encoded (`quote(..., safe="")`) into the path; no
  request-shaping user input reaches the URL otherwise. The base host/path prefix (`S2_RECOMMENDATIONS_BASE_URL`)
  is a fixed constant, not derived from any input — matching the existing "allowlisted code adapter, not an
  arbitrary URL" posture this doc's Provider-boundary section already establishes.
- **Fail-closed, retryable.** A non-200 status (including a confirmed-live 404 for a DOI Semantic Scholar doesn't
  index) or a request exception returns `[]` and is **not cached** — identical posture to the existing
  `_fetch_edge`'s 404/error handling, so a permanently-unindexed DOI stays retryable rather than being silently
  cached as "0 recommendations." A per-anchor failure no longer prevents the *other* anchors' independent fetches
  from being attempted (a deliberate improvement over the existing `_neighborhood_items`'s early-return-on-first-
  failure — see `INCREMENT-449-NOTES.md`'s Key technical detail).
- **No new secret, no new dependency.** Reuses the existing optional `CALLOSUM_S2_API_KEY` env var / `x-api-key`
  header resolution already in `SemanticScholarClient.__post_init__`; reuses `httpx` (already present) and the
  shared `integrations/api_cache.py` helper.
- **No SQL written unsafely.** `api_cache.py`'s existing `get_cached`/`put_cached` (bound parameters) is the only
  DB write path this method touches — no new table, no new query shape.

### Principles / A-A vetoes (extended)

- **No opaque composite score (Principles #7) — the load-bearing check for this addendum.** Semantic Scholar's
  recommendation ranking is itself a black-box algorithm. `_parse_recommendations()` parses only
  `title/abstract/year/authors/externalIds/venue/url` from the response — **no score, rank, or relevance field S2
  might return is ever parsed, stored, or exposed.** The visible ranking a user sees stays exactly the existing,
  fully-transparent `metadata_overlap` term-Jaccard float (untouched by this addendum) plus a named-mechanism
  relationship label (`"Recommended by Semantic Scholar alongside a locally relevant paper"`), matching the
  existing `related_to_local_match` precedent of naming a provider-computed (opaque) relation as such — distinct
  from the objectively-verifiable `cites`/`cited_by` graph edges, which are shown without needing that caveat.
- **Collision honesty (Principles #8, inspectability over authority — a real gap fixed in this addendum, not a
  pre-existing regression).** Once a second graph-neighborhood-style channel exists, the same outside paper can
  plausibly surface from both OpenAlex-neighborhood and S2-recommendations for the same anchor. The merge is now
  ordered so the verifiable OpenAlex graph-fact relation displays over S2's opaque one when both apply to the same
  paper — a deliberate choice, not accidental last-write-wins dict-merge ordering. See `INCREMENT-449-NOTES.md`.
- **Gate the boost, not the listing (unchanged posture).** A paper with no S2 recommendation data still appears
  via the other two channels unaffected; S2 is purely additive to the candidate pool, never a filter.

### Negative-path checks (new, `tests/test_semantic_scholar_recommendations.py` + `tests/test_citations_suggest.py`)

- **Non-DOI input → zero requests** — `test_client_validates_doi_and_fails_closed`. ✓
- **404 (a DOI unknown to S2) → `[]`, not cached, retryable** — `test_client_404_not_cached`. ✓
- **Transient exception → `[]`, not cached, retryable** — `test_client_validates_doi_and_fails_closed`. ✓
- **Fixed fetch cap independent of caller's `limit`; result sliced to `limit`** —
  `test_fetch_uses_fixed_cap_independent_of_requested_limit`. ✓
- **Targets `recommendations/v1`, not `graph/v1`** — `test_request_path_and_base_url`. ✓
- **Authors capped at 6** (matching the existing citation-context convention) — `test_authors_capped_at_six`. ✓
- **End-to-end wiring** — `test_suggest_endpoint_includes_semantic_scholar_recommendations`: a real
  `relationship_kind`/`relationship_label`/`anchor_paper_id`/`anchor_title` reach the response, and
  `source_coverage` gains a `semantic-scholar-recommendations` row. ✓
- **Collision precedence** — `test_suggest_endpoint_openalex_relation_wins_collision_with_s2`: the same outside
  DOI surfaced by both channels for the same anchor dedupes to **one** card, showing the OpenAlex relation. ✓
- **Per-anchor isolation** — `test_suggest_endpoint_s2_recommendation_failure_on_one_anchor_does_not_drop_others`:
  one anchor's S2 call raising does not prevent a second anchor's legitimate results from reaching the response;
  `source_coverage` honestly reports `"partial"` with the underlying error, not a silent `"success"`. ✓
- **No opaque score anywhere** — none of the new tests assert on (or the code ever constructs) an S2-internal
  score/rank field; `RecommendedPaper` structurally has no such field to leak. ✓

### Result

**Security Audit: PASS (addendum).** SSRF is closed by the reused DOI-validation + constant-host + full
URL-encoding posture; the recommendations path is fail-closed-but-retryable like the existing citation-context
edges; no S2-internal ranking value is ever parsed or exposed; the two-source collision case now resolves
deliberately rather than by accidental dict-merge ordering. No new secret, dependency, schema, or migration.
Pinned by 13 new tests (7 client-level + 3 endpoint-level, plus the existing 3 endpoint tests re-verified
unaffected) across `tests/test_semantic_scholar_recommendations.py` + `tests/test_citations_suggest.py`.
