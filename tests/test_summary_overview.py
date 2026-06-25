from __future__ import annotations

import sqlalchemy as sa

from app.backend.persistence.database import make_engine


def test_summaries_has_overview_json_column(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)  # create_all + alembic upgrade head
    cols = {c["name"] for c in sa.inspect(engine).get_columns("summaries")}
    engine.dispose()
    assert "overview_json" in cols
