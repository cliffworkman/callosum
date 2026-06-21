"""LibreOffice adapter (inc 108) — the UNO-free field-abstraction logic.

These cover the parts that don't need LibreOffice: the ReferenceMark name encode/decode (the live-field payload),
the document-order sort, the request builder, and the id stamp. The full insert→render→write-back→flatten
round-trip is exercised by `adapters/libreoffice/selftest_uno.py` (needs `uno` + a running soffice + callosum;
not collected here). The adapter module imports no `uno` at top level, so it loads fine under plain CPython.
"""

from __future__ import annotations

from adapters.libreoffice import callosum_cite as cc


def test_mark_name_roundtrip() -> None:
    payload = {"items": [{"id": "callosum-5", "title": "Attention", "type": "article-journal"}]}
    name = cc.encode_mark_name(payload, "c1")
    assert name.startswith("CALLOSUM_CITATION ") and len(name.split(" ")) == 3
    decoded = cc.decode_mark_name(name)
    assert decoded is not None
    assert decoded["rnd"] == "c1"
    assert decoded["items"] == payload["items"]


def test_decode_rejects_foreign_and_malformed() -> None:
    assert cc.decode_mark_name("ZOTERO_ITEM CSL_CITATION {}") is None  # another tool's mark
    assert cc.decode_mark_name("CALLOSUM_CITATION onlytwoparts") is None  # wrong arity
    assert cc.decode_mark_name("CALLOSUM_CITATION !!!notbase64!!! c1") is None  # bad base64/json
    assert cc.decode_mark_name("") is None
    # valid base64-json but no items → not a usable citation
    import base64
    import json

    empty = base64.b64encode(json.dumps({"items": []}).encode()).decode()
    assert cc.decode_mark_name(f"CALLOSUM_CITATION {empty} c1") is None


def test_stamp_item_id_is_stable_and_nondestructive() -> None:
    record = {"title": "X", "type": "article-journal"}
    stamped = cc.stamp_item_id(record, 42)
    assert stamped["id"] == "callosum-42"
    assert "id" not in record  # original untouched (copy)


def test_build_render_request_shape() -> None:
    fields = [
        {"citationID": "c1", "items": [{"id": "callosum-1"}], "_mark": object()},
        {"citationID": "c2", "items": [{"id": "callosum-2"}], "_mark": object()},
    ]
    req = cc.build_render_request(fields, "ieee", "en-US")
    assert req["style"] == "ieee" and req["locale"] == "en-US"
    assert req["citations"] == [
        {"citationID": "c1", "items": [{"id": "callosum-1"}]},
        {"citationID": "c2", "items": [{"id": "callosum-2"}]},
    ]
    assert "_mark" not in req["citations"][0]  # internal handle never sent to the server


def test_order_by_comparator_sorts_into_document_order() -> None:
    # compare(a, b) > 0 iff a precedes b (UNO compareRegionStarts convention).
    items = [{"id": "a", "pos": 2}, {"id": "b", "pos": 0}, {"id": "c", "pos": 1}]
    ordered = cc.order_by_comparator(items, lambda a, b: b["pos"] - a["pos"])
    assert [i["id"] for i in ordered] == ["b", "c", "a"]
