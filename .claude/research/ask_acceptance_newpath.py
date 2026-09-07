#!/usr/bin/env python3
"""Ask acceptance harness (inc 581): OLD (legacy single-query) vs NEW (faceted) on the SAME corpus.

Research only. Runs both paths against a backfilled COPY of the demo library with the real embedding
model, the real local NLI verifier, and real Gemini generation, on the frozen broad acceptance query,
and records the old-vs-new metrics the steering asked for (verified synthesis, facet coverage,
contributing-paper breadth, evidence hygiene, provenance) -- never raw claim count. Also checks that
narrow questions still route to the unchanged path.

    python .claude/research/ask_acceptance_newpath.py --db-url sqlite:///.../ask_acceptance.sqlite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Script mode puts only this file's own dir on sys.path; add the repo root so `app` resolves
# (.claude/research/ -> parents[2] == repo root), the inc-508 run_https.py fix.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from app.backend.api.app import create_app
from app.backend.api.dependencies import resolve_embedding_model, resolve_support_scorer
from app.backend.api.startup import _upgrade_database_to_head, load_local_env
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.llm.providers import complete
from app.backend.persistence.chunk_structure_repo import current_structure_roles
from app.backend.persistence.schema import citation_mappings, evidence_quotes, summary_sentences
from app.backend.summarization.faceted_pipeline import summarize_faceted
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from app.backend.summarization.query_planner import plan_query

FROZEN_BROAD = (
    "Synthesize the neural and biological systems implicated in late-life depression and its "
    "relationship to cognitive decline and dementia based on the literature in my library. I am "
    "particularly interested in serotonergic function, amyloid, glucose metabolism, gray-matter "
    "structure, memory and executive function, and other relevant neurobiological or cognitive "
    "findings. Give me a structured account of the systems and processes involved, what role each "
    "appears to play, and where the literature reports mixed, null, or uncertain findings."
)

NARROW_REGRESSION = [
    "What sample size did the serotonin transporter PET study use?",
    "Which brain region showed reduced volume in late-life depression?",
    "hippocampal volume in late-life depression?",
]


def _gemini_config(app):
    from integrations.gemini.generator import GeminiSummaryGenerator, LLMConfig

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("no GEMINI_API_KEY / GOOGLE_API_KEY in the environment (.env)")
    config = LLMConfig(
        provider="gemini",
        wire_format="gemini",
        model="gemini-2.5-flash-lite",
        api_key=key,
        data_egress_enabled=True,
        provider_runtime=app.state.provider_client_runtime,
    )
    return config, GeminiSummaryGenerator(config)


def _summary_facts(engine, summary_id: int) -> dict:
    """Read verified/flagged claims + cited-evidence provenance + hygiene roles from the persisted rows."""
    with engine.begin() as conn:
        sentences = list(
            conn.execute(select(summary_sentences.c.id).where(summary_sentences.c.summary_id == summary_id)).scalars()
        )
        rows = list(
            conn.execute(
                select(
                    citation_mappings.c.summary_sentence_id,
                    citation_mappings.c.status,
                    evidence_quotes.c.chunk_id,
                )
                .select_from(
                    citation_mappings.join(
                        evidence_quotes, evidence_quotes.c.citation_mapping_id == citation_mappings.c.id
                    )
                )
                .where(citation_mappings.c.summary_sentence_id.in_(sentences) if sentences else False)
            ).mappings()
        )
        cited_chunk_ids = sorted({int(r["chunk_id"]) for r in rows})
        roles = current_structure_roles(conn, cited_chunk_ids)
        # map cited chunk -> paper via chunks
        from app.backend.persistence.schema import chunks as chunks_t

        paper_of = dict(
            conn.execute(
                select(chunks_t.c.id, chunks_t.c.paper_id).where(
                    chunks_t.c.id.in_(cited_chunk_ids) if cited_chunk_ids else False
                )
            ).all()
        )
    verified_sentences = set()
    flagged_sentences = set()
    by_sentence: dict[int, list[str]] = {}
    for r in rows:
        by_sentence.setdefault(int(r["summary_sentence_id"]), []).append(r["status"])
    for sid in sentences:
        statuses = by_sentence.get(sid, [])
        (verified_sentences if statuses and all(s == "verified" for s in statuses) else flagged_sentences).add(sid)
    cited_role_dist = Counter(roles.get(cid, (None, "absent"))[1] for cid in cited_chunk_ids)
    return {
        "claims_total": len(sentences),
        "verified_claims": len(verified_sentences),
        "flagged_claims": len(flagged_sentences),
        "citation_count": len(rows),
        "citation_statuses": dict(Counter(r["status"] for r in rows)),
        "contributing_papers": len(set(paper_of.values())),
        "cited_chunks": len(cited_chunk_ids),
        "cited_evidence_role_distribution": dict(cited_role_dist),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", required=True)
    ap.add_argument("--out", default=".local/ask-acceptance-newpath.json")
    args = ap.parse_args()

    load_local_env()
    _upgrade_database_to_head(args.db_url)
    app = create_app(db_url=args.db_url)
    engine = app.state.engine
    model = resolve_embedding_model(app)
    store = SQLiteVecVectorStore()
    support_scorer = resolve_support_scorer(app, embedding_model=model)
    config, generator = _gemini_config(app)

    report: dict = {"db_url": args.db_url, "broad_query": FROZEN_BROAD}

    # ---- OLD path (legacy single-query, top_k=8) ----
    t0 = time.time()
    old = summarize_scope(
        engine,
        scope=SummaryScope(scope_type="query", query=FROZEN_BROAD),
        generator=generator,
        model=model,
        vector_store=store,
        top_k=8,
        support_scorer=support_scorer,
    )
    report["old"] = {
        "seconds": round(time.time() - t0, 1),
        "summary_id": old.summary_id,
        "status": old.status,
        "source_chunk_count": old.source_chunk_count,
        **_summary_facts(engine, old.summary_id),
    }

    # ---- NEW path (planner -> faceted) ----
    t0 = time.time()
    plan = plan_query(FROZEN_BROAD, config=config, complete_fn=complete)
    report["plan"] = {
        "scope": plan.scope,
        "is_broad": plan.is_broad,
        "planner_used": plan.planner_used,
        "facets": [{"label": f.label, "query": f.query} for f in plan.facets],
    }
    if plan.is_broad:
        new = summarize_faceted(
            engine,
            question=FROZEN_BROAD,
            plan=plan,
            generator=generator,
            model=model,
            vector_store=store,
            support_scorer=support_scorer,
        )
        with engine.begin() as conn:
            from app.backend.persistence.repository import get_summary

            scope_ref = get_summary(conn, new.summary_id)["scope_ref_json"]
        report["new"] = {
            "seconds": round(time.time() - t0, 1),
            "summary_id": new.summary_id,
            "status": new.status,
            "source_chunk_count": new.source_chunk_count,
            "coverage": scope_ref.get("coverage"),
            **_summary_facts(engine, new.summary_id),
        }
    else:
        report["new"] = {"error": "planner did not classify the frozen broad query as broad"}

    # ---- narrow routing regression (no provider call needed; the pre-gate short-circuits) ----
    report["narrow_routing"] = [
        {"query": q, "is_broad": plan_query(q, config=config, complete_fn=complete).is_broad} for q in NARROW_REGRESSION
    ]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
