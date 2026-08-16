"""Unit tests for the QA-route <-> public-showcase coverage gate's exclusion mechanism.

QA-POLICY.md documents that "internal/admin-only mechanics may be excluded from the public tour, but
the exclusion must be explicit in the registry" -- these tests pin the behavior of that exclusion path
in ``tools/qa/check_website_coverage.py`` directly (via its module-level ``check()`` function against a
monkeypatched registry/route set), independent of the real repo's current showcase content.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.qa import check_website_coverage as cwc


def _write_registry(path: Path, **overrides: object) -> None:
    base = {
        "schema": "callosum-showcase-coverage/1",
        "canonical_positioning": "positioning text",
        "workflow": [],
        "review": {
            "reviewed_at": "2026-01-01",
            "reviewed_rev": "deadbeef",
            "source_fingerprint": cwc._source_fingerprint(),
            "note": "test",
        },
        "qa_routes": {},
        "excluded_qa_routes": {},
        "external_surfaces": {},
        "figures": {},
        "index_links": [],
    }
    base.update(overrides)
    path.write_text(json.dumps(base), encoding="utf-8")


def _write_showcase(path: Path, index_path: Path, readme_path: Path) -> None:
    positioning = "positioning text"
    path.write_text(f"<html><body>{positioning}</body></html>", encoding="utf-8")
    index_path.write_text(f"<html><body>{positioning}</body></html>", encoding="utf-8")
    readme_path.write_text(positioning, encoding="utf-8")


@pytest.fixture
def _isolated_routes(tmp_path, monkeypatch):
    routes_dir = tmp_path / "qa-routes"
    routes_dir.mkdir()
    (routes_dir / "route_01_covered.md").write_text("# covered", encoding="utf-8")
    (routes_dir / "route_02_uncovered.md").write_text("# uncovered", encoding="utf-8")
    monkeypatch.setattr(cwc, "QA_ROUTES", routes_dir)

    showcase = tmp_path / "showcase.html"
    index = tmp_path / "index.html"
    readme = tmp_path / "README.md"
    _write_showcase(showcase, index, readme)
    monkeypatch.setattr(cwc, "SHOWCASE", showcase)
    monkeypatch.setattr(cwc, "INDEX", index)
    monkeypatch.setattr(cwc, "README", readme)

    registry = tmp_path / "showcase-coverage.json"
    monkeypatch.setattr(cwc, "REGISTRY", registry)
    return registry


def test_unmapped_route_with_no_exclusion_fails(_isolated_routes, capsys) -> None:
    _write_registry(_isolated_routes, qa_routes={"route_01_covered": "#missing"})
    assert cwc.check() == 1
    assert "unmapped public QA route: route_02_uncovered" in capsys.readouterr().out


def test_excluded_route_with_reason_passes_the_unmapped_check(_isolated_routes, capsys) -> None:
    _write_registry(
        _isolated_routes,
        qa_routes={},
        excluded_qa_routes={"route_01_covered": "internal-only", "route_02_uncovered": "internal-only"},
    )
    cwc.check()
    out = capsys.readouterr().out
    assert "unmapped public QA route" not in out


def test_excluded_route_requires_a_non_empty_reason(_isolated_routes, capsys) -> None:
    _write_registry(
        _isolated_routes,
        qa_routes={"route_02_uncovered": "#missing"},
        excluded_qa_routes={"route_01_covered": "   "},
    )
    assert cwc.check() == 1
    assert "excluded QA route has no reason: route_01_covered" in capsys.readouterr().out


def test_exclusion_for_a_route_that_no_longer_exists_is_flagged_stale(_isolated_routes, capsys) -> None:
    _write_registry(
        _isolated_routes,
        qa_routes={"route_01_covered": "#missing", "route_02_uncovered": "#missing"},
        excluded_qa_routes={"route_99_deleted": "internal-only"},
    )
    assert cwc.check() == 1
    out = capsys.readouterr().out
    assert "excluded QA route no longer exists, remove the stale exclusion: route_99_deleted" in out


def test_route_cannot_be_both_mapped_and_excluded(_isolated_routes, capsys) -> None:
    _write_registry(
        _isolated_routes,
        qa_routes={"route_01_covered": "#missing", "route_02_uncovered": "#missing"},
        excluded_qa_routes={"route_01_covered": "internal-only"},
    )
    assert cwc.check() == 1
    assert "QA route is both mapped and excluded: route_01_covered" in capsys.readouterr().out
