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
from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from app.backend.api.access_control import AccessControlMiddleware
from app.backend.api.auth.oidc import OidcClient, build_oidc_client_from_env
from app.backend.api.auth.router import router as auth_router
from app.backend.api.frontend import FRONTEND_DIR, build_frontend_document, frontend_sources_available
from app.backend.api.job_store import JobStore
from app.backend.api.routers import (
    access,
    acquisition,
    agent,
    annotations,
    axes,
    citation_context,
    citation_counts,
    citation_equity,
    citation_style_lifecycle,
    citations,
    credit,
    critical_review,
    discovery,
    duplicates,
    feed,
    feedback,
    findings,
    fulltext,
    funding,
    gaps,
    health,
    help,
    library,
    library_enrich,
    libreoffice,
    lmm,
    metaanalysis,
    methods,
    methods_bayes,
    methods_grim_saved,
    methods_retraction,
    methods_statcheck_cache,
    my_publication_citing_authors,
    my_publication_gaps,
    my_publication_topics,
    my_publications,
    ocr,
    overlooked,
    paper_enrich,
    paper_files,
    paper_urls,
    papers,
    publishers,
    reading_queue,
    reference_integrity,
    registration_acquisition,
    registration_commitments,
    registration_comparisons,
    registration_discovery,
    registration_retrieval,
    saved_searches,
    settings,
    settings_providers,
    status,
    summaries,
    sync,
    tags,
    text_health,
    transparency,
    wanted,
    wip,
    wip_checks,
    wip_provenance,
    wip_workflow,
    word,
    workbench,
)
from app.backend.api.sqlite_retry_middleware import SqliteWriteRetryMiddleware
from app.backend.api.startup import PROJECT_ROOT, _upgrade_database_to_head, load_local_env
from app.backend.discovery.feed import FeedRegistry, build_default_feed_registry
from app.backend.discovery.providers import SourceRegistry, build_default_registry
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorStore
from app.backend.feedback.relay_client import FeedbackRelayClient, HttpFeedbackRelayClient
from app.backend.help.assistant import HelpAssistant
from app.backend.methods.retraction import DEFAULT_CHECKERS as DEFAULT_RETRACTION_CHECKERS
from app.backend.persistence.database import make_engine
from app.backend.registration_acquisition.domain import RegistrationAcquisitionRegistry
from app.backend.registration_discovery.domain import RegistrationDiscoveryRegistry
from app.backend.summarization.generators import SummaryGenerator
from app.backend.summarization.overview import OverviewGenerator
from app.backend.summarization.verification import StanceScorer, SupportScorer, VerificationConfig
from integrations.crossref import CrossrefClient
from integrations.doaj.journals import DoajJournalsClient
from integrations.gemini import AxisClusterLabeler, AxisTermSuggester, ResearchSummaryGenerator
from integrations.gemini.extraction_assistant import ExtractionAssistant
from integrations.openalex import OpenAlexAuthorClient, OpenAlexClient
from integrations.openalex.sources import OpenAlexSourcesClient
from integrations.retraction_watch import RetractionWatchClient
from integrations.semantic_scholar.adapter import SemanticScholarClient

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
    openalex_sources_client: OpenAlexSourcesClient | None = None,
    doaj_journals_client: DoajJournalsClient | None = None,
    semantic_scholar_client: SemanticScholarClient | None = None,
    research_summary_generator: ResearchSummaryGenerator | None = None,
    overview_generator: OverviewGenerator | None = None,
    extraction_assistant: ExtractionAssistant | None = None,
    help_assistant: HelpAssistant | None = None,
    discovery_registry: SourceRegistry | None = None,
    feed_registry: FeedRegistry | None = None,
    registration_discovery_registry: RegistrationDiscoveryRegistry | None = None,
    registration_acquisition_registry: RegistrationAcquisitionRegistry | None = None,
    oidc_client: OidcClient | None = None,
    sync_transport: object | None = None,
    feedback_relay_client: FeedbackRelayClient | None = None,
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
    api.state.my_publication_gap_jobs = JobStore()
    api.state.my_publication_citing_author_jobs = JobStore()
    api.state.my_publication_topic_jobs = JobStore()
    api.state.openalex_citing_authors_client = None
    api.state.openalex_citing_topics_client = None
    api.state.library_scan_jobs = JobStore()
    api.state.library_scan_singleflight_lock = Lock()  # one scan/rescan writer at a time
    api.state.active_library_scan_job_id = None
    api.state.wip_scan_jobs = JobStore()
    api.state.wip_scan_singleflight_lock = Lock()
    api.state.active_wip_scan_job_id = None
    api.state.library_import_jobs = JobStore()  # inc 93: citation-file import
    api.state.library_bundle_import_jobs = JobStore()  # B2 SP1 (inc 234): portable library bundle import
    api.state.statcheck_jobs = JobStore()  # inc 97: library-wide statcheck batch
    api.state.pcurve_jobs = JobStore()  # inc 126: collection-level p-curve over a selection
    api.state.retraction_jobs = JobStore()  # inc 131: library-wide retraction batch
    api.state.lmm_jobs = JobStore()  # backlog #23 F1: library-wide LMM reporting-completeness batch
    api.state.meta_jobs = JobStore()  # backlog #23 F1: library-wide meta-analysis reporting-completeness batch
    api.state.bayes_jobs = JobStore()  # backlog #23 F1: library-wide Bayesian auditor batch
    api.state.retraction_checkers = DEFAULT_RETRACTION_CHECKERS  # inc 131: per-source checkers (overridable in tests)
    api.state.transparency_jobs = JobStore()  # inc 251: library-wide transparency-signals batch (#44)
    api.state.registration_discovery_jobs = JobStore()
    api.state.registration_discovery_registry = registration_discovery_registry
    api.state.registration_acquisition_jobs = JobStore()
    api.state.registration_acquisition_registry = registration_acquisition_registry
    api.state.registration_comparison_jobs = JobStore()
    api.state.registration_comparison_triage_evaluator = None
    api.state.retraction_db_jobs = JobStore()  # inc 132: Retraction Watch DB download
    api.state.retraction_watch_client = RetractionWatchClient()  # inc 132: RW download client (overridable in tests)
    api.state.gap_jobs = JobStore()  # inc 135: literature gap-finder
    api.state.overlooked_lens_jobs = JobStore()  # backlog #37: overlooked-work lens (per-axis discovery)
    api.state.citation_count_jobs = JobStore()  # inc 210 (A2): library-wide OpenAlex cited-by refresh
    api.state.critical_review_jobs = JobStore()  # backlog #12: single-paper critical-read (scrutiny surface)
    api.state.critical_review_set_jobs = JobStore()  # backlog #12: set (multi-paper) critical review
    api.state.critical_review_set_generator = None  # test seam for the Tier-2 set generator
    api.state.citation_equity_jobs = JobStore()  # inc 227 (#25): per-paper structural citation-equity audit
    api.state.overlooked_jobs = JobStore()  # inc 228 (#25 SP2): topical overlooked-work remediation
    api.state.metadata_enrich_jobs = JobStore()  # inc 217: multi-pass, gap-filling metadata enrichment
    api.state.ocr_jobs = JobStore()  # inc 231 (B3): per-paper OCR of a scanned PDF into a searchable copy
    api.state.text_health_jobs = JobStore()  # local PDF text-health batch reprocessing
    api.state.citation_context_jobs = JobStore()  # inc 232 (B4): per-paper "how this paper is cited" (scite analogue)
    api.state.publishers_jobs = JobStore()  # #40: PUBLISHERS "where to submit" journal-finder (SP1a)
    api.state.reference_integrity_jobs = JobStore()  # Meta Reference List: per-paper reference-integrity scan
    api.state.funding_jobs = JobStore()  # Funding Discovery: latent prospect discovery and opportunity resolution
    api.state.funding_award_provider = None  # test seam for bounded historical-award evidence
    api.state.funding_grants_gov_client = None  # test seam for current federal-opportunity evidence
    api.state.funding_openalex_provider = None  # test seam for scholarly funding-lineage evidence
    api.state.funding_crossref_provider = None  # test seam for Crossref grant metadata evidence
    api.state.funding_llm_triage_evaluator = None  # optional AI triage over already-surfaced funding results
    api.state.enrich_registry = None  # inc 217 test seam: a fake EnrichmentRegistry (else built from the clients)
    api.state.enrich_search_provider = None  # inc 217 test seam: a fake DOI-recovery search provider
    api.state.discovery_registry = discovery_registry or build_default_registry()  # inc 183: discovery Search providers
    api.state.citation_openalex_provider = None  # SP2 Cite: optional beyond-library OpenAlex provider test seam
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
    api.state.openalex_sources_client = openalex_sources_client  # #40: OpenAlex journals for the where-to-submit tool
    api.state.doaj_journals_client = doaj_journals_client  # #40: DOAJ journal facts (APC/waiver/Seal/license)
    api.state.semantic_scholar_client = semantic_scholar_client  # inc 232 (B4): citation-context data source
    api.state.openalex_author_client = openalex_author_client
    api.state.research_summary_generator = research_summary_generator
    api.state.overview_generator = overview_generator
    api.state.extraction_assistant = extraction_assistant  # SP2b: assisted-extraction funnel (None → built per-request)
    api.state.help_assistant = help_assistant
    # Optional account (SP1): the OIDC "Sign in with ORCID" client. None unless configured (issuer/client_id env) or
    # injected by a test. Identity-only — no library egress. Default-off: with no client, /auth/login → 503.
    api.state.oidc_client = oidc_client or build_oidc_client_from_env()
    api.state.sync_transport = (
        sync_transport  # SP3b: a test injects one bound to the in-process server; else built per-run
    )
    api.state.feedback_relay_client = feedback_relay_client or HttpFeedbackRelayClient.from_env()

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
    # Backstop for the "database is locked" transient writer-lock (Layer 2; Layer 1 is run_write in the hot
    # short-write endpoints). Added last → innermost user middleware, so it wraps just the route execution and
    # catches the OperationalError before it becomes a 500. Retries only replay-safe mutating requests.
    api.add_middleware(SqliteWriteRetryMiddleware)

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
    api.include_router(feedback.router)  # explicit, bounded proxy to the separately hosted feedback relay
    api.include_router(duplicates.router)  # before papers so "/papers/duplicates*" wins over "/papers/{paper_id}"
    api.include_router(acquisition.router)  # before papers so "/papers/acquire-oa*" wins over "/papers/{paper_id}"
    api.include_router(fulltext.router)  # before papers so "/papers/fulltext" wins over "/papers/{paper_id}" (inc 209)
    api.include_router(
        citation_counts.router
    )  # before papers so "/papers/citation-counts/*" wins over "/papers/{id}" (inc 210)
    api.include_router(ocr.router)  # before papers so "/papers/ocr/*" wins over "/papers/{paper_id}" (inc 231)
    api.include_router(text_health.router)  # before papers so "/papers/text-health/*" wins over "/papers/{paper_id}"
    api.include_router(
        citation_context.router
    )  # before papers so "/papers/citation-context/*" wins over "/papers/{id}" (inc 232)
    api.include_router(wanted.router)
    api.include_router(my_publications.router)
    api.include_router(my_publication_gaps.router)
    api.include_router(my_publication_citing_authors.router)
    api.include_router(my_publication_topics.router)
    api.include_router(
        paper_enrich.router
    )  # /papers/{id}/re-resolve + /fill-metadata — split out of papers.py (inc 226)
    api.include_router(paper_urls.router)  # /papers/{id}/urls — first-class extra URL rows
    api.include_router(workbench.router)  # /workbench/* — the meta-analysis extraction workspace (inc 253)
    api.include_router(papers.router)
    api.include_router(paper_files.router)  # /papers/{id}/pdf — split out of papers.py (inc 91)
    api.include_router(methods.router)  # /papers/{id}/statcheck — deterministic Methods producers (inc 95)
    api.include_router(
        methods_statcheck_cache.router
    )  # /papers/{id}/statcheck/cached,/rescan — per-paper cache, split from methods.py (inc 400)
    api.include_router(
        methods_grim_saved.router
    )  # /papers/{id}/grim-checks — saved GRIM/GRIMMER checks, split from methods.py (inc 401)
    api.include_router(
        methods_retraction.router
    )  # /methods/retraction/* — retraction findings, split from methods.py (inc 261)
    api.include_router(
        methods_bayes.router
    )  # /papers/{id}/bayes + /methods/bayes/* — Bayesian auditor, split from methods.py (backlog #23, inc 338)
    api.include_router(citation_equity.router)  # /methods/citation-equity/* — structural reference-list audit (inc 227)
    api.include_router(publishers.router)  # /methods/publishers/* — "where to submit" journal-finder (#40)
    api.include_router(reference_integrity.router)  # /papers/{id}/reference-integrity — Meta Reference List
    api.include_router(funding.router)  # /funding-discovery/* — Theory-pane funding prospects
    api.include_router(credit.router)  # /credit/* — CRediT contribution-statement builder (#26, inc 261)
    api.include_router(
        critical_review.router
    )  # /papers/{id}/critical-read — the critical-review scrutiny surface (#12)
    api.include_router(lmm.router)  # /papers/{id}/lmm — LMM-reporting completeness auditor (#23, inc 247)
    api.include_router(
        metaanalysis.router
    )  # /papers/{id}/meta-analysis — meta-analysis reporting auditor (#36, inc 249)
    api.include_router(transparency.router)  # /papers/{id}/transparency — transparency-signals auditor (#44, inc 250)
    api.include_router(registration_discovery.router)  # explicit metadata-only registration candidate discovery
    api.include_router(registration_acquisition.router)  # confirmed public registration artifact acquisition
    api.include_router(registration_commitments.router)  # local canonical registration plan extraction
    api.include_router(registration_retrieval.router)  # bounded article/supplement evidence retrieval
    api.include_router(registration_comparisons.router)  # persisted evidence crosswalk + review/staleness
    api.include_router(findings.router)  # /papers/{id}/findings — the FACT-vs-CANDIDATE store (inc 130)
    api.include_router(gaps.router)  # /gaps/* — literature gap-finder (inc 135)
    api.include_router(overlooked.router)  # /overlooked/* — overlooked-work lens: per-axis discovery (#37)
    api.include_router(discovery.router)  # /discovery/* — literature Search providers (inc 183)
    api.include_router(feed.router)  # /feed/* — literature Feed: followed sources, polled (inc 187)
    api.include_router(citation_style_lifecycle.router)  # explicit CSL provenance/update/copy lifecycle (inc 369)
    api.include_router(citations.router)  # /citations/* — formatted-citation engine (inc 106)
    api.include_router(annotations.router)
    api.include_router(tags.router)
    api.include_router(saved_searches.router)
    api.include_router(reading_queue.router)  # /reading-queue/* — the to-read Queue tab (inc 219)
    api.include_router(library.router)
    api.include_router(wip.router)  # /wip/* — local-only unpublished manuscript workspaces
    api.include_router(wip_checks.router)
    api.include_router(wip_provenance.router)
    api.include_router(wip_workflow.router)
    api.include_router(library_enrich.router)  # /library/enrich/refresh — split out of library.py (rule #1)
    api.include_router(axes.router)
    api.include_router(summaries.router)
    api.include_router(help.router)
    api.include_router(settings.router)  # /settings — BYOK: Gemini key + egress consent from the UI (inc 146)
    api.include_router(settings_providers.router)  # /settings/providers — unified custom-provider roster (inc 256)
    api.include_router(access.router)  # /access/recover — in-app recovery from a remote-access lockout (inc 254)
    api.include_router(status.router)  # /status/jobs — cross-feature async-job aggregator (inc 406)
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
