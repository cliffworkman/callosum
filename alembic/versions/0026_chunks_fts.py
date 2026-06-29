"""Full-text search over PDF chunk text (inc 209, A3): an external-content FTS5 index `chunks_fts` over
`chunks.text`, kept in sync by a trigger trio on `chunks`.

The exact-string complement to the semantic axes ("find a phrase verbatim"). External-content (`content='chunks',
content_rowid='id'`) so the text isn't duplicated; `snippet()`/`bm25()` are available. The DELETE trigger is the
critical one — it catches the **FK CASCADE delete** from `purge_paper` (inc 65) that bypasses the Python layer.

UNLIKE the metadata-table migrations (0021/0022), `metadata.create_all` (0001) **cannot** express an FTS5 virtual
table or triggers, so a fresh DB does NOT get them from create_all — this migration is the source of truth and runs
on fresh DBs too (the startup auto-migrate / the guarded chain). For the same reason 0001's downgrade loop (which
drops `metadata.sorted_tables`) can't drop `chunks_fts`, so this migration's `downgrade()` is **real + guarded** (no
double-drop conflict).

Revision ID: 0026_chunks_fts
Revises: 0025_saved_searches
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0026_chunks_fts"
down_revision = "0025_saved_searches"
branch_labels = None
depends_on = None

# The external-content FTS5 sync trigger trio (the standard SQLite pattern: a 'delete' command row removes the old
# terms from the index; INSERT adds the new ones). The DELETE trigger fires on the FK CASCADE from purge_paper.
_STATEMENTS = [
    "CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='id')",
    "CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN"
    "  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);"
    "END",
    "CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN"
    "  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);"
    "END",
    "CREATE TRIGGER chunks_au AFTER UPDATE ON chunks BEGIN"
    "  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);"
    "  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);"
    "END",
    # backfill the already-extracted chunks (empty on a fresh DB; populated on an existing library)
    "INSERT INTO chunks_fts(rowid, text) SELECT id, text FROM chunks",
]


def upgrade() -> None:
    bind = op.get_bind()
    if "chunks_fts" in set(sa.inspect(bind).get_table_names()):
        return  # already built
    for stmt in _STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    bind = op.get_bind()
    if "chunks_fts" not in set(sa.inspect(bind).get_table_names()):
        return
    for trig in ("chunks_ai", "chunks_ad", "chunks_au"):
        op.execute(f"DROP TRIGGER IF EXISTS {trig}")
    op.execute("DROP TABLE IF EXISTS chunks_fts")
