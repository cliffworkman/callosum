# Callosum

[![CI](https://github.com/cliffworkman/callosum/actions/workflows/ci.yml/badge.svg)](https://github.com/cliffworkman/callosum/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Callosum is a local-first, AI-assisted reference manager for scholarly PDFs. Its core thesis is simple: every AI claim must be independently verified against the source. The application imports papers, extracts PDF text with page and bounding-box coordinates, builds local retrieval indexes, and presents synthesis as inspectable evidence rather than authority.

The project is a working MVP at Increment 73. Longer-term plans live under `.claude/docs/future-tracks/`; this README describes the implemented application.

## What Exists Today

- Zotero import for metadata and available PDF attachments.
- PDF text extraction with page numbers and bounding boxes via PyMuPDF.
- Local embeddings and retrieval with `sentence-transformers` and `sqlite-vec`.
- User-defined semantic axes, local axis scoring, clustering, manual assignment, merge/delete flows, and Gemini-assisted axis term suggestions behind the egress gate.
- Tags, Crossref keyword import, and local tag suggestions.
- Citation-grounded VERIFIED synthesis: generated sentences are checked against the cited source using local retrieval, quote extraction, page evidence, stance/confidence, and coordinate precision.
- Citation export in BibTeX, RIS, and CSL-JSON.
- Duplicate detection with reviewable match reasons and persistent dismissals.
- Trash/restore and permanent delete workflows.
- Browser UI served locally by FastAPI, including PDF rendering, highlights, annotations, details editing, duplicate review, axes, tags, summaries, settings, and help.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLite via SQLAlchemy Core and Alembic migrations
- `sqlite-vec` for in-process vector search
- `sentence-transformers` for local embeddings and verification support
- PyMuPDF for PDF text and coordinate extraction
- scikit-learn for clustering
- React JSX chunks and pdf.js assembled without a bundler under `app/frontend/`
- Optional Gemini via `google-genai` for summary generation and selected assistive generation only

Gemini is off by default. Any source-text egress must pass the `CALLOSUM_ALLOW_DATA_EGRESS` consent gate (`1`, `true`, or `yes`) and requires `GOOGLE_API_KEY`.

## Setup

```powershell
pip install -r requirements.txt
```

Run the local app:

```powershell
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Then open:

```text
http://127.0.0.1:8080/
```

By default, the app uses a local SQLite database under `.local/`. Set `CALLOSUM_DB_URL` to point at a different SQLite database.

## Tests

```powershell
pytest
```

## Repository Notes

- Runtime implementation lives under `app/backend/`, `app/frontend/`, and implemented adapters in `integrations/`.
- `pipelines/` and `data/` are not live directories. Earlier planning-only README stubs were archived under `.claude/deprecated/`; implemented pipeline behavior now lives in `app/backend/`.
- `.claude/` is project working memory and planning context, not shipped application code.

## Principles

Callosum follows the commitments in [`.claude/PRINCIPLES.md`](.claude/PRINCIPLES.md): evidence over authority, signal not verdict, inspectability over confidence, and local-first/provider-swappable defaults. READMEs and implementation should not claim more certainty than the code can show.

## License

AGPL-3.0.
