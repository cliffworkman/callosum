# Evaluation of the Callosum Planning Scaffold

**Reviewer pass over the 35-file Markdown skeleton Codex produced (2026-06-15).**
Scope of this review: structure, technical correctness, decisions deferred that shouldn't be, and gaps the plan is silent on. No implementation exists yet, so this is a plan review, not a code review.

---

## 1. Overall assessment

The scaffold is strong, and stronger than most planning passes. Three things it gets genuinely right and should not be "fixed":

- **The local-first guardrails are stated as invariants, not aspirations.** "External LLM output is never treated as authoritative citation evidence" and "the app should remain useful when offline after import" appear in `architecture.md` and are echoed consistently in `summarization/`, `gemini/`, and `integrations/`. That consistency across files is the hard part and it's there.
- **The risk register caught the four real landmines** — citation grounding being probabilistic, Zotero schema drift, Mendeley encryption, and PyMuPDF's AGPL license. These are exactly the things that sink this kind of project, and the mitigations ("build evidence extraction before polished summary UX," "keep a permissive-license PDF fallback under evaluation") are the right instincts.
- **The roadmap's acceptance benchmarks are falsifiable.** "Given a verbatim excerpt, the system can locate the correct PDF page and draw a highlight region" is a real pass/fail test, not a vibe. Most roadmaps fail here.

The weaknesses are not structural. They are (a) a handful of technical claims that are slightly wrong or stale, (b) several "Open Decisions" that are deferred but actually block Stage 1–2 and should be decided now, and (c) a few load-bearing topics the plan doesn't mention at all. The rest of this document is those three categories, ordered by how early they bite.

---

## 2. Corrections — things that are wrong or stale

These are factual or technical issues to fix in the relevant README before building against it.

### 2.1 The vector-store framing buries the lede (and may force a needless dependency)
`data/vector-store/README.md` lists sqlite-vec, Chroma, and FAISS as co-equal "candidate backends." For a personal/lab-scale library (hundreds to low thousands of papers, tens of thousands of chunks), this is a non-decision being treated as a decision. At that scale:
- FAISS is overkill and adds a heavyweight dependency.
- Chroma adds a second datastore and its own lifecycle to manage.
- **sqlite-vec keeps everything in the one SQLite file you're already committed to**, which makes the "make backup and portability straightforward" principle in `data/README.md` trivially true (one file to copy) instead of a cross-store consistency problem.

Recommendation: name sqlite-vec the **default**, with FAISS noted only as a future escape hatch if the library grows past ~100k vectors and brute-force search gets slow. Delete Chroma from the plan unless there's a concrete reason for it; carrying a candidate you won't pick is planning debt. This also resolves the `data/sqlite/` open decision "whether vectors live inside SQLite or beside it" — inside.

### 2.2 "BERTopic-like topic modeling" for the abstract first pass is heavier than the goal needs
`clustering/README.md` lists "automatic first pass from abstracts using BERTopic-like topic modeling" alongside the user-axis scoring. BERTopic pulls in UMAP + HDBSCAN + a topic-representation layer — a real dependency stack, and its output (discovered topics with c-TF-IDF labels) is *not* the same shape as the user-defined nested axis tree that is the actual product. There's a risk of building an elaborate unsupervised pipeline whose output you then have to reconcile with the hand-defined hierarchy.

Recommendation: for V1, make the first pass the **cheap version of the thing you already need** — embed abstracts (you're embedding them anyway) and run plain agglomerative clustering to *propose* a starting grouping the user immediately reshapes. Keep BERTopic explicitly as a Stage 3+ enhancement, not part of the first guided-clustering milestone. The `product-scope.md` "first pass clustering from abstracts proposes a starting tree, you reshape it" is satisfied by the lighter approach; BERTopic is a way to make the *proposal* smarter later, not a V1 requirement.

### 2.3 Zotero specifics that should be pinned now, not discovered at import time
`integrations/zotero/README.md` is right to treat the DB as read-only and version-sensitive, but two concrete facts belong in the plan so they're not rediscovered as bugs:
- **Annotations live in the database, but annotation *position* data is stored as Zotero-specific JSON keyed to its own reader's coordinate model, not raw PDF bboxes.** The plan's "imported annotations tied to a document location" (in `data-contracts.md`) will need a translation step, and it won't line up 1:1 with the PyMuPDF coordinate space you use for your own highlights. Flag this now or the two coordinate systems will collide in Stage 2.
- **`linkMode` on `itemAttachments` distinguishes imported-stored vs linked-file vs linked-URL.** The `library-store/` plan mentions linked-in-place files generally, but the importer README should name `linkMode` explicitly as the field that drives copy-vs-link behavior, because a linked file may not exist on this machine at all (common when a library moved between computers). "Resolve attachment paths safely" should include "and record when the target is absent."

### 2.4 Gemini quota numbers are correctly flagged as volatile — add the specific recent change
`gemini/README.md` and `risk-register.md` both say free-tier limits are volatile and must be verified. Good. Add the specific datum so future-you knows the baseline shifted recently: **Google cut free-tier daily request quotas substantially in December 2025, and the strongest Gemini models moved behind a billing account.** The practical consequence for the plan: design Stage 4 around Flash / Flash-Lite class models and *batch* summarization, and treat "summarize my whole library in an afternoon" as a paid-tier or local-LLM path, not a free-tier assumption. This is worth one sentence in the Gemini README's Constraints section.

### 2.5 OpenAlex now requires a key — the plan hedges where it can be definite
`openalex/README.md` says "store and use a user-provided API key *if required*" and "API-key requirements and pricing may change." As of early 2026 this is no longer conditional: **OpenAlex began requiring a free API key, and introduced usage-based pricing with a free daily allowance.** Make the key non-optional in the adapter design and add the bulk data-dump as the documented fallback for any bulk enrichment (it sidesteps per-request limits entirely). The hedge is now stale; state it as fact with a date stamp per the `research/README.md` rule.

### 2.6 "Semantic Scholar intents ≠ support/contrast" is correct — make sure discovery honors it
`semantic-scholar/README.md` correctly keeps intents (Background/Method/Result) distinct from stance. But `discovery/README.md` lists both "Semantic Scholar for citation contexts, intents" and "local claim-support estimation through retrieval plus stance classification" without stating that the stance signal must come from the *latter*, never the former. Add one line to `discovery/` making explicit that support/contrast is computed locally (NLI over citation contexts), and S2 intents are at most a coarse pre-filter. This prevents a future contributor from wiring intents straight into a "supported/contrasted" UI badge, which would be wrong and would erode exactly the trust the project is built to earn.

---

## 3. Decisions deferred that actually block early stages

`Open Decisions` sections are appropriate for genuinely-later choices. These specific ones are listed as open but gate Stage 1–2 and should be decided before code, because the cost of changing them after data exists is high.

### 3.1 Canonical metadata shape (`data-contracts.md` "Contract Questions")
"Full CSL-JSON, a subset, or an internal model with CSL export" is the foundational schema decision and everything downstream keys off it. Defer this and the importer, the API, and the frontend all get built against a moving target.
**Recommendation:** internal normalized model (real columns for the fields the UI and search need) **plus a stored verbatim CSL-JSON blob** for round-trip fidelity and export. This is the standard answer and it's what lets you both query efficiently and regenerate clean bibliography output. Decide it now; it's cheap to state and expensive to retrofit.

### 3.2 Copy vs link as the default PDF storage mode (`library-store/` open decision)
This isn't a preference toggle to design later — it determines the entire integrity story (checksums, missing-file handling, dedup) and interacts with the Zotero `linkMode` issue in 2.3. **Recommendation for V1:** default to **copy into a managed store** (content-addressed by checksum), because it makes the library self-contained, makes "remain useful offline" true without depending on Zotero's folder staying put, and makes the highlight/coordinate cache stable. Offer link-in-place as an explicit opt-in later. State the default now so the schema and importer are built once.

### 3.3 SQLite access pattern (`app/backend/` open decision)
"SQLModel, SQLAlchemy, raw SQL, or another" is fine to leave loose on most projects, but here the schema is the spine of the whole system and migrations will happen often in early stages (every chunking-strategy or embedding-model change touches it). **Recommendation:** pick SQLAlchemy Core (not necessarily the full ORM) + a migration tool (Alembic) now, *or* commit to raw SQL with a hand-rolled migration table — but decide, because "we'll add migrations later" is how Stage 2 re-extraction silently corrupts Stage 1 data. The `data/sqlite/` "migration tool" open decision is the same decision and should be answered in the same place.

### 3.4 Frontend framework + pdf.js-direct-vs-wrapper (`app/frontend/` open decisions)
These two are listed as open and they're entangled: the highlight-overlay milestone (Stage 2's frontend validation) depends on having direct enough access to pdf.js's `viewport.convertToViewportRectangle` to draw bbox overlays. A heavy wrapper can hide exactly the API you need. **Recommendation:** decide the framework before Stage 2 (the existing JSX mockup implies React, which is a fine default), and plan to use **pdf.js directly** for the reader rather than a turnkey viewer component, specifically so the coordinate-overlay path stays under your control. The mockup is a styling reference; the reader is the one place to not abstract early.

---

## 4. Gaps — load-bearing topics the plan doesn't mention

These aren't wrong; they're absent, and each will cause real pain if it stays absent.

### 4.1 No deduplication / identity-resolution contract
The plan preserves DOI, OpenAlex ID, S2 ID, Zotero key, citation key (good), but never says **how two records are judged to be the same paper.** This matters the moment you (a) import from more than one source, (b) enrich an imported paper with OpenAlex metadata, or (c) accept a "missing literature" suggestion that's already silently in the library. Without a stated match precedence (DOI exact match → normalized title+year → fuzzy), discovery will suggest papers the user already has, and enrichment will create duplicates. Add a short "Identity resolution" section to `data-contracts.md` with the match precedence.

### 4.2 The verification confidence score is never operationally defined
This is the most important gap. The entire trust proposition rests on the confidence number in the provenance card, and `summarization/` says to match sentences "using embeddings and lexical overlap" and store a confidence — but **nothing states what the number means or how it's computed.** Embedding cosine similarity alone measures topical relatedness, not *support*; a sentence can be 0.9-similar to a chunk that actually contradicts it. The plan needs to commit, at least provisionally, to a definition: e.g., confidence = f(embedding similarity, lexical/quote overlap), with an **NLI entailment check** as the thing that distinguishes "related" from "supported," and the threshold(s) treated as a tunable evaluated in `research/`. This belongs in both `summarization/README.md` and `data-contracts.md` (the EvidenceQuote "confidence scores," plural, is currently undefined). Until this is pinned, "verified" has no agreed meaning, and that's the one word the product can't be vague about.

### 4.3 No statement of what happens when extraction or grounding *fails*
The plan tracks "extraction quality and failures" but never says how a paper with no usable text layer (scanned PDF, no OCR) flows through the rest of the system. Can it be clustered (abstract-only)? Can it be cited in a summary if there are no chunk coordinates to ground to? **Recommendation:** add a "degraded states" note — a paper can exist at metadata-only, abstract-embedded, or fully-chunked tiers, and the summarizer must refuse to emit a *verified* citation for a paper that never reached the chunked tier (it can still be flagged unverified). This connects 4.2 and the risk register's PDF-variability risk and prevents the failure mode where a scanned paper gets a falsely "verified" badge because the matcher found something.

### 4.4 No data lifecycle / re-extraction story
`pipelines/README.md` says each stage should be resumable and cacheable (good), but nothing addresses **invalidation**: when the embedding model or chunking strategy changes (explicitly anticipated in `embeddings/`), every chunk, every embedding, and every stored citation mapping built on the old chunks is now stale. Stored summaries point at chunk IDs that may no longer mean the same span. Add a "reprocessing and invalidation" note to `data/` or `pipelines/` stating that chunk and embedding records carry a strategy/model version, and that summaries record which chunk-version they were verified against, so a model change marks dependent summaries as needing re-verification rather than silently mis-pointing. This is the single most likely source of "the highlight jumps to the wrong place" bugs six months in.

### 4.5 Secrets handling is mentioned but not specified, and it touches a governance constraint
`ops/README.md` lists "how to store secrets locally" as an open decision. For a tool that may eventually touch IRB-governed material, "send PDF text to Gemini's free tier" is not a neutral default — free-tier inputs can be used to improve the provider's models. The Gemini README notes free-tier data-use terms "may not suit sensitive libraries," which is right, but the plan should go one step further and state a **per-library or per-action setting that governs whether any content leaves the machine**, defaulting to off for anything not explicitly cleared. This is cheap to design in now and effectively impossible to bolt on credibly after the fact. (Flagging this specifically because the intended user base includes people working under data-governance constraints where this isn't optional.)

### 4.6 No evaluation corpus is named
`research/` plans embedding comparisons, threshold experiments, and clustering reviews, and `tests/fixtures/` plans small legally-safe inputs (good). But there's no plan for a **held-out, ground-truthed evaluation set** for the one thing that most needs it: citation grounding. To tune the 4.2 threshold you need a set of (sentence, chunk, is-actually-supported) triples with human labels. Add to `research/` a note to build a small (~50–100 item) hand-labeled grounding eval set early, because every threshold and model decision downstream is unfalsifiable without it.

---

## 5. Smaller notes

- **`README.md` references two files not in the archive** — `opus4.8_callosumIdea_deepResearch.md` (source brief) and `callosum-reference-manager.jsx` (UI reference). They're cited across several docs but absent from the zip. Either add them to the repo or change the references to note they live elsewhere, so a fresh contributor isn't hunting for missing files. (Note also the filename in the brief reference, `callosum-reference-manager.jsx`, vs the mockup file as currently saved — keep one canonical name.)
- **`desktop-shell/` is correctly deferred.** No change needed; the "Deferred Until" gating is exactly right. Resist any pull to start it early.
- **The `ops/` Windows-native-vs-WSL2 open decision can stay open** — it genuinely is later — but add one line: GROBID (Docker) strongly prefers WSL2/Linux, so if GROBID lands in V1, that decision is effectively made for the extraction step. The two decisions are linked.
- **`tests/` should name the highlight-fidelity benchmark as the gate it implicitly is.** The README already says it's "the most important early benchmark"; make it an explicit blocking acceptance test for Stage 2 in `roadmap.md` so it can't be skipped under time pressure.
- **Consider one global glossary.** Terms like "chunk," "axis," "evidence mapping," "citation mapping," and "claim" are used consistently (impressive), but a single `docs/glossary.md` would lock the vocabulary before multiple contributors (human or model) start drifting it. Cheap insurance given how much the data contract leans on precise terms.

---

## 6. Suggested immediate actions, in order

1. Pin the canonical metadata shape (§3.1) and add an identity-resolution section (§4.1) to `data-contracts.md`. Everything keys off these.
2. Define the verification confidence score and the "verified vs related" distinction (§4.2), plus degraded-paper states (§4.3), in `summarization/` and `data-contracts.md`. This is the trust spine.
3. Decide copy-vs-link default (§3.2), SQLite access + migrations (§3.3), and the chunk/embedding versioning + invalidation story (§4.4). These prevent early data corruption.
4. Set sqlite-vec as the default vector store (§2.1) and downgrade BERTopic to a Stage-3 enhancement (§2.2).
5. Fix the stale external-API facts (§2.4 Gemini, §2.5 OpenAlex) with date stamps, and add the data-egress / sensitive-library setting (§4.5).
6. Resolve the missing referenced files and add a glossary (§5).

None of this requires restructuring the scaffold. It's a focused second planning pass on the four or five load-bearing contracts, after which Stage 1 can start against stable ground.

---

*The scaffold is in good shape. The corrections above are the difference between a plan that reads well and a plan that survives contact with real PDFs and a real embedding-model swap. The two that matter most, if you only do two: define what "verified" actually computes to (§4.2), and decide the chunk/embedding versioning story before any data is written (§4.4). Those are the ones that are nearly free now and very expensive later.*
