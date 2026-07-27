# Security audit — per-paper statcheck result cache

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

Two new endpoints, `GET /papers/{paper_id}/statcheck/cached` and `POST /papers/{paper_id}/statcheck/rescan`
(`app/backend/api/routers/methods_statcheck_cache.py`), backing a cache-then-explicit-rescan replacement
for the METHODS "Statistics" per-paper check, which previously recomputed live on every panel open. Both
are read/compute-only over already-authorized local data (the paper's own extracted chunks/attachments) —
no new authorization boundary, no new input surface beyond the existing `paper_id` path parameter every
sibling `/papers/{paper_id}/...` route already accepts.

## Threat review

- **Input validation:** `paper_id` is a path int; both routes 404 via the existing `get_paper` lookup
  before doing anything else — no new validation surface.
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); the cached
  `results_json`/`coverage_json` are the exact same Pydantic-validated shapes (`StatcheckResult`/
  `StatcheckCoverage`) the existing live endpoint already returns — no new serialization path.
- **SSRF / external calls:** none — pure local computation + SQLite read/write, identical to the existing
  `GET /papers/{paper_id}/statcheck` this sits beside.
- **Data egress:** none. Both routes are 100% local/deterministic; untouched by the egress gate
  (invariant #3) — no LLM, no external API call.
- **Coordinate honesty (invariant #2):** the cache stores the itemized `StatcheckResult` payload
  *verbatim*, including `bbox_json`/`coordinate_precision` — verified byte-identical to a live run for
  `exact` and `region` precision states via `tests/test_statcheck_cache.py`. The cache never degrades or
  reinterprets evidence; it only replays what a live run already produced.
- **Staleness honesty:** a content-fingerprint mismatch (the paper was reprocessed since the cached run)
  surfaces as a passive `stale: true` flag — it never silently substitutes a fresher, uncommunicated
  result, never blocks the cached result from displaying, and never auto-triggers a recompute. This is a
  direct application of "silence is not a certificate" (a stale cache is flagged, not silently treated as
  current) without overcorrecting into "a stale flag is a verdict" (the old result stays fully visible and
  usable until the user explicitly asks for a rescan).
- **Resource caps:** `rescan` performs exactly the same bounded computation the existing live endpoint
  already performs per request — no new fan-out, no new external call, no unbounded loop. The batch
  "Check all papers" job's cache-warming addition reuses that same per-paper bound, once per paper in the
  existing batch loop (no new iteration).
- **Supply chain:** no new dependency. One new table (`paper_statcheck_cache`, additive migration
  `0056`), no changes to any existing table.

## Negative-path checks

All verified by `tests/test_statcheck_cache.py` (6 passed):
- `GET .../cached` for a paper never checked → `cached: false`, all other fields honest defaults (never an
  error).
- `GET .../cached` / `POST .../rescan` for a nonexistent paper → 404, no traceback.
- `rescan` run twice → the cache overwrites (one row, `paper_id` primary key), never duplicates.
- A cached `exact`-precision result (patched `locate_quote_for_attachment`) is byte-identical across a
  live run, an explicit rescan, and a subsequent cached read — `bbox_json`/`coordinate_precision` survive
  the JSON round-trip exactly.
- A cached `region`-precision result is likewise byte-identical to a live run.
- Simulating a reprocess (a new chunk with a different `source_attachment_checksum`) flips `stale` to
  `true` on the next cached read while the returned `results`/`checked` counts remain the OLD values,
  verbatim, until an explicit rescan — proving the cache never silently updates itself.
- The library-wide batch run (`POST /methods/statcheck/run`) warms the cache for both a flagged and a
  clean (non-flagged) paper — confirmed via `GET .../cached` immediately after the batch completes.

## Result

No exploitable issue or new sensitive boundary was found. Both endpoints reuse the existing statcheck
compute path and its already-audited local-only threat model; the only genuinely new logic (the content
fingerprint) is a pure, local hash comparison with no side effects of its own.

**Security Audit: PASS**
