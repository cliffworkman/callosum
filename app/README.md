# App

`app/` contains the implemented local application.

## Current Layout

- `backend/`: FastAPI app, routers, persistence, PDF extraction, embeddings, retrieval, clustering, tags, duplicate detection, summarization, verification, help, importers, and metadata services.
- `frontend/`: browser UI source (`index.html`, `styles.css`, ordered `js/*.jsx` chunks) assembled and served by the backend.
- `desktop-shell/`: planned post-V1 desktop wrapper. Not yet implemented.

The old planning split between `pipelines/` and `data/` is no longer live. Import, extraction, embedding, clustering, retrieval, summaries, metadata, tags, and citation export are implemented in `app/backend/`.

## Runtime Entry Point

Start the app from the project root:

```powershell
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

FastAPI serves the frontend at `http://127.0.0.1:8080/`.

## Boundaries

Callosum is local-first. Extraction, embeddings, vector search, clustering, duplicate detection, tag suggestion, and verification run locally. External generation is optional and must pass the data-egress consent gate.
