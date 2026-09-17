"""Small fail-closed validator for this package's deliberately bounded JSON Schema vocabulary."""

import re

from .contracts import ContractError

SUPPORTED = {
    "$schema",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "pattern",
}


def validate(value, schema, location="$"):
    if set(schema) - SUPPORTED:
        raise ContractError("UNSUPPORTED_SCHEMA_KEYWORD")
    types = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: type(v) is int,
        "number": lambda v: type(v) in (int, float),
        "boolean": lambda v: type(v) is bool,
        "null": lambda v: v is None,
    }
    expected = schema.get("type")
    if expected is not None:
        names = expected if isinstance(expected, list) else [expected]
        if any(t not in types for t in names) or not any(types[t](value) for t in names):
            raise ContractError("SCHEMA_TYPE:" + location)
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError("SCHEMA_ENUM:" + location)
    if "const" in schema and value != schema["const"]:
        raise ContractError("SCHEMA_CONST:" + location)
    if isinstance(value, dict):
        if set(schema.get("required", [])) - set(value):
            raise ContractError("SCHEMA_REQUIRED:" + location)
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, child in value.items():
            if key in props:
                validate(child, props[key], location + "." + key)
            elif extra is False:
                raise ContractError("SCHEMA_ADDITIONAL_PROPERTY:" + location)
            elif isinstance(extra, dict):
                validate(child, extra, location + "." + key)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise ContractError("SCHEMA_ARRAY_LENGTH:" + location)
        for index, child in enumerate(value):
            validate(child, schema.get("items", {}), f"{location}[{index}]")
    if type(value) in (int, float):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            raise ContractError("SCHEMA_NUMERIC_BOUND:" + location)
    if isinstance(value, str) and "pattern" in schema and not re.search(schema["pattern"], value):
        raise ContractError("SCHEMA_PATTERN:" + location)
    return True
