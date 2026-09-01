"""Cross-feature async-job status (inc 406) — the "Status" menu popover's backend.

~30 independent features each keep their own :class:`~app.backend.api.job_store.JobStore` on
``api.state`` (axis scoring, dedup scan, library import, statcheck-all, meta-analysis
batches, Synthesize > Ask, ...) but there was no single place to ask "what's running right now,
across the whole app." This router answers that by **reflecting over ``api.state``** for every
``JobStore``-typed attribute rather than hand-maintaining the aggregation list. A structural test separately
requires every visible application store to declare a bounded UI destination, so new jobs cannot ship as dead rows.
Routine library and WIP folder scans are explicit noise exclusions; their own surfaces retain inline status.

A job's row *label* comes from which store it lives in (``JOB_LABELS``, falling back to an
auto-prettified attribute name), not from data the job itself carries — this is deliberate: most
of the ~30 job kinds never call ``mark_progress`` and so have no per-job label, and fixing that at
every call site would be a much larger change than this feature needs. Jobs that DO report real
progress (library import, citation-count refresh) still show it via the existing
``JobProgress``/``eta_seconds()`` machinery, verbatim.

Pure in-memory aggregation: no DB, no filesystem, no external calls. The only externally-supplied
value is the ``store`` path segment on the dismiss endpoint, checked against the discovered-store map — never used
to resolve an arbitrary attribute off ``api.state``. Per-job navigation is reduced to typed entity ids and merged
with server-owned destinations; URLs, free text, and destination overrides are discarded.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.backend.api.job_store import Job, JobStore

router = APIRouter(tags=["status"])

# Auto-expiry backstop (on top of the user's own explicit dismiss) so a long session doesn't
# accumulate finished rows forever if nobody clears them.
_FINISHED_TTL_SECONDS = 60 * 60

# High-frequency maintenance scans keep their own inline state but add little value to the global activity list.
# Keep them discoverable for cleanup/dismiss APIs while omitting both running rows and finished receipts from Status.
STATUS_HIDDEN_STORES = frozenset({"library_scan_jobs", "wip_scan_jobs"})

# Friendly names for the job kinds most likely to be visible at once. Anything not listed here
# still appears (via _prettify), just with a plainer auto-generated label.
JOB_LABELS: dict[str, str] = {
    "summary_jobs": "Synthesize · Ask",
    "overview_jobs": "Synthesize · Overview",
    "axis_score_jobs": "Axis scoring",
    "axis_suggest_jobs": "Axis suggest",
    "dedup_jobs": "Duplicate scan",
    "library_import_jobs": "Library import",
    "library_bundle_import_jobs": "Library bundle import",
    "share_import_jobs": "Shared-with-me import",
    "zotero_import_jobs": "Zotero library import",
    "statcheck_jobs": "statcheck (library-wide)",
    "pcurve_jobs": "p-curve",
    "zcurve_jobs": "z-curve",
    "retraction_jobs": "Retraction check",
    "retraction_db_jobs": "Retraction Watch DB download",
    "top_factor_db_jobs": "TOP Factor database download",
    "ajol_db_jobs": "AJOL database download",
    "lmm_jobs": "LMM reporting-completeness",
    "meta_jobs": "Meta-analysis reporting-completeness",
    "bayes_jobs": "Bayesian auditor",
    "transparency_jobs": "Transparency signals",
    "registration_discovery_jobs": "Registration discovery",
    "registration_acquisition_jobs": "Registration acquisition",
    "registration_comparison_jobs": "Registration comparison",
    "citation_count_jobs": "Cited-by refresh",
    "citation_equity_jobs": "Citation-equity audit",
    "wip_citation_equity_jobs": "WIP Citation-concentration audit",
    "citation_context_jobs": "Citation context",
    "critical_review_jobs": "Critical Read",
    "wip_critical_review_jobs": "WIP Critical Read",
    "critical_review_set_jobs": "Critical Read (set)",
    "metadata_enrich_jobs": "Metadata enrichment",
    "ocr_jobs": "OCR",
    "grobid_parse_jobs": "GROBID structure parsing",
    "grobid_lifecycle_jobs": "GROBID install (Docker)",
    "text_health_jobs": "Text-health reprocessing",
    "gap_jobs": "Gap-finder",
    "overlooked_jobs": "Overlooked-work remediation",
    "overlooked_lens_jobs": "Overlooked-work lens",
    "publishers_jobs": "Journal-finder",
    "reference_integrity_jobs": "Reference-integrity scan",
    "wip_reference_integrity_jobs": "WIP Reference-integrity scan",
    "funding_jobs": "Funding discovery",
    "feed_jobs": "Feed refresh",
    "acquire_jobs": "Full-text acquisition",
    "wanted_jobs": "Wanted-list re-check",
    "mypubs_jobs": "My Publications refresh",
    "mypubs_domain_jobs": "My Publications (domain scope)",
    "my_publication_gap_jobs": "Co-citation gap scan",
    "my_publication_citing_author_jobs": "Citing-authors scan",
    "my_publication_topic_jobs": "Emerging-topics scan",
}

# Every backend job family has a stable UI home. A job may add a narrower entity hint (paper_id, summary_id, ...)
# through Job.nav; these defaults make running rows clickable before a result exists and keep new callers from
# having to duplicate workspace knowledge. No arbitrary path/URL is accepted here.
JOB_NAV_DEFAULTS: dict[str, dict[str, Any]] = {
    "summary_jobs": {"workspace": "synthesis", "tab": "ask"},
    "overview_jobs": {"workspace": "synthesis", "tab": "ask"},
    "axis_score_jobs": {"pane": "theory", "section": "axes", "tab": "axes"},
    "axis_suggest_jobs": {"pane": "theory", "section": "axes", "tab": "axes", "modal": "suggest-axes"},
    "dedup_jobs": {"workspace": "library", "modal": "duplicates"},
    "library_import_jobs": {"workspace": "library", "modal": "import"},
    "library_bundle_import_jobs": {"workspace": "library", "modal": "bundle-import"},
    "share_import_jobs": {"workspace": "library", "modal": "shared-with-me"},
    "zotero_import_jobs": {"workspace": "library", "modal": "zotero-import"},
    "statcheck_jobs": {"pane": "methods", "section": "statcheck"},
    "pcurve_jobs": {"workspace": "library"},
    "zcurve_jobs": {"workspace": "library"},
    "retraction_jobs": {"pane": "methods", "section": "details"},
    "retraction_db_jobs": {"workspace": "settings"},
    "top_factor_db_jobs": {"workspace": "settings"},
    "ajol_db_jobs": {"workspace": "settings"},
    "lmm_jobs": {"pane": "methods", "section": "checklists", "tab": "lmm"},
    "meta_jobs": {"pane": "methods", "section": "checklists", "tab": "meta"},
    "bayes_jobs": {"pane": "methods", "section": "checklists", "tab": "bayes"},
    "transparency_jobs": {"pane": "methods", "section": "checklists", "tab": "transparency"},
    "registration_discovery_jobs": {"workspace": "synthesis", "tab": "meta-preregistration"},
    "registration_acquisition_jobs": {"workspace": "synthesis", "tab": "meta-preregistration"},
    "registration_comparison_jobs": {"workspace": "synthesis", "tab": "meta-preregistration"},
    "citation_count_jobs": {"workspace": "library", "view": "citations"},
    # Fixed inc 447: this used to point at {"pane": "methods", "section": "citation-equity"} -- no Methods-pane
    # section with that id exists (grepped every registerPaneSection call; the real set is
    # details/grim/statcheck/checklists), so clicking either of these Status rows silently landed on the Methods
    # pane's default "Details" section instead of Work -> Meta-Reference, where these tools actually render.
    "citation_equity_jobs": {"workspace": "work", "tab": "meta-reference"},
    "overlooked_jobs": {"workspace": "work", "tab": "meta-reference"},
    "citation_context_jobs": {"workspace": "work", "tab": "meta-reference"},
    "critical_review_jobs": {"workspace": "synthesis", "tab": "critique"},
    "wip_critical_review_jobs": {"workspace": "synthesis", "tab": "critique"},
    # The Critique tab renders a single paper's (or a WIP manuscript's) Critical Read only -- it has no concept
    # of a multi-paper "set" job. Reopen the modal that actually shows this job's progress/report instead of
    # landing on a tab with nothing relevant to display (found live: closing the modal mid-run stranded the
    # user with no way back to it).
    "critical_review_set_jobs": {"workspace": "synthesis", "modal": "critical-set"},
    "metadata_enrich_jobs": {"workspace": "library"},
    "ocr_jobs": {"pane": "methods", "section": "details"},
    # Task 11 (backlog #30 Stage 2) added the real per-paper "Parse document structure…" action right beside
    # ocr_jobs' own per-paper action in that same Details section (25a_detail_actions.jsx's GrobidParseRow) — so
    # this destination, once a placeholder, is now exactly where the action lives. paper_id (per-paper jobs
    # only; the bulk /grobid/library/parse job has none) is layered in automatically by _bounded_nav from Job.nav.
    "grobid_parse_jobs": {"pane": "methods", "section": "details"},
    "grobid_lifecycle_jobs": {"workspace": "settings"},
    "text_health_jobs": {"workspace": "library", "modal": "text-health"},
    "gap_jobs": {"workspace": "discover", "tab": "search", "modal": "gaps"},
    "overlooked_lens_jobs": {"workspace": "discover", "tab": "search", "modal": "overlooked"},
    "publishers_jobs": {"workspace": "discover", "tab": "journals"},
    "reference_integrity_jobs": {"workspace": "work", "tab": "meta-reference"},
    "wip_reference_integrity_jobs": {"workspace": "work", "tab": "meta-reference"},
    "wip_citation_equity_jobs": {"workspace": "work", "tab": "meta-reference"},
    "funding_jobs": {"workspace": "discover", "tab": "funding"},
    "feed_jobs": {"workspace": "discover", "tab": "feed"},
    "acquire_jobs": {"workspace": "library"},
    "wanted_jobs": {"workspace": "library", "modal": "wanted"},
    "mypubs_jobs": {"workspace": "profile"},
    "mypubs_domain_jobs": {"workspace": "profile"},
    "my_publication_gap_jobs": {"workspace": "profile"},
    "my_publication_citing_author_jobs": {"workspace": "profile"},
    "my_publication_topic_jobs": {"workspace": "profile"},
}

JOB_COMPUTE_KINDS: dict[str, str] = {
    "summary_jobs": "Provider AI + local verification",
    "overview_jobs": "Provider AI",
    "axis_score_jobs": "Local AI",
    "axis_suggest_jobs": "Local AI + optional provider AI",
    "dedup_jobs": "Local AI",
    "library_import_jobs": "Local AI",
    "library_bundle_import_jobs": "Local AI",
    "share_import_jobs": "Local AI",
    "zotero_import_jobs": "Local AI",
    "statcheck_jobs": "Local deterministic check",
    "pcurve_jobs": "Local deterministic check",
    "zcurve_jobs": "Local deterministic check",
    "retraction_jobs": "Public metadata",
    "retraction_db_jobs": "Public database download",
    "top_factor_db_jobs": "Public database download",
    "ajol_db_jobs": "Public database download",
    "lmm_jobs": "Local deterministic check",
    "meta_jobs": "Local deterministic check",
    "bayes_jobs": "Local deterministic check",
    "transparency_jobs": "Local deterministic check",
    "registration_discovery_jobs": "Public registry metadata",
    "registration_acquisition_jobs": "Public registry + local processing",
    "registration_comparison_jobs": "Local AI",
    "citation_count_jobs": "Public metadata",
    "citation_context_jobs": "Local AI + public metadata",
    "citation_equity_jobs": "Public metadata",
    "wip_citation_equity_jobs": "Public metadata",
    "critical_review_jobs": "Local AI",
    "wip_critical_review_jobs": "Local AI",
    "critical_review_set_jobs": "Provider AI + local verification",
    "metadata_enrich_jobs": "Public metadata",
    "ocr_jobs": "Local AI",
    "grobid_parse_jobs": "Local processing + self-hosted GROBID",
    "grobid_lifecycle_jobs": "Public container image + local execution",
    "text_health_jobs": "Local AI",
    "gap_jobs": "Public metadata + local analysis",
    "overlooked_jobs": "Local AI + public metadata",
    "overlooked_lens_jobs": "Local AI + public metadata",
    "publishers_jobs": "Local AI + public metadata",
    "reference_integrity_jobs": "Local AI + public metadata",
    "wip_reference_integrity_jobs": "Local AI + public metadata",
    "funding_jobs": "Public metadata + optional provider AI",
    "feed_jobs": "Public metadata",
    "acquire_jobs": "Public acquisition + local AI",
    "wanted_jobs": "Public acquisition + local AI",
    "mypubs_jobs": "Public metadata + local analysis",
    "mypubs_domain_jobs": "Local AI + public metadata",
    "my_publication_gap_jobs": "Public metadata + local analysis",
    "my_publication_citing_author_jobs": "Public metadata + local analysis",
    "my_publication_topic_jobs": "Public metadata + local analysis",
}

_NAV_ENTITY_IDS = {"paper_id", "summary_id", "manuscript_id"}


def _bounded_nav(store_name: str, job_nav: dict[str, Any] | None) -> dict[str, Any] | None:
    """Merge only typed entity ids into the server-owned destination descriptor.

    Job producers may identify the paper/summary they operate on, but they cannot publish URLs, free text, or
    override the destination vocabulary. This keeps Status navigation useful without turning ``Job.nav`` into a
    generic serialization channel.
    """
    nav = dict(JOB_NAV_DEFAULTS.get(store_name, {}))
    for key in _NAV_ENTITY_IDS:
        value = (job_nav or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            nav[key] = value
    paper_ids = (job_nav or {}).get("paper_ids")
    if isinstance(paper_ids, list):
        bounded = [
            value for value in paper_ids[:500] if isinstance(value, int) and not isinstance(value, bool) and value > 0
        ]
        if bounded:
            nav["paper_ids"] = bounded
    return nav or None


def _prettify(attr_name: str) -> str:
    base = attr_name[:-5] if attr_name.endswith("_jobs") else attr_name
    return base.replace("_", " ").strip().title()


def discover_stores(state: object) -> dict[str, JobStore]:
    """Every ``JobStore``-typed attribute currently on ``api.state``, keyed by attribute name.

    ``api.state`` is Starlette's ``State`` — it proxies ``state.foo = x`` into a private ``_state`` dict via
    `__setattr__`, so ``vars(state)`` only ever sees that one wrapper attribute, never the real entries. `State`
    is iterable/subscriptable over its real keys (`__iter__`/`__getitem__`), which is what this actually walks.
    """
    return {name: state[name] for name in state if isinstance(state[name], JobStore)}


class StatusProgress(BaseModel):
    current: int
    total: int
    label: str
    eta_seconds: int | None = None


class StatusStage(BaseModel):
    key: str
    label: str
    elapsed_seconds: float
    timing_key: str
    workload_size: int | None = None
    variable: bool = False


class StatusStageReceipt(BaseModel):
    key: str
    duration_seconds: float
    timing_key: str
    workload_size: int | None = None
    variable: bool = False


class StatusJob(BaseModel):
    store: str
    job_id: str
    label: str
    status: str
    detail: str | None = None
    progress: StatusProgress | None = None
    elapsed_seconds: float | None = None
    stage: StatusStage | None = None
    completed_stages: list[StatusStageReceipt] = Field(default_factory=list)
    # inc 415: a narrow, opt-in navigation hint (e.g. {"summary_id": 42}) a job may publish at mark_done()
    # time — NOT job.result, which stays deliberately unread here (inc 406 audit). Most jobs never set it.
    nav: dict[str, Any] | None = None
    compute_kind: str | None = None


class StatusResponse(BaseModel):
    jobs: list[StatusJob]


_STATUS_RANK = {"running": 0, "pending": 1, "error": 2, "done": 3}


def _to_status_job(store_name: str, job_id: str, job: Job) -> StatusJob:
    progress = None
    if job.progress is not None:
        eta = job.eta_seconds() if job.status == "running" else None
        progress = StatusProgress(
            current=job.progress.current, total=job.progress.total, label=job.progress.label, eta_seconds=eta
        )
    label = JOB_LABELS.get(store_name, _prettify(store_name))
    stage = None
    if job.stage is not None:
        stage = StatusStage(
            key=job.stage.key,
            label=job.stage.label,
            elapsed_seconds=max(0.0, time.monotonic() - job.stage.started_at),
            timing_key=job.stage.timing_key,
            workload_size=job.stage.workload_size,
            variable=job.stage.variable,
        )
    return StatusJob(
        store=store_name,
        job_id=job_id,
        label=label,
        status=job.status,
        detail=job.detail,
        progress=progress,
        elapsed_seconds=job.elapsed_seconds(),
        stage=stage,
        completed_stages=[
            StatusStageReceipt(
                key=item.key,
                duration_seconds=item.duration_seconds,
                timing_key=item.timing_key,
                workload_size=item.workload_size,
                variable=item.variable,
            )
            for item in job.completed_stages
        ],
        nav=_bounded_nav(store_name, job.nav),
        compute_kind=JOB_COMPUTE_KINDS.get(store_name),
    )


def _sort_key(sj: StatusJob, jobs_by_id: dict[str, Job]) -> tuple:
    job = jobs_by_id[sj.job_id]
    recency = -(job.finished_at or job.started_at or 0)
    return (_STATUS_RANK.get(sj.status, 9), recency)


@router.get("/status/jobs", response_model=StatusResponse)
def list_status_jobs(request: Request) -> StatusResponse:
    stores = discover_stores(request.app.state)
    out: list[StatusJob] = []
    jobs_by_id: dict[str, Job] = {}
    for store_name, store in stores.items():
        store.prune_finished_older_than(_FINISHED_TTL_SECONDS)
        if store_name in STATUS_HIDDEN_STORES:
            continue
        for job_id, job in store.list_all():
            if job.status == "pending" and job.started_at is None and job.finished_at is None:
                # Freshly created, not yet picked up by the background task — not worth a row yet.
                continue
            jobs_by_id[job_id] = job
            out.append(_to_status_job(store_name, job_id, job))
    out.sort(key=lambda sj: _sort_key(sj, jobs_by_id))
    return StatusResponse(jobs=out)


@router.post("/status/jobs/{store}/{job_id}/dismiss")
def dismiss_status_job(store: str, job_id: str, request: Request) -> dict:
    stores = discover_stores(request.app.state)
    target = stores.get(store)
    if target is None:
        raise HTTPException(status_code=404, detail="Unknown job store")
    if not target.dismiss(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True}


@router.post("/status/jobs/clear-finished")
def clear_finished_status_jobs(request: Request) -> dict:
    stores = discover_stores(request.app.state)
    cleared = 0
    for store in stores.values():
        for job_id, job in store.list_all():
            if job.status in ("done", "error") and store.dismiss(job_id):
                cleared += 1
    return {"ok": True, "cleared": cleared}
