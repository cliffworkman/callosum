# Architecture

Callosum is a working local-first MVP at Increment 73. It runs as a localhost FastAPI + Uvicorn service with a browser UI served at `/`, backed by SQLite and local ML components.

## Runtime Shape

- Backend: Python 3.11+, FastAPI, Uvicorn (`app/backend/api/app.py`).
- Persistence: SQLite through SQLAlchemy Core 2.0 (`app/backend/persistence/schema.py`) with Alembic auto-migration on startup (`app/backend/api/startup.py`). Current head is `0006_dismissed_duplicate_pairs`.
- Vectors: `sqlite-vec` in-process, with sentence-transformers embeddings. Default model is `all-MiniLM-L6-v2`; `bge-base-en-v1.5` is also supported.
- Local model lifetime: each FastAPI app owns a `ModelRuntimeRegistry` (`app/backend/model_runtime.py`). Compatible
  embedding and NLI feature wrappers share one lazy runtime per model name/revision/device/offline/backend identity;
  first load and inference use separate per-identity locks, and explicit injected test/custom dependencies win.
- LLM provider-client lifetime: each FastAPI app owns a `ProviderClientRuntime`
  (`app/backend/provider_runtime.py`). Compatible raw HTTP requests share one lazy HTTPX connection pool and
  compatible Gemini requests share one lazy SDK client; non-reversible endpoint/credential identities prevent
  stale configuration reuse, explicit client injection wins, and lifespan shutdown closes owned resources.
- PDF extraction: PyMuPDF (`fitz`) extracts text spans and `pdf-points-top-left` bounding boxes.
- Retrieval and clustering: local embedding retrieval plus scikit-learn agglomerative clustering, axis scoring, duplicate detection, and c-TF-IDF tag/axis suggestions.
- Summarization: Gemini `gemini-2.5-flash-lite` is optional, off by default, and used only to propose summary sentences/candidate citations. Local verification is authoritative.
- Frontend: `app/frontend/` contains `index.html`, `styles.css`, and ordered `js/*.jsx` React chunks. `app/backend/api/frontend.py` assembles them for FastAPI; `tools/build_frontend.py` rebuilds `callosum-app.html`.
- Packaged desktop: Tauri owns the Python/Uvicorn process tree. The main UI backend uses its remembered successful
  loopback port; an explicitly enabled Word integration uses a separate fixed `127.0.0.1:8443` HTTPS child.
  Python owns its per-user localhost leaf-certificate/trust lifecycle, while Tauri alone supervises the child.
  Browser/source use retains the separate developer-certificate launcher; neither path introduces egress.
- Static demo: the same assembled frontend calls the centralized `callosumFetch` transport. Normal builds use
  FastAPI; the explicit demo build injects a static provider backed by a validated, versioned public snapshot.
  `tools/demo/build_demo.py` emits a backend-free artifact and leaves normal web/desktop behavior unchanged.
- Feedback: `app/backend/feedback/` owns the shared strict schema and fixed-destination local relay client;
  `feedback_relay/` is a separately deployed FastAPI service with rate limiting and a generic publisher protocol.
  Only the hosted service imports the Slack publisher/webhook configuration, so Tauri staging contains no Slack
  credential or publication code.

## Backend Modules

- `app/backend/api/`: app factory, startup, dependency wiring, generic async `JobStore`, frontend serving, and routers for health, papers, duplicates, annotations, tags, axes, summaries, and help.
- `app/backend/persistence/`: SQLAlchemy schema, database wiring, repository functions, duplicate-dismissal data access, and tag data access.
- `app/backend/pdf_processing/`: PDF ingest, PyMuPDF extraction, quote matching, citation-location lookup, and CLI helpers.
- `app/backend/embeddings/`: embedding model wrappers, embedding pipeline, `sqlite-vec` vector store, and retrieval.
- `app/backend/model_runtime.py`: app-scoped ownership, identity resolution, lazy loading, and conservative
  per-runtime inference serialization for SentenceTransformer and CrossEncoder objects.
- `app/backend/provider_runtime.py`: app-scoped lazy ownership, configuration identity, connection-pool / Gemini
  client reuse, first-construction race protection, and provider-client shutdown cleanup.
- `app/backend/clustering/`: abstract clustering, user-defined axes, manual assignments, axis operations, optimal-axis suggestion, duplicate detection, and tag suggestion.
- `app/backend/summarization/`: summary orchestration, generator protocols, and local citation verification.
- `app/backend/llm/`: provider-neutral egress gates, content-addressed summary cache, and token usage logging.
- `app/backend/help/`: shipped help corpus and optional AI help assistant protocol.
- `app/backend/importers/`: Zotero importer; dormant bounded Mendeley snapshot→canonical-paper/collection mapper;
  and the shared imported-folder/group → ordinary-axis snapshot seam. Legacy EndNote `.enlx` remains research-
  only: the approved future seam is a one-shot, no-listener MariaDB bootstrap child over a private copied
  datadir, not a persistent database service. `tools/endnote/legacy_bootstrap.py` is the adversarially tested
  developer-only proof of that seam; the backend imports neither it nor a database runtime.
- `app/backend/metadata/`: DOI enrichment, safe paper edits, abstract display cleanup, and BibTeX/RIS/CSL-JSON export.
- `app/backend/wip/` plus `persistence/wip_*`: local unpublished-manuscript discovery, bounded primary-file text
  extraction, exact checkpoints, and generic snapshot-bound tool receipts/findings. Deterministic WIP checks reuse
  the same pure statcheck/Transparency/LMM/Bayesian/meta-analysis detectors as Library papers without creating a `papers.id`;
  method-specific adapters map their distinct evidence semantics into the shared WIP provenance tables.

## External Adapters

Implemented adapters live under `integrations/`: Zotero, Crossref, and Gemini. Mendeley has a dormant,
bounded/version-pinned official-API client plus a transport-free snapshot importer that reuses canonical
paper identity and generic imported collections. No OAuth route, token persistence, PDF download, or UI is
active; native use still awaits a desktop-safe registration/redirect design and live contract validation.
OpenAlex, Semantic Scholar, and GROBID currently remain README/stub future or import-coverage surfaces, not
active integrations.

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

## Static Demo Trust Boundary

The online demo is a separate deployment shape, not a hosted Callosum server. `app/backend/demo_snapshot.py`
combines strict demo metadata with the live paper/summary API response models. A whitelist exporter reads an
explicitly named dedicated database in read-only mode, strips all storage paths and private identifiers, verifies
licensed assets by checksum, and fails on unknown fields, credential markers, or machine paths. The committed
bundle contains only public data and licensed PDFs.

The current snapshot schema also embeds the live statcheck/four-checklist response models for every curated paper, their library
summary counts, a bounded completed Status receipt, a strict WIP state contract, and a strict extended-state
contract for saved Discover, Work, and additional Library results. The extended fixture is captured from a fresh
three-paper sandbox through production response models; the static provider exposes GET-shaped saved-artifact
routes so the ordinary Search, Journals, Funding, Followed Authors, Cite, Meta-Reference, CRediT, Statements, and
Meta-Analyze components remain the renderers. `demo/coverage-v1.json` is a build-validated workspace inventory
whose status must agree with the centralized capability map. `demo/experience-coverage-v1.json` separately
classifies every public-site capability claim, and the build rejects unclassified or stale claim ids; this makes
website-to-demo drift visible without coupling ordinary frontend visual changes to snapshot regeneration. The WIP fixture is generated
by migrating a fresh temporary database and driving the real manuscript discovery, workflow, provenance,
reference-link, and five deterministic-check endpoints over two public synthetic drafts; no working library is
read. A generated config starts the shared shell in Library and
identifies the saved synthesis only when Synthesize or its receipt is activated. `demo/demo-runtime.js` answers
those read-only API calls in memory. It rejects mutations and unknown routes locally;
its browser network guard permits only files under the configured same-origin base path. The artifact contains no
backend address or computational endpoint. Production FastAPI and Tauri builds do not include the runtime or
snapshot. See `demo/README.md` for the full data, licensing, drift, and deployment contract.

The only possible working-library input is the separately reviewed Feed candidate. Its whitelist exporter writes
under `.local`, removes database identity, and requires the exact candidate SHA-256 before records may enter the
public extended state. Unapproved Feed state is structurally required to be empty.

Saved Synthesize coverage lives in the separately generated `demo/synthesis-state-v1.json` and validates through
`DemoSynthesisState`. Critique, registration links/versions, and comparison runs/details embed production API
response models. The static provider only indexes those responses; the shared Critique and Meta-Preregistration
components remain the rendering paths. A public registry record with unclear reuse rights is excluded: its strict
license audit and bounded evidence remain, while the complete registration does not enter the artifact.
