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
from adapters.libreoffice import citations_panel as panel


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


class _FakeProgressIndicator:
    def __init__(self) -> None:
        self.calls = []

    def start(self, text: str, total: int) -> None:
        self.calls.append(("start", text, total))

    def setText(self, text: str) -> None:
        self.calls.append(("text", text))

    def setValue(self, value: int) -> None:
        self.calls.append(("value", value))

    def end(self) -> None:
        self.calls.append(("end",))


class _FakeProgressToolkit:
    def __init__(self) -> None:
        self.calls = []

    def reschedule(self) -> None:
        self.calls.append(("reschedule",))

    def removeKeyHandler(self, listener) -> None:
        self.calls.append(("remove", listener))


def test_refresh_progress_reports_clamped_values_cancels_and_cleans_up() -> None:
    progress = cc._RefreshProgress(3)
    progress.indicator = _FakeProgressIndicator()
    progress.toolkit = _FakeProgressToolkit()
    progress.listener = object()

    progress.start()
    progress.update(99, "Applying")
    progress.cancelled = True
    with pytest.raises(cc.RefreshCancelled, match="partial formatting was rolled back"):
        progress.update(2, "Ignored")
    listener = progress.listener
    progress.close()

    assert progress.indicator.calls == [
        ("start", "Callosum: preparing citation refresh (Esc cancels)", 3),
        ("text", "Applying (Esc cancels)"),
        ("value", 3),
        ("end",),
    ]
    assert progress.toolkit.calls == [("reschedule",), ("remove", listener)]
    assert not progress.started


def test_small_refresh_progress_is_a_noop_without_touching_uno() -> None:
    progress = cc._new_refresh_progress(object(), cc.PROGRESS_MIN_WORK - 1)
    assert progress.indicator is None
    progress.update(1, "No visible progress")
    progress.close()


def test_render_input_signature_tracks_identity_order_and_visible_text() -> None:
    first = SimpleNamespace(Name="mark-a", getAnchor=lambda: _FakeAnchor("(A, 2020)"))
    second = SimpleNamespace(Name="mark-b", getAnchor=lambda: _FakeAnchor("(B, 2021)"))
    fields = [
        {"citationID": "c1", "_mark": first},
        {"citationID": "c2", "_mark": second},
    ]
    assert cc.render_input_signature(fields) == (
        ("mark-a", "c1", "(A, 2020)", "inline", 0),
        ("mark-b", "c2", "(B, 2021)", "inline", 0),
    )
    assert cc.render_input_signature(list(reversed(fields))) != cc.render_input_signature(fields)


def test_incremental_citation_plan_skips_current_and_untargeted_fields(monkeypatch) -> None:
    current = SimpleNamespace(Name="mark-a", getAnchor=lambda: _FakeAnchor("(A, 2020)"))
    changed = SimpleNamespace(Name="mark-b", getAnchor=lambda: _FakeAnchor("STALE"))
    fields = [
        {"citationID": "c1", "_mark": current},
        {"citationID": "c2", "_mark": changed},
    ]
    rendered = {"c1": "(A, 2020)", "c2": "(B, 2021)"}

    assert cc.incremental_citation_plan(fields, rendered) == [("mark-b", "(B, 2021)", "")]
    assert cc.incremental_citation_plan(fields, rendered, {"mark-a"}) == []
    assert cc.incremental_citation_plan(fields, rendered, {"mark-b"}) == [("mark-b", "(B, 2021)", "")]

    monkeypatch.setattr(cc, "_mark_hyperlink_url", lambda mark: "#old" if mark.Name == "mark-a" else "")
    desired = {"mark-a": "#new", "mark-b": ""}
    assert cc.incremental_citation_plan(fields, rendered, desired_links=desired) == [
        ("mark-a", "(A, 2020)", "#new"),
        ("mark-b", "(B, 2021)", ""),
    ]


def test_bibliography_render_comparison_requires_intact_exact_managed_text(monkeypatch) -> None:
    entries = ["A reference.", "B reference."]
    expected = "References\nA reference.\nB reference.\n"
    assert cc.rendered_bibliography_text(entries) == expected
    assert cc.rendered_bibliography_text(entries, "Works Cited") == "Works Cited\nA reference.\nB reference.\n"
    assert cc.rendered_bibliography_text([]) == ""

    monkeypatch.setattr(cc, "bibliography_heading", lambda doc: "References")
    monkeypatch.setattr(cc, "_managed_bibliography_signature", lambda doc: (True, True, expected))
    assert cc.bibliography_render_is_current(object(), entries)
    monkeypatch.setattr(cc, "_managed_bibliography_signature", lambda doc: (True, False, expected))
    assert not cc.bibliography_render_is_current(object(), entries)
    monkeypatch.setattr(cc, "_managed_bibliography_signature", lambda doc: (True, True, expected + "manual edit"))
    assert not cc.bibliography_render_is_current(object(), entries)


def test_categorized_bibliography_preserves_style_order_within_deterministic_groups() -> None:
    entries = ["Alpha.", "Beta.", "Gamma."]
    entry_ids = [["callosum-1"], ["callosum-2"], ["callosum-3"]]
    entry_links = [[], [], []]
    grouped = cc.categorize_bibliography_entries(
        entries,
        entry_ids,
        entry_links,
        {"1": "Methods", "3": "Theory"},
    )
    grouped_entries, grouped_ids, grouped_links, categories = grouped
    assert grouped_entries == ["Alpha.", "Gamma.", "Beta."]
    assert grouped_ids == [["callosum-1"], ["callosum-3"], ["callosum-2"]]
    assert grouped_links == [[], [], []]
    assert categories == ["Methods", "Theory", cc.BIBLIOGRAPHY_UNCATEGORIZED]
    expected = "References\nMethods\nAlpha.\n\nTheory\nGamma.\n\nOther references\nBeta.\n"
    layout, offsets = cc.bibliography_layout(grouped_entries, categories)
    assert layout == expected
    assert [layout[offset : offset + len(entry)] for offset, entry in zip(offsets, grouped_entries, strict=True)] == (
        grouped_entries
    )
    assert cc.rendered_bibliography_text(grouped_entries, categories=categories) == expected

    custom = cc.categorize_bibliography_entries(
        entries,
        entry_ids,
        entry_links,
        {"1": "Methods", "3": "Theory"},
        ["Theory", "Methods"],
    )
    assert custom[0] == ["Gamma.", "Alpha.", "Beta."]
    assert custom[3] == ["Theory", "Methods", cc.BIBLIOGRAPHY_UNCATEGORIZED]
    assert cc.ordered_bibliography_categories(
        ["Theory", "Results", "Methods"],
        ["Theory"],
    ) == ["Theory", "Methods", "Results"]


def test_section_bibliography_bookmark_names_are_strict_and_inventory_damage() -> None:
    identifier = "a" * 32
    names = cc.section_bibliography_bookmarks(identifier)
    assert names == {
        "scope": f"{cc.SECTION_BIB_PREFIX}{identifier}_SCOPE",
        "start": f"{cc.SECTION_BIB_PREFIX}{identifier}_START",
        "end": f"{cc.SECTION_BIB_PREFIX}{identifier}_END",
    }
    assert cc.decode_section_bibliography_bookmark(names["scope"]) == (identifier, "scope")
    assert cc.decode_section_bibliography_bookmark(f"{names['scope']} Copy 1") is None
    assert cc.decode_section_bibliography_bookmark(f"{cc.SECTION_BIB_PREFIX}{'A' * 32}_SCOPE") is None
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        cc.section_bibliography_bookmarks("not-an-id")

    damaged_id = "b" * 32
    bookmark_names = [*names.values(), cc.section_bibliography_bookmarks(damaged_id)["scope"], "USER_BOOKMARK"]
    bookmarks = SimpleNamespace(getElementNames=lambda: tuple(bookmark_names))
    records, damaged = cc.section_bibliography_records(SimpleNamespace(getBookmarks=lambda: bookmarks))
    assert records == [{"id": identifier, **names}]
    assert damaged == [damaged_id]

    excessive = [
        cc.section_bibliography_bookmarks(f"{index:032x}")["scope"]
        for index in range(cc.MAX_SECTION_BIBLIOGRAPHIES + 1)
    ]
    excessive_bookmarks = SimpleNamespace(getElementNames=lambda: tuple(excessive))
    with pytest.raises(ValueError, match="at most 50"):
        cc.section_bibliography_records(SimpleNamespace(getBookmarks=lambda: excessive_bookmarks))


def test_section_bibliography_manager_rows_name_counts_plainly() -> None:
    assert cc.format_section_bibliography_row("Methods", 0) == "Methods — 0 cited works"
    assert cc.format_section_bibliography_row("Results", 1) == "Results — 1 cited work"
    assert cc.format_section_bibliography_row("Discussion", 12) == "Discussion — 12 cited works"
    assert cc.format_section_bibliography_row("Appendix", -2) == "Appendix — 0 cited works"


def test_filter_bibliography_entries_projects_section_membership_without_reordering() -> None:
    entries = ["Alpha.", "Beta and Gamma.", "Delta."]
    entry_ids = [["callosum-1"], ["callosum-2", "callosum-3"], ["callosum-4"]]
    links = [[(0, 5, "https://a.example")], [], []]
    categories = ["Methods", "Theory", cc.BIBLIOGRAPHY_UNCATEGORIZED]
    assert cc.filter_bibliography_entries(
        entries,
        entry_ids,
        links,
        categories,
        {"callosum-3", "callosum-4"},
    ) == (
        ["Beta and Gamma.", "Delta."],
        [["callosum-2", "callosum-3"], ["callosum-4"]],
        [[], []],
        ["Theory", cc.BIBLIOGRAPHY_UNCATEGORIZED],
    )
    assert cc.filter_bibliography_entries(entries, entry_ids[:-1], links, categories, {"callosum-1"}) == (
        [],
        [],
        [],
        [],
    )


def test_categorized_bibliography_degrades_to_original_layout_without_applicable_assignments() -> None:
    entries = ["Alpha.", "Beta."]
    ids = [["callosum-1"], ["callosum-2", "callosum-3"]]
    links = [[], []]
    assert cc.categorize_bibliography_entries(entries, ids, links, {"2": "Mixed"}) == (
        entries,
        ids,
        links,
        [None, None],
    )


def test_bibliography_targets_and_citation_links_are_stable_and_unambiguous() -> None:
    assert cc.bibliography_entry_bookmark("callosum-42") == "CALLOSUM_BIB_ENTRY_42"
    assert cc.bibliography_entry_bookmark("external-42") is None
    assert cc.bibliography_entry_bookmark("callosum-not-a-number") is None

    def mark(name, hyperlink=""):
        return SimpleNamespace(Name=name, hyperlink=hyperlink)

    single = mark("single")
    grouped = mark("grouped", "#CALLOSUM_BIB_ENTRY_9")
    excluded = mark("excluded", "https://example.test/manual")
    fields = [
        {"_mark": single, "items": [{"id": "callosum-1"}]},
        {"_mark": grouped, "items": [{"id": "callosum-1"}, {"id": "callosum-2"}]},
        {"_mark": excluded, "items": [{"id": "callosum-3"}]},
    ]
    original = cc._mark_hyperlink_url
    cc._mark_hyperlink_url = lambda current: current.hyperlink
    try:
        assert cc.desired_citation_links(fields, {"callosum-1", "callosum-2"}, True) == {
            "single": "#CALLOSUM_BIB_ENTRY_1",
            "grouped": "",
            "excluded": "https://example.test/manual",
        }
        assert cc.desired_citation_links(fields, {"callosum-1"}, False) == {
            "single": "",
            "grouped": "",
            "excluded": "https://example.test/manual",
        }
    finally:
        cc._mark_hyperlink_url = original


def test_citation_source_choices_are_bounded_deduplicated_and_fail_closed() -> None:
    items = [
        {
            "id": "callosum-1",
            "title": "First source",
            "author": [{"family": "Alpha"}],
            "issued": {"date-parts": [[2020]]},
        },
        {"id": "callosum-1", "title": "Duplicate"},
        {"id": "external-2", "title": "Foreign"},
        {"id": "callosum-nope", "title": "Malformed"},
        {"id": "callosum-2", "title": "Second source"},
    ]

    assert cc.citation_source_choices(items) == [
        {"item_id": "callosum-1", "paper_id": "1", "row": "Alpha 2020 — First source"},
        {"item_id": "callosum-2", "paper_id": "2", "row": "— n.d. — Second source"},
    ]
    assert cc.citation_source_choices(items, {"callosum-2"}) == [
        {"item_id": "callosum-2", "paper_id": "2", "row": "— n.d. — Second source"}
    ]
    many = [{"id": f"callosum-{index}", "title": str(index)} for index in range(100)]
    assert len(cc.citation_source_choices(many)) == cc.MAX_CITATION_SOURCE_CHOICES


def test_bibliography_external_link_metadata_is_bounded_and_fails_plain(monkeypatch) -> None:
    entries = ["A reference. https://doi.org/10.1234/example."]
    start = entries[0].index("https://")
    url = "https://doi.org/10.1234/example"
    raw = [
        [
            {"start": start, "length": len(url), "url": url},
            {"start": 0, "length": 1, "url": "javascript:alert(1)"},
            {"start": 999, "length": 1, "url": "https://example.test/out-of-range"},
        ]
    ]
    links = cc.normalize_bibliography_links(entries, raw)
    assert links == [[(start, len(url), url)]]
    assert cc.normalize_bibliography_links(entries, []) == [[]]

    seen = []
    monkeypatch.setattr(cc, "bibliography_heading", lambda _doc: "References")
    monkeypatch.setattr(cc, "_bibliography_span_url", lambda _doc, offset, length: seen.append((offset, length)) or "")
    assert cc.bibliography_external_links_are_current(object(), entries, links, False)
    assert seen == [(len("References\n") + start, len(url))]
    assert not cc.bibliography_external_links_are_current(object(), entries, links, True)


def test_bibliography_category_metadata_is_bounded_and_case_canonicalized() -> None:
    doc = _PanelDoc(
        {},
        user_props={
            cc.PREF_BIB_CATEGORIES: (
                '{"1":"Methods","2":"methods","bad":"Theory","3":"Other references","4":"x\\n",'
                '"123456789012345678901":"Theory"}'
            )
        },
    )
    assert cc.bibliography_categories(doc) == {"1": "Methods", "2": "Methods"}
    assert cc.normalize_bibliography_category("  Theory  ") == "Theory"
    assert cc.normalize_bibliography_category("  ") is None
    with pytest.raises(ValueError, match="reserved"):
        cc.normalize_bibliography_category("other REFERENCES")
    with pytest.raises(ValueError, match="80 characters"):
        cc.normalize_bibliography_category("x" * 81)
    oversized = _PanelDoc(
        {},
        user_props={cc.PREF_BIB_CATEGORIES: "x" * (cc.MAX_BIBLIOGRAPHY_CATEGORY_METADATA + 1)},
    )
    assert cc.bibliography_categories(oversized) == {}
    ordered = _PanelDoc(
        {},
        user_props={cc.PREF_BIB_CATEGORY_ORDER: '["Theory","Methods"]'},
    )
    assert cc.bibliography_category_order(ordered) == ["Theory", "Methods"]
    duplicate = _PanelDoc(
        {},
        user_props={cc.PREF_BIB_CATEGORY_ORDER: '["Theory","theory"]'},
    )
    assert cc.bibliography_category_order(duplicate) == []
    excessive_order = _PanelDoc(
        {},
        user_props={
            cc.PREF_BIB_CATEGORY_ORDER: "x" * (cc.MAX_BIBLIOGRAPHY_CATEGORY_ORDER_METADATA + 1),
        },
    )
    assert cc.bibliography_category_order(excessive_order) == []


def test_set_bibliography_span_url_selects_only_declared_range() -> None:
    class Cursor:
        moves = []
        hyperlink = None

        def setPropertyValue(self, name, value):
            assert name == "HyperLinkURL"
            self.hyperlink = value

        def goRight(self, count, select):
            self.moves.append((count, select))
            return True

    cursor = Cursor()

    class Text:
        def createTextCursorByRange(self, _range):
            return cursor

    class Bookmark:
        class Anchor:
            def getStart(self):
                return object()

        def getAnchor(self):
            return self.Anchor()

    class Bookmarks:
        def getByName(self, name):
            assert name == cc.BIB_BOOKMARK
            return Bookmark()

    class Doc:
        def getText(self):
            return Text()

        def getBookmarks(self):
            return Bookmarks()

    cc._set_bibliography_span_url(Doc(), 12, 3, "https://doi.org/10/x")
    assert cursor.moves == [(12, False), (3, True)]
    assert cursor.hyperlink == "https://doi.org/10/x"


def test_bibliography_heading_validation_is_bounded_single_line() -> None:
    assert cc.normalize_bibliography_heading(None) == "References"
    assert cc.normalize_bibliography_heading("   ") == "References"
    assert cc.normalize_bibliography_heading("  Works Cited  ") == "Works Cited"
    with pytest.raises(ValueError, match="120 characters"):
        cc.normalize_bibliography_heading("x" * 121)
    with pytest.raises(ValueError, match="single line"):
        cc.normalize_bibliography_heading("Works\nCited")


def test_set_bibliography_heading_refreshes_explicitly_and_rolls_back_on_failure(monkeypatch) -> None:
    state = {"value": "Old heading"}
    calls = []

    monkeypatch.setattr(cc, "_effective_user_prop", lambda _doc, _name: state["value"])

    def set_value(_doc, name, value):
        assert name == cc.PREF_BIB_HEADING
        state["value"] = value

    monkeypatch.setattr(cc, "_set_user_prop_value", set_value)
    monkeypatch.setattr(cc, "refresh_bibliography", lambda doc, base: calls.append((doc, base)))
    doc = object()
    assert cc.set_bibliography_heading(doc, "Works Cited", "http://x") == "Works Cited"
    assert state["value"] == "Works Cited"
    assert calls == [(doc, "http://x")]

    assert cc.set_bibliography_heading(doc, "Works Cited", "http://x") == "Works Cited"
    assert calls == [(doc, "http://x"), (doc, "http://x")]

    monkeypatch.setattr(cc, "refresh_bibliography", lambda _doc, _base: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        cc.set_bibliography_heading(doc, "Sources", "http://x")
    assert state["value"] == "Works Cited"


def test_set_bibliography_links_refreshes_explicitly_and_rolls_back_on_failure(monkeypatch) -> None:
    state = {"value": None}
    calls = []
    monkeypatch.setattr(cc, "_effective_user_prop", lambda _doc, _name: state["value"])
    monkeypatch.setattr(cc, "_set_user_prop_value", lambda _doc, _name, value: state.update(value=value))
    monkeypatch.setattr(cc, "refresh", lambda doc, base, **kwargs: calls.append((doc, base, kwargs)))
    doc = object()

    assert cc.set_bibliography_links(doc, True, "http://x")
    assert state["value"] == "1"
    assert calls == [
        (doc, "http://x", {"update_citations": True, "update_bibliography": True}),
    ]

    monkeypatch.setattr(cc, "refresh", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError, match="boom"):
        cc.set_bibliography_links(doc, False, "http://x")
    assert state["value"] == "1"


def test_set_bibliography_external_links_rebuilds_and_rolls_back_on_failure(monkeypatch) -> None:
    state = {"value": None}
    calls = []
    monkeypatch.setattr(cc, "_effective_user_prop", lambda _doc, _name: state["value"])
    monkeypatch.setattr(cc, "_set_user_prop_value", lambda _doc, _name, value: state.update(value=value))
    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda doc, base: calls.append((doc, base))
        or {
            "bibliography_text": "DOI",
            "bibliography_links": [[{"start": 0, "length": 3, "url": "https://doi.org/10/x"}]],
        },
    )
    doc = object()

    assert cc.set_bibliography_external_links(doc, True, "http://x") == (True, 1)
    assert state["value"] == "1"
    assert calls == [(doc, "http://x")]

    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        cc.set_bibliography_external_links(doc, False, "http://x")
    assert state["value"] == "1"


def test_set_bibliography_categories_batches_reuses_case_and_rolls_back_on_failure(monkeypatch) -> None:
    state = {"1": "Methods"}
    writes = []
    refreshes = []
    monkeypatch.setattr(cc, "bibliography_categories", lambda _doc: dict(state))

    def write(_doc, value):
        state.clear()
        state.update(value)
        writes.append(dict(value))

    monkeypatch.setattr(cc, "_set_bibliography_categories", write)
    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda doc, base: refreshes.append((doc, base)) or {"bibliography_text": "Entry"},
    )
    doc = object()
    assert cc.set_bibliography_categories(doc, ["2", "3", "2"], "methods", "http://x") == {
        "2": "Methods",
        "3": "Methods",
    }
    assert state == {"1": "Methods", "2": "Methods", "3": "Methods"}
    assert refreshes == [(doc, "http://x")]
    assert cc.set_bibliography_category(doc, "4", "methods", "http://x") == "Methods"
    with pytest.raises(ValueError, match="at most 1000"):
        cc.set_bibliography_categories(doc, [str(index) for index in range(1001)], "Methods", "http://x")
    assert state == {"1": "Methods", "2": "Methods", "3": "Methods", "4": "Methods"}

    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        cc.set_bibliography_categories(doc, ["2", "3"], "Theory", "http://x")
    assert state == {"1": "Methods", "2": "Methods", "3": "Methods", "4": "Methods"}
    assert writes[-1] == state


def test_set_bibliography_category_order_refreshes_once_resets_and_restores_exact_property(monkeypatch) -> None:
    state = {"value": '["Methods","Theory"]'}
    writes = []
    refreshes = []
    monkeypatch.setattr(cc, "_effective_user_prop", lambda _doc, _name: state["value"])

    def set_value(_doc, name, value):
        assert name == cc.PREF_BIB_CATEGORY_ORDER
        state["value"] = value
        writes.append(value)

    monkeypatch.setattr(cc, "_set_user_prop_value", set_value)
    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda doc, base: refreshes.append((doc, base)) or {"bibliography_text": "Entry"},
    )
    doc = object()
    assert cc.set_bibliography_category_order(doc, ["Theory", "Methods"], "http://x") == ["Theory", "Methods"]
    assert state["value"] == '["Theory", "Methods"]'
    assert refreshes == [(doc, "http://x")]
    assert cc.set_bibliography_category_order(doc, [], "http://x") == []
    assert state["value"] is None

    state["value"] = '{"corrupt":"but exact"}'
    monkeypatch.setattr(
        cc,
        "refresh_bibliography",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    with pytest.raises(RuntimeError, match="boom"):
        cc.set_bibliography_category_order(doc, ["Methods"], "http://x")
    assert state["value"] == '{"corrupt":"but exact"}'
    assert writes[-1] == '{"corrupt":"but exact"}'


def test_citations_panel_category_picker_reuses_labels_and_handles_mixed_selection() -> None:
    visible = [
        {"paper_id": "1", "category": "Methods"},
        {"paper_id": "2", "category": None},
        {"paper_id": "3", "category": "Theory"},
    ]

    class Control:
        def getSelectedItemsPos(self):
            return (2, 0, 99)

    selected = panel._selected_entries(Control(), visible)
    assert selected == [visible[2], visible[0]]
    options, current = panel._category_picker_options(
        selected,
        {"1": "Methods", "3": "Theory", "4": "methods"},
    )
    assert options == (
        ("Choose a category…", panel._CHOOSE_CATEGORY),
        ("Methods", "Methods"),
        ("Theory", "Theory"),
        ("Create new category…", panel._CREATE_CATEGORY),
        ("Remove category", panel._REMOVE_CATEGORY),
    )
    assert current == panel._CHOOSE_CATEGORY

    options, current = panel._category_picker_options([visible[1]], {"1": "Methods"})
    assert current == panel._CREATE_CATEGORY
    assert ("Methods", "Methods") in options


def test_empty_incremental_delta_creates_no_undo_context() -> None:
    class NoTransactionDoc:
        def getUndoManager(self):
            pytest.fail("an empty delta must not open an UndoManager context")

    cc._transactional_apply(NoTransactionDoc(), [], [], write_bibliography=False)


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


class _OutlineRange:
    def __init__(self, position: int) -> None:
        self.position = position

    def getStart(self):
        return self


class _OutlineParagraph(_OutlineRange):
    def __init__(self, position: int, level: int) -> None:
        super().__init__(position)
        self.OutlineLevel = level

    def getPropertyValue(self, name: str):
        if name != "OutlineLevel":
            raise KeyError(name)
        return self.OutlineLevel


class _OutlineEnumeration:
    def __init__(self, paragraphs) -> None:
        self._paragraphs = iter(paragraphs)
        self._next = None

    def hasMoreElements(self) -> bool:
        if self._next is None:
            self._next = next(self._paragraphs, False)
        return self._next is not False

    def nextElement(self):
        item = self._next
        self._next = None
        return item


class _OutlineText:
    def __init__(self, headings) -> None:
        self._paragraphs = [_OutlineParagraph(position, level) for position, level in headings]

    def createEnumeration(self):
        return _OutlineEnumeration(self._paragraphs)

    def compareRegionStarts(self, left, right) -> int:
        return 1 if left.position < right.position else (-1 if left.position > right.position else 0)

    def getStart(self):
        return _OutlineRange(0)

    def getEnd(self):
        return _OutlineRange(100)


class _OutlineController:
    def __init__(self, position: int) -> None:
        self._cursor = _OutlineRange(position)

    def getViewCursor(self):
        return self._cursor


class _OutlineDoc:
    def __init__(self, headings, cursor: int) -> None:
        self._text = _OutlineText(headings)
        self._controller = _OutlineController(cursor)

    def getText(self):
        return self._text

    def getCurrentController(self):
        return self._controller


@pytest.mark.parametrize(
    ("headings", "cursor", "expected"),
    [
        ([(10, 1), (30, 2), (50, 2), (80, 1)], 20, (10, 80)),
        ([(10, 1), (30, 2), (50, 2), (80, 1)], 35, (30, 50)),
        ([(10, 1), (30, 2)], 5, (0, 10)),
        ([], 35, (0, 100)),
    ],
)
def test_current_outline_section_bounds_follow_heading_subtrees(headings, cursor, expected) -> None:
    start, end = cc._current_outline_section_bounds(_OutlineDoc(headings, cursor))
    assert (start.position, end.position) == expected


def test_refresh_current_section_targets_only_section_marks(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(cc, "current_section_citation_names", lambda doc: {"mark-2", "mark-3"})
    monkeypatch.setattr(
        cc,
        "refresh",
        lambda doc, base, **kwargs: calls.append((doc, base, kwargs)) or {"ok": True},
    )
    doc = object()

    assert cc.refresh_current_section(doc, "http://x") == {"ok": True}
    assert calls == [
        (
            doc,
            "http://x",
            {
                "update_bibliography": False,
                "citation_names": {"mark-2", "mark-3"},
            },
        )
    ]


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (None, "Place your cursor in the main document text to refresh its current section."),
        (set(), "No live Callosum citations were found in the current section."),
    ],
)
def test_refresh_current_section_handles_missing_scope_without_render(monkeypatch, names, message) -> None:
    messages = []
    monkeypatch.setattr(cc, "current_section_citation_names", lambda doc: names)
    monkeypatch.setattr(cc, "_msgbox", messages.append)
    monkeypatch.setattr(cc, "refresh", lambda *args, **kwargs: pytest.fail("refresh should not run"))

    assert cc.refresh_current_section(object(), "http://x") is None
    assert messages == [message]


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
        {"citationID": "c2", "items": [{"id": "callosum-2"}], "noteIndex": 4, "_mark": object()},
    ]
    req = cc.build_render_request(fields, "ieee", "en-US")
    assert req["style"] == "ieee" and req["locale"] == "en-US"
    assert req["citations"] == [
        {"citationID": "c1", "items": [{"id": "callosum-1"}], "noteIndex": 0},
        {"citationID": "c2", "items": [{"id": "callosum-2"}], "noteIndex": 4},
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


def test_style_manifest_and_family_are_validated(monkeypatch) -> None:
    monkeypatch.setattr(
        cc,
        "_get_json",
        lambda url: {
            "styles": [
                {"id": "apa", "title": "APA", "family": "author-date"},
                {"id": "chicago-notes", "title": "Chicago", "family": "note"},
                {"id": 7, "family": "note"},
                "malformed",
            ]
        },
    )
    assert cc.list_style_ids("http://x") == {"apa", "chicago-notes"}
    assert cc.style_family("http://x", "chicago-notes") == "note"
    with pytest.raises(ValueError, match="Unknown citation style"):
        cc.style_family("http://x", "missing")


def test_style_catalog_preserves_preferences_and_search_metadata(monkeypatch) -> None:
    seen = []

    def get_json(url):
        seen.append(url)
        return {
            "styles": [
                {
                    "id": "apa",
                    "title": "APA",
                    "family": "author-date",
                    "citation_format": "author-date",
                    "fields": ["psychology", 7],
                    "favorite": True,
                    "recent_rank": 0,
                    "application_default": True,
                }
            ],
            "locales": ["en-US", "en-GB", None],
            "default_style": "apa",
            "default_locale": "en-GB",
        }

    monkeypatch.setattr(cc, "_get_json", get_json)
    catalog = cc.style_catalog("http://x", "social science")
    assert seen == ["http://x/citations/styles?q=social+science"]
    assert catalog["default_style"] == "apa" and catalog["default_locale"] == "en-GB"
    assert catalog["locales"] == ["en-US", "en-GB"]
    assert catalog["styles"][0] == {
        "id": "apa",
        "title": "APA",
        "family": "author-date",
        "citation_format": "author-date",
        "fields": ["psychology"],
        "favorite": True,
        "recent_rank": 0,
        "application_default": True,
    }
    assert cc.style_search_row(catalog["styles"][0]) == "★ APA — author date · psychology"


def test_record_style_use_updates_only_recent_state(monkeypatch) -> None:
    seen = {}

    def put_json(url, body):
        seen.update(url=url, body=body)
        return {"default_style": "apa", "recent_style_ids": ["ieee"]}

    monkeypatch.setattr(cc, "_put_json", put_json)
    result = cc.record_style_use("http://x", "ieee", "en-GB")
    assert seen == {
        "url": "http://x/citations/styles/preferences",
        "body": {"style": "ieee", "locale": "en-GB", "mark_used": True},
    }
    assert result["default_style"] == "apa"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("footnote", "footnote"), ("FOOTNOTE", "footnote"), (" endnote ", "endnote")],
)
def test_normalize_note_placement(raw: str, expected: str) -> None:
    assert cc.normalize_note_placement(raw) == expected


@pytest.mark.parametrize("raw", ["", "margin", "inline"])
def test_normalize_note_placement_rejects_unknown_values(raw: str) -> None:
    with pytest.raises(ValueError, match="footnote.*endnote"):
        cc.normalize_note_placement(raw)


class _InsertionDoc:
    def __init__(self, main_text) -> None:
        self._main_text = main_text

    def getText(self):
        return self._main_text


def test_note_insertion_text_accepts_main_or_matching_note_and_rejects_other_contexts(monkeypatch) -> None:
    main_text, footnote, endnote, unsupported = object(), object(), object(), object()
    doc = _InsertionDoc(main_text)
    monkeypatch.setattr(
        cc,
        "_note_containers",
        lambda _doc: [
            {"placement": "footnote", "_note": footnote},
            {"placement": "endnote", "_note": endnote},
        ],
    )
    monkeypatch.setattr(cc, "_range_belongs_to_text", lambda text, cursor: text is cursor)

    assert cc._note_insertion_text(doc, main_text, "footnote") is None
    assert cc._note_insertion_text(doc, footnote, "footnote") is footnote
    with pytest.raises(ValueError, match="endnote.*footnotes"):
        cc._note_insertion_text(doc, endnote, "footnote")
    with pytest.raises(ValueError, match="main document text"):
        cc._note_insertion_text(doc, unsupported, "footnote")


@pytest.mark.parametrize(
    ("family", "requested", "expected"),
    [
        ("author-date", "footnote", "inline"),
        ("numeric", "endnote", "inline"),
        ("note", "footnote", "footnote"),
        ("note", "endnote", "endnote"),
    ],
)
def test_conversion_target_placement(family: str, requested: str, expected: str) -> None:
    assert cc.conversion_target_placement(family, requested) == expected


def test_conversion_state_name_round_trip() -> None:
    values = {
        cc.PREF_STYLE: "chicago-notes-bibliography",
        cc.PREF_LOCALE: "en-US",
        cc.PREF_NOTE_PLACEMENT: "endnote",
        cc.PREF_CITE_DIRTY: "0",
        cc.PREF_BIB_DIRTY: None,
    }
    name = cc._conversion_state_name(values)

    assert name.startswith(cc.CONVERSION_STATE_PREFIX + " ")
    assert cc._decode_conversion_state_name(name) == values
    assert cc._decode_conversion_state_name(cc.CONVERSION_STATE_PREFIX + " invalid") is None


def test_placement_conversion_rejects_empty_same_and_mixed_without_mutation() -> None:
    assert "No live" in cc.placement_conversion_error(None, [], "footnote")
    assert "already" in cc.placement_conversion_error(None, [{"placement": "inline"}], "inline")
    assert "mixed" in cc.placement_conversion_error(
        None,
        [{"placement": "inline"}, {"placement": "footnote"}],
        "endnote",
    )


def test_placement_conversion_accepts_complete_section_bibliographies_but_refuses_damage(monkeypatch) -> None:
    identifier = "a" * 32
    names = cc.section_bibliography_bookmarks(identifier)
    monkeypatch.setattr(cc, "section_bibliography_records", lambda _doc: ([{"id": identifier, **names}], []))

    class StyleLookupReached(Exception):
        pass

    monkeypatch.setattr(cc, "list_styles", lambda _base: (_ for _ in ()).throw(StyleLookupReached()))
    with pytest.raises(StyleLookupReached):
        cc.convert_citation_placement(object(), "apa", "en-US")

    monkeypatch.setattr(cc, "section_bibliography_records", lambda _doc: ([], [identifier]))
    monkeypatch.setattr(
        cc,
        "list_styles",
        lambda _base: pytest.fail("damaged section bibliographies must refuse before an HTTP style lookup"),
    )
    with pytest.raises(ValueError, match="Repair damaged section bibliography"):
        cc.convert_citation_placement(object(), "apa", "en-US")
    monkeypatch.setattr(cc, "_get_pref", lambda _doc, _base: ("apa", "en-US"))
    monkeypatch.setattr(cc, "scan_citations_in_order", lambda _doc: [])
    monkeypatch.setattr(cc, "style_family", lambda _base, _style: "in-text")
    monkeypatch.setattr(cc, "note_placement", lambda _doc: "footnote")
    monkeypatch.setattr(cc, "_get_id_list", lambda _doc, _name: [])
    monkeypatch.setattr(
        cc,
        "render_document",
        lambda *_args, **_kwargs: pytest.fail("refresh must refuse before rendering"),
    )
    with pytest.raises(ValueError, match="damaged section bibliography"):
        cc.refresh(object(), update_citations=False, update_bibliography=True)


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((1, 3), (2, 4), True),
        ((1, 2), (2, 4), False),
        ((2, 2), (1, 3), True),
        ((3, 3), (1, 3), True),
        ((4, 4), (1, 3), False),
    ],
)
def test_ordered_ranges_overlap_treats_collapsed_boundaries_conservatively(
    first: tuple[int, int],
    second: tuple[int, int],
    expected: bool,
) -> None:
    def compare(first_position, second_position):
        return second_position - first_position

    assert cc._ordered_ranges_overlap(compare, *first, *second) is expected


class _PositionText:
    @staticmethod
    def createTextCursorByRange(range_):
        return range_

    @staticmethod
    def compareRegionStarts(first, second):
        return second - first


def test_tracked_change_conversion_error_allows_unrelated_and_rejects_managed_overlap(monkeypatch) -> None:
    text = _PositionText()
    monkeypatch.setattr(cc, "_conversion_managed_ranges", lambda _doc, _fields: [(text, 10, 20, "a live citation")])
    monkeypatch.setattr(cc, "_redline_ranges", lambda _doc: [{"text": text, "start": 1, "end": 5}])
    assert cc._tracked_change_conversion_error(object(), [{}]) is None

    monkeypatch.setattr(cc, "_redline_ranges", lambda _doc: [{"text": text, "start": 12, "end": 13}])
    assert "overlap a live citation" in cc._tracked_change_conversion_error(object(), [{}])

    monkeypatch.setattr(cc, "_redline_ranges", lambda _doc: (_ for _ in ()).throw(ValueError("unreadable")))
    assert "could not locate" in cc._tracked_change_conversion_error(object(), [{}])


def test_suspend_and_restore_record_changes_preserves_original_state() -> None:
    doc = SimpleNamespace(RecordChanges=True)
    assert cc._suspend_record_changes(doc) is True
    assert doc.RecordChanges is False
    cc._restore_record_changes(doc, True)
    assert doc.RecordChanges is True

    doc.RecordChanges = False
    assert cc._suspend_record_changes(doc) is False
    cc._restore_record_changes(doc, False)
    assert doc.RecordChanges is False


def test_suspend_record_changes_fails_closed_when_state_is_unreadable() -> None:
    class _UnreadableTracking:
        @property
        def RecordChanges(self):
            raise RuntimeError("unavailable")

    with pytest.raises(RuntimeError, match="did not expose"):
        cc._suspend_record_changes(_UnreadableTracking())


@pytest.mark.parametrize(
    ("family", "placements", "expected_note_placement", "has_error"),
    [
        ("note", ["footnote"], "footnote", False),
        ("note", ["endnote"], "endnote", False),
        ("note", ["endnote"], "footnote", True),
        ("note", ["inline"], "footnote", True),
        ("note", ["footnote", "inline"], "footnote", True),
        ("author-date", ["inline"], "footnote", False),
        ("numeric", ["footnote"], "footnote", True),
        ("note", [], "endnote", False),
    ],
)
def test_citation_placement_error(
    family: str,
    placements: list[str],
    expected_note_placement: str,
    has_error: bool,
) -> None:
    fields = [{"placement": placement} for placement in placements]
    assert (cc.citation_placement_error(fields, family, expected_note_placement) is not None) is has_error


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

    def getElementNames(self) -> tuple[str, ...]:
        return tuple(self._names)


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
        "section_bibliographies": {"count": 0, "damaged": []},
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


def test_note_placement_defaults_and_corrupt_values_fail_to_footnotes() -> None:
    assert cc.note_placement(_PanelDoc({})) == "footnote"
    assert cc.note_placement(_PanelDoc({}, {cc.PREF_NOTE_PLACEMENT: "endnote"})) == "endnote"
    assert cc.note_placement(_PanelDoc({}, {cc.PREF_NOTE_PLACEMENT: "margin"})) == "footnote"


def test_unstyled_document_inherits_application_style_without_overriding_embedded_style(monkeypatch) -> None:
    monkeypatch.setattr(
        cc,
        "style_catalog",
        lambda base: {
            "styles": [],
            "locales": ["en-US", "en-GB"],
            "default_style": "ieee",
            "default_locale": "en-GB",
        },
    )
    assert cc._get_pref(_PanelDoc({}), "http://x") == ("ieee", "en-GB")
    assert cc._get_pref(_PanelDoc({}, {cc.PREF_STYLE: "apa"}), "http://x") == ("apa", "en-GB")
    assert cc._get_pref(
        _PanelDoc({}, {cc.PREF_STYLE: "apa", cc.PREF_LOCALE: "en-US"}),
        "http://x",
    ) == ("apa", "en-US")


def test_dirty_state_defaults_clean_and_reads_each_persisted_flag() -> None:
    assert cc.dirty_state(_PanelDoc({})) == (False, False)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_CITE_DIRTY: "1"})) == (True, False)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_BIB_DIRTY: "1"})) == (False, True)
    assert cc.dirty_state(_PanelDoc({}, {cc.PREF_CITE_DIRTY: "1", cc.PREF_BIB_DIRTY: "1"})) == (True, True)


def test_structure_change_flags_ignore_prose_but_track_citations_and_bibliography() -> None:
    original = ((("mark-a", "(A, 2020)"),), ((True, True, "References\nA"), ()))
    assert cc.structure_change_flags(original, original) == (False, False)
    assert cc.structure_change_flags(original, ((("mark-b", "(B, 2021)"),), original[1])) == (True, True)
    edited_full = ((True, True, "References\nEdited"), ())
    assert cc.structure_change_flags(original, (original[0], edited_full)) == (False, True)
    edited_section = (original[1][0], (("a" * 32, True, True, "References\nSection"),))
    assert cc.structure_change_flags(original, (original[0], edited_section)) == (False, True)


class _ObserverDoc:
    RuntimeUID = "observer-doc"

    def __init__(self) -> None:
        self.listeners = []

    def supportsService(self, name: str) -> bool:
        return name == "com.sun.star.text.TextDocument"

    def addModifyListener(self, listener) -> None:
        self.listeners.append(listener)


def test_observe_document_restores_state_and_installs_one_listener(monkeypatch) -> None:
    doc = _ObserverDoc()
    listener = object()
    synced = []
    monkeypatch.setattr(cc, "_sync_dirty_infobar", lambda observed: synced.append(observed))
    monkeypatch.setattr(cc, "_new_document_observer", lambda observed: listener)
    cc._DOCUMENT_OBSERVERS.pop(doc.RuntimeUID, None)

    assert cc.observe_document(doc)
    assert cc.observe_document(doc)
    assert doc.listeners == [listener]
    assert synced == [doc, doc]
    cc._DOCUMENT_OBSERVERS.pop(doc.RuntimeUID, None)


def test_dispatch_suspends_observation_and_installs_listener_after_action(monkeypatch) -> None:
    doc = SimpleNamespace(RuntimeUID="dispatch-doc")
    calls = []

    def action(observed, base):
        calls.append(("action", observed, base, doc.RuntimeUID in cc._OBSERVATION_SUPPRESSIONS))

    monkeypatch.setitem(cc._ACTIONS, "_testObserver", action)
    monkeypatch.setattr(cc, "document_structure_signature", lambda observed: ((), ((False, False, ""), ())))
    monkeypatch.setattr(cc, "_sync_dirty_infobar", lambda observed: calls.append(("sync", observed)))
    monkeypatch.setattr(cc, "observe_document", lambda observed: calls.append(("observe", observed)))

    cc.dispatch("_testObserver", doc, "http://local")

    assert calls == [
        ("sync", doc),
        ("action", doc, "http://local", True),
        ("observe", doc),
    ]
    assert doc.RuntimeUID not in cc._OBSERVATION_SUPPRESSIONS


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
    doc = _PanelDoc(
        {n1: m1},
        user_props={
            cc.PREF_BIB_UNCITED: '["9"]',
            cc.PREF_BIB_CATEGORIES: '{"1":"Theory","9":"Methods"}',
        },
    )
    entries = cc.list_document_citations(doc, "http://x")
    assert [e["paper_id"] for e in entries] == ["1", "9"]
    assert [e["category"] for e in entries] == ["Theory", "Methods"]
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
