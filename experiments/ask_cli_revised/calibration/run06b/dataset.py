"""Construct the Run 0.6b calibration dataset entirely from frozen baseline artifacts.

No retrieval, no decomposition, no context growth, no new spans. Two strata, kept distinct:

  Stratum 1 (``select_evidence_span``): every ``e#`` sub-span shown to the old select_evidence stage,
      one unit each, context = its containing frozen chunk's full text.
  Stratum 2 (``pre_selection_chunk``): every frozen ``08`` chunk that never hosted an ``e#`` span (a
      context-gate discard or an H1a role reject), one unit each (the whole chunk), shown span-alone.

Code owns every id, provenance field, and the exact evidence anchor. Qwen never sees any of this file's
output structure — only the exact span text and its frozen context are handed to the primitives.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

from app.backend.pdf_processing.extraction import canonical_text_contains
from experiments.ask_cli_revised.calibration.structured_output import extract_json

# ---- named regression specimens (the DEV inspection set) --------------------------------------------
# Keyed by chunk_id, from the frozen-artifact map. A unit inherits a specimen label (and DEV split) when
# its containing chunk id is listed here; the RTPJ heading vs. its ignored siblings are split by span id.
_SPECIMEN_BY_CHUNK: dict[int, str] = {
    34974: "amygdala / just-world / empathy (discarded chunk)",
    35068: "explicit negative attitudes",
    34984: "implicit bias",
    33601: "implicit bias",
    23557: "author address / correspondence",
    23201: "author address / correspondence",
    46071: "reference-list fragment (reached form_claim, no claim)",
    26503: "table heading fragment (reached form_claim, no claim)",
    30770: "warmth / competence",
    30784: "warmth / competence (reference)",
    14422: "WEIRD / cross-cultural (nearest to Hadza; Hadza absent)",
    30603: "reference entry (H1a bibliographic reject)",
    23192: "running footer (H1a structural reject)",
    23171: "running footer (H1a structural reject)",
    22869: "table-cell debris (H1a structural reject)",
}
RTPJ_CHUNK_ID = 26831

# Requested specimens confirmed ABSENT from the frozen candidate/span set (never fabricate via retrieval).
ABSENT_SPECIMENS = (
    "Dictator Game behavior",
    "Hadza (explicit)",
    "IAT / Implicit Association Test (literal term)",
)

_EXCERPT_RE = re.compile(r"\[(e\d+)\]\s*(.*?)(?=\n\s*\[e\d+\]|\Z)", re.DOTALL)
_SPAN_IDS_RE = re.compile(r"\[span_ids\]\s*(\[.*\])")
_COUNT_RE = re.compile(r"selected\s+(\d+)\s+exact source excerpts")


def _load_json(root: Path, name: str) -> object:
    return json.loads((root / name).read_text(encoding="utf-8"))


def _load_jsonl(root: Path, name: str) -> list[dict]:
    return [json.loads(line) for line in (root / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def _subquestion_text_map(decomposition: dict) -> dict[str, str]:
    return {sq["text"].strip(): sq["subquestion_id"] for sq in decomposition.get("subquestions", [])}


def _parse_excerpts(prompt_text: str) -> list[tuple[str, str]]:
    """Return ordered ``(span_id, exact_text)`` pairs from a select_evidence prompt's excerpt block."""
    marker = "Candidate excerpts:"
    idx = prompt_text.rfind(marker)
    if idx < 0:
        return []
    block = prompt_text[idx + len(marker) :]
    out: list[tuple[str, str]] = []
    for span_id, text in _EXCERPT_RE.findall(block):
        cleaned = text.strip()
        if cleaned:
            out.append((span_id, cleaned))
    return out


def _subq_text_of(input_text: str) -> str | None:
    for line in input_text.splitlines():
        if line.startswith("[subq]"):
            return line[len("[subq]") :].strip()
    return None


def _old_model_selected_ids(raw_output: str) -> list[str] | None:
    """The span_ids the model's own output actually named — the FIRST balanced JSON object carrying a
    ``span_ids`` list. None means the model emitted no parseable selection (prose/garbage/truncation)."""
    parsed = extract_json(raw_output or "")
    if isinstance(parsed, dict) and isinstance(parsed.get("span_ids"), list):
        return [str(x) for x in parsed["span_ids"]]
    return None


def _downstream_count(consequence: str) -> int | None:
    m = _COUNT_RE.search(consequence or "")
    return int(m.group(1)) if m else None


_FORMCLAIM_QUOTE_RE = re.compile(r"\[quote\]\s*(.*)", re.DOTALL)
_FORMCLAIM_CHUNK_RE = re.compile(r"\[chunk\s+(\d+)\]")


def _effective_and_formclaim(qwen_calls: list[dict], propositions: list[dict]) -> tuple[set, dict]:
    """Which spans were EFFECTIVELY selected (reached form_claim), keyed by (chunk_id, canonical span text).

    The per-call ``e#`` ids are call-local (the same id can name different spans in different calls, and one
    chunk can be offered in two calls), so effective-selection is keyed by the span's own exact TEXT within
    its chunk — read from the frozen ``form_claim`` calls' ``[quote]``/``[chunk N]`` fields (the authority on
    what actually reached claim formation) and cross-checked against the sealed propositions.
    """
    effective: set[tuple[int, str]] = set()
    formclaim: dict[tuple[int, str], dict] = {}
    claimed_texts = {_canon(str(p.get("quote", ""))) for p in propositions}
    for call in qwen_calls:
        if call.get("task") != "form_claim":
            continue
        chunk_m = _FORMCLAIM_CHUNK_RE.search(call.get("prompt_text", ""))
        quote_m = _FORMCLAIM_QUOTE_RE.search(call.get("input_text", ""))
        if not chunk_m or not quote_m:
            continue
        chunk_id = int(chunk_m.group(1))
        quote_canon = _canon(quote_m.group(1))
        key = (chunk_id, quote_canon)
        effective.add(key)
        claim_formed = bool(call.get("validation_ok")) and quote_canon in claimed_texts
        claim_text = None
        if claim_formed:
            claim_text = next(
                (p.get("proposition_text") for p in propositions if _canon(str(p.get("quote", ""))) == quote_canon),
                None,
            )
        formclaim[key] = {"status": "claim_formed" if claim_formed else "no_claim", "claim": claim_text}
    return effective, formclaim


def _canon(text: str) -> str:
    """Canonical form for span-text equality: collapse whitespace + lowercase (matches the embedding text
    normalization and the containment helper's own whitespace/case handling)."""
    return " ".join((text or "").split()).lower()


def _decision_reason_by_chunk(decisions: list[dict]) -> dict[int, str]:
    """First recorded disposition reason_code per chunk (context-gate discard / H1a reject)."""
    out: dict[int, str] = {}
    for d in decisions:
        info = d.get("inputs", {})
        cid = info.get("chunk_id")
        if cid is None or "span_id" in info:
            continue
        out.setdefault(int(cid), d.get("reason_code", ""))
    return out


def _packet_chunk_index(packets: list[dict]) -> dict[int, dict]:
    """chunk_id -> a merged frozen record for that chunk (text/role/type/paper + packet appearances)."""
    index: dict[int, dict] = {}
    for pk in packets:
        for c in pk["chunks"]:
            cid = int(c["chunk_id"])
            rec = index.setdefault(
                cid,
                {
                    "chunk_id": cid,
                    "paper_id": int(pk["paper_id"]),
                    "text": c["text"],
                    "section": c.get("section"),
                    "chunk_type": c.get("chunk_type"),
                    "evidence_role": c.get("evidence_role"),
                    "appearances": [],
                },
            )
            rec["appearances"].append(
                {
                    "subquestion_id": pk["subquestion_id"],
                    "origin": pk["origin"],
                    "retrieval_anchor_chunk_id": int(pk["retrieval_anchor_chunk_id"]),
                    "retrieval_score": pk.get("retrieval_score"),
                    "discarded": bool(pk["discarded"]),
                }
            )
    return index


def _find_containing_chunk(span_text: str, chunk_index: dict[int, dict], prefer_subq: str | None) -> int | None:
    """The frozen chunk whose text canonically contains this exact span. Prefer a chunk that appears under
    the call's subquestion; fall back to any containing chunk. None => FROZEN_EXTRACTION_MISMATCH."""
    matches = [
        cid for cid, rec in chunk_index.items() if canonical_text_contains(needle=span_text, haystack=rec["text"])
    ]
    if not matches:
        return None
    if prefer_subq is not None:
        preferred = [
            cid for cid in matches if any(ap["subquestion_id"] == prefer_subq for ap in chunk_index[cid]["appearances"])
        ]
        if preferred:
            # Shortest containing chunk = tightest local context (a heading's own chunk over a huge sibling).
            return min(preferred, key=lambda cid: len(chunk_index[cid]["text"]))
    return min(matches, key=lambda cid: len(chunk_index[cid]["text"]))


def _specimen_for(chunk_id: int | None, span_id: str | None) -> str | None:
    if chunk_id is None:
        return None
    if chunk_id == RTPJ_CHUNK_ID:
        return "ASD/RTPJ heading (selected)" if span_id == "e1" else "ASD/RTPJ substantive sibling (ignored)"
    return _SPECIMEN_BY_CHUNK.get(int(chunk_id))


def build_dataset(baseline_dir: Path) -> dict:
    """Build and return the frozen Run 0.6b dataset (units + a content hash + provenance summary)."""
    root = Path(baseline_dir)
    decomposition = _load_json(root, "01_decomposition.json")
    packets = _load_jsonl(root, "08_evidence_packets.jsonl")
    propositions = _load_jsonl(root, "09_propositions.jsonl")
    decisions = _load_jsonl(root, "decisions.jsonl")
    qwen_calls = _load_jsonl(root, "qwen_calls.jsonl")

    subq_map = _subquestion_text_map(decomposition)
    chunk_index = _packet_chunk_index(packets)
    effective_set, formclaim_by_key = _effective_and_formclaim(qwen_calls, propositions)
    reason_by_chunk = _decision_reason_by_chunk(decisions)

    select_calls = [r for r in qwen_calls if r.get("task") == "select_evidence"]

    units: list[dict] = []
    hosting_chunks: set[int] = set()

    # ---- Stratum 1: e# spans shown to select_evidence -------------------------------------------------
    for call_index, call in enumerate(select_calls):
        subq_text = _subq_text_of(call.get("input_text", ""))
        subq_id = subq_map.get(subq_text.strip()) if subq_text else None
        offered_ids = _offered_ids(call.get("input_text", ""))
        model_selected = _old_model_selected_ids(call.get("raw_output", ""))
        fallback_used = bool(call.get("deterministic_fallback_used", False))
        call_failure = call.get("failure_reason")
        excerpts = _parse_excerpts(call.get("prompt_text", ""))
        for span_id, span_text in excerpts:
            containing = _find_containing_chunk(span_text, chunk_index, subq_id)
            if containing is not None:
                hosting_chunks.add(containing)
            rec = chunk_index.get(containing) if containing is not None else None
            key = (containing, _canon(span_text)) if containing is not None else None
            fc = formclaim_by_key.get(key) if key is not None else None
            effective = key in effective_set if key is not None else False
            units.append(
                {
                    "stratum": "select_evidence_span",
                    "subquestion_id": subq_id,
                    "old_select_evidence_call_index": call_index,
                    "local_span_id": span_id,
                    "offered_span_ids": offered_ids,
                    "exact_span_text": span_text,
                    "containing_chunk_id": containing,
                    "paper_id": rec["paper_id"] if rec else None,
                    "chunk_type": rec["chunk_type"] if rec else None,
                    "evidence_role": rec["evidence_role"] if rec else None,
                    "section": rec["section"] if rec else None,
                    "context_text": rec["text"] if rec else "",
                    "context_available": rec is not None,
                    "context_is_containing_chunk": True,
                    "old_model_selected": bool(model_selected) and span_id in (model_selected or []),
                    "old_effective_selected": effective,
                    "old_fallback_used": fallback_used,
                    "old_call_failure_reason": call_failure,
                    "old_form_claim_status": (fc or {}).get("status")
                    if fc
                    else ("reached_no_claim" if effective else "not_reached"),
                    "old_form_claim_text": (fc or {}).get("claim") if fc else None,
                    "old_verifier": _old_verifier_for(containing, span_id, root),
                    "old_select_evidence_status": "selected" if effective else "offered_not_selected",
                    "span_note": None if containing is not None else "FROZEN_EXTRACTION_MISMATCH",
                    "regression_specimen": _specimen_for(containing, span_id),
                }
            )

    # ---- Stratum 2: frozen chunks that never hosted an e# span ---------------------------------------
    for cid in sorted(chunk_index):
        if cid in hosting_chunks:
            continue
        rec = chunk_index[cid]
        units.append(
            {
                "stratum": "pre_selection_chunk",
                "subquestion_id": rec["appearances"][0]["subquestion_id"] if rec["appearances"] else None,
                "old_select_evidence_call_index": None,
                "local_span_id": None,
                "offered_span_ids": None,
                "exact_span_text": rec["text"],
                "containing_chunk_id": cid,
                "paper_id": rec["paper_id"],
                "chunk_type": rec["chunk_type"],
                "evidence_role": rec["evidence_role"],
                "section": rec["section"],
                "context_text": "",
                "context_available": False,
                "context_is_containing_chunk": True,
                "old_model_selected": False,
                "old_effective_selected": False,
                "old_fallback_used": None,
                "old_call_failure_reason": None,
                "old_form_claim_status": "not_reached",
                "old_form_claim_text": None,
                "old_verifier": None,
                "old_select_evidence_status": "not_reached",
                "old_reason_code": reason_by_chunk.get(cid),
                "packet_appearances": rec["appearances"],
                "span_note": None,
                "regression_specimen": _specimen_for(cid, None),
            }
        )

    _assign_ids_dedup_split(units)
    payload = {
        "baseline_run_dir": str(root),
        "counts": _counts(units),
        "absent_specimens": list(ABSENT_SPECIMENS),
        "units": units,
    }
    payload["dataset_hash"] = dataset_hash(units)
    return payload


def _offered_ids(input_text: str) -> list[str] | None:
    m = _SPAN_IDS_RE.search(input_text or "")
    if not m:
        return None
    try:
        value = ast.literal_eval(m.group(1))
        return [str(x) for x in value] if isinstance(value, list) else None
    except (ValueError, SyntaxError):
        return None


def _old_verifier_for(chunk_id: int | None, span_id: str | None, root: Path) -> dict | None:
    """The frozen verifier row for this span, if one exists (only the RTPJ span does)."""
    if chunk_id is None:
        return None
    for row in _load_jsonl(root, "10_verification.jsonl"):
        if int(row.get("evidence_anchor_chunk_id", -1)) == int(chunk_id):
            return {
                "retrieval": row.get("retrieval"),
                "quote": row.get("quote"),
                "support": row.get("support"),
                "contradiction": row.get("contradiction"),
                "status": row.get("status"),
                "coordinate_precision": row.get("coordinate_precision"),
            }
    return None


def _assign_ids_dedup_split(units: list[dict]) -> None:
    """Assign stable dataset_instance_ids, dedup groups (byte-identical span+context+provenance), and the
    DEV/EVAL split (DEV = a named regression specimen). Inference runs on representatives; results fan out."""
    groups: dict[str, str] = {}
    for i, u in enumerate(units):
        u["dataset_instance_id"] = f"d{i:04d}"
        u["split"] = "dev" if u.get("regression_specimen") else "eval"
        key = hashlib.sha256(
            json.dumps(
                [u["exact_span_text"], u["context_text"], u["containing_chunk_id"], u["local_span_id"]],
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        group_id = groups.setdefault(key, u["dataset_instance_id"])
        u["duplicate_group_id"] = group_id
        u["is_group_representative"] = group_id == u["dataset_instance_id"]
    multiplicity: dict[str, int] = {}
    for u in units:
        multiplicity[u["duplicate_group_id"]] = multiplicity.get(u["duplicate_group_id"], 0) + 1
    for u in units:
        u["multiplicity"] = multiplicity[u["duplicate_group_id"]]


def _counts(units: list[dict]) -> dict:
    def by(pred) -> int:
        return sum(1 for u in units if pred(u))

    return {
        "total_units": len(units),
        "stratum_1_spans": by(lambda u: u["stratum"] == "select_evidence_span"),
        "stratum_2_chunks": by(lambda u: u["stratum"] == "pre_selection_chunk"),
        "unique_inference_representatives": by(lambda u: u["is_group_representative"]),
        "dev_units": by(lambda u: u["split"] == "dev"),
        "eval_units": by(lambda u: u["split"] == "eval"),
        "frozen_extraction_mismatch": by(lambda u: u.get("span_note") == "FROZEN_EXTRACTION_MISMATCH"),
        "old_effective_selected": by(lambda u: u.get("old_effective_selected")),
    }


def dataset_hash(units: list[dict]) -> str:
    """Content hash over the load-bearing, order-stable projection of every unit (frozen before inference)."""
    projection = [
        {
            "dataset_instance_id": u["dataset_instance_id"],
            "stratum": u["stratum"],
            "exact_span_text": u["exact_span_text"],
            "context_text": u["context_text"],
            "containing_chunk_id": u["containing_chunk_id"],
            "local_span_id": u["local_span_id"],
            "paper_id": u["paper_id"],
            "evidence_role": u["evidence_role"],
        }
        for u in units
    ]
    canonical = json.dumps(projection, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
