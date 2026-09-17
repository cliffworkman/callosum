"""Offline arithmetic on external human labels. No semantic labeling or model calls."""

import math
from collections import Counter, defaultdict

from .contracts import ContractError
from .hashing import digest
from .referents import validate_review

CATEGORIES = ("FAITHFUL", "LOSS", "ADDITION", "LOSS_AND_ADDITION", "MALFORMED_OR_UNUSABLE")
FLAGS = ("LOSS", "ADDITION", "MALFORMED")
DIMENSIONS = (
    "obligations",
    "relationships",
    "operations",
    "exact_constructs",
    "open_requests",
    "null",
    "mixed",
    "uncertain",
    "populations",
    "measurement_constraints",
)


def rate(successes, total):
    if type(total) is not int or type(successes) is not int or not 0 <= successes <= total:
        raise ContractError("INVALID_RATE_COUNTS")
    if total == 0:
        return {"numerator": 0, "denominator": 0, "rate": None, "wilson_lower": None, "status": "NOT_ESTIMABLE"}
    z = 1.959963984540054  # lower endpoint of two-sided 95% Wilson interval
    p = successes / total
    lower = (p + z * z / (2 * total) - z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))) / (
        1 + z * z / total
    )
    return {
        "numerator": successes,
        "denominator": total,
        "rate": p,
        "wilson_lower": max(0.0, lower),
        "confidence": 0.95,
        "convention": "lower endpoint of two-sided Wilson",
        "status": "ESTIMATED",
    }


def context_choice(choice, reference, acceptable):
    if reference is None:
        return {"status": "UNLABELED"}
    if choice is None:
        return {"status": "NO_CHOICE"}
    if choice not in "ABCDE" or reference not in "ABCDE":
        raise ContractError("INVALID_CONTEXT_CHOICE")
    delta = "ABCDE".index(choice) - "ABCDE".index(reference)
    return {
        "status": "ACCEPTABLE"
        if choice in acceptable
        else "UNDER_EXPANDED"
        if delta < 0
        else "OVER_EXPANDED"
        if delta > 0
        else "EXACT",
        "under_distance": max(0, -delta),
        "over_distance": max(0, delta) if choice not in acceptable else 0,
        "meaning_of_E": "bounded context insufficient; never discard",
        "composite_penalty": None,
    }


def validate_label(row, *, synthetic):
    origin = "SYNTHETIC" if synthetic else "HUMAN"
    if row.get("origin") != origin:
        raise ContractError("EXTERNAL_HUMAN_LABEL_REQUIRED")
    if not synthetic and (
        row.get("referent_review_status") != "APPROVED"
        or not row.get("reviewer")
        or not row.get("referent_hash")
        or not row.get("output_hash")
    ):
        raise ContractError("HUMAN_REFERENT_REVIEW_REQUIRED")
    if row.get("overall") not in CATEGORIES:
        raise ContractError("INVALID_FIDELITY_CATEGORY")
    if set(row.get("flags", {})) != set(FLAGS) or any(type(v) is not bool for v in row["flags"].values()):
        raise ContractError("INDEPENDENT_FLAGS_REQUIRED")
    for dimension in DIMENSIONS:
        values = row.get("dimensions", {}).get(dimension, [])
        if any(v not in ("PRESERVED", "DRIFTED", "STARVED", "UNRESOLVED") for v in values):
            raise ContractError("INVALID_DIMENSION_LABEL")
    for axis in ("responsiveness", "completeness", "contamination"):
        if row.get(axis) is not None and type(row[axis]) is not bool:
            raise ContractError("INDEPENDENT_OUTCOME_MUST_BE_BOOLEAN_OR_UNLABELED")


def score(rows, *, synthetic=False, evidence=None):
    from pathlib import Path

    from .hashing import read_json
    from .validation import validate

    validate(rows, read_json(Path(__file__).parent / "schemas/score_input.schema.json"))
    grouped = defaultdict(list)
    seen = set()
    for row in rows:
        validate_label(row, synthetic=synthetic)
        if not synthetic:
            linked = (evidence or {}).get(row.get("cell_id"), {})
            inv, review = linked.get("inventory", {}), linked.get("review", {})
            receipt = linked.get("verified_receipt", {})
            if not inv or not validate_review(inv, review) or row["referent_hash"] != inv["inventory_sha256"]:
                raise ContractError("HUMAN_REFERENT_REVIEW_REQUIRED")
            if receipt.get("status") not in ("SUCCESS", "FAILED") or not receipt.get("receipt"):
                raise ContractError("VERIFIED_OBSERVATION_RECEIPT_REQUIRED")
            if row["output_hash"] not in {r["sha256"] for r in receipt["receipt"]["artifacts"]}:
                raise ContractError("LABEL_OUTPUT_PROVENANCE_MISMATCH")
        key = (row["question_id"], row["task_kind"], row["model_id"], row["package_id"], row["stratum_hash"])
        unique = (key, row["unit_id"])
        if unique in seen:
            raise ContractError("DUPLICATE_SCORED_UNIT")
        seen.add(unique)
        grouped[key].append(row)
    reports = []
    for key, units in sorted(grouped.items()):
        report = dict(zip(("question_id", "task_kind", "model_id", "package_id", "stratum_hash"), key, strict=False))
        report["overall_categories"] = dict(Counter(r["overall"] for r in units))
        report["independent_flags"] = {flag: rate(sum(r["flags"][flag] for r in units), len(units)) for flag in FLAGS}
        report["fidelity"] = rate(sum(r["overall"] == "FAITHFUL" for r in units), len(units))
        report["dimensions"] = {}
        for dim in DIMENSIONS:
            labels = [v for r in units for v in r.get("dimensions", {}).get(dim, [])]
            report["dimensions"][dim] = {
                "counts": dict(Counter(labels)),
                "preserved": rate(labels.count("PRESERVED"), len(labels)),
                "unresolved": labels.count("UNRESOLVED"),
            }
        for axis in ("mechanical_validity", "responsiveness", "completeness", "contamination"):
            values = [r[axis] for r in units if r.get(axis) is not None]
            report[axis] = rate(sum(values), len(values))
            report[axis]["unlabeled"] = len(units) - len(values)
        contaminated = any(r.get("contamination") is True for r in units)
        report["contamination_gate"] = (
            "FAIL" if contaminated else "UNRESOLVED" if report["contamination"]["unlabeled"] else "ZERO_OBSERVED"
        )
        report["product_viability"] = "REQUIRED_FINAL_FREEZE_VALUE"
        report["unit_ids"] = sorted(r["unit_id"] for r in units)
        report["units_hash"] = digest(report["unit_ids"])
        reports.append(report)
    return {
        "scorer_version": "070-offline-v0",
        "synthetic": synthetic,
        "per_question": reports,
        "cross_question_average": "PROHIBITED",
        "effects": effects(reports),
        "semantic_labels_generated": 0,
        "numeric_fidelity_floors": "REQUIRED_FINAL_FREEZE_VALUE",
    }


def effects(reports):
    """Matched per-question contrasts, never a fitted model-capacity or prompt effect."""
    strata = defaultdict(dict)
    for r in reports:
        strata[(r["question_id"], r["task_kind"], r["stratum_hash"], r["units_hash"])][
            (r["model_id"], r["package_id"])
        ] = r
    result = []
    for stratum, cells in sorted(strata.items()):
        models = sorted({m for m, _ in cells})
        packages = sorted({p for _, p in cells})
        contrasts = []
        metrics = ("fidelity", "mechanical_validity", "responsiveness", "completeness", "contamination", *DIMENSIONS)
        estimable = False
        for metric in metrics:

            def value(m, p, cells=cells, metric=metric):
                cell = cells.get((m, p), {})
                rate_data = (
                    cell.get("dimensions", {}).get(metric, {}).get("preserved", {})
                    if metric in DIMENSIONS
                    else cell.get(metric, {})
                )
                # Unlabeled observations cannot change contrast denominators silently.
                if rate_data.get("unlabeled", 0):
                    return None
                return rate_data.get("rate")

            for p in packages:
                for i, m in enumerate(models):
                    for n in models[i + 1 :]:
                        a, b = value(m, p), value(n, p)
                        contrasts.append(
                            {
                                "estimand": "MODEL_CONDITIONAL_ON_PACKAGE",
                                "metric": metric,
                                "package": p,
                                "models": [m, n],
                                "difference": None if a is None or b is None else b - a,
                            }
                        )
            package_deltas = {}
            for m in models:
                a, b = value(m, "R_CONTROL"), value(m, "R_0_6")
                delta = None if a is None or b is None else b - a
                package_deltas[m] = delta
                contrasts.append(
                    {
                        "estimand": "PACKAGE_WITHIN_MODEL_ACROSS_MODELS",
                        "metric": metric,
                        "model": m,
                        "difference": delta,
                    }
                )
            for i, m in enumerate(models):
                for n in models[i + 1 :]:
                    a, b = package_deltas[m], package_deltas[n]
                    available = a is not None and b is not None
                    estimable = estimable or available
                    contrasts.append(
                        {
                            "estimand": "MODEL_X_REPRESENTATION_PACKAGE_INTERACTION",
                            "metric": metric,
                            "models": [m, n],
                            "difference_in_differences": b - a if available else None,
                            "materiality": "REQUIRED_FINAL_FREEZE_VALUE",
                        }
                    )
        result.append(
            {
                "stratum": list(stratum),
                "contrasts": contrasts,
                "interaction_status": "DESCRIPTIVE_CONTRASTS" if estimable else "NOT_ESTIMABLE",
            }
        )
    return result
