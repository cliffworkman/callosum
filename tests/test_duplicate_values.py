from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.duplicate_values import RepeatedValuesResult, count_repeated_values


def test_no_repeats():
    r = count_repeated_values(["1.0", "2.0", "3.0"])
    assert isinstance(r, RepeatedValuesResult)
    assert r.total == 3 and r.distinct == 3 and r.repeats == []
    assert r.note == "No exact value repeats more than once."


def test_one_value_repeats():
    r = count_repeated_values(["3.45", "3.45", "3.45", "2.10", "5.00"])
    assert r.total == 5 and r.distinct == 3
    assert r.repeats == [{"value": "3.45", "count": 3}]
    assert "1 value repeats" in r.note
    assert "blunt heuristic" in r.note and "GRIM/GRIMMER/DEBIT" in r.note


def test_multiple_values_repeat_sorted_by_count_then_value():
    r = count_repeated_values(["a", "a", "b", "b", "b", "c", "d", "d"])
    assert r.repeats == [{"value": "b", "count": 3}, {"value": "a", "count": 2}, {"value": "d", "count": 2}]
    assert "3 values repeat" in r.note


def test_blank_entries_are_ignored():
    r = count_repeated_values(["1.0", "", "  ", "1.0"])
    assert r.total == 2 and r.repeats == [{"value": "1.0", "count": 2}]


def test_whitespace_is_stripped_before_comparison():
    r = count_repeated_values([" 1.0 ", "1.0"])
    assert r.repeats == [{"value": "1.0", "count": 2}]


def test_rejects_empty_input():
    with pytest.raises(ValueError):
        count_repeated_values([])
    with pytest.raises(ValueError):
        count_repeated_values(["", "  "])


def test_rejects_oversized_input():
    with pytest.raises(ValueError):
        count_repeated_values(["1"] * 501)


def test_duplicate_values_endpoint(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/methods/duplicate-values", json={"values": ["3.45", "3.45", "2.10"]})
    assert r.status_code == 200
    body = r.json()["duplicate_values"]
    assert body["total"] == 3 and body["repeats"] == [{"value": "3.45", "count": 2}]

    assert client.post("/methods/duplicate-values", json={"values": []}).status_code == 422
    assert client.post("/methods/duplicate-values", json={"values": ["1"] * 501}).status_code == 422
