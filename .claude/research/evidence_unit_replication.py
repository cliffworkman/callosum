"""Research-only sampler and context exporter for the 2026-09-05 evidence-unit study.

This file is under .claude (dev-only). It never writes the source library, opens a provider,
constructs a model, or changes production behavior. All generated outputs live under ignored
`.local/evidence-unit-replication`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SEED = 20260905
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".local" / "evidence-unit-replication"
DB = OUT / "study.sqlite"

RESULT_VERBS = re.compile(
    r"\b(associated|correlated|predicted|increased|decreased|higher|lower|improved|impaired|"
    r"significant|effect|difference|relationship|linked|mediated|moderated|observed|found|showed)\b",
    re.I,
)
STAT = re.compile(r"(?:\bp\s*[<=>]|\b[trfz]\s*\(?\d*\)?\s*=|\bCI\b|\bSE\b|\bSD\b|\bOR\b|\bHR\b|β\s*=)", re.I)
FOOTNOTE = re.compile(r"^\s*[*†‡a-z0-9, ]{0,12}(?:p\s*[<=>]|significant)", re.I)
CAPTION = re.compile(r"^\s*(?:table|fig(?:ure)?\.?|panel)\s*[0-9ivx]+|^\s*\([a-z]\)", re.I)
TRUNCATED = re.compile(r"(?:-\s*$|\b(?:ﬁ|ﬂ)\s*$|[,;:]\s*$)")
TERMINAL = re.compile(r"[.!?][\]\)\"']?\s*$")


def _connect(path: Path = DB) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def _spans(raw: object) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return []
    return [x for x in (raw or []) if isinstance(x, dict)] if isinstance(raw, list) else []


def _box(row: dict[str, Any]) -> tuple[float, float, float, float] | None:
    spans = _spans(row.get("bbox_json"))
    if not spans:
        return None
    try:
        return (
            min(float(x["x0"]) for x in spans),
            min(float(x["y0"]) for x in spans),
            max(float(x["x1"]) for x in spans),
            max(float(x["y1"]) for x in spans),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _role_sql() -> str:
    return """
    CASE
      WHEN lower(trim(coalesce(a.role,'')))='article-fulltext' THEN 'article-fulltext'
      WHEN lower(trim(coalesce(a.role,'')))='primary' THEN 'article-fulltext'
      WHEN trim(coalesce(a.role,''))='' AND lower(trim(coalesce(a.attachment_type,'')))
           NOT IN ('supplement','supplementary','supplementary-material','preregistration',
                   'registration','protocol') THEN 'article-fulltext'
      ELSE 'other'
    END
    """


def load_universe() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT c.id chunk_id,c.paper_id,c.attachment_id,c.text,c.section,c.page_start,c.page_end,
                   c.bbox_json,c.chunk_version,c.source_attachment_checksum,
                   a.checksum attachment_checksum,a.resolved_path,a.original_path,a.content_type,a.availability,
                   cs.chunk_type,cs.evidence_role,cs.reason_codes_json,cs.confidence,
                   cs.reference_region,cs.repeated_boilerplate,cs.raw_sha structure_raw_sha,
                   EXISTS(
                     SELECT 1 FROM embeddings e WHERE e.target_type='chunk' AND e.target_id=c.id
                       AND coalesce(e.source_chunk_version,'')=coalesce(c.chunk_version,'')
                   ) current_embedding
            FROM chunks c
            JOIN papers p ON p.id=c.paper_id
            JOIN attachments a ON a.id=c.attachment_id
            JOIN chunk_structure cs ON cs.chunk_id=c.id
            WHERE p.deleted_at IS NULL
              AND a.availability='available'
              AND lower(a.content_type)='application/pdf'
              AND ({_role_sql()})='article-fulltext'
              AND coalesce(c.source_attachment_checksum,'')=coalesce(a.checksum,'')
              AND cs.raw_sha=lower(hex(sha256(c.text)))
              AND cs.chunk_version=c.chunk_version
            ORDER BY c.id
            """
        ).fetchall()
    # SQLite has no built-in sha256 in most builds. The query above is retried without that predicate
    # by callers only through this explicit branch, followed by the same full hash check in Python.
    return [dict(row) for row in rows]


def load_universe_portable() -> list[dict[str, Any]]:
    try:
        return load_universe()
    except sqlite3.OperationalError as exc:
        if "no such function: sha256" not in str(exc):
            raise
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT c.id chunk_id,c.paper_id,c.attachment_id,c.text,c.section,c.page_start,c.page_end,
                   c.bbox_json,c.chunk_version,c.source_attachment_checksum,
                   a.checksum attachment_checksum,a.resolved_path,a.original_path,a.content_type,a.availability,
                   cs.chunk_type,cs.evidence_role,cs.reason_codes_json,cs.confidence,
                   cs.reference_region,cs.repeated_boilerplate,cs.raw_sha structure_raw_sha,
                   EXISTS(
                     SELECT 1 FROM embeddings e WHERE e.target_type='chunk' AND e.target_id=c.id
                       AND coalesce(e.source_chunk_version,'')=coalesce(c.chunk_version,'')
                   ) current_embedding
            FROM chunks c JOIN papers p ON p.id=c.paper_id
            JOIN attachments a ON a.id=c.attachment_id JOIN chunk_structure cs ON cs.chunk_id=c.id
            WHERE p.deleted_at IS NULL AND a.availability='available'
              AND lower(a.content_type)='application/pdf' AND ({_role_sql()})='article-fulltext'
              AND coalesce(c.source_attachment_checksum,'')=coalesce(a.checksum,'')
              AND cs.chunk_version=c.chunk_version ORDER BY c.id
            """
        ).fetchall()
    out = [dict(row) for row in rows]
    return [row for row in out if _sha(row["text"]) == row["structure_raw_sha"]]


def _page_profiles(rows: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    pages: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pages[(row["attachment_id"], row["page_start"])].append(row)
    profiles: dict[tuple[int, int], dict[str, Any]] = {}
    for key, members in pages.items():
        cells = [m for m in members if m["chunk_type"] in {"table_cell_debris", "math_or_symbol"}]
        captions = [m for m in members if m["chunk_type"] == "caption" or CAPTION.search(m["text"] or "")]
        prose_boxes = [_box(m) for m in members if len((m["text"] or "").split()) >= 25]
        prose_boxes = [b for b in prose_boxes if b]
        lefts = sorted(b[0] for b in prose_boxes)
        widths = sorted(b[2] - b[0] for b in prose_boxes)
        modal_width = widths[len(widths) // 2] if widths else 0.0
        split_gap = max((b - a for a, b in zip(lefts, lefts[1:], strict=False)), default=0.0)
        profiles[key] = {
            "n_cells": len(cells),
            "n_captions": len(captions),
            "multi_column_proxy": len(prose_boxes) >= 4 and modal_width > 0 and split_gap > 0.6 * modal_width,
        }
    return profiles


def _stress_tags(row: dict[str, Any], profile: dict[str, Any], adjacent_table_page: bool) -> list[str]:
    text = (row["text"] or "").strip()
    words = text.split()
    section = (row["section"] or "").casefold()
    kind = row["chunk_type"]
    tags: list[str] = []
    if len(words) <= 12 or TRUNCATED.search(text) or (len(words) <= 30 and text and not TERMINAL.search(text)):
        tags.append("short_truncated")
    reasons = json.loads(row["reason_codes_json"] or "[]")
    if kind == "heading_fragment" or any("heading" in str(x) for x in reasons):
        tags.append("heading_body")
    if kind in {"body_prose", "unknown"} and (not section or section == "unknown") and RESULT_VERBS.search(text):
        tags.append("body_null_unknown_scientific")
    if section == "results" and (RESULT_VERBS.search(text) or len(words) >= 20):
        tags.append("results_prose")
    if section in {"methods", "method"} and (STAT.search(text) or len(words) >= 20):
        tags.append("methods_statistics")
    if kind == "caption" or CAPTION.search(text):
        tags.append("captions_panels")
    if kind in {"table_cell_debris", "math_or_symbol"}:
        tags.append("isolated_rows_cells")
    if FOOTNOTE.search(text) and len(words) <= 30:
        tags.append("significance_footnotes")
    if profile["multi_column_proxy"]:
        tags.append("multi_column")
    if 5 <= profile["n_cells"] <= 20 and profile["n_captions"] == 1:
        tags.append("simple_table")
    if profile["n_cells"] > 20 or profile["n_captions"] > 1:
        tags.append("complex_table")
    if adjacent_table_page and profile["n_cells"] >= 5:
        tags.append("multi_page_table")
    return tags


def _allocate(strata: dict[str, list[dict[str, Any]]], target: int) -> dict[str, int]:
    allocation = {key: min(4, len(values)) for key, values in strata.items() if values}
    remaining = target - sum(allocation.values())
    capacity = {key: len(strata[key]) - allocation[key] for key in allocation}
    while remaining > 0 and sum(capacity.values()) > 0:
        total = sum(capacity.values())
        raw = {key: remaining * capacity[key] / total for key in capacity if capacity[key] > 0}
        floors = {key: min(capacity[key], math.floor(value)) for key, value in raw.items()}
        granted = sum(floors.values())
        if granted:
            for key, amount in floors.items():
                allocation[key] += amount
                capacity[key] -= amount
            remaining -= granted
            continue
        order = sorted(raw, key=lambda key: (-(raw[key] - math.floor(raw[key])), key))
        for key in order:
            if remaining == 0:
                break
            if capacity[key] > 0:
                allocation[key] += 1
                capacity[key] -= 1
                remaining -= 1
    return allocation


def sample() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_universe_portable()
    profiles = _page_profiles(rows)
    cell_pages = {key for key, value in profiles.items() if value["n_cells"] >= 5}
    for row in rows:
        key = (row["attachment_id"], row["page_start"])
        adjacent = (key[0], key[1] - 1) in cell_pages or (key[0], key[1] + 1) in cell_pages
        row["stress_tags"] = _stress_tags(row, profiles[key], adjacent)

    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[row["chunk_type"]].append(row)
    allocation = _allocate(strata, 120)
    rng = random.Random(SEED)
    selected: list[tuple[str, str, dict[str, Any]]] = []
    used: set[int] = set()
    for kind in sorted(allocation):
        candidates = sorted(strata[kind], key=lambda x: x["chunk_id"])
        rng.shuffle(candidates)
        for row in candidates[: allocation[kind]]:
            selected.append(("probability", kind, row))
            used.add(row["chunk_id"])

    stress_order = [
        "short_truncated", "heading_body", "body_null_unknown_scientific", "results_prose",
        "methods_statistics", "captions_panels", "simple_table", "complex_table",
        "isolated_rows_cells", "significance_footnotes", "multi_column", "multi_page_table",
    ]
    stress_available: dict[str, int] = {}
    for tag in stress_order:
        candidates = [row for row in rows if tag in row["stress_tags"] and row["chunk_id"] not in used]
        candidates.sort(key=lambda x: x["chunk_id"])
        rng.shuffle(candidates)
        stress_available[tag] = len(candidates)
        for row in candidates[:5]:
            selected.append(("stress", tag, row))
            used.add(row["chunk_id"])

    shuffled = list(range(len(selected)))
    rng.shuffle(shuffled)
    codes = [f"EU-{rng.randrange(16**8):08X}" for _ in selected]
    if len(set(codes)) != len(codes):
        raise RuntimeError("opaque-id collision")
    id_for_index = {index: codes[pos] for pos, index in enumerate(shuffled)}

    private: list[dict[str, Any]] = []
    safe: list[dict[str, Any]] = []
    pass_a: list[dict[str, Any]] = []
    n_by_type = Counter(row["chunk_type"] for row in rows)
    for index, (arm, stratum, row) in enumerate(selected):
        case_id = id_for_index[index]
        probability = allocation.get(row["chunk_type"], 0) / n_by_type[row["chunk_type"]] if arm == "probability" else None
        item = {
            "case_id": case_id,
            "arm": arm,
            "primary_stratum": stratum,
            "secondary_tags": row["stress_tags"],
            "inclusion_probability": probability,
            **row,
            "bbox_json": _spans(row["bbox_json"]),
            "text_sha256": _sha(row["text"]),
        }
        private.append(item)
        safe.append({key: item[key] for key in (
            "case_id", "arm", "primary_stratum", "secondary_tags", "inclusion_probability",
            "paper_id", "attachment_id", "chunk_id", "page_start", "page_end", "chunk_type",
            "evidence_role", "text_sha256", "source_attachment_checksum", "chunk_version",
        )})
        pass_a.append({"case_id": case_id, "text": row["text"]})
    rng.shuffle(pass_a)

    summary = {
        "schema": "evidence-unit-sample-summary-v1",
        "seed": SEED,
        "universe": len(rows),
        "papers": len({row["paper_id"] for row in rows}),
        "attachments": len({row["attachment_id"] for row in rows}),
        "currently_embedded": sum(bool(row["current_embedding"]) for row in rows),
        "not_repeated_boilerplate": sum(row["repeated_boilerplate"] != 1 for row in rows),
        "population_by_type": dict(sorted(n_by_type.items())),
        "probability_allocation": allocation,
        "stress_available": stress_available,
        "sample_n": len(selected),
        "probability_n": sum(arm == "probability" for arm, _, _ in selected),
        "stress_n": sum(arm == "stress" for arm, _, _ in selected),
        "sample_papers": len({row["paper_id"] for _, _, row in selected}),
    }
    for name, payload in (
        ("sample-private.json", private),
        ("sample-manifest.json", safe),
        ("pass-a-blind.json", pass_a),
        ("sample-summary.json", summary),
    ):
        (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    hashes = {name: _file_sha(OUT / name) for name in (
        "sample-private.json", "sample-manifest.json", "pass-a-blind.json", "sample-summary.json"
    )}
    (OUT / "sample-hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(json.dumps(hashes, indent=2))


# Investigator coding frozen from the shuffled, text-only pass-a-blind.json. These positions are
# meaningful only for the pinned sample hash in PASS_A_SAMPLE_SHA256. Keeping the coding here makes
# every judgment reproducible without placing source text in a tracked artifact.
PASS_A_SAMPLE_SHA256 = "18d42df6ab344706e60aa1fb3bf51826a28def0e92fd9ba1ca1ced2912f3b97a"
PASS_A_PROPOSITION_YES = {
    2, 9, 14, 18, 23, 26, 29, 42, 50, 64, 68, 70, 72, 75, 88, 92, 93, 95,
    102, 104, 110, 112, 113, 118, 119, 126, 128, 136, 151, 154, 160, 164,
    170, 173, 179,
}
PASS_A_MEANING_YES = PASS_A_PROPOSITION_YES | {
    6, 7, 20, 22, 28, 31, 36, 41, 47, 48, 51, 55, 57, 67, 71, 73, 76, 77,
    81, 83, 84, 86, 89, 94, 97, 98, 99, 101, 106, 111, 114, 116, 117, 123,
    125, 131, 132, 134, 138, 140, 147, 150, 152, 158, 163, 167, 175,
}
PASS_A_MEANING_AMBIGUOUS = {
    3, 5, 12, 16, 19, 21, 24, 30, 32, 34, 37, 38, 40, 43, 44, 45, 49,
    52, 54, 58, 59, 60, 63, 66, 71, 74, 79, 85, 87, 91, 100, 108, 109,
    120, 121, 122, 124, 127, 135, 137, 139, 144, 145, 149, 153, 165, 169,
    177, 178,
}


def rate_pass_a() -> None:
    path = OUT / "pass-a-blind.json"
    if _file_sha(path) != PASS_A_SAMPLE_SHA256:
        raise RuntimeError("blind sample hash differs from the preregistered sample")
    cases = json.loads(path.read_text(encoding="utf-8"))
    if len(cases) != 180:
        raise RuntimeError(f"expected 180 blind cases, got {len(cases)}")
    ratings: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        proposition = "yes" if index in PASS_A_PROPOSITION_YES else "no"
        if index in PASS_A_MEANING_YES:
            meaningful = "yes"
        elif index in PASS_A_MEANING_AMBIGUOUS:
            meaningful = "ambiguous"
        else:
            meaningful = "no"
        if proposition == "yes":
            missing = []
        elif meaningful == "ambiguous":
            missing = ["unlabeled_value_or_symbol"]
        elif meaningful == "yes":
            missing = ["referent_or_surrounding_context"]
        else:
            missing = ["not_scientific_evidence_as_extracted"]
        ratings.append(
            {
                "case_id": case["case_id"],
                "scientifically_meaningful_as_extracted": meaningful,
                "standalone_proposition_bearing": proposition,
                "missing_context_codes": missing,
            }
        )
    payload = {
        "schema": "evidence-unit-pass-a-ratings-v1",
        "sample_sha256": PASS_A_SAMPLE_SHA256,
        "rubric": {
            "proposition_bearing": (
                "The extracted text identifies what its reported finding, method, or value refers "
                "to without hidden neighboring context; grammatical sentence form is not required."
            ),
            "meaningful_as_extracted": (
                "The visible text conveys scientific content or a scientific structural label; "
                "ambiguous is retained for values/symbols whose scientific role cannot be known blind."
            ),
        },
        "ratings": ratings,
    }
    target = OUT / "pass-a-ratings.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "ratings": len(ratings),
        "proposition_bearing": dict(Counter(x["standalone_proposition_bearing"] for x in ratings)),
        "meaningful": dict(Counter(x["scientifically_meaningful_as_extracted"] for x in ratings)),
        "sha256": _file_sha(target),
    }
    (OUT / "pass-a-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sample", "pass-a-rate"))
    args = parser.parse_args()
    if args.command == "sample":
        sample()
    elif args.command == "pass-a-rate":
        rate_pass_a()


if __name__ == "__main__":
    main()
