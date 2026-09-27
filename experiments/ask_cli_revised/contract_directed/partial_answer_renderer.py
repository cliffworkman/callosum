"""Deterministic, offline partial-answer renderer for the c9+c11 vertical slice (2026-09-27).

Renders directly from the contract-directed manifest (`overview_bridge`'s own row shape) and a SAVED Gate 2
overview record (e.g. `runs/gate2-diagnostic-002/04_final_record.json`) -- never from a freshly-called model,
NLI, or embedding scorer. Both inputs are read, never mutated.

**Why this is a new, separate module rather than a call into `ledger_renderer.py`:** confirmed directly (not
assumed) that `ledger_renderer.validate_ledger` hard-requires `row["verification"]["status"] == "verified"` on
every proposition, or it raises `ValueError("terminal ledger contains ineligible evidence")` -- every one of
`render_ledger`/`render_responsive_ledger`/`render_answer` calls it first. `"verified"` there asserts a specific
thing contract-directed's own `derive_status` never computes: an NLI entailment check
(`app/backend/summarization/verification.py`'s support/contradiction scoring). Fabricating that status to pass
the gate would misrepresent what was actually established; weakening the gate would change what every other
caller of `ledger_renderer.py` can rely on. Both are out of scope. This module is the smallest necessary
integration boundary instead -- it reuses `ledger_renderer._literal` (pure Markdown-escaping; it asserts
nothing about evidence) and nothing else from that file.

**The three outcome states this renders, and only these three, never conflated:**

- ``source_supported_and_displayed`` -- the row's evidence produced an overview statement that survived
  screening in the saved run (`status == "grounded"`).
- ``unresolved`` -- a `genuinely_partial`/`unresolved_obligation` manifest row. Its `constraint_text` is shown
  verbatim. This is a coverage limit, never rendered as, or convertible to, a null finding or a claim that no
  evidence exists in the wider library.
- ``source_supported_overview_withheld`` -- the row's evidence is `source_supported`, but every overview
  candidate touching its matched unit(s) was withheld by screening (or none was ever produced). The underlying
  evidence is rendered in full, labeled as evidence; any withheld candidate is shown separately, explicitly
  labeled as withheld and never as displayed/approved output. `topical_only`/withheld is a screening outcome
  about a *later* stage, never evidence that the earlier, source-supported finding doesn't exist.

Matching a manifest row's `accepted_spans` to the saved record's overview units is by exact
``(paper_id, chunk_id, span_id)`` locator -- never by passage text (which the model may echo with cosmetic
changes) and never by unit_id alone (a `Un` id is an artifact of one specific run's own numbering).
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.ledger_renderer import _literal


def _child_sort_key(child_id: str) -> tuple[int, str]:
    """Canonical child order (`freeze.CHILD_IDS`, e.g. c9 before c11) rather than ASCII string order (which
    would put "c11" before "c9", since "1" < "9")."""
    try:
        return (freeze.CHILD_IDS.index(child_id), child_id)
    except ValueError:
        return (len(freeze.CHILD_IDS), child_id)


SOURCE_SUPPORTED = "source_supported"
NON_CLAIMABLE_STATUSES = ("genuinely_partial", "unresolved_obligation", "relevance_rejected", "relevance_disputed")

DISPLAYED = "source_supported_and_displayed"
WITHHELD = "source_supported_overview_withheld"
UNRESOLVED = "unresolved"

_UNRESOLVED_NOTE = (
    "This is a coverage limit on the admitted evidence, not a null finding: it does not claim the relationship "
    "does not exist, and it says nothing about whether the wider library holds evidence for it."
)
_WITHHELD_NOTE = (
    "This candidate did not survive screening in the saved run. Withholding is a screening outcome about this "
    "later stage; it is not evidence that the underlying, source-supported finding above does not exist."
)
_HEADER = (
    "# Partial answer -- two children only (deliberately incomplete)\n\n"
    "This renders exactly two request items (c9 and c11) from already-verified evidence and a single saved "
    "overview run. It does not answer the original parent question, does not include c6, c5, or c10, and "
    "certifies nothing about completeness. Three states are kept separate throughout: what the source evidence "
    "supports, what the overview stage displayed after screening, and what the overview stage withheld -- a "
    "withheld candidate is never shown as approved output, and a source-supported finding is never hidden just "
    "because its overview candidate was withheld.\n"
)


def _locator(span: dict) -> tuple[int, int, str]:
    return (span["paper_id"], span["chunk_id"], span["span_id"])


def match_units_by_locator(manifest_rows: list[dict], saved_units: list[dict]) -> dict[tuple[str, str], list[str]]:
    """``{(child_id, unit_id): [matched Un ids]}`` for every manifest row with `accepted_spans` -- exact-locator
    matched against the saved run's own `units[].locators`, never by passage text or by trusting a `Un` number
    to mean the same thing across two different runs."""
    locator_to_un: dict[tuple[int, int, str], str] = {}
    for unit in saved_units:
        for locator in unit["locators"]:
            key = (unit["paper_id"], locator["chunk_id"], locator["span_id"])
            locator_to_un[key] = unit["unit_id"]
    out: dict[tuple[str, str], list[str]] = {}
    for row in manifest_rows:
        matched = []
        for span in row.get("accepted_spans", []):
            un = locator_to_un.get(_locator(span))
            if un is not None and un not in matched:
                matched.append(un)
        out[(row["child_id"], row["unit_id"])] = matched
    return out


def _proposals_touching(unit_ids: list[str], proposals: list[dict]) -> list[dict]:
    unit_id_set = set(unit_ids)
    return [p for p in proposals if unit_id_set & set(p["unit_ids"])]


def classify_row(row: dict, matched_units: list[str], proposals: list[dict]) -> dict:
    """One manifest row's full classification -- everything a renderer or a test needs, nothing inferred beyond
    what the manifest and the saved record already state."""
    base = {
        "child_id": row["child_id"],
        "unit_id": row["unit_id"],
        "kind": row["kind"],
        "manifest_status": row["status"],
        "matched_overview_unit_ids": matched_units,
        "evidence_spans": list(row.get("accepted_spans", [])),
        "constraint_text": row.get("constraint_text"),
    }
    if row["status"] in NON_CLAIMABLE_STATUSES:
        return {**base, "outcome": UNRESOLVED, "displayed_statement": None, "withheld_candidates": []}

    touching = _proposals_touching(matched_units, proposals) if matched_units else []
    grounded = [p for p in touching if p["status"] == "grounded"]
    withheld = [p for p in touching if p["status"] == "withheld"]
    if grounded:
        return {**base, "outcome": DISPLAYED, "displayed_statement": grounded[0], "withheld_candidates": withheld}
    return {**base, "outcome": WITHHELD, "displayed_statement": None, "withheld_candidates": withheld}


def build_classifications(manifest_rows: list[dict], gate2_record: dict) -> list[dict]:
    matches = match_units_by_locator(manifest_rows, gate2_record["units"])
    return [
        classify_row(row, matches[(row["child_id"], row["unit_id"])], gate2_record["proposals"])
        for row in manifest_rows
    ]


def _evidence_block(spans: list[dict]) -> list[str]:
    lines = []
    for span in spans:
        lines.append(
            f"Evidence (verbatim, paper {span['paper_id']}, chunk {span['chunk_id']}, span {span['span_id']}):"
        )
        lines.append("> " + _literal(span["text"]))
        lines.append(
            "Verification (not NLI-verified -- a different, deterministic assertion): "
            f"exact_verbatim_match={span.get('attribution_state') is not None}, "
            f"clause_attribution_state={span.get('attribution_state')}, "
            f"slot_accepted_for={span.get('slots_accepted_for', [])}, nli_entailment_checked=False."
        )
        lines.append("")
    return lines


def render_partial_slice(manifest_rows: list[dict], gate2_record: dict) -> tuple[str, dict]:
    """``(markdown, manifest)`` -- mirrors `ledger_renderer`'s own `(text, manifest)` return convention, without
    calling any of its code beyond `_literal`."""
    classifications = build_classifications(manifest_rows, gate2_record)
    by_child: dict[str, list[dict]] = {}
    for c in classifications:
        by_child.setdefault(c["child_id"], []).append(c)

    lines = [_HEADER]
    for child_id in sorted(by_child, key=_child_sort_key):
        lines.append(f"## {child_id}\n")
        for c in by_child[child_id]:
            if c["outcome"] == DISPLAYED:
                stmt = c["displayed_statement"]
                lines.append(f"### {c['unit_id']} -- {c['kind']} (source-supported; overview statement displayed)\n")
                lines += _evidence_block(c["evidence_spans"])
                lines.append("Displayed overview statement (screened, grounded):")
                lines.append("> " + _literal(stmt["text"]))
                lines.append(f"Cites: {stmt['unit_ids']}; bears_on: {stmt['bears_on']}.\n")
            elif c["outcome"] == WITHHELD:
                lines.append(
                    f"### {c['unit_id']} -- {c['kind']} (source-supported; overview candidate WITHHELD by screening)\n"
                )
                lines += _evidence_block(c["evidence_spans"])
                for w in c["withheld_candidates"]:
                    lines.append("Raw overview candidate (WITHHELD -- NOT approved or displayed output):")
                    lines.append("> " + _literal(w["text"]))
                    lines.append(f"Screening reasons: {w['reasons']}.")
                if not c["withheld_candidates"]:
                    lines.append("No overview candidate was produced for this evidence in the saved run.")
                lines.append(_WITHHELD_NOTE + "\n")
            else:  # UNRESOLVED
                lines.append(
                    f"### {c['unit_id']} -- {c['kind']} (UNRESOLVED -- not established by the admitted evidence)\n"
                )
                lines.append("> " + _literal(c["constraint_text"] or ""))
                lines.append(_UNRESOLVED_NOTE + "\n")
    markdown = "\n".join(lines).rstrip() + "\n"

    manifest = {
        "mode": "partial-answer-v1",
        "children_covered": sorted(by_child, key=_child_sort_key),
        "classifications": classifications,
        "completeness": "not_certified",
        "excluded_children": ["c5", "c6", "c10"],
        "scientific_aggregates": 0,
    }
    return markdown, manifest
