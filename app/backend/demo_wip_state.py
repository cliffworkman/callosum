"""Strict, presentation-independent contract for the public demo's saved WIP workspace."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.backend.api.routers.wip_reference_integrity import WipReferenceReportModel

DEMO_WIP_STATE_SCHEMA_VERSION = 1


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoWipManuscript(_StrictModel):
    id: int
    root_path: str
    derived_title: str
    title_override: str | None = None
    display_title: str
    state: Literal["active", "paused", "archived", "missing"]
    manuscript_type: str
    stage: str
    target_journal: str | None = None
    deadline: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str
    last_filesystem_activity_at: str | None = None
    missing_since: str | None = None
    file_count: int
    missing_file_count: int
    open_task_count: int
    unresolved_finding_count: int
    stale_check_count: int
    missing_primary_file: bool


class DemoWipFile(_StrictModel):
    id: int
    manuscript_id: int
    relative_path: str
    role: str
    is_primary: bool
    existence_state: str
    file_size: int | None = None
    modified_at: str | None = None
    whole_file_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    extracted_text_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    extracted_from_whole_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    extraction_status: str
    extraction_error: str | None = None
    extraction_provider: str | None = None
    extraction_version: str | None = None
    last_scanned_at: str | None = None


class DemoWipActivity(_StrictModel):
    id: int
    manuscript_id: int
    event_type: str
    summary: str
    metadata_json: dict[str, Any] | None = None
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    created_at: str


class DemoWipSection(_StrictModel):
    id: int
    manuscript_id: int
    name: str
    position: int
    status: str
    notes: str | None = None
    content_detected: bool
    is_custom: bool
    created_at: str
    updated_at: str


class DemoWipTask(_StrictModel):
    id: int
    manuscript_id: int
    title: str
    description: str | None = None
    status: str
    due_date: str | None = None
    section_id: int | None = None
    file_id: int | None = None
    paper_id: int | None = None
    finding_id: int | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None


class DemoWipReference(_StrictModel):
    id: int
    manuscript_id: int
    paper_id: int
    relationship_state: str
    notes: str | None = None
    created_at: str
    updated_at: str
    paper_title: str
    paper_year: int | None = None


class DemoWipSnapshot(_StrictModel):
    id: int
    manuscript_id: int
    file_id: int
    whole_file_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    extracted_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_hashes_json: dict[str, str] | None = None
    evidence_context_json: list[str] | dict[str, Any]
    extracted_char_count: int
    extraction_provider: str
    extraction_version: str
    reason: str
    reason_detail: str
    created_at: str
    identity_status: str
    status_detail: str


class DemoWipTool(_StrictModel):
    id: str
    label: str
    kind: str


class DemoWipFinding(_StrictModel):
    id: int
    tool_run_id: int
    manuscript_id: int
    file_id: int
    section_id: int | None = None
    reference_id: int | None = None
    kind: str
    finding_type: str
    severity: str
    summary: str
    details_json: dict[str, Any]
    quote: str | None = None
    context: str | None = None
    coordinate_precision: str | None = None
    disposition: str | None = None
    resolution_notes: str | None = None
    created_at: str
    updated_at: str


class DemoWipToolRun(_StrictModel):
    id: int
    tool_id: str
    tool_version: str
    callosum_version: str
    parameters_json: dict[str, Any]
    result_summary: str
    structured_result_json: dict[str, Any]
    coverage: str
    status: str
    error_detail: str | None = None
    executed_at: str
    manuscript_id: int
    file_id: int
    snapshot_id: int
    validity: str
    unresolved_findings: int
    findings: list[DemoWipFinding]


class DemoWipChecks(_StrictModel):
    tools: list[DemoWipTool]
    runs: list[DemoWipToolRun]


class DemoWipManuscriptState(_StrictModel):
    manuscript: DemoWipManuscript
    files: list[DemoWipFile]
    activity: list[DemoWipActivity]
    sections: list[DemoWipSection]
    tasks: list[DemoWipTask]
    references: list[DemoWipReference]
    snapshots: list[DemoWipSnapshot]
    checks: DemoWipChecks
    funding_runs: list[dict[str, Any]] = Field(default_factory=list)
    journal_runs: list[dict[str, Any]] = Field(default_factory=list)
    reference_integrity: WipReferenceReportModel


class DemoWipState(_StrictModel):
    schema_version: int = DEMO_WIP_STATE_SCHEMA_VERSION
    generated_with: dict[str, str]
    manuscripts: list[DemoWipManuscript]
    by_id: dict[str, DemoWipManuscriptState]

    @model_validator(mode="after")
    def validate_contract(self) -> "DemoWipState":
        if self.schema_version != DEMO_WIP_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported demo WIP state schema; regenerate it")
        ids = [item.id for item in self.manuscripts]
        if len(ids) != 2 or len(set(ids)) != 2:
            raise ValueError("demo WIP state must contain exactly two synthetic manuscripts")
        if set(self.by_id) != set(map(str, ids)):
            raise ValueError("demo WIP index/detail ids do not agree")
        for manuscript_id, state in self.by_id.items():
            if state.manuscript.id != int(manuscript_id) or not state.checks.runs:
                raise ValueError("each demo WIP must have matching detail and saved checks")
            if {reference.paper_id for reference in state.references} != {42, 67, 88}:
                raise ValueError("each demo WIP must link all three curated papers")
        return self
