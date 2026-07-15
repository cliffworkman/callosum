"""cr_candidate_related_papers — the other set papers a cross-paper critique candidate spans (set critical review, #12).

Additive + guarded; no down-migration. The value is the MODEL's framing (validated to the set), not a verified link.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0045_cr_candidate_related_papers"
down_revision = "0044_paper_tag_locks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("critical_review_candidates")}
    if "related_paper_ids_json" not in cols:
        op.add_column("critical_review_candidates", sa.Column("related_paper_ids_json", sa.JSON()))


def downgrade() -> None:
    return
