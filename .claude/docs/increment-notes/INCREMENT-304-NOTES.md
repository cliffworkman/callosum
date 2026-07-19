# Increment 304 — per-item titles in import/embed progress labels (backlog #4)

## Implemented
The determinate progress bar for the two long-running import jobs used a static label — every tick read
**"Embedding papers — 3 / 12"**, so a user watching a big import had no idea *which* paper was in flight. Backlog
#4 ("progress titles") asked for the per-item title instead.

- **`app/backend/persistence/paper_query_repo.py`** — new read-only helper `titles_for_ids(conn, paper_ids) ->
  dict[int, str]`: one bound-param `IN` query mapping paper id → title, with a `paper <id>` fallback for a
  missing/blank title. Lives in the inc-301 leaf query module (the inc-137/220/262 extraction pattern) so
  `repository.py` stays under the 600-line cap.
- **`app/backend/persistence/repository.py`** — re-exports `titles_for_ids` alongside the other
  `paper_query_repo` helpers (`# noqa: E402,F401`), so existing call sites import it from `repository` unchanged.
- **`app/backend/api/routers/library.py`** — both embed loops (`_run_import_job` ~L432, `_run_bundle_import_job`
  ~L547) now fetch the created papers' titles **once** before the loop (`with engine.connect()` →
  `titles_for_ids`) and pass `f"Embedding {titles.get(paper_id, 'paper')[:60]}"` to `jobs.mark_progress(...)`
  instead of the constant `"Embedding papers"`. The `ProgressBar` (inc 142) already renders
  `${progress.label} — ${current} / ${total}${eta}`, so the per-paper title flows straight through the existing
  `/jobs/{id}` poll → no frontend change, no rebuild.
- **`tests/test_papers.py`** — `test_titles_for_ids` (id→title map; a missing id is omitted; a blank title →
  `paper <id>`).

## Key technical detail
The title lookup is a **single query per job, hoisted out of the per-item loop** — not a query per tick. The
loop already commits per-paper (`commit_each`, so the write lock is released between papers, inc 225 concurrency);
adding an N-times-per-job SELECT inside it would have re-contended that lattice. `titles_for_ids` runs once on its
own short-lived `engine.connect()` before the loop, materializes a `dict[int, str]`, and the loop reads from the
dict. The `[:60]` cap keeps a pathological title from blowing out the progress line. `titles.get(paper_id,
'paper')` degrades gracefully if a title vanished between the pre-fetch and the tick (it never has to raise).

## Principles / gates
- **Not a claim/signal feature** (rule #9 gate not triggered): a progress label is UI chrome, not a
  judgment about the literature — no provenance/evidence/egress posture touched.
- **QA (rule #10):** no new/changed surface — the `/jobs/{id}` status endpoint + its `progress.label` field
  already exist (inc 142); only the string *content* of an existing field changed. No route needed.
- **Experience (rule #11):** this *is* the experience win — it closes a legibility gap in an existing progress
  display (the corpus-builder importing 50 PDFs now sees which paper is embedding, not an opaque "Embedding
  papers"). Strict improvement to an existing surface; no persona-agent dispatch warranted for a label change.
- **SQL (rule #3):** bound-param `IN` only.

## Manual verification script
1. Start the app (`uvicorn app.backend.api.app:app --port 8888`), open `http://127.0.0.1:8888/`.
2. Import a multi-paper source (a Zotero export or a bundle with several PDFs) via the library **＋** menu.
3. While the import runs, watch the progress bar: the label should read **"Embedding <paper title> — k / N"**
   and the title should change as it advances through the papers (not the static "Embedding papers").
4. Confirm a paper with no title still shows "Embedding paper — k / N" (graceful fallback), never a crash.

## Pytest
`pytest tests/test_papers.py::test_titles_for_ids -q` → 1 passed. `pytest tests/test_citation_import.py -q` →
11 passed (the import loop path). Full parallel gate: `pytest -n auto -q` → (recorded in changes.md).
