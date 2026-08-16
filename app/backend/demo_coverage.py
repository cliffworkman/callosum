"""Auditable catalogue of result-bearing public-demo surfaces."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEMO_COVERAGE_SCHEMA_VERSION = 1


class DemoCoverageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    workspace: str
    label: str
    status: Literal["saved", "ephemeral-local", "visible-disabled", "scientifically-inapplicable"]
    data_source: str
    visitor_note: str


class DemoCoverageCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = DEMO_COVERAGE_SCHEMA_VERSION
    snapshot_schema_version: int
    items: list[DemoCoverageItem]

    @model_validator(mode="after")
    def validate_catalogue(self) -> "DemoCoverageCatalogue":
        if self.schema_version != DEMO_COVERAGE_SCHEMA_VERSION:
            raise ValueError("unsupported demo coverage catalogue; regenerate it")
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("demo coverage item ids must be unique")
        required = {
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
        missing = required - set(ids)
        if missing:
            raise ValueError(f"demo coverage catalogue is missing registered surfaces: {', '.join(sorted(missing))}")
        return self
