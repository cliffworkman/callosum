"""Reference-exclusion repair: the shared, pure eligibility policy (built entirely from literals).

Fixtures mirror the q_lld reference-leakage investigation: Docling (native) region text is dehyphenated and
de-ligatured while the PyMuPDF chunk keeps ``deﬁcits`` and ``depres- sion`` -- exactly the difference that made
the as-run exact-substring sidecar map 82.9% of reference exclusions to nothing.
"""

from __future__ import annotations

from app.backend.summarization.evidence_eligibility import (
    MIN_UNIT_KEY_CHARS,
    NATIVE_COVERAGE_THRESHOLD,
    AnchoredState,
    KeyedText,
    NativeCoverage,
    comparison_key,
    decide,
    map_region,
    select_slots,
)

# PyMuPDF legacy chunk (Marano 2015, p9 shape): several entries, ligature + hyphen-break artefacts.
LEGACY_REFERENCES = (
    "32. Egger K, Schocke M, Weiss E, et al: Pattern of brain atrophy in elderly patients with depression revealed "
    "by voxel-based morphometry. Psychiatry Res 2008; 164:237e244 33. Yuan Y, Zhu W, Zhang Z, et al: Regional gray "
    "matter changes are associated with cognitive deﬁcits in remitted geriatric depres- sion: an optimized "
    "voxel-based morphometry study. Biol Psychi- atry 2008; 64:541e544 34. Hwang JP, Lee TW, Tsai SJ, et al: "
    "Cortical and subcortical abnormalities in late-onset depression with history of suicide attempts investigated "
    "with MRI and voxel-based morphometry. J Geriatr Psychiatry Neurol 2010; 23:171e184"
)
# The same three entries as Docling regions (dehyphenated, ligature resolved).
NATIVE_ENTRIES = [
    "32. Egger K, Schocke M, Weiss E, et al: Pattern of brain atrophy in elderly patients with depression revealed "
    "by voxel-based morphometry. Psychiatry Res 2008; 164:237e244",
    "33. Yuan Y, Zhu W, Zhang Z, et al: Regional gray matter changes are associated with cognitive deficits in "
    "remitted geriatric depression: an optimized voxel-based morphometry study. Biol Psychiatry 2008; 64:541e544",
    "34. Hwang JP, Lee TW, Tsai SJ, et al: Cortical and subcortical abnormalities in late-onset depression with "
    "history of suicide attempts investigated with MRI and voxel-based morphometry. J Geriatr Psychiatry Neurol "
    "2010; 23:171e184",
]
DISCUSSION = (
    "In conclusion, decreased 5-HTT availability in LLD patients relative to controls was observed that may reflect "
    "an early stage of serotonin degeneration, consistent with prior reports (Smith et al., 2009; Kanellopoulos et "
    "al., 2011; doi:10.1016/j.jad.2011.04.031). These findings were robust to correction for partial volume effects."
)


def _coverage(unit_text: str, regions: list[tuple[str, str, str]]) -> tuple[KeyedText, NativeCoverage]:
    unit = KeyedText.build("u", unit_text)
    matches = []
    for region_id, decision, text in regions:
        _, match = map_region(KeyedText.build(region_id, text), decision, unit)
        if match is not None:
            matches.append(match)
    return unit, NativeCoverage(len(unit.key), tuple(matches))


def test_comparison_key_offsets_point_into_the_original_text() -> None:
    key, offsets = comparison_key("cognitive deﬁcits, depres- sion")
    assert key == "cognitivedeficitsdepression"
    assert len(offsets) == len(key)
    assert "cognitive deﬁcits, depres- sion"[offsets[-1]] == "n"


def test_ligature_and_dehyphenation_regions_map_with_exact_original_offsets() -> None:
    unit = KeyedText.build("28079", LEGACY_REFERENCES)
    state, match = map_region(KeyedText.build("#/texts/120", NATIVE_ENTRIES[1]), "exclude_reference", unit)
    assert state == "region_within_unit"
    original = LEGACY_REFERENCES[match.start : match.end]
    assert original.startswith("33. Yuan Y") and original.endswith("64:541e544")
    assert "deﬁcits" in original and "depres- sion" in original  # original text is preserved, never rewritten
    assert LEGACY_REFERENCES.find(NATIVE_ENTRIES[1]) == -1  # the as-run exact str.find failed on this entry


def test_multi_entry_reference_chunk_is_withheld_by_union_coverage() -> None:
    # T1: no single region equals the chunk (the as-run equality rule never fired), but their union covers it.
    unit, cov = _coverage(LEGACY_REFERENCES, [(f"r{i}", "exclude_reference", t) for i, t in enumerate(NATIVE_ENTRIES)])
    assert all(LEGACY_REFERENCES.strip() != t.strip() for t in NATIVE_ENTRIES)
    decision = decide("28079", key_length=len(unit.key), native=cov, anchored=AnchoredState("absent"))
    assert decision.native_reference_coverage >= NATIVE_COVERAGE_THRESHOLD
    assert decision.substantive == "withheld" and decision.decision == "native_reference_exclusion"
    assert decision.navigation_eligible  # T5: still available for bibliographic navigation
    assert len(decision.excluded_spans) == 3


def test_mixed_discussion_reference_chunk_stays_eligible_with_spans_preserved() -> None:
    # T3: partial coverage keeps the prose eligible and the excluded span identity attached.
    text = DISCUSSION + " " + NATIVE_ENTRIES[0]
    unit, cov = _coverage(text, [("r0", "exclude_reference", NATIVE_ENTRIES[0])])
    decision = decide("mixed", key_length=len(unit.key), native=cov, anchored=AnchoredState("absent"))
    assert 0 < decision.native_reference_coverage < NATIVE_COVERAGE_THRESHOLD
    assert decision.substantive == "eligible" and decision.decision == "eligible_mixed"
    span = decision.excluded_spans[0]
    assert text[span.start : span.end] == NATIVE_ENTRIES[0]
    assert decision.as_record()["excluded_spans"][0]["region_id"] == "r0"


def test_repeated_region_inside_a_unit_is_ambiguous_not_a_verified_match() -> None:
    entry = NATIVE_ENTRIES[0]
    state, match = map_region(
        KeyedText.build("r", entry), "exclude_reference", KeyedText.build("u", entry + " " + entry)
    )
    assert state == "ambiguous_repeated_in_unit" and match is None


def test_short_regions_and_units_are_never_matched_or_withheld_on_coverage() -> None:
    state, _ = map_region(KeyedText.build("r", "Table 2"), "retain_navigation", KeyedText.build("u", DISCUSSION))
    assert state == "region_too_short"
    label = "Figure 3 panel B, left hemisphere"
    unit, cov = _coverage(label, [("h", "retain_navigation", label)])
    assert len(unit.key) < MIN_UNIT_KEY_CHARS
    decision = decide("label", key_length=len(unit.key), native=cov, anchored=AnchoredState("absent"))
    assert decision.substantive == "disputed"  # never silently withheld on coverage alone


def test_region_continuing_across_a_chunk_boundary_is_a_partial_match() -> None:
    entry = NATIVE_ENTRIES[2]
    unit_text = entry[60:] + " " + DISCUSSION  # the chunk starts mid-entry
    state, match = map_region(KeyedText.build("r", entry), "exclude_reference", KeyedText.build("u", unit_text))
    assert state == "region_tail_at_unit_start"
    assert unit_text[match.start : match.end].endswith("23:171e184")


def test_scientific_paragraph_with_citations_and_doi_is_not_affected() -> None:
    # No native exclusion, no anchored label: conventional citations and a DOI never make prose bibliography.
    unit = KeyedText.build("p", DISCUSSION)
    decision = decide("p", key_length=len(unit.key), native=None, anchored=AnchoredState("absent"))
    assert decision.substantive == "eligible" and decision.decision == "eligible"


def test_anchored_label_alone_demotes_and_records_disagreement_never_withholds() -> None:
    # T4: the documented false positive S84f8688719ba478647 (Results conclusion) must remain reachable.
    unit = KeyedText.build("S84f8688719ba478647", DISCUSSION)
    decision = decide(
        "S84f8688719ba478647",
        key_length=len(unit.key),
        native=None,
        anchored=AnchoredState("current_bibliographic", 1.0, {"roles": ["bibliographic"]}),
        native_unit_role="prose_or_other",
    )
    assert decision.substantive == "disputed"
    assert decision.disagreements[0] == {
        "native": "prose_or_other",
        "anchored": "bibliographic",
        "resolution": "demoted_not_withheld",
    }


def test_stale_and_unresolved_classifications_are_recorded_and_ignored() -> None:
    unit = KeyedText.build("x", DISCUSSION)
    for state, reason in [
        ("stale", "anchored_classification_stale_ignored"),
        ("join_unresolved", "anchored_join_unresolved_ignored"),
    ]:
        decision = decide("x", key_length=len(unit.key), native=None, anchored=AnchoredState(state, 1.0))
        assert decision.substantive == "eligible" and reason in decision.reasons


def test_native_verified_exclusion_wins_over_anchored_scientific_and_records_it() -> None:
    unit, cov = _coverage(LEGACY_REFERENCES, [(f"r{i}", "exclude_reference", t) for i, t in enumerate(NATIVE_ENTRIES)])
    decision = decide(
        "u",
        key_length=len(unit.key),
        native=cov,
        anchored=AnchoredState("current_other", 0.0, {"roles": ["scientific"]}),
    )
    assert decision.substantive == "withheld"
    assert decision.disagreements[0]["resolution"] == "native_verified_wins"


def test_slot_selection_backfills_from_eligible_and_reports_disputed_fallback_and_shortage() -> None:
    def make(uid, status):
        anchored = AnchoredState("current_bibliographic", 1.0) if status == "disputed" else AnchoredState("absent")
        unit, cov = (
            _coverage(LEGACY_REFERENCES, [(f"r{i}", "exclude_reference", t) for i, t in enumerate(NATIVE_ENTRIES)])
            if status == "withheld"
            else _coverage(DISCUSSION, [])
        )
        return decide(uid, key_length=len(unit.key), native=cov, anchored=anchored)

    decisions = {
        u: make(u, s) for u, s in [("w1", "withheld"), ("d1", "disputed"), ("e1", "eligible"), ("e2", "eligible")]
    }
    ranked = ["w1", "d1", "e1", "e2"]
    slots = select_slots(ranked, decisions, 2)
    assert slots.selected == (("e1", "eligible"), ("e2", "eligible"))
    assert slots.withheld == ("w1",) and slots.demoted_unused == ("d1",) and slots.shortage == 0
    slots = select_slots(ranked, decisions, 4)
    assert slots.selected[-1] == ("d1", "disputed") and slots.disputed_fallback == ("d1",)
    assert slots.shortage == 1  # never padded with the withheld reference unit
