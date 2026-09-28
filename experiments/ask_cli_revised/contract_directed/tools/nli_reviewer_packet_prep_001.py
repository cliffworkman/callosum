"""Blinded candidate-review packet: preparation and leakage audit (2026-09-28 authorization).

Builds a reviewer-ready, distribution-safe version of `nli-candidate-reliability-study-001`'s 9-item
inventory WITHOUT touching that directory's original draft packet, identity map, or protocol -- this is a
separately versioned, additive package under a new run directory. **No inference call anywhere in this
module; no label is collected here.**

Four things the original draft got wrong or left under-specified, fixed here:

1. **Paper ID leaked by default.** The original `01_blinded_reviewer_packet_draft.json` included
   `source_papers` on every item; the protocol document itself says a reviewer should get it only on request,
   to resolve genuine ambiguity. This module's reviewer-facing packet omits it by default and adds an
   explicit, logged context-request path (`request_context`) instead.
2. **`blind_id` was sorted by `pair_sha256`, not concealed.** A coordinator who saw the inventory's own
   pair_sha256 order could trivially recover which item was which. `concealed_randomization` replaces the
   sort-order IDs with a seeded, reproducible SHUFFLE and opaque random-alphabet codes.
3. **No variant-family accounting.** Three of the 9 items are near-duplicate "variants" of the same
   underlying candidate (c9's marker/no-marker pair, c11's two near-identical scoring runs, {U2,U6}'s
   truncated/untruncated pair) -- derived here directly from each pair's own `related_variant` field
   (`nli_candidate_pair_inventory.py`'s own verified classification, never re-hardcoded), so a reviewer
   assignment can be designed to keep each family split across different reviewers.
4. **The labeling protocol's own c11 worked example is reviewer-visible content.** It must never appear in
   anything a reviewer actually receives -- this module's reviewer instruction sheet uses new, neutral,
   unrelated toy examples instead (see `reviewer_instruction_sheet_markdown`).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from experiments.ask_cli_revised.contract_directed.tools import nli_candidate_pair_inventory as inv_tool

RUNS_DIR = inv_tool.CONTRACT_DIRECTED_RUNS
EVAL_DIR = RUNS_DIR / "nli-candidate-reliability-review-prep-001"

# Fixed, documented, reproducible seeds. Changing any of these produces a DIFFERENT concealed order/assignment
# and would require a fresh authorized version -- they are not meant to be tuned casually.
RANDOM_SEED_ORDER = 20260928
RANDOM_SEED_FALLBACK_R1 = 20260928001
RANDOM_SEED_FALLBACK_R2 = 20260928002

_OPAQUE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L -- avoids transcription ambiguity


# ---------------------------------------------------------------------------------------------------------
# 1. Variant families and the broader unit-overlap note
# ---------------------------------------------------------------------------------------------------------


def identify_variant_families(pairs: list[dict]) -> dict:
    """A family = 2+ distinct pairs sharing the SAME unit_ids (the same evidentiary premise), regardless of
    how similar their hypothesis text is. The inventory's own `related_variant` field alone is too narrow to
    use directly here: it is only populated for a BYTE-LEVEL near-duplicate (one hypothesis a verified
    truncation or marker-difference of the other) -- confirmed empirically that it is `null` for c11's own
    two candidate-level pairs (`gate2-diagnostic-002` vs. `gate-integration-live-002`), because those two
    hypotheses are independently paraphrased, not a prefix of each other, even though they score the same
    premise and are unmistakably "closely related candidates" -- exactly what this authorization named.
    Grouping by `unit_ids` catches c11's pair correctly as well as the two byte-level cases."""
    by_unit_ids: dict[tuple, list[dict]] = {}
    for p in pairs:
        by_unit_ids.setdefault(tuple(p["unit_ids"]), []).append(p)

    families = []
    singleton_pair_sha256 = []
    for members in by_unit_ids.values():
        if len(members) < 2:
            singleton_pair_sha256.append(members[0]["pair_sha256"])
            continue
        # prefer the more specific verified byte-level classification when one fired; otherwise this pair is
        # still a family by the same-premise criterion, just not a byte-level near-duplicate.
        kind = next(
            (m["related_variant"]["kind"] for m in members if m["related_variant"]), "same_premise_multiple_scorings"
        )
        families.append({"kind": kind, "member_pair_sha256": sorted(m["pair_sha256"] for m in members)})
    return {"families": families, "singleton_pair_sha256": singleton_pair_sha256}


def extended_unit_overlap_note(pairs: list[dict]) -> dict:
    """Beyond the 3 formal related-variant families (identical or near-identical premise+hypothesis), several
    OTHER pairs in this population still share a constituent evidence UNIT even though their unit_id sets
    differ as a whole -- a softer, harder-to-fully-eliminate recognition risk. Not a formal family requiring
    hard separation; reported here as a coordinator-only limitation note, never shown to reviewers."""
    unit_to_shas: dict[str, set[str]] = {}
    for p in pairs:
        for uid in p["unit_ids"]:
            unit_to_shas.setdefault(uid, set()).add(p["pair_sha256"])
    return {uid: sorted(shas) for uid, shas in unit_to_shas.items() if len(shas) > 1}


# ---------------------------------------------------------------------------------------------------------
# 2. Concealed, reproducible randomization and opaque IDs
# ---------------------------------------------------------------------------------------------------------


def concealed_randomization(pairs: list[dict], seed: int = RANDOM_SEED_ORDER) -> list[dict]:
    """A seeded, reproducible shuffle of the 9 pairs plus opaque IDs that encode nothing about source, run,
    question, score, status, family, or the original inventory's own pair_sha256 sort order. Same seed ->
    identical order and identical IDs every time; "reproducible," not "secret" -- the seed itself is
    documented in this module, and re-running this function is how a coordinator audits the mapping."""
    rng = random.Random(seed)
    shuffled = list(pairs)
    rng.shuffle(shuffled)
    ids: list[str] = []
    seen_ids: set[str] = set()
    while len(ids) < len(shuffled):
        code = "RV-" + "".join(rng.choice(_OPAQUE_ALPHABET) for _ in range(4))
        if code not in seen_ids:
            seen_ids.add(code)
            ids.append(code)
    return [{"opaque_id": oid, **pair} for oid, pair in zip(ids, shuffled, strict=True)]


# ---------------------------------------------------------------------------------------------------------
# 3. Reviewer-facing packet (no forbidden fields) and the context-request path
# ---------------------------------------------------------------------------------------------------------

_REVIEWER_ALLOWED_KEYS = frozenset({"opaque_id", "premise", "candidate_statement"})


def build_reviewer_packet(ordered_pairs: list[dict]) -> list[dict]:
    """Exactly what a reviewer receives: opaque_id, verbatim premise, verbatim historically-scored candidate
    text -- nothing else. No source paper id, no run/source identity, no NLI/status/screening field. The
    exact scored hypothesis is preserved byte-for-byte (including any inline unit-citation marker like c9's
    own "(U1)") -- this module never edits candidate text."""
    return [
        {"opaque_id": p["opaque_id"], "premise": p["premise"], "candidate_statement": p["hypothesis"]}
        for p in ordered_pairs
    ]


def build_coordinator_map(ordered_pairs: list[dict], families: dict) -> list[dict]:
    """Coordinator-only: opaque_id -> full real identity, plus which family (if any) an item belongs to.
    Never distributed to reviewers."""
    family_of: dict[str, str] = {}
    for i, fam in enumerate(families["families"], start=1):
        label = f"family_{i}_{fam['kind']}"
        for sha in fam["member_pair_sha256"]:
            family_of[sha] = label
    return [
        {
            "opaque_id": p["opaque_id"],
            "pair_sha256": p["pair_sha256"],
            "source_id": p["source_id"],
            "index_in_source": p["index_in_source"],
            "unit_ids": p["unit_ids"],
            "paper_ids": sorted({loc["paper_id"] for loc in p["canonical_locators"]}),
            "family": family_of.get(p["pair_sha256"]),
        }
        for p in ordered_pairs
    ]


class ContextRequestLog:
    """Coordinator-side record of every context disclosure: what was disclosed, to whom, for which item, and
    why. A reviewer never sees this log; it exists so a disclosure is auditable after the fact."""

    def __init__(self):
        self.entries: list[dict] = []

    def request_context(self, coordinator_map: list[dict], opaque_id: str, reviewer_label: str, reason: str) -> dict:
        """The only sanctioned way a reviewer's genuine ambiguity gets more information: the coordinator
        looks up the ONE item's paper id (never NLI/status/screening data, which this function structurally
        cannot return -- it isn't in `coordinator_map`'s exposed shape) and logs the disclosure."""
        match = next((row for row in coordinator_map if row["opaque_id"] == opaque_id), None)
        if match is None:
            raise KeyError(f"unknown opaque_id: {opaque_id}")
        disclosure = {"opaque_id": opaque_id, "paper_ids": match["paper_ids"]}
        self.entries.append(
            {
                "opaque_id": opaque_id,
                "reviewer": reviewer_label,
                "reason": reason,
                "disclosed": disclosure,
            }
        )
        return disclosure


def context_disclosure_log_template() -> dict:
    """A blank, distributable schema for the disclosure log -- the coordinator's own working copy starts
    from this shape."""
    return {
        "schema": {
            "opaque_id": "the item this request concerns",
            "reviewer": "which reviewer requested it (a label, never a name tied to their label if avoidable)",
            "reason": "the reviewer's own stated reason the premise/candidate text left something ambiguous",
            "disclosed": "exactly what was given back -- paper_ids only; never an NLI/status/screening field",
        },
        "entries": [],
    }


# ---------------------------------------------------------------------------------------------------------
# 4. Reviewer assignment: the two options
# ---------------------------------------------------------------------------------------------------------


def build_variant_separated_assignment(ordered_pairs: list[dict]) -> dict:
    """Preferred design: minimum 4 reviewers, none of whom ever sees both members of any family. Two
    reviewers rate every family's "first" half plus roughly half the singles; the other two rate every
    family's "second" half plus the remaining singles. Every item ends up rated by exactly 2 reviewers."""
    fam_info = identify_variant_families(ordered_pairs)
    families, singles = fam_info["families"], fam_info["singleton_pair_sha256"]

    variant1 = [f["member_pair_sha256"][0] for f in families]
    variant2 = [f["member_pair_sha256"][1] for f in families]

    half = (len(singles) + 1) // 2
    singles_13, singles_24 = singles[:half], singles[half:]

    sha_to_opaque = {p["pair_sha256"]: p["opaque_id"] for p in ordered_pairs}
    to_ids = lambda shas: [sha_to_opaque[s] for s in shas]  # noqa: E731

    assignment = {
        "R1": to_ids(variant1) + to_ids(singles_13),
        "R2": to_ids(variant1) + to_ids(singles_24),
        "R3": to_ids(variant2) + to_ids(singles_13),
        "R4": to_ids(variant2) + to_ids(singles_24),
    }
    coverage: dict[str, int] = {}
    for items in assignment.values():
        for oid in items:
            coverage[oid] = coverage.get(oid, 0) + 1

    return {
        "min_reviewers": 4,
        "assignment": assignment,
        "coverage_per_item": coverage,
        "families": families,
        "singleton_pair_sha256": singles,
    }


def _spaced_single_order(
    ordered_pairs: list[dict], families: list[dict], singles: list[str], rng: random.Random
) -> list[str]:
    """A deterministic slot pattern (positions 0,2,4 = a family's "first" member; 1,3,5 = a single; 6,7,8 =
    the SAME families' "second" members) guarantees every family's two members are at least 4 slots apart,
    while which family/single/member lands in which slot is genuinely randomized per call. This is a spacing
    HEURISTIC for one reviewer's own item order -- it reduces adjacency, it does not remove either member
    from that reviewer's packet (see the two-reviewer fallback's own documented limitation below)."""
    if len(families) != 3 or len(singles) != 3:
        raise ValueError("this slot pattern is specific to today's population shape: 3 families + 3 singles")
    sha_to_opaque = {p["pair_sha256"]: p["opaque_id"] for p in ordered_pairs}

    fam_list = list(families)
    rng.shuffle(fam_list)
    single_list = list(singles)
    rng.shuffle(single_list)

    firsts, seconds = [], []
    for fam in fam_list:
        members = list(fam["member_pair_sha256"])
        rng.shuffle(members)
        firsts.append(members[0])
        seconds.append(members[1])

    slot_order_shas = [
        firsts[0], single_list[0], firsts[1], single_list[1], firsts[2], single_list[2],
        seconds[0], seconds[1], seconds[2],
    ]  # fmt: skip
    return [sha_to_opaque[s] for s in slot_order_shas]


def build_two_reviewer_fallback_assignment(ordered_pairs: list[dict]) -> dict:
    """Fallback design: only 2 reviewers, each rating the FULL 9-item packet in a separately randomized,
    family-spaced order. This guarantees exactly 2 ratings per item but CANNOT prevent either reviewer from
    eventually encountering both members of every family -- both are in their own 9-item packet by
    construction. Spacing reduces immediate adjacency; it does not, and is never described as, separation."""
    fam_info = identify_variant_families(ordered_pairs)
    families, singles = fam_info["families"], fam_info["singleton_pair_sha256"]

    r1_order = _spaced_single_order(ordered_pairs, families, singles, random.Random(RANDOM_SEED_FALLBACK_R1))
    r2_order = _spaced_single_order(ordered_pairs, families, singles, random.Random(RANDOM_SEED_FALLBACK_R2))

    return {
        "min_reviewers": 2,
        "R1_order": r1_order,
        "R2_order": r2_order,
        "families": families,
        "limitation": (
            "Every family's both members appear in BOTH reviewers' own 9-item packets. Random, spaced order "
            "lowers the chance either notices the repetition while working through the list, but it is not a "
            "separation guarantee -- record any reviewer-noticed repetition as a design limitation on the "
            "affected item's response, not as a blinding failure specific to that reviewer."
        ),
    }


# ---------------------------------------------------------------------------------------------------------
# 5. Blank response form
# ---------------------------------------------------------------------------------------------------------

LABEL_VOCABULARY = ("Entailed", "Contradicted", "Not established", "Ambiguous or unjudgeable", "Mixed or composite")
CONFIDENCE_LEVELS = ("low", "medium", "high")


def response_form_schema() -> dict:
    """The blank shape every reviewer response fills in. `locked` starts false; a coordinator only compares
    two reviewers' responses on the same item once BOTH are locked (see `can_reveal_peer_response`)."""
    return {
        "opaque_id": "string, required",
        "atomic_propositions": [{"text": "string", "label": list(LABEL_VOCABULARY)}],
        "overall_label": list(LABEL_VOCABULARY),
        "confidence": list(CONFIDENCE_LEVELS),
        "reason": "string, required -- brief, source-grounded",
        "context_requested": {"requested": "boolean", "reason": "string, required if requested=true"},
        "locked": False,
    }


def blank_response(opaque_id: str) -> dict:
    return {
        "opaque_id": opaque_id,
        "atomic_propositions": [],
        "overall_label": None,
        "confidence": None,
        "reason": "",
        "context_requested": {"requested": False, "reason": ""},
        "locked": False,
    }


def can_reveal_peer_response(response_a: dict, response_b: dict) -> bool:
    """Structural blinding boundary: a peer's response is revealable only once BOTH responses are locked."""
    return bool(response_a.get("locked")) and bool(response_b.get("locked"))


# ---------------------------------------------------------------------------------------------------------
# 6. Reviewer-facing instruction sheet -- NEW, neutral, unrelated-to-the-9-items examples only
# ---------------------------------------------------------------------------------------------------------


def reviewer_instruction_sheet_markdown() -> str:
    return """# Candidate-review task instructions

You will read a series of numbered items. Each item has a **premise** (a passage from a source) and a
**candidate statement** (a claim proposed as following from that premise). Your task: judge whether the
premise entails the candidate statement.

## What you are judging

Only whether the candidate statement follows from the premise -- not whether the candidate statement is a
*complete* answer to any larger question, not whether the source itself is correct or well-designed. Take the
premise as given; ask only whether the candidate follows from it.

## A note on inline citation markers

Some candidate statements end with a short parenthetical like "(U3)" or "(U6, U9)". This is attribution metadata
-- it marks which passage a sentence is drawn from -- not a numerical or scientific claim. Do not treat it as
an assertion to evaluate.

## Labels

- **Entailed** -- a reader who accepts the premise as true must accept the candidate statement as true.
- **Contradicted** -- the premise, read plainly, asserts something incompatible with the candidate statement.
- **Not established** -- the premise neither affirms nor denies the candidate statement's specific claim; the
  candidate goes beyond what the premise says. This is different from Contradicted: the premise being *silent*
  on a claim is not the same as the premise *denying* it.
- **Ambiguous or unjudgeable** -- you cannot form a confident judgment even after reading the available
  context. This is a legitimate final answer. Do not feel pressed to pick a definite label if the text
  genuinely does not support one.
- **Mixed or composite** -- the candidate statement bundles more than one distinct claim and they do not all
  get the same label. When this applies, list each claim separately (see "Breaking a candidate into parts"
  below) and label each one.

## Breaking a candidate into parts

Before labeling, restate the candidate statement as a numbered list of its individual claims -- each one a
single checkable fact (one relationship, one comparison, one quantity). If the candidate already makes exactly
one claim, your list has one item.

**Worked example (illustrative only -- not one of the items you will review):**

> Premise: "The cafe's espresso machine was recalibrated in March after staff noticed inconsistent shot
> timing. Since then, extraction times have stayed within the target window on every logged shot."
>
> Candidate: "The espresso machine was recalibrated in March, and extraction times have been perfectly
> consistent ever since, with no variation at all."

Breaking this into parts:
1. The espresso machine was recalibrated in March. *(Entailed -- the premise says this directly.)*
2. Extraction times have been perfectly consistent since, with no variation at all. *(Not established -- the
   premise says shot timing stayed "within the target window," which is a claim about a bounded range, not
   about zero variation. "No variation at all" goes beyond what the premise supports.)*

Overall label: **Mixed or composite** (one claim entailed, one not established) -- record both parts.

**A second worked example, showing the omission case:**

> Premise: "The trail was repaved last spring, and the new surface has held up well through two winters
> without cracking."
>
> Candidate: "The trail was repaved last spring."

The candidate simply doesn't repeat the premise's second claim about durability -- it isn't a false or
unsupported claim, it's just not made at all. **This is not grounds for "Not established."** The candidate's
one claim (repaved last spring) is straightforwardly entailed. Whether a candidate should have said more is a
separate question from whether what it does say is entailed -- it is outside this task.

## What to record for each item

1. Your atomic breakdown (a list of one or more claims), each with its own label.
2. An overall label for the item.
3. Your confidence: low, medium, or high.
4. A brief, source-grounded reason for your judgment.
5. If a name, abbreviation, or reference in the premise or candidate is genuinely unclear and you cannot
   judge the item without more context, note what you need and why -- a coordinator may be able to supply
   narrowly relevant context (see "Requesting context" below). Do not guess at unstated facts to force a
   judgment.

## Requesting context

If an item is genuinely unjudgeable as written (an unresolved abbreviation, an ambiguous pronoun, a reference
you cannot place), you may ask your coordinator for narrowly relevant context about that one item. State what
you need and why. Your coordinator will log what was (and was not) provided. You will not be given any scoring
information, source identity beyond what you specifically asked to resolve, or any other item's content.

## Working independently

Complete your judgments on your own, without discussing specific items with another reviewer, before
submitting. You will not see another reviewer's judgments before your own are recorded.
"""


# ---------------------------------------------------------------------------------------------------------
# 7. Coordinator collection/adjudication procedure (markdown)
# ---------------------------------------------------------------------------------------------------------


def coordinator_procedure_markdown() -> str:
    return """# Coordinator-facing collection and adjudication procedure

## Before distribution

1. Confirm which assignment design is in use (variant-separated, 4 reviewers; or the 2-reviewer fallback) and
   who is filling each reviewer slot.
2. Distribute ONLY: the reviewer instruction sheet, and each reviewer's own item packet (their own `premise`
   + `candidate_statement` + `opaque_id` per item, in their own assigned order). Never distribute the
   coordinator map, the family list, the disclosure log, or the original inventory/identity-map files from
   `nli-candidate-reliability-study-001/`.

## Collecting responses

3. Each reviewer completes their packet independently and submits. Mark each submitted response `locked` the
   moment it is received -- do not allow edits after locking without a recorded reason.
4. A context request during review is answered via `ContextRequestLog.request_context` -- log it immediately,
   disclose only what was asked for (never NLI/status/screening data, which this path cannot return), and
   continue.

## After both initial ratings are locked, per item

5. If both reviewers' labels agree (same overall label, or the same set of atomic labels under Mixed or
   composite): the label stands. Record it as agreed, no further action.
6. If they disagree: show each reviewer the other's label and reasoning (never any NLI/screening/self-pair
   information) and ask them to either (a) converge, with a joint note on what changed their mind, or (b)
   record the disagreement as unresolved, preserving both original labels. Do not break a disagreement by
   coordinator fiat or by an automatic majority rule among only two raters.
7. Only after every item's initial ratings are locked and reconciled (agreed, converged, or recorded
   unresolved) does the coordinator rejoin the opaque IDs to the real identity map
   (`build_coordinator_map`) to interpret results against source/self-pair-stratum context.

## Reporting

8. Report, per item: the opaque_id, both reviewers' locked initial labels, the reconciliation outcome
   (agreed / converged / unresolved), confidence levels, and any context request. Only after this is complete
   does a report reference the item's real pair identity, self-pair stratum, or original NLI outcome --
   reusing the language from `NLI_CANDIDATE_LEVEL_LABELING_PROTOCOL.md` §6 on what counts as independent.
9. Do not claim an inter-rater reliability statistic from fewer than 2 independent raters per item. With only
   1 rater available for an item, report its single label as exactly that -- one rating, not agreement.
"""


# ---------------------------------------------------------------------------------------------------------
# 8. Protected-directory guard (extends the inventory tool's own frozenset, never redefines it)
# ---------------------------------------------------------------------------------------------------------

# Inherit the inventory tool's own frozenset (which, by this point, ALSO protects this module's own EVAL_DIR
# -- inv_tool.py was updated to know about it once this directory started existing). Explicitly subtract our
# own directory back out: a tool never protects its own output directory from itself, and blindly inheriting
# a union that had grown to include it would otherwise make this module unable to write its own artifacts.
PROTECTED_RUN_DIRS = (inv_tool.PROTECTED_RUN_DIRS | {"nli-candidate-reliability-study-001"}) - {EVAL_DIR.name}


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
    inv = inv_tool.build_full_inventory()
    ordered = concealed_randomization(inv["pairs"])
    families = identify_variant_families(ordered)
    overlap_note = extended_unit_overlap_note(ordered)

    reviewer_packet = build_reviewer_packet(ordered)
    coordinator_map = build_coordinator_map(ordered, families)
    variant_separated = build_variant_separated_assignment(ordered)
    two_reviewer_fallback = build_two_reviewer_fallback_assignment(ordered)

    write_artifact(EVAL_DIR, "10_reviewer_instructions.md", reviewer_instruction_sheet_markdown())
    write_artifact(EVAL_DIR, "11_reviewer_packet.json", {"items": reviewer_packet})
    write_artifact(EVAL_DIR, "12_response_form_schema.json", response_form_schema())
    write_artifact(
        EVAL_DIR,
        "20_coordinator_identity_and_family_map_DO_NOT_SHOW_REVIEWERS.json",
        {"items": coordinator_map, "extended_unit_overlap_note": overlap_note},
    )
    write_artifact(EVAL_DIR, "21_assignment_variant_separated_DO_NOT_SHOW_REVIEWERS.json", variant_separated)
    write_artifact(EVAL_DIR, "22_assignment_two_reviewer_fallback_DO_NOT_SHOW_REVIEWERS.json", two_reviewer_fallback)
    write_artifact(
        EVAL_DIR, "23_context_disclosure_log_template_DO_NOT_SHOW_REVIEWERS.json", context_disclosure_log_template()
    )
    write_artifact(EVAL_DIR, "24_coordinator_procedure.md", coordinator_procedure_markdown())

    print(f"Wrote reviewer-ready package to {EVAL_DIR}")
    print(f"Families: {len(families['families'])}  Singletons: {len(families['singleton_pair_sha256'])}")
    print(f"Extended unit-overlap units: {sorted(overlap_note.keys())}")
