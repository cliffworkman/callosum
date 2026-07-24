"""Formatted-citation engine (inc 106) — citeproc-js rendering via the bundled CSL styles.

Requires the build toolchain (Node + the pinned `citeproc`; `npm install`/`npm ci`). Output is deterministic
for the pinned citeproc version + bundled style files, so we assert concrete substrings + the in-text marker.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.citations import render
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

PAPER_CSL = {
    "type": "article-journal",
    "title": "Attention is all you need",
    "author": [
        {"family": "Vaswani", "given": "Ashish"},
        {"family": "Shazeer", "given": "Noam"},
        {"family": "Parmar", "given": "Niki"},
    ],
    "issued": {"date-parts": [[2017]]},
    "container-title": "Advances in Neural Information Processing Systems",
    "volume": "30",
    "page": "5998-6008",
}


def _make_paper(temp_db_url: str) -> int:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Attention is all you need", csl_json=PAPER_CSL)
    engine.dispose()
    return pid


def test_render_apa_author_date(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render", json={"paper_ids": [pid], "style": "apa", "locale": "en-US"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["style"] == "apa"
    item = d["items"][0]
    assert item["in_text"] == "(Vaswani et al., 2017)"  # APA author-date in-text
    assert "Vaswani, A." in item["reference_text"] and "2017" in item["reference_text"]
    assert (
        "<i>" in item["reference_html"] and "<div" not in item["reference_html"]
    )  # sanitized: italics kept, divs dropped
    assert "Attention is all you need" in d["bibliography_text"]


def test_render_ieee_numeric(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render", json={"paper_ids": [pid], "style": "ieee"})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["in_text"] == "[1]"  # numeric in-text


def test_styles_endpoint(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    d = client.get("/citations/styles").json()
    ids = {s["id"] for s in d["styles"]}
    assert {"apa", "ieee", "modern-language-association", "chicago-author-date"} <= ids
    assert d["default_style"] == "apa" and "en-US" in d["locales"]


def test_render_validation(temp_db_url: str) -> None:
    pid = _make_paper(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/render", json={"paper_ids": [pid], "style": "not-a-style"}).status_code == 422
    assert (
        client.post("/citations/render", json={"paper_ids": [999999], "style": "apa"}).status_code == 422
    )  # no live papers


def test_engine_unavailable_returns_503(temp_db_url: str, monkeypatch) -> None:
    pid = _make_paper(temp_db_url)
    # Simulate the citeproc dependency being absent → the route degrades to 503, never 500.
    monkeypatch.setattr(render, "_CITEPROC", render.PROJECT_ROOT / "node_modules" / "__absent__")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/citations/render", json={"paper_ids": [pid], "style": "apa"}).status_code == 503


# ── document render (inc 107): position-aware in-text — numbering + disambiguation ──────────────────────

_DOC_ITEMS = {
    "a": {
        "id": "a",
        "type": "article-journal",
        "title": "Attention",
        "author": [{"family": "Vaswani", "given": "A"}],
        "issued": {"date-parts": [[2017]]},
        "container-title": "NeurIPS",
    },
    "b": {
        "id": "b",
        "type": "article-journal",
        "title": "BERT",
        "author": [{"family": "Devlin", "given": "J"}],
        "issued": {"date-parts": [[2019]]},
        "container-title": "NAACL",
    },
    "c": {
        "id": "c",
        "type": "article-journal",
        "title": "GPT",
        "author": [{"family": "Radford", "given": "A"}],
        "issued": {"date-parts": [[2018]]},
        "container-title": "OpenAI",
    },
}


def _cluster(cid: str, item_key: str) -> dict:
    return {"citationID": cid, "items": [_DOC_ITEMS[item_key]]}


def test_render_document_ieee_numbering_and_renumber(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    # Document order A,B,C → numbers follow appearance: A=[1] B=[2] C=[3].
    r = client.post(
        "/citations/render-document",
        json={"style": "ieee", "citations": [_cluster("A", "a"), _cluster("B", "b"), _cluster("C", "c")]},
    )
    assert r.status_code == 200, r.text
    d = r.json()
    by_id = {c["citationID"]: c["text"] for c in d["citations"]}
    assert by_id == {"A": "[1]", "B": "[2]", "C": "[3]"}
    assert len(d["bibliography_text"].splitlines()) == 3

    # Reverse the document order → the SAME citation renumbers by its new position.
    r2 = client.post(
        "/citations/render-document",
        json={"style": "ieee", "citations": [_cluster("C", "c"), _cluster("B", "b"), _cluster("A", "a")]},
    )
    assert r2.status_code == 200, r2.text
    by_id2 = {c["citationID"]: c["text"] for c in r2.json()["citations"]}
    assert by_id2 == {"C": "[1]", "B": "[2]", "A": "[3]"}  # A was [1], now [3]


def test_render_document_apa_disambiguation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    s1 = {
        "id": "s1",
        "type": "article-journal",
        "title": "Alpha",
        "author": [{"family": "Smith", "given": "J"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "J1",
    }
    s2 = {
        "id": "s2",
        "type": "article-journal",
        "title": "Beta",
        "author": [{"family": "Smith", "given": "J"}],
        "issued": {"date-parts": [[2020]]},
        "container-title": "J2",
    }
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [
                {"citationID": "x", "items": [s1]},
                {"citationID": "y", "items": [s2]},
            ],
        },
    )
    assert r.status_code == 200, r.text
    by_id = {c["citationID"]: c["text"] for c in r.json()["citations"]}
    assert by_id["x"] == "(Smith, 2020a)"  # same-author/year disambiguated across the document
    assert by_id["y"] == "(Smith, 2020b)"


def test_render_document_validation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    bad = client.post("/citations/render-document", json={"style": "not-a-style", "citations": [_cluster("A", "a")]})
    assert bad.status_code == 422


def test_render_document_note_indexes_reach_citeproc(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    citations = [
        {**_cluster("first", "a"), "noteIndex": 1},
        {**_cluster("other", "b"), "noteIndex": 2},
        {**_cluster("subsequent", "a"), "noteIndex": 3},
    ]
    r = client.post(
        "/citations/render-document",
        json={"style": "chicago-notes-bibliography", "citations": citations},
    )
    assert r.status_code == 200, r.text
    by_id = {c["citationID"]: c["text"] for c in r.json()["citations"]}
    assert "Vaswani" in by_id["first"]
    assert by_id["subsequent"] != by_id["first"]


@pytest.mark.parametrize("note_index", [-1, 5001, 1.5, True])
def test_render_document_rejects_invalid_note_index(temp_db_url: str, note_index: object) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={"style": "chicago-notes-bibliography", "citations": [{**_cluster("A", "a"), "noteIndex": note_index}]},
    )
    assert r.status_code == 422


# ── per-occurrence cite properties (P0 phase 3, backlog #33/#34): locator/prefix/suffix/suppress-author/
# author-only actually reach citeproc-js, via CitationItem → citeproc_runner.js's buildCitationItem ──────────


def test_render_document_locator_and_label(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "12", "label": "page"}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert "12" in text  # the locator value renders somewhere in the in-text citation
    assert text != "(Vaswani, 2017)"  # differs from the no-locator baseline


def test_render_document_prefix_suffix(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "prefix": "see ", "suffix": " (emphasis added)"}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    # citeproc wraps prefix/suffix INSIDE the citation's own parenthetical group, around the cite itself —
    # "(see Vaswani, 2017 (emphasis added))" — not appended outside the parens.
    assert text == "(see Vaswani, 2017 (emphasis added))"


def test_render_document_suppress_author(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    baseline = client.post(
        "/citations/render-document",
        json={"style": "apa", "citations": [{"citationID": "A", "items": [_DOC_ITEMS["a"]]}]},
    ).json()["citations"][0]["text"]
    item = {**_DOC_ITEMS["a"], "suppress-author": True}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert "Vaswani" not in text  # author suppressed
    assert text != baseline


def test_render_document_author_only(temp_db_url: str) -> None:
    """citeproc's "author-only" renders JUST the author name, dropping the date entirely — the building block
    for a manual narrative construction ("As Vaswani showed... (2017)"), paired with a companion suppress-author
    cite for the date elsewhere. It is not itself a full "Vaswani (2017)" narrative form."""
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "author-only": True}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 200, r.text
    text = r.json()["citations"][0]["text"]
    assert text == "Vaswani"  # no parens, no year — author name only
    assert "2017" not in text


def test_citation_item_rejects_unknown_locator_label(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "1", "label": "timestamp"}  # not a real CSL locator label
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 422


def test_citation_item_locator_length_capped(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    item = {**_DOC_ITEMS["a"], "locator": "x" * 201}
    r = client.post(
        "/citations/render-document", json={"style": "apa", "citations": [{"citationID": "A", "items": [item]}]}
    )
    assert r.status_code == 422


# ── P1 item #11 (backlog #33/#34): bibliography editing — include an uncited "further reading" work, exclude a
# specific CITED work from the bibliography (e.g. a personal communication) — both real citeproc-js mechanisms
# (updateUncitedItems / makeBibliography's field-filter bibsection), just newly wired through this endpoint ──


def test_render_document_uncited_item_appears_in_bibliography_with_no_in_text_citation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [_cluster("A", "a")],
            "uncited_items": [_DOC_ITEMS["c"]],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["citations"]) == 1  # only the actually-cited cluster gets an in-text render
    assert "Radford" in d["bibliography_text"]  # the uncited item ("c") still appears in the bibliography
    assert "Vaswani" in d["bibliography_text"]


def test_render_document_bibliography_exclude_removes_entry_but_keeps_in_text_citation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={
            "style": "apa",
            "citations": [_cluster("A", "a"), _cluster("B", "b")],
            "bibliography_exclude_ids": ["b"],
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    by_id = {c["citationID"]: c["text"] for c in d["citations"]}
    assert "Devlin" in by_id["B"]  # the excluded work's in-text citation still renders
    assert "Devlin" not in d["bibliography_text"]  # but it's gone from the bibliography
    assert "Vaswani" in d["bibliography_text"]  # the non-excluded work is unaffected


def test_render_document_uncited_item_missing_id_rejected(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/citations/render-document",
        json={"style": "apa", "citations": [_cluster("A", "a")], "uncited_items": [{"title": "No id"}]},
    )
    assert r.status_code == 422


def test_render_document_bibliography_editing_fields_are_optional(temp_db_url: str) -> None:
    """Existing callers (no uncited_items/bibliography_exclude_ids at all) are completely unaffected — the
    additive-fields contract the security-audit addendum relies on."""
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/citations/render-document", json={"style": "apa", "citations": [_cluster("A", "a")]})
    assert r.status_code == 200, r.text
