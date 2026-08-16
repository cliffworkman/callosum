"""Validated intermediate fixture for the demo's saved library organization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from app.backend.api.routers.axes_models import AxisResponse, ClusterNodeResponse
from app.backend.api.routers.my_publications import CitingResponse, DashboardResponse, ProfileResponse
from app.backend.api.routers.paper_models import PaperTagRef
from app.backend.api.routers.reading_queue import ReadingQueueItem
from app.backend.api.routers.tags import SuggestedTagsResponse, TagSummary

LIBRARY_STATE_SCHEMA_VERSION = 2


class DemoLibraryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_schema_version: int = LIBRARY_STATE_SCHEMA_VERSION
    generated_with: dict[str, str]
    axes: list[AxisResponse]
    axis_clusters: dict[str, list[ClusterNodeResponse]]
    tags: list[TagSummary]
    paper_tags: dict[str, list[PaperTagRef]]
    tag_colors: list[str]
    suggested_tags: dict[str, SuggestedTagsResponse]
    reading_queue: list[ReadingQueueItem]
    my_publications_profile: ProfileResponse
    my_publications_dashboard: DashboardResponse
    my_publications_citing: dict[str, CitingResponse] = {}

    @model_validator(mode="after")
    def validate_state(self) -> "DemoLibraryState":
        if self.state_schema_version != LIBRARY_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported demo library state; regenerate with the current generator")
        axis_ids = {axis.id for axis in self.axes}
        if set(map(int, self.axis_clusters)) != axis_ids:
            raise ValueError("saved cluster map does not match the saved axes")
        return self
