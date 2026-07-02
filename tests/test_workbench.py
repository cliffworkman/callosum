"""inc 253 — the meta-analysis extraction workspace (SP2a-1): the repo (projects/rows/cells + templates + the convert
hook) and the endpoints (CRUD + convert + CSV/audit export). Hermetic (temp_db_url + make_engine / TestClient)."""

from __future__ import annotations

import json

from sqlalchemy import delete

from app.backend.methods.effectsize import convert
from app.backend.persistence import workbench_repo as wr
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import metadata, papers


def _paper(conn, title) -> int:
    return create_paper(conn, title=title, csl_json={"title": title}, doi=f"10.1/{title}")


# ---- repo ---------------------------------------------------------------------------------------------------------


def test_create_project_seeds_template_and_lists(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = wr.create_project(conn, name="My review", design="two_group_continuous")
        p = wr.get_project(conn, pid)
        template = json.loads(p["template_json"])
        listed = wr.list_projects(conn)
    engine.dispose()
    assert p["design"] == "two_group_continuous"
    assert [f["key"] for f in template] == ["n1", "m1", "s1", "n2", "m2", "s2"]
    assert wr.role_columns(template).keys() == {"n1", "m1", "s1", "n2", "m2", "s2"}
    assert listed[0]["id"] == pid and listed[0]["row_count"] == 0


def test_add_row_upsert_cell_and_view(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper = _paper(conn, "Alpha")
        pid = wr.create_project(conn, name="R", design="correlation")
        r_linked = wr.add_row(conn, pid, paper_id=paper, label="Study A")
        r_manual = wr.add_row(conn, pid, label="external")
        wr.upsert_cell(conn, r_linked, "r", value="0.5", page=7, quote="r = .50")
        wr.upsert_cell(conn, r_linked, "r", value="0.42")  # upsert overwrites (page/quote cleared)
        wr.upsert_cell(conn, r_linked, "n", value="60")
        view = wr.project_view(conn, pid)
    engine.dispose()
    assert view["design"] == "correlation"
    assert [row["id"] for row in view["rows"]] == [r_linked, r_manual]  # position order
    linked = view["rows"][0]
    assert linked["paper_title"] == "Alpha"
    assert linked["cells"]["r"]["value"] == "0.42" and linked["cells"]["r"]["page"] is None
    assert linked["cells"]["n"]["value"] == "60"


def test_convert_map_two_group_matches_sp1(temp_db_url):
    cells = {"m1": "103", "s1": "5.5", "n1": "50", "m2": "100", "s2": "4.5", "n2": "50"}
    family, inputs = wr.CONVERT_MAP["two_group_continuous"](cells)
    result = convert(family, inputs)
    assert family == "smd"
    assert result.metric == "Hedges' g"
    assert abs(result.value - 0.5924) < 1e-3
    # binary + correlation maps
    bf, bi = wr.CONVERT_MAP["binary_2x2"]({"a": "10", "b": "20", "c": "5", "d": "25", "measure": "or"})
    assert bf == "binary" and abs(convert(bf, bi).value - 0.9163) < 1e-3
    cf, ci = wr.CONVERT_MAP["correlation"]({"r": "0.5", "n": "28"})
    assert cf == "correlation" and abs(convert(cf, ci).value - 0.5493) < 1e-3


def test_cascade_delete_and_paper_survives_purge(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper = _paper(conn, "Beta")
        pid = wr.create_project(conn, name="R", design="correlation")
        row = wr.add_row(conn, pid, paper_id=paper)
        wr.upsert_cell(conn, row, "r", value="0.3")
        # a purged paper must not break the row (paper_id is a plain column, no FK): delete the paper row directly
        conn.execute(delete(papers).where(papers.c.id == paper))
        view = wr.project_view(conn, pid)
        assert view["rows"][0]["paper_id"] == paper  # still there
        assert view["rows"][0]["paper_title"] is None  # the paper is gone
        # deleting the project cascades rows + cells
        assert wr.delete_project(conn, pid) is True
        remaining = conn.execute(metadata.tables["ma_cells"].select()).all()
    engine.dispose()
    assert remaining == []
