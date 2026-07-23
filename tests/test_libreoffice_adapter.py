"""LibreOffice adapter (inc 108) — the UNO-free field-abstraction logic.

These cover the parts that don't need LibreOffice: the ReferenceMark name encode/decode (the live-field payload),
the document-order sort, the request builder, and the id stamp. The full insert→render→write-back→flatten
round-trip is exercised by `adapters/libreoffice/selftest_uno.py` (needs `uno` + a running soffice + callosum;
not collected here). The adapter module imports no `uno` at top level, so it loads fine under plain CPython.
"""

from __future__ import annotations

from types import SimpleNamespace

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


def test_partial_refresh_wrappers_select_only_the_requested_surface(monkeypatch) -> None:
    calls = []

    def fake_refresh(doc, base, **kwargs):
        calls.append((doc, base, kwargs))
        return {"ok": True}

    monkeypatch.setattr(cc, "refresh", fake_refresh)
    doc = object()
    assert cc.refresh_citations(doc, "http://x") == {"ok": True}
    assert cc.refresh_bibliography(doc, "http://x") == {"ok": True}
    assert calls == [
        (doc, "http://x", {"update_bibliography": False}),
        (doc, "http://x", {"update_citations": False, "update_bibliography": True}),
    ]


def test_refresh_selected_citation_targets_only_mark_at_cursor(monkeypatch) -> None:
    calls = []
    field = {"_mark": SimpleNamespace(Name="CALLOSUM_CITATION target")}
    monkeypatch.setattr(cc, "mark_at_cursor", lambda doc: field)
    monkeypatch.setattr(
        cc,
        "refresh",
        lambda doc, base, **kwargs: calls.append((doc, base, kwargs)) or {"ok": True},
    )
    doc = object()

    assert cc.refresh_selected_citation(doc, "http://x") == {"ok": True}
    assert calls == [
        (
            doc,
            "http://x",
            {
                "update_bibliography": False,
                "citation_names": {"CALLOSUM_CITATION target"},
            },
        )
    ]


def test_refresh_selected_citation_requires_cursor_inside_mark(monkeypatch) -> None:
    messages = []
    monkeypatch.setattr(cc, "mark_at_cursor", lambda doc: None)
    monkeypatch.setattr(cc, "_msgbox", messages.append)
    monkeypatch.setattr(cc, "refresh", lambda *args, **kwargs: pytest.fail("refresh should not run"))

    assert cc.refresh_selected_citation(object(), "http://x") is None
    assert messages == ["Place your cursor inside a citation to refresh it."]


@pytest.mark.parametrize(
    ("cite_auto", "bib_auto", "expected", "expected_dirty"),
    [
        (True, True, {"update_citations": True, "update_bibliography": True}, []),
        (True, False, {"update_citations": True, "update_bibliography": False}, [{"bibliography": True}]),
        (False, True, {"update_citations": False, "update_bibliography": True}, [{"citations": True}]),
        (False, False, None, [{"citations": True, "bibliography": True}]),
    ],
)
def test_auto_refresh_honors_the_two_independent_preferences(
    monkeypatch, cite_auto, bib_auto, expected, expected_dirty
) -> None:
    calls = []
    dirty_calls = []
    monkeypatch.setattr(cc, "cite_auto_enabled", lambda doc: cite_auto)
    monkeypatch.setattr(cc, "bib_auto_enabled", lambda doc: bib_auto)
    monkeypatch.setattr(cc, "refresh", lambda doc, base, **kwargs: calls.append((doc, base, kwargs)) or {"ok": True})
    monkeypatch.setattr(cc, "set_dirty_state", lambda doc, **kwargs: dirty_calls.append(kwargs))
    doc = object()

    result = cc._auto_refresh(doc, "http://x")

    if expected is None:
        assert result is None
        assert calls == []  # both paused means no render request, not merely a no-op write-back
    else:
        assert result == {"ok": True}
        assert calls == [(doc, "http://x", expected)]
    assert dirty_calls == expected_dirty


def test_auto_refresh_failure_marks_both_surfaces_pending(monkeypatch) -> None:
    dirty_calls = []
    monkeypatch.setattr(cc, "cite_auto_enabled", lambda doc: True)
    monkeypatch.setattr(cc, "bib_auto_enabled", lambda doc: True)
    monkeypatch.setattr(cc, "set_dirty_state", lambda doc, **kwargs: dirty_calls.append(kwargs))

    def fail_refresh(doc, base, **kwargs):
        raise OSError("server unavailable")

    monkeypatch.setattr(cc, "refresh", fail_refresh)
    with pytest.raises(OSError, match="server unavailable"):
        cc._auto_refresh(object(), "http://x")
    assert dirty_calls == [{"citations": True, "bibliography": True}]


@pytest.mark.parametrize(
    ("state", "expected_kwargs"),
    [
        ((True, False), {"update_citations": True, "update_bibliography": False}),
        ((False, True), {"update_citations": False, "update_bibliography": True}),
        ((True, True), {"update_citations": True, "update_bibliography": True}),
    ],
)
def test_refresh_pending_targets_exact_dirty_surfaces(monkeypatch, state, expected_kwargs) -> None:
    calls = []
    monkeypatch.setattr(cc, "dirty_state", lambda doc: state)
    monkeypatch.setattr(cc, "refresh", lambda doc, base, **kwargs: calls.append(kwargs) or {"ok": True})
    assert cc.refresh_pending(object(), "http://x") == {"ok": True}
    assert calls == [expected_kwargs]


def test_refresh_pending_is_noop_when_clean(monkeypatch) -> None:
    synced = []
    monkeypatch.setattr(cc, "dirty_state", lambda doc: (False, False))
    monkeypatch.setattr(cc, "_sync_dirty_infobar", lambda doc: synced.append(doc))
    doc = object()
    assert cc.refresh_pending(doc, "http://x") is None
    assert synced == [doc]


def test_toggle_citation_auto_reports_manual_refresh_path(monkeypatch) -> None:
    states = []
    messages = []
    monkeypatch.setattr(cc, "cite_auto_enabled", lambda doc: False)
    monkeypatch.setattr(cc, "set_cite_auto", lambda doc, enabled: states.append(enabled))
    monkeypatch.setattr(cc, "_msgbox", messages.append)

    cc.toggle_cite_auto_interactive(object(), "http://x")

    assert states == [True]
    assert "now ON" in messages[0]
    assert "Existing pending changes are not refreshed automatically" in messages[0]


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
    # P1 item #11 (backlog #33/#34): omitted entirely -> empty lists, matching the backend's additive contract.
    assert req["uncited_items"] == []
    assert req["bibliography_exclude_ids"] == []


def test_build_render_request_bibliography_editing_fields() -> None:
    req = cc.build_render_request(
        [], "apa", "en-US", uncited_items=[{"id": "callosum-9"}], bibliography_exclude_ids=["callosum-5"]
    )
    assert req["uncited_items"] == [{"id": "callosum-9"}]
    assert req["bibliography_exclude_ids"] == ["callosum-5"]


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


def test_fetch_suggestions_posts_and_returns_both_lists(monkeypatch) -> None:
    captured = {}

    def fake_post(url, body, timeout=20):
        captured["url"], captured["body"] = url, body
        return {"suggestions": [{"paper_id": 3, "quote": "q"}], "beyond_library_suggestions": [{"title": "X"}]}

    monkeypatch.setattr(cc, "_post_json", fake_post)
    out = cc.fetch_suggestions("http://127.0.0.1:8080", "a draft sentence", top_k=4)
    assert out == {"suggestions": [{"paper_id": 3, "quote": "q"}], "beyond_library_suggestions": [{"title": "X"}]}
    assert captured["url"].endswith("/citations/suggest")
    assert captured["body"] == {
        "text": "a draft sentence",
        "top_k": 4,
        "evaluate": True,
        "include_beyond_library": False,
        "beyond_top_k": 5,
    }


def test_fetch_suggestions_include_beyond_library_flag_passes_through(monkeypatch) -> None:
    captured = {}

    def fake_post(url, body, timeout=20):
        captured["body"] = body
        return {"suggestions": [], "beyond_library_suggestions": []}

    monkeypatch.setattr(cc, "_post_json", fake_post)
    cc.fetch_suggestions("http://x", "s", include_beyond_library=True, beyond_top_k=3)
    assert captured["body"]["include_beyond_library"] is True
    assert captured["body"]["beyond_top_k"] == 3


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
    empty = {"suggestions": [], "beyond_library_suggestions": []}
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: {"oops": 1})
    assert cc.fetch_suggestions("http://x", "s") == empty
    monkeypatch.setattr(cc, "_post_json", lambda *a, **k: ["not", "a", "dict"])
    assert cc.fetch_suggestions("http://x", "s") == empty


# ── backlog #30 (Track C SP2/Stage-3): beyond-library suggest, wired into the LibreOffice adapter ───────────


def test_build_beyond_suggest_rows_prefers_relationship_label_over_reason() -> None:
    rows = cc.build_beyond_suggest_rows(
        [
            {
                "title": "Graph Attention Networks",
                "authors": ["Velickovic"],
                "year": 2018,
                "relationship_label": "Cited by a locally relevant paper: Vaswani et al. 2017",
                "reason": "Surfaced by openalex from title/abstract metadata; metadata term overlap 0.34.",
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0].startswith("[beyond library] Velickovic 2018 — Graph Attention Networks — ")
    assert "Cited by a locally relevant paper" in rows[0]
    assert "term overlap" not in rows[0]  # relationship_label wins when both are present


def test_build_beyond_suggest_rows_falls_back_to_reason_then_generic() -> None:
    reason_only = cc.build_beyond_suggest_rows([{"title": "X", "reason": "matches your search terms"}])
    assert "matches your search terms" in reason_only[0]
    generic = cc.build_beyond_suggest_rows([{"title": "X"}])
    assert "public metadata match" in generic[0]


def test_save_beyond_library_item_posts_expected_fields_and_returns_paper_id(monkeypatch) -> None:
    captured = {}

    def fake_post(url, body, timeout=20):
        captured["url"], captured["body"] = url, body
        return {"paper_id": 42, "created": True}

    monkeypatch.setattr(cc, "_post_json", fake_post)
    paper_id = cc.save_beyond_library_item(
        "http://127.0.0.1:8080",
        {
            "title": "Graph Attention Networks",
            "doi": "10.1/x",
            "abstract": "We present...",
            "authors": ["Velickovic"],
            "journal": "ICLR",
            "year": 2018,
            "url": "https://example.org/gat",
        },
    )
    assert paper_id == 42
    assert captured["url"].endswith("/discovery/save")
    assert captured["body"] == {
        "title": "Graph Attention Networks",
        "doi": "10.1/x",
        "abstract": "We present...",
        "authors": ["Velickovic"],
        "journal": "ICLR",
        "year": 2018,
        "url": "https://example.org/gat",
    }


def test_save_beyond_library_item_defaults_missing_fields() -> None:
    """paper_id is the only thing the caller actually needs back; title/authors get sane defaults so a
    minimally-populated candidate (e.g. from a bare public-metadata search hit) never 422s on a missing field."""
    import unittest.mock

    with unittest.mock.patch.object(cc, "_post_json", return_value={"paper_id": 7}) as mock_post:
        cc.save_beyond_library_item("http://x", {})
    _, body = mock_post.call_args.args
    assert body["title"] == "Untitled" and body["authors"] == []


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


class _FakeEmptyUserProps:
    def getPropertyValue(self, name: str) -> str:
        raise KeyError(name)


class _FakeDocumentProperties:
    def getUserDefinedProperties(self) -> _FakeEmptyUserProps:
        return _FakeEmptyUserProps()


class _FakeDiagDoc:
    def __init__(self, mark_names: list[str], bookmark_names=()) -> None:
        self._marks = _FakeMarksCollection(mark_names)
        self._bookmarks = _FakeBookmarks(bookmark_names)

    def getReferenceMarks(self) -> _FakeMarksCollection:
        return self._marks

    def getBookmarks(self) -> _FakeBookmarks:
        return self._bookmarks

    def getDocumentProperties(self) -> _FakeDocumentProperties:
        return _FakeDocumentProperties()


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
        "refresh_pending": {"citations": False, "bibliography": False},
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


# ── P1 item #12 (backlog #33/#34): list_document_citations -- the "Citations in this document" panel's data
# source. Unlike diagnose_document (which iterates getReferenceMarks() directly), this goes through
# scan_citations_in_order, so the fake needs a fuller doc: getText().compareRegionStarts for document order.


class _PanelAnchor:
    def __init__(self, pos: int) -> None:
        self.pos = pos


class _PanelMark:
    def __init__(self, name: str, pos: int) -> None:
        self.Name = name
        self._anchor = _PanelAnchor(pos)

    def getAnchor(self) -> _PanelAnchor:
        return self._anchor


class _PanelMarksCollection:
    def __init__(self, marks: dict) -> None:
        self._marks = marks

    def getElementNames(self) -> list[str]:
        return list(self._marks.keys())

    def getByName(self, name: str) -> _PanelMark:
        return self._marks[name]


class _PanelText:
    def compareRegionStarts(self, a: _PanelAnchor, b: _PanelAnchor) -> int:
        return b.pos - a.pos  # UNO convention: > 0 iff a precedes b


class _PanelUserProps:
    """Fakes the `getUserDefinedProperties()` bag well enough for `_get_id_list` (P1 item #11, backlog
    #33/#34): `getPropertyValue` raises for an unset name, matching `_user_prop`'s try/except -> None contract.
    Read-only — the write side (`_set_id_list`) needs a real `com.sun.star` import (like `_set_pref`/
    `set_bib_auto` before it) and so is only ever exercised via the real-UNO round-trip, never faked here."""

    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def getPropertyValue(self, name: str) -> str:
        if name not in self._values:
            raise KeyError(f"no such property: {name}")
        return self._values[name]


class _PanelDocProps:
    def __init__(self, props: _PanelUserProps) -> None:
        self._props = props

    def getUserDefinedProperties(self) -> _PanelUserProps:
        return self._props


class _PanelDoc:
    def __init__(self, marks: dict, user_props: dict[str, str] | None = None) -> None:
        self._marks = _PanelMarksCollection(marks)
        self._text = _PanelText()
        self._doc_props = _PanelDocProps(_PanelUserProps(user_props))

    def getReferenceMarks(self) -> _PanelMarksCollection:
        return self._marks

    def getText(self) -> _PanelText:
        return self._text

    def getDocumentProperties(self) -> _PanelDocProps:
        return self._doc_props


def test_auto_refresh_preferences_default_on_and_explicit_zero_disables() -> None:
    assert cc.cite_auto_enabled(_PanelDoc({}))
    assert cc.bib_auto_enabled(_PanelDoc({}))
    assert not cc.cite_auto_enabled(_PanelDoc({}, {cc.PREF_CITE_AUTO: "0"}))
    assert not cc.bib_auto_enabled(_PanelDoc({}, {cc.PREF_BIB_AUTO: "0"}))


def test_dirty_state_defaults_clean_and_reads_each_persisted_flag() -> None:
    assert cc.dirty_state(_PanelDoc({})) == (False, False)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_CITE_DIRTY: "1"})) == (True, False)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_BIB_DIRTY: "1"})) == (False, True)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_CITE_DIRTY: "1", cc.PREF_BIB_DIRTY: "1"})) == (True, True)


class _FakeInfobarController:
    def __init__(self, exists: bool = False) -> None:
        self.exists = exists
        self.appended = []
        self.updated = []
        self.removed = []

    def hasInfobar(self, infobar_id: str) -> bool:
        return self.exists

    def appendInfobar(self, *args) -> None:
        self.appended.append(args)
        self.exists = True

    def updateInfobar(self, *args) -> None:
        self.updated.append(args)

    def removeInfobar(self, infobar_id: str) -> None:
        self.removed.append(infobar_id)
        self.exists = False


class _FakeInfobarDoc(_PanelDoc):
    def __init__(self, user_props: dict[str, str], controller: _FakeInfobarController) -> None:
        super().__init__({}, user_props)
        self._controller = controller

    def getCurrentController(self) -> _FakeInfobarController:
        return self._controller


def test_dirty_infobar_is_non_dismissible_and_refreshes_exact_pending_state(monkeypatch) -> None:
    controller = _FakeInfobarController()
    doc = _FakeInfobarDoc({cc.PREF_CITE_DIRTY: "1", cc.PREF_BIB_DIRTY: "1"}, controller)
    button = object()
    monkeypatch.setattr(cc, "_infobar_refresh_button", lambda: button)

    assert cc._sync_dirty_infobar(doc)
    assert controller.appended == [
        (
            cc.DIRTY_INFOBAR_ID,
            "Callosum refresh pending",
            "Citation formatting and the bibliography are out of date.",
            2,
            (button,),
            False,
        )
    ]


def test_dirty_infobar_is_removed_when_persisted_state_is_clean() -> None:
    controller = _FakeInfobarController(exists=True)
    doc = _FakeInfobarDoc({}, controller)
    assert not cc._sync_dirty_infobar(doc)
    assert controller.removed == [cc.DIRTY_INFOBAR_ID]


def _panel_mark(paper_id: str, rnd: str, pos: int) -> tuple[str, _PanelMark]:
    name = cc.encode_mark_name({"items": [{"id": f"callosum-{paper_id}"}]}, rnd)
    return name, _PanelMark(name, pos)


def test_list_document_citations_groups_counts_and_orders(monkeypatch) -> None:
    monkeypatch.setattr(
        cc, "fetch_csl", lambda base, pid: {"title": f"Paper {pid}", "issued": {"date-parts": [[2020]]}}
    )
    monkeypatch.setattr(cc, "_get_json", lambda url: {"status": "none"})
    n1, m1 = _panel_mark("1", "c1", pos=1)
    n2, m2 = _panel_mark("2", "c2", pos=0)
    n3, m3 = _panel_mark("1", "c3", pos=2)  # paper 1 cited again -- rolls up into the SAME entry as n1
    doc = _PanelDoc({n1: m1, n2: m2, n3: m3})
    entries = cc.list_document_citations(doc, "http://x")
    assert [e["paper_id"] for e in entries] == ["2", "1"]  # document order: pos 0 (paper 2), then pos 1 (paper 1)
    paper1 = next(e for e in entries if e["paper_id"] == "1")
    assert paper1["count"] == 2
    assert paper1["orphaned"] is False
    assert paper1["retraction_label"] is None


def test_list_document_citations_marks_orphaned_and_retracted(monkeypatch) -> None:
    def fake_fetch(base, pid):
        if pid == "404":
            raise ValueError("missing")
        return {"title": "X", "issued": {"date-parts": [[2020]]}}

    monkeypatch.setattr(cc, "fetch_csl", fake_fetch)
    monkeypatch.setattr(cc, "_get_json", lambda url: {"status": "retracted"})
    n1, m1 = _panel_mark("1", "c1", pos=0)
    n2, m2 = _panel_mark("404", "c2", pos=1)
    doc = _PanelDoc({n1: m1, n2: m2})
    entries = cc.list_document_citations(doc, "http://x")
    by_id = {e["paper_id"]: e for e in entries}
    assert by_id["1"]["retraction_label"] == "RETRACTED"
    assert by_id["404"]["orphaned"] is True
    assert by_id["404"]["retraction_label"] is None  # never looked up for an orphaned paper


def test_list_document_citations_retraction_lookup_failure_is_non_fatal(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {"title": "X", "issued": {"date-parts": [[2020]]}})

    def fake_get(url):
        raise OSError("connection refused")

    monkeypatch.setattr(cc, "_get_json", fake_get)
    n1, m1 = _panel_mark("1", "c1", pos=0)
    doc = _PanelDoc({n1: m1})
    entries = cc.list_document_citations(doc, "http://x")
    assert entries[0]["retraction_label"] is None


def test_list_document_citations_empty_document() -> None:
    doc = _PanelDoc({})
    assert cc.list_document_citations(doc, "http://x") == []


# ── P1 item #11 (backlog #33/#34): bibliography editing -- persisted exclude/uncited lists (_get_id_list/
# _set_id_list) and their effect on list_document_citations' output ─────────────────────────────────────────


def test_get_id_list_defaults_to_empty_when_unset() -> None:
    doc = _PanelDoc({})
    assert cc._get_id_list(doc, cc.PREF_BIB_EXCLUDE) == []


def test_get_id_list_reads_a_set_json_property() -> None:
    doc = _PanelDoc({}, user_props={cc.PREF_BIB_EXCLUDE: '["3", "7"]'})
    assert cc._get_id_list(doc, cc.PREF_BIB_EXCLUDE) == ["3", "7"]


def test_get_id_list_defensive_on_corrupt_json() -> None:
    doc = _PanelDoc({}, user_props={cc.PREF_BIB_EXCLUDE: "not json"})
    assert cc._get_id_list(doc, cc.PREF_BIB_EXCLUDE) == []


def test_list_document_citations_marks_excluded_from_persisted_property(monkeypatch) -> None:
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {"title": "X", "issued": {"date-parts": [[2020]]}})
    monkeypatch.setattr(cc, "_get_json", lambda url: {"status": "none"})
    n1, m1 = _panel_mark("1", "c1", pos=0)
    doc = _PanelDoc({n1: m1}, user_props={cc.PREF_BIB_EXCLUDE: '["1"]'})
    entries = cc.list_document_citations(doc, "http://x")
    assert entries[0]["excluded"] is True
    assert entries[0]["uncited"] is False


def test_list_document_citations_includes_uncited_work_with_no_mark(monkeypatch) -> None:
    monkeypatch.setattr(
        cc, "fetch_csl", lambda base, pid: {"title": f"Paper {pid}", "issued": {"date-parts": [[2020]]}}
    )
    monkeypatch.setattr(cc, "_get_json", lambda url: {"status": "none"})
    n1, m1 = _panel_mark("1", "c1", pos=0)
    doc = _PanelDoc({n1: m1}, user_props={cc.PREF_BIB_UNCITED: '["9"]'})
    entries = cc.list_document_citations(doc, "http://x")
    assert [e["paper_id"] for e in entries] == ["1", "9"]
    uncited = entries[1]
    assert uncited["uncited"] is True
    assert uncited["count"] == 0
    assert uncited["mark"] is None
    assert uncited["excluded"] is False


def test_list_document_citations_uncited_entry_skipped_if_already_cited(monkeypatch) -> None:
    """A paper_id in PREF_BIB_UNCITED that's ALSO actually cited must not produce a duplicate row -- it's
    already represented once, correctly, as a cited entry."""
    monkeypatch.setattr(cc, "fetch_csl", lambda base, pid: {"title": "X", "issued": {"date-parts": [[2020]]}})
    monkeypatch.setattr(cc, "_get_json", lambda url: {"status": "none"})
    n1, m1 = _panel_mark("1", "c1", pos=0)
    doc = _PanelDoc({n1: m1}, user_props={cc.PREF_BIB_UNCITED: '["1"]'})
    entries = cc.list_document_citations(doc, "http://x")
    assert [e["paper_id"] for e in entries] == ["1"]
    assert entries[0]["uncited"] is False  # it's the CITED entry, not a separate uncited one


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
