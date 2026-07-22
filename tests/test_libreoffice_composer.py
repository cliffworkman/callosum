"""The LibreOffice citation composer (Phase 5a/5b/5c, backlog #33/#34) — its pure, UNO-free helpers.

`composer.py` only does lazy `import unohelper`/UNO imports INSIDE its dialog-building functions
(`_edit_item_options`, `run_composer_dialog`) — its module-level code is plain `sys.path`/`import callosum_cite`,
so the module itself loads fine under plain CPython. These cover the pure formatting/reconstruction helpers;
the dialogs themselves need a real human driving `dialog.execute()` and are verified via
`adapters/libreoffice/selftest_uno.py` + manual checks, never here.
"""

from __future__ import annotations

from adapters.libreoffice import composer


def _bare_item(**overrides) -> dict:
    base = {
        "paper_id": "5",
        "row": "Vaswani et al. 2017 — Attention is all you need",
        "record": {"id": "callosum-5", "title": "Attention is all you need"},
        "locator": None,
        "label": None,
        "prefix": None,
        "suffix": None,
        "suppress-author": False,
        "author-only": False,
    }
    base.update(overrides)
    return base


def test_item_overrides_excludes_unset_and_custom_override() -> None:
    item = _bare_item(locator="12", label="page")
    assert composer._item_overrides(item) == {"locator": "12", "label": "page"}
    assert "custom_override" not in composer._item_overrides(item)
    assert composer._item_overrides(_bare_item()) == {}  # nothing set -> nothing to merge


def test_format_assembly_row_plain_when_no_overrides() -> None:
    item = _bare_item()
    assert composer._format_assembly_row(item) == item["row"]


def test_format_assembly_row_shows_active_overrides() -> None:
    locator_row = composer._format_assembly_row(_bare_item(locator="12", label="page"))
    assert locator_row.endswith("[page 12]")

    unlabeled_locator_row = composer._format_assembly_row(_bare_item(locator="12"))
    assert "[loc. 12]" in unlabeled_locator_row  # no label set -> a generic fallback, not a blank/None

    prefix_row = composer._format_assembly_row(_bare_item(prefix="see "))
    assert 'prefix "see "' in prefix_row

    suffix_row = composer._format_assembly_row(_bare_item(suffix=" (emphasis added)"))
    assert 'suffix " (emphasis added)"' in suffix_row

    suppressed_row = composer._format_assembly_row(_bare_item(**{"suppress-author": True}))
    assert "no author" in suppressed_row

    author_only_row = composer._format_assembly_row(_bare_item(**{"author-only": True}))
    assert "author only" in author_only_row


def test_assembly_item_from_decoded_separates_overrides_from_the_bare_record() -> None:
    decoded_item = {
        "id": "callosum-9",
        "title": "New Paper",
        "author": [{"family": "Devlin", "given": "Jacob"}],
        "issued": {"date-parts": [[2019]]},
        "locator": "3-5",
        "label": "chapter",
        "prefix": "see ",
        "suffix": None,
        "suppress-author": False,
        "author-only": False,
        "custom_override": None,
    }
    item = composer._assembly_item_from_decoded(decoded_item)
    assert item["paper_id"] == "9"  # "callosum-" prefix stripped
    assert item["locator"] == "3-5" and item["label"] == "chapter" and item["prefix"] == "see "
    assert "custom_override" not in item  # adapter-internal only, never surfaced
    # the bare record keeps the CSL fields but none of the per-occurrence keys
    assert item["record"]["id"] == "callosum-9" and item["record"]["title"] == "New Paper"
    for key in ("locator", "label", "prefix", "suffix", "suppress-author", "author-only"):
        assert key not in item["record"]
    assert "Devlin" in item["row"] and "2019" in item["row"]
