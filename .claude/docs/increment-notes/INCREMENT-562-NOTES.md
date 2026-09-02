# Increment 562 Notes — OpenAlex destructive-refresh safety

## Implemented

- Retraction checks now distinguish an incomplete provider check from a complete clean result. An unavailable
  check cannot erase an existing FACT, stored status, or system retraction/correction tag.
- OpenAlex retraction and reference-integrity lookups expose a strict failure-aware seam while their legacy
  best-effort callers remain fail-closed.
- My Publications author-work pagination returns an explicit completeness receipt. Total failure, page-N failure,
  and the bounded 1,000-work cap never replace or cache a partial automatic-membership snapshot.
- Exact ORCID lookup outages stop resolution instead of falling through to the first fuzzy name-search result;
  a real 404 still permits the existing visibly lower-confidence fallback.
- Reference-integrity refresh clears absent signals only after complete discovery and complete inspection. A
  Semantic Scholar + OpenAlex outage preserves the last established signals.
- OpenAlex author paging now uses the documented 100-work page size while retaining the same 1,000-work ceiling.

## Key technical detail

The new boundary is **complete replacement only**. Empty is valid evidence only when the provider interaction
completed. `unavailable`, partial pagination, capped pagination, or a skipped detector preserve prior durable
state. This directly enforces “silence is not a certificate” and prevents a transient metadata-provider problem
from rewriting scientific safety signals or author identity.

## Manual verification script

1. Resolve My Publications and confirm existing automatic members.
2. Disconnect the network and press Refresh; confirm the refresh reports incomplete and existing members remain.
3. On a paper with a stored retraction or reference-integrity signal, run the corresponding refresh offline;
   confirm the old evidence remains and the provider failure is reported.
4. Resolve a profile by ORCID while OpenAlex is unavailable; confirm no name-fallback author is selected.

## Pytest

- `pytest -q -p no:cacheprovider tests/test_retraction.py tests/test_my_publications.py
  tests/test_reference_integrity.py tests/test_openalex_adapter.py` — **106 passed**.
- New regressions cover all-provider retraction outage, preserved retraction evidence, partial author pagination,
  preserved My Publications membership, ORCID outage without name fallback, and preserved reference signals.
- Ruff format/check passed for all touched Python files.
