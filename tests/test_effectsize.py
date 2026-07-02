"""Effect-size converter (meta-analysis workbench SP1, inc 252).

Hermetic (pure math, no network/model). Every conversion is asserted against a hand-verified anchor (Borenstein et al.
2009 formulas). The load-bearing boundary — convert one study at a time, NEVER aggregate — is pinned by an AST scan
(the module imports no meta-analysis/aggregation lib and defines no pool/combine/heterogeneity/meta_regress/aggregate
function). Degenerate inputs raise.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods import effectsize as es


def _approx(x, target, tol=1e-3):
    assert abs(x - target) < tol, f"{x} != {target}"


# --- SMD → Hedges' g -----------------------------------------------------------------------------------------------


def test_smd_from_means():
    c = es.smd(103, 5.5, 50, 100, 4.5, 50)
    assert c.metric == "Hedges' g"
    _approx(c.value, 0.5924)
    _approx(c.variance, 0.04114)
    assert c.path and c.formula_source and "Borenstein" in c.formula_source
    # a 95% CI is computed from the variance
    assert c.ci_low < c.value < c.ci_high


def test_smd_from_t_and_f_agree():
    ct = es.smd_from_t(2.5, 30, 30)
    cf = es.smd_from_f(6.25, 30, 30)  # F = t²
    _approx(es._d_to_g(0.6455, 30, 30, [])[0], ct.value, 2e-3)
    _approx(ct.value, cf.value)
    assert any("two-group one-way F" in cav for cav in cf.caveats)


def test_smd_degenerate_raises():
    with pytest.raises(ValueError):
        es.smd(103, 0, 50, 100, 4.5, 50)  # zero SD
    with pytest.raises(ValueError):
        es.smd(103, 5.5, 1, 100, 4.5, 50)  # n<2


# --- SD derivations (the recorded "which path" choice) -------------------------------------------------------------


def test_sd_derivations():
    sd_se, _ = es.sd_from_se(1.0, 25)
    _approx(sd_se, 5.0)
    sd_ci, _ = es.sd_from_ci(98, 102, 25)
    _approx(sd_ci, 5.1021)
    sd_iqr, _ = es.sd_from_iqr(6.75)
    _approx(sd_iqr, 5.0037)
    c = es.sd_derivation({"method": "ci", "lo": 98, "hi": 102, "n": 25})
    _approx(c.value, 5.1021)
    assert c.choices and "95% CI" in c.choices[0]


# --- Correlation → Fisher's z --------------------------------------------------------------------------------------


def test_correlation():
    c = es.correlation(0.5, 28)
    _approx(c.value, 0.5493)
    _approx(c.variance, 0.04)
    assert "Fisher" in c.formula_source
    with pytest.raises(ValueError):
        es.correlation(1.0, 28)  # r out of (−1,1)


# --- Binary → log OR / log RR / RD --------------------------------------------------------------------------------


def test_binary_measures():
    lor = es.binary(10, 20, 5, 25, "or")
    _approx(lor.value, 0.9163)
    _approx(lor.variance, 0.39)
    lrr = es.binary(10, 20, 5, 25, "rr")
    _approx(lrr.value, 0.6931)
    _approx(lrr.variance, 0.23333)
    rd = es.binary(10, 20, 5, 25, "rd")
    _approx(rd.value, 0.16667)
    _approx(rd.variance, 0.012037)


def test_binary_zero_cell_haldane():
    c = es.binary(0, 10, 5, 25, "or")
    _approx(c.value, -1.5106)
    _approx(c.variance, 2.31627)
    assert any("Haldane" in ch for ch in c.choices)


def test_binary_empty_raises():
    with pytest.raises(ValueError):
        es.binary(0, 0, 0, 0, "or")


# --- Cross-metric (APPROXIMATIONS, always caveated) ----------------------------------------------------------------


def test_cross_metric():
    dr = es.d_to_r(0.5, 50, 50)
    _approx(dr.value, 0.2425)
    assert dr.caveats and "APPROXIMATION" in dr.caveats[0]
    rd = es.r_to_d(0.3)
    _approx(rd.value, 0.6290)
    ld = es.logor_to_d(0.9163, 0.39)
    _approx(ld.value, 0.50518)
    _approx(ld.variance, 0.118546)
    for c in (dr, rd, ld):
        assert c.caveats and c.choices  # every cross-metric result records the approximation + the choice


# --- Dispatch + endpoint shape (via convert) -----------------------------------------------------------------------


def test_convert_dispatch():
    assert (
        es.convert("smd", {"method": "means", "m1": 103, "s1": 5.5, "n1": 50, "m2": 100, "s2": 4.5, "n2": 50}).metric
        == "Hedges' g"
    )
    assert es.convert("correlation", {"r": 0.5, "n": 28}).metric == "Fisher's z"
    assert es.convert("binary", {"a": 10, "b": 20, "c": 5, "d": 25}).metric == "log odds ratio"
    assert es.convert("cross", {"kind": "r_to_d", "r": 0.3}).metric.startswith("Cohen's d")
    with pytest.raises(ValueError):
        es.convert("nope", {})


# --- THE LOAD-BEARING BOUNDARY: no aggregation code path -----------------------------------------------------------


def test_no_aggregation_code_path():
    assert es.NO_AGGREGATION is True
    src = Path(es.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    # no import of a meta-analysis / stats-aggregation library
    banned_imports = {"numpy", "pandas", "statsmodels", "sklearn", "pymare", "metafor"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert n.name.split(".")[0] not in banned_imports, f"unexpected import {n.name}"
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned_imports, f"unexpected import {node.module}"
    # no pooling / heterogeneity / meta-regression / bias-inference function
    banned_defs = {
        "pool",
        "combine",
        "aggregate",
        "heterogeneity",
        "meta_regress",
        "meta_regression",
        "funnel",
        "eggers",
    }
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not (defs & banned_defs), f"aggregation function(s) present: {defs & banned_defs}"


def test_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/methods/effect-size",
        json={
            "family": "smd",
            "inputs": {"method": "means", "m1": 103, "s1": 5.5, "n1": 50, "m2": 100, "s2": 4.5, "n2": 50},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    _approx(body["value"], 0.5924)
    assert body["metric"] == "Hedges' g" and body["path"] and body["formula_source"]
    # binary via the endpoint
    rb = client.post(
        "/methods/effect-size",
        json={"family": "binary", "inputs": {"a": 10, "b": 20, "c": 5, "d": 25, "measure": "or"}},
    )
    _approx(rb.json()["value"], 0.9163)
    # degenerate + unknown family → 422
    assert (
        client.post("/methods/effect-size", json={"family": "correlation", "inputs": {"r": 2.0, "n": 28}}).status_code
        == 422
    )
    assert client.post("/methods/effect-size", json={"family": "nope", "inputs": {}}).status_code == 422
