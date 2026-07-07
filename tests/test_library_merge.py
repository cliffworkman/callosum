import json
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select

from alembic import command
from alembic.config import Config
from app.backend.persistence import schema
from app.backend.persistence.schema import merge_operations, papers


def _fresh_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.sqlite'}")
    schema.metadata.create_all(engine)
    return engine


def test_merge_operations_roundtrip_and_merged_into_column(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = conn.execute(insert(papers).values(title="A", csl_json={})).inserted_primary_key[0]
        b = conn.execute(insert(papers).values(title="B", csl_json={}, merged_into=a)).inserted_primary_key[0]
        op_id = conn.execute(
            insert(merge_operations).values(
                canonical_paper_id=a, merged_paper_id=b, snapshot_json=json.dumps({"repoints": []}), status="active"
            )
        ).inserted_primary_key[0]
        row = conn.execute(select(merge_operations).where(merge_operations.c.id == op_id)).mappings().one()
        assert row["status"] == "active" and row["canonical_paper_id"] == a and row["merged_paper_id"] == b
        assert conn.execute(select(papers.c.merged_into).where(papers.c.id == b)).scalar_one() == a


def test_migrations_upgrade_head_creates_merge_schema(tmp_path):
    db = tmp_path / "mig.sqlite"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    from sqlalchemy import inspect

    insp = inspect(engine)
    assert "merge_operations" in insp.get_table_names()
    assert "merged_into" in {c["name"] for c in insp.get_columns("papers")}


def test_allowlist_covers_every_paper_referencing_table():
    # Fails if a table references papers (by FK or a paper_id-shaped column) but isn't classified into a bucket.
    from app.backend.persistence.merge_allowlist import assert_allowlist_complete

    assert_allowlist_complete(schema.metadata)  # raises AssertionError naming any unbucketed table


def test_allowlist_guard_detects_a_missing_table(monkeypatch):
    import pytest

    import app.backend.persistence.merge_allowlist as al

    monkeypatch.setattr(al, "UNION_TABLES", [t for t in al.UNION_TABLES if t[0] != "annotations"])

    with pytest.raises(AssertionError, match="annotations"):
        al.assert_allowlist_complete(schema.metadata)


def _add_paper(conn, **cols):
    cols.setdefault("csl_json", {})
    return conn.execute(insert(papers).values(**cols)).inserted_primary_key[0]


def test_merge_preview_reports_field_conflicts_and_counts(tmp_path):
    from app.backend.persistence.merge_repo import merge_preview
    from app.backend.persistence.schema import annotations

    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(
            conn, title="Neural correlates", year=2023, doi="10.1/abc", csl_json={"title": "Neural correlates"}
        )
        b = _add_paper(conn, title="Neural Correlates", year=2023, csl_json={"title": "Neural Correlates"})
        conn.execute(insert(annotations).values(paper_id=b, page=1, note="x"))
        preview = merge_preview(conn, a, b)
    fields = {f["field"]: f for f in preview["fields"]}
    assert fields["title"]["agree"] is False and fields["title"]["value_a"] == "Neural correlates"
    assert fields["year"]["agree"] is True
    assert fields["doi"]["value_b"] in (None, "")  # B has no DOI
    assert preview["association_counts"]["annotations"] >= 1


def test_merge_repoints_union_dedups_membership_and_hides_b(tmp_path):
    from app.backend.persistence.merge_repo import merge_papers
    from app.backend.persistence.schema import annotations, paper_tags, tags

    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={"title": "A"})
        b = _add_paper(conn, title="B", csl_json={"title": "B"})
        t1 = conn.execute(insert(tags).values(name="shared")).inserted_primary_key[0]
        t2 = conn.execute(insert(tags).values(name="b-only")).inserted_primary_key[0]
        conn.execute(insert(paper_tags).values(paper_id=a, tag_id=t1))
        conn.execute(insert(paper_tags).values(paper_id=b, tag_id=t1))  # collision -> drop B's
        conn.execute(insert(paper_tags).values(paper_id=b, tag_id=t2))  # unique -> re-point
        conn.execute(insert(annotations).values(paper_id=b, page=1, note="n"))  # union -> re-point

        op_id = merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={"title": "A"})

        a_tags = set(conn.execute(select(paper_tags.c.tag_id).where(paper_tags.c.paper_id == a)).scalars())
        assert a_tags == {t1, t2}
        assert (
            conn.execute(select(func.count()).select_from(paper_tags).where(paper_tags.c.paper_id == b)).scalar_one()
            == 0
        )
        assert (
            conn.execute(select(func.count()).select_from(annotations).where(annotations.c.paper_id == a)).scalar_one()
            == 1
        )
        hidden = (
            conn.execute(select(papers.c.deleted_at, papers.c.merged_into).where(papers.c.id == b)).mappings().one()
        )
        assert hidden["deleted_at"] is not None and hidden["merged_into"] == a
        assert (
            conn.execute(select(merge_operations.c.status).where(merge_operations.c.id == op_id)).scalar_one()
            == "active"
        )


def test_merge_drops_derived_preserves_reviewed_finding_and_rewrites_json(tmp_path):
    from app.backend.persistence.merge_repo import merge_papers
    from app.backend.persistence.schema import open_science_signals, paper_findings, profile

    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={})
        b = _add_paper(conn, title="B", csl_json={})
        conn.execute(insert(open_science_signals).values(paper_id=b, signal_type="data", status="present", source="oa"))
        # findings collision on (source, content_key): B's is reviewed, A's isn't -> keep the reviewed one on A
        conn.execute(
            insert(paper_findings).values(
                paper_id=a, source="s", kind="candidate", payload={}, content_key="k", review_state=None
            )
        )
        conn.execute(
            insert(paper_findings).values(
                paper_id=b, source="s", kind="candidate", payload={}, content_key="k", review_state="confirmed"
            )
        )
        conn.execute(insert(profile).values(starred_paper_ids=[b], research_domains=[]))

        merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})

        assert (
            conn.execute(
                select(func.count()).select_from(open_science_signals).where(open_science_signals.c.paper_id == b)
            ).scalar_one()
            == 0
        )
        kept = (
            conn.execute(
                select(paper_findings.c.review_state).where(
                    paper_findings.c.paper_id == a, paper_findings.c.content_key == "k"
                )
            )
            .scalars()
            .all()
        )
        assert "confirmed" in kept  # the reviewed row survived on A
        assert conn.execute(select(profile.c.starred_paper_ids)).scalar_one() == [a]  # b -> a rewrite


def test_merge_drops_the_ab_dismissed_pair(tmp_path):
    from app.backend.persistence.merge_repo import merge_papers
    from app.backend.persistence.schema import dismissed_duplicate_pairs

    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={})
        b = _add_paper(conn, title="B", csl_json={})
        lo, hi = sorted((a, b))
        conn.execute(insert(dismissed_duplicate_pairs).values(paper_id_low=lo, paper_id_high=hi))
        merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})
        assert conn.execute(select(func.count()).select_from(dismissed_duplicate_pairs)).scalar_one() == 0
