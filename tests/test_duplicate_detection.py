"""Unit tests for the layered duplicate-detection engine (inc 56)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from app.backend.clustering.duplicate_detection import find_duplicate_groups
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, soft_delete_paper


@dataclass(frozen=True)
class DistinctModel:
    """One-hot per position → every paper orthogonal → the embedding layer never fires (isolates the
    deterministic layers)."""

    name: str = "distinct"
    version: str = "v1"
    dimension: int = 8
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        n = len(texts)
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


@dataclass(frozen=True)
class TwinModel:
    """Papers whose text contains 'zztwin' share one vector (cosine 1); others stay orthogonal."""

    name: str = "twin"
    version: str = "v1"
    dimension: int = 8
    normalization: str = DEFAULT_NORMALIZATION

    def encode_texts(self, texts: list[str]) -> list[list[float]]:
        n = len(texts)
        return [
            ([1.0] + [0.0] * n) if "zztwin" in t.lower() else [0.0] + [1.0 if j == i else 0.0 for j in range(n)]
            for i, t in enumerate(texts)
        ]


def _migrated(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'dup.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return make_engine(url)


def _mk(conn, title, *, pmid=None, author=None, year=None, abstract=None) -> int:
    csl = {"type": "article-journal", "title": title}
    if pmid:
        csl["PMID"] = pmid
    return create_paper(conn, title=title, csl_json=csl, abstract=abstract, first_author_family_name=author, year=year)


def test_identifier_layer_groups_shared_pmid(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        a = _mk(conn, "Alpha study one", pmid="30072749")
        b = _mk(conn, "Beta study two", pmid="30072749")
        _mk(conn, "Gamma unrelated", pmid="99999999")
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert len(groups) == 1
    assert groups[0].reason == "shared PMID" and groups[0].confidence == 0.99
    assert {p["id"] for p in groups[0].papers} == {a, b}


def test_title_author_year_layer(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        a = _mk(conn, "Resting-State Connectivity!", author="Baez", year=2018)
        b = _mk(
            conn, "resting  state connectivity", author="baez", year=2018
        )  # same canonical title, case/punct differ
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert len(groups) == 1
    assert groups[0].reason == "same title, author & year" and groups[0].confidence == 0.97
    assert {p["id"] for p in groups[0].papers} == {a, b}


def test_title_author_differing_year_is_lower_confidence(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        _mk(conn, "Same Title Here Long Enough", author="Smith", year=2020)
        _mk(conn, "same title here long enough", author="Smith", year=2021)  # preprint ↔ published
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert len(groups) == 1 and groups[0].reason == "same title & author" and groups[0].confidence == 0.85


def test_embedding_layer_flags_near_identical_text(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        a = _mk(conn, "Distinct title aaa", abstract="zztwin marker body one")
        b = _mk(conn, "Different title bbb", abstract="zztwin marker body two")
        _mk(conn, "Totally other ccc", abstract="unrelated content")
        groups = find_duplicate_groups(conn, model=TwinModel())
    engine.dispose()
    assert len(groups) == 1 and groups[0].reason == "very similar text"
    assert groups[0].confidence >= 0.92 and {p["id"] for p in groups[0].papers} == {a, b}


def test_union_find_merges_overlapping_pairs(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        a = _mk(conn, "Alpha distinct title", pmid="555")
        b = _mk(conn, "Shared canonical title here", pmid="555", author="Doe", year=2019)  # PMID-links a
        c = _mk(conn, "shared canonical title here", author="Doe", year=2019)  # title-links b
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert len(groups) == 1 and {p["id"] for p in groups[0].papers} == {a, b, c}
    assert groups[0].confidence == 0.99  # strongest pair in the component (the shared PMID)


def test_no_duplicates_returns_empty(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        _mk(conn, "First unique paper", pmid="1", author="A", year=2001)
        _mk(conn, "Second unique paper", pmid="2", author="B", year=2002)
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert groups == []


def test_excludes_trashed_papers(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        _mk(conn, "Dup paper", pmid="777")
        b = _mk(conn, "Dup paper two", pmid="777")
        soft_delete_paper(conn, b)  # trashed → only one live paper has PMID 777
        groups = find_duplicate_groups(conn, model=DistinctModel())
    engine.dispose()
    assert groups == []
