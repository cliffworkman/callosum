"""Production semantics unchanged; strict FORMAT diagnostics are independently recorded."""

import importlib.util
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from ..contracts import ContractError
from ..hashing import file_hash, read_json, text_hash

SCHEMA_FILE = Path(__file__).parents[1] / "specifications" / "r_control_format_v0.json"
PLANNER_SOURCE = Path(__file__).resolve().parents[3] / "app/backend/summarization/query_planner.py"


def _load_pure_planner():
    # Parent summarization.__init__ imports the model runtime. Load the exact pure source instead.
    name = "_callosum_070_frozen_production_planner"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, PLANNER_SOURCE)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        exec(compile(PLANNER_SOURCE.read_bytes(), str(PLANNER_SOURCE), "exec"), module.__dict__)
    return sys.modules[name]


planner = _load_pure_planner()
LOADED_PLANNER_SHA256 = file_hash(PLANNER_SOURCE)


def strict_format(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    try:
        payload = json.loads(
            raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError())
        )
    except (ValueError, TypeError):
        return {"whole_response_json_valid": False, "schema_valid": False}
    ok = isinstance(payload, dict) and set(payload) == {"scope", "facets"}
    ok = ok and payload["scope"] in ("narrow", "broad") and isinstance(payload["facets"], list)
    if ok:
        ok = all(
            isinstance(f, dict)
            and set(f) == {"label", "query"}
            and isinstance(f["label"], str)
            and isinstance(f["query"], str)
            for f in payload["facets"]
        )
    return {"whole_response_json_valid": True, "schema_valid": bool(ok)}


def transform_trace(payload):
    """Diagnostic replay only. The actual plan is always produced by production helpers."""
    events = []
    if not isinstance(payload, dict) or str(payload.get("scope", "")).strip().lower() != "broad":
        return events
    facets = payload.get("facets")
    if not isinstance(facets, list):
        return events
    seen = set()
    accepted = 0
    for index, item in enumerate(facets):
        reason = "KEPT"
        kept = False
        if accepted >= planner.MAX_FACETS:
            reason = "MAX_FACETS_EXCEEDED"
        elif not isinstance(item, dict):
            reason = "NON_OBJECT_FACET"
        else:
            label = str(item.get("label", "")).strip()[: planner._MAX_LABEL_CHARS]
            query = str(item.get("query", "")).strip()[: planner._MAX_QUERY_CHARS]
            norm = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
            if not label or not query or not norm:
                reason = "EMPTY_FACET"
            elif norm in seen:
                reason = "DUPLICATE_QUERY"
            else:
                seen.add(norm)
                accepted += 1
                kept = True
                if label != item.get("label") or query != item.get("query"):
                    reason = "PRODUCTION_TRIM_COERCE_OR_CHARACTER_CAP"
        events.append(
            {
                "decision": "KEEP" if kept else "DISCARD",
                "reason_code": reason,
                "inputs": {"raw_facet_index": index},
                "kept": kept,
            }
        )
    return events


class RControl:
    package_id = "R_CONTROL"

    def identity_manifest(self):
        if file_hash(PLANNER_SOURCE) != LOADED_PLANNER_SHA256:
            raise ContractError("PRODUCTION_PLANNER_CHANGED_AFTER_LOAD")
        return {
            "package_id": self.package_id,
            "status": "IMPLEMENTED",
            "planner_code_sha256": file_hash(planner.__file__),
            "adapter_code_sha256": file_hash(__file__),
            "prompt_version": planner.PLANNER_PROMPT_VERSION,
            "empty_question_prompt_sha256": text_hash(planner._planner_prompt("")),
            "schema_sha256": file_hash(SCHEMA_FILE),
            "config": {
                "min_facets": planner.MIN_FACETS,
                "max_facets": planner.MAX_FACETS,
                "label_chars": planner._MAX_LABEL_CHARS,
                "query_chars": planner._MAX_QUERY_CHARS,
            },
            "contract": "production breadth/prompt/tolerant parser/fallback; external referents excluded",
            "format_mechanism": "shared A1 enforcement; diagnostics never select the effective plan",
        }

    def prepare(self, task):
        if task.kind != "request_planning":
            raise ContractError("UNSUPPORTED_TASK_PACKAGE_COMBINATION")
        return {
            "invoke": planner.classify_breadth(task.text),
            "prompt": planner._planner_prompt(task.text),
            "schema": read_json(SCHEMA_FILE)["json_schema"]["schema"],
            "schema_name": "calibration",
        }

    def interpret(self, task, raw, *, error=None):
        # Use precisely the historical transformation, never gate it on strict diagnostics.
        payload = planner._extract_json_object(raw)
        route = planner.classify_breadth(task.text)
        plan = planner.NARROW if error or not route else planner._plan_from_payload(payload)
        if not route:
            state = "DETERMINISTIC_NARROW_NO_CALL"
        elif error:
            state = "PROVIDER_FAILURE_TO_NARROW"
        elif plan.is_broad:
            state = "BROAD"
        elif isinstance(payload, dict) and str(payload.get("scope", "")).strip().lower() == "narrow":
            state = "MODEL_NARROW"
        else:
            state = "PARSER_OR_VALIDATOR_FALLBACK_TO_NARROW"
        fallback = state in {"PROVIDER_FAILURE_TO_NARROW", "PARSER_OR_VALIDATOR_FALLBACK_TO_NARROW"}
        decisions = transform_trace(payload)
        if fallback:
            decisions.append(
                {
                    "decision": "PRODUCTION_FALLBACK",
                    "reason_code": state,
                    "inputs": {"raw_output_sha256": text_hash(raw)},
                    "kept": False,
                }
            )
        return {
            "effective_representation": asdict(plan),
            "format": strict_format(raw),
            "parser_result": payload,
            "state": state,
            "fallback": fallback,
            "decisions": decisions,
        }
