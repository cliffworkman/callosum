"""Generate genuine saved WIP state from a fresh, public-only Callosum sandbox."""

# ruff: noqa: E402 -- direct execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import insert

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api import create_app
from app.backend.api.routers.wip_reference_integrity import WipReferenceReportModel
from app.backend.demo_wip_state import (
    DEMO_WIP_STATE_SCHEMA_VERSION,
    DemoWipActivity,
    DemoWipChecks,
    DemoWipFile,
    DemoWipFinding,
    DemoWipManuscript,
    DemoWipManuscriptState,
    DemoWipReference,
    DemoWipSection,
    DemoWipSnapshot,
    DemoWipState,
    DemoWipTask,
    DemoWipTool,
    DemoWipToolRun,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from tools.demo.curated_library import CORPUS, CURATED_ON

ModelT = TypeVar("ModelT", bound=BaseModel)
FIXTURE_DIR = ROOT / "tools" / "demo" / "fixtures"
TOOLS = ("statcheck", "transparency", "lmm", "bayes", "meta-analysis")
FIXED_TIME = "2026-08-11T12:00:00"

MANUSCRIPTS = {
    "Integrated review": {
        "source": "integrated-review.md",
        "title": "Anomalous-is-bad bias: an integrated evidence review",
        "stage": "analysis",
        "manuscript_type": "systematic review and meta-analysis",
        "target_journal": "Psychological Bulletin",
        "deadline": "2026-10-15",
        "notes": "Synthetic public-demo draft. All detector results are genuine Callosum outputs; the study is not real.",
    },
    "Synthetic replication": {
        "source": "synthetic-replication.md",
        "title": "Facial difference impressions: synthetic replication report",
        "stage": "writing",
        "manuscript_type": "empirical article",
        "target_journal": "British Journal of Psychology",
        "deadline": "2026-09-30",
        "notes": "Synthetic public-demo draft linked to the complete three-paper sandbox library.",
    },
}


def _pick(model: type[ModelT], value: dict[str, Any], **overrides: Any) -> ModelT:
    selected = {key: value[key] for key in model.model_fields if key in value}
    selected.update(overrides)
    return model.model_validate(selected)


def _must(response, label: str) -> Any:
    if response.status_code >= 400:
        raise ValueError(f"{label} failed ({response.status_code}): {response.text}")
    return response.json() if response.content else None


def _poll(client: TestClient, job_id: str) -> None:
    for _ in range(50):
        result = _must(client.get(f"/wip/scan/{job_id}"), "WIP scan poll")
        if result["status"] == "done":
            return
        if result["status"] == "error":
            raise ValueError(f"WIP scan failed: {result.get('detail')}")
    raise ValueError("WIP scan did not complete")


def _seed_papers(db_url: str) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        for paper_id, item in CORPUS.items():
            conn.execute(
                insert(papers).values(
                    id=paper_id,
                    title=item["title"],
                    year=item["year"],
                    publication_date=item["publication_date"],
                    doi=item["doi"],
                    venue=item["venue"],
                    item_type="article-journal",
                    language="en",
                    first_author_family_name=item["csl_authors"][0]["family"],
                    imported_source="curated-public-demo",
                    csl_json={
                        "id": f"demo-{paper_id}",
                        "type": "article-journal",
                        "title": item["title"],
                        "author": item["csl_authors"],
                        "issued": {"date-parts": [[int(part) for part in item["publication_date"].split("-")]]},
                        "DOI": item["doi"],
                        "URL": item["canonical_url"],
                        "container-title": item["venue"],
                        "volume": item["volume"],
                        "issue": item["issue"],
                        "page": item["page"],
                        "ISSN": item["issn"],
                    },
                )
            )
    engine.dispose()


def _configure_manuscript(client: TestClient, manuscript: dict[str, Any], definition: dict[str, str]) -> None:
    manuscript_id = int(manuscript["id"])
    _must(
        client.patch(
            f"/wip/manuscripts/{manuscript_id}",
            json={
                "title_override": definition["title"],
                "stage": definition["stage"],
                "manuscript_type": definition["manuscript_type"],
                "target_journal": definition["target_journal"],
                "deadline": definition["deadline"],
                "notes": definition["notes"],
            },
        ),
        "manuscript update",
    )
    files = _must(client.get(f"/wip/manuscripts/{manuscript_id}/files"), "WIP files")
    primary = next(item for item in files if item["relative_path"] == definition["source"])
    _must(
        client.patch(f"/wip/manuscripts/{manuscript_id}/files/{primary['id']}", json={"is_primary": True}),
        "primary manuscript selection",
    )
    sections = _must(client.get(f"/wip/manuscripts/{manuscript_id}/sections"), "WIP sections")
    complete = {"Title page", "Introduction", "Method", "References", "Open practices statement"}
    for section in sections:
        status = "complete" if section["name"] in complete else "outlined"
        if section["name"] == "Results":
            status = "needs-revision"
        elif section["name"] == "Discussion":
            status = "drafting"
        _must(
            client.patch(
                f"/wip/manuscripts/{manuscript_id}/sections/{section['id']}",
                json={"status": status, "notes": "Saved synthetic-demo planning state."},
            ),
            "section update",
        )
    section_ids = {item["name"]: item["id"] for item in sections}
    tasks = (
        ("Resolve the intentionally surfaced detector candidates", "in-progress", "Results"),
        ("Connect every interpretive claim to quoted evidence", "open", "Discussion"),
        ("Verify the three corrected bibliography records", "complete", "References"),
    )
    for title, status, section_name in tasks:
        _must(
            client.post(
                f"/wip/manuscripts/{manuscript_id}/tasks",
                json={
                    "title": title,
                    "description": "Public synthetic-demo task generated through the real WIP workflow API.",
                    "status": status,
                    "section_id": section_ids[section_name],
                },
            ),
            "task creation",
        )
    for paper_id in sorted(CORPUS):
        _must(
            client.post(
                f"/wip/manuscripts/{manuscript_id}/references",
                json={
                    "paper_id": paper_id,
                    "relationship_state": "cited",
                    "notes": "Linked from the curated three-paper public demo library.",
                },
            ),
            "reference link",
        )
    _must(client.post(f"/wip/manuscripts/{manuscript_id}/snapshots", json={}), "manual checkpoint")
    for tool in TOOLS:
        _must(client.post(f"/wip/manuscripts/{manuscript_id}/checks/{tool}", json={}), f"{tool} run")


def _normalized_state(client: TestClient) -> DemoWipState:
    list_items = _must(client.get("/wip/manuscripts?state=active&sort=title"), "WIP manuscript list")
    manuscripts: list[DemoWipManuscript] = []
    by_id: dict[str, DemoWipManuscriptState] = {}
    for item in list_items:
        manuscript_id = int(item["id"])
        safe_root = f"Demo workspace / {item['derived_title']}"
        manuscript = _pick(
            DemoWipManuscript,
            item,
            root_path=safe_root,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
            last_filesystem_activity_at=FIXED_TIME,
        )
        manuscripts.append(manuscript)
        raw_files = _must(client.get(f"/wip/manuscripts/{manuscript_id}/files"), "WIP files export")
        files = [
            _pick(
                DemoWipFile,
                value,
                modified_at=FIXED_TIME,
                last_scanned_at=FIXED_TIME,
            )
            for value in raw_files
        ]
        raw_activity = _must(client.get(f"/wip/manuscripts/{manuscript_id}/activity"), "WIP activity export")
        activity = [_pick(DemoWipActivity, value, created_at=FIXED_TIME) for value in raw_activity]
        raw_sections = _must(client.get(f"/wip/manuscripts/{manuscript_id}/sections"), "WIP section export")
        sections = [
            _pick(DemoWipSection, value, created_at=FIXED_TIME, updated_at=FIXED_TIME) for value in raw_sections
        ]
        raw_tasks = _must(client.get(f"/wip/manuscripts/{manuscript_id}/tasks"), "WIP task export")
        tasks = [
            _pick(
                DemoWipTask,
                value,
                created_at=FIXED_TIME,
                updated_at=FIXED_TIME,
                completed_at=FIXED_TIME if value.get("completed_at") else None,
            )
            for value in raw_tasks
        ]
        raw_references = _must(client.get(f"/wip/manuscripts/{manuscript_id}/references"), "WIP refs export")
        references = [
            _pick(DemoWipReference, value, created_at=FIXED_TIME, updated_at=FIXED_TIME) for value in raw_references
        ]
        raw_snapshots = _must(client.get(f"/wip/manuscripts/{manuscript_id}/snapshots"), "WIP snapshots export")
        snapshots = [_pick(DemoWipSnapshot, value, created_at=FIXED_TIME) for value in raw_snapshots]
        raw_checks = _must(client.get(f"/wip/manuscripts/{manuscript_id}/checks"), "WIP checks export")
        runs = []
        for raw_run in raw_checks["runs"]:
            findings = [
                _pick(DemoWipFinding, finding, created_at=FIXED_TIME, updated_at=FIXED_TIME)
                for finding in raw_run["findings"]
            ]
            runs.append(_pick(DemoWipToolRun, raw_run, executed_at=FIXED_TIME, findings=findings))
        checks = DemoWipChecks(
            tools=[_pick(DemoWipTool, tool) for tool in raw_checks["tools"]],
            runs=runs,
        )
        reference_payload = _must(
            client.get(f"/wip/manuscripts/{manuscript_id}/reference-integrity"),
            "WIP reference-integrity export",
        )
        if reference_payload.get("last_checked_at"):
            reference_payload["last_checked_at"] = FIXED_TIME
        reference_integrity = WipReferenceReportModel.model_validate(reference_payload)
        by_id[str(manuscript_id)] = DemoWipManuscriptState(
            manuscript=manuscript,
            files=files,
            activity=activity,
            sections=sections,
            tasks=tasks,
            references=references,
            snapshots=snapshots,
            checks=checks,
            funding_runs=[],
            journal_runs=[],
            reference_integrity=reference_integrity,
        )
    return DemoWipState(
        schema_version=DEMO_WIP_STATE_SCHEMA_VERSION,
        generated_with={
            "source": "fresh dedicated public-demo database",
            "workflow": "Callosum WIP scan and workflow APIs",
            "checks": "Callosum deterministic WIP endpoints",
            "curated_on": CURATED_ON,
        },
        manuscripts=manuscripts,
        by_id=by_id,
    )


def generate_wip_state(output: Path) -> DemoWipState:
    with tempfile.TemporaryDirectory(prefix="callosum-public-demo-") as temporary:
        workspace = Path(temporary)
        sandbox = workspace / "sandbox"
        sandbox.mkdir()
        for folder_name, definition in MANUSCRIPTS.items():
            folder = sandbox / folder_name
            folder.mkdir()
            shutil.copyfile(FIXTURE_DIR / definition["source"], folder / definition["source"])
        db_url = f"sqlite:///{(workspace / 'demo.sqlite').as_posix()}"
        config = Config(str(ROOT / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(config, "head")
        _seed_papers(db_url)
        isolated_env = {
            "CALLOSUM_LIBRARY_DIR": str(workspace / "empty-library"),
            "CALLOSUM_SETTINGS_PATH": str(workspace / "settings.json"),
        }
        with patch.dict(os.environ, isolated_env, clear=False), TestClient(create_app(db_url=db_url)) as client:
            root = _must(
                client.post("/wip/watch-roots", json={"path": str(sandbox), "discovery_mode": "children"}),
                "WIP root creation",
            )
            scan = _must(client.post(f"/wip/watch-roots/{root['id']}/scan", json={}), "WIP scan")
            _poll(client, scan["job_id"])
            discovered = _must(client.get("/wip/manuscripts?state=active&sort=title"), "WIP discovery")
            if {item["derived_title"] for item in discovered} != set(MANUSCRIPTS):
                raise ValueError("sandbox WIP discovery did not find exactly the two curated manuscript folders")
            for manuscript in discovered:
                _configure_manuscript(client, manuscript, MANUSCRIPTS[manuscript["derived_title"]])
            state = _normalized_state(client)
    payload = (json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()
    for forbidden in (str(workspace), str(sandbox), "C:\\Users\\", "/home/", '"uid"', '"path_key"'):
        if forbidden and forbidden.encode() in payload:
            raise ValueError(f"generated WIP state contains forbidden public value {forbidden!r}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "demo" / "wip-state-v1.json")
    args = parser.parse_args()
    state = generate_wip_state(args.output)
    print(f"validated public WIP state: {args.output} ({len(state.manuscripts)} synthetic manuscripts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
