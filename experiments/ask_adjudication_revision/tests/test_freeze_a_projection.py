import json

import pytest

from experiments.ask_adjudication_revision.core import BoundaryError, canonical
from experiments.ask_adjudication_revision.freeze_a_projection import array_records, project


def test_projects_only_selected_fields(monkeypatch):
    raw = canonical(
        {
            "unit_id": "fixture",
            "qid": "q_aib",
            "lineage": {"secret": "NEVER_DECODE"},
            "quote": 'Synthetic Ω with ] } \\" delimiters',
        }
    )
    original = json.loads
    decoded = []

    def record(value, *args, **kwargs):
        assert b"NEVER_DECODE" not in value
        decoded.append(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(json, "loads", record)
    assert project(raw, ("unit_id", "qid")) == {"unit_id": "fixture", "qid": "q_aib"}
    assert decoded


def test_array_boundaries_and_string_preservation():
    objects = [{"unit_id": "a", "quote": 'Ω\n\\"}]'}, {"unit_id": "b", "quote": None}]
    data = canonical(objects)
    assert [project(raw, ("unit_id", "quote")) for raw in array_records(data)] == objects


@pytest.mark.parametrize(
    "raw,fields",
    [(b'{"x":1,"x":2}', ("x",)), (b'{"x":1}', ("y",)), (b'{"x":1} trailing', ("x",)), (b'{"x":[1}', ("x",))],
)
def test_fixed_errors(raw, fields):
    with pytest.raises(BoundaryError):
        project(raw, fields)
