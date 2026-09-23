"""The frozen supervisory battery: what is asked, and the expected judgments.

Everything here is public-safe text (the user's own request units and one-sentence claims). Verbatim
source quotes are private and enter only at prompt-rendering time, from `build_battery.py`.
`build_battery.py` verifies every string below byte-for-byte against the real run9 artifacts, so this
file cannot drift from the evidence it claims to come from.

Label authority: Cliff's stated labels. Gates cover labeled pairs plus obligations clearly unrelated to
the claim; anything else is recorded as diagnostic and never auto-fails a model.
"""

# The user's own request, verbatim (run9 `00_question.json`; pinned by its sha256 in the tests and re-checked
# against the source by build_battery). A supervisor always holds the request: item fragments such as
# "and using which scales?" mean nothing without it.
ORIGINAL_QUESTION = (
    "how does the anomalous is bad bias manifest in brain, behavior, and attitudes? please return specific brain "
    "areas and whether and how they relate to behaviors, which kinds of behaviors, and whether they relate to "
    "attitudes, and which kinds of attitudes. what kind of specific personality traits relate to its manifestation? "
    "and using which scales? is there any cross-cultural evidence for the bias? which cultures and how was this "
    "measures? and are there effective interventions aimed at reducing it?"
)

OBLIGATIONS = [
    {"field_id": "s1-o1", "note": "how does the anomalous is bad bias manifest in brain, behavior, and attitudes?"},
    {
        "field_id": "s2-o1",
        "note": "please return specific brain areas and whether and how they relate to behaviors, "
        "which kinds of behaviors, and whether they relate to attitudes, and which kinds of "
        "attitudes. what kind of specific personality traits relate to its manifestation?",
    },
    {"field_id": "s3-o1", "note": "and using which scales?"},
    {"field_id": "s4-o1", "note": "is there any cross-cultural evidence for the bias?"},
    {"field_id": "s5-o1", "note": "which cultures and how was this measures?"},  # sic: verbatim from the user's request
    {"field_id": "s6-o1", "note": "and are there effective interventions aimed at reducing it?"},
]
OBLIGATION_IDS = [o["field_id"] for o in OBLIGATIONS]

# The real verified ledger of run9 (`11_verified_ledger.json`): claim, the obligation it was retrieved for, paper.
PROPOSITIONS = [
    {
        "proposition_id": "p1",
        "claim": "people with anomalous faces have negative personality traits",
        "retrieved_for": "s2-o1",
        "paper_id": 67,
    },
    {
        "proposition_id": "p2",
        "claim": "people with anomalous faces have negative personality traits",
        "retrieved_for": "s3-o1",
        "paper_id": 67,
    },
    {
        "proposition_id": "p3",
        "claim": "explicit negative attitudes about people with facial anomalies",
        "retrieved_for": "s1-o1",
        "paper_id": 67,
    },
    {
        "proposition_id": "p4",
        "claim": "Laypersons with high levels of implicit bias toward individuals with facial "
        "anomalies demonstrated increased amygdala reactivity.",
        "retrieved_for": "s2-o1",
        "paper_id": 61,
    },
    {
        "proposition_id": "p5",
        "claim": "The dorsomedial prefrontal cortex affects individuals' responses to social situations.",
        "retrieved_for": "s3-o1",
        "paper_id": 45,
    },
    {
        "proposition_id": "p6",
        "claim": "Mentalizing regions represent distributed, continuous and abstract dimensions of others beliefs.",
        "retrieved_for": "s5-o1",
        "paper_id": 28,
    },
]
PROPOSITION_IDS = [p["proposition_id"] for p in PROPOSITIONS]

_ORDERINGS = {
    "original": OBLIGATION_IDS,
    "reversed": list(reversed(OBLIGATION_IDS)),
    "rotated": OBLIGATION_IDS[3:] + OBLIGATION_IDS[:3],  # s4,s5,s6,s1,s2,s3
}


def obligation_order(ordering):
    return list(_ORDERINGS[ordering])


def _ledger(pid):
    p = next(x for x in PROPOSITIONS if x["proposition_id"] == pid)
    return {"origin": "verified_ledger", "proposition_id": pid, "status": "verified", "paper_id": p["paper_id"]}


def _candidate(index, status, paper_id):
    return {"origin": f"09_propositions.jsonl[{index}]", "status": status, "paper_id": paper_id}


def _claim(pid):
    return next(p["claim"] for p in PROPOSITIONS if p["proposition_id"] == pid)


# Task A. `required`: must be selected. `diagnostic`: may be selected (recorded, never gated).
# Every other obligation is forbidden. Generic neuroscience (A3/A4) maps to NONE -- not to the
# nearest brain-related obligation. A5 stays negative: source provenance not supplied to a
# claim-only task must not influence the judgment.
_A_BASES = [
    {
        "base_id": "A1",
        "role": "positive",
        "claim": _claim("p3"),
        "claim_source": _ledger("p3"),
        "required": ["s1-o1"],
        "diagnostic": ["s2-o1"],
        "order_robust": True,
    },
    {
        "base_id": "A2",
        "role": "positive",
        "claim": "There is cross-cultural evidence for the bias in personality or behavior.",
        "claim_source": _candidate(21, "unverified", 269),
        "required": ["s4-o1"],
        "diagnostic": ["s1-o1", "s2-o1"],
        "order_robust": True,
    },
    {
        "base_id": "A3",
        "role": "negative",
        "claim": _claim("p5"),
        "claim_source": _ledger("p5"),
        "required": [],
        "diagnostic": [],
        "order_robust": True,
    },
    {
        "base_id": "A4",
        "role": "negative",
        "claim": _claim("p6"),
        "claim_source": _ledger("p6"),
        "required": [],
        "diagnostic": [],
        "order_robust": False,
    },
    {
        "base_id": "A5",
        "role": "negative",
        "claim": "how many years participants attended school",
        "claim_source": _candidate(72, "weak", 68),
        "required": [],
        "diagnostic": [],
        "order_robust": False,
    },
    {
        "base_id": "A6",
        "role": "diagnostic",
        "claim": _claim("p1"),
        "claim_source": _ledger("p1"),
        "required": [],
        "diagnostic": list(OBLIGATION_IDS),
        "order_robust": False,
    },
    {
        "base_id": "A7",
        "role": "positive",
        "claim": "The EBQ measures explicit bias.",
        "claim_source": _candidate(16, "weak", 248),
        "required": ["s3-o1"],
        "diagnostic": ["s5-o1"],
        "order_robust": True,
    },
]

# Task B expectations. p5/p6 (generic neuroscience) may support NO obligation. p1/p2 (traits) keep
# diagnostic latitude for s1/s2. p3 -> s1 is the clear positive. s4/s6 have no support in the ledger.
_B_EXPECTED = {
    "required_support": {"s1-o1": ["p3"]},
    "must_be_unresolved": ["s4-o1", "s6-o1"],
    "forbidden_attach": {
        "p1": ["s3-o1", "s4-o1", "s5-o1", "s6-o1"],
        "p2": ["s3-o1", "s4-o1", "s5-o1", "s6-o1"],
        "p3": ["s4-o1", "s6-o1"],
        "p4": ["s4-o1", "s6-o1"],
        "p5": list(OBLIGATION_IDS),
        "p6": list(OBLIGATION_IDS),
    },
}

RECOVERY_POLICY = [
    "The goal is one bounded attempt to resolve each remaining gap.",
    "Do not repeat an already-performed search action.",
    "If a gap remains unresolved and a broader, unused legal recovery action is available, choose that action "
    "before giving up.",
    "If the bounded recovery options have been exhausted without responsive verified evidence, preserve the "
    "obligation as unresolved.",
    "Never mark an obligation covered using evidence that does not directly support it.",
    "Never invent an action or an evidence item.",
]

_REAL = "real recovery record (13_gap_recovery.json, run9)"
_S4_RECONSTRUCTION = (
    "reconstruction: candidate counts are real, but NOMINATE is marked not-yet-performed; the real run "
    "nominated 5 additional papers for this item and found no new verified evidence"
)


def _searched(candidates, hits, nominated=None, nominated_hits=None):
    out = {
        "DEEPEN": f"re-searched the {candidates} candidate papers already nominated for this item with a "
        f"reformulated query ({hits} passages matched)"
    }
    if nominated is not None:
        out["NOMINATE"] = (
            f"searched the wider corpus for additional candidate papers ({nominated} additional papers "
            f"nominated, {nominated_hits} passages matched)"
        )
    return out


# Coverage audit inputs are the frozen expectations of Task B (responsive support per obligation).
_C_STATE = {
    "s1-o1": {
        "support": ["p3"],
        "performed": {"DEEPEN": True, "NOMINATE": True},
        "searched": _searched(25, 8, 0, 0),
        "provenance": _REAL,
    },
    "s2-o1": {
        "support": ["p4"],
        "performed": {"DEEPEN": True, "NOMINATE": True},
        "searched": _searched(25, 6, 5, 7),
        "provenance": _REAL,
    },
    "s3-o1": {
        "support": [],
        "performed": {"DEEPEN": True, "NOMINATE": True},
        "searched": _searched(25, 8, 12, 8),
        "provenance": _REAL,
    },
    "s4-o1": {
        "support": [],
        "performed": {"DEEPEN": True, "NOMINATE": False},
        "searched": _searched(25, 8),
        "provenance": _S4_RECONSTRUCTION,
    },
    "s5-o1": {
        "support": [],
        "performed": {"DEEPEN": True, "NOMINATE": True},
        "searched": _searched(25, 8, 9, 8),
        "provenance": _REAL,
    },
    "s6-o1": {
        "support": [],
        "performed": {"DEEPEN": True, "NOMINATE": True},
        "searched": _searched(25, 8, 16, 8),
        "provenance": _REAL,
    },
}

_C_EXPECTED = {
    "required_choice": {"s4-o1": "s4-o1:NOMINATE", "s5-o1": "s5-o1:PRESERVE_UNRESOLVED"},
    "closure_forbidden": ["s3-o1", "s4-o1", "s5-o1", "s6-o1"],
    "repeat_forbidden": ["s3-o1", "s4-o1", "s5-o1"],
    "performed": [f"{ob}:{action}" for ob, s in _C_STATE.items() for action, done in s["performed"].items() if done],
}


def _c_state():
    state = {}
    for ob in OBLIGATION_IDS:
        s = _C_STATE[ob]
        on_file = [p["proposition_id"] for p in PROPOSITIONS if p["retrieved_for"] == ob]
        state[ob] = {
            "coverage_support": list(s["support"]),
            "on_file": on_file,
            "performed": dict(s["performed"]),
            "searched": dict(s["searched"]),
            "state_provenance": s["provenance"],
        }
    return state


def _c_actions(state):
    actions = {}
    for ob in OBLIGATION_IDS:
        ids = [f"{ob}:DEEPEN", f"{ob}:NOMINATE"]
        ids += [f"{ob}:MARK_COVERED:{pid}" for pid in state[ob]["on_file"]]
        ids += [f"{ob}:NO_RECOVERY_NEEDED", f"{ob}:PRESERVE_UNRESOLVED"]
        actions[ob] = ids
    return actions


def build_case_specs():
    specs = []
    for base in _A_BASES:
        orderings = ["original", "reversed", "rotated"] if base["order_robust"] else ["original"]
        for ordering in orderings:
            specs.append(
                {
                    "case_id": f"{base['base_id']}.{ordering}",
                    "base_id": base["base_id"],
                    "family": "A",
                    "ordering": ordering,
                    "role": base["role"],
                    "order_robust": base["order_robust"],
                    "obligation_order": obligation_order(ordering),
                    "claim": base["claim"],
                    "claim_source": base["claim_source"],
                    "legal": {"obligation_ids": list(OBLIGATION_IDS)},
                    "expected": {
                        "required": list(base["required"]),
                        "diagnostic": list(base["diagnostic"]),
                        "gated": base["role"] != "diagnostic",
                    },
                }
            )
    for ordering in ("original", "reversed"):
        props = PROPOSITION_IDS if ordering == "original" else list(reversed(PROPOSITION_IDS))
        specs.append(
            {
                "case_id": f"B1.{ordering}",
                "base_id": "B1",
                "family": "B",
                "ordering": ordering,
                "role": "coverage",
                "order_robust": False,
                "obligation_order": obligation_order("original"),
                "proposition_order": list(props),
                "legal": {"obligation_ids": list(OBLIGATION_IDS), "proposition_ids": list(PROPOSITION_IDS)},
                "expected": _B_EXPECTED,
            }
        )
    state = _c_state()
    actions = _c_actions(state)
    for ordering in ("original", "reversed"):
        rev = ordering == "reversed"
        specs.append(
            {
                "case_id": f"C1.{ordering}",
                "base_id": "C1",
                "family": "C",
                "ordering": ordering,
                "role": "recovery",
                "order_robust": False,
                "obligation_order": obligation_order("reversed" if rev else "original"),
                "policy": " ".join(RECOVERY_POLICY),
                "state": state,
                "legal": {
                    "obligation_ids": list(OBLIGATION_IDS),
                    "actions": {ob: (list(reversed(ids)) if rev else list(ids)) for ob, ids in actions.items()},
                },
                "expected": _C_EXPECTED,
            }
        )
    return specs
