from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.clustering.tag_suggestion import suggest_tags_for_paper
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, soft_delete_paper


def test_suggest_ranks_distinctive_excludes_existing_and_handles_trashed(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        target = create_paper(
            conn,
            title="Photosynthesis Mechanisms",
            abstract="chloroplast photosynthesis converts photosynthesis photosynthesis",
            csl_json={"title": "Photosynthesis Mechanisms"},
        )
        create_paper(conn, title="Light Optics", abstract="light refraction light", csl_json={"title": "Light Optics"})
        create_paper(conn, title="Light Speed", abstract="light travels light", csl_json={"title": "Light Speed"})

        sugg = suggest_tags_for_paper(conn, target, existing_tag_names=[])
        assert sugg[0] == "photosynthesis"  # most distinctive + frequent
        assert "chloroplast" in sugg and "mechanisms" in sugg
        assert "light" not in sugg  # not in the target → never a candidate

        excluded = suggest_tags_for_paper(conn, target, existing_tag_names=["Photosynthesis"])  # case-insensitive
        assert "photosynthesis" not in excluded

        soft_delete_paper(conn, target)
        assert suggest_tags_for_paper(conn, target, existing_tag_names=[]) == []  # trashed
        assert suggest_tags_for_paper(conn, 999999, existing_tag_names=[]) == []  # missing
    engine.dispose()


def test_idf_demotes_a_common_term_below_a_rare_one(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        target = create_paper(conn, title="Tg", abstract="alpha alpha beta beta", csl_json={"title": "Tg"})
        create_paper(conn, title="Px", abstract="beta gamma", csl_json={"title": "Px"})
        create_paper(conn, title="Py", abstract="beta delta", csl_json={"title": "Py"})
        sugg = suggest_tags_for_paper(conn, target, existing_tag_names=[])
        # alpha (df=1) and beta (df=3) both have tf=2 in the target → idf ranks the rarer term higher
        assert sugg.index("alpha") < sugg.index("beta")
    engine.dispose()


def test_suggested_tags_endpoint_excludes_added_and_404s(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(
            conn,
            title="Quantum Entanglement",
            abstract="quantum entanglement qubits quantum",
            csl_json={"title": "Quantum Entanglement"},
        )
        create_paper(conn, title="Classical", abstract="classical mechanics", csl_json={"title": "Classical"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    sugg = client.get(f"/papers/{a}/suggested-tags")
    assert sugg.status_code == 200 and "quantum" in sugg.json()["suggestions"]
    client.post(f"/papers/{a}/tags", json={"name": "quantum"})  # add it →
    assert "quantum" not in client.get(f"/papers/{a}/suggested-tags").json()["suggestions"]  # no longer suggested
    assert client.get("/papers/999999/suggested-tags").status_code == 404
