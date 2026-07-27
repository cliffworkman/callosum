"""Persistence helpers for saved per-paper GRIM/GRIMMER checks (inc 401). Mirrors paper_urls_repo.py's shape."""

from __future__ import annotations

from sqlalchemy import Connection, delete, insert, select
from sqlalchemy.engine import RowMapping

from app.backend.persistence.schema import paper_grim_checks, papers


def list_grim_checks(conn: Connection, paper_id: int) -> list[RowMapping]:
    stmt = (
        select(paper_grim_checks)
        .where(paper_grim_checks.c.paper_id == paper_id)
        .order_by(paper_grim_checks.c.id.desc())  # newest first
    )
    return list(conn.execute(stmt).mappings())


def add_grim_check(
    conn: Connection,
    paper_id: int,
    *,
    label: str | None,
    mean: str,
    sd: str | None,
    n: int,
    items: int,
    result_json: dict,
) -> int | None:
    if not _paper_exists(conn, paper_id):
        return None
    result = conn.execute(
        insert(paper_grim_checks).values(
            paper_id=paper_id, label=label, mean=mean, sd=sd, n=n, items=items, result_json=result_json
        )
    )
    return int(result.inserted_primary_key[0])


def delete_grim_check(conn: Connection, paper_id: int, check_id: int) -> bool:
    result = conn.execute(
        delete(paper_grim_checks).where(paper_grim_checks.c.paper_id == paper_id, paper_grim_checks.c.id == check_id)
    )
    return bool(result.rowcount)


def _paper_exists(conn: Connection, paper_id: int) -> bool:
    return conn.execute(select(papers.c.id).where(papers.c.id == paper_id).limit(1)).first() is not None
