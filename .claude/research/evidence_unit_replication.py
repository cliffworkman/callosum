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

import fitz

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
        "short_truncated",
        "heading_body",
        "body_null_unknown_scientific",
        "results_prose",
        "methods_statistics",
        "captions_panels",
        "simple_table",
        "complex_table",
        "isolated_rows_cells",
        "significance_footnotes",
        "multi_column",
        "multi_page_table",
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
        probability = (
            allocation.get(row["chunk_type"], 0) / n_by_type[row["chunk_type"]] if arm == "probability" else None
        )
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
        safe.append(
            {
                key: item[key]
                for key in (
                    "case_id",
                    "arm",
                    "primary_stratum",
                    "secondary_tags",
                    "inclusion_probability",
                    "paper_id",
                    "attachment_id",
                    "chunk_id",
                    "page_start",
                    "page_end",
                    "chunk_type",
                    "evidence_role",
                    "text_sha256",
                    "source_attachment_checksum",
                    "chunk_version",
                )
            }
        )
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
    hashes = {
        name: _file_sha(OUT / name)
        for name in ("sample-private.json", "sample-manifest.json", "pass-a-blind.json", "sample-summary.json")
    }
    (OUT / "sample-hashes.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(json.dumps(hashes, indent=2))


# Investigator coding frozen from the shuffled, text-only pass-a-blind.json. These positions are
# meaningful only for the pinned sample hash in PASS_A_SAMPLE_SHA256. Keeping the coding here makes
# every judgment reproducible without placing source text in a tracked artifact.
PASS_A_SAMPLE_SHA256 = "18d42df6ab344706e60aa1fb3bf51826a28def0e92fd9ba1ca1ced2912f3b97a"
PASS_A_PROPOSITION_YES = {
    2,
    9,
    14,
    18,
    23,
    26,
    29,
    42,
    50,
    64,
    68,
    70,
    72,
    75,
    88,
    92,
    93,
    95,
    102,
    104,
    110,
    112,
    113,
    118,
    119,
    126,
    128,
    136,
    151,
    154,
    160,
    164,
    170,
    173,
    179,
}
PASS_A_MEANING_YES = PASS_A_PROPOSITION_YES | {
    6,
    7,
    20,
    22,
    28,
    31,
    36,
    41,
    47,
    48,
    51,
    55,
    57,
    67,
    71,
    73,
    76,
    77,
    81,
    83,
    84,
    86,
    89,
    94,
    97,
    98,
    99,
    101,
    106,
    111,
    114,
    116,
    117,
    123,
    125,
    131,
    132,
    134,
    138,
    140,
    147,
    150,
    152,
    158,
    163,
    167,
    175,
}
PASS_A_MEANING_AMBIGUOUS = {
    3,
    5,
    12,
    16,
    19,
    21,
    24,
    30,
    32,
    34,
    37,
    38,
    40,
    43,
    44,
    45,
    49,
    52,
    54,
    58,
    59,
    60,
    63,
    66,
    71,
    74,
    79,
    85,
    87,
    91,
    100,
    108,
    109,
    120,
    121,
    122,
    124,
    127,
    135,
    137,
    139,
    144,
    145,
    149,
    153,
    165,
    169,
    177,
    178,
}

# Pass-B investigator coding was made after inspecting DB neighborhoods, stored geometry, the
# reread PyMuPDF hierarchy, and targeted rendered-page checks. It intentionally distinguishes
# proposition recovery from preserving a context-only component (heading/caption/axis label).
PASS_B_CURRENT_RECOVERABLE = {
    # conservative same-column prose reunion
    11,
    22,
    28,
    36,
    76,
    77,
    83,
    86,
    97,
    116,
    147,
    163,
    175,
    176,
    # data-bearing table rows whose labels/context can be associated from stored page geometry
    3,
    16,
    21,
    37,
    52,
    60,
    67,
    79,
    85,
    87,
    91,
    109,
    139,
}
PASS_B_CURRENT_AMBIGUOUS_PDF_RECOVERABLE = {
    # fragmented/complex tables: the values survive, but safe row/column or continuation identity
    # is not explicit in current storage; PDF hierarchy or visual geometry resolves the sampled case
    19,
    30,
    38,
    40,
    54,
    66,
    74,
    100,
    108,
    111,
    124,
    127,
    # multi-column / cross-page prose whose semantic reading order is not emitted order
    6,
    114,
}
PASS_B_CONTEXT_COMPONENT_ONLY = {
    # headings, table/figure captions, column headers, and structural labels that should be linked
    # to evidence but are not themselves a recovered scientific proposition
    7,
    17,
    20,
    31,
    39,
    47,
    48,
    51,
    55,
    57,
    59,
    61,
    73,
    78,
    94,
    98,
    101,
    106,
    117,
    121,
    123,
    131,
    134,
    138,
    150,
    152,
    158,
    167,
}
PASS_B_UNRESOLVED_SCIENTIFIC_FRAGMENT = {
    # equations, unlabeled chart/table fragments, or orphan values for which adding nearby text
    # would still require an unsafe semantic inference in this sample
    5,
    10,
    12,
    24,
    32,
    34,
    43,
    44,
    45,
    49,
    58,
    63,
    71,
    122,
    132,
    135,
    137,
    144,
    145,
    149,
    153,
    165,
    169,
    177,
    178,
}
PASS_B_FALSE_JOIN_HAZARDS: dict[int, list[str]] = {
    5: ["figure_axis_misclassified_as_table", "wrong_caption_or_table_semantics"],
    6: ["cross_page_continuation", "cross_column_neighbor"],
    19: ["wrong_row_or_column"],
    30: ["wrong_row_or_column", "multi_page_table_context"],
    34: ["figure_axis_misclassified_as_table"],
    38: ["wrong_row_or_column", "wrong_table_caption"],
    40: ["wrong_row_or_column"],
    43: ["figure_axis_misclassified_as_table"],
    44: ["figure_axis_misclassified_as_table"],
    45: ["figure_axis_misclassified_as_table"],
    54: ["wrong_row_or_column", "multi_page_table_context"],
    66: ["wrong_row_or_column", "multi_page_table_context"],
    68: ["body_prose_near_table"],
    74: ["wrong_row_or_column"],
    85: ["two_side_by_side_tables"],
    91: ["multi_page_table_context", "wrong_row_or_column"],
    100: ["wrong_row_or_column"],
    104: ["cross_column_neighbor", "cross_page_continuation"],
    108: ["wrong_row_or_column"],
    109: ["wrong_row_or_column", "multiple_nearby_captions"],
    111: ["wrong_row_or_column", "duplicate_interaction_label"],
    114: ["cross_column_neighbor", "emitted_order_reversal"],
    122: ["figure_axis_misclassified_as_table"],
    124: ["wrong_row_or_column"],
    127: ["wrong_row_or_column", "multi_page_table_context"],
    137: ["figure_panel_label_misclassified_as_table"],
    139: ["wrong_row_or_column", "multiple_nearby_tables"],
    144: ["figure_axis_misclassified_as_table"],
    147: ["cross_column_neighbor"],
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


def rate_pass_b() -> None:
    cases = json.loads((OUT / "revealed-context.json").read_text(encoding="utf-8"))
    pass_a_order = json.loads((OUT / "pass-a-blind.json").read_text(encoding="utf-8"))
    by_code = {case["case_id"]: case for case in cases}
    if len(by_code) != 180 or len(pass_a_order) != 180:
        raise RuntimeError("Pass-B inputs must contain the frozen 180-case sample")
    ratings = []
    for index, blind in enumerate(pass_a_order):
        case = by_code[blind["case_id"]]
        proposition = case["pass_a"]["standalone_proposition_bearing"]
        meaningful = case["pass_a"]["scientifically_meaningful_as_extracted"]
        if proposition == "yes":
            current = pdf = "already_proposition_bearing"
            representation = "authoritative_source_text"
        elif index in PASS_B_CURRENT_RECOVERABLE:
            current = pdf = "faithfully_reconstructable"
            representation = "derived_multi_region_evidence_unit"
        elif index in PASS_B_CURRENT_AMBIGUOUS_PDF_RECOVERABLE:
            current = "ambiguous_not_safe_to_activate"
            pdf = "faithfully_reconstructable"
            representation = "derived_multi_region_evidence_unit"
        elif index in PASS_B_CONTEXT_COMPONENT_ONLY:
            current = pdf = "context_component_only"
            representation = "linked_source_component"
        elif index in PASS_B_UNRESOLVED_SCIENTIFIC_FRAGMENT or meaningful == "ambiguous":
            current = pdf = "unresolved_without_semantic_inference"
            representation = "preserve_ambiguity"
        else:
            current = pdf = "not_target_scientific_evidence"
            representation = "exclude_from_evidence_units"
        ratings.append(
            {
                "case_id": case["case_id"],
                "current_storage_recoverability": current,
                "pdf_reread_recoverability": pdf,
                "expected_representation": representation,
                "false_join_hazards": PASS_B_FALSE_JOIN_HAZARDS.get(index, []),
                "pdf_derived_provenance_confirmed": case["pdf_status"] == "read",
            }
        )
    payload = {
        "schema": "evidence-unit-pass-b-ratings-v1",
        "pass_a_ratings_sha256": "acce3518863d44fb71706a050339392fc0c97e33c7f54e60af8d98c94a37253b",
        "ratings": ratings,
    }
    target = OUT / "pass-b-ratings.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {
        "ratings": len(ratings),
        "current_storage_recoverability": dict(Counter(x["current_storage_recoverability"] for x in ratings)),
        "pdf_reread_recoverability": dict(Counter(x["pdf_reread_recoverability"] for x in ratings)),
        "cases_with_false_join_hazard": sum(bool(x["false_join_hazards"]) for x in ratings),
        "false_join_hazards": dict(Counter(h for x in ratings for h in x["false_join_hazards"])),
        "sha256": _file_sha(target),
    }
    (OUT / "pass-b-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def _pdf_block_text(block: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    lines: list[str] = []
    exported_spans: list[dict[str, Any]] = []
    for line_number, line in enumerate(block.get("lines", [])):
        parts: list[str] = []
        for span_number, span in enumerate(line.get("spans", [])):
            text = str(span.get("text", ""))
            parts.append(text)
            if text.strip():
                exported_spans.append(
                    {
                        "line": line_number,
                        "span": span_number,
                        "text": text,
                        "bbox": [float(v) for v in span.get("bbox", (0, 0, 0, 0))],
                        "font": span.get("font"),
                        "size": span.get("size"),
                        "flags": span.get("flags"),
                    }
                )
        joined = "".join(parts).strip()
        if joined:
            lines.append(joined)
    return "\n".join(lines).strip(), exported_spans


def _safe_pdf_path(case: dict[str, Any]) -> Path | None:
    for value in (case.get("resolved_path"), case.get("original_path")):
        if not value:
            continue
        path = Path(value)
        if not path.is_absolute():
            path = ROOT / path
        if path.is_file():
            return path
    return None


def reveal_context() -> None:
    """Reveal identifiers/context only after the committed Pass-A blindness boundary."""
    private = json.loads((OUT / "sample-private.json").read_text(encoding="utf-8"))
    rating_payload = json.loads((OUT / "pass-a-ratings.json").read_text(encoding="utf-8"))
    ratings = {item["case_id"]: item for item in rating_payload["ratings"]}
    if _file_sha(OUT / "pass-a-ratings.json") != "acce3518863d44fb71706a050339392fc0c97e33c7f54e60af8d98c94a37253b":
        raise RuntimeError("Pass-A ratings changed after freeze")

    with _connect() as conn:
        all_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT id chunk_id,attachment_id,paper_id,page_start,page_end,text,section,bbox_json "
                "FROM chunks ORDER BY attachment_id,page_start,id"
            ).fetchall()
        ]
    by_attachment: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        row["bbox_json"] = _spans(row["bbox_json"])
        by_attachment[int(row["attachment_id"])].append(row)
    position = {
        int(row["chunk_id"]): (attachment_id, index)
        for attachment_id, rows in by_attachment.items()
        for index, row in enumerate(rows)
    }

    documents: dict[str, fitz.Document] = {}
    cases: list[dict[str, Any]] = []
    try:
        for case in private:
            attachment_id, index = position[int(case["chunk_id"])]
            ordered = by_attachment[attachment_id]
            db_neighbors = []
            for offset in (-3, -2, -1, 1, 2, 3):
                candidate_index = index + offset
                if 0 <= candidate_index < len(ordered):
                    row = ordered[candidate_index]
                    db_neighbors.append(
                        {
                            "offset": offset,
                            "chunk_id": row["chunk_id"],
                            "page": row["page_start"],
                            "section": row["section"],
                            "text": row["text"],
                            "bbox_json": row["bbox_json"],
                        }
                    )

            pdf_path = _safe_pdf_path(case)
            page_export: dict[str, Any] | None = None
            pdf_status = "missing"
            if pdf_path is not None:
                key = str(pdf_path)
                if key not in documents:
                    documents[key] = fitz.open(pdf_path)
                document = documents[key]
                page_index = int(case["page_start"]) - 1
                if 0 <= page_index < document.page_count:
                    page = document[page_index]
                    text_dict = page.get_text("dict", sort=True)
                    pdf_blocks = []
                    for block_number, block in enumerate(text_dict.get("blocks", [])):
                        if block.get("type") != 0:
                            continue
                        block_text, spans = _pdf_block_text(block)
                        if block_text:
                            pdf_blocks.append(
                                {
                                    "block": block_number,
                                    "bbox": [float(v) for v in block.get("bbox", (0, 0, 0, 0))],
                                    "text": block_text,
                                    "normalized_text": " ".join(block_text.split()),
                                    "spans": spans,
                                }
                            )
                    target_blocks = sorted(
                        {
                            int(span["block"])
                            for span in case.get("bbox_json", [])
                            if isinstance(span, dict) and "block" in span
                        }
                    )
                    page_export = {
                        "page": int(case["page_start"]),
                        "width": float(page.rect.width),
                        "height": float(page.rect.height),
                        "target_block_numbers": target_blocks,
                        "blocks": pdf_blocks,
                    }
                    pdf_status = "read"
            cases.append(
                {
                    **case,
                    "pass_a": ratings[case["case_id"]],
                    "db_neighbors": db_neighbors,
                    "pdf_status": pdf_status,
                    "pdf_page": page_export,
                }
            )
    finally:
        for document in documents.values():
            document.close()

    target = OUT / "revealed-context.json"
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    status = Counter(case["pdf_status"] for case in cases)
    match = Counter()
    for case in cases:
        page = case["pdf_page"] or {}
        targets = set(page.get("target_block_numbers", []))
        blocks = [b for b in page.get("blocks", []) if b["block"] in targets]
        exact = any(b["normalized_text"] == case["text"] for b in blocks)
        any_exact = any(b["normalized_text"] == case["text"] for b in page.get("blocks", []))
        match["target_block_exact" if exact else "target_block_not_exact"] += 1
        if any_exact:
            match["page_any_exact"] += 1
    summary = {
        "cases": len(cases),
        "pdf_status": dict(status),
        "block_match": dict(match),
        "sha256": _file_sha(target),
    }
    (OUT / "revealed-context-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def _union_box(spans: list[dict[str, Any]]) -> fitz.Rect | None:
    if not spans:
        return None
    try:
        return fitz.Rect(
            min(float(span["x0"]) for span in spans),
            min(float(span["y0"]) for span in spans),
            max(float(span["x1"]) for span in spans),
            max(float(span["y1"]) for span in spans),
        )
    except (KeyError, TypeError, ValueError):
        return None


def measure_reread() -> None:
    """Measure information regained by deterministic PDF reread; makes no production writes."""
    cases = json.loads((OUT / "revealed-context.json").read_text(encoding="utf-8"))
    with _connect() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT id chunk_id,attachment_id,page_start,text,bbox_json FROM chunks ORDER BY id"
            ).fetchall()
        ]
    page_chunks: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        row["bbox_json"] = _spans(row["bbox_json"])
        page_chunks[(int(row["attachment_id"]), int(row["page_start"]))].append(row)

    page_specs: dict[tuple[int, int], dict[str, Any]] = {}
    for case in cases:
        page_specs[(int(case["attachment_id"]), int(case["page_start"]))] = case
    page_results: dict[tuple[int, int], dict[str, Any]] = {}
    documents: dict[str, fitz.Document] = {}
    try:
        for key, exemplar in page_specs.items():
            path = _safe_pdf_path(exemplar)
            if path is None:
                page_results[key] = {"status": "missing"}
                continue
            path_key = str(path)
            if path_key not in documents:
                documents[path_key] = fitz.open(path)
            page = documents[path_key][key[1] - 1]
            text_dict = page.get_text("dict", sort=True)
            blocks = []
            for block_number, block in enumerate(text_dict.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                text_value, spans = _pdf_block_text(block)
                if text_value.strip():
                    blocks.append(
                        {
                            "block": block_number,
                            "bbox": [float(v) for v in block.get("bbox", (0, 0, 0, 0))],
                            "text": text_value,
                            "normalized_text": " ".join(text_value.split()),
                            "spans": spans,
                        }
                    )
            stored = page_chunks.get(key, [])
            stored_texts = Counter(" ".join((row["text"] or "").split()) for row in stored)
            unmatched = []
            remaining = stored_texts.copy()
            for block in blocks:
                normalized = block["normalized_text"]
                if remaining[normalized] > 0:
                    remaining[normalized] -= 1
                else:
                    unmatched.append(block)

            tables = []
            try:
                for table in page.find_tables().tables:
                    extracted = table.extract()
                    tables.append(
                        {
                            "bbox": [float(v) for v in table.bbox],
                            "row_count": int(table.row_count),
                            "col_count": int(table.col_count),
                            "extract": extracted,
                        }
                    )
            except (AttributeError, RuntimeError, ValueError) as exc:
                tables.append({"error": f"{type(exc).__name__}: {exc}"})

            block_sequence = []
            for row in stored:
                numbers = sorted({int(span["block"]) for span in row["bbox_json"] if "block" in span})
                if numbers:
                    block_sequence.append((int(row["chunk_id"]), numbers[0]))
            inversions = sum(
                left[1] > right[1] for left, right in zip(block_sequence, block_sequence[1:], strict=False)
            )
            page_results[key] = {
                "status": "read",
                "width": float(page.rect.width),
                "height": float(page.rect.height),
                "pdf_text_blocks": len(blocks),
                "stored_chunks": len(stored),
                "unmatched_pdf_blocks": unmatched,
                "stored_id_block_inversions": inversions,
                "tables": tables,
            }
    finally:
        for document in documents.values():
            document.close()

    case_results = []
    for case in cases:
        key = (int(case["attachment_id"]), int(case["page_start"]))
        page_result = page_results[key]
        target_box = _union_box(case.get("bbox_json", []))
        intersecting = []
        if target_box is not None:
            for table_index, table in enumerate(page_result.get("tables", [])):
                if "bbox" in table and fitz.Rect(table["bbox"]).intersects(target_box):
                    flat = " ".join(str(cell or "") for row in table.get("extract", []) for cell in (row or []))
                    intersecting.append(
                        {
                            "table_index": table_index,
                            "row_count": table["row_count"],
                            "col_count": table["col_count"],
                            "target_text_in_extract": " ".join(case["text"].split()) in " ".join(flat.split()),
                        }
                    )
        case_results.append(
            {
                "case_id": case["case_id"],
                "intersecting_tables": intersecting,
                "pdf_unmatched_block_count": len(page_result.get("unmatched_pdf_blocks", [])),
                "page_id_block_inversions": page_result.get("stored_id_block_inversions"),
            }
        )

    serial_pages = {f"{attachment_id}:{page}": value for (attachment_id, page), value in page_results.items()}
    payload = {"schema": "evidence-unit-reread-measurement-v1", "pages": serial_pages, "cases": case_results}
    target = OUT / "reread-measurements.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    table_cases = [case for case in case_results if case["intersecting_tables"]]
    summary = {
        "sample_pages": len(page_results),
        "pages_read": sum(value.get("status") == "read" for value in page_results.values()),
        "pages_with_unmatched_pdf_blocks": sum(
            bool(value.get("unmatched_pdf_blocks")) for value in page_results.values()
        ),
        "unmatched_pdf_blocks": sum(len(value.get("unmatched_pdf_blocks", [])) for value in page_results.values()),
        "pages_with_id_block_inversions": sum(
            bool(value.get("stored_id_block_inversions")) for value in page_results.values()
        ),
        "id_block_inversions": sum(value.get("stored_id_block_inversions", 0) for value in page_results.values()),
        "pages_with_detected_tables": sum(
            any("bbox" in t for t in value.get("tables", [])) for value in page_results.values()
        ),
        "detected_tables": sum(sum("bbox" in t for t in value.get("tables", [])) for value in page_results.values()),
        "sample_cases_intersecting_detected_table": len(table_cases),
        "sha256": _file_sha(target),
    }
    (OUT / "reread-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("sample", "pass-a-rate", "pass-b-rate", "reveal-context", "measure-reread"))
    args = parser.parse_args()
    if args.command == "sample":
        sample()
    elif args.command == "pass-a-rate":
        rate_pass_a()
    elif args.command == "pass-b-rate":
        rate_pass_b()
    elif args.command == "reveal-context":
        reveal_context()
    elif args.command == "measure-reread":
        measure_reread()


if __name__ == "__main__":
    main()
