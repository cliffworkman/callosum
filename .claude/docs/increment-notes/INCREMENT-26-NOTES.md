# Increment 26 Notes

## Implemented

- Added persisted summary history endpoints:
  - `GET /summaries`
  - `GET /summaries/{summary_id}`
  - `DELETE /summaries/{summary_id}`
- Added thin repository helpers:
  - `list_summaries`
  - `get_summary`
  - `delete_summary`
- Added frontend synthesis history in `callosum-app.html`:
  - lists saved syntheses
  - reloads a saved synthesis into the existing sentence/citation renderer
  - deletes a saved synthesis after confirmation
  - preserves the current synthesis when switching between Synthesis and Detail tabs

## Shared Serialization

`GET /summaries/{summary_id}` and completed `GET /summarize/{job_id}` now share the same persisted-summary serializer. After `summarize_scope` writes the trust chain, the live job response reads the just-persisted `summary_id` back through the same function used by persisted summary read-back.

The reloaded shape matches the completed-job response model:

- `job_id`
- `status: "done"`
- `summary_id`
- `summary_status`
- `sentences[]`
- `sentences[].flagged`
- `sentences[].citations[]`
- citation confidence fields and `coordinate_precision`

Persisted read-back uses `job_id: "summary:{summary_id}"` because there is no live in-memory job after restart.

## Delete Behavior

`DELETE /summaries/{summary_id}` deletes only the selected summary. SQLite foreign keys are enabled by `make_engine`, so deleting from `summaries` cascades through:

`summaries -> summary_sentences -> citation_mappings -> evidence_quotes`

It does not touch papers, chunks, attachments, embeddings, or pipeline data.

## Scope Labels

History labels are derived from `summaries.scope_ref_json`:

- query scope: the stored query string
- papers scope: `"N paper(s)"`
- cluster node scope: `"Cluster node {id}"`
- fallback: the raw `scope_type`

## Frontend Behavior

- The history list calls `GET /summaries?limit=20&offset=0`.
- Clicking a history row calls `GET /summaries/{summary_id}` and renders the returned summary with the existing provenance cards.
- Clicking Delete asks for confirmation, calls `DELETE /summaries/{summary_id}`, and removes the row from the list.
- Running a new synthesis refreshes the history list when the job reaches `done`.
- The Synthesis and Detail tab contents remain mounted; inactive content is hidden rather than unmounted, so current synthesis state survives tab switching.

## Verification

API tests:

```text
$ pytest tests/test_api.py -q
..................                                                       [100%]
18 passed in 18.30s
```

Full suite:

```text
$ pytest -q
........................................................................ [ 74%]
.........................                                                [100%]
97 passed in 52.17s
```

Browser smoke check:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8768
```

Opened `http://127.0.0.1:8768/` with Playwright. Result: page title `Callosum`, library panes loaded, synthesis history rendered with saved summaries, and `0` console errors. The only warning was the existing Babel standalone development warning.

## Deferred

- PDF viewer / bbox overlay highlighting.
- Editing saved summaries.
- Export/share.
- Authentication.
