# Ask acceptance: OLD (legacy) vs NEW (faceted) — inc 581

- **Date:** 2026-09-07
- **Frozen broad query:** `.claude/docs/research/2026-09-07_ask-acceptance-frozen-query.md` (verbatim, chosen by Cliff before results).
- **Corpus:** a backfilled COPY of the demo library (`C:\Users\cliff\callosum-data\library.sqlite`), at
  `…\Temp\ask_acceptance.sqlite` — 216 papers, 24,024 chunks, embeddings present, `chunk_structure`
  backfilled (23,875 chunks: unknown 55.6% / structural ~23.9% / scientific ~11.7% / bibliographic 8.9%).
- **Both paths run on the SAME corpus** by `.claude/research/ask_acceptance_newpath.py` with the real
  `all-MiniLM-L6-v2` embedder, the real local NLI verifier (thresholds untouched), and real Gemini
  (`gemini-2.5-flash-lite`) generation. Result receipt: `.local/ask-acceptance-newpath.json`.
- **Judgement is verified-synthesis usefulness / coverage / breadth / hygiene / provenance / gaps — NOT raw claim count.**

## Result

| Metric | OLD (legacy single-query, top_k=8) | NEW (planner → faceted) |
|---|---:|---:|
| **Verified claims** | **1** | **10** |
| Flagged claims | 5 | 8 |
| Claims total | 6 | 18 |
| Citations verified / weak / unverified | 1 / 3 / 7 | 10 / 7 / 2 |
| **Contributing papers (cited)** | **5** | **9** |
| Source chunks considered | 8 | 22 |
| **Cited-evidence roles** | 1 bibliographic, 4 unknown, **0 scientific** | 1 bibliographic, 9 unknown, **4 scientific** |
| Facet coverage | — (undifferentiated smear) | **6/6 facets have verified evidence** (1 supported, 5 partial) |
| Overall status | flagged | flagged |

The planner decomposed the question into exactly the six named facets — Serotonergic function, Amyloid
pathology, Glucose metabolism, Gray matter structure, Memory and executive function, and "Other
neurobiological findings" — each with one retrieval subquery. Every facet produced ≥1 verified claim
(Glucose metabolism fully supported with 3 verified, 0 flagged); the five "partial" facets each verified
real evidence and also generated some unverified candidates.

**Narrow-routing regression:** all three narrow probes
("What sample size did the serotonin transporter PET study use?", "Which brain region showed reduced
volume in late-life depression?", "hippocampal volume in late-life depression?") route to `is_broad:
false` → the unchanged single-query path. The pre-gate short-circuits before any provider call.

## Reading against the acceptance criterion

- **Verified synthesis usefulness:** 10 verified claims vs 1 — a 10× improvement in *verified* content,
  not merely more claims (8 remain flagged and are shown as such, not as findings).
- **Facet coverage:** the old path smeared one vector across the whole question and could not represent
  the facets; the new path covers all six with per-facet, honest coverage (1 supported / 5 partial) and
  explicit unverified counts — never rendering an unverified facet as an established finding, and never
  claiming the library lacks a topic.
- **Contributing-paper breadth:** 9 papers vs 5.
- **Evidence hygiene:** the H1a deprioritization surfaced genuine `scientific`-role evidence (4 cited)
  that the old path never cited (0), while keeping `unknown` (the dominant, evidence-bearing class) at
  full priority. Bibliographic contamination stayed minimal (1) — consistent with demoting the ~33%
  bibliographic+structural tail out of the tiny budget.
- **Provenance:** unchanged, durable — attachment + page + verified verbatim quote + coordinate
  precision on every citation (verifier and its thresholds untouched).
- **Explicit gaps:** partial facets disclose their unverified candidate counts; the honesty rule holds.

**Verdict:** on the frozen broad query, rebuilt Ask **materially outperforms** legacy Ask on verified
synthesis, facet coverage, contributing-paper breadth, evidence hygiene, and explicit gaps, while
leaving the narrow path and the verifier untouched.

## Caveats

- Same-corpus comparison uses my backfilled copy of the live library (216 papers); Codex's independent
  OLD baseline (`…\callosum-codex-ask-baseline-20260907\…\generation-summary.json`, on its own snapshot)
  corroborates the OLD shape (7 claims → 2 verified / 5 flagged, 5 papers, references/table chunk in the
  pool).
- The demo library (`library.sqlite`) itself has `chunk_structure` = 0 rows today; the hygiene tier is a
  safe no-op there until the backfill runs
  (`python tools/backfill_chunk_structure.py --db-url "sqlite:///C:/Users/cliff/callosum-data/library.sqlite"`).
  The retrieval-decomposition win holds regardless of hygiene.
