"""Drop followed_author_candidates (backlog #29's Followed Authors tab consolidated into Discover -> Feed,
2026-08-27): its curated "gap" list (works by a followed author not yet in the library) was retired -- Feed's
own chronological stream (already covering followed authors' works via FollowedAuthorFeedSource, badged
"Followed") is the sole remaining surface. `followed_authors` itself (the subscription list) is untouched --
only its now-orphaned candidate cache goes. A genuine forward cleanup migration, not a downgrade of 0069:
that migration's own guarded create is left as historical record; this one removes what it created.

Revision ID: 0077_drop_followed_author_candidates
Revises: 0076_critical_review_candidate_triage
Create Date: 2026-08-27
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0077_drop_followed_author_candidates"
down_revision = "0076_critical_review_candidate_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "followed_author_candidates" in inspector.get_table_names():
        op.drop_table("followed_author_candidates")


def downgrade() -> None:
    # Additive-only convention -- 0001 owns eventual teardown; this migration is itself the cleanup.
    pass
