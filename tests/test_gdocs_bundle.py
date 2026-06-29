"""inc 193 — the single-file Google Docs add-on bundle stays in sync with its three sources (like the
frontend-assembly test). If this fails: `python tools/build_gdocs_addon.py`."""

from __future__ import annotations

from tools.build_gdocs_addon import OUTPUT, build


def test_gdocs_bundle_in_sync():
    assert OUTPUT.read_text(encoding="utf-8") == build(), "Regenerate the bundle: python tools/build_gdocs_addon.py"


def test_gdocs_bundle_inlines_core_and_sidebar():
    out = build()
    assert "CallosumCore" in out  # gdocs_core.js concatenated (sets globalThis.CallosumCore in Apps Script)
    assert "function _callosumSidebarHtml()" in out  # sidebar.html inlined as a JS string
    assert "HtmlService.createHtmlOutput(_callosumSidebarHtml())" in out  # served inline…
    assert 'createHtmlOutputFromFile("sidebar")' not in out  # …not from a separate file
