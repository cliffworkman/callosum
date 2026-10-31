"""Source-role structure derivation for a library's chunks (inc 577 H1a; v2 since inc 611; app-side since inc 613).

This module OWNS all I/O -- database reads and reference-metadata resolution -- and hands already-resolved inputs to
the pure classifier in ``app.backend.pdf_processing.chunk_structure``. Keeping the boundary here is what makes the
classifier deterministic and testable from literals. It lives in the packaged application (not ``tools/``) so a
desktop install can classify its own library in the background; ``tools/backfill_chunk_structure.py`` is a thin CLI
over it. The code moved verbatim: classification output is byte-identical to the inc-612 tool.

Properties, all deliberate:

* **Cache-only. No network.** Reference metadata comes from what is already in ``external_api_cache`` and
  ``reference_instances``. Opening an existing library must never require connectivity, and a paper with no cached
  metadata classifies conservatively rather than guessing.
* **Additive and non-destructive.** Raw chunk text, embeddings, sections and every ingest-time column are untouched.
  Only ``chunk_structure`` is written.
* **Per-paper commit, so an interrupted run resumes** by simply re-running: a paper whose rows are missing or stale is
  re-derived, everything else is skipped.
* **A derivation-version bump invalidates every older row.** Older rows are ignored by the retrieval path, never
  reinterpreted; a plain re-run re-derives exactly the papers that are not current at the new version.
* **The narrow Ask path reads what this writes (inc 607):** a current ``bibliographic`` label demotes a chunk behind
  every eligible candidate, but never withholds it. A library this has never run on is an exact no-op for that seam.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy import text as sqltext

from app.backend.pdf_processing.chunk_structure import ChunkInput, classify_paper
from app.backend.persistence.chunk_structure_repo import (
    papers_with_current_structure,
    raw_sha,
    replace_paper_structure,
)
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES, attachment_document_role_clause
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure

_WORD = re.compile(r"[a-z0-9]+")
_DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[^\s\"'<>,;)\]]+", re.I)
_NGRAM = 6
_MIN_TITLE_WORDS = 8
_MIN_DISTINCT_REFS = 4
_CLUSTER_GAP = 25
_REPEAT_MIN_PAGES = 3
_REPEAT_MAX_WORDS = 25


# --------------------------------------------------------------------------------------------
# Resolution (all I/O lives here, never in the classifier)
# --------------------------------------------------------------------------------------------
def _dense_key(text: str) -> str:
    """Aggressively normalized, whitespace-free comparison key. COMPARISON ONLY.

    Never stored, never quoted, never model-facing. It exists so a title split across a line break
    still matches its metadata: "Functional connectiv-\\nity in late-life depression" and
    "Functional Connectivity in Late-Life Depression" collapse to the same key, which is what took
    title matching from ~31% to ~90% of a paper's known references without needing to solve
    hyphenation first.
    """
    from app.backend.embeddings.models import normalize_text, strip_punctuation
    from app.backend.pdf_processing.extraction import _canonical_characters

    canon = normalize_text(strip_punctuation(_canonical_characters(text or "")))
    return re.sub(r"[^a-z0-9]+", "", canon)


def doi_owners(conn, diagnostics: dict | None = None) -> dict[str, tuple[int, ...]]:
    """``{normalized DOI: live canonical paper ids}`` -- never a soft-deleted or merged duplicate.

    A merge leaves the duplicate row (with the same DOI) behind, soft-deleted and pointing at its survivor via
    ``merged_into``. Mapping DOIs over every row let whichever duplicate came last capture the live paper's cached
    reference list -- measured, DOI 10.5498/wjp.v11.i6.201 went to merged paper 202, so live paper 171 got no
    reference region at all. Now: live, unmerged papers own their DOI; a DOI held only by non-live rows resolves
    through ``merged_into`` to its live survivor. Two LIVE papers sharing a DOI are an unresolved identity
    duplicate: the reference list belongs to the DOI, so each receives it, and the group is recorded in
    ``diagnostics['ambiguous_dois']`` instead of letting one silently win.
    """
    rows = conn.execute(
        select(papers.c.id, papers.c.doi, papers.c.deleted_at, papers.c.merged_into).where(papers.c.doi.is_not(None))
    ).fetchall()
    live = {int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))}
    merged_into = {int(r[0]): (int(r[3]) if r[3] is not None else None) for r in rows}

    def survivor(paper_id: int) -> int | None:
        seen: set[int] = set()
        while paper_id not in live:
            if paper_id in seen or merged_into.get(paper_id) is None:
                return None
            seen.add(paper_id)
            paper_id = merged_into[paper_id]  # type: ignore[assignment]
        return paper_id

    direct: dict[str, set[int]] = defaultdict(set)
    resolved: dict[str, set[int]] = defaultdict(set)
    for paper_id, doi, deleted_at, merged in rows:
        key = (doi or "").lower().strip()
        if not key:
            continue
        if deleted_at is None and merged is None:
            direct[key].add(int(paper_id))
        else:
            target = survivor(int(paper_id))
            if target is not None:
                resolved[key].add(target)
    owners = {key: tuple(sorted(direct.get(key) or resolved[key])) for key in set(direct) | set(resolved)}
    if diagnostics is not None:
        diagnostics["ambiguous_dois"] = {k: list(v) for k, v in sorted(owners.items()) if len(v) > 1}
        diagnostics["resolved_through_merge"] = sorted(k for k in resolved if k not in direct)
    return owners


def load_reference_metadata(conn, diagnostics: dict | None = None) -> dict[int, list[dict]]:
    """{paper_id: [reference records]} from LOCAL caches only. No network, ever."""
    by_doi = doi_owners(conn, diagnostics)
    out: dict[int, list[dict]] = defaultdict(list)
    rows = conn.execute(
        sqltext("SELECT cache_key, response_json FROM external_api_cache WHERE provider = 'crossref'")
    ).fetchall()
    for key, payload in rows:
        owner_ids = by_doi.get((key or "").lower().strip(), ())
        if not owner_ids:
            continue
        try:
            doc = json.loads(payload)
        except (TypeError, ValueError):
            continue
        message = doc.get("message", doc) if isinstance(doc, dict) else {}
        for ref in (message.get("reference") or []) if isinstance(message, dict) else []:
            if isinstance(ref, dict):
                for paper_id in owner_ids:
                    out[paper_id].append(ref)
    # `reference_instances` is the persisted Meta-Reference product -- authoritative where present.
    try:
        for citing, title, doi in conn.execute(sqltext("SELECT citing_paper_id, title, doi FROM reference_instances")):
            out[int(citing)].append({"article-title": title, "DOI": doi})
    except Exception:  # noqa: BLE001  # nosec B110 -- an older library may predate the table
        pass
    return dict(out)


def infer_reference_region(rows: list[dict], refs: list[dict]) -> tuple[set[int], str]:
    """Locate the bibliography by finding the paper's OWN known references in its text.

    Multi-prong by necessity, not preference: measured across 31,122 cached reference entries, 89%
    carry a DOI but only 42% carry a title -- yet the DOI is frequently not PRINTED in the reference
    list (older works especially), so dense-key title matching is the strongest general signal and
    the DOI is a corroborator. The region is the densest cluster of matches, never the first match:
    a cited title can legitimately appear in the body.
    """
    if not refs:
        return set(), "none"
    doi_map: dict[str, int] = {}
    gram_map: dict[str, int] = {}
    for ordinal, ref in enumerate(refs):
        doi = ref.get("DOI")
        if isinstance(doi, str) and doi.strip():
            doi_map.setdefault(doi.strip().lower(), ordinal)
        title = ref.get("article-title") or ref.get("volume-title") or ref.get("unstructured")
        if isinstance(title, str):
            words = _WORD.findall(title.lower())
            if len(words) >= _MIN_TITLE_WORDS:
                key = _dense_key(title)
                for i in range(0, max(len(key) - 40, 1), 10):
                    gram_map.setdefault(key[i : i + 40], ordinal)
    if not doi_map and not gram_map:
        return set(), "none"

    keys = [_dense_key(r["text"]) for r in rows]
    hits: list[tuple[int, set[int]]] = []
    for i, row in enumerate(rows):
        found: set[int] = set()
        for token in {m.group(0).lower().rstrip(".") for m in _DOI_IN_TEXT.finditer(row["text"] or "")}:
            if token in doi_map:
                found.add(doi_map[token])
        window = "".join(keys[i : i + 4])
        for gram, ordinal in gram_map.items():
            if gram and gram in window:
                found.add(ordinal)
        if found:
            hits.append((i, found))
    if not hits:
        return set(), "none"

    clusters: list[list[tuple[int, set[int]]]] = [[hits[0]]]
    for hit in hits[1:]:
        if hit[0] - clusters[-1][-1][0] <= _CLUSTER_GAP:
            clusters[-1].append(hit)
        else:
            clusters.append([hit])
    n_distinct, best = max(((len({o for _, s in cl for o in s}), cl) for cl in clusters), key=lambda t: t[0])
    if n_distinct < _MIN_DISTINCT_REFS:
        return set(), "none"
    start, end = best[0][0], best[-1][0]
    while end + 1 < len(rows) and len(_WORD.findall(rows[end + 1]["text"] or "")) < _MIN_TITLE_WORDS:
        end += 1
    return {rows[i]["id"] for i in range(start, end + 1)}, "anchored"


def detect_repeats(rows: list[dict]) -> dict[int, str]:
    """Verbatim short text repeating across >=3 of a paper's pages at a stable x -> page furniture.

    Position stability is what makes this defensible rather than merely plausible; the page band
    ("top"/"bottom") is what keeps running_head and running_footer distinct.
    """
    from app.backend.summarization.chunk_filtering import _repetition_key

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = _repetition_key(row["text"] or "")
        if key and len(key.split()) <= _REPEAT_MAX_WORDS:
            groups[key].append(row)
    tops = [r["y_top"] for r in rows if r["y_top"] is not None]
    page_top = min(tops) if tops else 0.0
    page_bottom = max(tops) if tops else 1.0
    span = max(page_bottom - page_top, 1.0)

    flagged: dict[int, str] = {}
    for members in groups.values():
        pages = {m["page_start"] for m in members if m["page_start"] is not None}
        if len(pages) < _REPEAT_MIN_PAGES:
            continue
        xs = [m["x0"] for m in members if m["x0"] is not None]
        if len(xs) > 1 and (max(xs) - min(xs)) > 12.0:
            continue  # not a stable margin position
        for member in members:
            if member["y_top"] is None:
                flagged[member["id"]] = "middle"
                continue
            rel = (member["y_top"] - page_top) / span
            flagged[member["id"]] = "top" if rel < 0.12 else ("bottom" if rel > 0.85 else "middle")
    return flagged


def _paper_rows(conn, paper_id: int) -> list[dict]:
    stmt = (
        select(
            chunks.c.id,
            chunks.c.paper_id,
            chunks.c.text,
            chunks.c.section,
            chunks.c.page_start,
            chunks.c.bbox_json,
            chunks.c.chunk_version,
        )
        .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
        .where(chunks.c.paper_id == paper_id, attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES))
        .order_by(chunks.c.id)
    )
    rows = []
    for row in conn.execute(stmt).mappings():
        record = dict(row)
        x0 = y_top = None
        if record["bbox_json"]:
            try:
                raw = record["bbox_json"]
                # A JSON column read hands back a decoded list; only a string needs loads().
                spans = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
                boxes = [s for s in spans if isinstance(s, dict) and "x0" in s]
                if boxes:
                    x0 = min(float(s["x0"]) for s in boxes)
                    y_top = min(float(s["y0"]) for s in boxes)
            except (TypeError, ValueError):
                pass
        record["x0"], record["y_top"] = x0, y_top
        rows.append(record)
    return rows


def backfill(engine, *, paper_id: int | None = None, limit: int | None = None, force: bool = False) -> dict:
    stats = {"papers": 0, "chunks": 0, "skipped_current": 0, "no_reference_metadata": 0}
    with engine.begin() as conn:
        targets = (
            [paper_id]
            if paper_id
            else [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))]
        )
        done = set() if force else papers_with_current_structure(conn, DERIVATION_VERSION)
        doi_diagnostics: dict = {}
        references = load_reference_metadata(conn, doi_diagnostics)
    stats["ambiguous_dois"] = doi_diagnostics["ambiguous_dois"]

    for pid in targets:
        if pid in done:
            stats["skipped_current"] += 1
            continue
        if limit is not None and stats["papers"] >= limit:
            break
        with engine.begin() as conn:  # per-paper commit: an interrupted run simply resumes
            rows = _paper_rows(conn, pid)
            if not rows:
                continue
            refs = references.get(pid, [])
            if not refs:
                stats["no_reference_metadata"] += 1
            region, source = infer_reference_region(rows, refs)
            repeats = detect_repeats(rows)
            results = classify_paper(
                [
                    ChunkInput(
                        chunk_id=int(r["id"]),
                        paper_id=int(r["paper_id"]),
                        text=r["text"] or "",
                        section=r["section"],
                        page_start=r["page_start"],
                        bbox_json=r["bbox_json"],
                        chunk_version=r["chunk_version"] or "",
                    )
                    for r in rows
                ],
                reference_region=region,
                reference_region_source=source,
                repeated=repeats,
            )
            written = replace_paper_structure(
                conn,
                paper_id=pid,
                results=results,
                source={int(r["id"]): (raw_sha(r["text"] or ""), r["chunk_version"] or "") for r in rows},
            )
            stats["papers"] += 1
            stats["chunks"] += written
    return stats


def coverage(engine) -> dict:
    """Derivation-version coverage: what the retrieval path will obey (current) vs ignore (stale/absent)."""
    with engine.begin() as conn:
        live = [int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))]
        with_chunks = {int(r[0]) for r in conn.execute(select(chunks.c.paper_id).distinct())}
        current = papers_with_current_structure(conn, DERIVATION_VERSION)
        by_version = dict(
            conn.execute(
                select(chunk_structure.c.derivation_version, sqltext("count(*)")).group_by(
                    chunk_structure.c.derivation_version
                )
            ).fetchall()
        )
    targets = [pid for pid in live if pid in with_chunks]
    return {
        "derivation_version": DERIVATION_VERSION,
        "papers_with_chunks": len(targets),
        "papers_current": sum(pid in current for pid in targets),
        "papers_needing_derivation": sum(pid not in current for pid in targets),
        "rows_by_derivation_version": by_version,
    }
