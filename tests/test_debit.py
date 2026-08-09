from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.grim import DebitResult, debit_test


def test_debit_consistent_zero_variance():
    r = debit_test("0.000", "0.000", 10)  # K=0 -> SD exactly 0
    assert isinstance(r, DebitResult) and r.consistent is True and r.mean_consistent is True


def test_debit_consistent_all_ones():
    r = debit_test("1.000", "0.000", 10)  # K=n -> SD exactly 0
    assert r.consistent is True


def test_debit_consistent_matches_derived_formula():
    # K=5, n=10 -> SD = sqrt(5*5/(10*9))
    sd_exact = math.sqrt(5 * 5 / (10 * 9))
    r = debit_test("0.500", f"{sd_exact:.3f}", 10)
    assert r.consistent is True


def test_debit_inconsistent_sd():
    r = debit_test("0.500", "0.999", 10)
    assert r.consistent is False and r.mean_consistent is True


def test_debit_inconsistent_mean_short_circuits():
    # 0.333 is not achievable as K/10 for any integer K at 3 decimals.
    r = debit_test("0.333", "0.471", 10)
    assert r.consistent is False and r.mean_consistent is False


def test_debit_requires_n_at_least_2():
    with pytest.raises(ValueError):
        debit_test("1.0", "0.0", 1)


def test_debit_bad_inputs():
    with pytest.raises(ValueError):
        debit_test("0.5", "0.1", 0)


def test_debit_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    sd_exact = math.sqrt(5 * 5 / (10 * 9))
    r = client.post("/methods/debit", json={"mean": "0.500", "sd": f"{sd_exact:.3f}", "n": 10})
    assert r.status_code == 200
    assert r.json()["debit"]["consistent"] is True

    r2 = client.post("/methods/debit", json={"mean": "0.500", "sd": "0.999", "n": 10})
    assert r2.json()["debit"]["consistent"] is False

    assert client.post("/methods/debit", json={"mean": "0.5", "sd": "0.1", "n": 1}).status_code == 422
    assert client.post("/methods/debit", json={"mean": "not-a-number", "sd": "0.1", "n": 10}).status_code == 422
