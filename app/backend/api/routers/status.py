"""Cross-feature async-job status (inc 406) — the "Status" menu popover's backend.

~30 independent features each keep their own :class:`~app.backend.api.job_store.JobStore` on
``api.state`` (axis scoring, dedup scan, library scan/import, statcheck-all, meta-analysis
batches, Synthesize > Ask, ...) but there was no single place to ask "what's running right now,
across the whole app." This router answers that by **reflecting over ``api.state``** for every
``JobStore``-typed attribute rather than hand-maintaining a list — so a future feature that adds
its own ``JobStore`` shows up automatically, never silently missing from this view.

A job's row *label* comes from which store it lives in (``JOB_LABELS``, falling back to an
auto-prettified attribute name), not from data the job itself carries — this is deliberate: most
of the ~30 job kinds never call ``mark_progress`` and so have no per-job label, and fixing that at
every call site would be a much larger change than this feature needs. Jobs that DO report real
progress (library scan/import, citation-count refresh) still show it via the existing
``JobProgress``/``eta_seconds()`` machinery, verbatim.

Pure in-memory aggregation: no DB, no filesystem, no external calls. The only externally-supplied
value is the ``store`` path segment on the dismiss endpoint, checked against the same allowlist
used for labels — never used to resolve an arbitrary attribute off ``api.state``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.backend.api.job_store import Job, JobStore

router = APIRouter(tags=["status"])

# Auto-expiry backstop (on top of the user's own explicit dismiss) so a long session doesn't
# accumulate finished rows forever if nobody clears them.
_FINISHED_TTL_SECONDS = 60 * 60

# Friendly names for the job kinds most likely to be visible at once. Anything not listed here
# still appears (via _prettify), just with a plainer auto-generated label.
JOB_LABELS: dict[str, str] = {
    "summary_jobs": "Synthesize · Ask",
    "axis_score_jobs": "Axis scoring",
    "axis_suggest_jobs": "Axis suggest",
    "dedup_jobs": "Duplicate scan",
    "library_scan_jobs": "Library scan",
    "library_import_jobs": "Library import",
    "library_bundle_import_jobs": "Library bundle import",
    "statcheck_jobs": "statcheck (library-wide)",
    "pcurve_jobs": "p-curve",
    "retraction_jobs": "Retraction check",
    "retraction_db_jobs": "Retraction Watch DB download",
    "lmm_jobs": "LMM reporting-completeness",
    "meta_jobs": "Meta-analysis reporting-completeness",
    "bayes_jobs": "Bayesian auditor",
    "transparency_jobs": "Transparency signals",
    "registration_discovery_jobs": "Registration discovery",
    "registration_acquisition_jobs": "Registration acquisition",
    "registration_comparison_jobs": "Registration comparison",
    "citation_count_jobs": "Cited-by refresh",
    "citation_equity_jobs": "Citation-equity audit",
    "citation_context_jobs": "Citation context",
    "critical_review_jobs": "Critical Read",
    "critical_review_set_jobs": "Critical Read (set)",
    "metadata_enrich_jobs": "Metadata enrichment",
    "ocr_jobs": "OCR",
    "text_health_jobs": "Text-health reprocessing",
    "gap_jobs": "Gap-finder",
    "overlooked_jobs": "Overlooked-work remediation",
    "overlooked_lens_jobs": "Overlooked-work lens",
    "publishers_jobs": "Journal-finder",
    "reference_integrity_jobs": "Reference-integrity scan",
    "funding_jobs": "Funding discovery",
    "feed_jobs": "Feed refresh",
    "acquire_jobs": "Full-text acquisition",
    "wanted_jobs": "Wanted-list re-check",
    "mypubs_jobs": "My Publications refresh",
    "mypubs_domain_jobs": "My Publications (domain scope)",
    "my_publication_gap_jobs": "Co-citation gap scan",
    "my_publication_citing_author_jobs": "Citing-authors scan",
    "my_publication_topic_jobs": "Emerging-topics scan",
    "wip_scan_jobs": "WIP folder scan",
}


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


class StatusJob(BaseModel):
    store: str
    job_id: str
    label: str
    status: str
    detail: str | None = None
    progress: StatusProgress | None = None
    # inc 415: a narrow, opt-in navigation hint (e.g. {"summary_id": 42}) a job may publish at mark_done()
    # time — NOT job.result, which stays deliberately unread here (inc 406 audit). Most jobs never set it.
    nav: dict[str, Any] | None = None


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
    return StatusJob(
        store=store_name,
        job_id=job_id,
        label=label,
        status=job.status,
        detail=job.detail,
        progress=progress,
        nav=job.nav,
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
