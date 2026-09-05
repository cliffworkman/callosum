"""Independent, research-only audit harness for H1b source components.

All generated artifacts are written beneath ignored ``.local/h1b-source-component-audit``.
The harness never calls a provider/model and never writes production databases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import fitz

SEED = 20260905
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local" / "h1b-source-component-audit"
sys.path.insert(0, str(ROOT))
FLOAT_TOLERANCE_PT = 0.0001
DIRECTION_TOLERANCE = 0.000001
DERIVATION_VERSION = "source-components-v1"


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _connect(path: Path, *, writable: bool = False) -> sqlite3.Connection:
    if writable:
        conn = sqlite3.connect(path)
    else:
        conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _feed_value(digest: Any, value: Any) -> None:
    if value is None:
        payload = b"N"
    elif isinstance(value, bytes):
        payload = b"B" + value
    elif isinstance(value, float):
        payload = b"F" + value.hex().encode("ascii")
    else:
        payload = b"S" + str(value).encode("utf-8", errors="surrogatepass")
    digest.update(len(payload).to_bytes(8, "big"))
    digest.update(payload)


def _query_digest(conn: sqlite3.Connection, sql: str) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    for row in conn.execute(sql):
        count += 1
        for value in row:
            _feed_value(digest, value)
        digest.update(b"\xff")
    return count, digest.hexdigest()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?", (name,)).fetchone()
        is not None
    )


def snapshot(db: Path, output: Path) -> dict[str, Any]:
    """Logical hashes for every pre-H1b retrieval-bearing identity."""
    with _connect(db) as conn:
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result: dict[str, Any] = {
            "schema": "codex-h1b-invariant-snapshot-v1",
            "database_file_sha256": _file_sha(db),
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "migration": conn.execute("SELECT version_num FROM alembic_version").fetchone()[0],
            "tables": {},
        }
        # Hash sqlite-vec's ordinary shadow tables directly. Opening the virtual root with the
        # stdlib sqlite3 module requires loading vec0; the row-id and vector blobs we need for an
        # invariant live in the shadow tables and are readable without executing an extension.
        targets = [
            "chunks",
            "embeddings",
            "attachments",
            "source_pages",
            "source_components",
            "paper_figures",
        ] + sorted(name for name in tables if name.startswith("callosum_vec_embeddings_384_"))
        for name in targets:
            if name not in tables:
                continue
            columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{name}")')]
            if not columns:
                continue
            order = "id" if "id" in columns else "rowid"
            count, digest = _query_digest(conn, f'SELECT * FROM "{name}" ORDER BY "{order}"')
            result["tables"][name] = {"rows": count, "sha256": digest, "columns": columns}

        result["counts"] = {
            "chunks_total": conn.execute("SELECT count(*) FROM chunks").fetchone()[0],
            "chunks_live": conn.execute(
                "SELECT count(*) FROM chunks c JOIN papers p ON p.id=c.paper_id WHERE p.deleted_at IS NULL"
            ).fetchone()[0],
            "chunks_trashed": conn.execute(
                "SELECT count(*) FROM chunks c JOIN papers p ON p.id=c.paper_id WHERE p.deleted_at IS NOT NULL"
            ).fetchone()[0],
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _attachment_path(row: sqlite3.Row | dict[str, Any]) -> Path | None:
    value = row["resolved_path"] or row["original_path"]
    return Path(value) if value else None


def coverage(db: Path, output: Path) -> dict[str, Any]:
    with _connect(db) as conn:
        pdf_rows = conn.execute(
            """
            SELECT a.id,a.paper_id,a.availability,a.resolved_path,a.original_path,a.checksum,
                   p.deleted_at
            FROM attachments a JOIN papers p ON p.id=a.paper_id
            WHERE lower(a.content_type)='application/pdf'
            ORDER BY a.id
            """
        ).fetchall()
        pages = conn.execute(
            """
            SELECT sp.attachment_id,sp.source_checksum,sp.derivation_version,count(*) n_pages
            FROM source_pages sp GROUP BY sp.attachment_id,sp.source_checksum,sp.derivation_version
            """
        ).fetchall()
        represented: dict[int, list[sqlite3.Row]] = defaultdict(list)
        for row in pages:
            represented[int(row["attachment_id"])].append(row)

        states: Counter[str] = Counter()
        private_rows: list[dict[str, Any]] = []
        for row in pdf_rows:
            aid = int(row["id"])
            live = row["deleted_at"] is None
            path = _attachment_path(row)
            exists = bool(path and path.is_file())
            actual = _file_sha(path) if exists and path else None
            checksum_match = bool(actual and row["checksum"] and actual == row["checksum"])
            reps = represented.get(aid, [])
            current = bool(reps) and all(
                item["source_checksum"] == row["checksum"] and item["derivation_version"] == DERIVATION_VERSION
                for item in reps
            )
            if not live:
                state = "trashed"
            elif not exists:
                state = "missing_file"
            elif row["checksum"] and not checksum_match:
                state = "checksum_mismatch"
            elif current:
                state = "current"
            elif reps:
                state = "stale"
            else:
                state = "absent"
            states[state] += 1
            private_rows.append(
                {
                    "attachment_id": aid,
                    "paper_id": int(row["paper_id"]),
                    "live": live,
                    "availability": row["availability"],
                    "path": str(path) if path else None,
                    "exists": exists,
                    "stored_checksum": row["checksum"],
                    "actual_checksum": actual,
                    "state": state,
                    "stored_page_rows": sum(int(item["n_pages"]) for item in reps),
                }
            )

        component_counts = dict(
            conn.execute("SELECT kind,count(*) FROM source_components GROUP BY kind ORDER BY kind").fetchall()
        )
        soft_delete = {
            "trashed_papers": conn.execute("SELECT count(*) FROM papers WHERE deleted_at IS NOT NULL").fetchone()[0],
            "trashed_chunks": conn.execute(
                "SELECT count(*) FROM chunks c JOIN papers p ON p.id=c.paper_id WHERE p.deleted_at IS NOT NULL"
            ).fetchone()[0],
            "paper_2_deleted": bool(conn.execute("SELECT deleted_at IS NOT NULL FROM papers WHERE id=2").fetchone()[0]),
            "paper_2_chunks": conn.execute("SELECT count(*) FROM chunks WHERE paper_id=2").fetchone()[0],
        }
        if _table_exists(conn, "chunk_structure"):
            soft_delete["paper_2_chunks_without_structure"] = conn.execute(
                "SELECT count(*) FROM chunks c LEFT JOIN chunk_structure cs ON cs.chunk_id=c.id "
                "WHERE c.paper_id=2 AND cs.chunk_id IS NULL"
            ).fetchone()[0]
            soft_delete["all_live_chunks_without_structure"] = conn.execute(
                "SELECT count(*) FROM chunks c JOIN papers p ON p.id=c.paper_id "
                "LEFT JOIN chunk_structure cs ON cs.chunk_id=c.id "
                "WHERE p.deleted_at IS NULL AND cs.chunk_id IS NULL"
            ).fetchone()[0]

    private = {
        "schema": "codex-h1b-coverage-private-v1",
        "attachments": private_rows,
    }
    (OUT / "coverage-private.json").write_text(json.dumps(private, indent=2), encoding="utf-8")
    safe = {
        "schema": "codex-h1b-coverage-summary-v1",
        "pdf_attachments_total": len(pdf_rows),
        "states": dict(states),
        "source_pages": sum(int(r["stored_page_rows"]) for r in private_rows),
        "source_components": sum(component_counts.values()),
        "component_counts": component_counts,
        "soft_delete": soft_delete,
    }
    output.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return safe


def _component_value(row: sqlite3.Row, field: str) -> Any:
    return row[field] if field in row.keys() else None


def _stored_page_tree(conn: sqlite3.Connection, attachment_id: int, page_number: int) -> dict[str, Any] | None:
    page = conn.execute(
        "SELECT * FROM source_pages WHERE attachment_id=? AND page_number=?",
        (attachment_id, page_number),
    ).fetchone()
    if page is None:
        return None
    rows = conn.execute("SELECT * FROM source_components WHERE source_page_id=? ORDER BY id", (page["id"],)).fetchall()
    by_parent: dict[int | None, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        by_parent[row["parent_id"]].append(row)

    fields = (
        "kind",
        "native_order",
        "sorted_order",
        "child_order",
        "x0",
        "y0",
        "x1",
        "y1",
        "text",
        "font",
        "font_size",
        "flags",
        "dir_x",
        "dir_y",
        "wmode",
    )

    def walk(row: sqlite3.Row, path: str) -> list[dict[str, Any]]:
        item = {"path": path, **{field: _component_value(row, field) for field in fields}}
        result = [item]
        children = sorted(
            by_parent.get(int(row["id"]), []),
            key=lambda child: (child["child_order"] is None, child["child_order"], child["id"]),
        )
        for child in children:
            result.extend(walk(child, f"{path}/{child['kind']}:{child['child_order']}"))
        return result

    top = sorted(
        by_parent.get(None, []),
        key=lambda row: (row["sorted_order"] is None, row["sorted_order"], row["id"]),
    )
    components: list[dict[str, Any]] = []
    for row in top:
        components.extend(walk(row, f"block:{row['sorted_order']}"))
    return {
        "page_number": int(page["page_number"]),
        "width": float(page["width"]),
        "height": float(page["height"]),
        "rotation": int(page["rotation"]),
        "coordinate_system": page["coordinate_system"],
        "extraction_tool": page["extraction_tool"],
        "extraction_version": page["extraction_version"],
        "derivation_version": page["derivation_version"],
        "source_checksum": page["source_checksum"],
        "components": components,
    }


def _fresh_callosum_tree(page: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "kind",
        "native_order",
        "sorted_order",
        "child_order",
        "text",
        "font",
        "font_size",
        "flags",
        "dir_x",
        "dir_y",
        "wmode",
    )

    def walk(component: Any, path: str) -> list[dict[str, Any]]:
        bbox = component.bbox or (None, None, None, None)
        item = {
            "path": path,
            **{field: getattr(component, field) for field in fields},
            "x0": bbox[0],
            "y0": bbox[1],
            "x1": bbox[2],
            "y1": bbox[3],
        }
        result = [item]
        for child in component.children:
            result.extend(walk(child, f"{path}/{child.kind}:{child.child_order}"))
        return result

    components: list[dict[str, Any]] = []
    for component in page.components:
        components.extend(walk(component, f"block:{component.sorted_order}"))
    return {
        "page_number": page.page_number,
        "width": page.width,
        "height": page.height,
        "rotation": page.rotation,
        **metadata,
        "components": components,
    }


def _compare_scalar(field: str, left: Any, right: Any) -> tuple[bool, bool]:
    exact = left == right
    if exact:
        return True, True
    if left is None or right is None:
        return False, False
    tolerance = DIRECTION_TOLERANCE if field in {"dir_x", "dir_y"} else FLOAT_TOLERANCE_PT
    if field in {"x0", "y0", "x1", "y1", "width", "height", "font_size", "dir_x", "dir_y"}:
        try:
            return False, math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)
        except (TypeError, ValueError):
            pass
    return False, False


def _compare_trees(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    fields = ["page_number", "width", "height", "rotation"]
    fields.extend(
        field
        for field in (
            "coordinate_system",
            "extraction_tool",
            "extraction_version",
            "derivation_version",
            "source_checksum",
        )
        if field in right
    )
    counts: Counter[str] = Counter()
    mismatches: Counter[str] = Counter()
    tolerant: Counter[str] = Counter()
    for field in fields:
        exact, within = _compare_scalar(field, left.get(field), right.get(field))
        counts[field] += 1
        if not exact:
            mismatches[field] += 1
        if within:
            tolerant[field] += 1
    l_items = left["components"]
    r_items = right["components"]
    counts["component_count"] += 1
    if len(l_items) != len(r_items):
        mismatches["component_count"] += 1
    else:
        tolerant["component_count"] += 1
    component_fields = (
        "path",
        "kind",
        "native_order",
        "sorted_order",
        "child_order",
        "x0",
        "y0",
        "x1",
        "y1",
        "text",
        "font",
        "font_size",
        "flags",
        "dir_x",
        "dir_y",
        "wmode",
    )
    for l_item, r_item in zip(l_items, r_items, strict=False):
        for field in component_fields:
            counts[field] += 1
            exact, within = _compare_scalar(field, l_item.get(field), r_item.get(field))
            if not exact:
                mismatches[field] += 1
            if within:
                tolerant[field] += 1
    return {
        "comparisons": dict(counts),
        "exact_mismatches": dict(mismatches),
        "within_tolerance": dict(tolerant),
    }


def _merge_comparisons(total: dict[str, Counter[str]], result: dict[str, Any]) -> None:
    total["comparisons"].update(result["comparisons"])
    total["exact_mismatches"].update(result["exact_mismatches"])
    total["within_tolerance"].update(result["within_tolerance"])


def _raw_tree(page: fitz.Page) -> dict[str, Any]:
    """Independent direct-PyMuPDF observation; never calls Callosum's component builder."""
    text_dict = page.get_text("dict", sort=True)
    components: list[dict[str, Any]] = []
    for sorted_order, block in enumerate(text_dict.get("blocks", []) or []):
        block_type = block.get("type")
        if block_type not in {0, 1}:
            continue
        kind = "image" if block_type == 1 else "raw_text_block"
        bbox = tuple(block.get("bbox", (None, None, None, None)))[:4]
        base = {
            "path": f"block:{sorted_order}",
            "kind": kind,
            "native_order": block.get("number") if isinstance(block.get("number"), int) else None,
            "sorted_order": sorted_order,
            "child_order": None,
            "x0": bbox[0],
            "y0": bbox[1],
            "x1": bbox[2],
            "y1": bbox[3],
            "text": None,
            "font": None,
            "font_size": None,
            "flags": None,
            "dir_x": None,
            "dir_y": None,
            "wmode": None,
        }
        if block_type == 1:
            components.append(base)
            continue
        valid_lines = []
        for line_order, line in enumerate(block.get("lines", []) or []):
            spans = [s for s in (line.get("spans", []) or []) if s.get("text", "")]
            if spans:
                valid_lines.append((line_order, line, spans))
        if not valid_lines:
            continue
        components.append(base)
        for line_order, line, _spans in valid_lines:
            line_bbox = tuple(line.get("bbox", (None, None, None, None)))[:4]
            direction = line.get("dir")
            dir_x = dir_y = None
            if isinstance(direction, (tuple, list)) and len(direction) >= 2:
                dir_x, dir_y = float(direction[0]), float(direction[1])
            line_path = f"block:{sorted_order}/line:{line_order}"
            components.append(
                {
                    "path": line_path,
                    "kind": "line",
                    "native_order": None,
                    "sorted_order": None,
                    "child_order": line_order,
                    "x0": line_bbox[0],
                    "y0": line_bbox[1],
                    "x1": line_bbox[2],
                    "y1": line_bbox[3],
                    "text": None,
                    "font": None,
                    "font_size": None,
                    "flags": None,
                    "dir_x": dir_x,
                    "dir_y": dir_y,
                    "wmode": line.get("wmode") if isinstance(line.get("wmode"), int) else None,
                }
            )
            for span_order, span in enumerate(line.get("spans", []) or []):
                text = span.get("text", "")
                if not text:
                    continue
                span_bbox = tuple(span.get("bbox", (None, None, None, None)))[:4]
                size = span.get("size")
                components.append(
                    {
                        "path": f"{line_path}/span:{span_order}",
                        "kind": "span",
                        "native_order": None,
                        "sorted_order": None,
                        "child_order": span_order,
                        "x0": span_bbox[0],
                        "y0": span_bbox[1],
                        "x1": span_bbox[2],
                        "y1": span_bbox[3],
                        "text": text,
                        "font": span.get("font") or None,
                        "font_size": float(size) if isinstance(size, (int, float)) else None,
                        "flags": span.get("flags") if isinstance(span.get("flags"), int) else None,
                        "dir_x": None,
                        "dir_y": None,
                        "wmode": None,
                    }
                )
    return {
        "page_number": page.number + 1,
        "width": float(page.rect.width),
        "height": float(page.rect.height),
        "rotation": int(page.rotation) % 360,
        "components": components,
    }


def _stored_as_raw(tree: dict[str, Any]) -> dict[str, Any]:
    copy = {key: value for key, value in tree.items() if key != "components"}
    items = []
    for item in tree["components"]:
        row = dict(item)
        if row["kind"] in {"text_block", "heading"}:
            row["kind"] = "raw_text_block"
            # Heading text is a derived convenience duplicate; the raw block layer has no text.
            row["text"] = None
        items.append(row)
    copy["components"] = items
    return copy


def _column_proxy(tree: dict[str, Any]) -> str:
    width = float(tree["width"])
    blocks = [
        row
        for row in tree["components"]
        if row["path"].count("/") == 0 and row["kind"] in {"text_block", "heading"} and row["x0"] is not None
    ]
    substantial = [row for row in blocks if float(row["x1"] - row["x0"]) >= width * 0.2]
    if len(substantial) < 4:
        return "uncertain"
    centers = sorted((float(row["x0"] + row["x1"]) / 2, index, row) for index, row in enumerate(substantial))
    gaps = [(centers[i + 1][0] - centers[i][0], i) for i in range(len(centers) - 1)]
    gap, index = max(gaps, default=(0.0, 0))
    left = [row for _, _, row in centers[: index + 1]]
    right = [row for _, _, row in centers[index + 1 :]]
    if gap >= width * 0.18 and len(left) >= 2 and len(right) >= 2:
        overlap = 0
        for a in left:
            for b in right:
                if min(a["y1"], b["y1"]) > max(a["y0"], b["y0"]):
                    overlap += 1
        if overlap:
            return "two_column"
    broad = sum(float(row["x1"] - row["x0"]) >= width * 0.55 for row in substantial)
    return "one_column" if broad >= 2 else "uncertain"


def _order_stats(tree: dict[str, Any]) -> dict[str, Any]:
    blocks = [row for row in tree["components"] if row["path"].count("/") == 0 and row["native_order"] is not None]
    native = [int(row["native_order"]) for row in blocks]
    distinct = len(native) == len(set(native))
    inversions = sum(native[i] > native[j] for i in range(len(native)) for j in range(i + 1, len(native)))
    pairs = len(native) * (len(native) - 1) // 2
    return {
        "blocks": len(blocks),
        "native_unique": distinct,
        "differs": native != sorted(native),
        "pair_disagreement": inversions / pairs if pairs else 0.0,
    }


def compare_callosum(db: Path, output: Path) -> dict[str, Any]:
    from app.backend.pdf_processing.extraction import extract_pdf

    with _connect(db) as conn:
        targets = conn.execute(
            """
            SELECT a.id,a.paper_id,a.resolved_path,a.original_path,a.checksum
            FROM attachments a JOIN papers p ON p.id=a.paper_id
            WHERE p.deleted_at IS NULL AND lower(a.content_type)='application/pdf'
            ORDER BY a.id
            """
        ).fetchall()
        totals: dict[str, Counter[str]] = {
            "comparisons": Counter(),
            "exact_mismatches": Counter(),
            "within_tolerance": Counter(),
        }
        order_rows: list[dict[str, Any]] = []
        private: list[dict[str, Any]] = []
        state = Counter()
        for target in targets:
            path = _attachment_path(target)
            if not path or not path.is_file():
                state["missing"] += 1
                continue
            actual = _file_sha(path)
            if target["checksum"] and actual != target["checksum"]:
                state["checksum_mismatch"] += 1
                continue
            extraction = extract_pdf(path)
            attachment_mismatches: Counter[str] = Counter()
            for fresh in extraction.source_pages:
                stored = _stored_page_tree(conn, int(target["id"]), fresh.page_number)
                if stored is None:
                    attachment_mismatches["missing_page"] += 1
                    continue
                expected = _fresh_callosum_tree(
                    fresh,
                    {
                        "coordinate_system": extraction.coordinate_system,
                        "extraction_tool": extraction.extraction_tool,
                        "extraction_version": extraction.extraction_version,
                        "derivation_version": DERIVATION_VERSION,
                        "source_checksum": actual,
                    },
                )
                comparison = _compare_trees(stored, expected)
                _merge_comparisons(totals, comparison)
                attachment_mismatches.update(comparison["exact_mismatches"])
                stats = _order_stats(stored)
                order_rows.append(
                    {
                        "attachment_id": int(target["id"]),
                        "page": fresh.page_number,
                        "column_proxy": _column_proxy(stored),
                        **stats,
                    }
                )
            state["audited"] += 1
            private.append(
                {
                    "attachment_id": int(target["id"]),
                    "paper_id": int(target["paper_id"]),
                    "path": str(path),
                    "pages": len(extraction.source_pages),
                    "exact_mismatches": dict(attachment_mismatches),
                }
            )

    rng = random.Random(SEED)
    by_column: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in order_rows:
        by_column[row["column_proxy"]].append(row)
    order_summary: dict[str, Any] = {}
    for category, rows in sorted(by_column.items()):
        ordered = sorted(rows, key=lambda row: (row["attachment_id"], row["page"]))
        rng.shuffle(ordered)
        sample = ordered[: min(40, len(ordered))]
        order_summary[category] = {
            "pages_total": len(rows),
            "sample_n": len(sample),
            "sample_disagreement_pages": sum(bool(row["differs"]) for row in sample),
            "sample_mean_pair_disagreement": (
                sum(float(row["pair_disagreement"]) for row in sample) / len(sample) if sample else None
            ),
        }
    (OUT / "callosum-roundtrip-private.json").write_text(
        json.dumps({"attachments": private, "order_pages": order_rows}, indent=2), encoding="utf-8"
    )
    safe = {
        "schema": "codex-h1b-callosum-roundtrip-v1",
        "attachment_states": dict(state),
        **{key: dict(value) for key, value in totals.items()},
        "pages_compared": len(order_rows),
        "order": order_summary,
    }
    output.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return safe


def _candidate_categories(conn: sqlite3.Connection) -> dict[str, list[tuple[int, int]]]:
    pages = conn.execute(
        "SELECT id,attachment_id,page_number FROM source_pages ORDER BY attachment_id,page_number"
    ).fetchall()
    categories: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for page in pages:
        tree = _stored_page_tree(conn, int(page["attachment_id"]), int(page["page_number"]))
        if tree is None:
            continue
        key = (int(page["attachment_id"]), int(page["page_number"]))
        proxy = _column_proxy(tree)
        categories[proxy].append(key)
        stats = _order_stats(tree)
        if stats["differs"]:
            categories["order_disagreement"].append(key)
        kinds = Counter(row["kind"] for row in tree["components"])
        if kinds["heading"]:
            categories["pure_heading"].append(key)
        if kinds["image"]:
            categories["image_figure"].append(key)
        if kinds["span"] >= 60:
            categories["table_or_dense_span"].append(key)

    if _table_exists(conn, "chunk_structure"):
        rows = conn.execute(
            """
            SELECT DISTINCT c.attachment_id,c.page_start,cs.chunk_type
            FROM chunks c JOIN papers p ON p.id=c.paper_id
            JOIN chunk_structure cs ON cs.chunk_id=c.id
            WHERE p.deleted_at IS NULL
            ORDER BY c.attachment_id,c.page_start
            """
        ).fetchall()
        for row in rows:
            key = (int(row["attachment_id"]), int(row["page_start"] or 1))
            kind = row["chunk_type"]
            if kind in {"table_cell_debris", "math_or_symbol"}:
                categories["orphan_table_value"].append(key)
            if kind == "caption":
                categories["caption"].append(key)
    return categories


def raw_sample(db: Path, output: Path) -> dict[str, Any]:
    with _connect(db) as conn:
        targets = {
            int(row["id"]): row
            for row in conn.execute(
                """
                SELECT a.id,a.paper_id,a.resolved_path,a.original_path,a.checksum
                FROM attachments a JOIN papers p ON p.id=a.paper_id
                WHERE p.deleted_at IS NULL AND lower(a.content_type)='application/pdf'
                """
            )
        }
        categories = _candidate_categories(conn)
        rng = random.Random(SEED)
        selected: dict[tuple[int, int], set[str]] = defaultdict(set)
        priority = (
            "one_column",
            "two_column",
            "order_disagreement",
            "pure_heading",
            "image_figure",
            "orphan_table_value",
            "caption",
            "table_or_dense_span",
        )
        for category in priority:
            values = sorted(set(categories.get(category, [])))
            rng.shuffle(values)
            for key in values[:4]:
                selected[key].add(category)
        all_pages = sorted({key for values in categories.values() for key in values})
        rng.shuffle(all_pages)
        for key in all_pages:
            if len(selected) >= 30:
                break
            selected[key].add("deterministic_fill")

        totals: dict[str, Counter[str]] = {
            "comparisons": Counter(),
            "exact_mismatches": Counter(),
            "within_tolerance": Counter(),
        }
        cases = []
        missing = Counter()
        for (attachment_id, page_number), labels in sorted(selected.items()):
            target = targets.get(attachment_id)
            if target is None:
                missing["attachment_not_live"] += 1
                continue
            path = _attachment_path(target)
            if not path or not path.is_file():
                missing["file_missing"] += 1
                continue
            if target["checksum"] and _file_sha(path) != target["checksum"]:
                missing["checksum_mismatch"] += 1
                continue
            with fitz.open(path) as document:
                if page_number < 1 or page_number > len(document):
                    missing["page_missing"] += 1
                    continue
                raw = _raw_tree(document[page_number - 1])
            stored = _stored_page_tree(conn, attachment_id, page_number)
            if stored is None:
                missing["stored_missing"] += 1
                continue
            comparison = _compare_trees(_stored_as_raw(stored), raw)
            _merge_comparisons(totals, comparison)
            opaque = hashlib.sha256(f"{SEED}:{attachment_id}:{page_number}".encode("ascii")).hexdigest()[:12].upper()
            cases.append(
                {
                    "opaque_id": f"H1B-{opaque}",
                    "attachment_id": attachment_id,
                    "page": page_number,
                    "paper_id": int(target["paper_id"]),
                    "path": str(path),
                    "labels": sorted(labels),
                    "comparison": comparison,
                }
            )
    (OUT / "raw-pymupdf-private.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    safe_cases = [
        {
            "opaque_id": case["opaque_id"],
            "labels": case["labels"],
            "exact_mismatch_fields": sorted(case["comparison"]["exact_mismatches"]),
        }
        for case in cases
    ]
    safe = {
        "schema": "codex-h1b-independent-pymupdf-v1",
        "sample_n": len(cases),
        "selection_missing": dict(missing),
        **{key: dict(value) for key, value in totals.items()},
        "cases": safe_cases,
    }
    output.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return safe


def locator_snapshot(db: Path, attachment_ids: Iterable[int], output: Path) -> dict[str, Any]:
    with _connect(db) as conn:
        payload: dict[str, Any] = {"schema": "codex-h1b-locator-snapshot-v1", "attachments": {}}
        for attachment_id in sorted(set(attachment_ids)):
            pages = conn.execute(
                "SELECT id,page_number FROM source_pages WHERE attachment_id=? ORDER BY page_number",
                (attachment_id,),
            ).fetchall()
            page_rows = []
            for page in pages:
                tree = _stored_page_tree(conn, attachment_id, int(page["page_number"]))
                assert tree is not None
                canonical = json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                component_ids = [
                    int(row[0])
                    for row in conn.execute(
                        "SELECT id FROM source_components WHERE source_page_id=? ORDER BY id", (page["id"],)
                    )
                ]
                page_rows.append(
                    {
                        "page_number": int(page["page_number"]),
                        "surrogate_page_id": int(page["id"]),
                        "surrogate_component_ids": component_ids,
                        "logical_tree_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                    }
                )
            payload["attachments"][str(attachment_id)] = page_rows
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def artifact_hashes(output: Path) -> dict[str, Any]:
    targets = [
        "alembic/versions/0080_source_components.py",
        "app/backend/pdf_processing/extraction.py",
        "app/backend/pdf_processing/source_components.py",
        "app/backend/pdf_processing/ingest.py",
        "app/backend/persistence/schema.py",
        "app/backend/persistence/schema_source_components.py",
        "app/backend/persistence/source_components_repo.py",
        "app/backend/grobid_pipeline.py",
        "integrations/grobid/client.py",
        "integrations/grobid/tei_parse.py",
        "tools/backfill_source_components.py",
        ".claude/research/h1b_source_component_audit.py",
    ]
    result = {
        "schema": "codex-h1b-code-hashes-v1",
        "files": {name: _file_sha(ROOT / name) for name in targets},
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def structural_audit(db: Path, output: Path) -> dict[str, Any]:
    """Schema-level safety checks plus stable logical-locator uniqueness."""
    with _connect(db) as conn:
        scalar_queries = {
            "orphan_source_page": """
                SELECT count(*) FROM source_components sc
                LEFT JOIN source_pages sp ON sp.id=sc.source_page_id WHERE sp.id IS NULL
            """,
            "orphan_parent": """
                SELECT count(*) FROM source_components sc
                LEFT JOIN source_components parent ON parent.id=sc.parent_id
                WHERE sc.parent_id IS NOT NULL AND parent.id IS NULL
            """,
            "cross_page_parent": """
                SELECT count(*) FROM source_components sc
                JOIN source_components parent ON parent.id=sc.parent_id
                WHERE parent.source_page_id != sc.source_page_id
            """,
            "invalid_top_kind": """
                SELECT count(*) FROM source_components
                WHERE parent_id IS NULL AND kind NOT IN ('text_block','heading','image')
            """,
            "invalid_line_parent": """
                SELECT count(*) FROM source_components sc
                JOIN source_components parent ON parent.id=sc.parent_id
                WHERE sc.kind='line' AND parent.kind NOT IN ('text_block','heading')
            """,
            "invalid_span_parent": """
                SELECT count(*) FROM source_components sc
                JOIN source_components parent ON parent.id=sc.parent_id
                WHERE sc.kind='span' AND parent.kind!='line'
            """,
            "partial_bbox": """
                SELECT count(*) FROM source_components
                WHERE (x0 IS NULL OR y0 IS NULL OR x1 IS NULL OR y1 IS NULL)
                  AND NOT (x0 IS NULL AND y0 IS NULL AND x1 IS NULL AND y1 IS NULL)
            """,
            "inverted_bbox": """
                SELECT count(*) FROM source_components
                WHERE x0 IS NOT NULL AND (x1 < x0 OR y1 < y0)
            """,
            "inverted_text_bbox": """
                SELECT count(*) FROM source_components
                WHERE kind!='image' AND x0 IS NOT NULL AND (x1 < x0 OR y1 < y0)
            """,
            "inverted_image_bbox": """
                SELECT count(*) FROM source_components
                WHERE kind='image' AND x0 IS NOT NULL AND (x1 < x0 OR y1 < y0)
            """,
            "null_image_bbox": """
                SELECT count(*) FROM source_components
                WHERE kind='image' AND x0 IS NULL AND y0 IS NULL AND x1 IS NULL AND y1 IS NULL
            """,
            "image_bbox_outside_page": """
                SELECT count(*) FROM source_components sc
                JOIN source_pages sp ON sp.id=sc.source_page_id
                WHERE sc.kind='image' AND sc.x0 IS NOT NULL
                  AND (sc.x0<0 OR sc.y0<0 OR sc.x1>sp.width OR sc.y1>sp.height)
            """,
            "empty_span_text": "SELECT count(*) FROM source_components WHERE kind='span' AND text=''",
            "heading_rows": "SELECT count(*) FROM source_components WHERE kind='heading'",
            "image_rows": "SELECT count(*) FROM source_components WHERE kind='image'",
            "heading_blocks_in_chunks": """
                SELECT count(DISTINCT sc.id)
                FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
                JOIN chunks c ON c.attachment_id=sp.attachment_id AND c.page_start=sp.page_number
                JOIN json_each(c.bbox_json) box
                WHERE sc.kind='heading'
                  AND json_extract(box.value,'$.page')=sp.page_number
                  AND json_extract(box.value,'$.block')=sc.sorted_order
            """,
            "image_blocks_in_chunks": """
                SELECT count(DISTINCT sc.id)
                FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
                JOIN chunks c ON c.attachment_id=sp.attachment_id AND c.page_start=sp.page_number
                JOIN json_each(c.bbox_json) box
                WHERE sc.kind='image'
                  AND json_extract(box.value,'$.page')=sp.page_number
                  AND json_extract(box.value,'$.block')=sc.sorted_order
            """,
            "styled_spans": """
                SELECT count(*) FROM source_components
                WHERE kind='span' AND (font IS NOT NULL OR font_size IS NOT NULL OR flags IS NOT NULL)
            """,
            "directed_lines": """
                SELECT count(*) FROM source_components
                WHERE kind='line' AND dir_x IS NOT NULL AND dir_y IS NOT NULL
            """,
            "rotated_pages": "SELECT count(*) FROM source_pages WHERE rotation != 0",
        }
        counts = {name: int(conn.execute(sql).fetchone()[0]) for name, sql in scalar_queries.items()}

        locator_count = 0
        locator_collisions = 0
        order_totals: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"pages": 0, "disagreement_pages": 0, "pair_disagreement_sum": 0.0}
        )
        for page in conn.execute(
            "SELECT attachment_id,page_number,source_checksum,derivation_version FROM source_pages "
            "ORDER BY attachment_id,page_number"
        ):
            tree = _stored_page_tree(conn, int(page["attachment_id"]), int(page["page_number"]))
            assert tree is not None
            paths = [tuple(item["path"]) for item in tree["components"]]
            locator_count += len(paths)
            locator_collisions += len(paths) - len(set(paths))
            layout = _column_proxy(tree)
            disagreement = float(_order_stats(tree)["pair_disagreement"])
            order_totals[layout]["pages"] += 1
            order_totals[layout]["disagreement_pages"] += int(disagreement > 0)
            order_totals[layout]["pair_disagreement_sum"] += disagreement

        order_summary = {}
        for layout, item in sorted(order_totals.items()):
            pages = int(item["pages"])
            order_summary[layout] = {
                "pages": pages,
                "disagreement_pages": int(item["disagreement_pages"]),
                "mean_pair_disagreement": float(item["pair_disagreement_sum"]) / pages if pages else 0.0,
            }

    result = {
        "schema": "codex-h1b-structural-audit-v1",
        "counts": counts,
        "logical_locator": {
            "basis": "attachment source checksum + derivation version + page number + component path",
            "components": locator_count,
            "within_page_path_collisions": locator_collisions,
        },
        "native_vs_sorted_order_all_pages": order_summary,
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def grobid_fixture_audit(output: Path) -> dict[str, Any]:
    """Compare production figure parsing with an independent ElementTree walk of the tracked TEI."""
    import xml.etree.ElementTree as ET

    from integrations.grobid.tei_parse import parse_figures

    fixture = ROOT / "tests" / "fixtures" / "grobid" / "sample_fulltext.tei.xml"
    payload = fixture.read_bytes()
    root = ET.fromstring(payload)
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    raw = root.findall(".//tei:text/tei:body/tei:figure", ns)
    parsed = parse_figures(payload)
    xml_key = "{http://www.w3.org/XML/1998/namespace}id"
    raw_ids = [node.get(xml_key) for node in raw]
    parsed_ids = [item.xml_id for item in parsed]
    raw_tables = [node for node in raw if node.get("type") == "table"]
    raw_grid_shape = []
    raw_note_count = 0
    for table in raw_tables:
        rows = table.findall("tei:table/tei:row", ns)
        raw_grid_shape.append([len(row.findall("tei:cell", ns)) for row in rows])
        raw_note_count += len(table.findall("tei:note", ns))
    parsed_tables = [item for item in parsed if item.figure_type == "table"]
    result = {
        "schema": "codex-h1b-grobid-fixture-audit-v1",
        "fixture_sha256": _file_sha(fixture),
        "raw_figure_count": len(raw),
        "parsed_figure_count": len(parsed),
        "xml_ids_exact": raw_ids == parsed_ids,
        "raw_table_count": len(raw_tables),
        "parsed_table_count": len(parsed_tables),
        "raw_grid_row_cell_counts": raw_grid_shape,
        "parsed_grid_row_cell_counts": [[len(row) for row in item.table_grid] for item in parsed_tables],
        "grid_shapes_exact": raw_grid_shape == [[len(row) for row in item.table_grid] for item in parsed_tables],
        "raw_table_note_elements": raw_note_count,
        "table_notes_have_destination_field": False,
        "figures_with_page_geometry": sum(item.page_number is not None and item.bbox is not None for item in parsed),
        "figures_without_page_geometry": sum(item.page_number is None or item.bbox is None for item in parsed),
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def heading_audit(db: Path, output: Path) -> dict[str, Any]:
    """Verify preserved headings remain absent from freshly generated current chunk drafts."""
    from app.backend.pdf_processing.extraction import extract_pdf, make_chunk_drafts

    with _connect(db) as conn:
        headings = [
            dict(row)
            for row in conn.execute(
                """
                SELECT sc.id,sp.attachment_id,sp.page_number,sc.sorted_order,sc.text,
                       a.resolved_path,a.checksum
                FROM source_components sc
                JOIN source_pages sp ON sp.id=sc.source_page_id
                JOIN attachments a ON a.id=sp.attachment_id
                JOIN papers p ON p.id=a.paper_id
                WHERE sc.kind='heading' AND p.deleted_at IS NULL
                ORDER BY sp.attachment_id,sp.page_number,sc.sorted_order
                """
            )
        ]
        legacy_matches = int(
            conn.execute(
                """
                SELECT count(DISTINCT sc.id)
                FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
                JOIN chunks c ON c.attachment_id=sp.attachment_id AND c.page_start=sp.page_number
                JOIN json_each(c.bbox_json) box
                WHERE sc.kind='heading'
                  AND json_extract(box.value,'$.page')=sp.page_number
                  AND json_extract(box.value,'$.block')=sc.sorted_order
                """
            ).fetchone()[0]
        )
        legacy_dates = conn.execute(
            """
            SELECT min(c.created_at),max(c.created_at)
            FROM source_components sc JOIN source_pages sp ON sp.id=sc.source_page_id
            JOIN chunks c ON c.attachment_id=sp.attachment_id AND c.page_start=sp.page_number
            JOIN json_each(c.bbox_json) box
            WHERE sc.kind='heading'
              AND json_extract(box.value,'$.page')=sp.page_number
              AND json_extract(box.value,'$.block')=sc.sorted_order
            """
        ).fetchone()

    rng = random.Random(SEED)
    sample = sorted(rng.sample(headings, min(20, len(headings))), key=lambda row: int(row["id"]))
    by_attachment: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in sample:
        by_attachment[int(row["attachment_id"])].append(row)
    current_draft_matches = 0
    safe_cases = []
    for _attachment_id, rows in by_attachment.items():
        extraction = extract_pdf(Path(rows[0]["resolved_path"]))
        drafts = make_chunk_drafts(extraction, source_attachment_checksum=rows[0]["checksum"])
        draft_blocks = {
            (int(box["page"]), int(box["block"]))
            for draft in drafts
            for box in draft.bbox_json
            if "page" in box and "block" in box
        }
        for row in rows:
            matched = (int(row["page_number"]), int(row["sorted_order"])) in draft_blocks
            current_draft_matches += int(matched)
            opaque = hashlib.sha256(f"heading:{SEED}:{row['id']}".encode("ascii")).hexdigest()[:12].upper()
            safe_cases.append({"opaque_id": f"H1B-H-{opaque}", "present_in_current_chunk_drafts": matched})
    result = {
        "schema": "codex-h1b-heading-audit-v1",
        "heading_population": len(headings),
        "sample_n": len(sample),
        "current_chunk_draft_matches": current_draft_matches,
        "legacy_stored_chunk_matches": legacy_matches,
        "legacy_match_created_at_min": legacy_dates[0],
        "legacy_match_created_at_max": legacy_dates[1],
        "cases": safe_cases,
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def edge_case_audit(db: Path, truncation_attachment: int, resume_attachment: int, output: Path) -> dict[str, Any]:
    """Mutating checks for a disposable audit DB clone only."""
    from sqlalchemy import select, update

    from app.backend.pdf_processing.extraction import extract_pdf
    from app.backend.persistence import source_components_repo as repo
    from app.backend.persistence.database import make_engine
    from app.backend.persistence.schema import attachments
    from app.backend.persistence.schema_source_components import source_components, source_pages
    from tools.backfill_source_components import backfill

    engine = make_engine(f"sqlite:///{db.resolve().as_posix()}")
    with engine.begin() as conn:
        target = conn.execute(
            select(attachments.c.resolved_path, attachments.c.checksum).where(attachments.c.id == truncation_attachment)
        ).mappings().one()
    extraction = extract_pdf(Path(target["resolved_path"]))
    old_max = repo.MAX_COMPONENTS_PER_ATTACHMENT
    try:
        repo.MAX_COMPONENTS_PER_ATTACHMENT = 10
        with engine.begin() as conn:
            truncated = repo.replace_attachment_source(
                conn,
                attachment_id=truncation_attachment,
                pages=list(extraction.source_pages),
                coordinate_system=extraction.coordinate_system,
                extraction_tool=extraction.extraction_tool,
                extraction_version=extraction.extraction_version,
                source_checksum=target["checksum"],
            )
        with engine.begin() as conn:
            current_after_truncation = truncation_attachment in repo.attachments_with_current_source(conn)
            truncated_pages = int(
                conn.execute(
                    select(__import__("sqlalchemy").func.count()).select_from(source_pages).where(
                        source_pages.c.attachment_id == truncation_attachment
                    )
                ).scalar_one()
            )
            truncated_components = int(
                conn.execute(
                    select(__import__("sqlalchemy").func.count())
                    .select_from(source_components.join(source_pages))
                    .where(source_pages.c.attachment_id == truncation_attachment)
                ).scalar_one()
            )
    finally:
        repo.MAX_COMPONENTS_PER_ATTACHMENT = old_max

    with engine.begin() as conn:
        original_checksum = conn.execute(
            select(attachments.c.checksum).where(attachments.c.id == truncation_attachment)
        ).scalar_one()
        conn.execute(
            update(attachments).where(attachments.c.id == truncation_attachment).values(checksum="0" * 64)
        )
        stale_excluded = truncation_attachment not in repo.attachments_with_current_source(conn)
        conn.execute(
            update(attachments).where(attachments.c.id == truncation_attachment).values(checksum=original_checksum)
        )

    with engine.begin() as conn:
        conn.execute(source_pages.delete().where(source_pages.c.attachment_id == resume_attachment))
    first = backfill(engine, attachment_id=resume_attachment)
    second = backfill(engine, attachment_id=resume_attachment)
    with engine.begin() as conn:
        resume_pages = int(
            conn.execute(
                select(__import__("sqlalchemy").func.count()).select_from(source_pages).where(
                    source_pages.c.attachment_id == resume_attachment
                )
            ).scalar_one()
        )

    result = {
        "schema": "codex-h1b-edge-case-audit-v1",
        "truncation": {
            "attachment": truncation_attachment,
            "write_result": truncated,
            "stored_pages": truncated_pages,
            "stored_components": truncated_components,
            "classified_current": current_after_truncation,
        },
        "stale_checksum_excluded": stale_excluded,
        "resume": {
            "attachment": resume_attachment,
            "first_run": first,
            "second_run": second,
            "stored_pages": resume_pages,
        },
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _vector_queries(db: Path, query_ids: list[int]) -> list[dict[str, Any]]:
    import sqlite_vec

    conn = sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True)
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)
    results = []
    for query_id in query_ids:
        row = conn.execute("SELECT embedding FROM callosum_vec_embeddings_384 WHERE rowid=?", (query_id,)).fetchone()
        if row is None:
            continue
        hits = conn.execute(
            """
            SELECT rowid,distance FROM callosum_vec_embeddings_384
            WHERE embedding MATCH ? ORDER BY distance LIMIT 20
            """,
            (row[0],),
        ).fetchall()
        results.append(
            {
                "query_embedding_id": query_id,
                "hits": [[int(hit[0]), float(hit[1]).hex()] for hit in hits],
            }
        )
    conn.close()
    return results


def retrieval_identity(before: Path, after: Path, output: Path) -> dict[str, Any]:
    with _connect(before) as conn:
        query_ids = [
            int(row[0])
            for row in conn.execute("SELECT rowid FROM callosum_vec_embeddings_384_rowids ORDER BY rowid LIMIT 10")
        ]
    left = _vector_queries(before, query_ids)
    right = _vector_queries(after, query_ids)
    result = {
        "schema": "codex-h1b-retrieval-identity-v1",
        "query_ids": query_ids,
        "queries_compared": len(left),
        "exactly_equal": left == right,
        "before_sha256": hashlib.sha256(
            json.dumps(left, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "after_sha256": hashlib.sha256(
            json.dumps(right, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("snapshot", "coverage", "compare-callosum", "raw-sample", "locator"):
        item = sub.add_parser(command)
        item.add_argument("--db", type=Path, required=True)
        item.add_argument("--out", type=Path, required=True)
        if command == "locator":
            item.add_argument("--attachment-id", type=int, action="append", required=True)
    hashes = sub.add_parser("artifact-hashes")
    hashes.add_argument("--out", type=Path, required=True)
    retrieval = sub.add_parser("retrieval-identity")
    retrieval.add_argument("--before", type=Path, required=True)
    retrieval.add_argument("--after", type=Path, required=True)
    retrieval.add_argument("--out", type=Path, required=True)
    structural = sub.add_parser("structural-audit")
    structural.add_argument("--db", type=Path, required=True)
    structural.add_argument("--out", type=Path, required=True)
    grobid = sub.add_parser("grobid-fixture-audit")
    grobid.add_argument("--out", type=Path, required=True)
    headings = sub.add_parser("heading-audit")
    headings.add_argument("--db", type=Path, required=True)
    headings.add_argument("--out", type=Path, required=True)
    edge = sub.add_parser("edge-case-audit")
    edge.add_argument("--db", type=Path, required=True)
    edge.add_argument("--truncation-attachment", type=int, required=True)
    edge.add_argument("--resume-attachment", type=int, required=True)
    edge.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        result = snapshot(args.db, args.out)
    elif args.command == "coverage":
        result = coverage(args.db, args.out)
    elif args.command == "compare-callosum":
        result = compare_callosum(args.db, args.out)
    elif args.command == "raw-sample":
        result = raw_sample(args.db, args.out)
    elif args.command == "locator":
        result = locator_snapshot(args.db, args.attachment_id, args.out)
    elif args.command == "artifact-hashes":
        result = artifact_hashes(args.out)
    elif args.command == "retrieval-identity":
        result = retrieval_identity(args.before, args.after, args.out)
    elif args.command == "structural-audit":
        result = structural_audit(args.db, args.out)
    elif args.command == "grobid-fixture-audit":
        result = grobid_fixture_audit(args.out)
    elif args.command == "heading-audit":
        result = heading_audit(args.db, args.out)
    else:
        result = edge_case_audit(args.db, args.truncation_attachment, args.resume_attachment, args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
