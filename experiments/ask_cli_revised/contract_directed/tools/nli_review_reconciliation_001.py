"""Reconcile the fresh-context reviewer submission against historical NLI outcomes (2026-09-28 authorization).

Zero inference: this module reads real saved JSON and calls exactly one already-shipped PURE function
(`overview_guards.strip_redundant_unit_markers`, regex/string logic, no model, no network) to determine
whether the already-repaired citation-boundary code would change what a given historical candidate's screen/
NLI input looks like -- it never re-scores anything.

`SUBMITTED_STRUCTURED_TRANSCRIPTION` below is a hand transcription of the verbatim reviewer submission saved
at `runs/nli-candidate-review-reconciliation-001/00_submitted_review_transcript_VERBATIM.md`. It is validated
against that file's own content by `test_transcription_matches_the_verbatim_file` (a substring-presence check
per atomic-proposition sentence, not a re-derivation) -- transcription fidelity is a testable property, not an
assertion trusted on its own.
"""

from __future__ import annotations

import json
from pathlib import Path

from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised.contract_directed.tools import nli_candidate_pair_inventory as inv_tool
from experiments.ask_cli_revised.contract_directed.tools import nli_reviewer_packet_prep_001 as prep

RUNS_DIR = inv_tool.CONTRACT_DIRECTED_RUNS
EVAL_DIR = RUNS_DIR / "nli-candidate-review-reconciliation-001"
REVIEW_PREP_DIR = RUNS_DIR / "nli-candidate-reliability-review-prep-001"
TRANSCRIPT_PATH = EVAL_DIR / "00_submitted_review_transcript_VERBATIM.md"

VALID_LABELS = frozenset(
    {"Entailed", "Contradicted", "Not established", "Ambiguous or unjudgeable", "Mixed or composite"}
)

# ---------------------------------------------------------------------------------------------------------
# Hand transcription of the verbatim submission. Every atomic proposition's `label` is normalized to the
# 5-value vocabulary; `label_verbatim` preserves the reviewer's own exact wording (some atomic labels for the
# two truncated items read "Ambiguous or unjudgeable as a complete proposition" -- the qualifier is preserved
# verbatim, never silently dropped, while `label` itself stores only the vocabulary term).
# ---------------------------------------------------------------------------------------------------------

SUBMITTED_STRUCTURED_TRANSCRIPTION: dict[str, dict] = {
    "RV-8WGZ": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {"text": "Participants completed the Just World Beliefs Scale.", "label": "Entailed"},
            {
                "text": "The scale measures beliefs about interpersonal fairness toward oneself and others.",
                "label": "Entailed",
            },
            {"text": "Participants completed the Interpersonal Reactivity Index.", "label": "Entailed"},
            {"text": "The index measures cognitive empathy through perspective taking.", "label": "Entailed"},
            {"text": "The index measures affective empathy through empathic concern.", "label": "Entailed"},
            {"text": "Participants completed a subscale from the Three-Domain Disgust scale.", "label": "Entailed"},
            {"text": "The subscale measures sensitivity to pathogen-related disgust.", "label": "Entailed"},
        ],
        "reason": "All seven propositions are directly stated in the premise. The citation marker U1 and the removal of bibliographic reference numbers do not change the scientific claims.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-MT5B": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {"text": "The study presented face pairs to 123 Hadza across ten camps.", "label": "Entailed"},
            {"text": "The pairs consisted of morphed Hadza faces.", "label": "Entailed"},
            {"text": "One face in each pair was altered to include a scar.", "label": "Entailed"},
            {"text": "Participants were asked which face they expected to be more moral.", "label": "Entailed"},
            {"text": "Participants were asked which face they expected to be a better forager.", "label": "Entailed"},
            {
                "text": "Hadza with greater exposure to other cultures expected the scarred face to be less moral.",
                "label": "Entailed",
            },
        ],
        "reason": "Every proposition follows directly from the premise. The candidate omits the finding that the scarred face was also expected to be a better forager. That omission does not make any proposition actually asserted by the candidate unsupported.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-RAJY": {
        "overall_label": "Mixed or composite",
        "confidence": "high",
        "atomic_propositions": [
            {
                "text": "The anomalous-is-bad stereotype is expressed in negative attitudes about people with facial anomalies.",
                "label": "Entailed",
            },
            {
                "text": "Participants expressed explicit biases against people with facial anomalies.",
                "label": "Entailed",
            },
            {"text": "Participants' implicit biases were slight.", "label": "Not established"},
            {"text": "Participants' implicit biases were not statistically significant.", "label": "Not established"},
            {
                "text": "People with anomalous faces are imbued with negative personality characteristics.",
                "label": "Entailed",
            },
            {
                "text": "Evidence for the stereotype was found in explicit negative attitudes expressed as individual character inferences.",
                "label": "Entailed",
            },
            {
                "text": "Evidence for the stereotype was found in explicit negative attitudes measured through group-level Explicit Bias Questionnaire scores.",
                "label": "Entailed",
            },
        ],
        "reason": "The premise explicitly reports negative personality inferences, explicit bias, and negative attitudes at the individual and group levels. It does not report the magnitude or statistical significance of implicit bias. Its reference to the anomalous-is-bad stereotype cannot establish either implicit-bias proposition.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-ZPXV": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {
                "text": "The authors suggest that negative attitudes measured by the IAT and EBQ underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that social cognitive biases involving just-world beliefs underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that emotional dispositions involving affective empathy underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that undesirable behaviors involving less generosity in the DG underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors describe these factors as associated with left amygdala functioning.",
                "label": "Entailed",
            },
            {
                "text": "The specific amygdala response to facial anomalies correlated with stronger just-world beliefs.",
                "label": "Entailed",
            },
            {"text": "That response correlated with less dispositional empathic concern.", "label": "Entailed"},
            {
                "text": "That response correlated with less prosociality toward people with facial anomalies.",
                "label": "Entailed",
            },
        ],
        "reason": "Both candidate sentences closely reproduce the premise. Importantly, the candidate preserves the authors' suggestive framing of the dehumanization account and describes the observed relationships as correlations rather than causal effects.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-Y4T5": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {"text": "The study involved 123 Hadza across ten camps.", "label": "Entailed"},
            {"text": "Participants were presented with pairs of morphed faces.", "label": "Entailed"},
            {"text": "One face in each pair was altered to include a scar.", "label": "Entailed"},
            {"text": "Participants were asked which face they expected to be more moral.", "label": "Entailed"},
            {"text": "Participants were asked which face they expected to be a better forager.", "label": "Entailed"},
            {
                "text": "Participants with greater exposure to other cultures expected the scarred face to be less moral.",
                "label": "Entailed",
            },
        ],
        "reason": "All propositions follow from the premise. Omitting the more specific description of the faces as Hadza faces and the additional better-forager finding introduces no unsupported assertion.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-78DB": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {"text": "Participants completed the Just World Beliefs Scale.", "label": "Entailed"},
            {
                "text": "The scale measures beliefs about interpersonal fairness toward oneself and others.",
                "label": "Entailed",
            },
            {"text": "Participants completed the Interpersonal Reactivity Index.", "label": "Entailed"},
            {"text": "The index measures cognitive empathy through perspective taking.", "label": "Entailed"},
            {"text": "The index measures affective empathy through empathic concern.", "label": "Entailed"},
            {"text": "Participants completed a subscale from the Three-Domain Disgust scale.", "label": "Entailed"},
            {"text": "The subscale measures sensitivity to pathogen-related disgust.", "label": "Entailed"},
        ],
        "reason": "Each proposition is directly stated in the premise. The candidate removes bibliographic reference numbers and normalizes line-break artifacts without changing the substantive assertions.",
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
    "RV-8G8J": {
        "overall_label": "Mixed or composite",
        "confidence": "high for the complete propositions, low for the truncated proposition",
        "atomic_propositions": [
            {
                "text": "The specific amygdala response to facial anomalies correlated with stronger just-world beliefs.",
                "label": "Not established",
            },
            {"text": "That response correlated with less dispositional empathic concern.", "label": "Not established"},
            {
                "text": "That response correlated with less prosociality toward people with facial anomalies.",
                "label": "Not established",
            },
            {
                "text": "Participants expressed explicit biases against people with facial anomalies.",
                "label": "Not established",
            },
            {"text": "Participants' implicit biases were slight.", "label": "Not established"},
            {"text": "Participants' implicit biases were not statistically significant.", "label": "Not established"},
            {
                "text": "The candidate begins an assertion that the anomalous-is-bad stereotype is expressed in negative attitudes, but the assertion is truncated.",
                "label": "Ambiguous or unjudgeable",
                "label_verbatim": "Ambiguous or unjudgeable as a complete proposition",
            },
        ],
        "reason": 'The premise establishes only that the anomalous-is-bad stereotype is expressed in negative attitudes about people with facial anomalies. It does not establish the candidate\'s amygdala correlations or its explicit- and implicit-bias findings. The final candidate sentence ends at "negative att", so its complete assertion cannot be verified without reconstructing missing text.',
        "context_requested": True,
        "context_reason": "The complete final candidate sentence is needed to determine whether it merely restates the premise or adds another assertion.",
        "locked": False,
    },
    "RV-UAHS": {
        "overall_label": "Mixed or composite",
        "confidence": "high for the complete propositions, low for the truncated proposition",
        "atomic_propositions": [
            {
                "text": "The authors suggest that negative attitudes measured by the IAT and EBQ underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that social cognitive biases involving just-world beliefs underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that emotional dispositions involving affective empathy underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors suggest that undesirable behaviors involving less generosity in the DG underpin dehumanization.",
                "label": "Entailed",
            },
            {
                "text": "The authors describe these factors as associated with left amygdala functioning.",
                "label": "Entailed",
            },
            {
                "text": "The candidate begins an assertion that the specific amygdala response to facial anomalies correlated with stronger just-world beliefs, but the assertion is truncated.",
                "label": "Ambiguous or unjudgeable",
                "label_verbatim": "Ambiguous or unjudgeable as a complete proposition",
            },
        ],
        "reason": 'The complete first sentence reproduces the authors\' suggested account and is entailed. The second sentence ends at "stronger just-world bel,". Although the premise contains an apparently matching correlation, the actual candidate is incomplete. The missing text could contain further claims or qualifications, so the complete proposition cannot be adjudicated.',
        "context_requested": True,
        "context_reason": "The complete second candidate sentence is needed to determine its full set of propositions.",
        "locked": False,
    },
    "RV-XV9K": {
        "overall_label": "Entailed",
        "confidence": "high",
        "atomic_propositions": [
            {
                "text": "Knowledge about individual differences in empathy and disgust sensitivity might improve decision-making.",
                "label": "Entailed",
            },
            {
                "text": "Knowledge about those individual differences might reduce bias toward people with anomalous faces.",
                "label": "Entailed",
            },
        ],
        "reason": 'The candidate reproduces both potential benefits stated in the premise and preserves the qualification "might". It does not turn the proposed benefits into demonstrated effects.',
        "context_requested": False,
        "context_reason": None,
        "locked": False,
    },
}


def load_transcript_text() -> str:
    return TRANSCRIPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------
# Coverage validation
# ---------------------------------------------------------------------------------------------------------


def load_reviewer_packet_ids() -> set[str]:
    with open(REVIEW_PREP_DIR / "11_reviewer_packet.json", encoding="utf-8") as f:
        packet = json.load(f)
    return {item["opaque_id"] for item in packet["items"]}


def validate_submission_coverage(submission: dict[str, dict], packet_ids: set[str]) -> None:
    """Raises if any opaque_id is missing, duplicated (impossible in a dict, but a malformed key is not), or
    doesn't match the packet -- never silently infers or drops an id."""
    submission_ids = set(submission.keys())
    if submission_ids != packet_ids:
        missing = packet_ids - submission_ids
        extra = submission_ids - packet_ids
        raise ValueError(f"submission does not cover exactly the packet's ids -- missing={missing} extra={extra}")
    for oid, entry in submission.items():
        if entry["overall_label"] not in VALID_LABELS:
            raise ValueError(f"{oid}: overall_label {entry['overall_label']!r} is not in the 5-value vocabulary")
        for prop in entry["atomic_propositions"]:
            if prop["label"] not in VALID_LABELS:
                raise ValueError(f"{oid}: atomic label {prop['label']!r} is not in the 5-value vocabulary")


# ---------------------------------------------------------------------------------------------------------
# Historical join
# ---------------------------------------------------------------------------------------------------------


def load_coordinator_map() -> list[dict]:
    with open(
        REVIEW_PREP_DIR / "20_coordinator_identity_and_family_map_DO_NOT_SHOW_REVIEWERS.json", encoding="utf-8"
    ) as f:
        return json.load(f)["items"]


def load_inventory_pairs() -> list[dict]:
    return inv_tool.build_full_inventory()["pairs"]


def classify_reason_kinds(screen_reasons: list[str], reasons: list[str]) -> dict:
    """Splits the complete saved reason set by mechanism, so a low NLI score is never mistaken for the sole
    or root cause when a deterministic guard also fired -- and vice versa."""
    nli_only = [
        r
        for r in reasons
        if r.startswith("nli_low_support:") or r.startswith("nli_contradicted:") or r == "nli_unavailable"
    ]
    deterministic = [r for r in reasons if r not in nli_only]
    return {
        "deterministic_guard_reasons": deterministic,
        "nli_score_reasons": nli_only,
        "had_any_deterministic_reason": bool(deterministic),
        "had_nli_score_reason": bool(nli_only),
        "withheld_by_nli_alone": bool(nli_only) and not deterministic,
    }


def truncation_status(hypothesis: str) -> dict:
    """Distinguishes a candidate PHYSICALLY cut off mid-word (exactly at the 400-char cap, no terminal
    punctuation) from one that merely exceeds the cap while remaining a complete, well-punctuated sentence
    (which still trips `screen()`'s own `text_too_long` reason via `len(text) > 400`, but is not itself an
    incomplete fragment)."""
    ends_clean = hypothesis.rstrip().endswith((".", "!", "?", '"'))
    physically_truncated = len(hypothesis) == guards.MAX_SENTENCE_CHARS and not ends_clean
    return {
        "length": len(hypothesis),
        "ends_with_terminal_punctuation": ends_clean,
        "physically_truncated_mid_word": physically_truncated,
        "exceeds_screen_cap": len(hypothesis) > guards.MAX_SENTENCE_CHARS,
    }


def marker_repair_status(hypothesis: str, unit_ids: list[str]) -> dict:
    """Calls the REAL, already-shipped, pure `strip_redundant_unit_markers` -- zero inference, zero network --
    to report whether the citation-boundary repair (predates this pass; postdates every historical record in
    this population) would change what this exact candidate's screen/NLI input looks like under current code.
    Never claims what a re-score WOULD produce -- only what INPUT would change."""
    result = guards.strip_redundant_unit_markers(hypothesis, unit_ids)
    return {
        "marker_outcome": result["marker_outcome"],
        "conflict_reason": result["conflict_reason"],
        "would_change_screen_and_nli_input_under_current_code": result["nli_hypothesis_text"] != hypothesis,
        "would_gain_new_conflict_reason_under_current_code": result["conflict_reason"] is not None,
    }


def build_reconciliation_records(
    submission: dict[str, dict], coordinator_map: list[dict], inventory_pairs: list[dict]
) -> list[dict]:
    by_sha = {p["pair_sha256"]: p for p in inventory_pairs}
    by_opaque = {row["opaque_id"]: row for row in coordinator_map}
    records = []
    for oid, review in submission.items():
        coord_row = by_opaque[oid]
        pair = by_sha[coord_row["pair_sha256"]]
        reason_kinds = classify_reason_kinds(pair["screen_reasons"], pair["reasons"])
        trunc = truncation_status(pair["hypothesis"])
        marker = marker_repair_status(pair["hypothesis"], pair["unit_ids"])
        records.append(
            {
                "opaque_id": oid,
                "pair_sha256": pair["pair_sha256"],
                "source_id": pair["source_id"],
                "index_in_source": pair["index_in_source"],
                "unit_ids": pair["unit_ids"],
                "family": coord_row["family"],
                "premise": pair["premise"],
                "hypothesis": pair["hypothesis"],
                "reviewer": {
                    "overall_label": review["overall_label"],
                    "confidence": review["confidence"],
                    "atomic_propositions": review["atomic_propositions"],
                    "context_requested": review["context_requested"],
                    "context_reason": review["context_reason"],
                    "locked": review["locked"],  # preserved exactly as submitted -- always False here
                },
                "historical": {
                    "status": pair["status"],
                    "nli_support": pair["nli_support"],
                    "nli_contradiction": pair["nli_contradiction"],
                    "screen_reasons": pair["screen_reasons"],
                    "reasons": pair["reasons"],
                    "self_pair_baseline": pair["premise_self_pair_baseline"],
                },
                "reason_kinds": reason_kinds,
                "truncation_status": trunc,
                "marker_repair_status": marker,
            }
        )
    return records


# ---------------------------------------------------------------------------------------------------------
# Coordinator-side freeze receipt (never sets the reviewer's own locked field to True)
# ---------------------------------------------------------------------------------------------------------


def build_freeze_receipt(submission: dict[str, dict]) -> dict:
    """A coordinator-side record that this exact submitted transcript is frozen for THIS reconciliation --
    distinct from, and never overwriting, the reviewer's own `locked` field, which every submitted item
    states as `false` and which this receipt does not change."""
    return {
        "note": (
            "This receipt freezes the submitted transcript for reconciliation purposes only. It does NOT "
            "assert the reviewer confirmed a lock, and it does not modify any submitted item's own `locked` "
            "field, which remains exactly as submitted (false) in every record."
        ),
        "frozen_opaque_ids": sorted(submission.keys()),
        "all_submitted_locked_values": {oid: entry["locked"] for oid, entry in submission.items()},
    }


# ---------------------------------------------------------------------------------------------------------
# Protected-directory guard
# ---------------------------------------------------------------------------------------------------------

PROTECTED_RUN_DIRS = (
    prep.PROTECTED_RUN_DIRS | {"nli-candidate-reliability-study-001", "nli-candidate-reliability-review-prep-001"}
) - {EVAL_DIR.name}


def write_artifact(run_dir: Path, name: str, data) -> Path:
    dirname = run_dir.name
    if dirname in PROTECTED_RUN_DIRS:
        raise RuntimeError(f"refusing to write into protected prior-attempt directory: {dirname}")
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite an already-written artifact: {path}")
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return path


if __name__ == "__main__":
    packet_ids = load_reviewer_packet_ids()
    validate_submission_coverage(SUBMITTED_STRUCTURED_TRANSCRIPTION, packet_ids)

    coordinator_map = load_coordinator_map()
    inventory_pairs = load_inventory_pairs()
    records = build_reconciliation_records(SUBMITTED_STRUCTURED_TRANSCRIPTION, coordinator_map, inventory_pairs)
    freeze_receipt = build_freeze_receipt(SUBMITTED_STRUCTURED_TRANSCRIPTION)

    write_artifact(EVAL_DIR, "01_structured_transcription.json", {"items": SUBMITTED_STRUCTURED_TRANSCRIPTION})
    write_artifact(EVAL_DIR, "02_freeze_receipt.json", freeze_receipt)
    write_artifact(EVAL_DIR, "03_reconciliation_records.json", {"items": records})

    print(f"Validated coverage: {len(SUBMITTED_STRUCTURED_TRANSCRIPTION)} items match the 9-item packet.")
    print(f"Wrote reconciliation artifacts to {EVAL_DIR}")
    for r in records:
        print(
            f"  {r['opaque_id']:10s} reviewer={r['reviewer']['overall_label']:22s} "
            f"historical={r['historical']['status']:9s} nli_support={r['historical']['nli_support']:.4f} "
            f"deterministic_reasons={len(r['reason_kinds']['deterministic_guard_reasons'])} "
            f"withheld_by_nli_alone={r['reason_kinds']['withheld_by_nli_alone']}"
        )
