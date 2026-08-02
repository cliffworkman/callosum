# Architecture

Callosum is a working local-first MVP at Increment 73. It runs as a localhost FastAPI + Uvicorn service with a browser UI served at `/`, backed by SQLite and local ML components.

## Runtime Shape

- Backend: Python 3.11+, FastAPI, Uvicorn (`app/backend/api/app.py`).
- Persistence: SQLite through SQLAlchemy Core 2.0 (`app/backend/persistence/schema.py`) with Alembic auto-migration on startup (`app/backend/api/startup.py`). Current head is `0006_dismissed_duplicate_pairs`.
- Vectors: `sqlite-vec` in-process, with sentence-transformers embeddings. Default model is `all-MiniLM-L6-v2`; `bge-base-en-v1.5` is also supported.
- PDF extraction: PyMuPDF (`fitz`) extracts text spans and `pdf-points-top-left` bounding boxes.
- Retrieval and clustering: local embedding retrieval plus scikit-learn agglomerative clustering, axis scoring, duplicate detection, and c-TF-IDF tag/axis suggestions.
- Summarization: Gemini `gemini-2.5-flash-lite` is optional, off by default, and used only to propose summary sentences/candidate citations. Local verification is authoritative.
- Frontend: `app/frontend/` contains `index.html`, `styles.css`, and ordered `js/*.jsx` React chunks. `app/backend/api/frontend.py` assembles them for FastAPI; `tools/build_frontend.py` rebuilds `callosum-app.html`.
- Feedback: `app/backend/feedback/` owns the shared strict schema and fixed-destination local relay client;
  `feedback_relay/` is a separately deployed FastAPI service with rate limiting and a generic publisher protocol.
  Only the hosted service imports the Slack publisher/webhook configuration, so Tauri staging contains no Slack
  credential or publication code.

## Backend Modules

- `app/backend/api/`: app factory, startup, dependency wiring, generic async `JobStore`, frontend serving, and routers for health, papers, duplicates, annotations, tags, axes, summaries, and help.
- `app/backend/persistence/`: SQLAlchemy schema, database wiring, repository functions, duplicate-dismissal data access, and tag data access.
- `app/backend/pdf_processing/`: PDF ingest, PyMuPDF extraction, quote matching, citation-location lookup, and CLI helpers.
- `app/backend/embeddings/`: embedding model wrappers, embedding pipeline, `sqlite-vec` vector store, and retrieval.
- `app/backend/clustering/`: abstract clustering, user-defined axes, manual assignments, axis operations, optimal-axis suggestion, duplicate detection, and tag suggestion.
- `app/backend/summarization/`: summary orchestration, generator protocols, and local citation verification.
- `app/backend/llm/`: provider-neutral egress gates, content-addressed summary cache, and token usage logging.
- `app/backend/help/`: shipped help corpus and optional AI help assistant protocol.
- `app/backend/importers/`: Zotero importer.
- `app/backend/metadata/`: DOI enrichment, safe paper edits, abstract display cleanup, and BibTeX/RIS/CSL-JSON export.

## External Adapters

Implemented adapters live under `integrations/`: Zotero, Crossref, and Gemini. OpenAlex, Semantic Scholar, GROBID, and Mendeley currently remain README/stub future or import-coverage surfaces, not active integrations.

## Trust Spine

External LLM output is never final citation evidence. Summary generation proposes sentence/citation candidates; `app/backend/summarization/verification.py` then verifies each citation locally with embedding retrieval, verbatim quote matching, and NLI support scoring. The UI shows quote text, page, component confidences, status, and coordinate precision.

`coordinate_precision` is part of the evidence contract:

- `exact`: draw precise PDF rectangles.
- `region`: open the page/area and label it as approximate.
- `null`: open the page if known, draw no rectangle.

## Local-First Boundary

Extraction, embeddings, retrieval, clustering, duplicate detection, tag suggestion, citation verification, and PDF display are local. Gemini calls are blocked unless `CALLOSUM_ALLOW_DATA_EGRESS` is explicitly set to `1`, `true`, or `yes`; the authoritative wrapper is `app/backend/llm/egress.py`.

Feedback is a separate, explicit, previewed egress channel. The React dialog sends the displayed version-1 JSON to
the local `/feedback/reports` proxy; that proxy can reach only `CALLOSUM_FEEDBACK_RELAY_URL`. The hosted relay repeats
strict validation, rate-limits by verified account or IP, and invokes `FeedbackPublisher`. Slack is the sole current
publisher. No feedback content is persisted, automatically retried, or derived from library/WIP/PDF state.
