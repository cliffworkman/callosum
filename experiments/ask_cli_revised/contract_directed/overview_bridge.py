"""Thin, additive bridge from contract-directed's own eligibility manifest to the shared overview stage's sealed-
ledger input shape (Gate 2 diagnostic, session 2026-09-27).

Builds ONLY what `overview.py` needs. Never modifies a contract-directed packet or `derive_status` result, and
never modifies `overview.py`/`overview_evidence.py`/`overview_guards.py` beyond the optional, backward-compatible
`coverage_constraints` parameter those modules already accept unchanged for every existing caller.

A manifest row is `{child_id, unit_id, kind, status, accepted_spans, constraint_text}`. `status` is one of
`SOURCE_SUPPORTED` (the only status ever projected as claimable evidence) or one of `NON_CLAIMABLE_STATUSES`
(`genuinely_partial` / `unresolved_obligation` / `relevance_rejected` / `relevance_disputed`), which may supply a
human-authored `constraint_text` -- a plain-language description of a LIMIT of the admitted evidence, never a
source passage, never a scientific finding of its own, and never sent unless it passes `validate_constraint_text`.
"""

from __future__ import annotations

import json
import re

from experiments.ask_cli_revised.contract_directed import freeze
from experiments.ask_cli_revised.hierarchy_contract import provenance_tokens

SOURCE_SUPPORTED = "source_supported"
NON_CLAIMABLE_STATUSES = ("genuinely_partial", "unresolved_obligation", "relevance_rejected", "relevance_disputed")

# Deliberately narrow and specific (not a bare "no"/"not" filter, which would reject legitimate hedged prose, and
# deliberately NOT a bare "no such X exists" pattern, which a correctly-hedged disclaimer legitimately negates --
# e.g. "not a finding that no such tie exists" -- so a naive substring match would wrongly reject the safe
# sentence). Each phrase here is instead a way of ASSERTING the negative finding outright: turning "not
# established by the admitted evidence" into "established to be absent" -- exactly the failure Cliff named ("do
# not turn the status into a claim that something was measured and found null"). A constraint that merely says
# something is "not established" passes; one that asserts the negative finding itself does not.
_BANNED_FINDING_PHRASES = re.compile(
    r"\b(?:measured and found|found to be absent|no relationship exists|no association exists|"
    r"no evidence exists|tested and found (?:absent|null|to be absent))\b",
    re.IGNORECASE,
)


class ConstraintTextInvalid(ValueError):
    """A coverage-constraint's model-facing text either leaks an internal provenance identifier (child/unit ids,
    clarification/decision ids, a raw sha256 -- see `hierarchy_contract.provenance_tokens`) or asserts a finding
    (that a relationship/effect was measured and found absent) rather than describing a limit of what the
    admitted evidence establishes. Raised before the text is ever rendered into a prompt."""


def validate_constraint_text(text: str) -> None:
    leaked = provenance_tokens(text)
    if leaked:
        raise ConstraintTextInvalid(f"constraint text leaks provenance token(s): {leaked}")
    banned = _BANNED_FINDING_PHRASES.search(text)
    if banned:
        raise ConstraintTextInvalid(f"constraint text asserts a finding, not a coverage limit: {banned.group(0)!r}")


def project_evidence(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """``(evidence_spans, verified_propositions)`` from every `source_supported` row's `accepted_spans` only.

    Never reads a spans list from a `genuinely_partial`/`unresolved_obligation`/`relevance_rejected`/
    `relevance_disputed` row -- those statuses never contribute claimable evidence, by construction (there is no
    code path here that could read their `accepted_spans` even if one were present on such a row).
    `proposition_text`/`quote` are always the identical, verbatim source span text -- this bridge never invents a
    paraphrase. `verification` never asserts NLI entailment, since contract-directed's own `derive_status` never
    computes one; it records only what was actually established (verbatim match, clause-level attribution state,
    which slots accepted the span).
    """
    evidence_spans: list[dict] = []
    verified_propositions: list[dict] = []
    seen_locators: set[tuple] = set()
    n = 0
    for row in rows:
        if row["status"] != SOURCE_SUPPORTED:
            continue
        for span in row["accepted_spans"]:
            locator = (span["paper_id"], span["chunk_id"], span["span_id"])
            if locator not in seen_locators:
                seen_locators.add(locator)
                evidence_spans.append(
                    {
                        "paper_id": span["paper_id"],
                        "chunk_id": span["chunk_id"],
                        "span_id": span["span_id"],
                        "text": span["text"],
                    }
                )
            n += 1
            verified_propositions.append(
                {
                    "proposition_id": f"p{n}",
                    "paper_id": span["paper_id"],
                    "evidence_anchor_chunk_id": span["chunk_id"],
                    "evidence_span_id": span["span_id"],
                    "proposition_text": span["text"],
                    "quote": span["text"],
                    "verification": {
                        "exact_verbatim_match": True,
                        "clause_attribution_state": span.get("attribution_state"),
                        "slot_accepted_for": list(span.get("slots_accepted_for", [])),
                        "nli_entailment_checked": False,
                    },
                    "responsive_obligation_ids": [row["child_id"]],
                }
            )
    return evidence_spans, verified_propositions


def coverage_constraints(rows: list[dict]) -> tuple[str, ...]:
    """Model-facing constraint strings, one per non-source_supported row that supplies `constraint_text`.

    Every string is validated (`validate_constraint_text`) before being returned; an invalid one raises rather
    than being silently dropped or silently sent. A row with no `constraint_text` contributes nothing (it is
    still excluded from `project_evidence`, but this bridge does not require every non-claimable row to carry a
    model-facing constraint).
    """
    out: list[str] = []
    for row in rows:
        if row["status"] not in NON_CLAIMABLE_STATUSES:
            continue
        text = row.get("constraint_text")
        if not text:
            continue
        validate_constraint_text(text)
        out.append(text)
    return tuple(out)


def available() -> bool:
    return (freeze.AB_ROOT / "runB" / "out" / "11_verified_ledger.json").is_file()


def real_obligation_states(field_ids: tuple[str, ...]) -> list[dict]:
    """The real, frozen ``field_id``/``note``/``state`` triples for the given children, read verbatim from the
    actual prior T5O run's own sealed ledger -- never invented or paraphrased.

    Carries exactly the three fields `overview.py` actually reads across its whole pipeline: `note` for the
    model-facing prompt (`render_part_lines`) and `state` for the post-response audit (`parts_status`'s
    `"no_responsive_evidence" if state["state"] != "not_assessed" else "not_assessed"` branch) -- omitting
    `state` is a real bug, not a harmless trim: `build_overview` raises `KeyError` reading it back, only after
    the one live call already happened, since `parts_status` runs last. The run's own richer per-field hierarchy
    detail is intentionally still not carried through.
    """
    path = freeze.AB_ROOT / "runB" / "out" / "11_verified_ledger.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    by_id = {s["field_id"]: s for s in data["obligation_states"]}
    missing = [fid for fid in field_ids if fid not in by_id]
    if missing:
        raise KeyError(f"field_id(s) not found in the real obligation_states: {missing}")
    return [{"field_id": fid, "note": by_id[fid]["note"], "state": by_id[fid]["state"]} for fid in field_ids]


def real_original_question() -> tuple[str, str]:
    """``(original_question, question_hash)``, read verbatim from the same frozen request contract this whole
    arc is built on. Raises if the file's own recorded hash no longer matches the frozen substrate's
    `freeze.QUESTION_SHA256` -- fail closed rather than silently use a drifted question.
    """
    path = freeze.AB_ROOT / "runB" / "out" / "01_request_contract.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["question_hash"] != freeze.QUESTION_SHA256:
        raise ValueError("the real request contract's question hash no longer matches the frozen substrate")
    return data["original_question"], data["question_hash"]
