# Increment 348 — Workbench locally retrieved drafting context (backlog #36)

## Context
The assisted-extraction funnel's provider previously received the first 50,000 characters of a linked paper's
page-tagged chunks. That bound prevented runaway prompts, but it could omit a late results passage while spending
most of the context budget on unrelated front matter. Backlog #36 called for embedding the requested field labels
locally and sending only the top relevant chunks.

## Implemented
- Papers with 12 or fewer chunks keep their complete page-tagged context (subject to the existing 50,000-character
  cap). Longer papers use the empty structured fields' human-readable labels as one local retrieval query.
- Callosum embeds/reuses only the linked paper's chunk vectors and calls the shared retrieval API with those exact
  chunk target IDs as the candidate set. At most 12 relevance-ranked, page-tagged passages reach the unchanged
  consent-gated extraction assistant.
- The 50,000-character cap remains a second resource guard after retrieval.
- If local embedding or vector search fails, the request logs a warning and falls back to the prior bounded
  document-order assembly. Retrieval runs in a savepoint so partial embedding metadata is rolled back before
  fallback. Drafting remains available; the egress gate and candidate-only persistence are unchanged.
- The API keeps its existing `truncated` compatibility field. The frontend now reports that locally selected
  relevant passages were sent, replacing the false "first part" description. Batch status uses the same wording.
- `search_similar` gained an additive `candidate_target_ids` filter so callers can constrain retrieval at the
  embedding-metadata query rather than searching the whole library and filtering results afterward.

## Verification
- `uv run pytest -q tests/test_frontend_assembly.py tests/test_workbench_assist.py tests/test_embeddings.py
  tests/test_workbench.py` — **93 passed**.
- Hermetic regressions pin the exact label query, linked-paper candidate-ID restriction, top-k selected text,
  document-order failure fallback, and candidate-target filtering in the shared retrieval API.
- `$env:PYTHONPATH='.'; uv run python tools/validation_harness.py --pdf-dir tests/fixtures
  --query "correlation sample size" --top-k 12 --output-dir .local/validation-inc348 --no-progress` — real fixture
  ingested, **3 chunk embeddings + 1 paper embedding**, retrieval completed, report inspected.
- `python tools/qa/build_surface_map.py check` — **260/260 API covered**; frontend **1186/1207 covered**, with the
  same 21 pre-existing uncovered controls in `10e_tagspanel.jsx` and `35a_mypubs.jsx`.
- Headed disposable-server pass at 1440×900 with the proposal response intercepted as `truncated: true`: the
  per-row draft control was enabled, the new relevant-passages note and candidate evidence both rendered, the old
  "first part" copy was absent, there was no page overflow, and console/page errors were **0**. Screenshot:
  `.local/inc348-retrieval-copy.png`. The disposable port 8099 server was terminated after the pass.
- `uv run pytest -n 4 -q` — **1418 passed, 1 skipped** in 604.00s on the final savepoint-protected source state.
- `uv run ruff check .` / `uv run ruff format --check .` — clean (**478 files formatted**).
- `python tools/check_line_budget.py` — clean (**351 application-source files** within cap).

## Gates
- **Principles / A-A:** aligned. Retrieval narrows what the model sees; it does not increase model authority. Every
  result remains an evidence-carried candidate awaiting individual human accept/edit/reject, with local anchor
  precision and no opaque relevance score in the UI.
- **Security:** the existing inc-259 audit has an inc-348 addendum. No new endpoint, host, secret, dependency,
  persistence, or consent path; selection is local and restricted to the linked paper. The old egress cap remains.
- **QA:** route 65 now requires a relevant passage beyond the former document head, excludes early unrelated and
  cross-paper chunks, and exercises the local-retrieval failure fallback.
- **Design:** no layout or visual recipe changed. Only inaccurate long-paper status copy was corrected.

## Outcome
Backlog #36's two near-term escalations are complete: increment 347 added conservative sequential batch-propose,
and increment 348 makes each long-paper proposal call field-aware and materially smaller without weakening the
human verification gate.
