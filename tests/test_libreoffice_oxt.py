"""LibreOffice extension build + config (inc 162) — the parts that don't need LibreOffice.

`build_oxt` just zips the source, and the server-URL config is pure file I/O, so both load + run under plain
CPython. The actual install + the menu/toolbar dispatcher resolving are verified through real LibreOffice by
`adapters/libreoffice/run_roundtrip.py` (unopkg add + the dispatcher check in selftest_uno.py; also runs in
CI — see `.github/workflows/libreoffice-adapter.yml`).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile

from adapters.libreoffice import callosum_cite as cc
from tools.build_libreoffice_oxt import ADAPTER_DIR, build_oxt

EXPECTED_ENTRIES = {
    "META-INF/manifest.xml",
    "description.xml",
    "Addons.xcu",
    "Jobs.xcu",
    "callosum_cite.py",
    "callosum_addon.py",
    "composer.py",
    "citations_panel.py",
}


def test_build_oxt_has_expected_entries(tmp_path) -> None:
    oxt = build_oxt(tmp_path / "callosum.oxt")
    assert oxt.exists()
    with zipfile.ZipFile(oxt) as z:
        assert set(z.namelist()) == EXPECTED_ENTRIES


def test_every_local_sibling_import_is_packaged(tmp_path) -> None:
    # Regression guard for the exact bug that shipped composer.py without adding it to ENTRIES: a packaged
    # install (unlike the by-hand macro, which shares callosum_cite.py's own folder) then 404s at runtime with
    # "No module named 'composer'" the first time that code path actually runs — invisible to every existing
    # test because none of them zip-import the built .oxt the way LibreOffice does. Scan callosum_cite.py's own
    # source for bare `import <name>` statements that name a real sibling .py file in the adapter dir, and assert
    # each one is actually bundled — this fails the moment a NEW sibling module is imported but not packaged,
    # without needing EXPECTED_ENTRIES (or this test) to be remembered and hand-updated again.
    src = (ADAPTER_DIR / "callosum_cite.py").read_text(encoding="utf-8")
    imported = set(re.findall(r"^\s*import (\w+)\s*$", src, re.MULTILINE))
    sibling_modules = {name for name in imported if (ADAPTER_DIR / f"{name}.py").is_file()}
    assert sibling_modules, "expected at least one local sibling import (e.g. composer) to check"

    oxt = build_oxt(tmp_path / "callosum.oxt")
    with zipfile.ZipFile(oxt) as z:
        packaged = set(z.namelist())
    missing = {f"{name}.py" for name in sibling_modules} - packaged
    assert not missing, f"sibling module(s) imported by callosum_cite.py but not packaged in the .oxt: {missing}"


def test_oxt_xml_well_formed_and_wires_the_dispatcher(tmp_path) -> None:
    oxt = build_oxt(tmp_path / "callosum.oxt")
    with zipfile.ZipFile(oxt) as z:
        for entry in ("description.xml", "META-INF/manifest.xml", "Addons.xcu", "Jobs.xcu"):
            ET.fromstring(z.read(entry))  # raises on malformed XML
        description = ET.fromstring(z.read("description.xml"))
        addons = z.read("Addons.xcu").decode("utf-8")
        jobs = z.read("Jobs.xcu").decode("utf-8")
        manifest = z.read("META-INF/manifest.xml").decode("utf-8")
    version = description.find("{http://openoffice.org/extensions/description/2006}version")
    assert version is not None and version.get("value") == "0.17.0"
    assert "service:com.callosum.cite.Dispatcher?suggest" in addons
    assert "callosum_addon.py" in manifest and "uno-component;type=Python" in manifest
    assert "Jobs.xcu" in manifest and "configuration-data" in manifest
    assert "onDocumentOpened" in jobs and "OnLoad" in jobs and "OnLoadFinished" in jobs
    assert "com.callosum.cite.DocumentLifecycle" in jobs


def test_every_menu_action_is_a_real_action(tmp_path) -> None:
    # No dead/typo'd menu items: every action the Addons.xcu menu/toolbar dispatches must exist in callosum_cite.
    oxt = build_oxt(tmp_path / "callosum.oxt")
    with zipfile.ZipFile(oxt) as z:
        addons = z.read("Addons.xcu").decode("utf-8")
    actions = set(re.findall(r"Dispatcher\?(\w+)", addons))
    assert actions, "no dispatcher actions found in Addons.xcu"
    assert actions <= set(cc._ACTIONS), f"menu actions {actions - set(cc._ACTIONS)} are not in callosum_cite._ACTIONS"
    assert {
        "refresh",
        "refreshCitations",
        "refreshSelectedCitation",
        "refreshCurrentSection",
        "refreshBibliography",
        "toggleCiteAuto",
        "setNotePlacement",
        "convertCitationPlacement",
    } <= actions


def test_dirty_infobar_refresh_button_targets_a_real_packaged_action() -> None:
    action = cc.DIRTY_REFRESH_URL.rsplit("?", 1)[-1]
    assert action == "refreshPending"
    assert action in cc._ACTIONS


def test_build_search_rows() -> None:
    rows = cc.build_search_rows(
        [
            {"id": 1, "title": "Attention is all you need", "authors": ["Vaswani", "Shazeer"], "year": 2017},
            {"id": 2, "title": "T" * 200, "authors": [], "year": None},
        ]
    )
    assert rows[0] == "Vaswani et al. 2017 — Attention is all you need"
    assert rows[1].startswith("— n.d. — ") and rows[1].endswith("…")  # no author / no year / truncated title


def test_search_library_query_encoding_and_shape(monkeypatch) -> None:
    captured = {}

    def fake_get(url, timeout=20):
        captured["url"] = url
        return [{"id": 5, "title": "X"}]

    monkeypatch.setattr(cc, "_get_json", fake_get)
    out = cc.search_library("http://h", "ada lovelace 2024")
    assert out == [{"id": 5, "title": "X"}]
    assert "/papers?q=ada%20lovelace%202024&limit=20" in captured["url"]
    assert cc.search_library("http://h", "   ") == []  # blank query → no request, empty result


def test_server_url_config_round_trip(tmp_path) -> None:
    p = str(tmp_path / "sub" / "libreoffice.json")  # nested dir is created on write
    assert cc.get_server_url(p) == cc.DEFAULT_BASE  # missing → default
    cc.set_server_url("http://127.0.0.1:9000/", p)
    assert cc.get_server_url(p) == "http://127.0.0.1:9000"  # stored; trailing slash stripped
    cc.set_server_url("", p)
    assert cc.get_server_url(p) == cc.DEFAULT_BASE  # blank → reset to default
