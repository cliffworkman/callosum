"""Versioned public-demo snapshot contract.

The snapshot deliberately embeds the live API response models consumed by the shared frontend. Demo-only
metadata describes the immutable bundle, capabilities, licensing, and asset locations; it does not duplicate
paper or synthesis presentation models.
"""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.backend.api.routers.axes_models import AxisResponse, ClusterNodeResponse, ClusterPaperResponse
from app.backend.api.routers.critical_review import (
    CandidateListResponse,
    CriticalReadJobResponse,
    MethodSignalResponse,
    ScrutinyBackboneResponse,
)
from app.backend.api.routers.health import HealthResponse
from app.backend.api.routers.help import HelpCorpusResponse, HelpSectionResponse
from app.backend.api.routers.lmm import LmmCheckOut, LmmLibrarySummary, LmmResponse
from app.backend.api.routers.metaanalysis import MetaCheckOut, MetaLibrarySummary, MetaResponse
from app.backend.api.routers.methods import StatcheckCoverage, StatcheckLibrarySummary, StatcheckResult
from app.backend.api.routers.methods_bayes import (
    BayesAdvisoryNote,
    BayesCompletenessItem,
    BayesCompletenessOut,
    BayesLibrarySummary,
    BayesResponse,
    BayesResult,
)
from app.backend.api.routers.methods_statcheck_cache import StatcheckCacheResponse
from app.backend.api.routers.my_publications import (
    CitingResponse,
    CitingWorkResponse,
    DashboardResponse,
    ProfileResponse,
)
from app.backend.api.routers.paper_models import AttachmentResponse, PaperDetailResponse, PaperListItem
from app.backend.api.routers.reading_queue import ReadingQueueItem
from app.backend.api.routers.registration_acquisition import RegistrationVersionOut
from app.backend.api.routers.registration_comparisons import ComparisonRowOut, ComparisonRunDetail, ComparisonRunSummary
from app.backend.api.routers.registration_discovery import RegistrationLinkOut
from app.backend.api.routers.status import StatusJob, StatusProgress, StatusResponse
from app.backend.api.routers.summaries import (
    SummarizeJobResponse,
    SummaryCitationResponse,
    SummaryListItem,
    SummarySentenceResponse,
)
from app.backend.api.routers.tags import SuggestedTagsResponse, TagSummary
from app.backend.api.routers.transparency import (
    RegistrationReferenceOut,
    TransparencyCheckOut,
    TransparencyLibrarySummary,
    TransparencyResponse,
)
from app.backend.demo_extended_state import DemoExtendedState
from app.backend.demo_synthesis_state import DemoSynthesisState
from app.backend.demo_wip_state import DemoWipState

SNAPSHOT_SCHEMA_VERSION = 9
SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS = {SNAPSHOT_SCHEMA_VERSION}

_WINDOWS_PATH = re.compile(r"(?:^|[\s\"'])(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+)")
_POSIX_PRIVATE_PATH = re.compile(r"(?:^|[\s\"'])/(?:Users|home|var|tmp|private|mnt)/", re.IGNORECASE)
_OPENAI_KEY = re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}")
_FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "original_path",
    "resolved_path",
    "zotero_library_id",
    "zotero_item_key",
    "sync_id",
    "recovery_code",
    "private_notes",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoCapabilities(StrictModel):
    library_browse: bool = True
    library_search: bool = True
    document_read: bool = True
    synthesis_inspect: bool = True
    evidence_navigation: bool = True
    saved_method_results_inspect: bool = True
    saved_status_receipts_inspect: bool = True
    saved_wip_inspect: bool = True
    saved_critique_inspect: bool = True
    saved_registration_inspect: bool = True
    mutations: bool = False
    method_execution: bool = False
    synthesis_generation: bool = False
    external_discovery: bool = False
    provider_configuration: bool = False
    desktop_integrations: bool = False
    network_egress: bool = False


class DemoWorkspaceCapability(StrictModel):
    mode: Literal["saved", "ephemeral-local", "visible-disabled"]
    note: str


class DemoLicense(StrictModel):
    work_title: str
    authors: list[str]
    license_name: str
    license_url: str
    redistribution_basis: str
    canonical_url: str
    doi: str | None = None
    attribution: str
    verified_via: str
    verified_on: str
    bundled_material: Literal["complete-pdf", "metadata-and-evidence-only"]
    notice: str | None = None


class DemoDocument(StrictModel):
    paper_id: int
    asset_path: str | None = None
    media_type: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    license: DemoLicense

    @model_validator(mode="after")
    def validate_public_asset(self) -> "DemoDocument":
        if self.asset_path is None:
            if self.sha256 is not None or self.media_type is not None:
                raise ValueError("document hash/media type require a bundled asset")
            return self
        path = PurePosixPath(self.asset_path)
        if path.is_absolute() or len(path.parts) != 2 or path.parts[0] != "documents" or ".." in path.parts:
            raise ValueError("demo document asset_path must be documents/<filename>")
        if self.sha256 is None or self.media_type != "application/pdf":
            raise ValueError("bundled demo documents require a PDF media type and SHA-256")
        return self


class DemoPaper(StrictModel):
    list_item: PaperListItem
    detail: PaperDetailResponse
    document: DemoDocument
    methods: "DemoMethodSnapshots"


class DemoMethodSnapshots(StrictModel):
    statcheck: StatcheckCacheResponse
    transparency: TransparencyResponse
    lmm: LmmResponse
    bayes: BayesResponse
    meta_analysis: MetaResponse


class DemoMethodSummaries(StrictModel):
    statcheck: StatcheckLibrarySummary
    transparency: TransparencyLibrarySummary
    lmm: LmmLibrarySummary
    bayes: BayesLibrarySummary
    meta_analysis: MetaLibrarySummary


class DemoApi(StrictModel):
    health: HealthResponse
    help_corpus: HelpCorpusResponse
    settings: dict[str, JsonValue]
    papers: list[DemoPaper]
    axes: list[AxisResponse]
    axis_clusters: dict[str, list[ClusterNodeResponse]]
    tags: list[TagSummary]
    tag_colors: list[str]
    suggested_tags: dict[str, SuggestedTagsResponse]
    reading_queue: list[ReadingQueueItem]
    my_publications_profile: ProfileResponse
    my_publications_dashboard: DashboardResponse
    my_publications_citing: dict[str, CitingResponse]
    method_summaries: DemoMethodSummaries
    summary_index: list[SummaryListItem]
    summaries: dict[str, SummarizeJobResponse]
    status: StatusResponse
    wip: DemoWipState
    synthesis: DemoSynthesisState
    extended: DemoExtendedState


class DemoManifest(StrictModel):
    snapshot_id: str
    snapshot_schema_version: int
    callosum_version: str
    compatible_frontend_version: str
    curated_on: str
    title: str
    question: str
    initial_workspace: Literal["library"] = "library"
    initial_paper_id: int
    initial_summary_id: int
    capabilities: DemoCapabilities
    workspace_capabilities: dict[str, DemoWorkspaceCapability]
    trust_boundary: str


class DemoSnapshot(StrictModel):
    manifest: DemoManifest
    api: DemoApi

    @model_validator(mode="after")
    def validate_contract(self) -> "DemoSnapshot":
        version = self.manifest.snapshot_schema_version
        if version not in SUPPORTED_SNAPSHOT_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported demo snapshot schema {version}; regenerate with the current exporter")
        initial = str(self.manifest.initial_summary_id)
        if initial not in self.api.summaries:
            raise ValueError("initial_summary_id is not present in api.summaries")
        initial_summary = self.api.summaries[initial]
        if not initial_summary.overview:
            raise ValueError("the saved demo synthesis must include its generated Overview")
        verified_ordinals = {sentence.ordinal for sentence in initial_summary.sentences or [] if not sentence.flagged}
        if any(not set(item.claim_ordinals) <= verified_ordinals for item in initial_summary.overview):
            raise ValueError("saved demo Overview must trace only to verified claims")
        paper_ids = [paper.list_item.id for paper in self.api.papers]
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("demo paper ids must be unique")
        if any(paper.detail.id != paper.list_item.id for paper in self.api.papers):
            raise ValueError("paper list/detail ids do not agree")
        if any(paper.document.paper_id != paper.list_item.id for paper in self.api.papers):
            raise ValueError("paper document ids do not agree")
        known_ids = set(paper_ids)
        if self.manifest.initial_paper_id not in known_ids:
            raise ValueError("initial_paper_id is not present in api.papers")
        queued_ids = [item.id for item in self.api.reading_queue]
        if set(queued_ids) != known_ids or len(queued_ids) != len(known_ids):
            raise ValueError("demo reading queue must contain every curated paper exactly once")
        if set(map(int, self.api.suggested_tags)) != known_ids:
            raise ValueError("demo suggested tags must cover every curated paper")
        axis_ids = {axis.id for axis in self.api.axes}
        if set(map(int, self.api.axis_clusters)) != axis_ids:
            raise ValueError("demo axis clusters must cover every saved axis")
        cluster_paper_ids = {
            paper.id for nodes in self.api.axis_clusters.values() for node in nodes for paper in node.papers
        }
        if not cluster_paper_ids <= known_ids:
            raise ValueError("demo axes reference a paper outside the curated library")
        my_pubs_axes = [axis for axis in self.api.axes if axis.kind == "my_publications"]
        if len(my_pubs_axes) != 1:
            raise ValueError("demo must contain exactly one My Publications axis")
        citing_work_ids = {
            item.openalex_work_id
            for item in self.api.my_publications_dashboard.paper_citations.values()
            if item.openalex_work_id
        }
        if set(self.api.my_publications_citing) != citing_work_ids:
            raise ValueError("demo cited-by snapshots must cover every displayed OpenAlex work id")
        if any(topic.increase <= 0 for topic in self.api.extended.discover.emerging_topics.topics):
            raise ValueError("demo emerging-topic snapshot must contain only increasing topics")
        for author in self.api.extended.discover.citing_authors.authors:
            distinct_titles = {
                re.sub(r"\W+", " ", str(work.title or "").casefold()).strip() for work in author.citing_works
            }
            if author.citing_work_count < 2 or author.cited_publication_count < 2 or len(distinct_titles) < 2:
                raise ValueError("demo citing-author rows must satisfy the visible repeated-connection qualification")
        status_summary_ids = {
            str(job.nav["summary_id"])
            for job in self.api.status.jobs
            if job.nav and job.nav.get("summary_id") is not None
        }
        if initial not in status_summary_ids:
            raise ValueError("status receipt does not navigate to initial_summary_id")
        required_surfaces = {
            "profile",
            "library",
            "library.wip",
            "synthesis.ask",
            "synthesis.critique",
            "synthesis.meta-preregistration",
            "discover.feed",
            "discover.search",
            "discover.journals",
            "discover.funding",
            "discover.followed-authors",
            "work.cite",
            "work.meta-reference",
            "work.credit",
            "work.statements",
            "work.meta-analyze",
            "help",
            "settings",
        }
        missing = required_surfaces - set(self.manifest.workspace_capabilities)
        if missing:
            raise ValueError(f"demo workspace capability map is incomplete: {', '.join(sorted(missing))}")
        if any(
            {reference.paper_id for reference in state.references} != known_ids for state in self.api.wip.by_id.values()
        ):
            raise ValueError("demo WIP references must resolve to the curated library")
        if set(map(int, self.api.synthesis.critical_reads)) != known_ids:
            raise ValueError("demo saved Critique state must cover every curated paper")
        extended_ids = set(map(int, self.api.extended.library.annotations))
        if extended_ids != known_ids:
            raise ValueError("demo extended state must cover every curated paper")
        cited_ids = {item.paper_id for item in self.api.extended.work.cite.suggestions}
        if set(map(int, self.api.extended.work.citation_renderings)) != cited_ids:
            raise ValueError("demo formatted citations must cover every saved Cite suggestion")
        if set(map(int, self.api.extended.work.citation_bibtex)) != cited_ids:
            raise ValueError("demo BibTeX must cover every saved Cite suggestion")
        return self


def assert_public_snapshot_bytes(payload: bytes) -> None:
    """Fail closed on forbidden names, secrets, or machine-specific paths in public JSON bytes."""

    text = payload.decode("utf-8")
    lowered = text.lower()
    for key in sorted(_FORBIDDEN_KEYS):
        if f'"{key}"' in lowered:
            raise ValueError(f"public demo snapshot contains forbidden field {key!r}")
    if _WINDOWS_PATH.search(text) or _POSIX_PRIVATE_PATH.search(text):
        raise ValueError("public demo snapshot contains a local filesystem path")
    if _OPENAI_KEY.search(text):
        raise ValueError("public demo snapshot contains credential-like marker 'sk-'")
    for marker in ("-----begin private key-----", "ghp_", "xoxb-", "bearer "):
        if marker in lowered:
            raise ValueError(f"public demo snapshot contains credential-like marker {marker!r}")
    raw = json.loads(text)
    _reject_unknown(raw, {"manifest", "api"}, "snapshot")
    _reject_unknown(raw["manifest"], set(DemoManifest.model_fields), "manifest")
    _reject_unknown(raw["manifest"]["capabilities"], set(DemoCapabilities.model_fields), "manifest.capabilities")
    for key, capability in raw["manifest"]["workspace_capabilities"].items():
        _reject_unknown(capability, set(DemoWorkspaceCapability.model_fields), f"manifest.workspace_capabilities.{key}")
    _reject_unknown(raw["api"], set(DemoApi.model_fields), "api")
    DemoWipState.model_validate(raw["api"]["wip"])
    _reject_synthesis_state(raw["api"]["synthesis"])
    # Override every nested live response model to fail closed too; several production response models retain
    # Pydantic's permissive default because ordinary API evolution may be additive.
    DemoExtendedState.model_validate(raw["api"]["extended"], extra="forbid")
    _reject_unknown(raw["api"]["health"], set(HealthResponse.model_fields), "api.health")
    _reject_unknown(raw["api"]["help_corpus"], set(HelpCorpusResponse.model_fields), "api.help_corpus")
    for index, section in enumerate(raw["api"]["help_corpus"]["sections"]):
        _reject_unknown(section, set(HelpSectionResponse.model_fields), f"api.help_corpus.sections[{index}]")
    _reject_unknown(
        raw["api"]["settings"],
        {"data_egress_enabled", "publisher_defaults_set", "publisher_weighting", "publisher_breadth"},
        "api.settings",
    )
    for index, axis in enumerate(raw["api"]["axes"]):
        _reject_unknown(axis, set(AxisResponse.model_fields), f"api.axes[{index}]")
    for axis_id, nodes in raw["api"]["axis_clusters"].items():
        for node_index, node in enumerate(nodes):
            prefix = f"api.axis_clusters[{axis_id}][{node_index}]"
            _reject_unknown(node, set(ClusterNodeResponse.model_fields), prefix)
            for paper_index, paper in enumerate(node.get("papers", [])):
                _reject_unknown(paper, set(ClusterPaperResponse.model_fields), f"{prefix}.papers[{paper_index}]")
    for index, tag in enumerate(raw["api"]["tags"]):
        _reject_unknown(tag, set(TagSummary.model_fields), f"api.tags[{index}]")
    for paper_id, suggestions in raw["api"]["suggested_tags"].items():
        _reject_unknown(suggestions, set(SuggestedTagsResponse.model_fields), f"api.suggested_tags[{paper_id}]")
    for index, item in enumerate(raw["api"]["reading_queue"]):
        _reject_unknown(item, set(ReadingQueueItem.model_fields), f"api.reading_queue[{index}]")
    _reject_unknown(
        raw["api"]["my_publications_profile"], set(ProfileResponse.model_fields), "api.my_publications_profile"
    )
    _reject_unknown(
        raw["api"]["my_publications_dashboard"], set(DashboardResponse.model_fields), "api.my_publications_dashboard"
    )
    for work_id, citing in raw["api"]["my_publications_citing"].items():
        prefix = f"api.my_publications_citing[{work_id}]"
        _reject_unknown(citing, set(CitingResponse.model_fields), prefix)
        for index, work in enumerate(citing.get("works", [])):
            _reject_unknown(work, set(CitingWorkResponse.model_fields), f"{prefix}.works[{index}]")
    for index, paper in enumerate(raw["api"]["papers"]):
        prefix = f"api.papers[{index}]"
        _reject_unknown(paper, set(DemoPaper.model_fields), prefix)
        _reject_unknown(paper["list_item"], set(PaperListItem.model_fields), prefix + ".list_item")
        _reject_unknown(paper["detail"], set(PaperDetailResponse.model_fields), prefix + ".detail")
        for attachment_index, attachment in enumerate(paper["detail"].get("attachments", [])):
            _reject_unknown(
                attachment,
                set(AttachmentResponse.model_fields),
                f"{prefix}.detail.attachments[{attachment_index}]",
            )
        _reject_unknown(paper["document"], set(DemoDocument.model_fields), prefix + ".document")
        _reject_unknown(paper["document"]["license"], set(DemoLicense.model_fields), prefix + ".document.license")
        methods = paper["methods"]
        _reject_unknown(methods, set(DemoMethodSnapshots.model_fields), prefix + ".methods")
        _reject_method_snapshot(methods, prefix + ".methods")
    method_summaries = raw["api"]["method_summaries"]
    _reject_unknown(method_summaries, set(DemoMethodSummaries.model_fields), "api.method_summaries")
    for key, model in (
        ("statcheck", StatcheckLibrarySummary),
        ("transparency", TransparencyLibrarySummary),
        ("lmm", LmmLibrarySummary),
        ("bayes", BayesLibrarySummary),
        ("meta_analysis", MetaLibrarySummary),
    ):
        _reject_unknown(method_summaries[key], set(model.model_fields), f"api.method_summaries.{key}")
    for index, item in enumerate(raw["api"]["summary_index"]):
        _reject_unknown(item, set(SummaryListItem.model_fields), f"api.summary_index[{index}]")
    for summary_id, summary in raw["api"]["summaries"].items():
        prefix = f"api.summaries[{summary_id}]"
        _reject_unknown(summary, set(SummarizeJobResponse.model_fields), prefix)
        for sentence_index, sentence in enumerate(summary.get("sentences", [])):
            sentence_prefix = f"{prefix}.sentences[{sentence_index}]"
            _reject_unknown(sentence, set(SummarySentenceResponse.model_fields), sentence_prefix)
            for citation_index, citation in enumerate(sentence.get("citations", [])):
                _reject_unknown(
                    citation,
                    set(SummaryCitationResponse.model_fields),
                    f"{sentence_prefix}.citations[{citation_index}]",
                )
    status = raw["api"]["status"]
    _reject_unknown(status, set(StatusResponse.model_fields), "api.status")
    for index, job in enumerate(status["jobs"]):
        prefix = f"api.status.jobs[{index}]"
        _reject_unknown(job, set(StatusJob.model_fields), prefix)
        if job.get("progress") is not None:
            _reject_unknown(job["progress"], set(StatusProgress.model_fields), prefix + ".progress")


def _reject_method_snapshot(methods: dict, prefix: str) -> None:
    statcheck = methods["statcheck"]
    _reject_unknown(statcheck, set(StatcheckCacheResponse.model_fields), prefix + ".statcheck")
    for index, result in enumerate(statcheck.get("results", [])):
        _reject_unknown(result, set(StatcheckResult.model_fields), f"{prefix}.statcheck.results[{index}]")
    if statcheck.get("coverage") is not None:
        _reject_unknown(statcheck["coverage"], set(StatcheckCoverage.model_fields), prefix + ".statcheck.coverage")
    bayes = methods["bayes"]
    _reject_unknown(bayes, set(BayesResponse.model_fields), prefix + ".bayes")
    for index, result in enumerate(bayes.get("results", [])):
        _reject_unknown(result, set(BayesResult.model_fields), f"{prefix}.bayes.results[{index}]")
    completeness = bayes["completeness"]
    _reject_unknown(completeness, set(BayesCompletenessOut.model_fields), prefix + ".bayes.completeness")
    for key, model in (("items", BayesCompletenessItem), ("advisories", BayesAdvisoryNote)):
        for index, item in enumerate(completeness.get(key, [])):
            _reject_unknown(item, set(model.model_fields), f"{prefix}.bayes.completeness.{key}[{index}]")
    for key, response_model, item_key, item_model in (
        ("lmm", LmmResponse, "checks", LmmCheckOut),
        ("meta_analysis", MetaResponse, "checks", MetaCheckOut),
        ("transparency", TransparencyResponse, "checks", TransparencyCheckOut),
    ):
        response = methods[key]
        _reject_unknown(response, set(response_model.model_fields), f"{prefix}.{key}")
        for index, item in enumerate(response.get(item_key, [])):
            _reject_unknown(item, set(item_model.model_fields), f"{prefix}.{key}.{item_key}[{index}]")
    for index, item in enumerate(methods["transparency"].get("registration_references", [])):
        _reject_unknown(
            item, set(RegistrationReferenceOut.model_fields), f"{prefix}.transparency.registration_references[{index}]"
        )


def _reject_synthesis_state(value: dict) -> None:
    prefix = "api.synthesis"
    _reject_unknown(value, set(DemoSynthesisState.model_fields), prefix)
    for paper_id, response in value["critical_reads"].items():
        response_prefix = f"{prefix}.critical_reads[{paper_id}]"
        _reject_unknown(response, set(CriticalReadJobResponse.model_fields), response_prefix)
        backbone = response.get("backbone")
        if backbone is not None:
            _reject_unknown(backbone, set(ScrutinyBackboneResponse.model_fields), response_prefix + ".backbone")
            for index, signal in enumerate(backbone.get("method_signals", [])):
                _reject_unknown(
                    signal,
                    set(MethodSignalResponse.model_fields),
                    f"{response_prefix}.backbone.method_signals[{index}]",
                )
    for paper_id, response in value["critical_candidates"].items():
        _reject_unknown(response, set(CandidateListResponse.model_fields), f"{prefix}.critical_candidates[{paper_id}]")
    for paper_id, links in value["registration_links"].items():
        for index, link in enumerate(links):
            _reject_unknown(
                link, set(RegistrationLinkOut.model_fields), f"{prefix}.registration_links[{paper_id}][{index}]"
            )
    for paper_id, versions in value["registration_versions"].items():
        for index, version in enumerate(versions):
            _reject_unknown(
                version,
                set(RegistrationVersionOut.model_fields),
                f"{prefix}.registration_versions[{paper_id}][{index}]",
            )
    for paper_id, runs in value["registration_comparison_runs"].items():
        for index, run in enumerate(runs):
            _reject_unknown(
                run,
                set(ComparisonRunSummary.model_fields),
                f"{prefix}.registration_comparison_runs[{paper_id}][{index}]",
            )
    for run_id, detail in value["registration_comparison_details"].items():
        detail_prefix = f"{prefix}.registration_comparison_details[{run_id}]"
        _reject_unknown(detail, set(ComparisonRunDetail.model_fields), detail_prefix)
        for index, row in enumerate(detail.get("rows", [])):
            _reject_unknown(row, set(ComparisonRowOut.model_fields), f"{detail_prefix}.rows[{index}]")


def _reject_unknown(value: object, allowed: set[str], location: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    unexpected = set(value) - allowed
    if unexpected:
        raise ValueError(f"{location} contains unrecognized fields: {', '.join(sorted(unexpected))}")
