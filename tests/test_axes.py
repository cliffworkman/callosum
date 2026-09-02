from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.backend.api import create_app
from app.backend.api.routers.axes import SUPERVISED_AXIS_CONFIG
from app.backend.clustering.axis_scoring import AxisScoringConfig, natural_break_assigned_ids
from app.backend.embeddings.models import DEFAULT_NORMALIZATION, normalize_text
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import cluster_nodes
from integrations.gemini import DataEgressDisabledError
from tests.api_helpers import _seed_library


@dataclass(frozen=True)
class WeakFakeModel:
    """Maps every paper to a low (<0.2) cosine similarity vs the axis, so nothing clears the floor."""

    name: str = "weak-axis-embedding"
    version: str = "v1"
    dimension: int = 2
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "weak" in normalize_text(t, self.normalization) else [0.15, 0.988] for t in texts]


def _hash_vec(text: str) -> list[float]:
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [float(b) - 128.0 for b in digest[:8]]


@dataclass(frozen=True)
class PunctSensitiveModel:
    """A deterministic vector from the EXACT normalized string — so 'resting-state' and
    'resting state' embed DIFFERENTLY unless the axis text is punctuation-normalized first.
    Identical strings embed identically (cosine 1.0), so a paper titled exactly like the cleaned
    axis is a guaranteed match."""

    name: str = "punct-sensitive"
    version: str = "v1"
    dimension: int = 8
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_hash_vec(normalize_text(t, self.normalization)) for t in texts]


# A 2-D fake embedding model that maps text → vectors with controlled cosine similarity to the
# axis vector, so scoring lands a clearly-high paper "assigned", a borderline one "uncertain",
# and a far one "below-threshold" (not stored). Keyed on distinctive words (post-normalize).
@dataclass(frozen=True)
class AxisFakeEmbeddingModel:
    name: str = "fake-axis-embedding"
    version: str = "v1"
    dimension: int = 2
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        return [_axis_vec(normalize_text(text, self.normalization)) for text in texts]


def _axis_vec(text: str) -> list[float]:
    if "anomalous" in text:
        return [1.0, 0.0]  # axis + high paper → cosine 1.0 → assigned (>= 0.35 cutoff)
    if "borderline" in text:
        return [0.3, 0.9539]  # cosine 0.30 with [1,0] → uncertain band [0.20, 0.35)
    return [0.0, 1.0]  # far → cosine 0.0 → below-threshold (not stored)


@dataclass(frozen=True)
class RaisingEmbeddingModel:
    name: str = "raising-embedding"
    version: str = "v1"
    dimension: int = 2
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding model unavailable")


@dataclass(frozen=True)
class FakeTermSuggester:
    terms: tuple = ("rsfmri", "functional connectivity", "default mode network")

    def suggest(self, *, label: str, description: str | None) -> list[str]:
        return list(self.terms)


def _axes_app(db_url: str, *, model=None, suggester=None, cluster_labeler=None):
    return create_app(
        db_url=db_url,
        embedding_model=model if model is not None else AxisFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        axis_term_suggester=suggester,
        axis_cluster_labeler=cluster_labeler,
    )


@dataclass(frozen=True)
class ClusterFakeModel:
    """Maps a paper/axis to one of three well-separated unit vectors by keyword, so clustering yields
    clean, predictable groups (alpha / beta / other)."""

    name: str = "cluster-fake"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            norm = normalize_text(text, self.normalization)
            if "alpha" in norm:
                out.append([1.0, 0.0, 0.0])
            elif "beta" in norm:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


@dataclass(frozen=True)
class FakeClusterLabeler:
    def label(self, *, titles, terms):
        return {"label": "Gemini Label", "terms": ["polished", "terms"]}


@dataclass(frozen=True)
class RaisingClusterLabeler:
    def label(self, *, titles, terms):
        raise DataEgressDisabledError("egress off")


def _seed_cluster_papers(db_url: str) -> None:
    engine = make_engine(db_url)
    with engine.begin() as conn:
        for text in (
            "alpha cortex mapping",
            "alpha cortex rhythms",
            "alpha cortex dynamics",
            "beta synapse plasticity",
            "beta synapse signaling",
            "beta synapse pruning",
        ):
            create_paper(
                conn,
                title=text.title(),
                abstract=text,
                csl_json={"type": "article-journal", "title": text.title()},
                processing_tier="fully-chunked",
            )
    engine.dispose()


def _run_suggest(client: TestClient) -> dict:
    started = client.post("/axes/suggest")
    assert started.status_code == 202, started.text
    return client.get(f"/axes/suggest/{started.json()['job_id']}").json()


def _seed_axis_papers(db_url: str) -> dict[str, int]:
    engine = make_engine(db_url)
    ids: dict[str, int] = {}
    with engine.begin() as conn:
        ids["high"] = create_paper(
            conn,
            title="Anomalous facial features and social bias",
            abstract="A study of anomalous appearance and negative evaluation.",
            csl_json={"type": "article-journal", "title": "Anomalous facial features and social bias"},
            processing_tier="fully-chunked",
        )
        ids["borderline"] = create_paper(
            conn,
            title="Borderline social perception",
            abstract="A borderline construct in social cognition.",
            csl_json={"type": "article-journal", "title": "Borderline social perception"},
            processing_tier="fully-chunked",
        )
        ids["far"] = create_paper(
            conn,
            title="Orchard irrigation methods",
            abstract="Banana orchard farming and irrigation.",
            csl_json={"type": "article-journal", "title": "Orchard irrigation methods"},
            processing_tier="fully-chunked",
        )
    engine.dispose()
    return ids


def _papers_by_id(clusters: list[dict]) -> dict[int, dict]:
    return {paper["id"]: paper for node in clusters for paper in node["papers"]}


def _run_score(client: TestClient, axis_id: int) -> dict:
    started = client.post(f"/axes/{axis_id}/score")
    assert started.status_code == 202, started.text
    return client.get(f"/axes/score/{started.json()['job_id']}").json()


def test_axes_and_clusters_return_sidebar_tree_data(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    axes_response = client.get("/axes")
    clusters_response = client.get(f"/axes/{seeded['axis_id']}/clusters")
    missing = client.get("/axes/999999/clusters")

    assert axes_response.status_code == 200
    listed_axes = axes_response.json()
    assert len(listed_axes) == 1
    created_at = listed_axes[0].pop("created_at")
    assert isinstance(created_at, str) and created_at  # server-defaulted timestamp, for sort-by-recency
    assert listed_axes[0].pop("scoring_gain") == 0.35  # never-scored axis → the default cutoff
    assert listed_axes[0].pop("kind") == "standard"  # inc 78: default axis kind
    assert listed_axes[0].pop("uncertain_count") == 0  # inc 79: the seeded paper (0.91) is assigned, not uncertain
    assert listed_axes == [
        {
            "id": seeded["axis_id"],
            "label": "Facial Anomalies",
            "description": "User-defined axis",
            "scored": False,  # seeded directly without an axis embedding
            "stale": False,
            "assignment_count": 1,
        }
    ]
    assert clusters_response.status_code == 200
    clusters = clusters_response.json()
    assert clusters[0]["label"] == "Facial cluster"
    assert clusters[0]["papers"] == [
        {
            "id": seeded["facial_paper_id"],
            "title": "Facial Anomaly Perception",
            "confidence": 0.91,
            "status": "assigned",  # 0.91 ≥ 0.7
            "manual": False,
            "starred": False,  # inc 84: standard axis → never starred
            "domain": None,  # inc 118: standard axis → no research-domain label
            "position": None,  # inc 211 (A7): NULL on a keyword axis (order stays papers.id)
        }
    ]
    assert missing.status_code == 404


def test_axis_create_validation(temp_db_url: str) -> None:
    client = TestClient(_axes_app(temp_db_url))
    assert client.post("/axes", json={}).status_code == 422  # missing label
    assert client.post("/axes", json={"label": ""}).status_code == 422  # empty label
    assert client.post("/axes", json={"label": "   "}).status_code == 422  # whitespace-only
    assert client.post("/axes", json={"label": "x" * 201}).status_code == 422  # over cap
    created = client.post("/axes", json={"label": "Valid axis", "description": "ok"})
    assert created.status_code == 201
    assert created.json()["scored"] is False and created.json()["assignment_count"] == 0


def test_axis_score_produces_three_honest_tiers(temp_db_url: str) -> None:
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis = client.post(
        "/axes", json={"label": "Anomalous appearance bias", "description": "negative evaluation of anomalous faces"}
    ).json()
    axis_id = axis["id"]
    assert (axis["scored"], axis["stale"], axis["assignment_count"]) == (False, False, 0)

    result = _run_score(client, axis_id)
    assert result["status"] == "done", result
    assert result["assigned_count"] == 1 and result["uncertain_count"] == 1
    assert result["cluster_node_id"] is not None

    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["high"]]["status"] == "assigned" and papers[ids["high"]]["manual"] is False
    assert papers[ids["high"]]["confidence"] >= 0.35  # at/above the default cutoff → assigned
    assert papers[ids["borderline"]]["status"] == "uncertain"
    assert 0.20 <= papers[ids["borderline"]]["confidence"] < 0.35  # in the uncertain band
    assert ids["far"] not in papers  # below-threshold is never stored

    listed = {a["id"]: a for a in client.get("/axes").json()}
    assert listed[axis_id]["scored"] is True and listed[axis_id]["stale"] is False
    assert listed[axis_id]["assignment_count"] == 2
    assert listed[axis_id]["uncertain_count"] == 1  # inc 79: the borderline (0.30 < 0.35) is the lone uncertain


def test_axis_cutoff_is_adjustable_and_persists(temp_db_url: str) -> None:
    # The assigned/uncertain cut is a per-axis "gain": default 0.35, overridable per re-score and saved.
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Anomalous", "description": "anomalous faces"}).json()["id"]

    assert _run_score(client, axis_id)["status"] == "done"  # default cutoff 0.35
    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["high"]]["status"] == "assigned"  # 1.00 >= 0.35
    assert papers[ids["borderline"]]["status"] == "uncertain"  # 0.30 in [0.20, 0.35)
    assert {a["id"]: a for a in client.get("/axes").json()}[axis_id]["scoring_gain"] == 0.35

    # Re-score at a lower cutoff → the borderline paper (0.30) is now ASSIGNED; the gain persists.
    started = client.post(f"/axes/{axis_id}/score", json={"gain": 0.25})
    assert started.status_code == 202
    assert client.get(f"/axes/score/{started.json()['job_id']}").json()["status"] == "done"
    papers2 = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers2[ids["borderline"]]["status"] == "assigned"  # lower cutoff promotes it
    assert {a["id"]: a for a in client.get("/axes").json()}[axis_id]["scoring_gain"] == 0.25


def test_confidence_rounded_to_displayed_two_decimals() -> None:
    # The cutoff/tier must act on the same 2-decimal value the UI shows (toFixed(2)), so a paper displayed
    # as "0.35" is never tagged uncertain because its raw score was 0.349.
    from app.backend.clustering.axis_scoring import _confidence_from_cosine_distance

    assert _confidence_from_cosine_distance(0.651) == 0.35  # raw 0.349 → 0.35 (shown + scored)
    assert _confidence_from_cosine_distance(0.602) == 0.40  # raw 0.398 → 0.40
    assert _confidence_from_cosine_distance(0.0) == 1.0
    assert _confidence_from_cosine_distance(1.5) == 0.0  # clamped


def test_axis_edit_description_marks_stale(temp_db_url: str) -> None:
    _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Anomalous", "description": "anomalous faces"}).json()["id"]
    assert _run_score(client, axis_id)["status"] == "done"

    listed = {a["id"]: a for a in client.get("/axes").json()}
    assert listed[axis_id]["scored"] is True and listed[axis_id]["stale"] is False

    patched = client.patch(f"/axes/{axis_id}", json={"description": "an entirely different construct"})
    assert patched.status_code == 200
    assert patched.json()["stale"] is True  # text changed → assignments now stale
    assert {a["id"]: a for a in client.get("/axes").json()}[axis_id]["stale"] is True


def test_axis_rescore_replaces_scored_and_preserves_manual_add(temp_db_url: str) -> None:
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Anomalous appearance", "description": "anomalous faces"}).json()[
        "id"
    ]

    # Manually add the FAR paper (one the scorer will never assign) — a human override.
    added = client.post(f"/axes/{axis_id}/papers", json={"paper_id": ids["far"]})
    assert added.status_code == 201 and added.json()["manual"] is True and added.json()["confidence"] is None

    assert _run_score(client, axis_id)["status"] == "done"
    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["high"]]["status"] == "assigned"
    assert papers[ids["borderline"]]["status"] == "uncertain"
    assert papers[ids["far"]]["manual"] is True and papers[ids["far"]]["confidence"] is None  # manual survived re-score

    # Re-score again: assignments are replaced, not duplicated; manual add still preserved.
    assert _run_score(client, axis_id)["status"] == "done"
    after = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert sorted(after) == sorted([ids["high"], ids["borderline"], ids["far"]])
    assert len(after) == 3  # no duplicate rows


def test_axis_manual_add_and_remove_are_distinguishable(temp_db_url: str) -> None:
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Lens", "description": "a lens"}).json()["id"]

    added = client.post(f"/axes/{axis_id}/papers", json={"paper_id": ids["high"]})
    assert added.status_code == 201
    assert added.json()["status"] == "manual" and added.json()["confidence"] is None and added.json()["manual"] is True

    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["high"]]["manual"] is True

    assert client.delete(f"/axes/{axis_id}/papers/{ids['high']}").status_code == 204
    assert ids["high"] not in _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())

    assert client.delete(f"/axes/{axis_id}/papers/{ids['high']}").status_code == 404  # already gone
    assert client.post(f"/axes/{axis_id}/papers", json={"paper_id": 999999}).status_code == 404  # unknown paper
    assert client.post("/axes/999999/papers", json={"paper_id": ids["high"]}).status_code == 404  # unknown axis


def test_confirm_uncertain_paper_promotes_it_to_manual(temp_db_url: str) -> None:
    # B: "✓ confirm" reuses POST /axes/{id}/papers, which now UPSERTS a scored row to confidence=NULL
    # (a human override) — so an UNCERTAIN scored paper becomes a manual assignment.
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Anomalous", "description": "anomalous faces"}).json()["id"]
    assert _run_score(client, axis_id)["status"] == "done"
    assert _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())[ids["borderline"]]["status"] == "uncertain"

    assert client.post(f"/axes/{axis_id}/papers", json={"paper_id": ids["borderline"]}).status_code == 201
    after = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert after[ids["borderline"]]["manual"] is True and after[ids["borderline"]]["confidence"] is None
    assert after[ids["borderline"]]["status"] == "manual"


def test_confirmed_uncertain_paper_survives_rescore(temp_db_url: str) -> None:
    # The confirm must be durable: a manual pick that would otherwise re-score above the floor must
    # stay manual after a re-score (restore_manual_assignments now forces NULL even when present).
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "Anomalous", "description": "anomalous faces"}).json()["id"]
    assert _run_score(client, axis_id)["status"] == "done"
    assert client.post(f"/axes/{axis_id}/papers", json={"paper_id": ids["borderline"]}).status_code == 201

    assert _run_score(client, axis_id)["status"] == "done"  # re-score would normally re-tag it uncertain
    after = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert after[ids["borderline"]]["manual"] is True and after[ids["borderline"]]["confidence"] is None
    assert after[ids["high"]]["status"] == "assigned"  # scored papers still recompute normally


def test_axis_delete_cascades_only_its_own_tree(temp_db_url: str) -> None:
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    a1 = client.post("/axes", json={"label": "Anomalous one", "description": "anomalous faces"}).json()["id"]
    a2 = client.post("/axes", json={"label": "Other lens", "description": "unrelated"}).json()["id"]
    client.post(f"/axes/{a1}/papers", json={"paper_id": ids["high"]})
    client.post(f"/axes/{a2}/papers", json={"paper_id": ids["borderline"]})

    assert client.delete(f"/axes/{a1}").status_code == 204

    listed = {a["id"] for a in client.get("/axes").json()}
    assert a1 not in listed and a2 in listed
    assert any(p["id"] == ids["borderline"] for p in _papers_by_id(client.get(f"/axes/{a2}/clusters").json()).values())
    assert client.get(f"/papers/{ids['high']}").status_code == 200  # papers untouched
    assert client.delete(f"/axes/{a1}").status_code == 404  # already gone

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        orphan_nodes = conn.execute(
            select(func.count()).select_from(cluster_nodes).where(cluster_nodes.c.axis_id == a1)
        ).scalar_one()
    engine.dispose()
    assert orphan_nodes == 0  # the deleted axis's nodes cascaded away


def test_axis_score_job_fails_gracefully_when_model_unavailable(temp_db_url: str) -> None:
    _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=RaisingEmbeddingModel()))
    axis_id = client.post("/axes", json={"label": "Lens", "description": "a lens"}).json()["id"]

    started = client.post(f"/axes/{axis_id}/score")
    assert started.status_code == 202
    result = client.get(f"/axes/score/{started.json()['job_id']}").json()
    assert result["status"] == "error"
    assert result["detail"]  # the failure reason is surfaced, not a 500

    assert client.get("/axes/score/not-a-real-job").status_code == 404


def test_strip_punctuation_makes_phrasings_equivalent() -> None:
    from app.backend.embeddings.models import strip_punctuation

    assert strip_punctuation("anomalous-is-bad") == strip_punctuation("anomalous is bad") == "anomalous is bad"
    assert strip_punctuation("resting-state") == strip_punctuation("resting state") == "resting state"
    assert strip_punctuation("resting_state/v2") == "resting state v2"
    assert strip_punctuation("5-HT receptors") == "5 HT receptors"  # digits + accents kept


def test_axes_differing_only_in_punctuation_score_identically(temp_db_url: str) -> None:
    # A paper named exactly like the cleaned axis is a guaranteed match under PunctSensitiveModel.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        p1 = create_paper(
            conn,
            title="resting state",
            csl_json={"type": "article-journal", "title": "resting state"},
            processing_tier="fully-chunked",
        )
        create_paper(
            conn,
            title="totally different subject matter",
            csl_json={"type": "article-journal", "title": "totally different subject matter"},
            processing_tier="fully-chunked",
        )
    engine.dispose()
    client = TestClient(_axes_app(temp_db_url, model=PunctSensitiveModel()))

    a1 = client.post("/axes", json={"label": "resting-state"}).json()["id"]
    a2 = client.post("/axes", json={"label": "resting state"}).json()["id"]
    assert _run_score(client, a1)["status"] == "done"
    assert _run_score(client, a2)["status"] == "done"

    def flat(data):
        return sorted((p["id"], p["status"], round(p["confidence"], 6)) for node in data for p in node["papers"])

    rows_a1 = flat(client.get(f"/axes/{a1}/clusters").json())
    rows_a2 = flat(client.get(f"/axes/{a2}/clusters").json())
    assert rows_a1 == rows_a2  # punctuation-variant axes → identical results
    assert any(pid == p1 and status == "assigned" for pid, status, _ in rows_a1)  # the matching paper is assigned


def test_suggest_terms_returns_curated_list(temp_db_url: str) -> None:
    client = TestClient(_axes_app(temp_db_url, suggester=FakeTermSuggester()))
    r = client.post("/axes/suggest-terms", json={"label": "resting state", "description": "rs-fMRI connectivity"})
    assert r.status_code == 200
    assert r.json()["terms"] == ["rsfmri", "functional connectivity", "default mode network"]
    assert client.post("/axes/suggest-terms", json={"label": ""}).status_code == 422  # empty label


def test_suggest_terms_egress_off_returns_503(temp_db_url: str, monkeypatch) -> None:
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(_axes_app(temp_db_url))  # no injected suggester → builds Gemini from env (egress off)
    r = client.post("/axes/suggest-terms", json={"label": "resting state"})
    assert r.status_code == 503
    assert "egress" in r.json()["detail"].lower()  # graceful, hermetic (no network touched)


def test_parse_terms_dedupes_caps_and_drops_echoes() -> None:
    import json as _json

    from integrations.gemini.axis_terms import MAX_TERM_LEN, MAX_TERMS, _parse_terms

    raw = _json.dumps(["rsfmri", "RSFMRI", "resting", "", " ", "y" * (MAX_TERM_LEN + 1)] + [f"t{i}" for i in range(20)])
    terms = _parse_terms(raw, label="resting state", description="")
    assert "resting" not in [t.lower() for t in terms]  # echoes of the label's words dropped
    assert [t.lower() for t in terms].count("rsfmri") == 1  # case-insensitive dedupe
    assert all(0 < len(t) <= MAX_TERM_LEN for t in terms)  # empties + over-long dropped
    assert len(terms) <= MAX_TERMS  # capped
    assert _parse_terms("not json at all", label="x", description=None) == []  # malformed → []


# ── suggest optimal axes (inc 52) ────────────────────────────────────────────


def test_suggest_axes_returns_diverse_clusters(temp_db_url: str) -> None:
    _seed_cluster_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel()))

    result = _run_suggest(client)

    assert result["status"] == "done", result
    suggestions = result["suggestions"]
    assert len(suggestions) == 2  # two clean, well-separated clusters
    for s in suggestions:
        assert s["label"] and s["terms"] and len(s["paper_ids"]) >= 2 and s["paper_titles"]


def test_suggest_axes_skips_themes_existing_axes_cover(temp_db_url: str) -> None:
    _seed_cluster_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel()))
    client.post("/axes", json={"label": "Alpha", "description": "alpha cortex"})  # already covers the alpha theme

    labels = [s["label"].lower() for s in _run_suggest(client)["suggestions"]]

    assert not any("alpha" in label for label in labels)  # covered → not re-suggested (novelty filter)
    assert any("beta" in label for label in labels)  # the uncovered theme still surfaces


def test_suggest_axes_uses_injected_gemini_labeler(temp_db_url: str) -> None:
    _seed_cluster_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel(), cluster_labeler=FakeClusterLabeler()))

    suggestions = _run_suggest(client)["suggestions"]

    assert suggestions and all(s["label"] == "Gemini Label" for s in suggestions)  # labeler polish applied


def test_suggest_axes_falls_back_to_local_when_egress_off(temp_db_url: str) -> None:
    _seed_cluster_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel(), cluster_labeler=RaisingClusterLabeler()))

    result = _run_suggest(client)

    assert result["status"] == "done"  # graceful — NOT error/503
    labels = [s["label"] for s in result["suggestions"]]
    assert labels and all(label and label != "Gemini Label" for label in labels)  # local labels used


def test_suggest_axes_empty_when_too_few_papers(temp_db_url: str) -> None:
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel()))  # empty library

    result = _run_suggest(client)

    assert result["status"] == "done"
    assert result["suggestions"] == []


def test_suggest_axes_falls_back_to_local_when_local_ai_not_ready(temp_db_url: str, monkeypatch) -> None:
    """A ManagedLocalTargetError resolving config for the optional labeler polish must degrade the same way
    egress-off already does (local labels, status 'done') -- not fail the WHOLE job over a step whose own
    inline comment already promises "egress-gated polish; local fallback". Confirmed this session: the job's
    single outer except Exception would otherwise swallow the raw exception as a job error, losing every
    cluster suggestion just because the optional polish step couldn't resolve a provider."""
    import app.backend.api.routers.axes as axes_mod
    from app.backend.llm.managed_local import ManagedLocalTargetError

    def _raise(app):
        raise ManagedLocalTargetError("descriptor_unreadable")

    monkeypatch.setattr(axes_mod, "resolve_llm_config", _raise)
    _seed_cluster_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel(), cluster_labeler=FakeClusterLabeler()))

    result = _run_suggest(client)

    assert result["status"] == "done"  # NOT "error" -- the whole job must not fail
    labels = [s["label"] for s in result["suggestions"]]
    assert labels and all(label and label != "Gemini Label" for label in labels)  # local labels used


def test_suggest_terms_reports_local_ai_not_ready_as_a_clean_422(temp_db_url: str, monkeypatch) -> None:
    import app.backend.api.routers.axes as axes_mod
    from app.backend.llm.managed_local import ManagedLocalTargetError

    def _raise(app):
        raise ManagedLocalTargetError("descriptor_unreadable")

    monkeypatch.setattr(axes_mod, "resolve_llm_config", _raise)
    client = TestClient(_axes_app(temp_db_url))
    r = client.post("/axes/suggest-terms", json={"label": "resting state"})
    assert r.status_code == 422
    assert "Local AI is not ready (descriptor_unreadable)" in r.json()["detail"]


# ── egress gate at the DI seam (inc 58) ──────────────────────────────────────


def test_suggest_terms_injected_suggester_blocked_when_egress_off(temp_db_url: str, monkeypatch) -> None:
    """Hole closed: an injected suggester that does NOT self-gate is blocked at the seam (503) when
    egress is disabled — it is not called. (With egress on, test_suggest_terms_returns_curated_list
    proves the injected fake IS called.)"""
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(_axes_app(temp_db_url, suggester=FakeTermSuggester()))
    r = client.post("/axes/suggest-terms", json={"label": "resting state"})
    assert r.status_code == 503
    assert "egress" in r.json()["detail"].lower()


def test_suggest_axes_injected_labeler_blocked_when_egress_off(temp_db_url: str, monkeypatch) -> None:
    """Hole closed: an injected cluster labeler that does NOT self-gate is blocked at the seam when
    egress is disabled — apply_labels catches the error and falls back to LOCAL labels, never the
    injected 'Gemini Label'. (With egress on, test_suggest_axes_uses_injected_gemini_labeler proves
    the injected fake IS called.)"""
    _seed_cluster_papers(temp_db_url)
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel(), cluster_labeler=FakeClusterLabeler()))

    result = _run_suggest(client)

    assert result["status"] == "done"  # graceful, never 503
    labels = [s["label"] for s in result["suggestions"]]
    assert labels and all(
        label and label != "Gemini Label" for label in labels
    )  # seam blocked the leaky labeler → local


def test_suggest_axes_terms_exclude_jats_markup(temp_db_url: str) -> None:
    # JATS-wrapped abstracts must not leak tag names ("jats", "italic", …) into the c-TF-IDF terms/labels.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for word in (
            "alpha cortex mapping",
            "alpha cortex rhythms",
            "alpha cortex dynamics",
            "beta synapse plasticity",
            "beta synapse signaling",
            "beta synapse pruning",
        ):
            create_paper(
                conn,
                title=word.title(),
                abstract=f"<jats:p>{word} <jats:italic>study</jats:italic>.</jats:p>",
                csl_json={"type": "article-journal", "title": word.title()},
                processing_tier="fully-chunked",
            )
    engine.dispose()
    client = TestClient(_axes_app(temp_db_url, model=ClusterFakeModel()))

    result = _run_suggest(client)

    assert result["status"] == "done" and result["suggestions"]
    for s in result["suggestions"]:
        blob = (s["label"] + " " + " ".join(s["terms"])).lower()
        assert "jats" not in blob and "italic" not in blob, s


def test_natural_break_assigned_ids_splits_at_largest_gap() -> None:
    # The natural-break utility is still a supported mode; test it with its own config (SUPERVISED is now
    # absolute since inc 45).
    cfg = AxisScoringConfig(
        assignment_mode="natural_break", uncertainty_threshold=0.2, assignment_threshold=0.2, minimum_gap=0.03
    )
    # Realistic compressed-similarity ranking: relevant cluster, a clear gap, then sub-floor noise.
    ranking = [(1, 0.37), (2, 0.34), (3, 0.27), (4, 0.27), (5, 0.18), (6, 0.18)]
    assert natural_break_assigned_ids(ranking, config=cfg) == {1, 2}  # above the 0.34→0.27 break; 0.18 sub-floor
    assert natural_break_assigned_ids([(1, 0.1), (2, 0.05)], config=cfg) == set()  # all sub-floor → none assigned
    assert natural_break_assigned_ids([(1, 0.5)], config=cfg) == {1}  # single eligible → assigned


def test_axis_score_is_never_empty_when_nothing_clears_the_floor(temp_db_url: str) -> None:
    # A weak axis where every paper scores below the floor still surfaces the closest few as
    # 'uncertain' candidates (never-empty), with nothing falsely 'assigned'.
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url, model=WeakFakeModel()))
    axis_id = client.post("/axes", json={"label": "weak lens", "description": "weak"}).json()["id"]
    result = _run_score(client, axis_id)
    assert result["status"] == "done"
    assert result["assigned_count"] == 0  # nothing cleared the floor → none assigned
    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert 1 <= len(papers) <= 3  # the closest few are shown (never empty)
    assert all(p["status"] == "uncertain" for p in papers.values())
    assert set(papers) <= set(ids.values())


def test_merge_into_survivor_unions_manual_and_deletes_sources(temp_db_url: str) -> None:
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    keep = client.post("/axes", json={"label": "Resting state", "description": "rs-fMRI"}).json()["id"]
    secondary = client.post("/axes", json={"label": "rsfmri", "description": "functional connectivity"}).json()["id"]
    bystander = client.post("/axes", json={"label": "Unrelated lens", "description": "orchards"}).json()["id"]

    # Distinct human overrides on the survivor and the folded axis — the union must survive the merge.
    assert client.post(f"/axes/{keep}/papers", json={"paper_id": ids["high"]}).status_code == 201
    assert client.post(f"/axes/{secondary}/papers", json={"paper_id": ids["borderline"]}).status_code == 201

    merged = client.post(
        "/axes/merge",
        json={
            "keep_axis_id": keep,
            "merge_axis_ids": [secondary],
            "label": "Resting state",
            # Per the user: the folded axis's label is carried as a Related term so re-scores keep
            # its vocabulary contributing (the frontend composes this; here we post it explicitly).
            "description": "rs-fMRI\n\nRelated: rsfmri, functional connectivity",
        },
    )
    assert merged.status_code == 200, merged.text
    body = merged.json()
    assert body["id"] == keep  # the survivor keeps its identity (row + created_at)
    assert body["label"] == "Resting state"
    assert "Related: rsfmri" in body["description"]
    assert body["created_at"]  # survivor's timestamp preserved

    listed = {a["id"]: a for a in client.get("/axes").json()}
    assert secondary not in listed  # folded source deleted
    assert keep in listed and bystander in listed  # survivor + untouched axis remain

    papers = _papers_by_id(client.get(f"/axes/{keep}/clusters").json())
    assert papers[ids["high"]]["manual"] is True  # survivor's own manual assignment
    assert papers[ids["borderline"]]["manual"] is True  # unioned in from the folded axis
    assert client.get(f"/papers/{ids['borderline']}").status_code == 200  # papers themselves untouched

    assert _run_score(client, keep)["status"] == "done"  # the merged survivor re-scores cleanly


def test_merge_validation(temp_db_url: str) -> None:
    client = TestClient(_axes_app(temp_db_url))
    keep = client.post("/axes", json={"label": "Keep"}).json()["id"]
    other = client.post("/axes", json={"label": "Other"}).json()["id"]

    base = {"keep_axis_id": keep, "merge_axis_ids": [other], "label": "Merged"}
    assert client.post("/axes/merge", json={**base, "label": ""}).status_code == 422  # empty label
    assert client.post("/axes/merge", json={**base, "label": "   "}).status_code == 422  # whitespace-only label
    assert client.post("/axes/merge", json={**base, "merge_axis_ids": []}).status_code == 422  # nothing to merge
    assert (
        client.post("/axes/merge", json={**base, "merge_axis_ids": [keep]}).status_code == 422
    )  # survivor in merge list
    assert client.post("/axes/merge", json={**base, "keep_axis_id": 999999}).status_code == 404  # unknown survivor
    assert client.post("/axes/merge", json={**base, "merge_axis_ids": [999999]}).status_code == 404  # unknown source
    # Both axes still exist — a rejected merge changed nothing.
    assert {a["id"] for a in client.get("/axes").json()} == {keep, other}


def test_axis_scoring_keys_on_description_not_label(temp_db_url: str) -> None:
    # Title/term decoupling (inc 44): the label is a cosmetic display name, NOT the search query —
    # only the description is embedded. Label says "anomalous" (would assign the anomalous paper if
    # embedded); description says "borderline" → scoring must follow the DESCRIPTION.
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "anomalous", "description": "borderline construct"}).json()["id"]
    assert _run_score(client, axis_id)["status"] == "done"

    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["borderline"]]["status"] == "assigned"  # the description's term drove the match
    assert papers[ids["high"]]["status"] == "uncertain"  # the label's "anomalous" did NOT dominate


def test_axis_freshness_survives_text_revisiting_a_prior_scored_version(temp_db_url: str) -> None:
    # Regression: scoring text A, then B, then back to A leaves a stale B-embedding with a HIGHER id than
    # the A-embedding that matches the current text. Staleness must check ALL embeddings, not newest-by-id
    # (else the axis reads "re-score" forever even though it was just scored at its current text).
    from app.backend.clustering.axis_assignments import axis_score_state
    from app.backend.clustering.axis_scoring import create_axis, score_axis, update_axis

    _seed_axis_papers(temp_db_url)
    engine = make_engine(temp_db_url)
    model, store = AxisFakeEmbeddingModel(), InMemoryVectorStore()
    with engine.begin() as conn:
        aid = create_axis(conn, label="lens", description="anomalous faces")
        score_axis(conn, axis_id=aid, model=model, vector_store=store, config=SUPERVISED_AXIS_CONFIG)  # emb for A
        update_axis(conn, aid, description="borderline construct")
        score_axis(
            conn, axis_id=aid, model=model, vector_store=store, config=SUPERVISED_AXIS_CONFIG
        )  # higher-id emb for B
        update_axis(conn, aid, description="anomalous faces")  # revisit A
        score_axis(
            conn, axis_id=aid, model=model, vector_store=store, config=SUPERVISED_AXIS_CONFIG
        )  # reuses A-emb, no insert
        state = axis_score_state(conn, aid)
    engine.dispose()
    assert state["scored"] is True
    assert state["stale"] is False  # current text matches an existing embedding → fresh (not newest-by-id)


def test_axis_label_only_falls_back_to_label_for_embedding(temp_db_url: str) -> None:
    # Legacy / not-yet-curated axes with a blank description still score: _axis_text falls back to the
    # label so there is always text to embed (nothing breaks, no migration needed).
    ids = _seed_axis_papers(temp_db_url)
    client = TestClient(_axes_app(temp_db_url))
    axis_id = client.post("/axes", json={"label": "anomalous"}).json()["id"]  # no description
    assert _run_score(client, axis_id)["status"] == "done"

    papers = _papers_by_id(client.get(f"/axes/{axis_id}/clusters").json())
    assert papers[ids["high"]]["status"] == "assigned"  # label fallback embedded "anomalous"
