# Increment 480 — response-size caps on external HTTP reads (backlog #56)

## Implemented

A shared bounded-read helper, `integrations/http_bounds.py`, closing the gap the GROBID security audit
(`.claude/security-audits/2026-08-15_grobid-integration.md`, item 4) surfaced and the backlog generalized
codebase-wide: no client in `integrations/` bounded the size of an inbound response before fully buffering it
into memory.

- `bounded_get(url, *, max_bytes, client=None, **kwargs)` / `bounded_post(...)` — both delegate to an internal
  `_bounded_request(method, url, ...)` that streams the response (`client.stream(method, url, **kwargs)`),
  accumulates bytes with a running cap check, and raises `ResponseTooLargeError` (a `httpx.HTTPError` subclass)
  the moment the cumulative size crosses `max_bytes` — before the rest of the body is ever read. Under the cap,
  returns a normal, fully-materialized `httpx.Response` (`.json()`/`.text`/`.status_code` all work), so every
  existing call site needed only a one-line swap from `httpx.get(...)`/`httpx.post(...)`.
- Two named caps: `METADATA_RESPONSE_CAP` (10 MB — per-record JSON/XML/Atom lookups; GROBID's per-paper
  TEI-XML) and `MIRROR_DOWNLOAD_CAP` (100 MB — recorded for future reuse, not wired into any adapter this
  increment; see below).
- Wired into 16 call sites across 15 files: `arxiv`, `biorxiv`, `core`, `crossref`, `doaj/adapter.py`,
  `doaj/journals.py`, `europepmc`, `nlm/journals.py`, `openalex/adapter.py`, `openalex/author.py`,
  `openalex/sources.py`, `osf`, `scielo/journals.py`, `semantic_scholar` (2 sites), and `grobid/client.py`
  (the one `httpx.post()` site — the only one needing a bespoke catch, since it wraps every `httpx.HTTPError`
  into its own `GrobidError` type; `ResponseTooLargeError` is caught first so the module boundary's exception
  contract still holds).

## Key technical detail — the real gap was narrower than the backlog item described

Before touching anything, `grep -rn "httpx\.get(\|httpx\.post(\|httpx\.Client(\|httpx\.stream("` across
`integrations/` found 19 call sites in 18 files, not 15. Reading each (not assuming from the backlog's own
summary) found the three "mirror download" adapters the item explicitly named — `ajol/adapter.py`,
`retraction_watch/adapter.py`, `top_factor/adapter.py` — **already had correct, working bounded-read logic**
(`MAX_AJOL_BYTES`/`MAX_RW_BYTES`/`MAX_TOP_FACTOR_BYTES`, streamed accumulation, each raising its own domain
exception on overflow). These were left untouched per rule #7 (minimal diffs; no drive-by refactor of
already-correct code) rather than folded onto the new shared helper for pure DRY's sake. The backlog's own
description was stale on this point — corrected here rather than propagated forward.

`ResponseTooLargeError`'s `httpx.HTTPError` inheritance was a deliberate design choice, verified against real
call sites rather than assumed: 14 of the 15 metadata-lookup adapters already wrap their fetch call in a broad
`except Exception:` (fail-closed → cache a failure marker → return `None`/`[]`, the same pattern already used
for connection errors and timeouts) — the new exception type needed **zero additional wiring** at any of them.

## Manual verification

No UI surface — this is backend-only defensive hardening. Verification is the test suite:
`tests/test_http_bounds.py` (7 tests: under-cap passthrough, over-cap rejection for both GET and POST, `.json()`
support, header/status preservation, self-created-client cleanup) plus `tests/test_grobid_client.py`'s new
oversized-response test, plus every pre-existing test file that exercises the 15 edited adapters (directly or
through a higher-level caller — `test_acquisition_sources.py`, `test_publishers.py`, `test_citation_context.py`,
`test_metadata_enrichment.py`, `test_openalex_adapter.py`, and others) run unmodified against the new code path.
`python tools/check_line_budget.py` and `python -m tach check` both clean.

## Pytest

Full suite (`pytest -n 4 -q`): **2285 passed, 3 skipped** — up from the 2277-passed/3-skipped baseline recorded
earlier this session by exactly the 8 new tests this increment added (7 in `test_http_bounds.py` + 1 in
`test_grobid_client.py`).
