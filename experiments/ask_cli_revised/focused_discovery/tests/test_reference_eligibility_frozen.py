"""Reference-exclusion repair against the FROZEN q_lld artifacts (read-only; skipped where they are absent).

Every fixture named by the 2026-10-28 investigation is exercised on its real frozen text: Marano chunks 28075/28079,
the Davies-Jenkins continuation units (a11 #/texts/130, #/texts/139), bracketed-numbering (a19) and glued-author
(a48) units, the documented anchored false positive S84f8688719ba478647, and the critical validation fixture
S6db56bec1dbc892a85. Databases are opened ``mode=ro&immutable=1``; nothing is written.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pytest
from sqlalchemy import bindparam, create_engine, text

from app.backend.persistence.chunk_structure_repo import structure_role_states
from app.backend.summarization.evidence_eligibility import AnchoredState, KeyedText, NativeCoverage, decide, map_region
from experiments.ask_cli_revised.focused_discovery.reference_eligibility import (
    continuation_flags,
    guarded_anchored_state,
    legacy_anchored_state,
    map_native_regions,
    mapping_audit,
    validate_claims,
)

ROOT = Path(__file__).resolve().parents[4]
QLLD = ROOT / ".local/q-lld-shadow-e2e-20261019-175119Z"
GUARD = ROOT / ".local/guarded-evidence-arctic-bge-20261018-212644Z"
LIBS = Path("C:/Users/cliff/callosum-data/shadow-3embed-20261015/run_libraries")
pytestmark = pytest.mark.skipif(
    not (QLLD.exists() and GUARD.exists() and (LIBS / "minilm.sqlite").exists()),
    reason="frozen q_lld artifacts are local-only",
)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def engine(name: str):
    return create_engine(f"sqlite:///file:{(LIBS / name).as_posix()}?mode=ro&immutable=1&uri=true")


@pytest.fixture(scope="module")
def handoff_chunks():
    return read(QLLD / "prep/baseline/handoff.json")["chunks"]


def regions(attachment_id: int) -> list[dict]:
    return read(GUARD / f"corpus/documents/a{attachment_id}.json")["regions"]


def legacy_decisions(units: list[dict]) -> dict:
    by_attachment = defaultdict(list)
    for unit in units:
        by_attachment[unit["attachment_id"]].append(unit)
    coverage, _ = map_native_regions(units, {a: regions(a) for a in by_attachment})
    with engine("minilm.sqlite").connect() as conn:
        roles = structure_role_states(conn, [u["id"] for u in units])
    out = {}
    for unit in units:
        raw = hashlib.sha256(unit["text"].encode()).hexdigest()
        cov = coverage[unit["id"]]
        anchored = legacy_anchored_state(unit["id"], roles, text_sha256=raw)
        out[unit["id"]] = decide(str(unit["id"]), key_length=cov.key_length, native=cov, anchored=anchored)
    return out


def guarded_decisions(unit_ids: set[int]) -> dict:
    units = [u for u in read(GUARD / "corpus/EVIDENCE_UNITS.json") if u["research_chunk_id"] in unit_ids]
    attachments = {u["attachment_id"] for u in units}
    with engine("arctic_s.sqlite").connect() as conn:
        legacy = [
            dict(r)
            for r in conn.execute(
                text(
                    "select id, attachment_id, page_start, page_end, text from chunks where attachment_id in :ids"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": sorted(attachments)},
            ).mappings()
        ]
        roles = structure_role_states(conn, [c["id"] for c in legacy])
    out = {}
    for unit in units:
        anchored = guarded_anchored_state(
            unit, [c for c in legacy if c["attachment_id"] == unit["attachment_id"]], roles
        )
        key_len = len(KeyedText.build("u", unit["text"]).key)
        out[unit["research_chunk_id"]] = decide(
            str(unit["research_chunk_id"]),
            key_length=key_len,
            native=NativeCoverage(key_len),
            anchored=anchored,
            native_unit_role=unit["source_role"],
        )
    return out


def test_marano_reference_chunks_are_withheld_by_native_union_coverage(handoff_chunks) -> None:
    units = [c for c in handoff_chunks if c["attachment_id"] == 34]
    decisions = legacy_decisions(units)
    for chunk_id in (28075, 28079):
        decision = decisions[chunk_id]
        assert decision.substantive == "withheld" and decision.decision == "native_reference_exclusion"
        assert decision.anchored.state == "current_bibliographic"  # the existing detector agrees, now consumed
        assert decision.navigation_eligible


def test_native_exclusions_cannot_silently_disappear_in_mapping(handoff_chunks) -> None:
    units = [c for c in handoff_chunks if c["attachment_id"] in (11, 34)]
    _, ledger = map_native_regions(units, {a: regions(a) for a in (11, 34)})
    reference_rows = [r for r in ledger if r["decision"] == "exclude_reference"]
    native_total = sum(r["retrieval_decision"] == "exclude_reference" for a in (11, 34) for r in regions(a))
    assert len(reference_rows) == native_total  # every native exclusion is accounted for, mapped or not
    assert all(r["status"] for r in reference_rows)
    audit = mapping_audit(ledger)
    assert audit["passed"], audit


def test_davies_jenkins_continuation_units_are_disputed_and_flagged() -> None:
    decisions = guarded_decisions({1013892, 1013828, 1013936})
    for unit_id in (1013892, 1013828, 1013936):
        decision = decisions[unit_id]
        assert decision.substantive == "disputed", decision.as_record()
        assert decision.anchored.state == "current_bibliographic"
        assert decision.disagreements[0]["native"] == "prose_or_other"
    # The flag-only context signal is a partial indicator: #/texts/139 neighbours another missed continuation
    # (#/texts/140), so it is not sandwiched. The verified anchored join, not the flag, is what catches it.
    flags = continuation_flags(regions(11))
    assert "#/texts/130/segment/0" in flags and "#/texts/139/segment/0" not in flags


def test_bracketed_numbering_and_glued_author_units_are_disputed_not_eligible() -> None:
    decisions = guarded_decisions({1003065, 1003079, 1018392, 1018387})
    assert {uid: d.substantive for uid, d in decisions.items()} == {
        1003065: "disputed",
        1003079: "disputed",
        1018392: "disputed",
        1018387: "disputed",
    }


def _delivered(arm: str) -> dict[str, dict]:
    out = {}
    for path in sorted((QLLD / f"prep/prepared/{arm}").glob("*.evidence.json")):
        for record in read(path)["evidence"]:
            out[record["source_id"]] = record
    return out


def test_documented_false_positive_prose_is_never_withheld() -> None:
    delivered = _delivered("B")
    record = delivered["S84f8688719ba478647"]
    decision = guarded_decisions({record["internal_unit_id"]})[record["internal_unit_id"]]
    assert decision.substantive in {"eligible", "disputed"}  # demotion at most -- never deletion


def test_independent_validator_detects_s6db56bec1dbc892a85(handoff_chunks) -> None:
    delivered = _delivered("A")
    ids = {r["internal_unit_id"] for r in delivered.values()}
    decisions = legacy_decisions([c for c in handoff_chunks if c["id"] in ids])
    authority = {("legacy_chunk", str(uid)): d.as_record() for uid, d in decisions.items()}
    run = QLLD / "juno_run/continuation-c9-20261022-201142Z/generations/A"
    hits = []
    for response in sorted(run.glob("*.response.json")):
        content = read(response)["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        try:
            parsed = json.loads(content)
        except ValueError:
            continue
        hits += [f for f in validate_claims(parsed, delivered, authority) if f["source_id"] == "S6db56bec1dbc892a85"]
    kinds = {f["finding"] for f in hits}
    assert "ineligible_source_cited" in kinds  # the as-run validator reported 0 navigation violations
    assert sum(f["finding"] == "ineligible_source_cited" for f in hits) >= 9


# ---- Known limitation: native scientific false exclusions --------------------------------------------------------
# Diagnostic fixtures, NOT production exceptions: no code path names these units. Native ``exclude_reference`` is
# assigned from entry-start morphology and is unverified for every region, so prose that begins like a citation
# (a column/page continuation, a parenthetical author-year) can be withheld. Two candidate corrections (trust an
# anchored "scientific" label; trust native's own reference_classification) and one guarded-join change were
# rejected against preregistered held-out criteria (REFERENCE_EXCLUSION_REPAIR_REPORT.md), so the behaviour stands
# and is documented here. The xfail tests assert the SCIENTIFICALLY CORRECT outcome and are strict: if a future
# general mechanism fixes a case, the XPASS fails the suite so the limitation record is updated, not left stale.
NATIVE_SCIENTIFIC_FALSE_EXCLUSIONS = {
    23431: (8, "Methods: counterbalanced within-subjects face-rating design"),
    35671: (70, "Results: Experiment 2 theory-of-mind ROI response by outcome"),
    38379: (88, "Methods: definition of the hat matrix in linear-model diagnostics"),
}


@pytest.fixture(scope="module")
def false_exclusion_decisions(handoff_chunks):
    attachments = {a for a, _ in NATIVE_SCIENTIFIC_FALSE_EXCLUSIONS.values()}
    return legacy_decisions([c for c in handoff_chunks if c["attachment_id"] in attachments])


@pytest.mark.parametrize("unit_id", sorted(NATIVE_SCIENTIFIC_FALSE_EXCLUSIONS))
def test_native_false_exclusion_is_inspectable_and_never_deleted(unit_id, false_exclusion_decisions) -> None:
    """Current behaviour, recorded as a known limitation (not as correct): withheld from substantive slots."""
    decision = false_exclusion_decisions[unit_id]
    assert decision.decision == "native_reference_exclusion"  # current behaviour; scientific risk documented above
    assert decision.navigation_eligible  # still reachable; the source text is never deleted or rewritten
    record = decision.as_record()
    assert record["excluded_spans"] and all(s["region_text_sha256"] for s in record["excluded_spans"])


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="known limitation: native morphology withholds prose")
@pytest.mark.parametrize("unit_id", sorted(NATIVE_SCIENTIFIC_FALSE_EXCLUSIONS))
def test_native_false_exclusion_scientific_text_stays_substantively_available(
    unit_id, false_exclusion_decisions
) -> None:
    assert false_exclusion_decisions[unit_id].substantive != "withheld"


# a11 #/texts/39 and a57 #/texts/79 are Methods paragraphs that native labels reference_entry. Neither withholds
# anything today, but only because the mapping fails (a11: a short tail divergence; a57: one math-bold beta glyph),
# and because the containing legacy chunks are large enough that coverage would stay below the threshold anyway.
MISLABELLED_METHODS_REGIONS = {(11, "#/texts/39/segment/0"): 23798, (57, "#/texts/79/segment/0"): 33093}


def test_mislabelled_methods_regions_currently_withhold_nothing(handoff_chunks) -> None:
    for (attachment_id, region_id), unit_id in MISLABELLED_METHODS_REGIONS.items():
        units = [c for c in handoff_chunks if c["attachment_id"] == attachment_id]
        _, ledger = map_native_regions(units, {attachment_id: regions(attachment_id)})
        row = next(r for r in ledger if r["region_id"] == region_id)
        assert row["decision"] == "exclude_reference" and row["source_role"] == "reference_entry"  # the mislabel
        assert row["status"] == "no_normalized_match"  # protection is incidental, not a property of the policy
        decision = legacy_decisions(units)[unit_id]
        assert decision.substantive == "eligible"
        assert region_id not in {s.region_id for s in decision.excluded_spans}


def _a57_if_mapped(handoff_chunks):
    """The a57 decision had the one glyph that blocks the mapping been extracted identically (no other change)."""
    unit = next(c for c in handoff_chunks if c["id"] == 33093)
    region = next(r for r in regions(57) if r["id"] == "#/texts/79/segment/0")
    keyed = KeyedText.build(region["id"], region["text"].replace("\U0001d6c3", ""))
    unit_key = KeyedText.build("33093", unit["text"])
    state, match = map_region(keyed, "exclude_reference", unit_key)
    decision = decide(
        "33093",
        key_length=len(unit_key.key),
        native=NativeCoverage(len(unit_key.key), (match,)),
        anchored=AnchoredState("absent"),
    )
    return unit, state, decision


def test_a57_mislabel_if_mapped_stays_eligible_but_carries_an_excluded_span(handoff_chunks) -> None:
    _, state, decision = _a57_if_mapped(handoff_chunks)
    assert state == "region_within_unit"
    assert decision.substantive == "eligible" and decision.decision == "eligible_mixed"  # coverage below threshold


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="known limitation: mislabelled span flags Methods quotes")
def test_a57_methods_quote_is_not_reported_as_an_eligibility_violation_if_mapped(handoff_chunks) -> None:
    unit, _, decision = _a57_if_mapped(handoff_chunks)
    quote = "MVPA compared spatial patterns of activity between two condi- tions"
    assert quote in unit["text"]
    record = {
        "source_id": "Sa57",
        "text": unit["text"],
        "text_sha256": hashlib.sha256(unit["text"].encode()).hexdigest(),
        "original_unit_namespace": "legacy_chunk",
        "internal_unit_id": 33093,
        "source_role": "prose_or_other",
    }
    findings = validate_claims(
        {"claims": [{"claim_id": "c", "source_quotes": [{"source_id": "Sa57", "quote": quote}]}]},
        {"Sa57": record},
        {("legacy_chunk", "33093"): decision.as_record()},
    )
    assert findings == []
