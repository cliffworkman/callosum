"""Unit tests for the pure Details-pane edit-mapping helper (inc 49)."""

from __future__ import annotations

from app.backend.metadata.paper_edits import build_paper_update


def _row(csl: dict) -> dict:
    return {"csl_json": csl}


def test_scalar_field_updates_column_and_csl_and_stamps_provenance() -> None:
    out = build_paper_update(_row({"title": "Old", "type": "article-journal"}), {"venue": "Nature"})
    assert out["venue"] == "Nature"
    assert out["csl_json"]["container-title"] == "Nature"
    assert out["csl_json"]["title"] == "Old"  # untouched
    assert out["imported_source"] == "user-edited"


def test_clearing_a_field_pops_csl_and_nulls_column() -> None:
    out = build_paper_update(_row({"container-title": "Nature"}), {"venue": None})
    assert out["venue"] is None
    assert "container-title" not in out["csl_json"]


def test_csl_only_fields_have_no_column() -> None:
    out = build_paper_update(_row({}), {"volume": "8", "issue": "1", "page": "1-9", "issn": "2045-2322"})
    assert out["csl_json"]["volume"] == "8"
    assert out["csl_json"]["issue"] == "1"
    assert out["csl_json"]["page"] == "1-9"
    assert out["csl_json"]["ISSN"] == "2045-2322"
    assert {key for key in out if key != "csl_json"} == {"imported_source"}  # no scalar columns touched


def test_date_parts_rebuild_and_project_columns() -> None:
    out = build_paper_update(_row({}), {"year": 2018, "month": 12, "day": 1})
    assert out["csl_json"]["issued"] == {"date-parts": [[2018, 12, 1]]}
    assert out["year"] == 2018
    assert out["publication_date"] == "2018-12-1"


def test_partial_date_edit_merges_existing_parts() -> None:
    out = build_paper_update(_row({"issued": {"date-parts": [[2018, 12, 1]]}}), {"month": 6})
    assert out["csl_json"]["issued"] == {"date-parts": [[2018, 6, 1]]}
    assert out["publication_date"] == "2018-6-1"


def test_clearing_month_truncates_trailing_day() -> None:
    out = build_paper_update(_row({"issued": {"date-parts": [[2018, 12, 1]]}}), {"month": None})
    assert out["csl_json"]["issued"] == {"date-parts": [[2018]]}
    assert out["publication_date"] == "2018"


def test_clearing_year_drops_issued_entirely() -> None:
    out = build_paper_update(_row({"issued": {"date-parts": [[2018, 12, 1]]}}), {"year": None})
    assert "issued" not in out["csl_json"]
    assert out["year"] is None
    assert out["publication_date"] is None


def test_authors_stored_as_literal_with_first_family_projection() -> None:
    out = build_paper_update(_row({}), {"authors": ["Baez S", "Herrera E"]})
    assert out["csl_json"]["author"] == [{"literal": "Baez S"}, {"literal": "Herrera E"}]
    assert out["first_author_family_name"] == "Baez"


def test_empty_authors_clears() -> None:
    out = build_paper_update(_row({"author": [{"literal": "X"}]}), {"authors": []})
    assert "author" not in out["csl_json"]
    assert out["first_author_family_name"] is None


def test_generic_passthrough_sets_extras_and_ignores_reserved_keys() -> None:
    out = build_paper_update(_row({"title": "T"}), {"csl": {"publisher": "Springer", "title": "HACK"}})
    assert out["csl_json"]["publisher"] == "Springer"
    assert out["csl_json"]["title"] == "T"  # reserved key never overwritten via the generic path


def test_doi_is_normalized_in_column_and_csl() -> None:
    out = build_paper_update(_row({}), {"doi": "  10.1000/ABC  "})
    assert out["doi"] == "10.1000/abc"
    assert out["csl_json"]["DOI"] == "10.1000/abc"


def test_untouched_csl_keys_are_preserved() -> None:
    out = build_paper_update(_row({"title": "T", "volume": "8", "custom": "keep"}), {"venue": "N"})
    assert out["csl_json"]["custom"] == "keep"
    assert out["csl_json"]["volume"] == "8"
    assert out["csl_json"]["title"] == "T"
