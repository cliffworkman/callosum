"""Population inventory for a proposed real-premise NLI self-entailment evaluation (2026-09-28 authorization).

**No inference call is made by this module.** Its job is to establish, offline, how many genuinely distinct
real production NLI premises exist anywhere under `C:\\Users\\cliff\\callosum-data` -- i.e. premises
reconstructable exactly as `overview_guards.nli_pair` builds them (`" ".join(units[i]["passage"] for i in
proposal["unit_ids"])`), from a record that actually went through `overview_guards.screen_proposals` (fingerprint:
the JSON key `"screen_version"`).

**Population-inclusion rule (fixed before counting, not adjusted after):** a source file is eligible only if it
carries `screen_version` (proof its proposals were built and scored through the real `overview_guards`/`overview.py`
pipeline) and its unit texts can be resolved to real, saved passage strings with verified provenance (either
directly, or -- for `diag_s_unbounded`, which omits its own units array -- by cross-referencing every cited
unit id against a sibling record proven to share the same `question_hash`/`contract_sha256` and to contain
every one of those unit ids).

A recursive `grep -rl "screen_version" callosum-data --include=*.json` (excluding `ab-backend-2026-09-26/runA/`,
the OLD packaged-app backend -- confirmed by direct inspection to use a completely different module,
`app/backend/summarization/overview.py`, with no `unit_ids`/`nli_pair` shape at all, not `experiments/
ask_cli_revised/overview_guards.py`) found exactly four files. `child_answer_diag/`/`child_evidence_diag/`
(same 2026-09-26 session, a different per-child-answer experiment) were inspected directly and confirmed to
carry no `screen_version` key and no `unit_ids`-cited-proposal shape at all -- excluded, not silently skipped.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

DATA_ROOT = Path(r"C:\Users\cliff\callosum-data")
CONTRACT_DIRECTED_RUNS = DATA_ROOT / "contract-directed-slice" / "runs"
AB_BACKEND = DATA_ROOT / "ab-backend-2026-09-26"

NLI_MODEL = "cross-encoder/nli-MiniLM2-L6-H768"
NLI_REVISION = "b95119ce93d3e065de6214e38cd4a97b0f2f2c6d"

# The complete result of the population grep, as SOURCE records (not files to sample from directly -- see
# `_load_sources` for how each is turned into premises).
ELIGIBLE_SOURCE_FILES = (
    CONTRACT_DIRECTED_RUNS / "gate2-diagnostic-002" / "04_final_record.json",
    CONTRACT_DIRECTED_RUNS / "gate-integration-live-002" / "04_final_record.json",
    AB_BACKEND / "runB" / "out" / "14a_overview.json",
    AB_BACKEND / "diag_s_unbounded" / "06_screening_offline.json",
)

EXCLUDED_SOURCES = (
    (
        "ab-backend-2026-09-26/runA/",
        "the OLD packaged-app backend (confirmed by direct inspection: its own overview.py is "
        "app/backend/summarization/overview.py, a different module with no unit_ids/nli_pair shape)",
    ),
    (
        "ab-backend-2026-09-26/child_answer_diag/",
        "a different, per-child-answer experiment from the same 2026-09-26 session -- confirmed by direct "
        "inspection to carry no screen_version key and no unit_ids-cited-proposal shape",
    ),
    (
        "ab-backend-2026-09-26/child_evidence_diag/",
        "same exclusion reason as child_answer_diag",
    ),
    (
        "callosum-data/*/library.sqlite",
        "the packaged desktop app's own database (app/backend/summarization/overview.py's records, not "
        "experiments/ask_cli_revised's) -- a different production code path entirely, out of scope",
    ),
)


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _units_from_gate_record(record: dict) -> dict[str, str]:
    return {u["unit_id"]: u["passage"] for u in record["units"]}


def inventory() -> dict:
    """Returns the complete, deduplicated distinct-premise inventory with full provenance. Pure/offline."""
    gate2 = _load(ELIGIBLE_SOURCE_FILES[0])["record"]
    live2 = _load(ELIGIBLE_SOURCE_FILES[1])["record"]
    o14a = _load(ELIGIBLE_SOURCE_FILES[2])
    diag = _load(ELIGIBLE_SOURCE_FILES[3])
    diag_receipt = _load(AB_BACKEND / "diag_s_unbounded" / "00_pre_call_receipt.json")

    # cross-reference proof for diag_s_unbounded (it carries no units array of its own)
    ab_units = _units_from_gate_record(o14a) if "units" in o14a else {u["unit_id"]: u["passage"] for u in o14a["units"]}
    assert o14a["question_hash"] == gate2["question_hash"] == live2["question_hash"], (
        "all sources must share the same question_hash to be treated as one population -- they do (verified)"
    )
    cited_by_diag = {uid for r in diag["records"] for uid in r["unit_ids"]}
    missing = cited_by_diag - set(ab_units)
    assert not missing, f"diag_s_unbounded cites unit ids not present in its cross-referenced source: {missing}"
    assert set(diag_receipt["sent_unit_ids"]) <= set(ab_units), "diag receipt's sent units must be a subset too"

    distinct: dict[tuple[str, ...], dict] = {}

    def register(unit_ids: list[str], units_map: dict[str, str], source: str):
        key = tuple(unit_ids)
        premise = " ".join(units_map[u] for u in unit_ids)
        entry = distinct.setdefault(
            key,
            {
                "unit_ids": list(unit_ids),
                "span_count": len(unit_ids),
                "premise": premise,
                "char_len": len(premise),
                "occurrences": [],
            },
        )
        assert entry["premise"] == premise, f"same unit_ids key produced a different premise string: {key}"
        entry["occurrences"].append(source)

    gate2_units = _units_from_gate_record(gate2)
    live2_units = _units_from_gate_record(live2)
    for p in gate2["proposals"]:
        register(p["unit_ids"], gate2_units, "gate2-diagnostic-002 proposal idx=" + str(p["index"]))
    for p in live2["proposals"]:
        register(p["unit_ids"], live2_units, "gate-integration-live-002 proposal idx=" + str(p["index"]))
    for p in o14a["proposals"]:
        register(p["unit_ids"], ab_units, "ab-backend/runB/14a_overview.json proposal idx=" + str(p["index"]))
    for r in diag["records"]:
        register(
            r["unit_ids"], ab_units, "ab-backend/diag_s_unbounded/06_screening_offline.json idx=" + str(r["index"])
        )

    return {
        "question_hash": o14a["question_hash"],
        "eligible_source_files": [str(p) for p in ELIGIBLE_SOURCE_FILES],
        "excluded_sources": list(EXCLUDED_SOURCES),
        "distinct_premise_count": len(distinct),
        "premises": list(distinct.values()),
    }


def tokenize_lengths(premises: list[dict]) -> list[dict]:
    """Real cached tokenizer, offline, no network. Adds `tokens` (self-entailment pair token count) to each
    premise dict, in place, and returns the same list."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(NLI_MODEL, revision=NLI_REVISION, local_files_only=True)
    for p in premises:
        enc = tok(p["premise"], p["premise"], truncation=False)  # a self-entailment pair: premise vs itself
        p["self_entailment_pair_tokens"] = len(enc["input_ids"])
        p["model_max_length"] = tok.model_max_length
        p["would_truncate"] = len(enc["input_ids"]) > tok.model_max_length
    return premises


def content_hash(premises: list[dict]) -> list[dict]:
    import hashlib

    for p in premises:
        p["sha256"] = hashlib.sha256(p["premise"].encode("utf-8")).hexdigest()
    return premises


EVAL_DIR = CONTRACT_DIRECTED_RUNS / "nli-premise-population-eval-001"

PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-candidate-reliability-study-001",
        "nli-four-span-ablation-001",
        "nli-clause-count-experiment-001",
        "nli-polarity-lexical-experiment-001",
        "nli-prospective-corpus-eval-001",
        "nli-prospective-pilot-001",
        "nli-repair-demo-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


def write_manifest(run_dir: Path, inv: dict) -> Path:
    name = run_dir.name
    if name in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {name}")
    if run_dir.exists() and any(run_dir.iterdir()):
        raise RuntimeError(f"refusing to overwrite an already-populated directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "00_population_inventory.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    inv = inventory()
    tokenize_lengths(inv["premises"])
    content_hash(inv["premises"])
    print(f"Distinct real premises found: {inv['distinct_premise_count']}")
    for p in inv["premises"]:
        print(
            f"  span_count={p['span_count']} char_len={p['char_len']} "
            f"tokens={p['self_entailment_pair_tokens']} occurrences={len(p['occurrences'])} "
            f"sha256={p['sha256'][:12]}..."
        )
    if inv["distinct_premise_count"] < 24:
        print(
            f"\nSTOP CONDITION MET: {inv['distinct_premise_count']} < 24 distinct real premises available. "
            "No inference batch will be run. Writing the inventory only."
        )
    out_path = write_manifest(EVAL_DIR, inv)
    print(f"Wrote inventory to {out_path}")
