# Final validation and commit receipt (inc 610)

Branch `integrate/inc607-608-ask`, worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`, parent
`b6b8bfe0` (inc 609). **Local commit only: not pushed, not merged, not deployed, not tagged.** The commit hash is
reported in the session's final message (a file cannot contain its own commit's hash).

## Code changes

New: `app/backend/embeddings/{resources,index_lock,index_runs,index_worker,index_supervisor}.py`,
`app/backend/persistence/schema_index_runs.py`, `alembic/versions/0086_embedding_index_runs.py`,
`app/backend/api/routers/embedding_index.py`, `tools/run_profile_index.py`, `tests/test_index_recovery.py`,
`tests/index_worker_fake.py`.
Modified: `app/backend/embeddings/profile_index.py`, `app/backend/persistence/schema.py`,
`app/backend/api/app.py` (600 lines, at the cap), `app/backend/api/routers/embedding_profiles.py`,
`app/frontend/js/35i_retrieval_profiles.jsx`, `callosum-app.html`, `app/backend/help/help_content.md`,
`tests/test_embedding_profiles.py`, QA route 97, demo/website coverage ledgers (deferral through 610),
`.claude/CLAUDE.md`, `.claude/changes.md`.
Docs: `INCREMENT-610-NOTES.md`, security audit `2026-10-30_supervised-index-worker.md` (PASS), and this folder's
seven deliverables.

## Migration

`0086_embedding_index_runs`: additive, guarded create of `embedding_index_runs`. Applied only to the disposable copy
(byte backup `C:\Users\cliff\callosum-data\experiments\arctic-continuation-20261030\copy.pre-inc610.sqlite`). No
protected database was opened for writing.

## Tests

| Run | Result |
|---|---|
| `tests/test_index_recovery.py` (after the final edits) | 17 passed (51 s) |
| Targeted serial set: recovery, embedding profiles, 607+608 integration, frontend assembly, status, migrations, startup migration, health, NLI failure/provenance, help | **210 passed**, 0 failed (164 s; peak tree RSS 588 MB, min free 4,925 MB) |
| Full suite | **not run** (resource constraints; Codex workload) |

An earlier targeted run had 9 failures. The cause was a test helper passing `db_url="unused"` once the supervisor
started consulting the OS lock path; the helper was fixed, not the production code.

## Static and QA gates

| Gate | Result |
|---|---|
| `ruff format --check` / `ruff check` (changed files) | clean |
| `tools/check_line_budget.py` | OK (672 files) |
| `tach check` | OK |
| `tools/run_bandit.py` (ratcheted) | exit 0 (new findings annotated `# nosec` with reasons; see audit) |
| `tools/qa/build_surface_map.py check` | OK (every gated surface claimed) |
| demo / website coverage | OK after an explicit `--decline` for 610 (integration-branch change; review deferred with 607–609) |
| `check_whatsnew_coverage.py` | OK |

## Real continuation (disposable copy)

25,453 → **42,044 / 42,044** Arctic S passages, state `completed`, verified from stored vectors. Integrity: 0 missing
vectors, 0 orphans, 0 stale, 0 duplicates. MiniLM metadata and vectors, the 25,453 pre-existing Arctic rows, and
chunks are byte-identical by sha256; `quick_check ok`. An idempotent rerun added 0 rows. Three injected failures
(two worker kills, one app kill) were recovered without manual repair. See `ARCTIC_INDEX_CONTINUATION_RECEIPT.json`
and `INDEX_INTEGRITY_AND_MINILM_PRESERVATION.json`.

## Limitations

- No browser/visual review (Playwright MCP failed to connect).
- Not run in a packaged build, on macOS or on Linux.
- The full pytest suite was not run.
- A worker with nothing pending still loads the model (about 25 s).
- No 607 backfill, retrieval comparison, DeBERTa evaluation or JUNO use, as instructed.
- The originals, research master, desktop DB, DEV library, frozen experiments, and Codex's branch/worktree were not
  touched.
