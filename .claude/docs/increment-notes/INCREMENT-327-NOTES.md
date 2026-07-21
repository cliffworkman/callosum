# Increment 327 — LibreOffice adapter rework: Phase 9 (document diagnostics)

## Context
The last of the smaller phases before Phase 5 (the composer, deferred). Every state this phase reports is one
the adapter already knows how to describe or safely fix — a damaged bibliography bookmark pair self-heals on
the next refresh (`_write_bibliography`'s own damaged-document branch, shipped in Phase 7); an unsupported
future schema version is already left inert rather than guessed at (Phase 1). What was missing was surfacing
any of this to the user instead of them discovering it by accident. Scoped deliberately narrow: **read-only**,
no new repair mutation — "repair" here means pointing the user at mechanisms that already exist and are already
safe, not inventing new ones that would need their own transactional/undo treatment and spike.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`diagnose_document(doc, base) -> dict`**: a full-document health scan. Walks every `CALLOSUM_CITATION`-
  prefixed `ReferenceMark` and classifies it: **malformed** (our prefix, but `decode_mark_name` fails — a
  corrupted or hand-edited mark), **unsupported_version** (ours, but a schema version this adapter doesn't
  understand — `scan_citations_in_order` already skips these; this just reports them), **duplicate_ids** (two
  marks sharing the same embedded `rnd`/citationID — a real ReferenceMark *name* is unique, but nothing enforces
  the embedded rnd's uniqueness beyond `_new_rnd`'s own counter), and **orphaned** (an item's paper id no longer
  resolves in the library — reuses `fetch_csl`, one HTTP call per distinct paper id, cached). Also reports the
  bibliography's state: `ok` (a healthy bookmark pair), `damaged` (only one of the pair present), `not_built`
  (citations exist but no bibliography yet — informational, not a defect), or `n/a` (no citations at all). Never
  mutates the document. Any exception OTHER than "paper not found" (e.g. the server being unreachable) is
  deliberately let through rather than being misreported as "these citations are orphaned."
- **`document_diagnostics_interactive(doc, base)`**: formats the report into a plain-language message box; "no
  issues found" when the scan is clean.
- New `_ACTIONS` entry (`diagnostics`) + `CallosumDiagnostics` macro wrapper + a new `Addons.xcu` menu node
  (`m09`, "Document diagnostics…").

**A real, pre-existing bug found and fixed along the way:** `fetch_csl`'s docstring claimed it raises
`ValueError` when a paper doesn't exist, based on an unverified assumption that `/papers/export` returns 200
with an empty list for an unknown id. It doesn't — `routers/papers.py::export_citations` raises **HTTP 422**
("No existing (non-trashed) papers to export") when the result set is empty. `fetch_csl`'s own "empty rows"
check was dead code for this exact case: a genuinely missing paper always hit `urllib.error.HTTPError` first,
never reached it. This means the orphan-detection design (reuse `fetch_csl`'s already-correct raise, per the
original Phase 9 sketch) was working from a wrong premise — caught only because the real-UNO spike exercises a
paper id that was never seeded, something no pytest mock would have caught (the existing tests all monkeypatch
`fetch_csl` directly, bypassing its real implementation). Fixed by catching `HTTPError` with code 422 in
`fetch_csl` and translating it to the same `ValueError` the rest of the adapter already expects — a strictly
better error message falls out of this for free on the existing "Insert citation by id" path too (a typo'd
paper id now shows a clear "no paper with id N" instead of a raw HTTP error dump).

## Tests
- **`tests/test_libreoffice_adapter.py`** (8 new tests, pure/fakeable — `diagnose_document` reads two simple
  UNO collections + makes an HTTP call, faithfully fakeable like the existing `_snapshot_marks` precedent, so
  real mutation stays real-UNO-only but this read-only inspection gets pytest coverage too): a clean document
  reports nothing; a mark from another tool is ignored entirely; malformed/unsupported-version/duplicate-id/
  orphaned are each detected; orphan checks are cached per paper id (cited twice → one HTTP call); a
  connectivity error propagates rather than being reported as "orphaned"; all four bibliography states. Plus
  2 new tests for the `fetch_csl` fix itself (422 → `ValueError`; a non-422 HTTP error is NOT swallowed).
- **`selftest_uno.py`**: `spike_document_diagnostics` — a clean document reports nothing; a second document
  hand-plants a malformed mark, a `"v": 99` mark, two marks sharing an rnd, and a citation to paper id 999999
  (never seeded) and confirms all four are detected correctly in one pass; a third document gets a healthy
  bibliography built by a real refresh, then has its END bookmark manually removed (simulating outside damage)
  and is confirmed reported as `damaged`; a fourth disables bib-auto *before* its first-ever citation (so no
  bookmark pair is ever created) and is confirmed reported as `not_built`. This is the spike that caught the
  `fetch_csl`/422 bug — the orphan sub-case failed on the first run with an uncaught `HTTPError` before the fix.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 25 passed (15 prior + 8 new diagnostics + 2 new fetch_csl).
2. `python .local/lo_roundtrip/run_roundtrip.py` — `SELFTEST OK`, all prior spikes plus the new Phase-9 spike
   (one retry needed for the usual transient "nothing listening on UNO port 2003" startup flake, unrelated to
   any code change; the second attempt caught the real `fetch_csl` bug on its first run through the new spike,
   fixed, then re-ran clean).
3. `ruff format` / `ruff check .` — clean (3 files reformatted, no lint findings). `python tools/check_line_budget.py`
   — clean (`adapters/` is exempt from the 600-line cap regardless; confirmed anyway).
4. `python -c "import xml.dom.minidom; ...parse(...)"` — `Addons.xcu` well-formed.
5. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count.

## Gates
- **Security audit:** not triggered as a new stub — no new endpoint, no new external integration, no new
  file-write path, no auth change. `diagnose_document` reuses the already-audited `fetch_csl`/`/papers/export`
  call exactly as `insert_citation` already does; it is read-only over UNO collections otherwise. Noted here
  rather than a separate file, consistent with how Phases 1/7 handled similarly narrow, non-triggering changes.
- **Principles/A-A (rule #9):** a diagnostic surfaces facts about the document's own internal state (malformed/
  unsupported/duplicate/orphaned/bibliography-state) — no claim about the literature, no score, no judgment;
  each finding names exactly what's wrong and what to do about it. Aligned with signal-not-verdict by
  construction — there's no composite "health score," just a plain list of what was found.
- **README:** `adapters/libreoffice/README.md`'s "Use" section gained item 15; the macro-names list gained
  `CallosumDiagnostics`.

## Next
Phase 5 (the composer UI) is the last major piece of the original P0 roadmap, deferred per Cliff's own request
until after a `/compact`. A new, additional final phase was requested in this same session: hardening this
rework's test coverage itself — promoting the manual `selftest_uno.py`/`run_roundtrip.py` harness (currently
gitignored, dev-only, zero CI enforcement) into something more repeatable, since the LibreOffice/Word/Google-
Docs adapters sit entirely outside the QA surface-map gate by construction (confirmed via `tools/qa/
build_surface_map.py`, which only walks `app/backend/api/routers/` and `app/frontend/js/`). That phase's shape
(whether/how it touches CI) still needs a short scoping conversation before any workflow-file changes are made.
