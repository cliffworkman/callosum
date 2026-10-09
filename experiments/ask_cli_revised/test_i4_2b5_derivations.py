"""I4-2b5 preflight: the actual producer's anchor/guard association, before integration."""

import pytest

from experiments.ask_cli_revised import achieved_outcome_span as aos
from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import ledger_renderer as lr
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import sufficiency_diagnostic as sd
from experiments.ask_cli_revised import sufficiency_mapping as sm
from experiments.ask_cli_revised import test_i4_2a_local_grounding as local

BASE = "We found that the signal increased."
PAIRS = [
    ("both_clear", BASE, BASE, 1, [()]),
    ("both_guarded_same", BASE + " It may persist.", BASE + " It may persist.", 1, [("hedged",)]),
    ("clear_and_guarded", BASE, BASE + " It may persist.", 2, [(), ("hedged",)]),
    (
        "different_guards",
        BASE + " It may persist.",
        BASE + " No evidence was available.",
        2,
        [("hedged",), ("absence_statement",)],
    ),
]


def sealed_pair(left, right):
    rows = []
    spans = []
    for i, quote in enumerate((left, right), 1):
        rows.append(
            dict(
                proposition_id=f"p{i}",
                proposition_text=BASE,
                quote=quote,
                paper_id=1,
                evidence_anchor_chunk_id=i,
                evidence_span_id=f"e{i}",
                responsive_obligation_ids=["c"],
                verification={"status": "verified"},
            )
        )
        spans.append(dict(paper_id=1, chunk_id=i, span_id=f"e{i}", text=quote))
    return dict(verified_propositions=rows, evidence_spans=spans)


@pytest.mark.parametrize("name,left,right,n,guards", PAIRS, ids=[r[0] for r in PAIRS])
def test_producer_never_merges_conflicting_guard_derivations(name, left, right, n, guards):
    sealed = sealed_pair(left, right)
    lr.validate_ledger(sealed)
    units = sd.units_by_child(sealed)["c"]
    assert len(units) == n
    assert len({pid for u in units for pid in u["proposition_ids"]}) == 2
    assert sum(len(u["proposition_ids"]) for u in units) == 2
    actual = [tuple(g for g in ("hedged", "absence_statement") if u["flags"].get(g)) for u in units]
    assert actual == guards
    by_key = {}
    for ui, u in enumerate(units):
        assert u["flags"] == oe.passage_flags(u["passage"])
        for hit in aos.find_achieved_outcome_matches(u["passage"]).matches:
            j = aa.locate_containing_assertion(
                u["passage"], *hit.content_span, ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F
            )
            if j["resolved"] and j["assertion"]["assertion"]["text"] == BASE[:-1]:
                key = (u["proposition_ids"][0], tuple(j["assertion"]["span"]))
                by_key.setdefault(key, []).append((ui, actual[ui]))
    assert len(by_key) == n
    assert all(len({ui for ui, _ in ds}) == len({gs for _, gs in ds}) == 1 for ds in by_key.values())
    # Equal scientific text with distinct anchors remains two candidates, not one merged identity.
    assert (len(by_key) == 2) == (name in ("clear_and_guarded", "different_guards"))
    spec = {**local.SPEC, "disqualifying_guards": ["hedged", "absence_statement"]}
    binding = sm._bind_achieved_outcome_v7(spec, units, role_completion=local.FREE, sibling_bindings={})[0]
    supports = [c for c in binding["candidate_supports"] if c["exact_text"] == BASE[:-1]]
    assert len(supports) == n
    assert [tuple(c["guard_exclusions"]) for c in supports] == guards
    assert binding["state"] == ("filled" if () in guards else "missing")


def test_multiple_raw_predicates_share_one_unit_guard_surface():
    text = "Results: Greater X was associated with higher Y, while lower X was associated with increased Z. It may persist."
    unit = local.unit(text)
    records = {}
    for hit in aos.find_achieved_outcome_matches(text).matches:
        j = aa.locate_containing_assertion(
            text, *hit.content_span, ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F
        )
        if j["resolved"]:
            records.setdefault(tuple(j["assertion"]["span"]), []).append(unit["flags"])
    assert any(len(ds) > 1 for ds in records.values())
    assert all(all(flags is unit["flags"] for flags in ds) for ds in records.values())
