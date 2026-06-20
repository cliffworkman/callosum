# Increment 21 Notes

## Implemented

- Added a read-only FastAPI app under `app/backend/api/`.
- Added the following GET endpoints:
  - `GET /health`
  - `GET /papers`
  - `GET /papers/{paper_id}`
  - `GET /papers/{paper_id}/chunks`
  - `GET /axes`
  - `GET /axes/{axis_id}/clusters`
- Added thin read-only repository helpers for paper listing/counts and axis/cluster reads.
- Added Pydantic response models that reflect the current schema fields for papers, attachments, chunks, axes, cluster nodes, and cluster assignments.
- Added FastAPI/TestClient coverage with a migrated temporary SQLite DB and synthetic seed data.

## Configuration And Launch

- The API reads its DB URL from `CALLOSUM_DB_URL`; if unset, it defaults to `sqlite:///.local/validation/validation.sqlite`.
- The app builds its engine through `make_engine` and opens/closes one SQLAlchemy connection per request.
- Launch locally with:

```text
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8000
```

## Local-Only / CORS

- The app is intended to bind to `127.0.0.1`; do not run it on `0.0.0.0` for this local-only increment.
- CORS is limited to `http://localhost:<port>` and `http://127.0.0.1:<port>` origins.
- No mutation endpoints were added. Tests assert the Callosum API routes are GET-only and `POST /papers` returns 405.

## Schema / Frontend Reconciliation Notes

- Attachments do not currently store page count, so the API does not invent a `page_count` value.
- Attachments do not have a separate processing-status column; the API exposes `availability`, `storage_mode`, and related stored fields.
- Full author lists are not normalized into paper columns. The API returns authors by reading the stored CSL-JSON `author` list, with `first_author_family_name` as a fallback. The `q` filter searches normalized title and first-author family name.

## Raw Pytest Output

```text
........................................................................ [ 92%]
......                                                                   [100%]
78 passed in 48.11s
```
