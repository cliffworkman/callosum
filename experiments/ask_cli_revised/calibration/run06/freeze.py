"""Run 0.6 decomposition freeze: serialize the chosen decomposition + a content hash, then assert the
frozen items are never silently edited during the retrieval/context walk.

Once chosen, the decomposition is the FROZEN RETRIEVAL REPRESENTATION. `decomposition_hash` is over the
frozen items only (the load-bearing content); the walk calls `assert_unchanged` before and after retrieval
so downstream success/failure can never retro-edit the chosen representation.
"""

from __future__ import annotations

import hashlib
import json


def _frozen_items(items: list[dict]) -> list[dict]:
    """The minimal, order-stable item record that the walk consumes and the hash covers."""
    return [
        {
            "item_id": i["item_id"],
            "source_unit_id": i["source_unit_id"],
            "source_text": i["source_text"],
            "text": i["text"],
            "from_fallback": bool(i.get("from_fallback", False)),
            "is_baseline": bool(i.get("is_baseline", False)),
            "repaired": bool(i.get("repaired", False)),
        }
        for i in items
    ]


def decomposition_hash(items: list[dict]) -> str:
    canonical = json.dumps(_frozen_items(items), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def freeze_decomposition(*, case_id: str, question: str, selected: str, items: list[dict], selection: dict, repair: dict | None) -> dict:
    frozen_items = _frozen_items(items)
    payload = {
        "case_id": case_id,
        "question": question,
        "question_hash": hashlib.sha256(question.encode("utf-8")).hexdigest(),
        "selected_candidate": selected,
        "items": frozen_items,
        "decomposition_hash": decomposition_hash(items),
        "selection": selection,
        "repair": repair,
    }
    return payload


def assert_unchanged(frozen: dict, items: list[dict]) -> None:
    """Fail loudly if the frozen decomposition's content hash no longer matches (walk must not edit it)."""
    current = decomposition_hash(items)
    if current != frozen["decomposition_hash"]:
        raise AssertionError(
            f"frozen decomposition for {frozen['case_id']} changed during the walk "
            f"({frozen['decomposition_hash'][:12]} -> {current[:12]})"
        )
