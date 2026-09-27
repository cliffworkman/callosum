"""Which chunks of an already-nominated paper deserve to be read for THIS child? (obligation- and section-directed)

Probes are the child's approved wording plus each owned content unit's frozen words (the asked-for element, without the shared
subject framing that otherwise drowns it: "using which scales?" ranks the Methods sentence naming the scales far above the
whole-wording query). Each unit probe searches a section-family pool that is a UNION (chunks labelled with the family, plus every
chunk with no usable label), so missing section metadata widens the search instead of excluding a paper. The paper's own
abstract is located in the attachment by text match (embeddings dilute it) and always anchored. Nothing here writes; every
anchor keeps ALL the routes that reached it, with probe, score and pool provenance, so a route's contribution is attributable
(descriptively, in one union run) afterwards.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.contract_directed import abstracts, neighborhood, sections
from experiments.ask_cli_revised.contract_directed.freeze import ChildContract
from experiments.ask_cli_revised.contract_directed.retriever import DEPRIORITIZED_ROLES, Hit, Retriever
from experiments.ask_cli_revised.contract_directed.store import Library

GLOBAL_PER_PAPER = 2
UNIT_PROBE_PER_PAPER = 1
ABSTRACT_PER_PAPER = 1
MAX_ANCHORS_PER_PAPER = 7
MAX_CONTENT_UNITS = 2  # the most content units any frozen child owns
INSPECTED_PAPERS = 6  # budget I (nominate.INSPECT_CAP)
# Derived, not chosen: each inspected paper contributes its abstract page + its best neighborhood per content unit.
NEIGHBORHOODS_PER_CHILD = INSPECTED_PAPERS * (1 + MAX_CONTENT_UNITS)  # N = 18; overflow is budget_capped, never dropped
ABSTRACT_PAGES = 2  # the abstract is looked for on the first pages of the attachment
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_SQUASH = re.compile(r"[^a-z0-9]+")
_ROUTE_PRIORITY = {"unit_probe": 0, "abstract_page": 1, "abstract_directed": 2, "global_wording": 3}


def probes_for(child: ChildContract) -> list[dict]:
    """The child's retrieval probes: approved wording (+ carried scope) and each content unit's frozen text."""
    out = [{"probe_id": "wording", "text": child.retrieval_query(), "families": None, "unit_id": None}]
    for unit in child.content_units:
        out.append(
            {
                "probe_id": f"unit:{unit.unit_id}",
                "text": unit.text,
                "families": sections.families_for_units([unit.kind]),
                "unit_id": unit.unit_id,
            }
        )
    return out


def _squash(text: str) -> str:
    return _SQUASH.sub("", text.lower())


def abstract_sentences(abstract_clean: str) -> list[str]:
    return [t.strip() for t in _SENTENCE.split(abstract_clean) if len(t.strip()) > 20]


def abstract_page_chunk(abstract_clean: str, chunks: list[dict]) -> dict | None:
    """Where the paper's own abstract sits in the attachment (text match only, no embeddings).

    A chunk is abstract-like if its squashed text lies inside the squashed abstract (line-level chunking) or reproduces an
    abstract sentence (paragraph-level chunking), on the first pages. The longest consecutive run of such chunks is the abstract;
    the anchor is the run's largest chunk. Deterministic and robust to hyphen/space breaks. Returns {chunk_id, run_len} or None.
    """
    whole = _squash(abstract_clean)
    sentences = [_squash(x)[:80] for x in abstract_sentences(abstract_clean)]
    sentences = [x for x in sentences if len(x) >= 25]
    runs: list[list[dict]] = []
    current: list[dict] = []
    for chunk in chunks:
        if (chunk.get("page_start") or 1) > ABSTRACT_PAGES:
            if current:
                runs.append(current)
                current = []
            continue
        body = _squash(chunk["text"])
        like = bool(body) and ((len(body) >= 12 and body in whole) or any(x in body for x in sentences))
        if like:
            current.append(chunk)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    if not runs:
        return None
    run = max(runs, key=lambda r: (sum(len(c["text"]) for c in r), -r[0]["chunk_id"]))
    anchor = max(run, key=lambda c: (len(c["text"]), -c["chunk_id"]))
    return {"chunk_id": anchor["chunk_id"], "run_len": len(run)}


def best_abstract_sentence(abstract_clean: str, child: ChildContract, retriever: Retriever) -> str | None:
    """Deterministic stand-in for a triage quote: the abstract sentence closest to the child's wording (embedding cosine)."""
    sentences = abstract_sentences(abstract_clean)
    if not sentences:
        return None
    query = retriever.encode(child.retrieval_query())
    vectors = retriever.model.encode_texts(sentences)
    scored = [(sum(a * b for a, b in zip(query, v, strict=False)), s) for s, v in zip(sentences, vectors, strict=True)]
    return max(scored)[1]


def working_attachment(library: Library, paper_id: int) -> dict | None:
    """The attachment read first: the paper's primary article attachment, else its first article attachment."""
    attachments = library.article_attachments(paper_id)
    return attachments[0] if attachments else None


def select_anchors(
    child: ChildContract,
    paper_id: int,
    library: Library,
    retriever: Retriever,
    *,
    attachment_id: int | None = None,
    abstract_quote: str | None = None,
    exclude_chunk_ids: set[int] | None = None,
    max_anchors: int = MAX_ANCHORS_PER_PAPER,
) -> dict:
    """Anchors for one paper in one attachment (default: the working attachment). Returns anchors + what was skipped and why.

    A chunk reached by several routes is ONE anchor carrying every route (`routes`) and each route's score (`route_scores`).
    """
    attachment = library.attachment(attachment_id) if attachment_id else working_attachment(library, paper_id)
    if attachment is None:
        return {"paper_id": paper_id, "attachment": None, "anchors": [], "skipped": [], "state": "no_chunks"}
    chunks = library.attachment_chunks(attachment["id"])
    by_id = {c["chunk_id"]: c for c in chunks}
    anchors: dict[int, dict] = {}
    skipped: list[dict] = []
    blocked = set(exclude_chunk_ids or ())

    def take(hits, route: str, probe: dict, limit: int, pool_size: int) -> None:
        got = 0
        for hit in hits:
            if got >= limit:
                return
            chunk = by_id.get(hit.chunk_id)
            if chunk is None or hit.chunk_id in blocked:
                continue
            family, state = sections.family_of(chunk.get("section"), chunk.get("grobid_kind"))
            if family == "references":
                skipped.append({"chunk_id": hit.chunk_id, "reason": "references_section", "route": route})
                continue
            if hit.evidence_role in DEPRIORITIZED_ROLES:
                skipped.append(
                    {"chunk_id": hit.chunk_id, "reason": f"evidence_role_{hit.evidence_role}", "route": route}
                )
                continue
            if hit.chunk_id in anchors:  # already an anchor: it gains this route, it does not use a new slot
                anchors[hit.chunk_id]["routes"].append(route)
                anchors[hit.chunk_id]["route_scores"][route] = round(hit.score, 4)
                got += 1
                continue
            if len(anchors) >= max_anchors:
                return
            got += 1
            anchors[hit.chunk_id] = {
                "chunk_id": hit.chunk_id,
                "routes": [route],
                "route_scores": {route: round(hit.score, 4)},
                "probe_id": probe["probe_id"],
                "family": family,
                "section_state": state,
                "pool_size": pool_size,
            }

    every = {c["chunk_id"] for c in chunks}
    probes = probes_for(child)
    wording = probes[0]
    take(
        retriever.search(wording["text"], chunk_ids=every, top_k=GLOBAL_PER_PAPER + 6),
        "global_wording",
        wording,
        GLOBAL_PER_PAPER,
        len(every),
    )
    for probe in probes[1:]:
        pool = sections.family_pool(chunks, probe["families"])
        ids = {c["chunk_id"] for c in pool}
        take(
            retriever.search(probe["text"], chunk_ids=ids, top_k=UNIT_PROBE_PER_PAPER + 6),
            f"unit_probe:{probe['unit_id']}",
            probe,
            UNIT_PROBE_PER_PAPER,
            len(ids),
        )
    clean = abstracts.clean_abstract((library.paper(paper_id) or {}).get("abstract"))
    found = abstract_page_chunk(clean, chunks) if clean else None
    page_chunk = found["chunk_id"] if found else None
    if page_chunk is not None:
        take([Hit(page_chunk, paper_id, 1.0)], "abstract_page", {"probe_id": "abstract_page_text_match"}, 1, len(every))
    quote = abstract_quote or (best_abstract_sentence(clean, child, retriever) if clean else None)
    if quote:
        take(
            retriever.search(
                quote, chunk_ids=every - ({page_chunk} if page_chunk else set()), top_k=ABSTRACT_PER_PAPER + 6
            ),
            "abstract_directed",
            {"probe_id": "abstract_quote", "text": quote},
            ABSTRACT_PER_PAPER,
            len(every),
        )
    return {
        "paper_id": paper_id,
        "attachment": attachment,
        "anchors": list(anchors.values()),
        "skipped": skipped,
        "state": "ok",
        "abstract_probe": quote,
        "abstract_page_chunk": page_chunk,
    }


def neighborhoods_for(anchor_set: dict, library: Library) -> list[dict]:
    """Merged neighborhoods for a paper's anchors; each keeps every anchor's routes and scores."""
    attachment = anchor_set["attachment"]
    if attachment is None or not anchor_set["anchors"]:
        return []
    ordered = library.attachment_chunks(attachment["id"])
    index = {c["chunk_id"]: i for i, c in enumerate(ordered)}
    built = [neighborhood.build_neighborhood(ordered, index[a["chunk_id"]]) for a in anchor_set["anchors"]]
    merged = neighborhood.merge_neighborhoods(built, {attachment["id"]: ordered})
    by_anchor = {a["chunk_id"]: a for a in anchor_set["anchors"]}
    for nb in merged:
        inside = [by_anchor[c] for c in nb["anchor_chunk_ids"] if c in by_anchor]
        nb["anchors"] = [
            {k: a[k] for k in ("chunk_id", "routes", "route_scores", "probe_id", "family", "section_state")}
            for a in inside
        ]
        nb["routes"] = sorted({r for a in inside for r in a["routes"]})
        unit_scores: dict[str, float] = {}
        for a in inside:
            for route, score in a["route_scores"].items():
                if route.startswith("unit_probe:"):
                    unit = route.split(":", 1)[1]
                    unit_scores[unit] = max(unit_scores.get(unit, 0.0), score)
        nb["unit_scores"] = unit_scores
        nb["best_score"] = max((s for a in inside for s in a["route_scores"].values()), default=0.0)
        nb["attachment"] = {k: attachment[k] for k in ("id", "role", "checksum", "is_primary")}
    return merged


def _priority(nb: dict) -> tuple:
    best = min((_ROUTE_PRIORITY.get(r.split(":")[0], 9) for r in nb["routes"]), default=9)
    return (best, -nb["best_score"], nb["paper_id"])


def select_neighborhoods(
    per_paper: list[list[dict]], child: ChildContract, *, cap: int = NEIGHBORHOODS_PER_CHILD
) -> dict:
    """Fit a child's neighborhoods to the budget by a fixed, recorded, PAPER-MAJOR, obligation-directed rule.

    Each inspected paper, in inspection order, contributes (1) its abstract-page neighborhood (the authors' own summary of their
    findings) and (2) its best neighborhood for EACH of the child's content units (by that unit's probe score within the paper).
    Comparing probe scores across papers is deliberately not used: a paper lexically close to a probe word would crowd out the
    paper most tied to the subject. The bound is derived, not chosen: N = I inspected papers x (1 abstract + at most 2 units).
    Room left by papers without an abstract or with merged neighborhoods is filled by route priority. What does not fit is
    returned as `budget_capped` with full provenance: never dropped, and the first thing recovery revisits.
    """
    chosen: list[dict] = []

    def add(nb: dict) -> None:
        if len(chosen) < cap and all(nb is not c for c in chosen):
            chosen.append(nb)

    for group in per_paper:
        page = next((nb for nb in sorted(group, key=_priority) if "abstract_page" in nb["routes"]), None)
        if page is not None:
            add(page)
        for unit in child.content_units:
            candidates = [nb for nb in group if unit.unit_id in nb["unit_scores"]]
            if candidates:
                add(max(candidates, key=lambda nb: nb["unit_scores"][unit.unit_id]))
    everything = [nb for group in per_paper for nb in group]
    rest = sorted((nb for nb in everything if all(nb is not c for c in chosen)), key=_priority)
    for nb in rest:
        add(nb)
    capped = [nb for nb in rest if all(nb is not c for c in chosen)]
    return {"read": chosen, "budget_capped": capped}
