# Backend Scope

## Purpose

The backend should be a local Python service, likely FastAPI, responsible for local API endpoints, job orchestration, persistence access, and coordination between importers, pipelines, and external adapters.

## Planned Responsibilities

- Serve local HTTP API routes for the frontend.
- Manage library records, attachments, collections, tags, annotations, and processing state.
- Start and track import, extraction, embedding, clustering, and summarization jobs.
- Read and write SQLite records through a defined data access layer.
- Query the vector store.
- Expose source-coordinate data needed by the PDF viewer.
- Keep Gemini, OpenAlex, Semantic Scholar, GROBID, and Zotero details behind adapters.

## Persistence Decision

Use SQLAlchemy Core with Alembic migrations as the initial SQLite access pattern. This keeps the schema explicit while avoiding a heavy ORM model before the data contract stabilizes.

Every mutating workflow should write processing state and versions so failed or stale pipeline steps can be resumed or invalidated without guessing.

## Open Decisions

- Whether to use async jobs in-process first or introduce a worker queue.
- Whether the backend should own static frontend serving or run separately during development.
- How to represent job progress and recover failed processing steps.

## First Validation

The first backend milestone should expose enough local API shape to list imported papers, inspect one paper, and retrieve PDF-page evidence coordinates.
