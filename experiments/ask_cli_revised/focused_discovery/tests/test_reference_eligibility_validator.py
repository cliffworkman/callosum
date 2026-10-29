"""T8 (synthetic): the independent validator distinguishes every finding class without one masking another."""

from __future__ import annotations

import hashlib

from app.backend.summarization.evidence_eligibility import AnchoredState, KeyedText, NativeCoverage, decide, map_region
from experiments.ask_cli_revised.focused_discovery.reference_eligibility import continuation_flags, validate_claims

REFERENCE = (
    "11. Benjamin S, Steffens DC: Structural neuroimaging of geriatric depression. Psychiatr Clin North Am 2011."
)
PROSE = "Hippocampal volume was smaller in late-life depression than in controls across both cohorts studied here."
MIXED = PROSE + " " + REFERENCE


def record(sid, text, unit, role="prose_or_other", tamper=False):
    digest = hashlib.sha256((text + ("x" if tamper else "")).encode()).hexdigest()
    return {
        "source_id": sid,
        "text": text,
        "text_sha256": digest,
        "original_unit_namespace": "legacy_chunk",
        "internal_unit_id": unit,
        "source_role": role,
    }


ABSENT = AnchoredState("absent")


def decision(unit, text, *, reference_region=None, anchored=ABSENT):
    keyed = KeyedText.build(str(unit), text)
    matches = []
    if reference_region:
        _, match = map_region(KeyedText.build("#/texts/9/segment/0", reference_region), "exclude_reference", keyed)
        matches.append(match)
    return decide(
        str(unit), key_length=len(keyed.key), native=NativeCoverage(len(keyed.key), matches), anchored=anchored
    )


EVIDENCE = {
    "Sref": record("Sref", REFERENCE, 1),
    "Sprose": record("Sprose", PROSE, 2),
    "Sdisp": record("Sdisp", PROSE, 3),
    "Smixed": record("Smixed", MIXED, 4),
    "Sstale": record("Sstale", PROSE, 5),
    "Stamper": record("Stamper", PROSE, 6, tamper=True),
    "Shead": record("Shead", PROSE, 7, role="page_header"),
    "Sunknown": record("Sunknown", PROSE, 8),
}
AUTHORITY = {
    ("legacy_chunk", "1"): decision(1, REFERENCE, reference_region=REFERENCE).as_record(),
    ("legacy_chunk", "2"): decision(2, PROSE).as_record(),
    ("legacy_chunk", "3"): decision(3, PROSE, anchored=AnchoredState("current_bibliographic", 1.0)).as_record(),
    ("legacy_chunk", "4"): decision(4, MIXED, reference_region=REFERENCE).as_record(),
    ("legacy_chunk", "5"): decision(
        5, PROSE, anchored=AnchoredState("stale", 0.0, {"stale_reason": "text_hash"})
    ).as_record(),
    ("legacy_chunk", "6"): decision(6, PROSE).as_record(),
    ("legacy_chunk", "7"): decision(7, PROSE).as_record(),
}


def kinds(claim):
    return sorted(f["finding"] for f in validate_claims({"claims": [claim]}, EVIDENCE, AUTHORITY))


def test_provenance_findings_are_distinct() -> None:
    assert kinds({"claim_id": "c", "citations": [""]}) == ["missing_source_id"]
    assert kinds({"claim_id": "c", "citations": ["Snope"]}) == ["source_not_delivered"]
    assert kinds({"claim_id": "c", "citations": ["Stamper"]}) == ["text_identity_mismatch"]
    assert kinds({"claim_id": "c", "citations": ["Sunknown"]}) == ["eligibility_unresolved"]
    assert kinds({"claim_id": "c", "citations": ["Sstale"]}) == ["classification_stale"]


def test_withheld_disputed_and_incompatible_role_are_different_classes() -> None:
    assert kinds({"claim_id": "c", "citations": ["Sref"]}) == ["ineligible_source_cited"]
    assert kinds({"claim_id": "c", "citations": ["Sdisp"]}) == ["disputed_eligibility_cited"]
    assert kinds({"claim_id": "c", "citations": ["Shead"]}) == ["incompatible_source_role"]
    assert kinds({"claim_id": "c", "citations": ["Sprose"]}) == []


def test_inexact_quote_never_hides_an_eligibility_violation() -> None:
    exact = {"claim_id": "c", "source_quotes": [{"source_id": "Sref", "quote": "Structural neuroimaging of geriatric"}]}
    assert kinds(exact) == ["exact_quote_from_ineligible_source"]
    inexact = {"claim_id": "c", "source_quotes": [{"source_id": "Sref", "quote": "neuroimaging shows atrophy"}]}
    assert kinds(inexact) == ["inexact_quotation", "inexact_quote_attributed_to_ineligible_source"]
    disputed = {"claim_id": "c", "source_quotes": [{"source_id": "Sdisp", "quote": "made-up words"}]}
    assert kinds(disputed) == ["inexact_quotation", "quote_from_disputed_source"]


def test_quote_into_the_excluded_span_of_a_mixed_unit_is_a_violation_but_the_prose_part_is_not() -> None:
    assert AUTHORITY[("legacy_chunk", "4")]["substantive_eligibility"] == "eligible"
    bad = {"claim_id": "c", "source_quotes": [{"source_id": "Smixed", "quote": "Structural neuroimaging of geriatric"}]}
    assert kinds(bad) == ["exact_quote_inside_excluded_span"]
    good = {"claim_id": "c", "source_quotes": [{"source_id": "Smixed", "quote": "Hippocampal volume was smaller"}]}
    assert kinds(good) == []


def test_continuation_flag_marks_only_sandwiched_included_regions() -> None:
    regions = [
        {"id": "r1", "retrieval_decision": "exclude_reference"},
        {"id": "nav", "retrieval_decision": "retain_navigation"},
        {"id": "r2", "retrieval_decision": "include_provisional"},
        {"id": "r3", "retrieval_decision": "exclude_reference"},
        {"id": "r4", "retrieval_decision": "include_provisional"},
        {"id": "r5", "retrieval_decision": "include_provisional"},
    ]
    assert continuation_flags(regions) == {"r2"}
