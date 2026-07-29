# Increment 410 — ORCID→name fallback for My Publications author resolution

## Implemented

A real external bug report (from Isabella Bobrow, a lab colleague and an early external adopter) traced to a
genuine gap, not a Callosum defect: she entered her real, verified ORCID iD in My Publications settings and
clicked **Refresh my papers**, but got "No OpenAlex author found for Isabella Bobrow — check the name / ORCID."
Direct verification against the live OpenAlex API confirmed her ORCID-keyed lookup (`/authors/orcid:...`)
genuinely 404s — but a plain name search (`/authors?filter=display_name.search:...`) finds her real author
record (`A5098776798`, 14 works) immediately. The root cause: her OpenAlex author profile has never been
linked to her ORCID iD on OpenAlex's own side (`orcid: null` in her raw record) — OpenAlex and ORCID are
separate systems, and this gap is common, not a data-entry mistake on her part.

`integrations/openalex/author.py`'s `resolve_author`/`cached_author` previously treated ORCID and name as
**mutually exclusive** inputs (`_author_cache_key` picked one or the other, preferring ORCID whenever present,
with no fallback). Both methods now try ORCID first and — only if that comes up empty — fall back to a name
search when a name is also on file, via two small helpers (`_fetch_by_orcid`/`_fetch_by_name`,
`_cached_by_key`). `_author_cache_key` is retired in favor of `_orcid_cache_key`/`_name_cache_key`, since the
two lookups can now both run in a single call and each needs its own cache key. `cached_author` mirrors the
same ORCID-then-name order (not just `resolve_author`) — otherwise a name-fallback match resolved once would
silently vanish on every later cache-only dashboard read, since the dashboard never re-fetches.

No changes were needed in `app/backend/clustering/my_publications.py` — it already calls
`resolve_author(conn, orcid=profile.get("orcid"), name=profile.get("display_name"))` with both fields; the gap
was entirely inside the client's exclusive-or key logic.

**Principles alignment (rule #9):** this touches provenance/confidence signaling for an identity match — the
closest worked pattern is "signal not verdict" (#2) + "inspectability over authority" (#8). The easy,
misaligned path would be to just make the fallback silently succeed, presenting a fuzzy name-match with the
same authority as an exact ORCID match. The data model already had the honest distinction
(`ResolvedAuthor.matched_by: "orcid" | "name"`) and it was already wired through to the `MyPubsSummary` API
response — it just wasn't rendered. The aligned fix keeps both halves together: the fallback finds real work
that was going undiscovered, *and* the UI now visibly labels a name-fallback match as lower-confidence
("Matched by name, not ORCID — lower confidence; double-check this is you") rather than presenting it as
equivalent to an ORCID-exact hit.

Also added, per the same conversation, a Help-doc section (`app/backend/help/help_content.md`, the My
Publications section) explaining that a correct ORCID can still fail to resolve if the *OpenAlex* author
profile itself was never linked to it, and pointing users at fixing the link on OpenAlex's own site (the
durable fix) rather than only leaning on Callosum's automatic fallback.

## Key technical detail

The ORCID lookup's 404 gets cached (as it did before this change) under the `orcid:<id>` key with
`status_code=404`; the name-search's success is cached separately under its own `name:<sha256-hash>` key.
`cached_author` must therefore probe *both* keys in the same order as `resolve_author`, or a previously-found
name-fallback match would read back as `None` (dashboard shows "not-resolved") purely because the first
(ORCID) cache probe misses — even though the second (name) cache entry holds the real match.

## Manual verification

- Live OpenAlex API calls (not mocked) confirmed the exact real-world scenario before writing the fix:
  `GET /authors/orcid:0009-0008-6787-5123` → 404; `GET /authors/A5098776798` → real record, `orcid: null`;
  `GET /authors?filter=display_name.search:Isabella%20Bobrow` → finds the same author, 14 works.
- `pytest tests/test_my_publications.py -q` → **44 passed** (4 new: orcid→name fallback found + call count,
  orcid-success never touches the name endpoint, and the matching `cached_author` fallback/cache-only pair).
- `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q` → **53 passed** (the
  `matched_by` UI label touches `35a_mypubs.jsx`).
- Full suite: `pytest -n auto -q` — see the pass count logged in `changes.md` for this date.

## Pytest

`tests/test_my_publications.py`: 44 passed. `tests/test_frontend_assembly.py`: 53 passed.
