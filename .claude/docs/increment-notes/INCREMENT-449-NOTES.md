# Increment 449 — Semantic Scholar recommendations, a third beyond-library Cite source (backlog #30)

## Implemented

Work → Cite's opt-in "Also search beyond my library" feature (backlog #30, Track C) had two candidate channels:
a Crossref/PubMed/OpenAlex keyword-search fan-out, and OpenAlex citation-graph neighborhood expansion (referenced/
related/citing works) anchored on the user's top in-library Cite matches. This increment wires in the backlog's
last genuinely-open item: Semantic Scholar's `/recommendations` API as a third source.

Verified live before building: `GET https://api.semanticscholar.org/recommendations/v1/papers/forpaper/DOI:{doi}
?fields=title,abstract,year,authors,externalIds,venue,url&limit=N` works with a real DOI, returns
`{"recommendedPapers": [...]}` (a single-call endpoint, no pagination cursor — unlike the existing client's
`graph/v1` citations/references edges). A bad/unknown DOI returns a clean `404`.

**`integrations/semantic_scholar/adapter.py`** (161 → 260 lines) gains `S2_RECOMMENDATIONS_BASE_URL`,
`MAX_S2_RECOMMENDATIONS_FETCH = 20`, a `RecommendedPaper` frozen dataclass, a second injectable
`recommendations_fetcher` field on `SemanticScholarClient` (a different base URL than the existing `fetcher`),
a shared `_valid_doi()` helper (factored out of the existing DOI normalize+regex-match one-liner, now used by
both `_fetch_edge` and the new method), and `fetch_recommendations(conn, doi, *, limit=10) ->
list[RecommendedPaper]`. It always fetches+caches the fixed `MAX_S2_RECOMMENDATIONS_FETCH` cap (a
limit-independent cache entry keyed `recommendations:{doi}`) and slices to the caller's `limit` at return time —
mirroring `_fetch_edge`'s own fetch-then-cap pattern. A 404/non-200/exception returns `[]` **uncached**, matching
`_fetch_edge`'s existing posture: a permanently-unindexed DOI stays retryable, same as a transient failure.

**`app/backend/citations/beyond_library.py`** (402 → 465 lines) gains `MAX_S2_RECOMMENDATIONS_PER_ANCHOR = 5`, a
`semantic_scholar_client` param on `suggest_beyond_library` (defaulted internally exactly like the existing
`openalex_client` param), and a new `_s2_recommendation_items()` function mirroring `_neighborhood_items`'s
per-anchor loop shape. `_relation()` gains one label:
`"recommended_alongside_local_match": "Recommended by Semantic Scholar alongside a locally relevant paper"`.
`app/backend/api/routers/citations.py` gained one line threading `request.app.state.semantic_scholar_client`
(already existed since inc 232) through to `suggest_beyond_library` — no `app.py` change needed. The frontend
(`37_cite.jsx`) and the LibreOffice adapter needed **zero changes**: both already render/relay `sources`/
`reason`/`relationship_label`/`anchor_title` generically.

## Key technical detail

**Two real correctness gaps found and fixed while designing the new channel (a plan-review pass, not live
debugging) — neither is a regression in existing behavior, both are choices this increment had to make once a
second graph-neighborhood-style channel existed:**

1. **Relation-collision precedence.** `suggest_beyond_library` builds `relations = {item.dedup_key: relation for
   item, relation in neighbor_items}`. Once S2-recommendations and OpenAlex-neighborhood both anchor on the same
   local papers, the same outside paper can plausibly surface from both — and a naive concatenation into one dict
   comprehension would let whichever pair happens to be processed last silently win, with no visible trace that a
   second signal even existed. Fixed by merging deliberately: `relations = {**s2_pairs}; relations.update(
   {**openalex_pairs})` — the verifiable OpenAlex graph-fact relation (`cites`/`cited_by`/`related_to`) always
   wins the collision over S2's opaque algorithmic "recommended alongside," honoring commitment #8
   (inspectability over authority) rather than accidental ordering. Proven by
   `test_suggest_endpoint_openalex_relation_wins_collision_with_s2`.
2. **Per-anchor failure isolation.** The existing `_neighborhood_items` has a real (pre-existing, out-of-scope)
   design smell: its per-anchor `try/except` doesn't actually isolate anchors — the first anchor whose OpenAlex
   calls raise causes an early `return`, so every anchor *after* it is never attempted even if it would have
   worked fine. The new `_s2_recommendation_items` deliberately does NOT replicate this: each anchor's
   `fetch_recommendations` call is wrapped in its own `try/except` that `continue`s to the next anchor on
   failure, accumulating a `"partial"` status only if any anchor actually failed. Empirically verified end-to-end
   (not just asserted): with anchor 1 raising and anchor 2 succeeding, `source_coverage` honestly reports
   `"partial"` with the real exception message, and anchor 2's legitimate candidate still reaches the response —
   see `test_suggest_endpoint_s2_recommendation_failure_on_one_anchor_does_not_drop_others`.

**Principles-gate note (rule #9, commitment #7 — no opaque composite scores).** Semantic Scholar's recommendation
ranking is its own black-box algorithm. `_parse_recommendations()` parses only public paper metadata
(title/abstract/year/authors/venue/url/external-ids) — no score, rank, or relevance value S2 might return is ever
parsed, stored, or exposed. The visible ranking a user sees stays exactly the pre-existing, fully-transparent
`metadata_overlap` term-Jaccard float plus the named-mechanism relationship label, matching the existing
`related_to_local_match` precedent of naming a provider-computed relation as such because it's opaque (unlike the
objectively-verifiable `cites`/`cited_by` graph edges, shown without that caveat).

## Housekeeping / gates

- **Security-audit addendum** appended to `.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`
  ("Addendum — Semantic Scholar recommendations") — one new bounded external fetch path, reused DOI-validation/
  fail-closed/env-key posture, explicit confirmation no S2-internal score is ever parsed/exposed, both correctness
  fixes documented as Principles-gate items.
- **QA route extended, not forked** — `route_42_cite.md` gained an updated egress-provider line, a new
  adversarial-checklist bullet (an S2-unknown anchor DOI → clean 404-handled miss), and a Step-5 example of the
  new relationship label.
- **`THIRD-PARTY-NOTICES.md`** — broadened the existing Semantic Scholar credit's scope (no new entry; per
  `CREDIT-THE-LINEAGE.md`, beyond-library's three sources are data sources, not reimplemented methods, so no new
  lineage entry or `MethodCreditButton` either — matching the existing uncredited-in-panel posture of Crossref/
  PubMed/OpenAlex there today).
- **`help_content.md`** updated (provider list + relationship-label examples); `changes.md`'s
  `HELP-DOCS-SYNCED` marker moved forward.
- **Backlog #30 updated** — the Semantic Scholar recommendations item moves from "still genuinely open" to
  shipped; the persistent-dismissible-cache-surface and Stage-4 section-scoping items remain open.

## Manual verification script

1. Select a library paper with a real DOI (or seed one). Open Work → Cite, paste a sentence matching that paper.
2. Check "Also search beyond my library," click Suggest.
3. Confirm a card labeled "Recommended by Semantic Scholar alongside a locally relevant paper: `<anchor title>`"
   renders alongside the existing OpenAlex-neighborhood/keyword-search cards, with no bare/opaque S2 score
   anywhere on it.
4. Confirm unrelated existing cards (OpenAlex-neighborhood `cited by`/`cites`/`related to`, keyword-search) still
   render correctly.
5. Confirm the LibreOffice adapter's "Suggest citations" macro also surfaces the new source with no adapter-side
   code change (it rides the same `/citations/suggest` endpoint).

## Verification

- `pytest tests/test_semantic_scholar_recommendations.py tests/test_citations_suggest.py
  tests/test_citation_context.py tests/test_help.py -q` → **all 47 passing** (7 new client tests + 3 new
  endpoint tests + 14 existing citations-suggest tests + 9 existing citation-context tests + 14 existing help
  tests).
- `python tools/check_line_budget.py`: all application-source files within the 600-line cap.
- `ruff format` + `ruff check` on every touched file: clean.
- No schema/migration change; no `app.py` change; no frontend change (verified by full read of `37_cite.jsx` and
  the LibreOffice adapter before starting — confirmed unnecessary, not just assumed).

## Rollback

Remove `fetch_recommendations`/`RecommendedPaper`/`recommendations_fetcher`/`_valid_doi` from
`integrations/semantic_scholar/adapter.py` (or just stop calling the new method — `_fetch_edge` is unaffected);
remove `_s2_recommendation_items`/the `semantic_scholar_client` param/the collision-ordering merge and the new
relation label from `beyond_library.py`; remove the one-line kwarg in `routers/citations.py`. No schema/migration
to reverse. DOAJ/Crossref/PubMed/OpenAlex-neighborhood beyond-library behavior is otherwise untouched.
