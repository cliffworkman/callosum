"""Read-only access to the disposable library copy.

Every connection is opened `mode=ro&immutable=1`: it cannot create a WAL/SHM sidecar, checkpoint, or write, so the copy's
fingerprint is unchanged by construction. (`make_engine` in the app sets `journal_mode=WAL` on connect, so it is NOT used here.)
Two handles: a plain sqlite3 connection for row reads, and a SQLAlchemy engine for the embedding/vector-store helpers.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine

from app.backend.persistence.document_roles import SQLITE_DOCUMENT_ROLE_CASE_FOR_A
from experiments.ask_cli_revised.contract_directed import seams

CHUNK_COLUMNS = (
    "c.id AS chunk_id, c.paper_id, c.attachment_id, c.text, c.section, c.page_start, c.page_end, c.char_start, c.char_end, "
    "c.bbox_json, c.extraction_tool, c.extraction_version, c.chunking_strategy, c.chunk_version, c.source_attachment_checksum, "
    "c.grobid_section_id, s.section_kind AS grobid_kind"
)


def _uri(path: Path) -> str:
    return f"file:{Path(path).resolve().as_posix()}?mode=ro&immutable=1"


class Library:
    def __init__(self, db_path: Path | str):
        self.path = Path(db_path)
        self.con = sqlite3.connect(_uri(self.path), uri=True)
        self.con.row_factory = sqlite3.Row
        self.engine: Engine = create_engine(f"sqlite:///{_uri(self.path)}&uri=true", future=True)
        self._chunk_cache: dict[int, list[dict]] = {}
        self._box_cache: dict[tuple[int, int], dict[int, seams.Box]] = {}

    def close(self) -> None:
        self.con.close()
        self.engine.dispose()

    # ---- papers and attachments -------------------------------------------------------------------------------------

    def papers(self) -> list[dict]:
        rows = self.con.execute(
            "SELECT id, title, abstract, year, doi, venue FROM papers WHERE deleted_at IS NULL ORDER BY id"
        ).fetchall()
        return [dict(r) for r in rows]

    def paper(self, paper_id: int) -> dict | None:
        row = self.con.execute(
            "SELECT id, title, abstract, year, doi, venue FROM papers WHERE id=?", (paper_id,)
        ).fetchone()
        return dict(row) if row else None

    def article_attachments(self, paper_id: int) -> list[dict]:
        """Article-role attachments that have chunks, primary first. `is_primary` is the stored role, never inferred."""
        rows = self.con.execute(
            f"""
            SELECT a.id, a.role, a.checksum, a.attachment_type, {SQLITE_DOCUMENT_ROLE_CASE_FOR_A} AS document_role,
                   (SELECT COUNT(*) FROM chunks c WHERE c.attachment_id = a.id) AS n_chunks
            FROM attachments a WHERE a.paper_id = ?
            """,
            (paper_id,),
        ).fetchall()
        out = []
        for r in rows:
            if r["document_role"] != "article-fulltext" or not r["n_chunks"]:
                continue
            out.append(
                {
                    "id": r["id"],
                    "role": r["role"],
                    "checksum": r["checksum"],
                    "is_primary": (r["role"] or "").strip().lower() == "primary",
                    "n_chunks": r["n_chunks"],
                }
            )
        return sorted(out, key=lambda a: (not a["is_primary"], a["id"]))

    def attachment(self, attachment_id: int) -> dict | None:
        row = self.con.execute(
            "SELECT id, paper_id, role, checksum FROM attachments WHERE id=?", (attachment_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "paper_id": row["paper_id"],
            "role": row["role"],
            "checksum": row["checksum"],
            "is_primary": (row["role"] or "").strip().lower() == "primary",
        }

    # ---- chunks -----------------------------------------------------------------------------------------------------

    def attachment_chunks(self, attachment_id: int) -> list[dict]:
        """All chunks of one attachment in stream order (char_start, id), with GROBID kind when mapped."""
        if attachment_id not in self._chunk_cache:
            rows = self.con.execute(
                f"""
                SELECT {CHUNK_COLUMNS}
                FROM chunks c LEFT JOIN paper_sections s ON s.id = c.grobid_section_id
                WHERE c.attachment_id = ? ORDER BY c.char_start, c.id
                """,
                (attachment_id,),
            ).fetchall()
            self._chunk_cache[attachment_id] = [dict(r) for r in rows]
        return self._chunk_cache[attachment_id]

    def chunk(self, chunk_id: int) -> dict | None:
        row = self.con.execute(
            f"SELECT {CHUNK_COLUMNS} FROM chunks c LEFT JOIN paper_sections s ON s.id = c.grobid_section_id WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        return dict(row) if row else None

    def page_boxes(self, attachment_id: int, page: int) -> dict[int, seams.Box]:
        """chunk_id -> Box for every geometry-bearing chunk on one page of one attachment (for the intervening-block check)."""
        key = (attachment_id, page)
        if key not in self._box_cache:
            boxes = {}
            for chunk in self.attachment_chunks(attachment_id):
                if chunk["page_start"] == page:
                    box = seams.chunk_box(chunk)
                    if box is not None:
                        boxes[chunk["chunk_id"]] = box
            self._box_cache[key] = boxes
        return self._box_cache[key]

    def seam_verifier(self):
        """A `(chunk_a, chunk_b) -> SeamVerdict` callable bound to this library (attachment checksums and page geometry)."""

        def verify(a: dict, b: dict):
            attachment = self.attachment(a["attachment_id"]) if a.get("attachment_id") is not None else None
            checksum = attachment["checksum"] if attachment else None
            page = a.get("page_start")
            boxes = (
                self.page_boxes(a["attachment_id"], page)
                if page is not None and a.get("attachment_id") is not None
                else {}
            )
            return seams.verify_seam(a, b, attachment_checksum=checksum, page_boxes=boxes)

        return verify

    def article_chunk_index(self) -> list[dict]:
        """Light rows (no text) for every chunk of every live paper's article-role attachment: the whole-library pool."""
        rows = self.con.execute(
            f"""
            SELECT c.id AS chunk_id, c.paper_id, c.attachment_id, c.section, c.page_start, c.chunk_version,
                   s.section_kind AS grobid_kind, a.role AS attachment_role
            FROM chunks c
            JOIN attachments a ON a.id = c.attachment_id
            JOIN papers p ON p.id = c.paper_id AND p.deleted_at IS NULL
            LEFT JOIN paper_sections s ON s.id = c.grobid_section_id
            WHERE ({SQLITE_DOCUMENT_ROLE_CASE_FOR_A}) = 'article-fulltext'
            ORDER BY c.id
            """
        ).fetchall()
        return [dict(r) for r in rows]
