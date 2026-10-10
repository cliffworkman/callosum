"""Preregistered attribution-only boundary tests. All fixtures are local and domain neutral."""

import ast
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from experiments.ask_cli_revised import assertion_authority as aa
from experiments.ask_cli_revised import ownership_context as oc
from experiments.ask_cli_revised import sufficiency_engine as se

HERE = Path(__file__).parent
CASES = json.loads((HERE / "attribution_i4_2b3_preregistered.json").read_text(encoding="utf-8"))
LEGACY = aa.ASSERTION_AUTHORITY_RULESET_I4_1F
NEW = aa.ASSERTION_AUTHORITY_RULESET_I4_2B3
R1 = (
    "We examined responses at levels A and B. At level A, scores increased. "
    "At level B, ratings decreased. Across these levels, scores correlated with ratings."
)


def snapshot(text, quote=None, *, cid=101, pid="unit", checksum="source", occurrence=None):
    quote = text[text.index("Across these levels") :] if quote is None else quote
    row = {
        "proposition_id": pid,
        "paper_id": 10,
        "evidence_anchor_chunk_id": cid,
        "evidence_span_id": "span",
        "quote": quote,
        "provenance": {"context_read": [cid]},
    }
    if occurrence is not None:
        row["provenance"]["quote_span_in_chunk"] = occurrence
    chunk = {
        "chunk_id": cid,
        "attachment_id": 20,
        "source_attachment_checksum": checksum,
        "text": text,
        "chunk_type": "body_prose",
        "extraction_tool": "test",
        "extraction_version": "1",
    }
    sealed, packets = {"verified_propositions": [row]}, [{"paper_id": 10, "chunks": [chunk]}]
    return sealed, packets, row


def prepared(text=R1, quote=None):
    sealed, packets, row = snapshot(text, quote)
    index = oc.build_context_index(sealed, packets)
    return oc.context_for(index, row), row, index


def proof_for(context, quote, target):
    legacy = aa.classify_surface(quote, target)["results"]
    records = []
    if context.get("status") == "available":
        para = context["paragraph_text"]
        records = aa.classify_target_assertions(para, target_start=0, target_end=len(para))["assertions"]
    return oc.resolve_local_antecedent(context, quote, legacy["assertion"]["span"], records)


def classify(text, target, context=None):
    return aa.classify_surface(text, target, ruleset_version=NEW, ownership_context=context)["results"]


def relation(result):
    return aa.assertion_relation(result["assertion_source"])


@pytest.mark.parametrize("case", CASES["initial_cases"], ids=lambda c: c["id"] + "-" + c["name"])
def test_B1_all_32(case):
    text, target = case["text"], case["target"]
    legacy = aa.classify_surface(text, target)["results"]
    assert relation(legacy) == case["legacy_relation"]
    assert legacy["assertion_kind"] == case["kind"]
    context = None
    quote = text
    if case["name"].startswith("context_"):
        view, row, _ = prepared(text)
        quote = row["quote"]
        context = proof_for(view, quote, target)
    got = classify(quote, target, context)
    assert relation(got) == case["corrected_relation"]
    old = aa.classify_surface(quote, target)["results"]
    for key in ("assertion", "assertion_kind", "aggregation", "authority_veto"):
        assert got[key] == old[key]


LOCAL = [
    ("E04", "Recent work found X.6 Scores increased.7 Ratings decreased.6", "Ratings decreased", "unresolved"),
    ("E05", "Recent work found X.6 We examined Y. Scores increased.6", "Scores increased", "unresolved"),
    ("E06", "Recent work found X.6\n\nScores increased.6", "Scores increased", "unresolved"),
    ("E14", "Results: Scores increased. Ratings decreased.", "Ratings decreased", "unresolved"),
    ("E15", "Results: Scores increased; ratings decreased.", "ratings decreased", "unresolved"),
    ("E16", "Results: Scores increased, whereas ratings decreased.", "ratings decreased", "current_document"),
    (
        "E17",
        "Results: Scores increased, whereas previous studies found that ratings decreased.",
        "ratings decreased",
        "attributed_external",
    ),
    (
        "E18",
        "Results: Scores increased, while previous studies found that ratings decreased.",
        "ratings decreased",
        "attributed_external",
    ),
    ("E19", "Results: Scores increased, whereas ratings decreased.6", "ratings decreased", "unresolved"),
    (
        "E21",
        "Results: Scores increased, whereas we suggest that ratings decreased.",
        "ratings decreased",
        "current_document",
    ),
    (
        "E22",
        "Background: X changed. Results: Scores increased, while ratings decreased.",
        "ratings decreased",
        "unresolved",
    ),
    ("E23", "Results: Previous studies found X, whereas ratings decreased.", "ratings decreased", "unresolved"),
    ("E24", "Recent work found X.6 By contrast, scores increased.6", "scores increased", "unresolved"),
    ("E25", "Recent work found X.6,7 Scores increased.7,6", "Scores increased", "attributed_external"),
    ("E26", "Recent work found X.6–8 Scores increased.6,7,8", "Scores increased", "attributed_external"),
    (
        "E27-statistic",
        "Recent work found scores at p = 0.06. Scores increased at p = 0.06.",
        "Scores increased",
        "unresolved",
    ),
    ("E27-bare-number", "Recent work found 6 scores. Scores increased by 6.", "Scores increased", "unresolved"),
    ("E27-unsupported-brackets", "Recent work found X [6]. Scores increased [6].", "Scores increased", "unresolved"),
    ("E27-descending-range", "Recent work found X.8–6 Scores increased.8–6", "Scores increased", "unresolved"),
    (
        "E28-unparsed-sentence",
        "Recent work found X.6 An unrelated fragment. Scores increased.6",
        "Scores increased",
        "unresolved",
    ),
    (
        "R2-no-recursion",
        "Recent work found X.6 Scores increased.6 Ratings decreased.6",
        "Ratings decreased",
        "unresolved",
    ),
    ("R2-partial-overlap", "Recent work found X.6,7 Scores increased.7,8", "Scores increased", "unresolved"),
    (
        "R3-third-clause",
        "Results: Scores increased, while ratings decreased, whereas counts increased.",
        "counts increased",
        "unresolved",
    ),
    (
        "R3-replication",
        "Results: Scores increased, while ratings replicated previous results.",
        "ratings replicated",
        "unresolved",
    ),
]
for connector in ("while", "whereas"):
    for token in ("probably decreased", "could decrease", "did not increase"):
        LOCAL.append(
            (
                f"E20-{connector}-{token}",
                f"Results: Scores increased, {connector} ratings {token}.",
                f"ratings {token}",
                "unresolved",
            )
        )
    for marker in ("ref.", "refs.", "cf.", "et al."):
        LOCAL.append(
            (
                f"R3-marker-{connector}-{marker}",
                f"Results: Scores increased, {connector} ratings decreased ({marker} 6).",
                "ratings decreased",
                "unresolved",
            )
        )


@pytest.mark.parametrize("name,text,target,expected", LOCAL, ids=[r[0] for r in LOCAL])
def test_local_matrix(name, text, target, expected):
    got = classify(text, target)
    assert relation(got) == expected


def test_E07_missing_context():
    quote = R1[R1.index("Across these levels") :]
    got = classify(quote, "scores correlated")
    assert relation(got) == "unresolved"
    assert got["ownership"]["context_status"] == "unavailable"


@pytest.mark.parametrize(
    "field,value",
    [
        ("quote_sha256", "0" * 64),
        ("target_assertion_span", [0, 999]),
        ("quote_span_in_chunk", [0, 999]),
        ("source", {"paper_id": 999}),
        ("schema_version", "unknown"),
        ("resolver_version", "unknown"),
        ("relation", "invalid"),
        ("context_entry_id", "0" * 64),
        ("owner_assertion_span_in_chunk", [-1, 20]),
    ],
    ids=[
        "E08-quote-hash",
        "E08-target-span",
        "E08-out-of-bounds",
        "E08-source-identity",
        "E31-schema",
        "E31-resolver",
        "E31-relation",
        "E08-entry-hash",
        "E08-owner-span",
    ],
)
def test_E08_E31_invalid_proof(field, value):
    view, row, _ = prepared()
    proof = proof_for(view, row["quote"], "scores correlated")
    assert proof["status"] == "applied"
    proof["proofs"][0][field] = value
    got = classify(row["quote"], "scores correlated", proof)
    assert relation(got) == "unresolved"
    assert got["ownership"]["context_status"] == "invalid"


@pytest.mark.parametrize("mutate", ["source_hash", "quote_hash", "span", "identity"])
def test_E08_context_integrity(mutate):
    view, row, index = prepared()
    eid = view["entry_id"]
    sid = view["entry"]["source_id"]
    if mutate == "source_hash":
        index["sources"][sid]["text"] += " altered"
    elif mutate == "quote_hash":
        index["entries"][eid]["quote_sha256"] = "0" * 64
    elif mutate == "span":
        index["entries"][eid]["quote_span_in_chunk"] = [-1, 10000]
    else:
        index["sources"][sid]["paper_id"] = 999
    assert oc.context_for(index, row)["status"] == "invalid"


def test_E09_repeated_quote_and_verified_locator():
    quote = R1[R1.index("Across these levels") :]
    text = R1 + " " + quote
    sealed, packets, row = snapshot(text, quote)
    assert oc.context_for(oc.build_context_index(sealed, packets), row)["status"] == "ambiguous"
    start = text.index(quote)
    row["provenance"]["quote_span_in_chunk"] = [start, start + len(quote)]
    assert oc.context_for(oc.build_context_index(sealed, packets), row)["status"] == "available"


def test_E10_prior_antecedent():
    view, row, _ = prepared(R1.replace("We examined", "Previous studies examined"))
    got = classify(row["quote"], "scores correlated", proof_for(view, row["quote"], "scores correlated"))
    assert relation(got) == "attributed_external"


@pytest.mark.parametrize(
    "text",
    [
        R1.replace("At level A", "We examined responses at levels A and B. At level A"),
        R1.replace("At level B", "At level A"),
        R1.replace("At level B, ratings decreased. ", ""),
    ],
    ids=["E11-two-introductions", "E11-duplicate-header", "E11-missing-header"],
)
def test_E11_ambiguous_antecedent(text):
    view, row, _ = prepared(text)
    got = classify(row["quote"], "scores correlated", proof_for(view, row["quote"], "scores correlated"))
    assert relation(got) == "unresolved"


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("We found that ", "current_document"),
        ("Previous studies found that ", "attributed_external"),
    ],
    ids=["E12-explicit-current", "E13-explicit-external"],
)
def test_explicit_owner_wins(prefix, expected):
    quote = prefix + "scores correlated with ratings."
    assert relation(classify(quote, "scores correlated", {"status": "conflicting", "failure": "competing"})) == expected


def test_E29_missing_bytes():
    view, row, _ = prepared()
    del view["source"]["text"]
    assert proof_for(view, row["quote"], "scores correlated")["status"] == "invalid"


@pytest.mark.parametrize(
    "mode", ["agree", "conflict", "missing"], ids=["pooled-agreement", "E30-conflict", "E30-missing"]
)
def test_pooled_sources(mode):
    view, row, _ = prepared()
    a = proof_for(view, row["quote"], "scores correlated")
    if mode == "missing":
        b = oc.failure("context_unavailable")
    else:
        text = R1 if mode == "agree" else R1.replace("We examined", "Previous studies examined")
        sealed, packets, other = snapshot(text, cid=102)
        bview = oc.context_for(oc.build_context_index(sealed, packets), other)
        b = proof_for(bview, other["quote"], "scores correlated")
    merged = oc.combine_proofs([a, b])
    got = classify(row["quote"], "scores correlated", merged)
    assert relation(got) == ("current_document" if mode == "agree" else "unresolved")
    if mode == "agree":
        assert len(got["ownership"]["proofs"]) == 2


@pytest.mark.parametrize(
    "text,target,expected",
    [
        ("Recent work found X.6 Scores increased.6", "Scores increased", "attributed_external"),
        ("Results: Scores increased, while ratings decreased.", "ratings decreased", "current_document"),
    ],
    ids=["E32-R2", "E32-R3"],
)
def test_E32_local_survives_bad_context(text, target, expected):
    got = classify(text, target, {"status": "applied", "proofs": [{"malformed": True}]})
    assert relation(got) == expected
    assert got["ownership"]["context_status"] == "invalid"


def test_E33_append_stability_and_defensive_copy():
    sealed, packets, row = snapshot(R1)
    first = oc.build_context_index(sealed, packets)
    s2, p2, _ = snapshot(R1.replace("A and B", "C and D"), cid=999, pid="other")
    sealed["verified_propositions"] += s2["verified_propositions"]
    second = oc.build_context_index(sealed, packets + p2)
    assert oc.context_for(first, row) == oc.context_for(second, row)
    view = oc.context_for(first, row)
    view["source"]["text"] = "modified"
    assert oc.context_for(first, row)["source"]["text"] == R1


def test_E34_seeded_chunks_absent():
    sealed, _, row = snapshot(R1)
    packets = [{"paper_id": 10, "candidate_spans": [{"text": row["quote"]}]}]
    view = oc.context_for(oc.build_context_index(sealed, packets), row)
    assert view["status"] == "unavailable"
    for text, target, expected in [
        ("Recent work found X.6 Scores increased.6", "Scores increased", "attributed_external"),
        ("Results: Scores increased, while ratings decreased.", "ratings decreased", "current_document"),
    ]:
        assert relation(classify(text, target, view)) == expected


APIS = [
    "classify_assertion_authority",
    "classify_target_assertions",
    "locate_containing_assertion",
    "classify_surface",
    "classify_all_occurrences",
    "aggregation",
]


def invoke(name, **kwargs):
    if name == "locate_containing_assertion":
        return getattr(aa, name)("Scores increased.", 0, 6, **kwargs)
    if name in ("classify_surface", "classify_all_occurrences"):
        return getattr(aa, name)("Scores increased.", "Scores", **kwargs)
    return getattr(aa, name)("Scores increased.", target_start=0, target_end=6, **kwargs)


@pytest.mark.parametrize("name", APIS)
@pytest.mark.parametrize("version", [None, "", "latest", 1, [], {}])
def test_E37_unknown_rulesets(name, version):
    with patch.object(aa, "_all_assertions", side_effect=AssertionError("parsed before validation")):
        with pytest.raises(ValueError, match="unsupported"):
            invoke(name, ruleset_version=version)


@pytest.mark.parametrize("name", APIS)
def test_E36_E37_dispatch_legacy_isolation(name):
    with patch.object(aa, "_corrected_fields", side_effect=AssertionError("legacy reached corrected resolver")):
        assert invoke(name) == invoke(name, ruleset_version=LEGACY)
    with pytest.raises(ValueError):
        invoke(name, ownership_context={})
    with pytest.raises(ValueError):
        invoke(name, ruleset_version=NEW, structural_context={"owner_signal": "this_study"})


def test_E38_multi_assertion_attachment():
    text = "Results: Scores increased, while ratings decreased."
    a = aa.classify_target_assertions(text, target_start=0, target_end=len(text))
    b = aa.classify_target_assertions(text, target_start=0, target_end=len(text), ruleset_version=NEW)
    assert a["target_scope"] == b["target_scope"]
    assert [r["assertion"] for r in a["assertions"]] == [r["assertion"] for r in b["assertions"]]
    singular = aa.classify_assertion_authority(text, target_start=0, target_end=len(text), ruleset_version=NEW)
    assert singular["ambiguity"] is not None


@pytest.mark.parametrize("one,two", [("cobalt", "amber"), ("channel alpha", "channel beta"), ("R7", "T8")])
def test_E39_opaque_items(one, two):
    text = (
        R1.replace("A and B", one + " and " + two)
        .replace("level A,", "level " + one + ",")
        .replace("level B,", "level " + two + ",")
    )
    view, row, _ = prepared(text)
    assert (
        relation(classify(row["quote"], "scores correlated", proof_for(view, row["quote"], "scores correlated")))
        == "current_document"
    )


@pytest.mark.parametrize("noun", ["scores", "counts", "values"])
def test_E40_order_and_neutral_nouns(noun):
    texts = [f"Recent work found X.6 {noun} increased.6", f"Results: Counts increased, while {noun} decreased."]

    def run(items):
        return {
            t: relation(classify(t, noun + (" increased" if t.startswith("Recent") else " decreased"))) for t in items
        }

    assert run(texts) == run(list(reversed(texts)))


def test_legacy_ast_freeze():
    freeze = json.loads((HERE / "assertion_authority_legacy_freeze.json").read_text())
    nodes = {}
    for node in ast.parse(Path(aa.__file__).read_text(encoding="utf-8")).body:
        names = (
            [node.name]
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
            else [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node, ast.Assign)
            else [node.target.id]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            else []
        )
        for name in names:
            nodes[name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    assert len(freeze["nodes"]) == 119
    assert {name: nodes[name] for name in freeze["nodes"]} == freeze["nodes"]


def test_context_purity_and_domain_neutrality():
    source = Path(oc.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"__future__", "copy", "hashlib", "json", "re"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(n.name in allowed for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.module in allowed
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "exec", "eval", "__import__"}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not any(
                word in node.value.lower()
                for word in ("q_aib", "p41", "p40", "34974", "attractiveness", "support_policy")
            )
    assert not any(word in source for word in ("assertion_authority", "sufficiency_engine"))


def test_candidate_optional_schema():
    old = se.new_candidate_support(
        supporting_proposition_ids=["unit"],
        exact_text="Scores increased",
        assertion_relation="unresolved",
        aggregation="non_synthetic_or_unspecified",
        assertion_kind="result",
    )
    assert "attribution" not in old
    assert se.new_candidate_supports([old]) == [old]
    with pytest.raises(ValueError):
        se.new_candidate_supports([{**old, "attribution": None}])


def historical_cases():
    names = [
        "assertion_authority_preregistered.json",
        "assertion_authority_holdout.json",
        *[
            f"assertion_authority_i4_1{phase}_{kind}.json"
            for phase in ("b", "c")
            for kind in ("preregistered", "holdout", "twins")
        ],
        "prior_source_review_i4_1f_preregistered.json",
        *[f"aggregation_i4_1f_{kind}.json" for kind in ("preregistered", "holdout", "twins")],
    ]

    def walk(value):
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                yield value
            else:
                for child in value.values():
                    yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    return [(name, case) for name in names for case in walk(json.loads((HERE / name).read_text(encoding="utf-8")))]


@pytest.mark.parametrize(
    "name,case", historical_cases(), ids=[f"{n}:{c.get('id', i)}" for i, (n, c) in enumerate(historical_cases())]
)
def test_E36_every_historical_text_case_complete_equality(name, case):
    text = case["text"]
    kw = {k: case[k] for k in ("is_caption", "structural_context") if k in case}
    target = case.get("target", {})
    if not isinstance(target, dict):
        target = {}
    surface = target.get("surface", case.get("target_surface", text))
    start = text.find(surface)
    assert start >= 0
    args = {"target_start": start, "target_end": start + len(surface), **kw}
    with patch.object(aa, "_corrected_fields", side_effect=AssertionError("legacy correction")):
        for fn in (aa.classify_assertion_authority, aa.classify_target_assertions):
            assert fn(text, **args) == fn(text, **args, ruleset_version=LEGACY)
        for fn in (aa.classify_surface, aa.classify_all_occurrences):
            assert fn(text, surface, **kw) == fn(text, surface, **kw, ruleset_version=LEGACY)
        assert aa.locate_containing_assertion(
            text, start, start + len(surface), **kw
        ) == aa.locate_containing_assertion(text, start, start + len(surface), **kw, ruleset_version=LEGACY)


def unauthorized_consumers(sources, module, allowed):
    violations = []
    for name, source in sources.items():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("experiments.ask_cli_revised"):
                if (
                    (node.module or "").endswith("." + module) or any(n.name == module for n in node.names)
                ) and name not in allowed:
                    violations.append(name)
            if (
                isinstance(node, ast.Import)
                and any(n.name.endswith("." + module) for n in node.names)
                and name not in allowed
            ):
                violations.append(name)
    return violations


def test_exact_consumer_allowlists_and_negative_guards():
    root = HERE.parents[1]
    sources = {
        str(p.relative_to(root)).replace("\\", "/"): p.read_text(encoding="utf-8")
        for base in (root / "app", root / "experiments")
        for p in base.rglob("*.py")
        if not p.name.startswith("test") and p.name != "conftest.py" and "tests" not in p.parts
    }
    prefix = "experiments/ask_cli_revised/"
    authority_allowed = {prefix + "sufficiency_mapping.py"}
    context_allowed = {
        prefix + n
        for n in (
            "ownership_context.py",
            "sufficiency_mapping.py",
            "sufficiency_diagnostic.py",
            "e2e.py",
            "producer_replay.py",  # D1's fixed, offline issuer builds context from pinned byte snapshots.
        )
    }
    assert not unauthorized_consumers(sources, "assertion_authority", authority_allowed)
    assert not unauthorized_consumers(sources, "ownership_context", context_allowed)
    for module, allowed in (("assertion_authority", authority_allowed), ("ownership_context", context_allowed)):
        bad = {prefix + "answer_plan/unauthorized.py": f"from experiments.ask_cli_revised import {module}"}
        assert unauthorized_consumers(bad, module, allowed)


def test_conflicting_proposals_are_inspectable():
    view, row, _ = prepared()
    proof = proof_for(view, row["quote"], "scores correlated")
    with patch.object(
        aa, "_local_rule_proofs", return_value=[{"relation": "attributed_external", "rule_id": "test-conflict"}]
    ):
        got = classify(row["quote"], "scores correlated", proof)
    assert relation(got) == "unresolved"
    assert got["ownership"]["context_status"] == "conflicting"
    assert len(got["ownership"]["proofs"]) == 2


@pytest.mark.parametrize(
    "field,value",
    [("header_spans_in_chunk", [[-1, 999], [0, 999]]), ("anaphor_span_in_chunk", [0, 999]), ("list_items", ["A", "A"])],
)
def test_malformed_structural_proof_spans(field, value):
    view, row, _ = prepared()
    proof = proof_for(view, row["quote"], "scores correlated")
    proof["proofs"][0][field] = value
    got = classify(row["quote"], "scores correlated", proof)
    assert relation(got) == "unresolved"
    assert got["ownership"]["context_status"] == "invalid"


@pytest.mark.parametrize("mode", ["agree", "conflict", "missing"])
def test_E30_mapper_preserves_pooled_ids(mode):
    from experiments.ask_cli_revised import sufficiency_mapping as sm
    from experiments.ask_cli_revised.test_i4_2a_local_grounding import FREE, SPEC, unit

    view, row, _ = prepared()
    quote = row["quote"]
    text = R1 if mode == "agree" else R1.replace("We examined", "Previous studies examined")
    sealed, packets, other = snapshot(text, cid=102)
    second = oc.context_for(oc.build_context_index(sealed, packets), other)
    pooled = unit(quote, ids=("first", "second"))
    pooled["ownership_contexts"] = {"first": view, "second": second if mode != "missing" else oc.failure("missing")}
    result = sm._bind_achieved_outcome_v6(SPEC, [pooled], sibling_bindings=None, role_completion=FREE)
    candidate = result[0]["candidate_supports"][0]
    assert candidate["supporting_proposition_ids"] == ["first", "second"]
    assert candidate["assertion_relation"] == ("current_document" if mode == "agree" else "unresolved")


@pytest.mark.parametrize("connector", ["while", "whereas"])
def test_caption_does_not_receive_results_coordination(connector):
    text = f"Results: Scores increased, {connector} ratings decreased."
    got = aa.classify_surface(text, "ratings decreased", ruleset_version=NEW, is_caption=True)["results"]
    assert relation(got) == "unresolved"


@pytest.mark.parametrize("change", ["anaphor", "header", "list", "reset", "paragraph"])
def test_R1_outside_grammar_stays_unresolved(change):
    text = R1
    quote = R1[R1.index("Across these levels") :]
    if change == "anaphor":
        quote = quote.replace("Across these levels", "Across these categories")
        text = text.replace("Across these levels", "Across these categories")
    elif change == "header":
        text = text.replace("At level A", "At tier A")
    elif change == "list":
        text = text.replace("at levels A and B", "at tiers A and B")
    elif change == "reset":
        text = text.replace("At level B", "However, at level B")
    else:
        text = text.replace("At level B", "\n\nAt level B")
    view, row, _ = prepared(text, quote)
    assert (
        relation(classify(quote, "scores correlated", proof_for(view, row["quote"], "scores correlated")))
        == "unresolved"
    )


def test_R2_proof_boundary_after_whitespace_blank_line():
    prefix = "An unrelated fragment.\n \n"
    text = prefix + "Recent work found X.6 Scores increased.6"
    got = classify(text, "Scores increased")
    assert relation(got) == "attributed_external"
    assert got["ownership"]["proofs"][0]["paragraph_span"][0] == len(prefix)
