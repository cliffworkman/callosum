"""allow_duplicate_paper_dois.

Revision ID: 0040_allow_duplicate_paper_dois
Revises: 0039_funding_discovery
Create Date: 2026-07-10
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0040_allow_duplicate_paper_dois"
down_revision = "0039_funding_discovery"
branch_labels = None
depends_on = None


def _paper_unique_constraints() -> set[str]:
    bind = op.get_bind()
    return {constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints("papers")}


def upgrade() -> None:
    if "uq_papers_doi" in _paper_unique_constraints():
        op.execute("PRAGMA foreign_keys=OFF")
        try:
            op.execute("DROP TABLE IF EXISTS _alembic_tmp_papers")
            with op.batch_alter_table("papers", recreate="always") as batch:
                batch.drop_constraint("uq_papers_doi", type_="unique")
        finally:
            op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    if "uq_papers_doi" not in _paper_unique_constraints():
        op.execute("PRAGMA foreign_keys=OFF")
        try:
            op.execute("DROP TABLE IF EXISTS _alembic_tmp_papers")
            with op.batch_alter_table("papers", recreate="always") as batch:
                batch.create_unique_constraint("uq_papers_doi", ["doi"])
        finally:
            op.execute("PRAGMA foreign_keys=ON")
