# Increment 23 Notes

## Implemented

- Added a read-only `GET /` route to the FastAPI app that serves `callosum-app.html`.
- Kept the frontend file at the repository root. The default path is computed from `app/backend/api/app.py`; it can be overridden with `CALLOSUM_FRONTEND_PATH` or by passing `frontend_path` to `create_app()` in tests.
- Updated `callosum-app.html` so API calls default to same-origin relative paths. Separate frontend development remains supported with `?api=http://127.0.0.1:8080` or `window.CALLOSUM_API_BASE`.
- Added graceful missing-file handling: if the configured frontend HTML file is absent, `GET /` returns a small HTML message explaining the missing path and `CALLOSUM_FRONTEND_PATH`; JSON API routes still work.
- Added TestClient coverage for root HTML serving, JSON route precedence, missing frontend behavior, and the read-only route surface.

## Route Precedence

The app uses an explicit `GET /` route rather than a catch-all static mount, so existing JSON routes (`/health`, `/papers`, `/papers/{id}`, `/papers/{id}/chunks`, `/axes`, `/axes/{id}/clusters`) are not shadowed.

## Local Launch

PowerShell example:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Then open:

```text
http://127.0.0.1:8080/
```

Optional frontend path override:

```powershell
$env:CALLOSUM_FRONTEND_PATH = "C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/callosum-app.html"
```

## Raw Pytest Output

```text
$ pytest tests/test_api.py -q
.........                                                                [100%]
9 passed in 9.31s

$ pytest -q
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 49.07s
```

## Notes

- No API behavior or JSON response models were changed.
- No write routes were added.
- No schema, pipeline, extraction, verification, or metadata-enrichment code was changed.
