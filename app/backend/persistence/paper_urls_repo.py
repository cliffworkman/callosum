"""Persistence helpers for first-class per-paper extra URLs."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Connection, delete, func, insert, select, update

from app.backend.persistence.schema import paper_urls, papers

URL_MAX_LEN = 2000
LABEL_MAX_LEN = 120


def list_paper_urls(conn: Connection, paper_id: int) -> list:
    stmt = (
        select(paper_urls)
        .where(paper_urls.c.paper_id == paper_id)
        .order_by(paper_urls.c.position.asc(), paper_urls.c.id.asc())
    )
    return list(conn.execute(stmt).mappings())


def add_paper_url(conn: Connection, paper_id: int, url: str, label: str | None = None) -> int | None:
    url = _clean_url(url)
    label = _clean_label(label)
    if not _paper_exists(conn, paper_id):
        return None
    row = conn.execute(
        select(paper_urls.c.id).where(paper_urls.c.paper_id == paper_id, paper_urls.c.url == url)
    ).first()
    if row is not None:
        conn.execute(update(paper_urls).where(paper_urls.c.id == int(row[0])).values(label=label))
        sync_csl_extra_urls(conn, paper_id)
        return int(row[0])
    pos = conn.execute(
        select(func.coalesce(func.max(paper_urls.c.position), -1) + 1).where(paper_urls.c.paper_id == paper_id)
    ).scalar_one()
    result = conn.execute(insert(paper_urls).values(paper_id=paper_id, url=url, label=label, position=int(pos)))
    sync_csl_extra_urls(conn, paper_id)
    return int(result.inserted_primary_key[0])


def delete_paper_url(conn: Connection, paper_id: int, url_id: int) -> bool:
    result = conn.execute(delete(paper_urls).where(paper_urls.c.paper_id == paper_id, paper_urls.c.id == url_id))
    changed = bool(result.rowcount)
    if changed:
        sync_csl_extra_urls(conn, paper_id)
    return changed


def replace_paper_urls(conn: Connection, paper_id: int, urls: Sequence[str] | None) -> bool:
    if not _paper_exists(conn, paper_id):
        return False
    cleaned = _dedup_urls(urls or [])
    conn.execute(delete(paper_urls).where(paper_urls.c.paper_id == paper_id))
    for pos, url in enumerate(cleaned):
        conn.execute(insert(paper_urls).values(paper_id=paper_id, url=url, position=pos))
    sync_csl_extra_urls(conn, paper_id)
    return True


def sync_csl_extra_urls(conn: Connection, paper_id: int) -> None:
    row = conn.execute(select(papers.c.csl_json).where(papers.c.id == paper_id)).first()
    if row is None:
        return
    csl = dict(row[0] or {})
    urls = [row["url"] for row in list_paper_urls(conn, paper_id)]
    if urls:
        csl["extra_urls"] = urls
    else:
        csl.pop("extra_urls", None)
    conn.execute(update(papers).where(papers.c.id == paper_id).values(csl_json=csl))


def _dedup_urls(urls: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in urls:
        url = _clean_url(raw)
        key = url.casefold()
        if key not in seen:
            seen.add(key)
            cleaned.append(url)
    return cleaned


def _clean_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        raise ValueError("URL must not be empty.")
    if len(text) > URL_MAX_LEN:
        raise ValueError("URL exceeds the maximum length.")
    if not (text.startswith("http://") or text.startswith("https://")):
        raise ValueError("URL must start with http:// or https://.")
    return text


def _clean_label(label: str | None) -> str | None:
    text = (label or "").strip()
    if not text:
        return None
    if len(text) > LABEL_MAX_LEN:
        raise ValueError("URL label exceeds the maximum length.")
    return text


def _paper_exists(conn: Connection, paper_id: int) -> bool:
    return conn.execute(select(papers.c.id).where(papers.c.id == paper_id).limit(1)).first() is not None
