"""Per-case output schemas.

Vocabulary is deliberately limited to what is already proven on this Ollama/grammar stack:
object / required / additionalProperties:false / array+maxItems / string+enum / string+maxLength.
No `uniqueItems`: the bakeoff compares supervisory semantics, not models' handling of an unproven
grammar keyword, and duplicate IDs are removed deterministically after parsing (scoring.py).

`rationale` is declared first (property order is emission order for this grammar conversion) and is
bounded; it is stored for inspection but never scored.
"""

RATIONALE_MAX_CHARS = 400


def _rationale():
    return {"type": "string", "maxLength": RATIONALE_MAX_CHARS}


def _id_enum(ids):
    return {"type": "string", "enum": list(ids)}


def _obj(properties, required):
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def build_schema(spec):
    legal = spec["legal"]
    obligations = legal["obligation_ids"]
    family = spec["family"]
    if family == "A":
        selected = {"type": "array", "items": _id_enum(obligations), "maxItems": len(obligations)}
        return _obj(
            {"rationale": _rationale(), "responsive_obligation_ids": selected},
            ["rationale", "responsive_obligation_ids"],
        )
    if family == "B":
        supports = {
            "type": "array",
            "items": _id_enum(legal["proposition_ids"]),
            "maxItems": len(legal["proposition_ids"]),
        }
        entry = _obj(
            {
                "status": {"type": "string", "enum": ["responsive_support", "unresolved"]},
                "supporting_proposition_ids": supports,
            },
            ["status", "supporting_proposition_ids"],
        )
        coverage = _obj({ob: entry for ob in obligations}, obligations)
        return _obj({"rationale": _rationale(), "coverage": coverage}, ["rationale", "coverage"])
    if family == "C":
        plan = _obj({ob: _id_enum(legal["actions"][ob]) for ob in obligations}, obligations)
        return _obj({"rationale": _rationale(), "plan": plan}, ["rationale", "plan"])
    raise ValueError(f"unknown family {family!r}")
