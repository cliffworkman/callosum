"""B2 SP3 — re-verify an imported synthesis against my library (convert in place to native).

Hermetic: the summarization app injects fake embed/vector/support models (via `_summarization_app`); we seed a
paper + chunk + an imported synthesis blob, then hit `POST /summaries/{id}/reverify`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper
from app.backend.persistence.schema import summaries

from .api_helpers import _summarization_app


def _blob(*, paper_id, source, quote="the relayed finding is supported", text="The relayed finding holds."):
    return {
        "generated_by": "sender",
        "scope_label": "1 paper",
        "overview": None,
        "sentences": [
            {
                "ordinal": 0,
                "text": text,
                "flagged": False,
                "citations": [
                    {
                        "paper_id": paper_id,
                        "paper_title": "Relayed Paper",
                        "source": source,
                        "quote": quote,
                        "page_start": 2,
                        "page_end": 2,
                        "status": "verified",
                        "retrieval_confidence": 0.9,
                        "quote_confidence": 1.0,
                        "support_confidence": 0.8,
                        "coordinate_precision": "region",
                    }
                ],
            }
        ],
    }


def _insert_imported(conn, blob):
    return conn.execute(
        insert(summaries).values(
            scope_type="papers",
            scope_ref_json={},
            content="A synthesis.",
            generated_by="sender",
            chunk_version_verified_against="imported",
            embedding_version_verified_against="imported",
            verification_version="imported",
            status="imported",
            imported_json=blob,
        )
    ).inserted_primary_key[0]


def _seed_paper_with_chunk(conn):
    pid = create_paper(
        conn,
        title="Relayed Paper",
        csl_json={"title": "Relayed Paper", "DOI": "10.7/rev"},
        doi="10.7/rev",
        year=2024,
        first_author_family_name="Reviewer",
    )
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="revchk",
    )
    create_chunk(
        conn,
        paper_id=pid,
        attachment_id=aid,
        text="the relayed finding is supported by strong evidence",
        page_start=2,
        page_end=2,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version="cv1",
        source_attachment_checksum="revchk",
    )
    return pid


def test_reverify_converts_imported_to_native(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _seed_paper_with_chunk(conn)  # the source paper IS in the library
        # paper_id None in the blob → re-verify must RE-RESOLVE via the source identity (paper added since import)
        sid = _insert_imported(conn, _blob(paper_id=None, source={"doi": "10.7/rev"}))
    engine.dispose()

    cl = TestClient(_summarization_app(temp_db_url))
    listed = cl.get("/summaries").json()
    assert [s for s in listed if s["imported"]][0]["summary_id"] == sid  # flagged imported before

    r = cl.post(f"/summaries/{sid}/reverify")
    assert r.status_code == 200
    body = r.json()
    assert body["imported"] is False  # now native
    cit = body["sentences"][0]["citations"][0]
    assert cit["chunk_id"] is not None  # a native, chunk-backed citation (re-resolved by identity)

    # 422 on re-verifying a now-native summary; 404 on a missing id
    assert cl.post(f"/summaries/{sid}/reverify").status_code == 422
    assert cl.post("/summaries/999999/reverify").status_code == 404

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        row = conn.execute(select(summaries).where(summaries.c.id == sid)).mappings().first()
        assert row["imported_json"] is None  # converted in place → native
        assert row["generated_by"] == "re-verified-from-bundle"  # provenance survives
        assert not [s for s in cl.get("/summaries").json() if s["imported"]]  # no longer flagged imported
    engine.dispose()


def test_reverify_source_not_in_library_flags_the_sentence(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        sid = _insert_imported(conn, _blob(paper_id=None, source={"doi": "10.7/absent"}))  # source NOT in the library
    engine.dispose()

    cl = TestClient(_summarization_app(temp_db_url))
    body = cl.post(f"/summaries/{sid}/reverify").json()
    assert body["imported"] is False
    sentence = body["sentences"][0]
    assert sentence["flagged"] is True  # unverifiable claim → flagged
    assert sentence["citations"] == []  # no local source → no native citation (the claim text still shows)
    assert sentence["text"] == "The relayed finding holds."
