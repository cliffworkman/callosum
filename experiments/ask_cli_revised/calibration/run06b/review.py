"""Model-authored review annotations + the human-readable review artifacts.

Two kinds of annotation, kept clearly distinct and NEVER presented as human ground truth:

  * DEV proposition annotations — authored (by Claude, deterministically, from the frozen span+context
    ONLY) and hashed BEFORE any Qwen inference. They cover the named regression specimens and are the
    single inspection set the at-most-one prompt revision may consult (steering #4). Because they are
    pre-registered and held out, qualitative agreement may be reported for DEV.
  * Post-hoc claim-review flags — computed AFTER P2, deterministic heuristics surfaced beside the raw
    span/context/claim so a human can adjudicate. Explicitly labeled post-hoc; NO accuracy/FP/FN language.
"""

from __future__ import annotations

import hashlib
import json
import re

# ---- DEV proposition-annotation judgment (frozen span/context only) ---------------------------------
PROPOSITION_BEARING = "PROPOSITION_BEARING"
NON_PROPOSITION = "NON_PROPOSITION"
AMBIGUOUS = "AMBIGUOUS"

# Chunks whose content is structural/bibliographic/metadata → NON_PROPOSITION by their own text.
_NONPROP_CHUNKS = {23557, 23201, 46071, 26503, 30784, 30603, 23192, 23171, 22869}
# Chunks that assert an empirical/scientific proposition → PROPOSITION_BEARING.
_PROP_CHUNKS = {34974, 35068, 34984, 33601, 30770, 14422}
_RTPJ_CHUNK = 26831


def dev_proposition_annotation(unit: dict) -> dict | None:
    """A pre-registered, model-authored reference label for a DEV (named-specimen) unit, else None.

    Deterministic and derived only from the frozen span/context. This is Claude's descriptive review, not
    human ground truth, and is used only to guide at most one bounded prompt revision.
    """
    if unit.get("split") != "dev":
        return None
    cid = unit.get("containing_chunk_id")
    sid = unit.get("local_span_id")
    if cid == _RTPJ_CHUNK:
        if sid == "e1":
            return {
                "label": AMBIGUOUS,
                "rationale": "A results-section heading, but its own text asserts a directional finding "
                "(ASD adults show atypical RTPJ activity). A span-defensible YES is reasonable; a strict "
                "reading calls it a heading. This is the context-leakage probe.",
            }
        return {
            "label": PROPOSITION_BEARING,
            "rationale": "A null/association neural finding stated in the excerpt itself.",
        }
    if cid in _NONPROP_CHUNKS:
        return {
            "label": NON_PROPOSITION,
            "rationale": "Structural/bibliographic/metadata text (address, reference entry, running "
            "footer, table-cell debris, or a bare heading/label) with no propositional content of its own.",
        }
    if cid in _PROP_CHUNKS:
        return {
            "label": PROPOSITION_BEARING,
            "rationale": "An empirical/scientific proposition (result, association, or phenomenon) stated "
            "in the excerpt itself.",
        }
    return None


def freeze_dev_annotations(units: list[dict]) -> dict:
    """Compute + hash the pre-registered DEV annotation set (called BEFORE inference)."""
    rows = []
    for u in units:
        ann = dev_proposition_annotation(u)
        if ann is not None:
            rows.append(
                {
                    "dataset_instance_id": u["dataset_instance_id"],
                    "containing_chunk_id": u["containing_chunk_id"],
                    "local_span_id": u["local_span_id"],
                    "regression_specimen": u.get("regression_specimen"),
                    "label": ann["label"],
                    "rationale": ann["rationale"],
                }
            )
    canonical = json.dumps(
        [{k: r[k] for k in ("dataset_instance_id", "label")} for r in rows], sort_keys=True, ensure_ascii=False
    )
    return {"annotations": rows, "count": len(rows), "hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def assert_dev_annotations_unchanged(frozen: dict, units: list[dict]) -> None:
    current = freeze_dev_annotations(units)
    if current["hash"] != frozen["hash"]:
        raise AssertionError(f"DEV annotations changed after freeze ({frozen['hash'][:12]} -> {current['hash'][:12]})")


# ---- Post-hoc claim-review heuristics (labeled, not ground truth) -----------------------------------
_HEDGES = (
    "may",
    "might",
    "suggest",
    "suggests",
    "appear",
    "appears",
    "associated with",
    "correlat",
    "possib",
    "tend",
    "likely",
    "marginal",
)
_CAUSAL = ("causes", "caused", "leads to", "results in", "because of", "due to")


def claim_review_flags(*, span_text: str, claim: str | None) -> dict:
    """Deterministic post-hoc heuristics comparing the claim to its exact span. Heuristics, not verdicts."""
    if not claim:
        return {"null": True, "flags": []}
    flags: list[str] = []
    span_l, claim_l = span_text.lower(), claim.lower()
    span_hedged = any(h in span_l for h in _HEDGES)
    claim_hedged = any(h in claim_l for h in _HEDGES)
    if span_hedged and not claim_hedged:
        flags.append("LOST_QUALIFIER?")
    if any(c in claim_l for c in _CAUSAL) and not any(c in span_l for c in _CAUSAL):
        flags.append("ADDED_CAUSALITY?")
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", claim.strip()) if s]
    if len(sentences) > 1:
        flags.append("NON_ATOMIC?")
    if canonical_equal(span_text, claim):
        flags.append("VERBATIM_ECHO?")
    if not flags:
        flags.append("SOURCE_LOCAL?")
    return {"null": False, "flags": flags}


def canonical_equal(a: str, b: str) -> bool:
    def norm(s: str) -> str:
        return " ".join((s or "").split()).lower()

    return norm(a) == norm(b)


# ---- markdown builders ------------------------------------------------------------------------------
def _trunc(text: str, n: int = 240) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def proposition_review_md(units: list[dict], p1_by_id: dict) -> list[str]:
    lines = [
        "# Run 0.6b — Proposition-screen review (P1)",
        "",
        "Model-authored review annotations are Claude's descriptive labels (DEV = pre-registered before "
        "inference; EVAL = none pre-registered — post-hoc, qualitative only). NOT human ground truth.",
        "",
    ]
    for stratum, title in (
        ("select_evidence_span", "Stratum 1 — select_evidence e# spans"),
        ("pre_selection_chunk", "Stratum 2 — pre-selection chunks"),
    ):
        lines += ["", f"## {title}", ""]
        for u in [x for x in units if x["stratum"] == stratum]:
            p1 = p1_by_id.get(u["dataset_instance_id"], {})
            ann = dev_proposition_annotation(u)
            lines += [
                f"### {u['dataset_instance_id']} · chunk {u['containing_chunk_id']} · span {u['local_span_id']} · role={u['evidence_role']}",
                f"- **exact span:** {_trunc(u['exact_span_text'])}",
                f"- **context:** {'(span shown alone)' if not u['context_available'] else _trunc(u['context_text'])}",
                f"- **old select_evidence:** status={u['old_select_evidence_status']} model_selected={u.get('old_model_selected')} effective={u.get('old_effective_selected')} fallback={u.get('old_fallback_used')} failure={u.get('old_call_failure_reason')}",
                f"- **P1 answer:** {p1.get('answer')} (schema_ok={p1.get('schema_ok')} truncated={p1.get('truncated')})",
                f"- **model-authored annotation ({'DEV/pre-registered' if u['split'] == 'dev' else 'EVAL/post-hoc'}):** {ann['label'] if ann else '(none)'}"
                + (f" — {ann['rationale']}" if ann else ""),
                "",
            ]
    return lines


def claim_review_md(units_yes: list[dict], p2_by_id: dict, verifier_by_id: dict) -> list[str]:
    lines = [
        "# Run 0.6b — Claim-formation + verifier review (P2 → unchanged verifier)",
        "",
        "Claim-review flags are post-hoc deterministic heuristics (not verdicts). Verifier scores are the "
        "UNCHANGED local verifier, diagnostic only — 'verified' does NOT mean 'answers the user'.",
        "",
    ]
    for u in units_yes:
        p2 = p2_by_id.get(u["dataset_instance_id"], {})
        claim = p2.get("claim")
        v = verifier_by_id.get(u["dataset_instance_id"])
        flags = claim_review_flags(span_text=u["exact_span_text"], claim=claim)
        lines += [
            f"### {u['dataset_instance_id']} · chunk {u['containing_chunk_id']} · span {u['local_span_id']} · role={u['evidence_role']}",
            f"- **exact span:** {_trunc(u['exact_span_text'])}",
            f"- **claim:** {claim if claim else 'null'}",
        ]
        if v is None:
            lines.append(f"- **verifier:** (not run — {u.get('span_note') or 'null claim'})")
        else:
            lines.append(
                f"- **verifier:** status={v['status']} retrieval={v['retrieval_confidence']:.4f} "
                f"quote={v['quote_confidence']:.1f} support={v['support_confidence']:.4f} "
                f"contradiction={(v['contradiction_confidence'] if v['contradiction_confidence'] is not None else float('nan')):.4f}"
            )
        lines += [f"- **post-hoc claim flags:** {', '.join(flags['flags'])}", ""]
    return lines
