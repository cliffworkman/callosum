import pytest

from experiments.ask_adjudication_revision.core import ROLES, SyntheticCase
from experiments.ask_adjudication_revision.frontier_contract import (
    batch_objects,
    escape_reason,
    parse_response,
    prompt,
    render_packet,
)


def test_labels_lossless_escaping_and_empty_no_flag():
    reason = 'Source Ω | says "mixed"\nwith \\ and\ttab\r.'
    for label in ("FLAG", "UNCERTAIN"):
        raw = (f"a | {label} | {escape_reason(reason)}\nb | NO_FLAG |\n").encode()
        result = parse_response(raw, ["a", "b"])
        assert result["technical_status"] == "VALID"
        assert result["rows"][0]["reason"] == reason
        assert result["rows"][1]["reason"] == ""
        assert parse_response(raw.replace(b"\n", b"\r\n"), ["a", "b"])["rows"] == result["rows"]


@pytest.mark.parametrize(
    "raw",
    [
        b"a | FLAG | reason",
        b"a | FLAG | reason\na | FLAG | reason",
        b"b | NO_FLAG |\na | FLAG | reason",
        b"x | FLAG | reason\nb | NO_FLAG |",
        b"a | MAYBE | reason\nb | NO_FLAG |",
        b"a | FLAG | \nb | NO_FLAG |",
        b"a | FLAG |    \nb | NO_FLAG |",
        b"a | NO_FLAG | certified\nb | NO_FLAG |",
        b"a | FLAG | reason\nb | NO_FLAG | ",
        b"a | FLAG | a|b\nb | NO_FLAG |",
        b"a | FLAG | bad\\q\nb | NO_FLAG |",
        b"a | FLAG | bad\\\nb | NO_FLAG |",
        b"a | FLAG | bad\ttext\nb | NO_FLAG |",
        b"```\na | FLAG | reason\nb | NO_FLAG |\n```",
        b"Prose\na | FLAG | reason\nb | NO_FLAG |",
        b" a | FLAG | reason\nb | NO_FLAG |",
        b"a | FLAG | reason\nb | NO_FLAG |\nextra",
        b"a | FLAG | reason\nb | NO_FLAG |\xff",
    ],
)
def test_no_repair_or_partial_favorable_rows(raw):
    for adapter in (False, True):
        result = parse_response(raw, ["a", "b"], copilot_empty_lines=adapter)
        assert result["technical_status"] != "VALID" and result["rows"] == []


def test_only_empty_line_adapter():
    raw = b"a | FLAG | reason\n\nb | NO_FLAG |\n"
    assert parse_response(raw, ["a", "b"])["technical_status"] != "VALID"
    assert parse_response(raw, ["a", "b"], copilot_empty_lines=True)["technical_status"] == "VALID"
    assert (
        parse_response(raw.replace(b"\n\n", b"\n \n"), ["a", "b"], copilot_empty_lines=True)["technical_status"]
        != "VALID"
    )


def test_utf8_budget_and_terminal_missingness():
    raw = ("a | UNCERTAIN | " + "Ω" * 256 + "\nb | NO_FLAG |\n").encode()
    assert parse_response(raw, ["a", "b"])["technical_status"] == "VALID"
    assert (
        parse_response(raw.replace(b" | UNCERTAIN | ", b" | UNCERTAIN | x"), ["a", "b"])["technical_status"] != "VALID"
    )
    for flags in ({"truncated": True}, {"service_failure": True}):
        assert parse_response(raw, ["a", "b"], **flags)["rows"] == []


def test_prompt_budgets_and_one_rater_combined_roles():
    assert len(prompt(["literal_fidelity", "skeptical_review"]).encode()) <= 2048
    assert all(len(prompt([role]).encode()) <= 2048 for role in ROLES)


def test_whole_object_batching_reproduction_and_no_source_pair():
    objects = []
    for i in range(5):
        obj = SyntheticCase(i, "fixture_a").content()
        obj["source"]["source_unit_id"] = "unit-" + str(i // 2)
        objects.append(obj)
    prompts = [prompt(["literal_fidelity", "skeptical_review"]), prompt(["qualifiers_modality"])]
    batches = batch_objects(objects, prompts)
    assert sorted(x["candidate_id"] for batch in batches for x in batch) == sorted(x["candidate_id"] for x in objects)
    assert batches == batch_objects(list(reversed(objects)), prompts)
    for batch in batches:
        assert len({x["source"]["source_unit_id"] for x in batch}) == len(batch)
        for p in prompts:
            assert len(render_packet(batch, p)) < 20480
