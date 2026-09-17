"""Run 0.6 Phase 8 walk: a FROZEN decomposition item -> discovery -> within-paper retrieval -> the FROZEN
Run 0.5 minimum-sufficient-context controller. STOP after context selection.

Reuses production-adjacent experiment stages unchanged: `discovery.nominate_papers` (paper-kNN u axis),
`retrieval.within_paper_retrieve` (H1a-aware within-paper anchors), and `context_windows.build_window_case`
+ `select_window` (the frozen A/B/C/D/E controller — NOT the retired grow_context/5-way gate). All caps are
the existing constants. Deterministic code owns every id; Qwen only picks one A/B/C/D/E letter per anchor.
"""

from __future__ import annotations

from experiments.ask_cli_revised import discovery, retrieval
from experiments.ask_cli_revised.calibration import context_windows as cw


def _nomination_record(nom) -> dict:
    return {
        "paper_id": nom.paper_id,
        "reasons": nom.reasons,
        "score": round(nom.best_score, 4),
        "direct_score": round(nom.direct_score, 4),
        "axis_score": round(nom.axis_score, 4),
        "axis_hits": nom.axis_hits,
    }


def _window_sizes(case) -> dict:
    return {
        lbl: {
            "n_chunks": case.windows[lbl]["n_chunks"],
            "chars": case.windows[lbl]["chars"],
            "approx_tokens": case.windows[lbl]["approx_tokens"],
            "boundary_reduced": case.windows[lbl]["boundary_reduced"],
        }
        for lbl in "ABCD"
    }


def walk_item(conn, *, rt, base_config, case_id, item, mode, axis_cache, trace) -> dict:
    """Walk one frozen decomposition item to A/B/C/D/E envelopes. `item` carries source_unit_id + item_id."""
    query = item["text"]
    item_id = item["item_id"]
    nominations, nomination_log = discovery.nominate_papers(
        conn,
        subquestion_text=query,
        model=rt.model,
        vector_store=rt.vector_store,
        axis_cache=axis_cache,
    )
    paper_ids = [n.paper_id for n in nominations]
    axis_nom_count = sum(1 for row in nomination_log if str(row.get("reason", "")).startswith("axis:"))

    hits = retrieval.within_paper_retrieve(
        conn,
        subquestion_id=item_id,
        subquestion_text=query,
        paper_ids=paper_ids,
        model=rt.model,
        vector_store=rt.vector_store,
    )

    anchors = []
    for hit in hits:
        case = cw.build_window_case(
            conn, case_id=f"{item_id}::a{hit.chunk.chunk_id}", anchor_chunk_id=hit.chunk.chunk_id, paper_id=hit.chunk.paper_id
        )
        if case is None:
            anchors.append(
                {
                    "anchor_chunk_id": hit.chunk.chunk_id,
                    "paper_id": hit.chunk.paper_id,
                    "retrieval_score": round(hit.score, 4),
                    "section": hit.section,
                    "evidence_role": hit.evidence_role,
                    "window_choice": None,
                    "window_sizes": None,
                    "note": "no_window_case",
                }
            )
            continue
        choice, call, prompt = cw.select_window(base_config, case, mode=mode)
        trace.qwen_call(
            stage="walk_context",
            task="select_window",
            input_text=f"{item_id} anchor {hit.chunk.chunk_id}",
            prompt_text=prompt,
            raw_output=call.raw_text,
            provider_ok=call.provider_ok,
            parse_ok=call.parsed is not None,
            validation_ok=choice is not None,
            failure_reason=call.failure_reason,
            deterministic_fallback_used=choice is None,
            downstream_consequence=f"window={choice}",
            elapsed_seconds=call.elapsed_seconds,
            output_cap=call.output_cap,
        )
        anchors.append(
            {
                "anchor_chunk_id": hit.chunk.chunk_id,
                "paper_id": hit.chunk.paper_id,
                "retrieval_score": round(hit.score, 4),
                "section": hit.section,
                "chunk_type": hit.chunk_type,
                "evidence_role": hit.evidence_role,
                "window_choice": choice,
                "window_sizes": _window_sizes(case),
            }
        )

    return {
        "case_id": case_id,
        "source_unit_id": item["source_unit_id"],
        "item_id": item_id,
        "retrieval_query": query,
        "n_papers": len(nominations),
        "axis_nomination_count": axis_nom_count,
        "nominations": [_nomination_record(n) for n in nominations],
        "hits": [
            {"chunk_id": h.chunk.chunk_id, "paper_id": h.chunk.paper_id, "score": round(h.score, 4), "evidence_role": h.evidence_role}
            for h in hits
        ],
        "anchors": anchors,
    }


def walk_decomposition(conn, *, rt, base_config, frozen, mode, trace) -> list[dict]:
    """Walk every frozen item of one decomposition. Fresh axis cache per question (per-run memoization)."""
    axis_cache: dict = {}
    return [
        walk_item(conn, rt=rt, base_config=base_config, case_id=frozen["case_id"], item=item, mode=mode, axis_cache=axis_cache, trace=trace)
        for item in frozen["items"]
    ]
