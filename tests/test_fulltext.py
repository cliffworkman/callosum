from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy import text as sql_text

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.fulltext_repo import SNIPPET_OPEN, _safe_match
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    soft_delete_paper,
)
from app.backend.persistence.schema import papers


def _seed_chunk(conn, *, title, text, page, checksum, first_author=None):
    pid = create_paper(conn, title=title, csl_json={"title": title}, first_author_family_name=first_author)
    aid = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=checksum,
    )
    create_chunk(
        conn,
        paper_id=pid,
        attachment_id=aid,
        text=text,
        page_start=page,
        page_end=page,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version=f"cv-{checksum}",
        source_attachment_checksum=checksum,
    )
    return pid


def test_safe_match_sanitization() -> None:
    # tokens become AND-ed quoted phrases; alphanumeric-only kept; FTS5 operators/quotes neutralized (never syntax err)
    assert _safe_match("ultimatum game") == '"ultimatum" "game"'
    assert _safe_match("") is None
    assert _safe_match("   ") is None
    assert _safe_match("* : ^") is None  # all-punctuation tokens dropped → None (the caller skips the query)
    assert _safe_match('say "hi"') == '"say" """hi"""'  # embedded quote escaped, no error
    assert _safe_match("risk OR reward") == '"risk" "OR" "reward"'  # OR is a literal term, not the FTS5 operator


def test_fulltext_search_and_trashed_exclusion(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed_chunk(
            conn,
            title="Game theory",
            text="the ultimatum game paradigm explored",
            page=3,
            checksum="a",
            first_author="Doe",
        )
        other = _seed_chunk(conn, title="Unrelated", text="a paper about photosynthesis", page=1, checksum="b")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    hits = client.get("/papers/fulltext", params={"q": "ultimatum game"}).json()
    assert len(hits) == 1
    h = hits[0]
    assert h["paper_id"] == pid and h["page_start"] == 3 and h["coordinate_precision"] == "region"
    assert "ultimatum" in h["snippet"] and SNIPPET_OPEN in h["snippet"]  # the matched term is marked
    assert h["author"] == "Doe"
    assert client.get("/papers/fulltext", params={"q": "photosynthesis"}).json()[0]["paper_id"] == other

    # a trashed (soft-deleted) paper is excluded from full-text results
    eng2 = make_engine(temp_db_url)
    with eng2.begin() as conn:
        soft_delete_paper(conn, pid)
    eng2.dispose()
    assert client.get("/papers/fulltext", params={"q": "ultimatum game"}).json() == []


def test_fulltext_malformed_and_empty_never_500(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    for q in ['"', "*", "NEAR(", "^", "", "   ", "a AND b OR (c"]:
        r = client.get("/papers/fulltext", params={"q": q})
        assert r.status_code == 200 and r.json() == []  # sanitized/handled → empty, never a 500


def test_fts_trigger_syncs_on_insert_and_cascade_delete(temp_db_url: str) -> None:
    # The AFTER INSERT + AFTER DELETE triggers keep chunks_fts in sync; the DELETE trigger must catch the FK CASCADE
    # from deleting a paper (the inc-65 path that bypasses the Python layer).
    engine = make_engine(temp_db_url)

    def fts_count(conn, term: str) -> int:
        return conn.execute(
            sql_text("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH :q"), {"q": f'"{term}"'}
        ).scalar()

    with engine.begin() as conn:
        pid = _seed_chunk(conn, title="Trigger test", text="a unique heliotrope passage", page=1, checksum="t")
        assert fts_count(conn, "heliotrope") == 1  # the AFTER INSERT trigger indexed the new chunk
        conn.execute(delete(papers).where(papers.c.id == pid))  # FK CASCADE → chunk deleted → AFTER DELETE trigger
        assert fts_count(conn, "heliotrope") == 0  # the trigger removed it from the FTS index
    engine.dispose()
