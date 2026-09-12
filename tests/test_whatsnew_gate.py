"""The what's-new release drift gate (#43, inc 593): every shipped desktop version needs a banner entry OR an
explicit no-banner decline. Tests the gate against temp whatsnew.json / tauri.conf.json fixtures."""

from __future__ import annotations

import json

import tools.check_whatsnew_coverage as gate


def _setup(monkeypatch, tmp_path, *, version, whatsnew):
    wn = tmp_path / "whatsnew.json"
    wn.write_text(json.dumps(whatsnew), encoding="utf-8")
    tc = tmp_path / "tauri.conf.json"
    tc.write_text(json.dumps({"version": version}), encoding="utf-8")
    monkeypatch.setattr(gate, "WHATSNEW", wn)
    monkeypatch.setattr(gate, "TAURI_CONF", tc)
    return wn


def test_passes_when_current_version_has_an_entry(monkeypatch, tmp_path):
    _setup(
        monkeypatch,
        tmp_path,
        version="0.5.13",
        whatsnew={"entries": {"0.5.13": {"headline": "New thing", "actionKind": None}}, "no_banner": {}},
    )
    assert gate.check() == 0


def test_passes_when_current_version_has_a_no_banner_decline(monkeypatch, tmp_path):
    _setup(
        monkeypatch,
        tmp_path,
        version="0.5.12",
        whatsnew={"entries": {}, "no_banner": {"0.5.12": {"note": "bug fix", "at": "2026-09-12"}}},
    )
    assert gate.check() == 0


def test_fails_when_current_version_has_neither(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, version="0.5.99", whatsnew={"entries": {}, "no_banner": {}})
    assert gate.check() == 1


def test_fails_on_a_malformed_entry_for_the_current_version(monkeypatch, tmp_path):
    _setup(
        monkeypatch,
        tmp_path,
        version="0.5.13",
        whatsnew={"entries": {"0.5.13": {"headline": ""}}, "no_banner": {}},  # empty headline
    )
    assert gate.check() == 1


def test_decline_records_the_current_version_and_then_passes(monkeypatch, tmp_path):
    wn = _setup(monkeypatch, tmp_path, version="0.5.20", whatsnew={"entries": {}, "no_banner": {}})
    assert gate.check() == 1  # nothing recorded yet
    assert gate.decline("Deliberate silence.") == 0
    written = json.loads(wn.read_text(encoding="utf-8"))
    assert written["no_banner"]["0.5.20"]["note"] == "Deliberate silence."
    assert gate.check() == 0  # now passes


def test_decline_requires_a_note(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, version="0.5.20", whatsnew={"entries": {}, "no_banner": {}})
    try:
        gate.decline("   ")
    except SystemExit:
        return
    raise AssertionError("decline with a blank note should SystemExit")
