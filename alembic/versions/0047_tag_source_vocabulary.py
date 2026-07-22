"""Tag provenance vocabulary formalization (backlog #9): rename the two bare `tags.import_source` values that
predate the `{namespace}:{origin}` contract — `"zotero"` -> `"import:zotero"` and `"ai-agent"` -> `"agent:mcp"` —
so every tag producer's provenance conforms (`app/backend/persistence/tags_repo.py::TAG_SOURCE_NAMESPACES`). The
existing `keyword:crossref` / `keyword:openalex` / `keyword:pubmed` values already conform; `"user"` stays the
one blessed bare sentinel. Pure data UPDATE, scoped to the `tags` table only — the same bare values on
`papers`/`attachments`/`collections`/`notes`/`annotations` are a separate, untouched provenance vocabulary.
Idempotent (a re-run matches zero rows).

Revision ID: 0047_tag_source_vocabulary
Revises: 0046_overlooked_candidates
Create Date: 2026-07-22
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0047_tag_source_vocabulary"
down_revision = "0046_overlooked_candidates"
branch_labels = None
depends_on = None

_RENAMES = {"zotero": "import:zotero", "ai-agent": "agent:mcp"}


def upgrade() -> None:
    bind = op.get_bind()
    tags = sa.table("tags", sa.column("import_source", sa.String))
    for old, new in _RENAMES.items():
        bind.execute(tags.update().where(tags.c.import_source == old).values(import_source=new))


def downgrade() -> None:
    # No-op by design (no down-migrations, per project convention).
    return
