"""Axis endpoint request/response models + their field-cap constants.

Split out of ``routers/axes.py`` (inc 264) to keep it under the 600-line cap (rule #1). A **leaf** module: it
imports only pydantic + stdlib and nothing from ``axes.py``, so ``axes.py`` imports these back with no cycle
(the inc-137/inc-207 pattern). ``DEFAULT_AXIS_CUTOFF`` lives here as the schema default for ``scoring_gain``;
the scoring logic in ``axes.py`` imports it back.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

AXIS_LABEL_MAX = 200
AXIS_DESCRIPTION_MAX = 4000
DEFAULT_AXIS_CUTOFF = 0.35  # assigned-similarity cutoff default (axes.scoring_gain NULL -> this)


class AxisCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=AXIS_LABEL_MAX)
    description: str | None = Field(default=None, max_length=AXIS_DESCRIPTION_MAX)
    kind: str = "standard"  # A7 (inc 211): "standard" (keyword/scored) or "curated" (hand-populated). Allowlisted.


class AxisUpdateRequest(BaseModel):
    # Partial update; omitted fields are unchanged. Editing the description changes the axis text,
    # so the axis becomes stale until re-scored (surfaced via the response's `stale`).
    label: str | None = Field(default=None, min_length=1, max_length=AXIS_LABEL_MAX)
    description: str | None = Field(default=None, max_length=AXIS_DESCRIPTION_MAX)
    kind: str | None = None  # A7 (inc 211): switch keyword<->curated (freeze / warned revert). Allowlisted.


class ManualAssignmentRequest(BaseModel):
    paper_id: int


class SuggestTermsRequest(BaseModel):
    label: str = Field(min_length=1, max_length=AXIS_LABEL_MAX)
    description: str | None = Field(default=None, max_length=AXIS_DESCRIPTION_MAX)


class SuggestTermsResponse(BaseModel):
    terms: list[str]


class MergeAxesRequest(BaseModel):
    # Consolidate several axes into one surviving axis. `keep_axis_id` survives (the frontend
    # comparison view composes its label/description from all sources); `merge_axis_ids` are folded
    # in (their manual assignments unioned into the survivor) and then deleted. Re-score afterwards.
    keep_axis_id: int
    merge_axis_ids: list[int] = Field(min_length=1)
    label: str = Field(min_length=1, max_length=AXIS_LABEL_MAX)
    description: str | None = Field(default=None, max_length=AXIS_DESCRIPTION_MAX)


class AxisResponse(BaseModel):
    id: int
    label: str
    description: str | None = None
    scored: bool = False  # has score_axis run for this axis (an axis embedding exists)?
    stale: bool = False  # has the text changed since the last score (assignments outdated)?
    assignment_count: int = 0  # papers currently assigned (scored + manual)
    created_at: datetime | None = None  # for client-side sort-by-recency
    scoring_gain: float = DEFAULT_AXIS_CUTOFF  # effective assigned-cutoff (axes.scoring_gain or default)
    kind: str = "standard"  # "standard" or "my_publications" (inc 78 — drives the pinned card + variant UI)
    uncertain_count: int = 0  # scored-but-below-cutoff papers (inc 79 — for the hide-uncertain count badge)


class ClusterPaperResponse(BaseModel):
    id: int
    title: str
    confidence: float | None = None  # cosine-similarity confidence; NULL for a manual override
    status: str = "uncertain"  # "assigned" / "uncertain" / "manual" (honest tier, not truth)
    manual: bool = False  # True when the human added this, not the scorer
    starred: bool = False  # inc 84: My Publications only — a starred key publication
    domain: str | None = None  # inc 118 (SP2 #16): My Publications only — the paper's research-domain label
    position: int | None = None  # A7 (inc 211): manual order on a curated axis (NULL on keyword axes)


class ClusterNodeResponse(BaseModel):
    id: int
    axis_id: int | None = None
    parent_id: int | None = None
    label: str
    description: str | None = None
    confidence: float | None = None
    papers: list[ClusterPaperResponse]


class AxisScoreStartRequest(BaseModel):
    # Optional per-re-score cutoff ("gain"); omitted → reuse the axis's saved gain, else the default.
    gain: float | None = Field(default=None, ge=0.0, le=1.0)


class AxisScoreStartResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]


class AxisScoreJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    axis_id: int | None = None
    cluster_node_id: int | None = None
    assigned_count: int | None = None
    uncertain_count: int | None = None


# ── suggest-optimal-axes (inc 52): an async clustering job, mirroring the score job ──
class SuggestedAxisResponse(BaseModel):
    label: str
    terms: list[str]
    paper_ids: list[int]
    paper_titles: list[str]
    size: int
    # "keywords" = this label came from the local c-TF-IDF pass; "ai" = a provider polished it. Without this a
    # polished label and an unpolished one are byte-identical on the wire (inc 568).
    label_source: Literal["ai", "keywords"] = "keywords"


class AxisSuggestJobResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    suggestions: list[SuggestedAxisResponse] | None = None
    # Set when some/all labels were NOT polished, naming the cause. The job still succeeds — keyword labels are
    # a usable result — but the user is told, rather than left to read the fallback as a model regression.
    label_notice: str | None = None
