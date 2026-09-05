"""B0 vs B1 retrieval. Frozen embeddings; the ONLY manipulated variable is evidence eligibility.

Causal cleanliness rests on three choices:

* the same query vector, the same vector store, the same index -- only the
  ``candidate_embedding_ids`` set differs between arms;
* **full-depth retrieval once per arm, sliced offline.** ``SQLiteVecVectorStore._search_limit`` is
  ``min(len(candidates), top_k, max_knn_k)``, so passing a shrunken candidate set together with a
  fixed ``top_k`` would conflate "excluded a chunk" with "changed the KNN limit";
* nested, monotone policies -- each only removes -- so every reason code gets its own estimate.

Chunk text is never re-encoded. No generation runs here.
"""

from __future__ import annotations

import json
from collections import Counter

from app.backend.embeddings.models import SentenceTransformerEmbeddingModel
from app.backend.embeddings.pipeline import current_chunk_embedding_ids
from app.backend.embeddings.vector_store import SQLiteVecVectorStore
from app.backend.persistence.database import make_engine
from tools.evidence_hygiene import classify as C
from tools.evidence_hygiene.store import LIBRARY_DB, study_dir

# Non-evidential for a SCIENTIFIC CLAIM. References keep a distinct bibliographic-evidence role
# ("what did this paper cite?") -- they are scoped out of claim evidence, never deleted or erased.
POLICIES: dict[str, set[str]] = {
    "P0_production": set(),
    "P1a_running_head": {C.RUNNING_HEAD},
    "P1b_debris": {C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS},
    "P1c_references": {C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS, C.REFERENCE_ENTRY},
    "P1d_publisher": {
        C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS, C.REFERENCE_ENTRY,
        C.PUBLICATION_METADATA, C.CITATION_INSTRUCTION, C.KEYWORD_LINE,
    },
    "P1f_headings": {
        C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS, C.REFERENCE_ENTRY,
        C.PUBLICATION_METADATA, C.CITATION_INSTRUCTION, C.KEYWORD_LINE,
        C.HEADING_FRAGMENT, C.MATH_OR_SYMBOL,
    },
    # Captions are tested SEPARATELY and last. They are not assumed universally non-evidential:
    # a caption can carry a real result, it just cannot carry the proposition Ask needs.
    "P1g_plus_captions": {
        C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS, C.REFERENCE_ENTRY,
        C.PUBLICATION_METADATA, C.CITATION_INSTRUCTION, C.KEYWORD_LINE,
        C.HEADING_FRAGMENT, C.MATH_OR_SYMBOL, C.CAPTION,
    },
}

# The two frozen B0 questions, verbatim, so B1 is measured on the same fixtures.
QUESTIONS = {
    "primary": (
        "I want you to do a synthesis of the brain regions and neural systems involved in late-life "
        "depression and risk for cognitive decline or dementia. I am interested in findings from "
        "fMRI, structural MRI, and molecular imaging (amyloid, serotonin transporter, and glucose "
        "metabolism) studies, including hippocampal changes, executive dysfunction, mild cognitive "
        "impairment, and amyloid pathology. Give me a list of the brain regions or systems involved, "
        "their reported role, the construct they are associated with, and the type of evidence "
        "supporting each finding."
    ),
    "control": (
        "I want you to do a synthesis of the facial and social cues that shape how people are "
        "perceived and judged. I am interested in findings on facial anomalies and scarring, facial "
        "attractiveness, empathy, moral character, and dehumanization. Give me a list of the cues or "
        "characteristics involved, their reported effect, the construct they are associated with, and "
        "the type of evidence supporting each finding."
    ),
}

MY_PUBS_NODE = 7
TOP_K = 8


def main() -> None:
    from sqlalchemy import text as sqltext

    chunks, cal, feats, biblio, rep, labels, _diag = C.build_all()
    label_of = {x.chunk_id: x.chunk_type for x in labels}
    byid = {c.chunk_id: c for c in chunks}

    engine = make_engine(f"sqlite:///{LIBRARY_DB.as_posix()}")
    model = SentenceTransformerEmbeddingModel()
    store = SQLiteVecVectorStore()

    with engine.begin() as conn:
        axis_papers = {
            int(r[0])
            for r in conn.execute(
                sqltext(
                    "SELECT DISTINCT cnp.paper_id FROM cluster_node_papers cnp "
                    "JOIN cluster_nodes n ON n.id = cnp.cluster_node_id WHERE n.axis_id = :a"
                ),
                {"a": MY_PUBS_NODE},
            )
        }
        pool = [c for c in chunks if c.paper_id in axis_papers]
        current = current_chunk_embedding_ids(
            conn, ((c.chunk_id, c.chunk_version) for c in pool), model=model
        )
        emb_to_chunk = {e: c for c, e in current.items()}

        report: dict = {"top_k": TOP_K, "pool_chunks": len(current), "questions": {}}
        for qname, question in QUESTIONS.items():
            qvec = model.encode_texts([question])[0]
            report["questions"][qname] = {"question": question, "arms": {}}
            print("=" * 78)
            print(f"{qname.upper()}  (candidate pool {len(current)} embedded chunks)")
            print("=" * 78)
            print(f"  {'policy':<20}{'excluded':>9}{'top-8 junk':>12}{'papers':>8}  top-8 composition")

            baseline_ids: list[int] = []
            for pname, banned in POLICIES.items():
                eligible = {
                    e for e, cid in emb_to_chunk.items() if label_of.get(cid, C.UNKNOWN) not in banned
                }
                # Full-depth once, sliced offline -- see the module docstring.
                hits = store.search(
                    conn, vector=qvec, top_k=len(eligible), candidate_embedding_ids=eligible
                )
                ranked = [emb_to_chunk[h.embedding_id] for h in hits]
                top = ranked[:TOP_K]
                if pname == "P0_production":
                    baseline_ids = list(top)
                kinds = Counter(label_of.get(cid, C.UNKNOWN) for cid in top)
                junk = sum(
                    1 for cid in top
                    if label_of.get(cid, C.UNKNOWN) in POLICIES["P1g_plus_captions"]
                )
                papers = len({byid[cid].paper_id for cid in top})
                comp = ", ".join(f"{k}:{v}" for k, v in kinds.most_common(4))
                print(f"  {pname:<20}{len(emb_to_chunk) - len(eligible):>9}{junk:>9}/8{papers:>8}  {comp}")
                report["questions"][qname]["arms"][pname] = {
                    "n_excluded": len(emb_to_chunk) - len(eligible),
                    "top_k_chunk_ids": top,
                    "junk_in_top_k": junk,
                    "distinct_papers": papers,
                    "composition": dict(kinds),
                    "jaccard_vs_P0": round(
                        len(set(top) & set(baseline_ids)) / max(len(set(top) | set(baseline_ids)), 1), 3
                    ),
                    "chars_in_top_k": sum(len(byid[cid].text) for cid in top),
                }

            arms = report["questions"][qname]["arms"]
            print(f"\n  displacement vs P0 (Jaccard of top-8): "
                  + ", ".join(f"{k.split('_')[0]}={v['jaccard_vs_P0']}" for k, v in arms.items()))
            print(f"  context chars in top-8: "
                  + ", ".join(f"{k.split('_')[0]}={v['chars_in_top_k']}" for k, v in arms.items()))

            best = arms["P1g_plus_captions"]["top_k_chunk_ids"]
            print(f"\n  P1g top-8 for {qname}:")
            for i, cid in enumerate(best, 1):
                c = byid[cid]
                print(f"    #{i} c{cid} p{c.paper_id} [{c.section or 'NULL'}] "
                      f"({label_of.get(cid)}) {' '.join(c.text.split())[:92]}")
            print()

    out = study_dir() / "b0_vs_b1_retrieval.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"wrote {out.name}")


if __name__ == "__main__":
    main()
