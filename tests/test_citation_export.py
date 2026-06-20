from __future__ import annotations

import json

import pytest

from app.backend.metadata.citation_export import render_citations, to_bibtex, to_csl_json, to_ris

PAPER = {
    "csl_json": {
        "type": "article-journal",
        "title": "Faces & Judgments: A Study",
        "author": [{"family": "Smith", "given": "Jane"}, {"family": "Doe", "given": "John"}],
        "issued": {"date-parts": [[2020, 5, 1]]},
        "container-title": "Journal of Faces",
        "volume": "12",
        "issue": "3",
        "page": "10-20",
        "DOI": "10.1/abc",
        "URL": "https://example.org/x",
        "ISSN": "1234-5678",
        "abstract": "<jats:p>An abstract.</jats:p>",
    },
    "citation_key": "smith2020faces",
    "first_author_family_name": "Smith",
    "year": 2020,
    "venue": "Journal of Faces",
    "doi": "10.1/abc",
    "item_type": "article-journal",
    "title": "Faces & Judgments: A Study",
    "abstract": "<jats:p>An abstract.</jats:p>",
}


def test_bibtex_maps_fields_escapes_and_preserves_title_case() -> None:
    bib = to_bibtex([PAPER])
    assert bib.startswith("@article{smith2020faces,")  # citation_key used as the entry key
    assert "author = {Smith, Jane and Doe, John}" in bib
    assert "title = {{Faces \\& Judgments: A Study}}" in bib  # double-braced (case) + escaped &
    assert "journal = {Journal of Faces}" in bib
    assert "year = {2020}" in bib
    assert "volume = {12}" in bib and "number = {3}" in bib
    assert "pages = {10--20}" in bib  # en-dash range
    assert "doi = {10.1/abc}" in bib
    assert "abstract = {An abstract.}" in bib  # JATS stripped


def test_bibtex_key_falls_back_and_dedupes() -> None:
    p1 = {
        "csl_json": {
            "type": "article-journal",
            "author": [{"family": "Lee", "given": "A"}],
            "issued": {"date-parts": [[2019]]},
            "title": "One",
        },
        "first_author_family_name": "Lee",
        "year": 2019,
    }
    p2 = {
        "csl_json": {
            "type": "article-journal",
            "author": [{"family": "Lee", "given": "B"}],
            "issued": {"date-parts": [[2019]]},
            "title": "Two",
        },
        "first_author_family_name": "Lee",
        "year": 2019,
    }
    bib = to_bibtex([p1, p2])
    assert "@article{Lee2019," in bib  # no citation_key → {family}{year}
    assert "@article{Lee2019a," in bib  # collision → suffixed


def test_bibtex_entry_type_falls_back_to_misc() -> None:
    bib = to_bibtex([{"csl_json": {"type": "dataset", "title": "Data"}, "title": "Data"}])
    assert bib.startswith("@misc{")


def test_ris_maps_tags_and_terminates_record() -> None:
    ris = to_ris([PAPER])
    assert ris.startswith("TY  - JOUR")
    assert "AU  - Smith, Jane" in ris and "AU  - Doe, John" in ris
    assert "TI  - Faces & Judgments: A Study" in ris  # RIS is not brace-escaped
    assert "PY  - 2020" in ris
    assert "T2  - Journal of Faces" in ris
    assert "DO  - 10.1/abc" in ris
    assert "SP  - 10" in ris and "EP  - 20" in ris
    assert "AB  - An abstract." in ris
    assert ris.rstrip().endswith("ER  -")


def test_csl_json_round_trips_the_stored_record() -> None:
    out = json.loads(to_csl_json([PAPER]))
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["title"] == "Faces & Judgments: A Study"
    assert out[0]["DOI"] == "10.1/abc"
    assert out[0]["author"][0] == {"family": "Smith", "given": "Jane"}


def test_render_citations_dispatch_and_bad_format() -> None:
    for fmt, ext, mt in (("bibtex", "bib", "x-bibtex"), ("ris", "ris", "research-info"), ("csl-json", "json", "json")):
        text, media_type, file_ext = render_citations([PAPER], fmt)
        assert file_ext == ext and mt in media_type and text.strip()
    with pytest.raises(ValueError):
        render_citations([PAPER], "bogus")


def test_literal_author_kept_verbatim_and_empty_list_is_blank() -> None:
    org = to_bibtex(
        [
            {
                "csl_json": {
                    "type": "report",
                    "author": [{"literal": "World Health Organization"}],
                    "title": "WHO Report",
                },
                "title": "WHO Report",
            }
        ]
    )
    assert "author = {World Health Organization}" in org and org.startswith("@techreport{")
    assert to_bibtex([]) == "" and to_ris([]) == "" and to_csl_json([]) == "[]\n"
