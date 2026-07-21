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
from tools.build_libreoffice_oxt import build_oxt

EXPECTED_ENTRIES = {
    "META-INF/manifest.xml",
    "description.xml",
    "Addons.xcu",
    "callosum_cite.py",
    "callosum_addon.py",
}


def test_build_oxt_has_expected_entries(tmp_path) -> None:
    oxt = build_oxt(tmp_path / "callosum.oxt")
    assert oxt.exists()
    with zipfile.ZipFile(oxt) as z:
        assert set(z.namelist()) == EXPECTED_ENTRIES


def test_oxt_xml_well_formed_and_wires_the_dispatcher(tmp_path) -> None:
    oxt = build_oxt(tmp_path / "callosum.oxt")
    with zipfile.ZipFile(oxt) as z:
        for entry in ("description.xml", "META-INF/manifest.xml", "Addons.xcu"):
            ET.fromstring(z.read(entry))  # raises on malformed XML
        addons = z.read("Addons.xcu").decode("utf-8")
        manifest = z.read("META-INF/manifest.xml").decode("utf-8")
    assert "service:com.callosum.cite.Dispatcher?suggest" in addons
    assert "callosum_addon.py" in manifest and "uno-component;type=Python" in manifest


def test_every_menu_action_is_a_real_action(tmp_path) -> None:
    # No dead/typo'd menu items: every action the Addons.xcu menu/toolbar dispatches must exist in callosum_cite.
    oxt = build_oxt(tmp_path / "callosum.oxt")
    with zipfile.ZipFile(oxt) as z:
        addons = z.read("Addons.xcu").decode("utf-8")
    actions = set(re.findall(r"Dispatcher\?(\w+)", addons))
    assert actions, "no dispatcher actions found in Addons.xcu"
    assert actions <= set(cc._ACTIONS), f"menu actions {actions - set(cc._ACTIONS)} are not in callosum_cite._ACTIONS"


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
