# Security audit — response-size caps on external HTTP reads (backlog #56)

**Date:** 2026-08-16
**Status:** PASS
**Feature:** a shared bounded-read helper (`integrations/http_bounds.py`) wired into every previously-unbounded
external HTTP fetch in `integrations/`, closing a gap surfaced by the GROBID security audit
(`.claude/security-audits/2026-08-15_grobid-integration.md`, item 4) and confirmed codebase-wide.
**Audit trigger:** a hardening change spanning 15 files (rule #5's "net-new feature spanning 3+ files" — this
is a defensive-hardening pass, not a new feature, but the same discoverability value applies: it closes a gap
an earlier audit named).

## Scope confirmed empirically, not assumed

`grep -rn "httpx\.get(\|httpx\.post(\|httpx\.Client(\|httpx\.stream(" integrations/` found 19 call sites
across 18 files. Reading each before touching it found the real gap was **narrower** than the backlog item's
own description: the three "mirror download" adapters it named (`ajol/adapter.py`, `retraction_watch/
adapter.py`, `top_factor/adapter.py`) already had their own correct streaming-with-cap logic
(`MAX_AJOL_BYTES`/`MAX_RW_BYTES`/`MAX_TOP_FACTOR_BYTES`, each raising its own domain exception on overflow) —
left untouched, per rule #7 (minimal diffs; no drive-by refactor of already-correct code). The genuine gap was
16 call sites across 15 files: 15 simple metadata-lookup `httpx.get()` calls (arXiv, bioRxiv, CORE, Crossref,
DOAJ ×2, Europe PMC, NLM, OpenAlex ×3, OSF, SciELO, Semantic Scholar ×2) plus GROBID's one `httpx.post()`
multipart-upload call — all now route through `bounded_get`/`bounded_post`.

## Threat review

- **Unbounded memory growth from a misbehaving or compromised external service.** Every one of the 16 sites
  previously called `httpx.get()`/`httpx.post()` directly, which fully buffers the response body into memory
  before the caller sees it — no cap on that buffer. `bounded_get`/`bounded_post` stream the body
  (`client.stream(...)` + `response.iter_bytes()`) and raise `ResponseTooLargeError` **during** iteration, the
  moment the cumulative byte count crosses the cap — the rest of the body is never read or buffered.
- **Two named caps, not one blanket constant**, matching the two genuinely different response-size profiles
  already present in the codebase: `METADATA_RESPONSE_CAP` (10 MB — per-record JSON/XML/Atom lookups; GROBID's
  per-paper TEI-XML) and `MIRROR_DOWNLOAD_CAP` (100 MB — recorded for future reuse; not wired into the three
  already-correct mirror adapters, which keep their own existing, already-audited cap values).
- **Fail-closed, not fail-open.** `ResponseTooLargeError` subclasses `httpx.HTTPError`, so every call site's
  pre-existing error handling (a broad `except Exception:` → cache a failure marker → return `None`/`[]`, the
  same fail-closed pattern already used for connection errors and timeouts across every one of these adapters)
  catches it with **zero additional wiring** at 14 of the 15 metadata sites — verified by reading each
  adapter's call site, not assumed from one example. The one exception, GROBID's `client.py`, wraps all
  `httpx.HTTPError` into its own `GrobidError` type; `ResponseTooLargeError` is explicitly caught there first
  so the module boundary's own exception contract (never leak a foreign exception type across it) still holds.
- **No change to what leaves the machine.** This is a read-side memory-safety hardening, not a new egress path
  — every one of the 16 endpoints was already being called by existing code; the egress gate (invariant #3) and
  each adapter's own SSRF/DOI-shape validation are untouched.
- **The response object contract is preserved.** `bounded_get`/`bounded_post` return a real, fully-materialized
  `httpx.Response` (constructed via `httpx.Response(status_code, headers=..., content=..., request=...)`) once
  the body is confirmed under the cap, so every existing call site's `.json()`/`.text`/`.status_code` usage
  needed zero changes beyond the one-line swap from `httpx.get(...)` to `bounded_get(..., max_bytes=...)`.
- **Resource ownership.** When no `client=` kwarg is supplied, `bounded_get`/`bounded_post` create and always
  close their own `httpx.Client` (verified by a monkeypatch-and-spy test asserting `.is_closed` afterward) —
  no connection-pool leak on the new default path.

## Negative-path checks

- A response exceeding the cap raises `ResponseTooLargeError` before the full body is read (`tests/
  test_http_bounds.py::test_bounded_get_raises_when_over_cap` / `test_bounded_post_raises_when_over_cap`).
- The GROBID module boundary never leaks `ResponseTooLargeError` — an oversized GROBID response surfaces as
  the module's own `GrobidError` (`tests/test_grobid_client.py::
  test_parse_fulltext_oversized_response_raises_grobid_error_not_response_too_large`).
- The helper closes a client it created itself (no leaked connection pool) — `tests/test_http_bounds.py::
  test_bounded_get_closes_the_client_it_creates_when_none_supplied`.
- Every one of the 15 metadata-lookup adapters' own existing test suites (or the higher-level test files that
  exercise them where no dedicated per-adapter test file exists — `test_acquisition_sources.py`,
  `test_publishers.py`, `test_citation_context.py`, `test_metadata_enrichment.py`, and others) still pass
  unmodified against the new code path.
- `python tools/check_line_budget.py` and `python -m tach check` both clean after the change (no file crossed
  the 600-line cap; no new cross-module import violates the `integrations/` boundary).

## Result

The shared helper closes the real, narrower-than-described gap with a fail-closed, minimal-diff change that
required no new call-site error handling at 14 of 15 metadata sites and preserved the exact existing response
contract everywhere. The three mirror-download adapters already had equivalent protection and were correctly
left untouched.

**Security Audit: PASS.**
