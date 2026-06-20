"""Duplicate detection — flag likely-duplicate paper groups for review (backlog E, inc 56).

Layered signals, ordered so the deterministic ones lead and the fuzzy one only catches near-identical
text (the backlog's warning: pure embedding similarity false-positives on same-topic papers):

  1. **shared identifier** — same PMID or arXiv id (from csl_json). DOI can't collide (it's UNIQUE).
  2. **title + author + year** — identical canonical title (+ first-author, + year).
  3. **embedding near-dup** — pairwise cosine ≥ a HIGH threshold over the in-memory paper embeddings.

Pairs from all layers are merged via union-find into groups; each group carries its highest-confidence
reason. Flag-only + ephemeral: the user resolves by trashing the redundant copy (soft-delete) or
inspecting; nothing is persisted, nothing is auto-merged. Trashed papers are excluded.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sqlalchemy import Connection, select

from app.backend.embeddings.models import EmbeddingModel, normalize_text, strip_punctuation
from app.backend.embeddings.pipeline import paper_embedding_text
from app.backend.persistence.dedup_repo import get_dismissed_duplicate_pairs
from app.backend.persistence.schema import papers

MIN_TITLE_LEN = 8  # below this a canonical title is too generic to anchor a match
EMBEDDING_SIM = 0.92  # high → only near-identical text, not same-topic papers
MAX_EMBED_PAPERS = 3000  # skip the O(N^2) embedding layer above this (local-library guard)


@dataclass(frozen=True)
class DuplicateGroup:
    reason: str
    confidence: float
    papers: list[dict]


def find_duplicate_groups(conn: Connection, *, model: EmbeddingModel) -> list[DuplicateGroup]:
    rows = list(conn.execute(select(papers).where(papers.c.deleted_at.is_(None)).order_by(papers.c.id)).mappings())
    if len(rows) < 2:
        return []
    by_id = {int(r["id"]): r for r in rows}

    pairs: list[tuple[int, int, str, float]] = []
    pairs += _identifier_pairs(rows)
    pairs += _title_author_year_pairs(rows)
    pairs += _embedding_pairs(rows, model=model)
    # Drop pairs the user marked "not a duplicate" (inc 64) BEFORE the union-find, so a dismissed pair can't
    # link its two papers into a group — even if a stronger signal would otherwise connect them.
    dismissed = get_dismissed_duplicate_pairs(conn)
    if dismissed:
        pairs = [p for p in pairs if (min(p[0], p[1]), max(p[0], p[1])) not in dismissed]
    if not pairs:
        return []

    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, _reason, _conf in pairs:
        parent[find(a)] = find(b)

    comp_best: dict[int, tuple[str, float]] = {}  # root → (reason, confidence) of its strongest pair
    members: dict[int, list[int]] = {}
    for a, _b, reason, conf in pairs:
        root = find(a)
        cur = comp_best.get(root)
        if cur is None or conf > cur[1]:
            comp_best[root] = (reason, conf)
    for pid in {p for pair in pairs for p in pair[:2]}:
        members.setdefault(find(pid), []).append(pid)

    groups = [
        DuplicateGroup(
            reason=comp_best[root][0],
            confidence=round(comp_best[root][1], 2),
            papers=[_paper_ref(by_id[pid]) for pid in sorted(ids)],
        )
        for root, ids in members.items()
        if len(ids) >= 2
    ]
    groups.sort(key=lambda g: (-g.confidence, g.papers[0]["id"]))
    return groups


def _identifier_pairs(rows) -> list[tuple[int, int, str, float]]:
    index: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        csl = r["csl_json"] or {}
        for kind, value in (("PMID", csl.get("PMID")), ("arXiv", csl.get("arxiv") or csl.get("arXiv"))):
            v = str(value).strip().lower() if value else ""
            if v:
                index.setdefault((kind, v), []).append(int(r["id"]))
    pairs = []
    for (kind, _v), ids in index.items():
        for other in ids[1:]:  # chain to the first — union-find connects the whole set
            pairs.append((ids[0], other, f"shared {kind}", 0.99))
    return pairs


def _title_author_year_pairs(rows) -> list[tuple[int, int, str, float]]:
    by_title: dict[str, list] = {}
    for r in rows:
        canonical = normalize_text(strip_punctuation(str(r["title"] or "")))
        if len(canonical) >= MIN_TITLE_LEN:
            by_title.setdefault(canonical, []).append(r)
    pairs = []
    for group in by_title.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                fa_a = (a["first_author_family_name"] or "").strip().lower()
                fa_b = (b["first_author_family_name"] or "").strip().lower()
                same_author = bool(fa_a) and fa_a == fa_b
                same_year = a["year"] is not None and a["year"] == b["year"]
                if same_author and same_year:
                    pairs.append((int(a["id"]), int(b["id"]), "same title, author & year", 0.97))
                elif same_author:  # year differs/missing — catches preprint ↔ published
                    pairs.append((int(a["id"]), int(b["id"]), "same title & author", 0.85))
                # same title, different/absent author → not flagged (too weak; generic-title false positives)
    return pairs


def _embedding_pairs(rows, *, model: EmbeddingModel) -> list[tuple[int, int, str, float]]:
    if len(rows) > MAX_EMBED_PAPERS:
        return []
    vectors = _l2_normalize(np.array(model.encode_texts([paper_embedding_text(r) for r in rows]), dtype=float))
    sims = vectors @ vectors.T
    ids = [int(r["id"]) for r in rows]
    pairs = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            score = float(sims[i, j])
            if score >= EMBEDDING_SIM:
                pairs.append((ids[i], ids[j], "very similar text", score))
    return pairs


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _paper_ref(row) -> dict:
    return {
        "id": int(row["id"]),
        "title": row["title"],
        "authors": _authors(row),
        "year": row["year"],
        "venue": row["venue"],
    }


def _authors(row) -> list[str]:
    out = []
    for author in (row["csl_json"] or {}).get("author") or []:
        if not isinstance(author, dict):
            continue
        literal, family, given = author.get("literal"), author.get("family"), author.get("given")
        if literal:
            out.append(str(literal))
        elif family and given:
            out.append(f"{given} {family}")
        elif family:
            out.append(str(family))
    if not out and row["first_author_family_name"]:
        out.append(str(row["first_author_family_name"]))
    return out
