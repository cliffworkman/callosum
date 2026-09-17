from pathlib import Path

import pytest

from experiments.ask_070.contracts import ContractError
from experiments.ask_070.hashing import read_json
from experiments.ask_070.validation import validate

ROOT = Path(__file__).parents[1]


def test_real_frozen_nonsemantic_artifact_schemas():
    validate(
        read_json(ROOT / "frozen/corpus_presence_v0.json"), read_json(ROOT / "schemas/corpus_presence.schema.json")
    )
    for inv in read_json(ROOT / "frozen/referent_inventories_v0.json")["inventories"]:
        validate(inv, read_json(ROOT / "schemas/referent_inventory.schema.json"))


def test_validator_fails_closed():
    for data, schema in [
        (True, {"type": "integer"}),
        ({}, {"type": "object", "required": ["x"]}),
        ({"unexpected": 1}, {"type": "object", "additionalProperties": False}),
        ([], {"type": "array", "minItems": 1}),
        ("a", {"pattern": "^b$"}),
        ({}, {"$ref": "https://must-not-resolve.invalid/schema"}),
    ]:
        with pytest.raises(ContractError):
            validate(data, schema)
