"""Independent, research-only verification harness for H1b.1.

All outputs go beneath ignored ``.local/h1b1-hardening-audit``. The harness never
calls a model/provider and never opens the user's production database for writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import sys
import time
from collections import Counter
from dataclasses import replace as dataclass_replace
from pathlib import Path
from typing import Any

from sqlalchemy import delete, event, func, select

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local" / "h1b1-hardening-audit"

sys.path.insert(0, str(ROOT))

from app.backend.pdf_processing.extraction import extract_pdf, file_sha256  # noqa: E402
from app.backend.pdf_processing.source_components import build_page  # noqa: E402
from app.backend.persistence import source_components_repo as component_repo  # noqa: E402
from app.backend.persistence.database import make_engine  # noqa: E402
from app.backend.persistence.repository import create_attachment, create_paper  # noqa: E402
from app.backend.persistence.schema import attachments, metadata  # noqa: E402
from app.backend.persistence.schema_source_components import (  # noqa: E402
    source_components,
    source_pages,
    source_representations,
)
from app.backend.persistence.source_components_repo import (  # noqa: E402
    attachments_with_current_source,
    locator_for_component,
    record_source_failure,
    replace_attachment_source,
    resolve_locator,
)
from tools.backfill_source_components import backfill  # noqa: E402

SEED = 20260905
TOLERANCE = 2.0


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(name: str, payload: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


def _connect(path: Path, *, write: bool = False) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(path)
    else:
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def artifact_hashes() -> dict[str, Any]:
    paths = [
        "alembic/versions/0081_source_representations.py",
        "app/backend/persistence/schema.py",
        "app/backend/persistence/schema_source_components.py",
        "app/backend/persistence/source_components_repo.py",
        "app/backend/persistence/source_representation_repo.py",
        "app/backend/pdf_processing/source_components.py",
        "app/backend/pdf_processing/ingest.py",
        "tools/backfill_source_components.py",
        ".claude/docs/specs/2026-09-05-evidence-unit-contract.md",
        ".claude/research/h1b_source_component_audit.py",
        ".claude/research/codex_h1b1_hardening_audit.py",
    ]
    return {path: _sha(ROOT / path) for path in paths}


def _span(text: str, bbox: tuple[float, float, float, float]) -> dict[str, Any]:
    return {"text": text, "bbox": bbox, "font": "Times", "size": 10.0, "flags": 0}


def _page(number: int, blocks: int = 2, *, width: float = 612.0, height: float = 792.0):
    raw_blocks = []
    for index in range(blocks):
        y = 72.0 + 20.0 * index
        bbox = (72.0, y, 400.0, y + 12.0)
        raw_blocks.append(
            {
                "type": 0,
                "number": index,
                "bbox": bbox,
                "lines": [
                    {"bbox": bbox, "dir": (1.0, 0.0), "wmode": 0, "spans": [_span(f"Evidence {number}-{index}.", bbox)]}
                ],
            }
        )
    return build_page({"blocks": raw_blocks}, page_number=number, width=width, height=height)


def _new_engine(path: Path, *, pdf: Path | None = None, checksum: str = "live-sha"):
    if path.exists():
        path.unlink()
    engine = make_engine(f"sqlite:///{path.resolve().as_posix()}")
    metadata.create_all(engine)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="opaque-h1b1-fixture", csl_json={"title": "opaque"})
        if pdf is not None:
            checksum = file_sha256(pdf)
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf) if pdf else "opaque.pdf",
            resolved_path=str(pdf.resolve()) if pdf else "opaque.pdf",
            checksum=checksum,
            file_size=pdf.stat().st_size if pdf else 100,
            content_type="application/pdf",
            import_source="research-fixture",
            attachment_type="pdf",
            role="article-fulltext",
        )
    return engine, attachment_id, checksum


def _store(engine, attachment_id: int, pages: list[Any], checksum: str = "live-sha"):
    with engine.begin() as conn:
        return replace_attachment_source(
            conn,
            attachment_id=attachment_id,
            pages=pages,
            coordinate_system="pdf-points-top-left",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            source_checksum=checksum,
        )


def _current(engine, attachment_id: int) -> bool:
    with engine.begin() as conn:
        return attachment_id in attachments_with_current_source(conn)


def _logical_tree(engine, attachment_id: int) -> str:
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                source_pages.c.page_number,
                source_pages.c.width,
                source_pages.c.height,
                source_pages.c.rotation,
                source_pages.c.coordinate_system,
                source_components.c.component_path,
                source_components.c.kind,
                source_components.c.native_order,
                source_components.c.sorted_order,
                source_components.c.child_order,
                source_components.c.x0,
                source_components.c.y0,
                source_components.c.x1,
                source_components.c.y1,
                source_components.c.text,
                source_components.c.font,
                source_components.c.font_size,
                source_components.c.flags,
                source_components.c.dir_x,
                source_components.c.dir_y,
                source_components.c.wmode,
            )
            .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
            .where(source_pages.c.attachment_id == attachment_id)
            .order_by(source_pages.c.page_number, source_components.c.component_path)
        ).all()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def _fresh_complete(case: str):
    engine, attachment_id, checksum = _new_engine(OUT / f"case-{case}.sqlite")
    receipt = _store(engine, attachment_id, [_page(1), _page(2)], checksum)
    assert receipt.state == "complete" and _current(engine, attachment_id)
    return engine, attachment_id, checksum


def adversarial() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    currentness: dict[str, bool] = {}
    repaired_state: dict[str, bool] = {}

    mutations = {
        "state_truncated": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(state="truncated")
        ),
        "state_incomplete": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(state="incomplete")
        ),
        "state_failed": lambda c, aid: c.execute(
            source_representations.update().where(source_representations.c.attachment_id == aid).values(state="failed")
        ),
        "checksum_mismatch": lambda c, aid: c.execute(
            attachments.update().where(attachments.c.id == aid).values(checksum="different-sha")
        ),
        "derivation_mismatch": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(derivation_version="source-components-v999")
        ),
        "representation_extraction_tool_mismatch": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(extraction_tool="different")
        ),
        "representation_extraction_version_mismatch": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(extraction_version="different")
        ),
        "page_checksum_mismatch": lambda c, aid: c.execute(
            source_pages.update().where(source_pages.c.attachment_id == aid).values(source_checksum="different-sha")
        ),
        "page_derivation_mismatch": lambda c, aid: c.execute(
            source_pages.update()
            .where(source_pages.c.attachment_id == aid)
            .values(derivation_version="source-components-v999")
        ),
        "page_extraction_tool_mismatch": lambda c, aid: c.execute(
            source_pages.update().where(source_pages.c.attachment_id == aid).values(extraction_tool="different")
        ),
        "page_extraction_version_mismatch": lambda c, aid: c.execute(
            source_pages.update().where(source_pages.c.attachment_id == aid).values(extraction_version="different")
        ),
        "written_pages_mismatch": lambda c, aid: c.execute(
            source_representations.update().where(source_representations.c.attachment_id == aid).values(written_pages=1)
        ),
        "written_components_mismatch": lambda c, aid: c.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(written_components=999)
        ),
        "skipped_pages_positive": lambda c, aid: c.execute(
            source_representations.update().where(source_representations.c.attachment_id == aid).values(skipped_pages=1)
        ),
        "missing_component": lambda c, aid: c.execute(
            delete(source_components).where(
                source_components.c.id == c.execute(select(func.max(source_components.c.id))).scalar_one()
            )
        ),
        "missing_page": lambda c, aid: c.execute(
            delete(source_pages).where(source_pages.c.id == c.execute(select(func.max(source_pages.c.id))).scalar_one())
        ),
    }
    for name, mutate in mutations.items():
        engine, aid, _ = _fresh_complete(name)
        with engine.begin() as conn:
            mutate(conn, aid)
        currentness[name] = _current(engine, aid)
        if name in {"state_truncated", "state_incomplete", "state_failed"}:
            _store(engine, aid, [_page(1), _page(2)])
            repaired_state[name] = _current(engine, aid)
        engine.dispose()

    engine, aid, _ = _fresh_complete("absent")
    with engine.begin() as conn:
        conn.execute(delete(source_representations).where(source_representations.c.attachment_id == aid))
    currentness["absent"] = _current(engine, aid)
    engine.dispose()

    # Original and last-page cap variants; then ordinary repair through the real backfill function.
    pdf = (ROOT / "tests" / "fixtures" / "seed.pdf").resolve()
    engine, aid, checksum = _new_engine(OUT / "case-truncation-repair.sqlite", pdf=pdf)
    extraction = extract_pdf(pdf)
    old_cap = component_repo.MAX_COMPONENTS_PER_ATTACHMENT
    component_repo.MAX_COMPONENTS_PER_ATTACHMENT = 0
    try:
        truncated = _store(engine, aid, list(extraction.source_pages), checksum)
    finally:
        component_repo.MAX_COMPONENTS_PER_ATTACHMENT = old_cap
    truncation_current = _current(engine, aid)
    repaired_stats = backfill(engine, attachment_id=aid)
    repaired_current = _current(engine, aid)

    engine2, aid2, checksum2 = _new_engine(OUT / "case-last-page-truncation.sqlite")
    pages = [_page(1, 1), _page(2, 1)]
    component_repo.MAX_COMPONENTS_PER_ATTACHMENT = 3
    try:
        last_page = _store(engine2, aid2, pages, checksum2)
    finally:
        component_repo.MAX_COMPONENTS_PER_ATTACHMENT = old_cap
    last_page_current = _current(engine2, aid2)
    _store(engine2, aid2, pages, checksum2)
    last_page_repaired = _current(engine2, aid2)

    interruption: dict[str, Any] = {}

    def run_interruption(name: str, mode: str) -> None:
        engine3, aid3, checksum3 = _new_engine(OUT / f"case-interrupt-{name}.sqlite")
        original_clear = component_repo.clear_representation
        original_flatten = component_repo._flatten
        original_replace = component_repo._replace_representation
        calls = {"n": 0}

        def fail_clear(*args, **kwargs):
            raise RuntimeError("before-write")

        def fail_flatten(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("after-partial")
            return original_flatten(*args, **kwargs)

        def fail_marker(*args, **kwargs):
            raise RuntimeError("before-marker")

        listener = None
        if mode == "before":
            component_repo.clear_representation = fail_clear
        elif mode == "partial":
            component_repo._flatten = fail_flatten
        elif mode == "marker":
            component_repo._replace_representation = fail_marker
        elif mode == "sql":

            def listener(_conn, _cursor, statement, _parameters, _context, _executemany):
                if statement.lstrip().upper().startswith("INSERT INTO SOURCE_COMPONENTS"):
                    raise RuntimeError("component-insert")

            event.listen(engine3, "before_cursor_execute", listener)
        raised = False
        try:
            _store(engine3, aid3, [_page(1), _page(2)], checksum3)
        except RuntimeError:
            raised = True
        finally:
            component_repo.clear_representation = original_clear
            component_repo._flatten = original_flatten
            component_repo._replace_representation = original_replace
            if listener is not None:
                event.remove(engine3, "before_cursor_execute", listener)
        before_repair_current = _current(engine3, aid3)
        _store(engine3, aid3, [_page(1), _page(2)], checksum3)
        interruption[name] = {
            "raised": raised,
            "current_before_repair": before_repair_current,
            "current_after_repair": _current(engine3, aid3),
            "tree_after_repair": _logical_tree(engine3, aid3),
        }
        engine3.dispose()

    for name, mode in (
        ("before_any_page", "before"),
        ("after_partial_graph", "partial"),
        ("before_complete_marker", "marker"),
        ("persistence_exception", "sql"),
    ):
        run_interruption(name, mode)

    control_engine, control_aid, control_checksum = _new_engine(OUT / "case-interrupt-control.sqlite")
    _store(control_engine, control_aid, [_page(1), _page(2)], control_checksum)
    control_tree = _logical_tree(control_engine, control_aid)
    for item in interruption.values():
        item["matches_control"] = item["tree_after_repair"] == control_tree

    # A failed rebuild inside a savepoint must restore the previous current representation.
    rollback_engine, rollback_aid, rollback_checksum = _new_engine(OUT / "case-rollback.sqlite")
    _store(rollback_engine, rollback_aid, [_page(1), _page(2)], rollback_checksum)
    rollback_tree = _logical_tree(rollback_engine, rollback_aid)
    original_flatten = component_repo._flatten

    def explode(*_args, **_kwargs):
        raise RuntimeError("forced-rebuild-failure")

    with rollback_engine.begin() as conn:
        try:
            with conn.begin_nested():
                component_repo._flatten = explode
                replace_attachment_source(
                    conn,
                    attachment_id=rollback_aid,
                    pages=[_page(1), _page(2)],
                    coordinate_system="pdf-points-top-left",
                    extraction_tool="pymupdf",
                    extraction_version="1.27.2",
                    source_checksum=rollback_checksum,
                )
        except RuntimeError:
            pass
        finally:
            component_repo._flatten = original_flatten
        failure_recorded = record_source_failure(
            conn,
            attachment_id=rollback_aid,
            source_checksum=rollback_checksum,
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            reason="persistence_error:RuntimeError",
        )
    rollback = {
        "current": _current(rollback_engine, rollback_aid),
        "tree_unchanged": _logical_tree(rollback_engine, rollback_aid) == rollback_tree,
        "failure_marker_written": failure_recorded,
    }

    # Raw geometry preservation and committed classifier behavior.
    geometry_cases = {
        "valid": (1.0, 2.0, 3.0, 4.0),
        "inverted_x": (3.0, 2.0, 1.0, 4.0),
        "inverted_y": (1.0, 4.0, 3.0, 2.0),
        "out_of_page": (-2.0001, 2.0, 3.0, 4.0),
        "at_tolerance": (-2.0, 2.0, 3.0, 4.0),
        "zero_width": (2.0, 2.0, 2.0, 4.0),
        "zero_height": (2.0, 2.0, 4.0, 2.0),
        "missing": None,
        "partial": (1.0, None, 3.0, 4.0),
        "nan": (1.0, 2.0, float("nan"), 4.0),
        "infinite": (1.0, 2.0, float("inf"), 4.0),
    }
    geometry: dict[str, Any] = {}
    from app.backend.pdf_processing.source_components import classify_geometry

    for name, bbox in geometry_cases.items():
        try:
            state, reason = classify_geometry(bbox, page_width=100.0, page_height=100.0)
            geometry[name] = {"state": state, "reason": reason, "input_repr": repr(bbox)}
        except Exception as exc:  # preserve unexpected fail-closed/open behavior as evidence
            geometry[name] = {"exception": type(exc).__name__, "input_repr": repr(bbox)}

    # Exercise geometry through persistence too: SQLite may represent non-finite values differently
    # from an in-memory Python tuple, which is itself part of the fail-closed question.
    persisted_geometry: dict[str, Any] = {}
    for name in ("nan", "infinite", "zero_width", "zero_height", "partial"):
        bbox = geometry_cases[name]
        raw = {
            "type": 0,
            "number": 0,
            "bbox": bbox,
            "lines": [
                {
                    "bbox": bbox,
                    "dir": (1.0, 0.0),
                    "wmode": 0,
                    "spans": [{"text": "x", "bbox": bbox, "font": "Times", "size": 10.0, "flags": 0}],
                }
            ],
        }
        persist_engine, persist_aid, persist_checksum = _new_engine(OUT / f"case-geometry-{name}.sqlite")
        error = None
        try:
            receipt = _store(
                persist_engine,
                persist_aid,
                [build_page({"blocks": [raw]}, page_number=1, width=100.0, height=100.0)],
                persist_checksum,
            )
            with persist_engine.begin() as conn:
                rows = (
                    conn.execute(
                        select(
                            source_components.c.kind,
                            source_components.c.x0,
                            source_components.c.y0,
                            source_components.c.x1,
                            source_components.c.y1,
                            source_components.c.geometry_state,
                        )
                        .join(source_pages, source_pages.c.id == source_components.c.source_page_id)
                        .where(source_pages.c.attachment_id == persist_aid)
                        .order_by(source_components.c.id)
                    )
                    .mappings()
                    .all()
                )
            persisted_geometry[name] = {"receipt_state": receipt.state, "rows": [dict(row) for row in rows]}
        except Exception as exc:
            error = type(exc).__name__
            persisted_geometry[name] = {"exception": error}
        persist_engine.dispose()

    # Independent destructive-rebuild checks: logical identity must survive an unchanged rebuild,
    # while a reused surrogate can silently name changed content in a controlled changed-tree case.
    rebuild_engine, rebuild_aid, rebuild_checksum = _new_engine(OUT / "case-rebuild.sqlite")
    with rebuild_engine.begin() as conn:
        paper2 = create_paper(conn, title="opaque-neighbour", csl_json={"title": "opaque"})
        neighbour = create_attachment(
            conn,
            paper_id=paper2,
            storage_mode="linked",
            availability="available",
            original_path="opaque2.pdf",
            resolved_path="opaque2.pdf",
            checksum="neighbour-sha",
            file_size=100,
            content_type="application/pdf",
            import_source="research-fixture",
            attachment_type="pdf",
            role="article-fulltext",
        )
    original_pages = [_page(1), _page(2)]
    _store(rebuild_engine, rebuild_aid, original_pages, rebuild_checksum)
    _store(rebuild_engine, neighbour, [_page(1)], "neighbour-sha")
    with rebuild_engine.begin() as conn:
        before_rows = conn.execute(
            select(source_components.c.id, source_components.c.text, source_components.c.component_path)
            .join(source_pages, source_pages.c.id == source_components.c.source_page_id)
            .where(source_pages.c.attachment_id == rebuild_aid)
            .order_by(source_components.c.id)
        ).all()
        locator = locator_for_component(conn, int(before_rows[-1].id))
    before_tree = _logical_tree(rebuild_engine, rebuild_aid)
    _store(rebuild_engine, rebuild_aid, original_pages, rebuild_checksum)
    with rebuild_engine.begin() as conn:
        after_rows = conn.execute(
            select(source_components.c.id, source_components.c.text, source_components.c.component_path)
            .join(source_pages, source_pages.c.id == source_components.c.source_page_id)
            .where(source_pages.c.attachment_id == rebuild_aid)
            .order_by(source_components.c.id)
        ).all()
        resolved_after = resolve_locator(conn, rebuild_aid, locator) if locator else None
        if locator:
            stale_extraction_resolves = (
                resolve_locator(conn, rebuild_aid, dataclass_replace(locator, extraction_version="stale-version"))
                is not None
            )
            stale_derivation_resolves = (
                resolve_locator(conn, rebuild_aid, dataclass_replace(locator, derivation_version="stale-derivation"))
                is not None
            )
            conn.execute(attachments.update().where(attachments.c.id == rebuild_aid).values(checksum="stale-sha"))
            stale_resolves = resolve_locator(conn, rebuild_aid, locator) is not None
        else:
            stale_extraction_resolves = None
            stale_derivation_resolves = None
    unchanged_rebuild = {
        "all_surrogate_ids_changed": [row.id for row in before_rows] != [row.id for row in after_rows]
        and not ({row.id for row in before_rows} & {row.id for row in after_rows}),
        "logical_tree_unchanged": before_tree == _logical_tree(rebuild_engine, rebuild_aid),
        "locator_resolved_after_rebuild": resolved_after is not None,
        "locator_content_path_after": resolved_after.get("component_path") if resolved_after else None,
        "stale_checksum_resolved": stale_resolves,
        "stale_extraction_resolved": stale_extraction_resolves,
        "stale_derivation_resolved": stale_derivation_resolves,
    }

    reuse_engine, reuse_aid, reuse_checksum = _new_engine(OUT / "case-surrogate-reuse.sqlite")
    _store(reuse_engine, reuse_aid, [_page(1, 2)], reuse_checksum)
    with reuse_engine.begin() as conn:
        old_rows = conn.execute(
            select(
                source_components.c.id,
                source_components.c.kind,
                source_components.c.text,
                source_components.c.component_path,
            )
            .join(source_pages, source_pages.c.id == source_components.c.source_page_id)
            .where(source_pages.c.attachment_id == reuse_aid)
            .order_by(source_components.c.id)
        ).all()
    changed = build_page(
        {
            "blocks": [
                {
                    "type": 0,
                    "number": 0,
                    "bbox": (10.0, 10.0, 50.0, 20.0),
                    "lines": [
                        {
                            "bbox": (10.0, 10.0, 50.0, 20.0),
                            "dir": (1.0, 0.0),
                            "wmode": 0,
                            "spans": [_span("different content", (10.0, 10.0, 50.0, 20.0))],
                        }
                    ],
                }
            ]
        },
        page_number=1,
        width=612.0,
        height=792.0,
    )
    _store(reuse_engine, reuse_aid, [changed], reuse_checksum)
    with reuse_engine.begin() as conn:
        new_rows = conn.execute(
            select(
                source_components.c.id,
                source_components.c.kind,
                source_components.c.text,
                source_components.c.component_path,
            )
            .join(source_pages, source_pages.c.id == source_components.c.source_page_id)
            .where(source_pages.c.attachment_id == reuse_aid)
            .order_by(source_components.c.id)
        ).all()
    old_by_id = {row.id: (row.kind, row.text, row.component_path) for row in old_rows}
    new_by_id = {row.id: (row.kind, row.text, row.component_path) for row in new_rows}
    reused_different = [
        row_id for row_id in sorted(old_by_id.keys() & new_by_id.keys()) if old_by_id[row_id] != new_by_id[row_id]
    ]
    surrogate_reuse = {
        "old_rows": len(old_rows),
        "new_rows": len(new_rows),
        "reused_ids_with_different_payload": len(reused_different),
        "bounded_reused_ids": reused_different[:10],
    }

    result = {
        "schema": "codex-h1b1-adversarial-v1",
        "currentness_after_single_mutation": currentness,
        "ordinary_repair_after_state": repaired_state,
        "truncation": {
            "state": truncated.state,
            "written_pages": truncated.written_pages,
            "expected_pages": truncated.expected_pages,
            "current_before_repair": truncation_current,
            "repair_stats": repaired_stats,
            "current_after_repair": repaired_current,
            "last_page_state": last_page.state,
            "last_page_written_pages": last_page.written_pages,
            "last_page_expected_pages": last_page.expected_pages,
            "last_page_current_before_repair": last_page_current,
            "last_page_current_after_repair": last_page_repaired,
        },
        "interruption": interruption,
        "rollback": rollback,
        "geometry_cases": geometry,
        "persisted_geometry_cases": persisted_geometry,
        "unchanged_rebuild": unchanged_rebuild,
        "surrogate_reuse": surrogate_reuse,
    }
    _write("adversarial.json", result)
    return result


def _independent_geometry(row: sqlite3.Row) -> tuple[str, str, bool]:
    bbox = (row["x0"], row["y0"], row["x1"], row["y1"])
    degenerate = False
    if any(value is None for value in bbox):
        return "unknown", "missing", degenerate
    values = [float(value) for value in bbox]
    if not all(math.isfinite(value) for value in values + [float(row["width"]), float(row["height"])]):
        return "invalid", "non_finite", degenerate
    x0, y0, x1, y1 = values
    if x1 < x0 or y1 < y0:
        return "invalid", "inverted", degenerate
    degenerate = x1 == x0 or y1 == y0
    if (
        x0 < -TOLERANCE
        or y0 < -TOLERANCE
        or x1 > float(row["width"]) + TOLERANCE
        or y1 > float(row["height"]) + TOLERANCE
    ):
        return "invalid", "out_of_page", degenerate
    return "valid", "degenerate" if degenerate else "ordinary", degenerate


def _payload(row: sqlite3.Row, parent_path: str | None) -> str:
    value = {
        "page_number": row["page_number"],
        "page_width": row["width"],
        "page_height": row["height"],
        "page_rotation": row["rotation"],
        "coordinate_system": row["coordinate_system"],
        "component_path": row["component_path"],
        "parent_component_path": parent_path,
        "kind": row["kind"],
        "native_order": row["native_order"],
        "sorted_order": row["sorted_order"],
        "child_order": row["child_order"],
        "text": row["text"],
        "bbox": [row["x0"], row["y0"], row["x1"], row["y1"]],
        "font": row["font"],
        "font_size": row["font_size"],
        "flags": row["flags"],
        "dir_x": row["dir_x"],
        "dir_y": row["dir_y"],
        "wmode": row["wmode"],
    }
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True)


def corpus(db: Path) -> dict[str, Any]:
    sql = """
        SELECT sp.attachment_id,sp.id source_page_id,sp.page_number,sp.width,sp.height,sp.rotation,
               sp.coordinate_system,sp.extraction_tool,sp.extraction_version,sp.derivation_version,
               sp.source_checksum,sc.id,sc.parent_id,sc.kind,sc.native_order,sc.sorted_order,
               sc.child_order,sc.x0,sc.y0,sc.x1,sc.y1,sc.text,sc.font,sc.font_size,sc.flags,
               sc.dir_x,sc.dir_y,sc.wmode,sc.component_path,sc.geometry_state
        FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
        JOIN attachments a ON a.id=sp.attachment_id JOIN papers p ON p.id=a.paper_id
        WHERE p.deleted_at IS NULL
        ORDER BY sp.attachment_id,sp.page_number,sc.id
    """
    compared = path_matches = geometry_matches = 0
    path_mismatches: list[dict[str, Any]] = []
    geometry_mismatches: list[dict[str, Any]] = []
    duplicate_paths = 0
    persisted_states: Counter[str] = Counter()
    independent_states: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    degenerates: Counter[str] = Counter()
    current_page: tuple[int, int] | None = None
    derived_by_id: dict[int, str | None] = {}
    stored_by_id: dict[int, str | None] = {}
    seen_paths: set[str] = set()
    with _connect(db) as conn:
        for row in conn.execute(sql):
            page_key = (int(row["attachment_id"]), int(row["page_number"]))
            if page_key != current_page:
                current_page = page_key
                derived_by_id = {}
                stored_by_id = {}
                seen_paths = set()
            if row["parent_id"] is None:
                expected = f"b{row['sorted_order']}" if row["sorted_order"] is not None else None
            else:
                parent = derived_by_id.get(int(row["parent_id"]))
                if parent is None:
                    expected = None
                elif row["kind"] == "line":
                    expected = f"{parent}/l{row['child_order']}"
                elif row["kind"] == "span":
                    expected = f"{parent}/s{row['child_order']}"
                else:
                    expected = None
            compared += 1
            if expected == row["component_path"]:
                path_matches += 1
            elif len(path_mismatches) < 25:
                path_mismatches.append(
                    {
                        "attachment_id": row["attachment_id"],
                        "page": row["page_number"],
                        "kind": row["kind"],
                        "stored": row["component_path"],
                        "expected": expected,
                    }
                )
            if expected in seen_paths:
                duplicate_paths += 1
            if expected is not None:
                seen_paths.add(expected)
            derived_by_id[int(row["id"])] = expected
            stored_by_id[int(row["id"])] = row["component_path"]

            independent, reason, degenerate = _independent_geometry(row)
            persisted_states[str(row["geometry_state"])] += 1
            independent_states[independent] += 1
            reasons[reason] += 1
            if degenerate:
                degenerates[str(row["kind"])] += 1
            if independent == row["geometry_state"]:
                geometry_matches += 1
            elif len(geometry_mismatches) < 25:
                geometry_mismatches.append(
                    {
                        "attachment_id": row["attachment_id"],
                        "page": row["page_number"],
                        "kind": row["kind"],
                        "stored": row["geometry_state"],
                        "expected": independent,
                        "reason": reason,
                    }
                )

        state_counts = dict(conn.execute("SELECT state,count(*) FROM source_representations GROUP BY state").fetchall())
        live = conn.execute(
            "SELECT count(*) FROM attachments a JOIN papers p ON p.id=a.paper_id WHERE a.content_type='application/pdf' AND p.deleted_at IS NULL"
        ).fetchone()[0]
        trashed = conn.execute(
            "SELECT count(*) FROM attachments a JOIN papers p ON p.id=a.paper_id WHERE a.content_type='application/pdf' AND p.deleted_at IS NOT NULL"
        ).fetchone()[0]
        current_rows = conn.execute("""
            SELECT count(*) FROM source_representations sr JOIN attachments a ON a.id=sr.attachment_id
            JOIN papers p ON p.id=a.paper_id WHERE p.deleted_at IS NULL AND sr.state='complete'
        """).fetchone()[0]

        dup_checksums = [
            row[0]
            for row in conn.execute("""
            SELECT a.checksum FROM attachments a JOIN papers p ON p.id=a.paper_id
            WHERE p.deleted_at IS NULL AND a.content_type='application/pdf' AND a.checksum IS NOT NULL
            GROUP BY a.checksum HAVING count(*) > 1
        """)
        ]
        duplicate_sources = []
        same_key_same_payload = 0
        same_key_different_payload = 0
        for checksum in dup_checksums:
            attachment_ids = [
                int(row[0])
                for row in conn.execute(
                    """
                SELECT a.id FROM attachments a JOIN papers p ON p.id=a.paper_id
                WHERE p.deleted_at IS NULL AND a.content_type='application/pdf' AND a.checksum=? ORDER BY a.id
            """,
                    (checksum,),
                )
            ]
            placeholders = ",".join("?" for _ in attachment_ids)
            rows = conn.execute(
                f"""
                SELECT sp.attachment_id,sp.page_number,sp.width,sp.height,sp.rotation,sp.coordinate_system,
                       sp.extraction_tool,sp.extraction_version,sp.derivation_version,sp.source_checksum,
                       sc.id,sc.parent_id,sc.kind,sc.native_order,sc.sorted_order,sc.child_order,
                       sc.x0,sc.y0,sc.x1,sc.y1,sc.text,sc.font,sc.font_size,sc.flags,sc.dir_x,sc.dir_y,
                       sc.wmode,sc.component_path
                FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
                WHERE sp.attachment_id IN ({placeholders}) ORDER BY sp.attachment_id,sp.page_number,sc.id
            """,
                attachment_ids,
            )
            keys: dict[tuple[Any, ...], tuple[str, set[int]]] = {}
            parent_paths: dict[tuple[int, int], str | None] = {}
            component_rows = 0
            for row in rows:
                component_rows += 1
                parent_path = (
                    parent_paths.get((int(row["attachment_id"]), int(row["parent_id"])))
                    if row["parent_id"] is not None
                    else None
                )
                parent_paths[(int(row["attachment_id"]), int(row["id"]))] = row["component_path"]
                key = (
                    row["source_checksum"],
                    row["extraction_tool"],
                    row["extraction_version"],
                    row["derivation_version"],
                    row["page_number"],
                    row["component_path"],
                )
                payload_hash = hashlib.sha256(_payload(row, parent_path).encode("utf-8")).hexdigest()
                if key in keys:
                    prior_hash, aids = keys[key]
                    if prior_hash == payload_hash:
                        same_key_same_payload += 1
                    else:
                        same_key_different_payload += 1
                    aids.add(int(row["attachment_id"]))
                else:
                    keys[key] = (payload_hash, {int(row["attachment_id"])})
            duplicate_sources.append(
                {
                    "checksum_prefix": checksum[:12],
                    "attachment_count": len(attachment_ids),
                    "component_rows": component_rows,
                }
            )

    # Measure the actual SQLAlchemy currentness query, which includes persisted count subqueries.
    engine = make_engine(f"sqlite:///{db.resolve().as_posix()}")
    with engine.begin() as conn:
        attachments_with_current_source(conn)
        timings = []
        result_size = 0
        for _ in range(10):
            start = time.perf_counter()
            result_size = len(attachments_with_current_source(conn))
            timings.append((time.perf_counter() - start) * 1000)
    engine.dispose()

    result = {
        "schema": "codex-h1b1-corpus-audit-v1",
        "database_sha256": _sha(db),
        "live_pdf_attachments": live,
        "trashed_pdf_attachments": trashed,
        "representation_states_all": state_counts,
        "complete_live_representation_rows": current_rows,
        "component_paths": {
            "compared": compared,
            "exact_matches": path_matches,
            "mismatches": compared - path_matches,
            "duplicate_expected_paths": duplicate_paths,
            "bounded_examples": path_mismatches,
        },
        "geometry": {
            "compared": compared,
            "exact_agreement": geometry_matches,
            "disagreements": compared - geometry_matches,
            "persisted_states": dict(persisted_states),
            "independent_states": dict(independent_states),
            "independent_reasons": dict(reasons),
            "degenerate_by_kind": dict(degenerates),
            "bounded_examples": geometry_mismatches,
        },
        "duplicate_source_identity": {
            "groups": len(duplicate_sources),
            "groups_detail": duplicate_sources,
            "same_key_same_payload": same_key_same_payload,
            "same_key_different_payload": same_key_different_payload,
        },
        "currentness_query_ms": {
            "runs": 10,
            "result_size": result_size,
            "min": min(timings),
            "median": statistics.median(timings),
            "max": max(timings),
        },
    }
    _write("corpus-audit.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("hashes", "adversarial", "corpus"))
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    if args.command == "hashes":
        _write("artifact-hashes.json", artifact_hashes())
    elif args.command == "adversarial":
        adversarial()
    elif args.command == "corpus":
        if args.db is None:
            parser.error("--db is required for corpus")
        corpus(args.db)


if __name__ == "__main__":
    main()
