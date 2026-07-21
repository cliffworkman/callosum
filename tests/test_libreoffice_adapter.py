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
    # every item is normalized to the v2 shape (the original fields plus the defaulted per-occurrence keys)
    assert decoded["items"] == [
        {
            "id": "callosum-5",
            "title": "Attention",
            "type": "article-journal",
            "locator": None,
            "label": None,
            "prefix": None,
            "suffix": None,
            "suppress-author": False,
            "author-only": False,
            "custom_override": None,
        }
    ]


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


# ── inc TBD (P0 phase 1, backlog #33/#34): the versioned mark-payload schema ────────────────────────────────


def _raw_mark(payload: dict, rnd: str = "c1") -> str:
    """Build a mark name from a raw payload dict WITHOUT going through encode_mark_name's own version-stamping —
    lets a test construct an exact v1 (no "v" key) or unsupported-future-version payload."""
    import base64
    import json

    blob = base64.b64encode(json.dumps(payload).encode()).decode()
    return f"CALLOSUM_CITATION {blob} {rnd}"


def test_decode_v1_mark_gets_defaults_filled() -> None:
    """A mark written before this schema existed (no "v" key, a single bare item) must keep decoding losslessly —
    existing documents never need user action. Every new per-occurrence key is filled with its default."""
    name = _raw_mark({"items": [{"id": "callosum-1", "title": "Old Paper"}]})
    decoded = cc.decode_mark_name(name)
    assert decoded is not None
    assert decoded["v"] == 1
    assert decoded.get("unsupported") is not True
    item = decoded["items"][0]
    assert item["id"] == "callosum-1" and item["title"] == "Old Paper"
    assert item["locator"] is None and item["label"] is None
    assert item["prefix"] is None and item["suffix"] is None
    assert item["suppress-author"] is False and item["author-only"] is False
    assert item["custom_override"] is None


def test_decode_v2_mark_preserves_set_per_occurrence_fields() -> None:
    """A v2 payload with some per-occurrence keys already set round-trips those values exactly; only the keys
    it didn't set get defaulted."""
    name = _raw_mark(
        {
            "v": 2,
            "items": [
                {
                    "id": "callosum-9",
                    "title": "New Paper",
                    "locator": "12-15",
                    "label": "page",
                    "prefix": "see ",
                    "suppress-author": True,
                }
            ],
        }
    )
    decoded = cc.decode_mark_name(name)
    assert decoded is not None
    assert decoded["v"] == 2
    item = decoded["items"][0]
    assert item["locator"] == "12-15" and item["label"] == "page"
    assert item["prefix"] == "see " and item["suppress-author"] is True
    assert item["suffix"] is None and item["author-only"] is False  # not set → defaulted
    assert item["custom_override"] is None


def test_decode_unsupported_future_version_is_inert_not_foreign() -> None:
    """A mark from a future schema version must be recognized as OURS (never treated as a foreign/corrupt mark,
    which would let something else clobber it) but its items must never be guessed at."""
    name = _raw_mark({"v": 99, "items": [{"id": "callosum-1"}]})
    decoded = cc.decode_mark_name(name)
    assert decoded is not None  # ours, not foreign
    assert decoded["v"] == 99
    assert decoded["unsupported"] is True
    assert decoded["items"] is None  # never guessed at


def test_encode_always_stamps_current_schema_version() -> None:
    payload = {"items": [{"id": "callosum-3", "title": "X"}]}
    name = cc.encode_mark_name(payload, "c2")
    decoded = cc.decode_mark_name(name)
    assert decoded["v"] == cc.SCHEMA_VERSION
    # a caller-supplied "v" is overwritten, never trusted — encode_mark_name is the single source of truth
    name2 = cc.encode_mark_name({**payload, "v": 1}, "c3")
    assert cc.decode_mark_name(name2)["v"] == cc.SCHEMA_VERSION


def test_normalize_item_fills_only_missing_keys() -> None:
    out = cc._normalize_item({"id": "x", "locator": "3", "suppress-author": True})
    assert out["locator"] == "3" and out["suppress-author"] is True  # kept as-is
    assert out["label"] is None and out["prefix"] is None and out["suffix"] is None  # filled
    assert out["author-only"] is False and out["custom_override"] is None


# ── inc TBD (P0 phase 2, backlog #33/#34): the transactional-refresh verification oracle ────────────────────
# `_transactional_apply` itself (the UndoManager-grouped mutation + rollback) needs a real UNO `doc` to mean
# anything -- it's exercised by a fault-injection spike in `selftest_uno.py`, not faked here (this codebase's
# established split: real-doc mutation logic is only ever real-UNO-tested, never mocked). `_snapshot_marks` is
# the one piece of that mechanism simple enough to fake faithfully -- two duck-typed method calls, no risk of
# the fake diverging from real UNO semantics.


class _FakeAnchor:
    def __init__(self, text: str) -> None:
        self._text = text

    def getString(self) -> str:
        return self._text


class _FakeMark:
    def __init__(self, text: str) -> None:
        self._anchor = _FakeAnchor(text)

    def getAnchor(self) -> _FakeAnchor:
        return self._anchor


class _FakeMarks:
    def __init__(self, marks: dict) -> None:
        self._marks = marks

    def hasByName(self, name: str) -> bool:
        return name in self._marks

    def getByName(self, name: str) -> _FakeMark:
        return self._marks[name]


class _FakeDoc:
    def __init__(self, marks: dict) -> None:
        self._marks = _FakeMarks(marks)

    def getReferenceMarks(self) -> _FakeMarks:
        return self._marks


def test_snapshot_marks_reads_current_anchor_text() -> None:
    doc = _FakeDoc({"m1": _FakeMark("Smith, 2020"), "m2": _FakeMark("[1]")})
    assert cc._snapshot_marks(doc, ["m1", "m2"]) == {"m1": "Smith, 2020", "m2": "[1]"}
    assert cc._snapshot_marks(doc, ["m1", "missing"]) == {"m1": "Smith, 2020"}  # an absent name is silently skipped


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


# ── inc 156/157: highlight-to-suggest (the LibreOffice "Suggest citations" macro) ──────────────────────────


def test_build_suggest_rows_formats_stance_author_match_quote() -> None:
    suggestions = [
        {
            "paper_id": 5,
            "title": "Faces",
            "author": "Lovelace",
            "year": 2024,
            "match_score": 0.6234,
            "quote": "Facial anomalies influence social judgments in observers and beyond.",
            "stance": {"label": "supports", "confidence": 0.9, "probs": {}},
        },
        {
            "paper_id": 7,
            "title": "Signals",
            "author": None,
            "year": None,
            "match_score": 0.41,
            "quote": "x" * 200,
            "stance": None,
        },
    ]
    rows = cc.build_suggest_rows(suggestions)
    assert len(rows) == len(suggestions)  # parallel to suggestions (index → paper_id)
    assert rows[0].startswith("[supports] Lovelace 2024 · match 0.62 — ")
    assert "Facial anomalies" in rows[0]
    # no stance → "no stance"; no author/year → falls back to the title; a long quote is truncated with …
    assert rows[1].startswith("[no stance] Signals · match 0.41 — ")
    assert rows[1].endswith('…"')


def test_build_suggest_rows_match_fallbacks() -> None:
    assert "match 0.00" in cc.build_suggest_rows([{"paper_id": 1, "title": "T", "quote": "q"}])[0]
    assert "match ?" in cc.build_suggest_rows([{"paper_id": 1, "title": "T", "quote": "q", "match_score": "n/a"}])[0]


def test_fetch_suggestions_posts_and_returns_list(monkeypatch) -> None:
    captured = {}

    def fake_post(url, body, timeout=20):
        captured["url"], captured["body"] = url, body
        return {"suggestions": [{"paper_id": 3, "quote": "q"}]}

    monkeypatch.setattr(cc, "_post_json", fake_post)
    out = cc.fetch_suggestions("http://127.0.0.1:8080", "a draft sentence", top_k=4)
    assert out == [{"paper_id": 3, "quote": "q"}]
    assert captured["url"].endswith("/citations/suggest")
    assert captured["body"] == {"text": "a draft sentence", "top_k": 4, "evaluate": True}


def test_fetch_suggestions_defensive_on_bad_shape(monkeypatch) -> None:
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: {"oops": 1})
    assert cc.fetch_suggestions("http://x", "s") == []
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: ["not", "a", "dict"])
    assert cc.fetch_suggestions("http://x", "s") == []
