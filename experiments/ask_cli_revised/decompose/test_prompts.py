"""Offline proof of the two prospective writer prompts (corrected-full, lean), the matched output budget, the request-form and
source-gap rules, and the isolation of the held-out reference. Synthetic requests only, except one test that checks the frozen
v3 bodies against the preserved local artifacts and skips itself when they are absent. No model is called."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import experiments.ask_cli_revised.decompose.test_decompose as base
from experiments.ask_cli_revised.calibration.structured_output import SchemaCall
from experiments.ask_cli_revised.decompose import children as ch
from experiments.ask_cli_revised.decompose import clarifications, ledger, prompts, relations
from experiments.ask_cli_revised.decompose.calllog import CallLog
from experiments.ask_cli_revised.decompose.engine import run_engine
from experiments.ask_cli_revised.decompose.model import ReplayModel, ScriptedModel
from experiments.ask_cli_revised.decompose.parent import build_parent_contract
from experiments.ask_cli_revised.decompose.test_relations import CLAR, Q
from experiments.ask_cli_revised.decompose.test_tree import CLAR_FRAGMENT, CLAR_UNIT, Q2, _respond_q2

NL = chr(10)
ZONES = Q.index("specific reef zones")
CLAR_Z = {**CLAR, "refers_to": {"span": [ZONES, ZONES + len("specific reef zones")], "phrase": "specific reef zones"}}
VARIANTS = ("corrected-full", "lean")


def _run(variant, overrides=None, clars=None, **kw):
    model = ScriptedModel(base.responder(overrides))
    result = run_engine(Q, model, repair=False, prompt_variant=variant, clarifications=clars, **kw)
    return result, model


def _writes(result):
    """The child-writing calls (the engine also records its inventory calls when no inventory model is replayed)."""
    return [c for c in result["calls"] if c["task"] == "children.write"]


def _prompt(result, needle):
    return next(c["prompt"] for c in _writes(result) if needle in c["prompt"])


def _child(result, needle):
    return next(c for c in result["pass1"]["children"] if needle in c["question"])


def _flags(child):
    return {f["kind"] for f in child["edit_ledger"]["flags"] if f["class"] != "info"}


# ---- the frozen v3 prompts are untouched ---------------------------------------------------------------------------------------------------------


def test_the_frozen_v3_prompt_is_byte_identical_to_the_preserved_bodies():
    root = Path(__file__).resolve().parents[3] / ".local" / "decompose-runs" / "aib-dev"
    saved = root / "offline_review_v3" / "assembled_requests"
    files = [root / "reference" / "q_aib.original.v1.txt", root / "clarifications" / "q_aib.v3.approved.json", saved]
    if not all(f.exists() for f in files) or not (root / "dev-run-2-obligation-qwen35-9b").exists():
        pytest.skip("the local q_aib development artifacts are not present")
    question = files[0].read_text(encoding="utf-8")
    recorded = [
        json.loads(x)
        for x in (root / "dev-run-2-obligation-qwen35-9b" / "model_calls_LIVE_ORIGINAL.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if x.strip()
    ]
    inventory = [r for r in recorded if r["task"].startswith("parent.")]
    result = run_engine(
        question,
        ScriptedModel(lambda prompt, schema: {"question": "x", "unresolved": []}),
        repair=False,
        max_calls=11,
        inventory_model=ReplayModel(inventory, inventory[0]["produced_by"]),
        clarifications=clarifications.load(files[1]),
        prompt_variant="v3",
    )
    for i, rec in enumerate(result["calls"], 1):
        body = json.loads((saved / f"{i:02d}_{rec['unit_id']}.request.json").read_text(encoding="utf-8"))
        assert body["messages"][0]["content"] == rec["prompt"], rec["unit_id"]
    assert len(result["calls"]) == 11


def test_the_governing_operation_is_carried_only_by_the_variants_and_only_inside_its_sentence():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    from experiments.ask_cli_revised.decompose.children import plan_children

    plans = plan_children(parent)
    by = ch.by_id_map(parent)
    rel = next(
        p
        for p in plans
        if p["relation"]
        and "whether and how" in parent["original_question"][p["relation"]["source_spans"][0][0] :][:30]
    )
    assert (
        ch.child_context(parent, rel, by, plans=plans, governing_operation=False)["governing"] is None
    )  # v3: unchanged
    ctx = ch.child_context(parent, rel, by, plans=plans, governing_operation=True)
    assert Q[ctx["governing"][0] : ctx["governing"][1]] == "please return"
    assert prompts.substance(parent, rel, plans, by)["extract_text"].startswith(
        "please return whether and how they relate"
    )
    pigments = next(p for p in plans if p["relation"] and "pigments" in p["relation"]["subject"]["text"])
    assert (
        ch.child_context(parent, pigments, by, plans=plans, governing_operation=True)["governing"] is None
    )  # another sentence
    growth = next(p for p in plans if p["anchor_id"] and by[p["anchor_id"]]["text"] == "growth")
    assert (
        ch.child_context(parent, growth, by, plans=plans, governing_operation=True)["governing"] is None
    )  # no operation there


# ---- both variants carry the same substance and every applicable safeguard ---------------------------------------------------------------------


def _substance_strings(sub):
    out = list(sub["extract_lines"])
    out += [c["points_at"] for c in sub["clarified_references"] if c["points_at"]]
    out += [c["means"] for c in [*sub["clarified_references"], *sub["meaning_clarifications"]]]
    out += [c["link"] for c in sub["meaning_clarifications"] if c["link"]]
    out += [m for j in sub["pairs"] for m in j["members"]]
    out += [c["text"] for c in sub["continues"]] + [i["words"] for i in sub["inherited_subject"]]
    rel = sub["relationship"]
    if rel:
        out += [rel["subject"], rel["relation"], rel["target"], *rel["qualifications"]]
    if sub["context"]["state"] in ("available_with_link", "unstated_link", "via_inherited"):
        out.append(sub["context"]["words"])
    return [s for s in out if s]


@pytest.mark.parametrize("clars", [None, [CLAR_Z]])
def test_both_variants_render_the_same_substance_and_every_applicable_safeguard(clars):
    full, _ = _run("corrected-full", clars=clars)
    lean, _ = _run("lean", clars=clars)
    parent = full["parent_contract"]
    by = ch.by_id_map(parent)
    plans = full["pass1"]["plans"]
    assert len(_writes(full)) == len(_writes(lean)) > 0
    for plan, f, ln in zip(
        [p for p in plans if p["kind"] not in ("unit_level", "elliptical")], _writes(full), _writes(lean), strict=True
    ):
        sub = prompts.substance(parent, plan, plans, by)
        for text in _substance_strings(sub):
            assert text in f["prompt"] and text in ln["prompt"], (plan["child_id"], text)
        for key in prompts.applicable_safeguards(sub):
            assert prompts.SAFEGUARDS[key]["full"][0] in f["prompt"], (plan["child_id"], key)
            assert prompts.SAFEGUARDS[key]["lean"][0] in ln["prompt"], (plan["child_id"], key)
        assert len(ln["prompt"]) < len(f["prompt"])


def test_the_two_variants_share_one_schema_and_one_generation_budget_and_the_lean_prompt_is_not_redundant():
    a, b = prompts.settings_for("corrected-full"), prompts.settings_for("lean")
    assert a["schema"] == b["schema"] and a["cap"] == b["cap"] and a["limits"] == b["limits"]
    lean, _ = _run("lean", clars=[CLAR_Z])
    for rec in _writes(lean):
        p = rec["prompt"]
        assert "(chars" not in p and "Return only JSON" not in p and "[requested_item]" not in p
        assert p.count(NL + "Fields:") == 1
    rel = _prompt(lean, "whether and how they relate")
    assert (
        rel.count("whether and how they relate") == 1
    )  # the source words appear once, not as owned item + slot + extract + excerpt


# ---- request form, unresolved meaning, clarification prose ------------------------------------------------------------------------------------


def test_an_imperative_is_kept_as_an_imperative_and_a_recast_or_final_question_mark_is_reported():
    ok, _ = _run("lean", {"specific reef zones": {"question": "Please return specific reef zones"}})
    assert _child(ok, "Please return specific")["status"] in ("candidate", "source_gap")
    assert "request_form_changed" not in _flags(_child(ok, "Please return specific"))
    for wording, key in (
        ("Which specific reef zones?", "imperative_to_question"),
        ("Please return specific reef zones?", "final_question_mark"),
    ):
        bad, _ = _run("lean", {"specific reef zones": {"question": wording}})
        kid = _child(bad, wording[:12])
        assert (
            "request_form_changed" in _flags(kid)
            and key in next(f for f in kid["edit_ledger"]["flags"] if f["kind"] == "request_form_changed")["words"]
        )
        assert kid["child_id"] not in bad["pass1"]["reconciliation"]["summary"]["successful_children"]
    assert "please return X" in prompts.SAFEGUARDS["FORM"]["full"][1]


def test_an_unclarified_reference_is_never_offered_a_reading_and_a_guess_is_not_a_success():
    for variant in VARIANTS:
        result, _ = _run(variant)  # no clarification: "they" stays unclarified
        p = _prompt(result, "whether and how they relate")
        assert "most direct reading" not in p and "could mean" not in p  # no candidate reading is offered to be picked
        assert '"they"' in p and ("Not clarified" in p)
        guess = "Whether and how the specific reef zones relate to depth, which kinds of depth"
        bad, _ = _run(variant, {"whether and how": {"question": guess, "unresolved": []}})
        kid = _child(bad, "Whether and how the specific")
        assert kid["status"] in ("conditional_on_unresolved_reading", "semantic_conflict", "semantic_review_required")
        assert kid["child_id"] not in bad["pass1"]["reconciliation"]["summary"]["successful_children"]
        assert (
            kid["diagnostics"]["hard_fail"] or kid["status"] == "conditional_on_unresolved_reading"
        )  # silent or declared guess


def test_pasting_a_clarification_explanation_is_flagged_and_a_proposed_brief_never_authorizes_wording():
    lo = Q.index("relate to its expression")
    long_means = "zebra stripes are documented as positive or negative associations across many reef zones and pigments"
    rc = {
        "id": "RC-L",
        "span": [lo, lo + len("relate to its expression")],
        "phrase": "relate to its expression",
        "means": long_means,
        "authorized_by": "tester",
        "refers_to": {"span": [Q.index("coral effect"), Q.index("coral effect") + 12], "phrase": "coral effect"},
    }
    pasted = "What kind of specific pigments relate to its expression, " + long_means
    result, _ = _run("lean", {"pigments": {"question": pasted}}, clars=[rc])
    assert "clarification_prose_pasted" in _flags(_child(result, "zebra stripes"))
    ann = [
        {
            "clarification": "RC-L",
            "brief": {"text": "quagga only", "status": "proposed", "condensed_from": "RC-L", "authored_by": "Claude"},
        }
    ]
    plain, _ = _run(
        "lean",
        {"pigments": {"question": "What kind of specific pigments relate to its expression quagga"}},
        clars=[rc],
        clarification_annotations=ann,
    )
    assert "quagga" not in _prompt(
        plain, "pigments"
    )  # a proposed brief is not shown to a model unless the run is a what-if
    assert "unsupported_substitution" in _flags(_child(plain, "quagga"))  # ...and never authorizes a word
    whatif, _ = _run(
        "lean",
        {"pigments": {"question": "What kind of specific pigments relate to its expression quagga"}},
        clars=[rc],
        clarification_annotations=ann,
        use_proposed_briefs=True,
    )
    assert "PROPOSED condensation, NOT approved" in _prompt(whatif, "quagga only")
    assert "unsupported_substitution" in _flags(_child(whatif, "quagga"))
    assert (
        whatif["manifest"]["proposed_briefs_shown_to_the_model"] is True
        and plain["manifest"]["proposed_briefs_shown_to_the_model"] is False
    )


def test_a_context_link_must_be_the_researchers_own_words_and_a_brief_needs_its_provenance():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    clarifications.apply(parent, [CLAR_Z])
    with pytest.raises(clarifications.ClarificationError, match="not verbatim"):
        clarifications.annotate(parent, [{"clarification": "RC-T", "context_link": "in the setting of"}])
    with pytest.raises(clarifications.ClarificationError, match="condensed_from"):
        clarifications.annotate(parent, [{"clarification": "RC-T", "brief": {"text": "x", "status": "proposed"}}])
    with pytest.raises(clarifications.ClarificationError, match="approved_by"):
        clarifications.annotate(
            parent, [{"clarification": "RC-T", "brief": {"text": "x", "status": "approved", "condensed_from": "RC-T"}}]
        )
    clarifications.annotate(
        parent,
        [
            {
                "clarification": "RC-T",
                "brief": {"text": "the zones", "status": "proposed", "condensed_from": "RC-T", "authored_by": "Claude"},
            }
        ],
    )
    assert parent["clarifications"][0]["means"] == CLAR_Z["means"]  # the approved clarification is intact
    assert parent["clarifications"][0]["brief"]["authorizes_wording"] is False and clarifications.proposed_briefs(
        parent
    ) == ["RC-T"]


# ---- relationship constraints, fragments, gaps ----------------------------------------------------------------------------------------------------


def test_relationship_constraints_and_clarification_obligations_reach_the_writer_in_both_variants():
    lo = Q.index("whether and how they relate to depth")
    rc = {
        **CLAR_Z,
        "id": "RC-A",
        "span": [lo, lo + 5],
        "phrase": "whether and how they relate to depth"[:5],
        "reference_word": None,
    }
    rc.pop("reference_word")
    rc["adds"] = ["manner"]
    for variant in VARIANTS:
        result, _ = _run(variant, clars=[CLAR_Z, {**rc, "means": "also how, with direction where documented"}])
        p = _prompt(result, "whether and how they relate")
        for text in ("specific reef zones", "relate to", "depth", "which kinds of depth", "RC-T"):
            assert text in p, (variant, text)
        assert (
            "answer form" in p.lower()
            and prompts.SAFEGUARDS["RELATION"][("full" if variant == "corrected-full" else "lean")][0] in p
        )


def test_a_fragment_sees_the_source_words_it_continues_as_context_but_may_not_ask_them_again():
    model = ScriptedModel(_respond_q2)
    result = run_engine(Q2, model, repair=False, prompt_variant="lean", clarifications=[CLAR_FRAGMENT, CLAR_UNIT])
    frag = (
        _child(result, "scales")
        if any("scales" in c["question"] for c in result["pass1"]["children"])
        else next(c for c in result["pass1"]["children"] if c["clarified_fragment"] == "RC-F")
    )
    prompt = _prompt(result, "Continues")
    assert (
        "Continues c2" in prompt
        and "specific pigments relate to shell color" in prompt
        and "do not ask it again" in prompt
    )
    again = "which specific pigments relate to shell color, using which scales?"
    bad = run_engine(
        Q2,
        ScriptedModel(
            lambda p, s: _respond_q2(p, s)
            if "requirements" in s["properties"] or "ambiguities" in s["properties"]
            else {"question": again, "unresolved": []}
        ),
        repair=False,
        prompt_variant="lean",
        clarifications=[CLAR_FRAGMENT, CLAR_UNIT],
    )
    dup = next(c for c in bad["pass1"]["children"] if c["clarified_fragment"] == "RC-F")
    assert "operator_added" in _flags(dup) or "possible_bundling_of_other_obligations" in {
        f["flag"] for f in dup["flags"]
    }
    assert frag["clarified_fragment"] == "RC-F"


GAP_Q = "how does coral bleaching spread across reefs? please return specific reef zones."


def _gap_run(wording: str, variant: str = "lean"):
    """A one-item request whose subject is stated only in its first sentence (nothing says how the item relates to it)."""

    def respond(prompt: str, schema: dict):
        props = schema["properties"]
        if "requirements" in props:
            part = prompt.split("Part to read:" + NL, 1)[1] if "Part to read:" + NL in prompt else ""
            if part.startswith("how does"):
                return {"requirements": [{"kind": "manner", "quotes": ["how"], "note": ""}]}
            if part.startswith("please return"):
                return {"requirements": [{"kind": "requested_item", "quotes": ["specific reef zones"], "note": ""}]}
            return {"requirements": []}
        if "ambiguities" in props:
            return {"ambiguities": []}
        return {"question": wording.replace("{S}", subject), "unresolved": []}

    parent = build_parent_contract(CallLog(ScriptedModel(respond)), GAP_Q)
    subject = parent["referents"][0]["text"]
    result = run_engine(GAP_Q, ScriptedModel(respond), repair=False, prompt_variant=variant)
    return result, subject


def test_an_item_the_request_leaves_unlinked_is_a_source_gap_kept_apart_from_a_writer_failure():
    unchanged, subject = _gap_run("please return specific reef zones")
    kid = next(c for c in unchanged["pass1"]["children"] if c["kind"] == "generated")
    assert kid["status"] == "source_gap" and not kid["diagnostics"]["hard_fail"]
    summary = unchanged["pass1"]["reconciliation"]["summary"]
    assert kid["child_id"] in summary["source_gap"] and kid["child_id"] not in summary["successful_children"]
    prompt = _prompt(unchanged, "please return specific reef zones")
    assert f'"{subject}"' in prompt and "do not connect them" in prompt  # the writer is told the link is not approved
    assert kid["unresolved_links"] and kid["unresolved_links"][0]["kind"] == "item_subject_link_unstated"
    for connective in ("involved in", "associated with", "in", "of", "for"):
        made, _ = _gap_run("please return specific reef zones " + connective + " {S}")
        writer = next(c for c in made["pass1"]["children"] if c["kind"] == "generated")
        assert writer["status"] == "semantic_review_required", connective  # the WRITER departed: not a gap
        assert {"link_introduced", "relation_word_added", "unsupported_substitution"} & _flags(writer), connective


# ---- the matched output budget ----------------------------------------------------------------------------------------------------------------


def test_the_matched_budget_covers_the_schema_and_v3_keeps_its_known_mismatch():
    budget = prompts.schema_output_budget(prompts.MATCHED_SCHEMA)
    assert (
        prompts.MATCHED_OUTPUT_CAP >= budget["tokens_at_1_5_chars_per_token"]
    )  # comfortable even at 1.5 chars per token
    assert prompts.MATCHED_SCHEMA["properties"]["question"]["maxLength"] == 600
    assert prompts.MATCHED_SCHEMA["required"] == ch.CHILD_SCHEMA["required"]  # same shape, only the limits differ
    assert set(prompts.MATCHED_SCHEMA["properties"]["unresolved"]["items"]["properties"]) == set(
        ch.CHILD_SCHEMA["properties"]["unresolved"]["items"]["properties"]
    )
    old = prompts.schema_output_budget(ch.CHILD_SCHEMA)
    assert (
        old["tokens_at_2_5_chars_per_token"] > ch.CHILD_OUTPUT_CAP
    )  # the frozen v3 permits more output than its cap allows


def test_a_request_that_cannot_fit_the_limit_is_reported_not_shortened_and_not_sent():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    from experiments.ask_cli_revised.decompose.children import plan_children

    plans, by = plan_children(parent), ch.by_id_map(parent)
    tight = {**prompts.settings_for("lean"), "limits": {**prompts.MATCHED_LIMITS, "question_max": 30}}
    model = ScriptedModel(lambda p, s: {"question": "x", "unresolved": []})
    plan = next(p for p in plans if p["kind"] == "anchor")
    child = ch.write_child(CallLog(model), parent, plan, by, pass_no=1, settings=tight, plans=plans)
    assert child["kind"] == "constraint_failure" and model.calls == []  # never sent
    assert child["constraint"]["constraint"] == "question_length" and child["constraint"]["needed_chars"] > 25
    assert child["question"] == " ".join(
        e["text"] for e in ch.child_context(parent, plan, by, plans=plans, governing_operation=True)["extract"]
    )  # exact words, not shortened
    ch.annotate(parent, child, by, plans)
    assert any(f["flag"] == "output_constraint_failure" for f in child["flags"])


class _Stub:
    label = "stub"

    def __init__(self, question, unresolved=(), truncated=False):
        self.out = {"question": question, "unresolved": list(unresolved)}
        self.truncated = truncated

    def call(self, prompt, *, schema, output_cap):
        return SchemaCall(
            json.dumps(self.out), self.out, True, self.truncated, not self.truncated, None, 0.0, output_cap, "stub"
        )

    def identity(self):
        return {}


def test_truncation_a_full_question_and_a_full_unresolved_list_are_detected_never_silent():
    parent = build_parent_contract(CallLog(ScriptedModel(base.responder())), Q)
    from experiments.ask_cli_revised.decompose.children import plan_children

    plans, by = plan_children(parent), ch.by_id_map(parent)
    plan = next(p for p in plans if p["kind"] == "anchor")
    settings = prompts.settings_for("lean")
    limits = settings["limits"]
    item = {"word": "w", "reading_used": "none chosen", "other_readings": []}
    cases = {
        "output_question_at_limit": _Stub("x" * limits["question_max"]),
        "unresolved_list_at_capacity": _Stub("How does it work", [item] * limits["unresolved_max"]),
        "output_truncated": _Stub("How does it work", truncated=True),
    }
    for flag, stub in cases.items():
        child = ch.write_child(CallLog(stub), parent, plan, by, pass_no=1, settings=settings, plans=plans)
        ch.annotate(parent, child, by, plans)
        assert flag in {f["flag"] for f in child["flags"]}, flag
        if flag != "unresolved_list_at_capacity":
            assert child["diagnostics"]["hard_fail"] if child["diagnostics"] else True


def test_a_subset_run_writes_only_the_listed_children_and_records_the_rest_without_a_call():
    result, model = _run("lean", only=["c1", "c2"])
    assert len(_writes(result)) == 2 and result["manifest"]["only"] == ["c1", "c2"]
    kinds = {c["child_id"]: c["kind"] for c in result["pass1"]["children"]}
    assert kinds["c1"] == kinds["c2"] == "generated" and set(v for k, v in kinds.items() if k not in ("c1", "c2")) == {
        "not_selected"
    }
    summary = result["pass1"]["reconciliation"]["summary"]
    assert "c3" in summary["not_selected"] and "c3" not in summary["successful_children"]
    assert (
        result["manifest"]["prompt_variant"] == "lean" and result["manifest"]["output_limits"] == prompts.MATCHED_LIMITS
    )


# ---- the held-out reference never reaches generation -------------------------------------------------------------------------------------------


def test_no_generation_module_or_rendered_prompt_contains_held_out_reference_material():
    root = Path(__file__).parent
    for path in sorted(root.glob("*.py")):
        if path.name.startswith("test_") or path.name == "reference_compare.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not [
            w for w in ("intent_reference", "expected_evidence", "q_aib", "anomalous", "Workman", "Hadza") if w in text
        ], path.name
    for variant in VARIANTS:
        result, _ = _run(variant, clars=[CLAR_Z])
        for rec in _writes(result):
            assert not any(
                w in rec["prompt"] for w in ("intent_reference", "expected_evidence", "4A", "4B", "held-out")
            )
    ref = (
        Path(__file__).resolve().parents[3]
        / ".local"
        / "decompose-runs"
        / "aib-dev"
        / "reference"
        / "q_aib.intent_reference.v2.json"
    )
    if ref.exists():
        held = json.loads(ref.read_text(encoding="utf-8"))
        evidence = [q["expected_evidence"] for q in held["questions"]]
        for variant in VARIANTS:
            root_dir = (
                Path(__file__).resolve().parents[3]
                / ".local"
                / "decompose-runs"
                / "aib-dev"
                / "offline_prompt_variants"
                / variant.replace("-", "_")
            )
            for f in sorted(root_dir.glob("*.request.json")) if root_dir.exists() else []:
                content = json.loads(f.read_text(encoding="utf-8"))["messages"][0]["content"]
                assert not any(e[:40] in content for e in evidence), f.name


def test_relation_parser_and_ledger_agree_that_a_leading_context_clause_does_not_hide_the_form():
    assert ledger.request_form("In the context of X, please return whether and how they relate to Y") == "imperative"
    assert ledger.request_form("In the context of X, whether they relate to Y") == "whether_clause"
    assert relations.parse_question("In the context of X, whether and how zones relate to depth")["form"] == "polar"
