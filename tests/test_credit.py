"""CRediTer — CRediT contribution-statement builder (inc 261).

Hermetic (pure formatting, no network/model/DB). The load-bearing boundary — build, never infer — is pinned by an
AST scan (the module imports no model/LLM lib and defines no read/infer/score/judge/verify/aggregate function).
Malformed role/degree input raises; an empty or mid-entry grid is a valid empty statement, not an error.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods import credit as cr


def _author(name, *roles):
    # roles: (key,) for no degree, or (key, degree)
    return {"name": name, "roles": [{"role": r[0], "degree": (r[1] if len(r) > 1 else None)} for r in roles]}


# --- Formatter: by-author layout ----------------------------------------------------------------------------------


def test_by_author_canonical_role_order_and_degree():
    # roles supplied out of canonical order; degree only rendered when set.
    a = _author("Jane Smith", ("methodology",), ("conceptualization", "lead"), ("writing_original_draft",))
    st = cr.format_statement([a])
    # rendered in canonical taxonomy order: conceptualization < methodology < writing_original_draft
    assert st.by_author == ["Jane Smith: Conceptualization (lead), Methodology, Writing – original draft."]


def test_by_author_preserves_input_author_order_and_omits_roleless():
    authors = [
        _author("Bob Lee", ("software",)),
        _author("No Contributor"),  # zero roles → omitted from by_author
        _author("Amy Ng", ("validation", "supporting")),
    ]
    st = cr.format_statement(authors)
    assert st.by_author == [
        "Bob Lee: Software.",
        "Amy Ng: Validation (supporting).",
    ]


# --- Formatter: by-role layout ------------------------------------------------------------------------------------


def test_by_role_canonical_order_authors_in_input_order_and_omits_unused():
    authors = [
        _author("Jane Smith", ("conceptualization", "lead"), ("methodology",)),
        _author("Bob Lee", ("methodology", "supporting")),
    ]
    st = cr.format_statement(authors)
    # only used roles appear, in taxonomy order; authors within a role keep input order.
    assert st.by_role == [
        "Conceptualization: Jane Smith (lead).",
        "Methodology: Jane Smith, Bob Lee (supporting).",
    ]


def test_roles_legend_is_the_full_taxonomy():
    st = cr.format_statement([])
    assert [r["key"] for r in st.roles] == [r["key"] for r in cr.CREDIT_ROLES]
    assert len(st.roles) == 14


# --- Empty / de-dupe ----------------------------------------------------------------------------------------------


def test_empty_is_empty_statement_not_error():
    st = cr.format_statement([])
    assert st.by_author == [] and st.by_role == []


def test_duplicate_role_deduped_last_degree_wins():
    a = _author("Jane Smith", ("software",), ("software", "lead"))
    st = cr.format_statement([a])
    assert st.by_author == ["Jane Smith: Software (lead)."]


# --- Validation ---------------------------------------------------------------------------------------------------


def test_unknown_role_and_degree_raise():
    with pytest.raises(ValueError):
        cr.format_statement([_author("X", ("not_a_role",))])
    with pytest.raises(ValueError):
        cr.format_statement([{"name": "X", "roles": [{"role": "software", "degree": "primary"}]}])


def test_caps_raise():
    with pytest.raises(ValueError):
        cr.format_statement([_author(f"A{i}", ("software",)) for i in range(cr.MAX_AUTHORS + 1)])
    with pytest.raises(ValueError):
        cr.format_statement([_author("X" * (cr.MAX_NAME_LEN + 1), ("software",))])


# --- THE LOAD-BEARING BOUNDARY: no inference / model / aggregation code path --------------------------------------


def test_no_inference_code_path():
    assert cr.NO_INFERENCE is True
    src = Path(cr.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned_imports = {
        "google",
        "openai",
        "anthropic",
        "httpx",
        "transformers",
        "torch",
        "sentence_transformers",
        "numpy",
        "pandas",
        "fitz",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert n.name.split(".")[0] not in banned_imports, f"unexpected import {n.name}"
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned_imports, f"unexpected import {node.module}"
    banned_defs = {"infer", "score", "judge", "verify", "classify", "aggregate", "read_pdf", "extract", "predict"}
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not (defs & banned_defs), f"inference function(s) present: {defs & banned_defs}"


# --- Endpoint -----------------------------------------------------------------------------------------------------


def test_statement_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/credit/statement",
        json={
            "authors": [
                {
                    "name": "Jane Smith",
                    "roles": [
                        {"role": "conceptualization", "degree": "lead"},
                        {"role": "methodology"},
                    ],
                },
                {"name": "Bob Lee", "roles": [{"role": "software"}]},
            ]
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["by_author"] == [
        "Jane Smith: Conceptualization (lead), Methodology.",
        "Bob Lee: Software.",
    ]
    assert body["by_role"][0] == "Conceptualization: Jane Smith (lead)."
    assert len(body["roles"]) == 14
    # empty grid → 200 empty statement (not an error)
    re = client.post("/credit/statement", json={"authors": []})
    assert re.status_code == 200 and re.json()["by_author"] == []


def test_statement_endpoint_rejects_bad_input(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    # unknown role → 422
    assert (
        client.post(
            "/credit/statement",
            json={"authors": [{"name": "X", "roles": [{"role": "nope"}]}]},
        ).status_code
        == 422
    )
    # unknown degree → 422
    assert (
        client.post(
            "/credit/statement",
            json={"authors": [{"name": "X", "roles": [{"role": "software", "degree": "primary"}]}]},
        ).status_code
        == 422
    )
    # over-cap author count → 422 (Pydantic max_length on the list)
    too_many = {"authors": [{"name": f"A{i}", "roles": [{"role": "software"}]} for i in range(cr.MAX_AUTHORS + 1)]}
    assert client.post("/credit/statement", json=too_many).status_code == 422


def test_pending_roundtrip(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    # the in-memory holder is module-level (shared across app instances); reset for isolation.
    from app.backend.api.routers import credit as credit_router

    credit_router._pending_statement["text"] = ""
    assert client.get("/credit/pending").json()["text"] == ""
    # stage → pull
    staged = client.post("/credit/pending", json={"text": "Jane Smith: Conceptualization (lead)."})
    assert staged.status_code == 200
    assert client.get("/credit/pending").json()["text"] == "Jane Smith: Conceptualization (lead)."
    # over-long staged text → 422
    assert client.post("/credit/pending", json={"text": "x" * 20_001}).status_code == 422
