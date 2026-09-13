# Increment 597 — Feed "Suggested sources" completeness (GitHub #76 + suggestion-parity invariant)

GitHub #76 asked to consolidate the Feed Suggest modal's separate **bioRxiv Categories** / **medRxiv
Categories** top-level tabs into one **Rxiv Categories** tab with provider subtabs. During planning the user
raised the broader **suggestion-parity invariant**: *every canonical followable feed source kind must be
represented in Suggested Sources, or explicitly exempt with a documented reason; lack of local signal produces
an honest empty state, not absence.* Re-tracing all 8 followable kinds showed the only remaining gap (after the
Rxiv work) was **Europe PMC** — same keyword/query semantics as PubMed — so it joins a shared **Keyword Search**
surface rather than a new top-level tab.

Result: `Journal | Rxiv Categories | Keyword Search | Author`, where **Rxiv Categories** = bioRxiv | medRxiv |
arXiv | PsyArXiv and **Keyword Search** = PubMed | Europe PMC. **Frontend-only; zero backend change.**

## Implemented (`app/frontend/js/30g_feed_suggest.jsx`)
- Top-level `FEED_SUGGEST_TABS` → Journal / Rxiv Categories / Keyword Search / Author. Top-level tabs name the
  *kind of thing*; providers are subtabs.
- **Grouping is presentation-only, not a second taxonomy** (steering constraint 1): two fixed ordered lists of
  canonical kind IDs — `RXIV_KINDS` and `SEARCH_KINDS`. Everything else is **derived from `source_meta`**: the
  subtab label (`_feedProviderLabel` strips the trailing " category"/" keyword"/" search" from the canonical
  label), the category list (`meta.suggestions`), and the category-vs-keyword **mode from `suggestions.length`
  itself** (`_feedIsCategoryKind`) — a real signal already in the canonical contract (a source that ships a fixed
  suggestion list is category-style; one without is keyword-style). No hardcoded provider/category taxonomy.
- The two grouped tabs render a second `tags-srcfilter` subtab row (reuses the theme-aware/responsive primitive)
  + the active subtab's component chosen by derived mode: `FeedSuggestCategories` (bio/med/arXiv) or
  `FeedSuggestQueries` (PsyArXiv/PubMed/Europe PMC).
- `FeedSuggestCategories` generalized: `providerLabel` prop (was a hardcoded `server` bio/med ternary) + a
  human-readable empty state (no silent blanks). `FeedSuggestQueries` generalized: `providerNoun` prop (the
  canonical `source_meta` label) drives the follow note, so PubMed/Europe PMC/PsyArXiv share it identically.
- `styles.css`: one `.feed-suggest-subtabs` rule (a separated nested subtab row, `var(--line)` — theme-aware).

## Following creates the canonical source (no parallel path)
`onFollow(kind, value)` → `followFromSuggest` → `POST /feed/subscriptions {kind, value}`, which accepts any
registered kind (`routers/feed.py:74`). So following an arXiv/PsyArXiv/Europe PMC suggestion produces the exact
same source object as the ordinary Follow flow.

## Testing
- **Suggestion-parity invariant + canonical kind/value** (`tests/test_feed_rxiv_suggest.py`, 3): every followable
  kind (registry kinds + the `followed_author` resolve flow) is in the `SUGGESTION_SURFACE` mapping or an explicit
  `EXEMPT` set (empty today) — a future kind added without a surface fails this; `source_meta` encodes the
  derived category-vs-keyword mode (bio/med/arXiv have `suggestions`, psyarxiv/pubmed/europepmc do not); and
  `POST /feed/subscriptions` stores the exact kind+value for all six suggestable kinds. **These are
  data/contract tests — they do not claim to test tab switching.**
- **Top-level/subtab switching** (steering constraint 2): a real Playwright test using the committed e2e harness
  (`tests/e2e/test_smoke.py::test_feed_suggest_groups_providers_under_kind_of_thing_top_level_tabs`) — opens
  Discover → Feed → Suggest, asserts the four top-level tabs (old per-archive tabs gone), Rxiv Categories → the
  four archive subtabs (arXiv shows its categories), Keyword Search → PubMed | Europe PMC (Europe PMC shows its
  keyword note), zero console errors. **Passes locally in headless Chromium** (runs in CI's `e2e-smoke` job).
- `tests/test_frontend_assembly.py` (87); `tools/build_frontend.py`; line budget (30g 351 ≤600); ruff clean.
- **Remaining manual QA (honest):** light/dark theming of the nested subtab row + exact follow-click round-trips
  at narrow widths — a manual pass against the packaged app, not claimed as automated.

## Principles / scope
Preserves the "suggestions are a plain, inspectable tally of your own library, never a quality/prestige ranking"
posture; no-signal → honest empty state. **No backend change; no second source taxonomy; the canonical registry
stays the source of truth** — the frontend holds only the ordered kind-ID grouping. Europe PMC parity was the
same thin frontend seam (no backend/semantic boundary hit). Audit gate not triggered (no endpoint/fetch/ingest
change). Help corpus updated (Follow-a-source + Suggest descriptions).

## Deferred (separate task — steering constraint 3)
The **0.5.14** release (bump/tag/whatsnew/`desktop-shell-release.yml`) is NOT done here; it begins from fresh
context after #76 lands and CI is green. It will bundle inc 595 (reader Find referenced paper), 596 (reader Ask
this paper), and 597 (#76). The manual installer checks still owed from 0.5.13 (splash #39 / banner #43) and the
reader-modal focus smokes travel with that release task.
