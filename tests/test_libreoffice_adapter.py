"""LibreOffice adapter (inc 108) — the UNO-free field-abstraction logic.

These cover the parts that don't need LibreOffice: the ReferenceMark name encode/decode (the live-field payload),
the document-order sort, the request builder, and the id stamp. The full insert→render→write-back→flatten
round-trip is exercised by `adapters/libreoffice/selftest_uno.py` (needs `uno` + a running soffice + callosum;
not collected here). The adapter module imports no `uno` at top level, so it loads fine under plain CPython.
"""

from __future__ import annotations

import pytest

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


def test_fetch_csl_translates_422_to_value_error(monkeypatch) -> None:
    """The export endpoint 422s on an all-missing/trashed result rather than returning 200 + []
    (`routers/papers.py::export_citations`) -- found empirically by the phase-9 diagnostics spike, which
    showed fetch_csl's own "empty rows" check was unreachable dead code for this exact case."""
    import urllib.error

    def raise_422(url, body, timeout=20):
        raise urllib.error.HTTPError(url, 422, "Unprocessable Entity", {}, None)

    monkeypatch.setattr(cc, "_post_json", raise_422)
    with pytest.raises(ValueError, match="No paper with id 999999"):
        cc.fetch_csl("http://127.0.0.1:8080", 999999)


def test_fetch_csl_does_not_swallow_other_http_errors(monkeypatch) -> None:
    import urllib.error

    def raise_500(url, body, timeout=20):
        raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None)

    monkeypatch.setattr(cc, "_post_json", raise_500)
    with pytest.raises(urllib.error.HTTPError):
        cc.fetch_csl("http://127.0.0.1:8080", 1)


def test_fetch_suggestions_defensive_on_bad_shape(monkeypatch) -> None:
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: {"oops": 1})
    assert cc.fetch_suggestions("http://x", "s") == []
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: ["not", "a", "dict"])
    assert cc.fetch_suggestions("http://x", "s") == []


# ── inc TBD (P0 phase 9, backlog #33/#34): document diagnostics ─────────────────────────────────────────────
# `diagnose_document` reads two simple UNO collections (getReferenceMarks/getBookmarks) and makes an HTTP call
# per distinct cited paper id -- simple + faithfully fakeable, like `_snapshot_marks` above (real mutation stays
# real-UNO-only; this is read-only inspection).


class _FakeMarksCollection:
    def __init__(self, names: list[str]) -> None:
        self._names = names

    def getElementNames(self) -> list[str]:
        return self._names


class _FakeBookmarks:
    def __init__(self, names) -> None:
        self._names = set(names)

    def hasByName(self, name: str) -> bool:
        return name in self._names


class _FakeDiagDoc:
    def __init__(self, mark_names: list[str], bookmark_names=()) -> None:
        self._marks = _FakeMarksCollection(mark_names)
        self._bookmarks = _FakeBookmarks(bookmark_names)

    def getReferenceMarks(self) -> _FakeMarksCollection:
        return self._marks

    def getBookmarks(self) -> _FakeBookmarks:
        return self._bookmarks


def _ok_mark(paper_id: str, rnd: str) -> str:
    return cc.encode_mark_name({"items": [{"id": f"callosum-{paper_id}"}]}, rnd)


def test_diagnose_document_clean_document_reports_nothing(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {"id": f"callosum-{pid}"})
    doc = _FakeDiagDoc([_ok_mark("1", "c1")], bookmark_names={cc.BIB_BOOKMARK, cc.BIB_BOOKMARK_END})
    report = cc.diagnose_document(doc, "http://127.0.0.1:8080")
    assert report == {
        "malformed": [],
        "unsupported_version": [],
        "duplicate_ids": [],
        "orphaned": [],
        "bibliography": "ok",
    }


def test_diagnose_document_ignores_marks_from_other_tools(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {})
    doc = _FakeDiagDoc(["ZOTERO_ITEM CSL_CITATION {}"])
    report = cc.diagnose_document(doc, "http://x")
    assert report["malformed"] == []  # not ours -- irrelevant to this diagnostic, not a defect to report


def test_diagnose_document_detects_malformed() -> None:
    bad_name = "CALLOSUM_CITATION !!!notbase64!!! c1"
    doc = _FakeDiagDoc([bad_name])
    report = cc.diagnose_document(doc, "http://x")
    assert report["malformed"] == [bad_name]


def test_diagnose_document_detects_unsupported_version() -> None:
    name = _raw_mark({"v": 99, "items": [{"id": "callosum-1"}]}, rnd="c9")
    doc = _FakeDiagDoc([name])
    report = cc.diagnose_document(doc, "http://x")
    assert report["unsupported_version"] == ["c9"]
    assert report["orphaned"] == []  # never guessed at -- no fetch_csl call for an unsupported mark's items


def test_diagnose_document_detects_duplicate_ids(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {})
    # two distinct marks (different payload -> different mark name) sharing the same rnd -- a real UNO
    # ReferenceMark name is unique, but the embedded "rnd" citationID is a separate value we don't enforce.
    doc = _FakeDiagDoc([_ok_mark("1", "c1"), _ok_mark("2", "c1")])
    report = cc.diagnose_document(doc, "http://x")
    assert report["duplicate_ids"] == ["c1"]


def test_diagnose_document_detects_orphaned_and_caches_per_paper(monkeypatch) -> None:
    calls = []

    def fake_fetch(base, pid):
        calls.append(pid)
        raise ValueError(f"No paper with id {pid} in the library.")

    monkeypatch.setattr(cc, "fetch_csl", fake_fetch)
    # the same missing paper cited twice must only trigger one fetch_csl call
    doc = _FakeDiagDoc([_ok_mark("404", "c1"), _ok_mark("404", "c2")])
    report = cc.diagnose_document(doc, "http://x")
    assert report["orphaned"] == ["404"]
    assert calls == ["404"]


def test_diagnose_document_connectivity_errors_are_not_reported_as_orphaned(monkeypatch) -> None:
    def fake_fetch(base, pid):
        raise OSError("connection refused")

    monkeypatch.setattr(cc, "fetch_csl", fake_fetch)
    doc = _FakeDiagDoc([_ok_mark("1", "c1")])
    with pytest.raises(OSError):
        cc.diagnose_document(doc, "http://x")


def test_diagnose_document_bibliography_states(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {})
    ok = cc.diagnose_document(_FakeDiagDoc([_ok_mark("1", "c1")], {cc.BIB_BOOKMARK, cc.BIB_BOOKMARK_END}), "http://x")
    assert ok["bibliography"] == "ok"
    damaged_no_end = cc.diagnose_document(_FakeDiagDoc([_ok_mark("1", "c1")], {cc.BIB_BOOKMARK}), "http://x")
    assert damaged_no_end["bibliography"] == "damaged"
    damaged_no_start = cc.diagnose_document(_FakeDiagDoc([_ok_mark("1", "c1")], {cc.BIB_BOOKMARK_END}), "http://x")
    assert damaged_no_start["bibliography"] == "damaged"
    not_built = cc.diagnose_document(_FakeDiagDoc([_ok_mark("1", "c1")]), "http://x")
    assert not_built["bibliography"] == "not_built"
    no_citations = cc.diagnose_document(_FakeDiagDoc([]), "http://x")
    assert no_citations["bibliography"] == "n/a"


# ── Phase 5c (backlog #33/#34): csl_record_row -- formatting an EXISTING citation's CSL record for the
# composer's Edit-Citation pre-population (as opposed to build_search_rows, which formats a /papers?q= hit) ──


def test_csl_record_row_formats_family_name_and_issued_year() -> None:
    record = {
        "title": "Attention is all you need",
        "author": [{"family": "Vaswani", "given": "Ashish"}, {"family": "Shazeer", "given": "Noam"}],
        "issued": {"date-parts": [[2017]]},
    }
    row = cc.csl_record_row(record)
    assert row == "Vaswani et al. 2017 — Attention is all you need"


def test_csl_record_row_defensive_on_missing_fields() -> None:
    assert cc.csl_record_row({}) == "— n.d. — Untitled"
    single_author = cc.csl_record_row({"author": [{"family": "Devlin"}], "title": "BERT"})
    assert single_author == "Devlin n.d. — BERT"  # no "et al." for a single author


def test_csl_record_row_truncates_long_titles() -> None:
    long_title = "X" * 200
    row = cc.csl_record_row({"title": long_title, "issued": {"date-parts": [[2020]]}})
    assert row.endswith("…") and len(row) < len(long_title)
