"""FastAPI application factory for local Callosum library access and synthesis.

Thin orchestrator: it wires shared state, runs the startup auto-migration, mounts CORS, serves
the frontend at `/`, and includes the per-resource routers (see `app/backend/api/routers/`).
All endpoint logic + response models live in those router modules.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.backend.api.access_control import AccessControlMiddleware
from app.backend.api.auth.oidc import OidcClient, build_oidc_client_from_env
from app.backend.api.auth.router import router as auth_router
from app.backend.api.frontend import FRONTEND_DIR, build_frontend_document, frontend_sources_available
from app.backend.api.job_store import JobStore
from app.backend.api.routers import (
    acquisition,
    agent,
    annotations,
    axes,
    citation_counts,
    citations,
    discovery,
    duplicates,
    feed,
    findings,
    fulltext,
    gaps,
    health,
    help,
    library,
    libreoffice,
    methods,
    my_publications,
    paper_files,
    papers,
    saved_searches,
    settings,
    summaries,
    sync,
    tags,
    wanted,
    word,
)
from app.backend.api.startup import PROJECT_ROOT, _upgrade_database_to_head, load_local_env
from app.backend.discovery.feed import FeedRegistry, build_default_feed_registry
from app.backend.discovery.providers import SourceRegistry, build_default_registry
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorStore
from app.backend.help.assistant import HelpAssistant
from app.backend.methods.retraction import DEFAULT_CHECKERS as DEFAULT_RETRACTION_CHECKERS
from app.backend.persistence.database import make_engine
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.overview import OverviewGenerator
from app.backend.summarization.verification import StanceScorer, SupportScorer, VerificationConfig
from integrations.crossref import CrossrefClient
from integrations.gemini import AxisClusterLabeler, AxisTermSuggester, ResearchSummaryGenerator
from integrations.openalex import OpenAlexAuthorClient, OpenAlexClient
from integrations.retraction_watch import RetractionWatchClient

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"
FRONTEND_PATH_ENV = "CALLOSUM_FRONTEND_PATH"
# The frontend source of truth is app/frontend/ (assembled by frontend.py). For convenience
# and to support file-based UI testing, `tools/build_frontend.py` rebuilds this single file
# from that source; it is served by default when present, with live assembly as the fallback.
DEFAULT_FRONTEND_PATH = PROJECT_ROOT / "callosum-app.html"


def create_app(
    db_url: str | None = None,
    frontend_path: str | Path | None = None,
    *,
    summary_generator: SummaryGenerator | None = None,
    embedding_model: EmbeddingModel | None = None,
    vector_store: VectorStore | None = None,
    support_scorer: SupportScorer | None = None,
    stance_scorer: StanceScorer | None = None,
    verifier_config: VerificationConfig | None = None,
    axis_term_suggester: AxisTermSuggester | None = None,
    axis_cluster_labeler: AxisClusterLabeler | None = None,
    crossref_client: CrossrefClient | None = None,
    openalex_client: OpenAlexClient | None = None,
    openalex_author_client: OpenAlexAuthorClient | None = None,
    research_summary_generator: ResearchSummaryGenerator | None = None,
    overview_generator: OverviewGenerator | None = None,
    help_assistant: HelpAssistant | None = None,
    discovery_registry: SourceRegistry | None = None,
    feed_registry: FeedRegistry | None = None,
    oidc_client: OidcClient | None = None,
    sync_transport: object | None = None,
) -> FastAPI:
    resolved_db_url = db_url or os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL)
    resolved_frontend_path = _resolve_frontend_path(frontend_path)
    engine = make_engine(resolved_db_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Self-heal: bring the opened DB to the latest schema before serving, so a
        # pre-existing database that predates a migration can't 500 on writes.
        _upgrade_database_to_head(resolved_db_url)
        try:
            yield
        finally:
            engine.dispose()

    api = FastAPI(title="Callosum Local API", version="0.1.0", lifespan=lifespan)
    api.state.engine = engine
    api.state.db_url = resolved_db_url
    api.state.frontend_path = resolved_frontend_path
    api.state.summary_jobs = JobStore()
    api.state.axis_score_jobs = JobStore()
    api.state.axis_suggest_jobs = JobStore()
    api.state.dedup_jobs = JobStore()
    api.state.acquire_jobs = JobStore()
    api.state.wanted_jobs = JobStore()
    api.state.mypubs_jobs = JobStore()
    api.state.mypubs_domain_jobs = JobStore()
    api.state.library_scan_jobs = JobStore()
    api.state.library_import_jobs = JobStore()  # inc 93: citation-file import
    api.state.statcheck_jobs = JobStore()  # inc 97: library-wide statcheck batch
    api.state.pcurve_jobs = JobStore()  # inc 126: collection-level p-curve over a selection
    api.state.retraction_jobs = JobStore()  # inc 131: library-wide retraction batch
    api.state.retraction_checkers = DEFAULT_RETRACTION_CHECKERS  # inc 131: per-source checkers (overridable in tests)
    api.state.retraction_db_jobs = JobStore()  # inc 132: Retraction Watch DB download
    api.state.retraction_watch_client = RetractionWatchClient()  # inc 132: RW download client (overridable in tests)
    api.state.gap_jobs = JobStore()  # inc 135: literature gap-finder
    api.state.citation_count_jobs = JobStore()  # inc 210 (A2): library-wide OpenAlex cited-by refresh
    api.state.metadata_enrich_jobs = JobStore()  # inc 217: multi-pass, gap-filling metadata enrichment
    api.state.enrich_registry = None  # inc 217 test seam: a fake EnrichmentRegistry (else built from the clients)
    api.state.enrich_search_provider = None  # inc 217 test seam: a fake DOI-recovery search provider
    api.state.discovery_registry = discovery_registry or build_default_registry()  # inc 183: discovery Search providers
    api.state.feed_registry = feed_registry or build_default_feed_registry()  # inc 187: Feed sources (bioRxiv)
    api.state.feed_jobs = JobStore()  # inc 187: async Feed refresh (poll subscriptions)
    api.state.acquire_registry = None  # test seam: a fake ResolverRegistry for the wanted re-check job
    api.state.summary_generator = summary_generator
    api.state.embedding_model = embedding_model
    api.state.vector_store = vector_store
    api.state.support_scorer = support_scorer
    api.state.stance_scorer = stance_scorer  # inc 156: NLI stance for highlight-to-evaluate (overridable in tests)
    api.state.verifier_config = verifier_config
    api.state.axis_term_suggester = axis_term_suggester
    api.state.axis_cluster_labeler = axis_cluster_labeler
    api.state.crossref_client = crossref_client
    api.state.openalex_client = openalex_client
    api.state.openalex_author_client = openalex_author_client
    api.state.research_summary_generator = research_summary_generator
    api.state.overview_generator = overview_generator
    api.state.help_assistant = help_assistant
    # Optional account (SP1): the OIDC "Sign in with ORCID" client. None unless configured (issuer/client_id env) or
    # injected by a test. Identity-only — no library egress. Default-off: with no client, /auth/login → 503.
    api.state.oidc_client = oidc_client or build_oidc_client_from_env()
    api.state.sync_transport = (
        sync_transport  # SP3b: a test injects one bound to the in-process server; else built per-run
    )

    api.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    # Remote-access gate (inc 168): when the user enables Remote access (for the Google Docs add-on via a
    # cloudflared tunnel), require a bearer token + rate-limit. OFF by default → a pure pass-through (no change
    # for localhost-only users). Added after CORS so CORS stays the outermost layer (preflight handled there).
    api.add_middleware(AccessControlMiddleware)

    @api.get("/", response_model=None, include_in_schema=False)
    def frontend_shell() -> FileResponse | HTMLResponse:
        # Precedence: an explicit CALLOSUM_FRONTEND_PATH / frontend_path wins; else serve the
        # built callosum-app.html when present (the default, rebuilt from app/frontend/ via
        # tools/build_frontend.py); else assemble the modular source live so we are never broken.
        path = api.state.frontend_path
        if path is not None:
            return _frontend_response(path)
        if DEFAULT_FRONTEND_PATH.is_file():
            return FileResponse(DEFAULT_FRONTEND_PATH, media_type="text/html")
        if frontend_sources_available():
            try:
                # Live assembly precompiles the JSX with esbuild (inc 102). If the build toolchain
                # is absent, degrade to the unavailable response rather than 500 — the normal path
                # serves the prebuilt callosum-app.html and never reaches here.
                return HTMLResponse(build_frontend_document(), media_type="text/html")
            except RuntimeError:
                return _assembly_unavailable_response()
        return _assembly_unavailable_response()

    api.include_router(health.router)
    api.include_router(duplicates.router)  # before papers so "/papers/duplicates*" wins over "/papers/{paper_id}"
    api.include_router(acquisition.router)  # before papers so "/papers/acquire-oa*" wins over "/papers/{paper_id}"
    api.include_router(fulltext.router)  # before papers so "/papers/fulltext" wins over "/papers/{paper_id}" (inc 209)
    api.include_router(
        citation_counts.router
    )  # before papers so "/papers/citation-counts/*" wins over "/papers/{id}" (inc 210)
    api.include_router(wanted.router)
    api.include_router(my_publications.router)
    api.include_router(papers.router)
    api.include_router(paper_files.router)  # /papers/{id}/pdf — split out of papers.py (inc 91)
    api.include_router(methods.router)  # /papers/{id}/statcheck — deterministic Methods producers (inc 95)
    api.include_router(findings.router)  # /papers/{id}/findings — the FACT-vs-CANDIDATE store (inc 130)
    api.include_router(gaps.router)  # /gaps/* — literature gap-finder (inc 135)
    api.include_router(discovery.router)  # /discovery/* — literature Search providers (inc 183)
    api.include_router(feed.router)  # /feed/* — literature Feed: followed sources, polled (inc 187)
    api.include_router(citations.router)  # /citations/* — formatted-citation engine (inc 106)
    api.include_router(annotations.router)
    api.include_router(tags.router)
    api.include_router(saved_searches.router)
    api.include_router(library.router)
    api.include_router(axes.router)
    api.include_router(summaries.router)
    api.include_router(help.router)
    api.include_router(settings.router)  # /settings — BYOK: Gemini key + egress consent from the UI (inc 146)
    api.include_router(
        agent.router
    )  # /agent/* — gated MCP agent writes: tag/axis/reference/note + audit + revert (SP2)
    api.include_router(sync.router)  # /sync/* — opt-in E2E sync: setup/settings/status/run (SP3b, inc 202)
    api.include_router(auth_router)  # /auth/* + /oauth/callback — optional account: Sign in with ORCID (SP1)
    api.include_router(
        libreoffice.router
    )  # /integrations/libreoffice/* — install the LO plugin from Settings (inc 162)
    api.include_router(word.router)  # /integrations/word/* — serve the Word add-in task pane + manifest (inc 164)

    return api


def _resolve_frontend_path(frontend_path: str | Path | None) -> Path | None:
    # An explicit path (arg or CALLOSUM_FRONTEND_PATH) serves a single prebuilt file;
    # None means "assemble the modular source under app/frontend/ at serve time".
    configured = frontend_path or os.environ.get(FRONTEND_PATH_ENV)
    return Path(configured) if configured else None


def _assembly_unavailable_response() -> HTMLResponse:
    expected = escape(str(FRONTEND_DIR))
    env_name = escape(FRONTEND_PATH_ENV)
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><title>Callosum frontend not found</title></head>"
            "<body>"
            "<h1>Callosum frontend source not found</h1>"
            f"<p>The API is running, but the frontend source was not found at <code>{expected}</code>.</p>"
            f"<p>Reinstall the app, or set <code>{env_name}</code> to a prebuilt single-file frontend.</p>"
            "</body></html>"
        ),
        status_code=200,
    )


def _frontend_response(frontend_path: Path) -> FileResponse | HTMLResponse:
    if frontend_path.is_file():
        return FileResponse(frontend_path, media_type="text/html")
    expected = escape(str(frontend_path))
    env_name = escape(FRONTEND_PATH_ENV)
    return HTMLResponse(
        content=(
            "<!doctype html><html><head><title>Callosum frontend not found</title></head>"
            "<body>"
            "<h1>Callosum frontend file not found</h1>"
            f"<p>The API is running, but no frontend HTML file was found at <code>{expected}</code>.</p>"
            f"<p>Set <code>{env_name}</code> to the path of <code>callosum-app.html</code>, "
            "or place the file at the default repository-root location.</p>"
            "</body></html>"
        ),
        status_code=200,
    )


# Load a local .env (gitignored) into the environment before building the default app, so a
# user's GOOGLE_API_KEY / flags are picked up without manual export (no-op under pytest).
load_local_env()
app = create_app()
