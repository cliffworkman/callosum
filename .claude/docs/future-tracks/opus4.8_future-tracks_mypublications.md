Goal: Build a "My Publications" feature — an automated, aesthetically distinct, pinned axis
populated with the logged-in researcher's own papers. Resolve authorship deterministically
via OpenAlex (preferring ORCID), confirm-and-learn for lower-confidence matches, and keep the
axis current incrementally on import. This feature is LLM-FREE: author disambiguation is
structured-metadata work and must consume zero model tokens.

KEY DESIGN DECISIONS (do not substitute a naive approach):
- Resolution is OpenAlex-first, NOT local name-string matching. OpenAlex already disambiguates
  authors and exposes a canonical works list. Resolve the user to an OpenAlex Author (by ORCID
  if provided, else by name), fetch their works, and intersect with the local library by
  DOI/identifier. Local fuzzy name matching is a LAST-RESORT fallback only for library papers
  that lack a resolvable identifier — flag, never auto-confirm, those.
- Confidence tiers reuse cluster_node_papers.confidence: ORCID/OpenAlex-confirmed members get
  high confidence (auto-included); name-only fallback candidates get low confidence and are
  surfaced as uncertain, awaiting user accept/reject (reuse the existing uncertainty-flag
  pattern, do not invent a new one).
- Confirm-and-learn: PERSIST user accept/reject decisions so a rejected paper is never
  re-proposed on a later match run. Confirmations and rejections both survive re-matching.
- Incremental, not regenerate-on-login. Match once, persist, then update on IMPORT: hook after
  metadata enrichment so each newly imported paper is checked against the profile identity and
  added or flagged. Do NOT rescan the whole library every session.
- Decouple from login. Identity is a PROFILE SETTING (researcher name, additional published-name
  variants, optional ORCID) — do NOT require building a full account/login system first; build
  against the profile so it can be dogfooded now. If multi-user-per-instance login is added
  later, axis visibility can be session-scoped then; leave a comment noting this, but do not
  build session machinery now.

BUILD ORDER:

1. OpenAlex adapter (currently a README stub at integrations/openalex/). Implement an
   OpenAlexClient following the pattern in integrations/crossref/adapter.py: injectable fetcher
   Protocol, httpx, DB-backed caching via external_api_cache, frozen dataclass results,
   key-required (per the integration README — do NOT design it key-optional). Provide:
   resolve_author(orcid | name) -> author id + canonical metadata, and fetch_author_works(author)
   -> work records with DOIs. This is metadata enrichment egress (same posture as Crossref), NOT
   the Gemini library-text egress gate — keep that distinction explicit.

2. Profile/identity store. Add a lightweight profile table (alembic migration): researcher
   display name, a list of additional published-name variants, optional ORCID, and a
   my_publications_dismissed flag (for the deleted-don't-auto-regenerate behavior). One profile
   is sufficient for now (single-user-local); do not over-model for multi-tenant.

3. Axis kind marker. Add a `kind` column to the axes table (alembic migration), default
   'standard', with 'my_publications' as the special kind driving variant styling, pinned
   placement, and the dismissable/no-auto-regen lifecycle. Do NOT fork the axis component —
   reuse existing axis rendering and branch on kind for color/icon/pin.

4. Decisions store. A my_publication_decisions table (paper_id, decision in {confirmed,rejected},
   created_at) so confirm/reject survives re-matching and rejected papers are excluded from
   future candidate sets.

5. Resolver service. Given the profile identity: resolve via OpenAlex, fetch works, intersect
   with library by DOI; write the my_publications axis + memberships with confidence (confirmed
   = high; identifier-less name-only fallback = low/uncertain); exclude anything in the decisions
   store as rejected. Idempotent and incremental.

6. Import hook. In the import/enrichment path (app/backend/metadata/enrichment.py /
   pdf_processing/ingest.py), after a paper's authors/identifiers are known, check it against the
   profile identity and add/flag it to the my_publications axis if matched (respecting the
   decisions store).

7. API (routers, via the existing create_app DI conventions): create/refresh the my_publications
   axis; delete it (sets my_publications_dismissed = true, does NOT remove the profile);
   manually add it (clears the dismissed flag and re-runs the resolver); confirm/reject a
   candidate (writes to decisions store, updates membership).

8. Frontend:
   - Pinned card at the TOP of the axis list, orthogonal to sort/filter (its position is fixed;
     sorting/filtering the list does not move or hide it). Variant color scheme PLUS an
     icon/label — never color alone (accessibility). Show a publication count on its face, and
     let the card double as a one-click "show only my papers" filter toggle.
   - Candidate review UI for low-confidence matches, each showing WHY it matched (name variant /
     ORCID / co-author overlap), with accept/reject — same verification-funnel pattern used
     elsewhere.
   - No-pubs handling with GRANULAR messaging, distinguishing: library empty ("import papers
     first"), no match for identity ("no probable publications found for [name] — check the
     name/ORCID"), and not-yet-run. In the no-match case, render [name] as a link that opens the
     settings modal and focuses the name/ORCID field, with a brief highlight/glow (NOT a blink)
     gated behind prefers-reduced-motion.

CONSTRAINTS:
- Additive. Do not alter existing axis assignment, import, summary, or verification behavior, or
  public API shapes beyond the new endpoints.
- LLM-FREE: this feature makes no model calls and consumes no tokens.
- Migrations via alembic, consistent with the existing schema conventions.

TESTS:
- ORCID-confirmed work in the library lands as a high-confidence member; identifier-less name
  match lands as a low-confidence candidate, not auto-confirmed.
- A rejected candidate is excluded from all future match runs (decisions store honored).
- Importing a new matching paper incrementally adds/flags it without a full rescan.
- Deleting the axis sets dismissed and it does NOT regenerate on next resolve; the manual-add
  button clears dismissed and rebuilds.
- No-pubs profile yields the correct granular message, not a generic empty state.

OUTPUT: a summary of new tables/migrations, the OpenAlex adapter surface, the endpoints added,
and confirmation that no existing path was modified and no model tokens are consumed.

=================================================================================================

Goal: Clicking the pinned "My Publications" card opens a dashboard TAB in the library frame
(the same way opening a PDF does) — an impact dashboard that INTERPRETS and PROSPECTS rather
than cloning Google Scholar. Build in layers; each layer ships and is useful independently.

DEPENDENCIES (from the prior My Publications axis work — if any are missing, report and stop
rather than rebuilding them here): OpenAlex adapter with author resolution + works fetch;
profile/identity store; axes.kind = 'my_publications'; the resolver service; the decisions store.

ORGANIZING PRINCIPLE (anti-bloat): Google Scholar DESCRIBES; this dashboard interprets and
prospects. Progressive disclosure keeps it from overwhelming: Overview -> Domain decomposition
(opt-in) -> Enriched cards -> a bounded Prospection panel. Build and ship in that order.

TAB INTEGRATION: Reuse the existing LibraryFrame tab system (app/frontend/js/30_viewer.jsx,
40_app.jsx). The card's onClick opens a tab via the same path as openPdf, with a dashboard
target type (e.g. { type: 'my_publications_dashboard' }); render the dashboard pane in the
tabs.map branch in place of PdfViewer. The tab stays mounted on switch, like PDF tabs. Do NOT
build a parallel tab system.

OPENALEX DATA (extend the adapter): add counts_by_year, citing works (with citing-author ids +
DOIs), and field/year citation percentile (VERIFY the current OpenAlex work-schema field names
before relying on them). Cache everything in external_api_cache. Compute on an EXPLICIT refresh
action, never on plain tab open. For heavy citing-graph analysis, the OpenAlex bulk snapshot
named in the integration README is the fallback. OpenAlex is key-required and paid — be frugal.

METRICS DENOMINATOR (decided): headline metrics (citations, h-index, i10-index) reflect the
AUTHORITATIVE OpenAlex author record. The paper cards reflect what is locally in the library.
Surface the gap ("34 indexed works, 28 in your library") as an import nudge. Do NOT silently
compute the headline metrics over only the library subset — they would then disagree with
Google Scholar and erode trust.

LAYER 1 — Overview (the tab opens on this):
- Hand-rolled SVG bar chart of publications-by-year, matching the codebase's dependency-free,
  CSS-variable-themed style. Do NOT add recharts/d3.
- Headline metric tiles: citations, h-index, i10-index (authoritative OpenAlex), plus the
  indexed-vs-in-library gap.
- An EDITABLE one-paragraph research summary generated from the user's actual publication
  titles/abstracts via the existing summary generator. Editable, persisted, non-load-bearing.
  This describes the user's own work, so verification is "reads true to me."

LAYER 2 — Domain decomposition (opt-in; this is the differentiator):
- A user-triggered action clusters the user's OWN corpus into sub-axes, reusing
  app/backend/clustering/abstract_clustering.py and the axes / cluster_nodes /
  cluster_node_papers model (sub-axes under the my_publications axis). Show citation counts per
  sub-axis (impact by domain).
- Selecting a sub-axis highlights it (complementary color scheme, same structure) and RE-FILTERS
  the Layer-1 plot and metric tiles to that sub-axis; clicking again deselects and restores all.
  Multi-select allowed.

LAYER 3 — Enriched paper cards (filtered library; user's pubs only):
- Reuse the existing library card. Add: OpenAlex citation count (click -> modal of citing works
  with DOI links, reusing the synthesis citation-routing pattern); field/year percentile (the
  honest impact signal, shown alongside or instead of the raw count); a small citations-by-year
  sparkline (counts_by_year); a self-vs-external citation split (intersect citing-author ids with
  the user's OpenAlex id).
- Optional within this layer: cluster the CITING works (reuse abstract_clustering) to show which
  communities cite each paper.

LAYER 4 — Grounded prospection panel (bounded, kept separate from the impact-reading layers):
- Three graph-derived, VERIFIABLE surfaces — NOT generic AI future-direction bullets:
  * Citation gaps: works that cite the same clusters you cite but that you have not cited (the
    "missing paper" problem applied to your own corpus).
  * Emerging citing-topics: fastest-growing topics among recent works citing you.
  * Candidate collaborators: authors who cite you repeatedly but whom you have never co-authored
    with.
- The LLM's role here is NARRATION ONLY: it may phrase these findings in prose, but every claim
  must trace to the specific papers/authors/trends behind it, surfaced and clickable. No
  ungrounded suggestions. Route narration through the grounded data and the caching/egress
  posture from the token-optimization pass.

CONSTRAINTS:
- Additive. Reuse the LibraryFrame tabs, the library card, abstract_clustering, the axis model,
  and the summary generator. No parallel components.
- Frugal with OpenAlex: explicit-refresh, cached, bulk-snapshot fallback for heavy analysis.
- LLM touches are limited to (a) the editable research summary and (b) narration of grounded
  prospection findings — both grounded and verifiable. No ungrounded generation.
- Ship layer by layer; each layer must be independently functional and must not block on later
  layers.

TESTS:
- The card opens a dashboard tab through the existing tab system and stays mounted on switch.
- Headline metrics reflect the OpenAlex record; the indexed-vs-library gap renders.
- Selecting a sub-axis re-filters the plot and tiles; deselecting restores all pubs.
- A citation-count click opens the citing-works modal with valid DOIs.
- Every prospection surface resolves to real, clickable papers/authors; no claim is unsourced.
- OpenAlex calls are cached and are NOT re-fired on a plain tab open.

OUTPUT: a layer-by-layer summary of what was added, the OpenAlex adapter extensions, the
tab-integration touchpoints, and confirmation that no existing component was forked and that
OpenAlex usage is refresh-gated and cached.
