"""Unit tests for the bounded Ask query planner (inc 581). Pure -- no DB, no real provider."""

from __future__ import annotations

from types import SimpleNamespace

from app.backend.summarization.query_planner import (
    MAX_FACETS,
    NARROW,
    QueryPlan,
    broadening_hint_applies,
    classify_breadth,
    plan_query,
)

FROZEN_BROAD = (
    "Synthesize the neural and biological systems implicated in late-life depression and its "
    "relationship to cognitive decline and dementia based on the literature in my library. I am "
    "particularly interested in serotonergic function, amyloid, glucose metabolism, gray-matter "
    "structure, memory and executive function, and other relevant neurobiological or cognitive "
    "findings. Give me a structured account of the systems and processes involved, what role each "
    "appears to play, and where the literature reports mixed, null, or uncertain findings."
)


def _complete(text: str):
    """A fake provider-agnostic completion: returns an object with a ``.text`` attribute, exactly like
    ``app.backend.llm.providers.complete``. The 'provider' is irrelevant -- proves agnosticism."""

    def _fn(config, prompt):
        assert isinstance(prompt, str) and prompt  # the planner always builds a prompt string
        return SimpleNamespace(text=text)

    return _fn


# ---- pre-gate -------------------------------------------------------------------------------------


def test_classify_breadth_narrow_short():
    assert classify_breadth("What sample size did Smith 2019 use?") is False
    assert classify_breadth("hippocampal volume?") is False
    assert classify_breadth("") is False


def test_classify_breadth_broad_frozen_query():
    assert classify_breadth(FROZEN_BROAD) is True


def test_classify_breadth_enumeration_without_marker():
    # Several coordinated items -> escalate even without an explicit breadth verb.
    assert classify_breadth("Tell me about amyloid, serotonin, glucose metabolism, and gray matter changes") is True


def test_broadening_hint_fires_for_the_short_open_ended_case():
    # The flagship issue-#30 example: broad in meaning, short in wording -> routed narrow -> hint.
    assert broadening_hint_applies("What does my library say about brains?") is True


def test_broadening_hint_not_fired_for_empty_or_broad_or_long_questions():
    assert broadening_hint_applies("") is False
    assert broadening_hint_applies("   ") is False
    # A broad, enumerated question already escalates -> no hint (it will get broad treatment).
    assert broadening_hint_applies(FROZEN_BROAD) is False
    # A longer focused question is deliberately scoped -> not nagged even though it routes narrow.
    assert broadening_hint_applies("What sample size did Smith 2019 use in the anxiety-treatment cohort?") is False


def test_broadening_hint_only_fires_where_routing_is_narrow():
    # Invariant: the hint is a strict subset of narrow-routed questions -- it never contradicts routing.
    for q in ("What does my library say about brains?", "aging?", "", FROZEN_BROAD):
        if broadening_hint_applies(q):
            assert classify_breadth(q) is False


# ---- routing / fallback --------------------------------------------------------------------------


def test_narrow_question_never_calls_provider():
    calls = []

    def _fn(config, prompt):
        calls.append(prompt)
        return SimpleNamespace(text="{}")

    plan = plan_query("What was the effect size in Jones 2020?", config=object(), complete_fn=_fn)
    assert plan is NARROW
    assert plan.scope == "narrow" and not plan.facets
    assert calls == []  # the pre-gate short-circuits before any provider call


def test_broad_valid_plan():
    payload = (
        '{"scope":"broad","facets":['
        '{"label":"Serotonin","query":"serotonergic function late-life depression"},'
        '{"label":"Amyloid","query":"amyloid deposition late-life depression"},'
        '{"label":"Glucose","query":"cerebral glucose metabolism depression"}]}'
    )
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(payload))
    assert plan.is_broad
    assert plan.scope == "broad"
    assert [f.label for f in plan.facets] == ["Serotonin", "Amyloid", "Glucose"]
    assert plan.planner_used is True


def test_facet_count_capped():
    facets = ",".join(f'{{"label":"L{i}","query":"q{i} distinct topic"}}' for i in range(12))
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(f'{{"scope":"broad","facets":[{facets}]}}'))
    assert plan.is_broad
    assert len(plan.facets) == MAX_FACETS


def test_fewer_than_min_facets_falls_back_to_narrow():
    payload = '{"scope":"broad","facets":[{"label":"Only","query":"one facet only"}]}'
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(payload))
    assert plan is NARROW


def test_duplicate_queries_deduped_then_narrow():
    # Three facets but two collapse to the same normalized query -> only 2 distinct -> narrow.
    payload = (
        '{"scope":"broad","facets":['
        '{"label":"A","query":"amyloid deposition"},'
        '{"label":"B","query":"Amyloid   deposition!"},'
        '{"label":"C","query":"serotonin function"}]}'
    )
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(payload))
    assert plan is NARROW  # 2 distinct < MIN_FACETS


def test_planner_scope_narrow_is_respected():
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete('{"scope":"narrow","facets":[]}'))
    assert plan is NARROW


def test_malformed_json_falls_back():
    for junk in ["not json at all", "", "{", '{"scope":"broad"', "[1,2,3]"]:
        assert plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(junk)) is NARROW


def test_prose_wrapped_json_recovered():
    payload = (
        "Sure! Here is the plan:\n```json\n"
        '{"scope":"broad","facets":[{"label":"A","query":"alpha topic"},'
        '{"label":"B","query":"beta topic"},{"label":"C","query":"gamma topic"}]}\n```\nHope that helps!'
    )
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(payload))
    assert plan.is_broad and len(plan.facets) == 3


def test_provider_exception_falls_back():
    def _boom(config, prompt):
        raise RuntimeError("provider down")

    assert plan_query(FROZEN_BROAD, config=object(), complete_fn=_boom) is NARROW


def test_missing_or_empty_fields_dropped():
    payload = (
        '{"scope":"broad","facets":['
        '{"label":"","query":"empty label dropped"},'
        '{"label":"Ok1","query":""},'
        '{"label":"Ok2","query":"kept one two"},'
        '{"label":"Ok3","query":"kept three four"},'
        '{"label":"Ok4","query":"kept five six"}]}'
    )
    plan = plan_query(FROZEN_BROAD, config=object(), complete_fn=_complete(payload))
    assert plan.is_broad
    assert [f.label for f in plan.facets] == ["Ok2", "Ok3", "Ok4"]


def test_query_plan_is_broad_requires_min_facets():
    assert QueryPlan(scope="broad", facets=()).is_broad is False
