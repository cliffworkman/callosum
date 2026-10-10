"""Fixed repository trust root. No caller-selectable registry or material paths."""

from pathlib import Path

from experiments.ask_cli_revised._producer_schema import (
    _LOADER_TOKEN,
    ROOT_SCHEMA,
    _trusted_registry,
    decode,
    require,
    valid_ref,
    validate_material,
)

_BASE = Path(__file__).resolve().parent
_REGISTRY = _BASE / "producer_authorization.registry.json"
_STORE = _BASE / "producer_authorization_material"


def _references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if ":sha256:" in key:
                yield key
            yield from _references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)
    elif isinstance(value, str) and ":sha256:" in value:
        yield value


def load_trusted_producer_registry():
    """Load ONLY the installation's root; edits to that root belong to threat E."""
    body = decode(_REGISTRY.read_bytes())
    require(body.get("schema") == ROOT_SCHEMA, "registry schema")
    validate_material(body)
    materials = {}
    pending = list(_references(body))
    while pending:
        ref = pending.pop()
        schema, sha = valid_ref(ref)
        if ref in materials:
            continue
        path = _STORE / (schema + "--" + sha + ".json")
        require(path.resolve().parent == _STORE.resolve(), "material path escape")
        try:
            material = decode(path.read_bytes())
        except OSError as exc:
            raise ValueError("missing fixed producer material: " + ref) from exc
        validate_material(material, ref)
        materials[ref] = material
        pending.extend(_references(material))
    return _trusted_registry(body, materials, _LOADER_TOKEN)
