# Increment 506 — Feed Author-follow bug fixes (closes backlog #61) + co-author exclusion, axis scoping, and library-filter link

## Implemented

### The reported bug — two independent bugs, plus one deeper root cause found live

Cliff reported that following several authors from Feed's Suggest → Author tab showed a "✓ Following" success
state while an error also appeared saying "no OpenAlex author matched," for names he was confident had real
OpenAlex/ORCID records.

- **Frontend (`app/frontend/js/30g_feed_suggest.jsx`):** `FeedSuggestAuthors.handleFollow` called
  `setJustFollowed` unconditionally after `await onFollow(name)`, regardless of whether the follow actually
  succeeded — `followAuthor` (`30e_feed.jsx`) never signaled failure back to its caller, it only set a
  page-level error string. Fixed: `followAuthor` now returns `true`/`false` (success iff the backend's
  `FollowResponse.status` is `"followed"`/`"already-following"`, never on `"no-match"` or a request error);
  `handleFollow` only marks a row followed when that's `true`.
- **Backend cache (`integrations/openalex/author.py::_fetch`, closes backlog #61):** the cache-read branch
  treated *any* cached row as authoritative, including one the `except Exception` branch wrote after a
  transport/decode failure (`status_code=None`). Cache keys are deterministic hashes with no TTL
  (`integrations/api_cache.py`), so one transient failure permanently "poisoned" that exact name/ORCID —
  every retry short-circuited to the same stale error instead of trying again. Fixed: the read branch now
  requires `cached["status_code"] is not None` to short-circuit — a `None` status means "we never got a real
  response," not an answer, mirroring `_cached_by_key`'s already-correct analogous check. Self-healing, no
  migration: `_put_cached_once` is a true upsert, so a retry that succeeds overwrites the poisoned row.
  Regression test: `tests/test_my_publications.py::test_author_client_retries_after_a_transient_fetch_failure`.
- **The actual root cause of the live symptom, found during Playwright verification (not by inspection):**
  the "transient decode error" Cliff hit wasn't rare or random — every single name resolution was failing,
  because `integrations/http_bounds.py::_bounded_request` (inc 480, backlog #56's response-size-cap helper,
  wired into 16 call sites across 15 integration files: arXiv/bioRxiv/CORE/Crossref/DOAJ/Europe PMC/GROBID/
  NLM/OpenAlex/OSF/SciELO/Semantic Scholar) streams + transparently decompresses the wire body via
  `response.iter_bytes()`, then reconstructs a fresh `httpx.Response` from the already-plain bytes — but kept
  the *original* response's headers, including `Content-Encoding`. httpx's `Response.__init__` auto-reads
  when `content=` bytes are supplied, sees `Content-Encoding: br`/`gzip`, and tries to decompress the
  already-decompressed plain bytes a second time — raising exactly the "BrotliDecoderDecompressStream failed"
  error observed live against OpenAlex. Confirmed by direct reproduction (a raw call to `_httpx_fetcher`
  crashed identically) and by removing only the `Content-Encoding` header from the reconstructed response,
  which fixed it. Fixed by stripping both `Content-Encoding` and the now-stale `Content-Length` from the
  reconstructed response's headers. This wasn't a rare/flaky bug — it broke *every* metadata lookup against
  any Brotli/gzip-compressing origin through `bounded_get`/`bounded_post`, silently, since inc 480 shipped.
  Regression test: `tests/test_http_bounds.py::test_bounded_get_handles_a_compressed_origin_response` (a
  MockTransport response carrying a real `Content-Encoding: gzip` header + genuinely gzip-compressed content —
  the prior tests never exercised this path, which is why it went undetected).

### Feature — "Exclude Your Co-Authors" toggle (default ON)

`suggest_authors_to_follow` (`app/backend/clustering/followed_authors.py`) gained `exclude_coauthors: bool`.
A new `_coauthor_names(conn)` helper resolves the My Publications axis's top-level node and collects every
author name on its confirmed (DOI-matched, `confidence >= CONFIRMED_CONFIDENCE`) or manual (`confidence IS
NULL`) papers — deliberately excluding the 0.25-confidence name-only candidate tier, since an unconfirmed
match shouldn't be trusted to name a "definite" co-author. Matched on the full lower-cased name (not the
looser last-name-only token match the self-exclusion uses), so an unrelated same-surname author isn't
over-excluded. `GET /feed/suggest-authors?exclude_coauthors=true` wires it through
(`app/backend/api/routers/feed.py`). Frontend: a `.settings-check` checkbox in `FeedSuggestAuthors`, checked
by default per Cliff's explicit choice (his stated problem — "every suggestion is a co-author" — is fixed the
moment the tab opens, not after discovering a toggle).

### Feature — axis-scoped suggestions

Same function gained `axis_id: int | None`, mirroring `gapfinder.py::_scoped_paper_rows`'s exact pattern (an
"any node under this axis" `cluster_node_papers`/`cluster_nodes` subquery — not my-publications' own
top-level-only form, since a research axis can have sub-clusters). `GET /feed/suggest-authors?axis_id=N`
restricts the tally to that axis's papers. Frontend: a `<select className="lib-sort">` axis dropdown in
`FeedSuggestAuthors`, the exact `36_gaps.jsx` markup precedent, defaulting to `""` (whole library, resets on
each modal open). `FeedSuggestModal`'s author-fetch effect changed from a mount-only `useEffect` to a
dependency-driven `useCallback`+`useEffect([load])` (the `36_gaps.jsx` idiom) so both the toggle and the axis
selection re-fetch live.

### Feature — "N papers in your library" → Library-filter link

Since the tally now needs `papers.c.id` for axis scoping anyway, it also collects `paper_ids` per author and
returns them in the response. Frontend reuses the existing `libraryTextHealthFilter`/`libraryReferenceFilter`
local-only `{label, paperIds}` pattern (`app/frontend/js/03_library.jsx`) rather than the free-text
`search_field=author` substring search, which LIKE-matches the *entire* serialized CSL-JSON blob and would
show a different, non-matching count. New `libraryAuthorFilter` state + `filterToAuthorPapers`/
`clearAuthorFilter` (mirrors `showTextHealthFilter`'s body exactly), folded into the existing
`localPaperFilter` union and every mutually-exclusive-filter reset site (~15 call sites across
`03_library.jsx` needed the new state added to their reset list — the same convention the two existing local
filters already follow). Wired through `paneCtx` (`40_app.jsx`) → Feed's `registerWorkspaceTab` render call
(`04b_workspaces.jsx`) → `FeedPane` (`30e_feed.jsx`) → `FeedSuggestModal` → `FeedSuggestAuthors`
(`30g_feed_suggest.jsx`), where the paper-count span became an `axis-link`-styled `<button>` that sets the
filter then closes the modal (the `26b_text_health.jsx::showGroupInLibrary` precedent). `10_pdf_layer.jsx`
gained a matching display block (a `focus-card` with the author's name + shown-count + Clear), reusing
`.gap-count axis-link` — no new CSS class needed.

## Key technical detail

The `http_bounds.py` bug is the one worth remembering: **a response reconstructed from already-decoded bytes
must never carry the original `Content-Encoding` header**, or httpx (or any HTTP client that respects that
header) will try to decode plain bytes as if they were still compressed. This is a general hazard whenever
code manually streams + rebuilds an `httpx.Response` (as the bounded-read pattern here does) rather than
letting the client's own `.read()` handle decompression once.

## Manual verification script

1. Start the app, restart the backend after pulling these changes (backend Python changed).
2. Discover → Feed → Suggest → Author tab: confirm "Exclude Your Co-Authors" is checked by default, the axis
   dropdown is populated from your real axes, and paper counts render as clickable buttons.
3. Click a paper-count button → confirms the modal closes and Library shows exactly that author's papers with
   a "Clear" affordance.
4. Click Follow on a real suggested author → confirms "✓ Following" appears with no error, and the author
   shows in the followed-sources pill row. (Live-verified via Playwright against a real OpenAlex network call
   during this increment — this is what surfaced the `http_bounds.py` bug in the first place.)
5. Toggle "Exclude Your Co-Authors" off/on and change the axis dropdown → confirm the suggestion list
   re-fetches and changes.

## Pytest

`pytest tests/test_feed.py tests/test_my_publications.py tests/test_http_bounds.py tests/test_frontend_assembly.py -q`
→ all green. Full suite `pytest -n 4 -q` → **2535 passed, 3 skipped** (4 new tests over inc 505's 2531).
