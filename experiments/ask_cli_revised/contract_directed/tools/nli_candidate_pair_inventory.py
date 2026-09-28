"""Offline inventory of REAL, production-scored candidate-level (premise, hypothesis) pairs -- the overview
stage's actual (screen_proposals/nli_pair) NLI calls, as distinct from every self-entailment (premise, premise)
diagnostic this arc has run so far (2026-09-28 authorization). **No inference call anywhere in this module.**

Source population: every JSON file under `callosum-data` carrying `screen_version` (the same population-
inclusion rule `nli_premise_population_eval.py` established) -- the only records whose candidate text was
scored through the real `overview_guards.nli_pair`/`screen_proposals` path, not a diagnostic self-pair.

None of these 4 files carry `nli_hypothesis_text`/`marker_outcome`/`stripped_marker` (confirmed directly: their
proposal dicts only have the pre-citation-boundary-repair key set) -- they all predate commit `15d7592b`, so
`proposal["text"]` IS, verbatim, the exact string the NLI scorer received as the hypothesis. No reconstruction
needed for this population; the raw and scored text are provably identical for every pair here.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# Callosum's own production screening cap (overview_guards.py / screen_proposals' text_too_long rule).
MAX_SENTENCE_CHARS = 400

# Matches a trailing inline unit-citation marker exactly the way overview_guards._TRAILING_UNIT_MARKER does
# (" (U1)", " (U7)", etc.) -- used here only to CLASSIFY an observed length difference, never to strip one.
_TRAILING_MARKER_RE = re.compile(r"\s*\(U\d+\)\s*$")

DATA_ROOT = Path(r"C:\Users\cliff\callosum-data")
CONTRACT_DIRECTED_RUNS = DATA_ROOT / "contract-directed-slice" / "runs"
AB_BACKEND = DATA_ROOT / "ab-backend-2026-09-26"

SOURCES = (
    {
        "source_id": "gate2-diagnostic-002",
        "path": CONTRACT_DIRECTED_RUNS / "gate2-diagnostic-002" / "04_final_record.json",
        "shape": "final_record",
        "units_path": None,  # units are inline in the same file
    },
    {
        "source_id": "gate-integration-live-002",
        "path": CONTRACT_DIRECTED_RUNS / "gate-integration-live-002" / "04_final_record.json",
        "shape": "final_record",
        "units_path": None,
    },
    {
        "source_id": "ab-backend-14a-overview",
        "path": AB_BACKEND / "runB" / "out" / "14a_overview.json",
        "shape": "final_record_unwrapped",  # not nested under "record"
        "units_path": None,
    },
    {
        "source_id": "ab-backend-diag-s-unbounded",
        "path": AB_BACKEND / "diag_s_unbounded" / "06_screening_offline.json",
        "shape": "screening_only",  # no units of its own -- borrows ab-backend-14a-overview's
        "units_path": AB_BACKEND / "runB" / "out" / "14a_overview.json",
    },
)

# Diagnostics under this arc that establish a SELF-PAIR (premise, premise) baseline for a given premise
# string -- searched to see whether any REAL candidate-level premise above also has a self-entailment result.
SELF_PAIR_SOURCES = (
    CONTRACT_DIRECTED_RUNS / "nli-boundary-diagnostic-001" / "01_raw_scores.json",
    CONTRACT_DIRECTED_RUNS / "nli-boundary-diagnostic-002" / "01_raw_scores.json",
    CONTRACT_DIRECTED_RUNS / "nli-prospective-pilot-001" / "01_raw_scores.json",
    CONTRACT_DIRECTED_RUNS / "nli-four-span-ablation-001" / "01_raw_scores.json",
)


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _record_of(source: dict) -> dict:
    raw = _load(source["path"])
    if source["shape"] == "final_record":
        return raw["record"]
    if source["shape"] == "final_record_unwrapped":
        return raw
    raise ValueError(f"_record_of only applies to final_record shapes, got {source['shape']}")


def _units_by_id(source: dict) -> dict[str, dict]:
    if source["shape"] == "screening_only":
        units_record = _load(source["units_path"])
        return {u["unit_id"]: u for u in units_record["units"]}
    record = _record_of(source)
    return {u["unit_id"]: u for u in record["units"]}


def _build_premise(unit_ids: list[str], units: dict[str, dict]) -> str:
    """Exactly overview_guards.nli_pair's own join convention -- premise-side text, unit order preserved."""
    return " ".join(units[uid]["passage"] for uid in unit_ids)


def _canonical_locators(unit_ids: list[str], units: dict[str, dict]) -> list[dict]:
    out = []
    for uid in unit_ids:
        u = units[uid]
        locs = u.get("locators") or []
        chunk_id = locs[0]["chunk_id"] if locs else None
        out.append({"unit_id": uid, "paper_id": u["paper_id"], "chunk_id": chunk_id})
    return out


def _extract_pairs_from_source(source: dict) -> list[dict]:
    units = _units_by_id(source)
    if source["shape"] == "screening_only":
        raw = _load(source["path"])
        raw_pairs = raw["records"]
        question_hash = None  # 06_screening_offline.json carries no question_hash of its own
        contract_sha256 = None
        screen_version = raw.get("screen_version")
    else:
        record = _record_of(source)
        raw_pairs = record["proposals"]
        question_hash = record.get("question_hash")
        contract_sha256 = record.get("contract_sha256")
        screen_version = record.get("screen_version")

    out = []
    for p in raw_pairs:
        unit_ids = p["unit_ids"]
        premise = _build_premise(unit_ids, units)
        hypothesis = p["text"]  # verbatim -- confirmed no marker_outcome/nli_hypothesis_text field exists here
        out.append(
            {
                "source_id": source["source_id"],
                "index_in_source": p.get("index"),
                "unit_ids": unit_ids,
                "bears_on": p.get("bears_on"),
                "premise": premise,
                "hypothesis": hypothesis,
                "raw_text_equals_scored_hypothesis": True,  # predates the citation-boundary repair; asserted below
                "canonical_locators": _canonical_locators(unit_ids, units),
                "nli_support": p.get("nli", {}).get("support") if isinstance(p.get("nli"), dict) else None,
                "nli_contradiction": p.get("nli", {}).get("contradiction") if isinstance(p.get("nli"), dict) else None,
                "screen_reasons": p.get("screen_reasons"),
                "reasons": p.get("reasons"),
                "status": p.get("status"),
                "question_hash": question_hash,
                "contract_sha256": contract_sha256,
                "screen_version": screen_version,
                "pair_sha256": hashlib.sha256((premise + "\x00" + hypothesis).encode("utf-8")).hexdigest(),
            }
        )
    return out


def build_raw_inventory() -> list[dict]:
    """Every candidate-level pair from all 4 sources, NOT yet deduplicated. Asserts the "predates the
    citation-boundary repair" claim against the real saved proposal dicts, not just documentation."""
    all_pairs = []
    for source in SOURCES:
        raw = _load(source["path"])
        proposals = (
            raw["records"]
            if source["shape"] == "screening_only"
            else (raw["record"]["proposals"] if source["shape"] == "final_record" else raw["proposals"])
        )
        for p in proposals:
            assert "nli_hypothesis_text" not in p and "marker_outcome" not in p, (
                f"{source['source_id']} unexpectedly carries citation-boundary fields -- "
                "raw_text_equals_scored_hypothesis assumption would be wrong"
            )
        all_pairs.extend(_extract_pairs_from_source(source))
    return all_pairs


def load_self_pair_baselines() -> dict[str, dict]:
    """{premise_sha256: {support, contradiction, source, pair_id}} for every SELF-PAIR (premise==hypothesis)
    result found across the self-entailment diagnostics in this arc."""
    baselines: dict[str, dict] = {}
    for path in SELF_PAIR_SOURCES:
        if not path.exists():
            continue
        raw = _load(path)
        for r in raw["results"]:
            premise = r.get("premise")
            if premise is None:
                continue
            key = hashlib.sha256(premise.encode("utf-8")).hexdigest()
            if key not in baselines:  # first occurrence kept; every prior pass already proved exact reproduction
                baselines[key] = {
                    "support": r["support"],
                    "contradiction": r["contradiction"],
                    "source": str(path),
                    "pair_id": r.get("pair_id") or r.get("id"),
                }
    return baselines


def _is_hard_length_cap_truncation(shorter: str, longer: str) -> bool:
    """Verified directly against the real ab-backend {U2,U6} pair: production's text_too_long truncation is
    NOT a clean slice -- it keeps the first 399 characters of the real text and replaces what would have been
    the 400th character with a synthetic trailing comma. So the check is "agree on the first 399 chars, the
    400th differs, and the 400th of `longer` continues mid-word" -- not a strict `startswith`."""
    if len(shorter) != MAX_SENTENCE_CHARS or len(longer) <= MAX_SENTENCE_CHARS:
        return False
    return shorter[:-1] == longer[: MAX_SENTENCE_CHARS - 1] and shorter[-1] != longer[MAX_SENTENCE_CHARS - 1]


def _is_trailing_citation_marker_difference(shorter: str, longer: str) -> bool:
    """Verified directly against the real gate2-diagnostic-002 vs. gate-integration-live-002 U1/c9 pair: a
    trailing " (U<n>)" marker is inserted BEFORE the sentence's own final punctuation, not appended after it
    -- so `longer` is shorter's own text with the closing punctuation moved out and a marker spliced in front
    of it, e.g. "...disgust." -> "...disgust (U1)." (period relocates around the inserted marker)."""
    if not shorter or shorter[-1] not in '.!?"':
        return False
    body, punct = shorter[:-1], shorter[-1]
    if not (longer.startswith(body) and longer.endswith(punct)):
        return False
    inserted = longer[len(body) : -1]
    return bool(_TRAILING_MARKER_RE.fullmatch(inserted))


def _classify_relationship(shorter: str, longer: str) -> str:
    """Distinguishes the two genuinely different "related, not identical" patterns actually observed in this
    population -- conflating them would misdescribe the evidence. A generic 'prefix_variant' is the honest
    fallback when neither specific, verified pattern matches."""
    if _is_hard_length_cap_truncation(shorter, longer):
        return "hard_length_cap_truncation"
    if _is_trailing_citation_marker_difference(shorter, longer):
        return "trailing_citation_marker_difference"
    return "prefix_variant"


def deduplicate(raw_pairs: list[dict]) -> list[dict]:
    """Byte-identical (premise, hypothesis) pairs counted once; every source occurrence preserved. A pair with
    the SAME unit_ids but DIFFERENT hypothesis bytes (e.g. the 400-char-truncated vs. unbounded {U2,U6}
    candidate, or c9's own U1 candidate with/without a trailing citation marker) is NEVER merged -- each is a
    genuinely distinct string that was ACTUALLY submitted to and independently scored by the NLI model (their
    `nli_support` values differ), so each stays its own row. The relationship is recorded, not resolved."""
    by_sha: dict[str, dict] = {}
    for p in raw_pairs:
        key = p["pair_sha256"]
        if key not in by_sha:
            entry = dict(p)
            entry["occurrences"] = [{"source_id": p["source_id"], "index_in_source": p["index_in_source"]}]
            by_sha[key] = entry
        else:
            by_sha[key]["occurrences"].append({"source_id": p["source_id"], "index_in_source": p["index_in_source"]})
    distinct = list(by_sha.values())
    # flag related-variant pairs: same unit_ids (same evidentiary premise), hypotheses related by one of the
    # two specific, verified patterns above -- classified per-pair, never assumed to be the same phenomenon.
    for a in distinct:
        a["related_variant"] = None
        for b in distinct:
            if a is b or a["unit_ids"] != b["unit_ids"] or len(a["hypothesis"]) >= len(b["hypothesis"]):
                continue
            kind = _classify_relationship(a["hypothesis"], b["hypothesis"])
            if kind == "prefix_variant" and not b["hypothesis"].startswith(a["hypothesis"]):
                continue  # neither a verified pattern nor an actual prefix -- not related, say nothing
            a["related_variant"] = {
                "kind": kind,
                "of_pair_sha256": b["pair_sha256"],
                "of_source": b["source_id"],
                "nli_support_self": a["nli_support"],
                "nli_support_other": b["nli_support"],
            }
    return distinct


def attach_self_pair_baselines(distinct_pairs: list[dict], baselines: dict[str, dict]) -> list[dict]:
    for p in distinct_pairs:
        key = hashlib.sha256(p["premise"].encode("utf-8")).hexdigest()
        p["premise_self_pair_baseline"] = baselines.get(key)
    return distinct_pairs


def classify_groups(distinct_pairs: list[dict]) -> dict[str, list[str]]:
    """The 4 analytically meaningful groups from Section 4 of the authorization, keyed by pair_sha256."""
    groups = {"passing_self_pair": [], "failing_self_pair": [], "no_self_pair_result": []}
    for p in distinct_pairs:
        baseline = p["premise_self_pair_baseline"]
        if baseline is None:
            groups["no_self_pair_result"].append(p["pair_sha256"])
        elif baseline["support"] < 0.01:  # the operational "severe failure" band this arc has used throughout
            groups["failing_self_pair"].append(p["pair_sha256"])
        else:
            groups["passing_self_pair"].append(p["pair_sha256"])
    return groups


def build_full_inventory() -> dict:
    raw_pairs = build_raw_inventory()
    distinct_pairs = deduplicate(raw_pairs)
    baselines = load_self_pair_baselines()
    distinct_pairs = attach_self_pair_baselines(distinct_pairs, baselines)
    groups = classify_groups(distinct_pairs)

    distinct_premises = {p["premise"] for p in distinct_pairs}
    distinct_hypotheses = {p["hypothesis"] for p in distinct_pairs}
    distinct_question_hashes = {p["question_hash"] for p in distinct_pairs if p["question_hash"]}
    distinct_papers = sorted({loc["paper_id"] for p in distinct_pairs for loc in p["canonical_locators"]})

    return {
        "raw_pair_count": len(raw_pairs),
        "distinct_pair_count": len(distinct_pairs),
        "distinct_premise_count": len(distinct_premises),
        "distinct_hypothesis_count": len(distinct_hypotheses),
        "distinct_question_hash_count": len(distinct_question_hashes),
        "distinct_papers": distinct_papers,
        "groups": {k: len(v) for k, v in groups.items()},
        "group_membership": groups,
        "pairs": distinct_pairs,
    }


def cross_reference_prospective_corpus_group4(distinct_pairs: list[dict]) -> dict:
    """Section 4, Group 4: source-derived prospective premises (self-pair-tested in nli-prospective-pilot-001)
    that have NO real candidate-level scoring record -- i.e. no naturally-occurring overview candidate was
    ever scored against that exact premise. Imports the pilot's own frozen manifest read-only; runs no
    inference (the manifest is a plain data structure the pilot module builds offline)."""
    from experiments.ask_cli_revised.contract_directed.tools import nli_prospective_pilot_001 as pilot

    candidate_premise_shas = {hashlib.sha256(p["premise"].encode("utf-8")).hexdigest() for p in distinct_pairs}
    manifest = pilot.build_execution_manifest()
    group4 = []
    for item in manifest["pairs"]:
        premise = item.get("premise")
        if premise is None:
            continue
        sha = hashlib.sha256(premise.encode("utf-8")).hexdigest()
        if sha not in candidate_premise_shas:
            group4.append(
                {
                    "pair_id": item.get("pair_id"),
                    "stratum": item.get("stratum"),
                    "premise_sha256": sha,
                    "span_count": item.get("span_count"),
                    "paper_ids": item.get("paper_ids"),
                }
            )
    return {
        "total_prospective_pilot_premises": len(manifest["pairs"]),
        "with_no_candidate_level_record": len(group4),
        "members": group4,
    }


def build_blinded_reviewer_packet(distinct_pairs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Returns (packet, identity_map) as two SEPARATE structures -- the packet is what a reviewer sees; the
    identity map is kept apart so blinding is structural, not merely a matter of which fields a reviewer
    happens to look at. Deliberately excludes every NLI-derived field: support/contradiction, status,
    screen_reasons, self-pair baseline, related_variant, and even which source file it came from (a reviewer
    who knows "this is from live-002" could infer it was a withheld candidate)."""
    packet, identity_map = [], []
    for i, p in enumerate(sorted(distinct_pairs, key=lambda x: x["pair_sha256"]), start=1):
        blind_id = f"packet-item-{i:02d}"
        packet.append(
            {
                "blind_id": blind_id,
                "premise": p["premise"],
                "candidate_statement": p["hypothesis"],
                "source_papers": sorted({loc["paper_id"] for loc in p["canonical_locators"]}),
            }
        )
        identity_map.append(
            {
                "blind_id": blind_id,
                "pair_sha256": p["pair_sha256"],
                "source_id": p["source_id"],
                "index_in_source": p["index_in_source"],
                "unit_ids": p["unit_ids"],
            }
        )
    return packet, identity_map


EVAL_DIR = CONTRACT_DIRECTED_RUNS / "nli-candidate-reliability-study-001"

PROTECTED_RUN_DIRS = frozenset(
    {
        "gate-integration-001",
        "gate-integration-live-001",
        "gate-integration-live-002",
        "gate2-diagnostic-001",
        "gate2-diagnostic-002",
        "nli-boundary-diagnostic-001",
        "nli-boundary-diagnostic-002",
        "nli-candidate-reliability-review-prep-001",
        "nli-clause-count-experiment-001",
        "nli-four-span-ablation-001",
        "nli-polarity-lexical-experiment-001",
        "nli-premise-population-eval-001",
        "nli-prospective-corpus-eval-001",
        "nli-prospective-pilot-001",
        "nli-repair-demo-001",
        "pilot-001",
        "pilot-prep-003",
        "replay-eligibility-001",
        "replay-eligibility-001-offline-analysis",
    }
)


def write_artifact(run_dir: Path, name: str, data: dict) -> Path:
    dirname = run_dir.name
    if dirname in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {dirname}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite an already-written artifact: {path}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    inv = build_full_inventory()
    print(f"Raw candidate pairs across 4 sources: {inv['raw_pair_count']}")
    print(f"Distinct (premise, hypothesis) pairs: {inv['distinct_pair_count']}")
    print(
        f"Distinct premises: {inv['distinct_premise_count']}  Distinct hypotheses: {inv['distinct_hypothesis_count']}"
    )
    print(f"Distinct question_hash values seen: {inv['distinct_question_hash_count']}")
    print(f"Distinct papers represented: {inv['distinct_papers']}")
    print(f"Groups: {inv['groups']}")
    out = write_artifact(EVAL_DIR, "00_candidate_pair_inventory.json", inv)
    print(f"Wrote inventory to {out}")

    group4 = cross_reference_prospective_corpus_group4(inv["pairs"])
    print(f"Group 4 (prospective, self-pair-tested, no candidate record): {group4['with_no_candidate_level_record']}")
    out4 = write_artifact(EVAL_DIR, "00b_group4_prospective_no_candidate_record.json", group4)
    print(f"Wrote Group 4 cross-reference to {out4}")

    packet, identity_map = build_blinded_reviewer_packet(inv["pairs"])
    out_packet = write_artifact(EVAL_DIR, "01_blinded_reviewer_packet_draft.json", {"items": packet})
    out_map = write_artifact(EVAL_DIR, "01b_identity_map_DO_NOT_SHOW_REVIEWERS.json", {"items": identity_map})
    print(f"Wrote blinded packet draft to {out_packet}")
    print(f"Wrote identity map (reviewer-facing DO NOT SHOW) to {out_map}")
