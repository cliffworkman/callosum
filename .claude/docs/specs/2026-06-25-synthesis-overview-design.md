# Design spec — synthesis Overview + front-matter fix (inc 123 + 124)

**Date:** 2026-06-25 · **Status:** approved design (brainstorming Q&A) → spec under review.
**Supersedes/extends** `2026-06-25-synthesis-papers-scope-bug.md` (which captured only cause #1).

## 0. Problem (verified hands-on, fresh context)

User report: *"synthesis doesn't actually provide syntheses — no text-based summaries, just relevant sections
from papers; it should provide a summary, too."* Confirmed against `.local/validation-summarize/validation.sqlite`:

- **Summary #1** (scope **query**) → a real narrative. ✅
- **Summary #7** (scope **papers**, `paper_ids [2,1,3]`, no query — the inc-62 select-papers→summarize path) →
  `content` and every `summary_sentences.text` are **front matter**: "Original Manuscript", "Typical is
  Trustworthy…", "Social Psychological and Personality Science 1-10 © The Author(s) 2021 … DOI:", "r Human Brain
  Mapping 38:3391–3401 (2017) r", author lists. ❌

**Two root causes** (the earlier spec named only the first):

1. **Input.** The no-query papers scope orders chunks by `chunks.c.id` (= import order → the *first* chunk of each
   paper is its title page / masthead), then `_round_robin_by_paper(rows)[:top_k]` takes the first chunk of each
   paper. With no query to steer retrieval, the LLM is fed front matter. (`summarization/pipeline.py`.)
2. **Prompt / no synthesis surface.** `integrations/gemini/generator.py::_prompt` says only *"Return JSON only:
   an array of objects with keys text and citations… Do not invent citations."* — it never asks for a synthesis,
   and there is **no prose-summary surface** at all; the "summary" is just the concatenated verified sentences.
   So even good input reads extractively, and there is no narrative — the heart of the user's complaint.

## 1. Decisions (from brainstorming)

- **Output shape:** add a **separate narrative "Overview"** shown **above** the verified, cited claims. It is
  **not** presented as authoritative prose, but it is **not** a free-floating "unverified blob" either: every
  Overview statement **traces back to the verified evidence** — it works only from verified information and any
  claim it presents can be followed to the cited, evidenced claim it came from (the user's refinement
  2026-06-25). Framing: *"Overview — synthesized from the verified claims below"*, not "AI draft — unverified."
- **Overview source:** a **second LLM pass that narrativizes ONLY the verified claims** ("restate what we
  verified; add no new facts") — the most grounded option.
- **Traceability granularity: per-sentence.** Each Overview sentence is tagged with the verified-claim
  index/indices it restates (validated ⊆ the verified set; invalid refs dropped). The UI makes each Overview
  sentence clickable → highlights the cited claim(s) it came from (which carry quote/page/confidence). The
  Overview's citations are **inherited from verified claims, never LLM-invented** — so it traces to evidence
  without itself being authoritative evidence (honors invariant #1).
- **Ship as two increments:** **inc 123 = Part A** (front-matter input fix; deterministic, no egress, no
  migration). **inc 124 = Part B** (the Overview; generator + migration + frontend + egress + audit + Principles).
  Part A is the prerequisite quality fix (so the verified claims the Overview narrativizes aren't mastheads).

## 2. Part A — front-matter input fix (inc 123)

**Goal:** the no-query papers scope feeds **content** chunks, not mastheads — so the verified claims are real
body text. Deterministic and fully testable without egress.

- **New pure module `app/backend/summarization/chunk_filtering.py`** with
  `is_front_matter_chunk(text: str) -> bool` — a conservative classifier. A chunk is front-matter/non-content when
  it shows **multiple** metadata signals or a strong single one:
  - DOI pattern (`10.\d{4,}/\S+`) or `doi.org`; copyright/`©`/`(c)`/"The Author(s)"; "Article reuse guidelines",
    "journals.sagepub", "Downloaded from", "Contents lists available", "ScienceDirect"; journal volume/page runs
    (e.g. `1-10`, `38:3391–3401`); affiliation superscripts (`,1*`, `,2`).
  - **and/or** very short + low stopword ratio (title/author lines: few function words, mostly capitalized
    tokens). Threshold tuned conservatively — **err toward keeping** (a false "content" is harmless here; a false
    "front matter" only *deprioritizes*, never drops — see selection below).
- **`_source_chunks_for_scope` no-query path** (`pipeline.py`): partition each paper's chunks into
  content vs front-matter (order preserved); **round-robin across papers drawing content chunks first**, then —
  only if `top_k` isn't filled and content is exhausted — continue round-robin across the front-matter chunks;
  slice `top_k`. So every selected chunk is content when any exists; front matter is fallback-only (a paper with
  *only* front matter still contributes something — never empty). `_round_robin_by_paper` is refactored to take a
  pre-partitioned ordering (or a new `_select_no_query` helper wraps it). Query/cluster paths unchanged (query
  retrieval already ranks past front matter; the classifier is defense-in-depth there if cheaply applicable).
- **No prompt change, no migration, no egress, no frontend change.**

**Verification (no egress):** unit-test `is_front_matter_chunk` on real masthead strings (from #7) vs body
sentences; a `_source_chunks_for_scope` test asserting the papers-scope no-query selection returns body chunks,
not the front-matter first-chunks, given a seeded multi-paper fixture (mirrors the existing inc-62
`_round_robin_by_paper` coverage). pytest green; no UI verification needed (backend-only).

## 3. Part B — the evidence-traceable Overview (inc 124, recorded now)

**Goal:** a short Overview that narrativizes the verified claims, where **each Overview sentence traces back to
the specific verified claim(s) it restates** — shown above the claims, framed as synthesized-from-the-evidence
(not authoritative, not a free-floating "unverified" blob).

- **`OverviewGenerator` Protocol** (a new `summarization/overview.py`, keeping `generators.py`/`pipeline.py`
  lean): `generate(*, verified_claims: list[str], scope_ref, conn=None) -> list[OverviewSentence]` where
  `OverviewSentence = {text: str, claim_indices: list[int]}` (indices into the passed `verified_claims`). A
  `FakeOverviewGenerator` (hermetic tests) + `GeminiOverviewGenerator` (`integrations/gemini/overview.py`,
  mirrors `GeminiSummaryGenerator`; `OVERVIEW_PROMPT_VERSION`), wrapped by **`EgressGatedOverviewGenerator`**
  (`app/backend/llm/egress.py`) at the inc-58 DI seam. Prompt: *"You are given N numbered claims already verified
  against source papers. Write a brief (2–4 sentence) overview synthesizing them. Return JSON: an array of
  {text, claim_indices} where claim_indices lists the claim numbers each sentence restates. Use ONLY information
  in these claims; introduce no new facts, numbers, or citations."*
- **`summarize_scope`** gains an optional `overview_generator`. After `sentence_results` is built, collect the
  ordered `status=="verified"` sentences (their text + their `sentence_id`/`ordinal`); if **≥1**, call the
  generator, **validate each returned `claim_indices` ⊆ the verified set** (drop out-of-range refs; drop a
  sentence whose refs all dropped), map indices → the verified sentences' ids/ordinals, and store the result.
  **0 verified → no overview** (honest degenerate case). Egress off → summary generation already raised upstream,
  so the overview pass is never reached (no new 503 path); a generator error is caught → overview `None` (never
  fails the whole synthesis).
- **Storage:** new nullable `summaries.overview_json` column (JSON: `[{text, claim_ordinals:[int]}]`; Alembic
  migration, head derived from scripts per inc 99 — no hardcoded-head test edits). Exposed as `overview` on the
  summary response (`routers/summaries.py`), each item `{text, claim_ordinals}` so the client can map a sentence
  to the verified claims by ordinal. Generator injected via a router factory like `_summary_generator`.
- **Frontend (`20_synthesis.jsx`):** render the Overview **above** the claims in a labeled block — **"Overview —
  synthesized from the verified claims below"** (reuse an existing muted/eyebrow recipe; read DESIGN.md; no new
  token). Each Overview sentence is **clickable → scrolls to / highlights the verified claim(s)** it traces to
  (reuse the existing citation-flash/scroll affordance). Read-only, regenerated per synthesis (not editable —
  YAGNI vs My-Pubs).
- **Gates:** **Principles (#9)** — aligned: traceable-to-evidence (per-sentence claim links), restates only
  verified claims, citations inherited not invented, secondary/above the evidence, egress-gated, omitted when
  nothing verified; declined the authoritative-prose-eclipsing-evidence path. **Audit (#5)** — open
  `security-audits/2026-06-2x_synthesis-overview.md` (reuses the existing Gemini provider + egress gate; no new
  external service; input = library-derived verified claims → same egress class as summary generation).
  **Rule #10** — extend the synthesis QA route (route_55) to cover the overview field, the per-sentence
  claim-trace links, and the egress/empty-claims degenerate cases.

**Verification:** hermetic (FakeOverviewGenerator): overview stored + returned + rendered with the
synthesized-from-evidence label; **each Overview sentence links to ≥1 verified claim**; **out-of-range
`claim_indices` are dropped** (no LLM-invented refs survive); "only verified claims fed to the generator";
"0 verified → no overview"; egress-gate wrapper raises when off. The **real overview quality** check needs one
Gemini call = the user's egress/tokens — built + unit-tested, final eyes-on deferred to the user (or run on
request with egress enabled).

## 4. Out of scope

Rewriting the cited-claims prompt to be more "synthetic" (the claims stay verbatim-grounded evidence claims; the
Overview carries the narrative); editable/persisted overviews; caching the overview pass (a later token-spend
follow-up if the second call proves material — it's small: input is a handful of claim sentences, not full
chunks); the inc-62 "critical-review supplement" (still deferred).
