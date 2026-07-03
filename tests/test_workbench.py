"""inc 253 — the meta-analysis extraction workspace (SP2a-1): the repo (projects/rows/cells + templates + the convert
hook) and the endpoints (CRUD + convert + CSV/audit export). Hermetic (temp_db_url + make_engine / TestClient)."""

from __future__ import annotations

import json

import fitz
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.backend import workbench_assist as wa
from app.backend.api import create_app
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


# ---- endpoints ----------------------------------------------------------------------------------------------------


def _seed_paper(temp_db_url, title) -> int:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, title)
    engine.dispose()
    return pid


def test_project_crud_and_convert_and_export(temp_db_url):
    paper = _seed_paper(temp_db_url, "Alpha")
    client = TestClient(create_app(db_url=temp_db_url))

    # create + get
    r = client.post("/workbench/projects", json={"name": "My review", "design": "two_group_continuous"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert [f["key"] for f in r.json()["template"]] == ["n1", "m1", "s1", "n2", "m2", "s2"]
    assert client.post("/workbench/projects", json={"name": "x", "design": "bogus"}).status_code == 422

    # add a row linked to a paper; unknown paper → 404
    r = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper, "label": "Study A"})
    assert r.status_code == 200
    row_id = r.json()["rows"][0]["id"]
    assert r.json()["rows"][0]["paper_title"] == "Alpha"
    assert client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": 999999}).status_code == 404

    # fill the 6 role cells (with a provenance anchor on one); field not in template → 422
    for key, val in {"m1": "103", "s1": "5.5", "n1": "50", "m2": "100", "s2": "4.5", "n2": "50"}.items():
        body = {"value": val}
        if key == "m1":
            body |= {"page": 7, "quote": "M = 103.0"}
        assert client.put(f"/workbench/rows/{row_id}/cells/{key}", json=body).status_code == 200
    assert client.put(f"/workbench/rows/{row_id}/cells/nope", json={"value": "1"}).status_code == 422

    # convert → Hedges' g stored
    r = client.post(f"/workbench/rows/{row_id}/convert")
    assert r.status_code == 200 and r.json()["metric"] == "Hedges' g"
    assert abs(r.json()["value"] - 0.5924) < 1e-3

    # a degenerate row (blank cells) → 422
    client.post(f"/workbench/projects/{pid}/rows", json={})
    bad_row = client.get(f"/workbench/projects/{pid}").json()["rows"][1]["id"]
    assert client.post(f"/workbench/rows/{bad_row}/convert").status_code == 422

    # CSV export: header + the converted row's g/var
    csv_resp = client.get(f"/workbench/projects/{pid}/export", params={"format": "csv"})
    assert csv_resp.status_code == 200 and csv_resp.headers["content-type"].startswith("text/csv")
    lines = csv_resp.text.strip().splitlines()
    assert lines[0].startswith("row_label,N (group 1)")
    assert "Hedges' g" in lines[1]

    # audit export carries the per-cell provenance
    audit = client.get(f"/workbench/projects/{pid}/export", params={"format": "audit"}).json()
    assert audit["rows"][0]["cells"]["m1"]["page"] == 7
    assert client.get(f"/workbench/projects/{pid}/export", params={"format": "bogus"}).status_code == 422

    # editing a cell drops the stale effect size (never a silently-stale g) — checked last (it mutates the row)
    def _converted():
        return client.get(f"/workbench/projects/{pid}").json()["rows"][0]["converted"]

    assert _converted() is not None
    client.put(f"/workbench/rows/{row_id}/cells/m1", json={"value": "104"})
    assert _converted() is None


def test_template_patch_guards_role_columns(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    base = client.get(f"/workbench/projects/{pid}").json()["template"]
    # add a moderator column → OK
    good = base + [{"key": "notes", "label": "Notes", "type": "text", "role": None}]
    assert client.patch(f"/workbench/projects/{pid}", json={"template": good}).status_code == 200
    # remove a role column (the `r` spine) → 422
    without_r = [f for f in base if f["key"] != "r"]
    assert client.patch(f"/workbench/projects/{pid}", json={"template": without_r}).status_code == 422
    # a non-role column trying to claim a role → 422
    fake_role = base + [{"key": "sneaky", "label": "x", "type": "number", "role": "sneaky"}]
    assert client.patch(f"/workbench/projects/{pid}", json={"template": fake_role}).status_code == 422


def test_csv_escapes_formula_injection(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"label": "=DANGER()"}).json()["rows"][0]["id"]
    client.put(f"/workbench/rows/{row_id}/cells/r", json={"value": "0.3"})
    csv_text = client.get(f"/workbench/projects/{pid}/export", params={"format": "csv"}).text
    assert "'=DANGER()" in csv_text  # a leading = is neutralized with a prefixed '


def test_delete_project_then_404(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    assert client.delete(f"/workbench/projects/{pid}").status_code == 204
    assert client.get(f"/workbench/projects/{pid}").status_code == 404
    assert client.delete(f"/workbench/projects/{pid}").status_code == 404


# ---- SP2b: the dataset loop (convert-all) + stat-package exports ---------------------------------------------------


def _fill(client, row_id, cells):
    for k, v in cells.items():
        client.put(f"/workbench/rows/{row_id}/cells/{k}", json={"value": v})


def test_convert_all_converts_complete_leaves_incomplete_honest(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "two_group_continuous"}).json()["id"]
    good = client.post(f"/workbench/projects/{pid}/rows", json={"label": "A"}).json()["rows"][0]["id"]
    _fill(client, good, {"m1": "103", "s1": "5.5", "n1": "50", "m2": "100", "s2": "4.5", "n2": "50"})
    client.post(f"/workbench/projects/{pid}/rows", json={"label": "B"})  # left blank → un-convertible

    r = client.post(f"/workbench/projects/{pid}/convert-all")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and body["converted"] == 1
    assert [inc["label"] for inc in body["incomplete"]] == ["B"]  # reported, not fabricated
    assert set(body) == {"total", "converted", "incomplete"}  # NO pooled/summary estimate — per-study only

    by_label = {row["label"]: row for row in client.get(f"/workbench/projects/{pid}").json()["rows"]}
    assert by_label["A"]["converted"]["metric"] == "Hedges' g"
    assert by_label["B"]["converted"] is None  # honestly un-converted, never a fabricated 0
    assert client.post("/workbench/projects/999999/convert-all").status_code == 404


def test_metafor_export_yi_vi_columns_and_negative_effect(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "two_group_continuous"}).json()["id"]
    base = client.get(f"/workbench/projects/{pid}").json()["template"]
    client.patch(
        f"/workbench/projects/{pid}",
        json={"template": base + [{"key": "year", "label": "Year", "type": "text", "role": None}]},
    )
    # group 1 < group 2 → a NEGATIVE Hedges' g: it must export as a clean number, not a "'-…" formula-neutralised cell
    neg = client.post(f"/workbench/projects/{pid}/rows", json={"label": "Neg"}).json()["rows"][0]["id"]
    _fill(client, neg, {"m1": "100", "s1": "4.5", "n1": "50", "m2": "103", "s2": "5.5", "n2": "50"})
    client.put(f"/workbench/rows/{neg}/cells/year", json={"value": "2020"})
    client.post(f"/workbench/projects/{pid}/rows", json={"label": "Empty"})  # un-converted → blank yi/vi
    client.post(f"/workbench/projects/{pid}/convert-all")

    lines = client.get(f"/workbench/projects/{pid}/export", params={"format": "metafor"}).text.strip().splitlines()
    assert lines[0] == "study,yi,vi,sei,ci_lb,ci_ub,metric,Year"
    neg_line = next(ln for ln in lines if ln.startswith("Neg,"))
    assert ",-0." in neg_line and "'-0" not in neg_line  # negative yi is a clean number, not neutralised
    assert neg_line.endswith(",2020")  # the moderator column rides along for meta-regression
    empty_line = next(ln for ln in lines if ln.startswith("Empty,"))
    assert empty_line.startswith("Empty,,,")  # blank yi/vi for an un-converted row (honest coverage)


def test_revman_export_raw_study_data_by_design(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    # continuous → Mean/SD/Total per group (a negative mean must survive verbatim)
    cpid = client.post("/workbench/projects", json={"name": "C", "design": "two_group_continuous"}).json()["id"]
    crow = client.post(f"/workbench/projects/{cpid}/rows", json={"label": "S1"}).json()["rows"][0]["id"]
    _fill(client, crow, {"m1": "-2.3", "s1": "5.5", "n1": "50", "m2": "100", "s2": "4.5", "n2": "48"})
    clines = client.get(f"/workbench/projects/{cpid}/export", params={"format": "revman"}).text.strip().splitlines()
    assert clines[0] == "Study,Mean 1,SD 1,Total 1,Mean 2,SD 2,Total 2"
    assert clines[1] == "S1,-2.3,5.5,50,100,4.5,48"

    # binary → Events + group Total (= events + non-events); RevMan computes the effect itself
    bpid = client.post("/workbench/projects", json={"name": "B", "design": "binary_2x2"}).json()["id"]
    brow = client.post(f"/workbench/projects/{bpid}/rows", json={"label": "S2"}).json()["rows"][0]["id"]
    _fill(client, brow, {"a": "10", "b": "20", "c": "5", "d": "25"})
    blines = client.get(f"/workbench/projects/{bpid}/export", params={"format": "revman"}).text.strip().splitlines()
    assert blines[0] == "Study,Events 1,Total 1,Events 2,Total 2"
    assert blines[1] == "S2,10,30,5,30"  # Total1 = a+b = 30, Total2 = c+d = 30

    # correlation → RevMan generic-IV Effect (Fisher's z) + SE, from the converted row
    rpid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    rrow = client.post(f"/workbench/projects/{rpid}/rows", json={"label": "S3"}).json()["rows"][0]["id"]
    _fill(client, rrow, {"r": "0.5", "n": "28"})
    client.post(f"/workbench/projects/{rpid}/convert-all")
    rlines = client.get(f"/workbench/projects/{rpid}/export", params={"format": "revman"}).text.strip().splitlines()
    assert rlines[0] == "Study,Effect,SE"
    assert rlines[1].startswith("S3,0.5493") and rlines[1].endswith(",0.2")  # z=atanh(.5); SE=√(1/25)=0.2


# ---- SP2b funnel: proposals (candidates) + the origin audit column ------------------------------------------------


def test_proposals_replace_get_delete_and_view(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = wr.create_project(conn, name="R", design="correlation")
        row = wr.add_row(conn, pid, label="S")
        wr.replace_row_proposals(
            conn,
            row,
            [
                {
                    "field_key": "r",
                    "value": "0.42",
                    "quote": "r = .42",
                    "page": 3,
                    "bbox_json": '[{"page":3,"x0":1,"y0":2,"x1":3,"y1":4}]',
                    "anchor_state": "exact",
                    "reason": None,
                }
            ],
        )
        view = wr.project_view(conn, pid)
        props = view["rows"][0]["proposals"]
        got = wr.get_proposal(conn, props[0]["id"])
        # re-drafting replaces the row's live proposals
        wr.replace_row_proposals(
            conn,
            row,
            [
                {
                    "field_key": "n",
                    "value": "60",
                    "quote": None,
                    "page": None,
                    "bbox_json": None,
                    "anchor_state": "unanchored",
                    "reason": "quote_not_found",
                }
            ],
        )
        after = wr.proposals_for_row(conn, row)
        deleted = wr.delete_proposal(conn, after[0]["id"])
        empty = wr.proposals_for_row(conn, row)
    engine.dispose()
    assert props[0]["field_key"] == "r" and props[0]["anchor_state"] == "exact"
    assert got["row_id"] == row and got["value"] == "0.42" and got["page"] == 3
    assert [p["field_key"] for p in after] == ["n"]  # the earlier `r` proposal was replaced
    assert deleted is True and empty == []


def test_upsert_cell_origin_surfaces_in_view(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = wr.create_project(conn, name="R", design="correlation")
        row = wr.add_row(conn, pid, label="S")
        wr.upsert_cell(conn, row, "r", value="0.5", origin="assisted")
        wr.upsert_cell(conn, row, "n", value="60")  # manual → origin NULL
        view = wr.project_view(conn, pid)
    engine.dispose()
    cells = view["rows"][0]["cells"]
    assert cells["r"]["origin"] == "assisted"
    assert cells["n"]["origin"] is None


# ---- SP2b funnel: propose / accept / reject endpoints (candidate-safety + the egress gate) -------------------------


class _FakeAssistant:
    """A canned assistant injected at the create_app seam — returns already-parsed proposals; no network."""

    def __init__(self, proposals):
        self._proposals = proposals

    def propose(self, *, text, fields):
        return list(self._proposals)


def _pdf_with(tmp_path, text) -> str:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    path = tmp_path / "study.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_propose_accept_reject_candidate_safety(temp_db_url, tmp_path, monkeypatch):
    import app.backend.api.routers.workbench as wbmod

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))  # isolate app-settings
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")  # so the gate delegates to the fake
    paper = _seed_paper(temp_db_url, "Alpha")
    pdf = _pdf_with(tmp_path, "The correlation was r = 0.42 across the full sample.")
    fake = _FakeAssistant(
        [{"field_key": "r", "value": "0.42", "quote": "The correlation was r = 0.42 across the full sample", "page": 9}]
    )
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(
        wbmod,
        "get_chunks_for_paper",
        lambda conn, pid, **k: [
            {"page_start": 1, "page_end": 1, "text": "The correlation was r = 0.42 across the full sample."}
        ],
    )
    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=fake))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper, "label": "A"}).json()["rows"][0][
        "id"
    ]

    # propose → an amber candidate (only `r`; the fake omits `n`), located EXACT (value literal in the quote)
    r = client.post(f"/workbench/rows/{row_id}/propose")
    assert r.status_code == 200
    props = r.json()["proposals"]
    assert [p["field_key"] for p in props] == ["r"]
    assert props[0]["anchor_state"] == "exact" and props[0]["bbox_json"]

    # candidate-safety: NOTHING is in the trusted cell / convert / export yet
    view = client.get(f"/workbench/projects/{pid}").json()
    assert "r" not in view["rows"][0]["cells"]
    assert "0.42" not in client.get(f"/workbench/projects/{pid}/export", params={"format": "csv"}).text

    # accept → the value is promoted with exact provenance + origin=assisted; the proposal is consumed
    prop_id = props[0]["id"]
    acc = client.post(f"/workbench/proposals/{prop_id}/accept", json={})
    assert acc.status_code == 200
    cells = next(rw for rw in acc.json()["rows"] if rw["id"] == row_id)["cells"]
    assert cells["r"]["value"] == "0.42" and cells["r"]["origin"] == "assisted" and cells["r"]["bbox_json"]
    # now it IS a fact → it appears in the export; the proposal is gone
    assert "0.42" in client.get(f"/workbench/projects/{pid}/export", params={"format": "csv"}).text
    after = next(rw for rw in client.get(f"/workbench/projects/{pid}").json()["rows"] if rw["id"] == row_id)
    assert after["proposals"] == []

    # a 404 on an unknown proposal (accept + reject)
    assert client.post("/workbench/proposals/999999/accept", json={}).status_code == 404
    assert client.post("/workbench/proposals/999999/reject").status_code == 404


def test_propose_edit_before_accept_drops_exact_to_region(temp_db_url, tmp_path, monkeypatch):
    import app.backend.api.routers.workbench as wbmod

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    paper = _seed_paper(temp_db_url, "Gamma")
    pdf = _pdf_with(tmp_path, "The correlation was r = 0.42 across the full sample.")
    fake = _FakeAssistant(
        [{"field_key": "r", "value": "0.42", "quote": "The correlation was r = 0.42 across the full sample", "page": 1}]
    )
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(
        wbmod, "get_chunks_for_paper", lambda conn, pid, **k: [{"page_start": 1, "page_end": 1, "text": "r = 0.42"}]
    )
    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=fake))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    prop = client.post(f"/workbench/rows/{row_id}/propose").json()["proposals"][0]
    assert prop["anchor_state"] == "exact"
    # edit-before-accept: an overridden value can't claim the exact bbox → precision honestly falls back to region
    acc = client.post(f"/workbench/proposals/{prop['id']}/accept", json={"value": "0.40"})
    cell = next(rw for rw in acc.json()["rows"] if rw["id"] == row_id)["cells"]["r"]
    assert cell["value"] == "0.40" and cell["bbox_json"] is None and cell["origin"] == "assisted"


def test_propose_egress_off_returns_403(temp_db_url, tmp_path, monkeypatch):
    import app.backend.api.routers.workbench as wbmod

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)  # egress OFF, default gemini provider
    paper = _seed_paper(temp_db_url, "Beta")
    pdf = _pdf_with(tmp_path, "r = 0.5 was found.")
    fake = _FakeAssistant([{"field_key": "r", "value": "0.5", "quote": "r = 0.5 was found", "page": 1}])
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(
        wbmod,
        "get_chunks_for_paper",
        lambda conn, pid, **k: [{"page_start": 1, "page_end": 1, "text": "r = 0.5 was found."}],
    )
    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=fake))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    assert client.post(f"/workbench/rows/{row_id}/propose").status_code == 403


def test_propose_requires_linked_paper(temp_db_url, monkeypatch, tmp_path):
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    client = TestClient(create_app(db_url=temp_db_url))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"label": "external"}).json()["rows"][0]["id"]
    assert client.post(f"/workbench/rows/{row_id}/propose").status_code == 422  # no linked paper
    assert client.post("/workbench/rows/999999/propose").status_code == 404


def test_propose_short_circuits_no_model_call_when_all_fields_filled(temp_db_url, tmp_path, monkeypatch):
    """Empty-fields short-circuit: when ALL structured cells are already filled, propose returns 200 + empty
    proposals WITHOUT ever calling the model. Egress is enabled and PDF/text are stubbed so the bomb WOULD fire
    (AssertionError) if the short-circuit ever stopped — proving no egress occurs when nothing is draftable."""
    import app.backend.api.routers.workbench as wbmod

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    paper = _seed_paper(temp_db_url, "Delta")
    pdf = _pdf_with(tmp_path, "any text here")
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(
        wbmod,
        "get_chunks_for_paper",
        lambda conn, pid, **k: [{"page_start": 1, "page_end": 1, "text": "any text here"}],
    )

    class _BombAssistant:
        def propose(self, *, text, fields):
            raise AssertionError("model must not be called")

    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=_BombAssistant()))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    # Fill ALL structured fields (r + n for the correlation design) → proposable_fields returns []
    client.put(f"/workbench/rows/{row_id}/cells/r", json={"value": "0.42"})
    client.put(f"/workbench/rows/{row_id}/cells/n", json={"value": "60"})

    r = client.post(f"/workbench/rows/{row_id}/propose")
    assert r.status_code == 200
    body = r.json()
    assert body["proposals"] == []
    assert body["truncated"] is False


def test_propose_no_pdf_returns_422(temp_db_url, tmp_path, monkeypatch):
    """No local PDF (primary_pdf_path returns None) → 422. The row has an empty structured field so the
    short-circuit does not fire and the endpoint reaches the PDF-path check."""
    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    paper = _seed_paper(temp_db_url, "Epsilon")
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: None)
    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=_FakeAssistant([])))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    # Both structured fields are empty → past the short-circuit; no PDF → 422
    assert client.post(f"/workbench/rows/{row_id}/propose").status_code == 422


def test_propose_no_extracted_text_returns_422(temp_db_url, tmp_path, monkeypatch):
    """No extracted text (empty chunk list → page_tagged_text returns '') → 422."""
    import app.backend.api.routers.workbench as wbmod

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    paper = _seed_paper(temp_db_url, "Zeta")
    pdf = _pdf_with(tmp_path, "any text here")
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(wbmod, "get_chunks_for_paper", lambda conn, pid, **k: [])  # empty → "" → 422
    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=_FakeAssistant([])))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    # Both structured fields are empty → past the short-circuit; PDF present; chunks empty → 422
    assert client.post(f"/workbench/rows/{row_id}/propose").status_code == 422


def test_propose_provider_failure_returns_502(temp_db_url, tmp_path, monkeypatch):
    """A ProviderError raised by the assistant is mapped to 502 Bad Gateway."""
    import app.backend.api.routers.workbench as wbmod
    from app.backend.llm.providers import ProviderError

    monkeypatch.setenv("CALLOSUM_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("CALLOSUM_ALLOW_DATA_EGRESS", "1")
    paper = _seed_paper(temp_db_url, "Eta")
    pdf = _pdf_with(tmp_path, "some extracted text on the page")
    monkeypatch.setattr(wa, "primary_pdf_path", lambda conn, pid: __import__("pathlib").Path(pdf))
    monkeypatch.setattr(
        wbmod,
        "get_chunks_for_paper",
        lambda conn, pid, **k: [{"page_start": 1, "page_end": 1, "text": "some extracted text on the page"}],
    )

    class _ProviderFailAssistant:
        def propose(self, *, text, fields):
            raise ProviderError("upstream timeout")

    client = TestClient(create_app(db_url=temp_db_url, extraction_assistant=_ProviderFailAssistant()))
    pid = client.post("/workbench/projects", json={"name": "R", "design": "correlation"}).json()["id"]
    row_id = client.post(f"/workbench/projects/{pid}/rows", json={"paper_id": paper}).json()["rows"][0]["id"]
    # Both structured fields are empty → past the short-circuit; provider fails → 502
    assert client.post(f"/workbench/rows/{row_id}/propose").status_code == 502
