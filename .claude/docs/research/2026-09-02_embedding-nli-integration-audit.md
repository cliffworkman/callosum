# Embedding/NLI model integration audit (2026-09-02)

Read-only audit, mirroring `2026-09-01_llm-provider-integration-audit.md`'s process and the
increments (557-561) it led to. That audit covered the LLM-provider boundary (Gemini/OpenAI/
Anthropic/local/managed-local generation calls); this one covers callosum's other two always-local
model families: the **embedding model** (`all-MiniLM-L6-v2` default, plus the SPECTER variant
`sentence-transformers/allenai-specter` used by Overlooked-Work/Publishers) and the **NLI model**
(`cross-encoder/nli-MiniLM2-L6-H768`, backing citation-verification support/contradiction and
Critical-Review/Suggest-Citation stance classification). No code has changed as a result of this
pass — findings only, for a Codex ping-pong cycle to follow, same pattern as the LLM audit.

**Method:** three parallel research passes covering (1) every backend call site resolving/using the
embedding model, (2) every backend call site resolving/using the NLI model, (3) the frontend/
Settings/Status-popover/dev-tooling surfaces for both. Four of the highest-stakes, and two
independently-cross-validated, findings were then spot-checked directly against the code before
writing this document: `critical_review.py`'s `_run_set_tier2`, `citations/suggest.py`'s stance
loop, `wip_critical_review.py`'s degrade path, and `papers.py`'s reprocess-pdf handler — all four
confirmed exactly as reported.

**Explicit non-finding, stated up front so it isn't assumed later:** registration comparison
(`app/backend/registration_comparison/`) has **no NLI touch point at all** — grepped and confirmed
zero hits for `NLI|stance|Stance|CrossEncoder|support_scorer|classify_stance`. Its "semantic
interpretation" step is explicitly deferred to the human reader; its LLM triage is Gemini-only. Any
initial assumption that this feature area used NLI was wrong and is corrected here.

---

## 1. DB-transaction-boundary-across-model-call bugs

The same bug class increment 561 just fixed for the LLM-provider layer (`summarize_scope`'s 3-phase
restructure) — a long-held SQLite write transaction spanning a slow model call — recurs at several
sites the LLM audit didn't reach, because embedding/NLI calls are usually fast (so the pattern is
easy to miss) but are **not** fast on a cold Hugging Face cache (first real use, or a corrupted-cache
re-download), when they become exactly the same shape of problem.

- **`_run_set_tier2`** (`app/backend/api/routers/critical_review.py:445-510`) — **the sharpest
  finding in this audit.** `with engine.begin() as conn:` (line 476) is a write transaction that
  spans `generator.propose(set_papers)` (an LLM call — remote or managed-local) **and**
  `verify_set_candidates(...)` (NLI stance classification) **and** the subsequent
  `repo.insert_candidates` writes, all before the block closes at line 497. Spot-checked and
  confirmed line-for-line. This site is already named in the Codex handoff doc
  (`2026-09-01_codex-local-ai-audit-handoff.md`) as "the single highest-risk remaining site" from
  the LLM-provider angle alone; this audit adds that the NLI call sits on the exact same held
  connection, so a broken/cold NLI model is a second, independent way this site can fail badly. The
  module's own inline comment ("no DB connection is held during either provider call") is only true
  of the *later* triage step (a separate `conn2` at line 503) — it does not describe line 476-497.

- **`generate_candidates`** (`critical_review.py:252-304`) — single-paper Tier 2, the synchronous
  (foreground) sibling of the above. `conn: Connection = Depends(get_connection)` is held across
  `generator.propose(...)` (line 289), `verify_candidates(...)` (NLI, lines 292-298), and
  `repo.insert_candidates` + `conn.commit()` (line 303). Same shape, worse in one respect (it's a
  synchronous request, so the user's browser is blocked, not just a background job).

- **`reprocess_paper_pdf`** (`app/backend/api/routers/papers.py:202-225`, `POST /papers/{id}/
  reprocess-pdf`) — spot-checked and confirmed. `conn: Connection = Depends(get_connection)`
  (implicit-autobegin). `reprocess_pdf_attachment(conn, ...)` internally deletes old chunks, creates
  new ones, **then** calls `embed_chunks()` — all writes happen *before* the embedding call on the
  same connection, so the writer lock is already escalated when `model.encode_texts()` runs. Only
  `PdfReprocessEmptyExtraction` is caught (line 223); any other exception (a cold-cache download
  stall, a corrupted cache, an OOM) is **uncaught**, propagating as a raw 500 while the write lock is
  held.

- **`_run_text_reprocess_job`** (`app/backend/api/routers/text_health.py:138-180`) — the bulk
  version of the above. Unlike every sibling ingestion job (see §5), this one wraps its **entire
  multi-paper loop** in one `engine.begin()` rather than per-item `commit_each` transactions. On a
  cold model cache, paper 1's embedding call can hold the writer lock for the whole remaining batch.

- **`_run_ocr_job`** (`app/backend/api/routers/ocr.py:102-139`) — same shape (writes precede
  `embed_chunks` inside one `engine.begin()`), lower severity: single paper, and it already has a
  job-level `except Exception` so a failure degrades to a job error rather than a raw crash.

- **Citation-context's background job** (`app/backend/api/routers/citation_context.py:119-156`) —
  the worst *combination* found in this audit: `with app.state.engine.begin() as conn:` (line 124,
  a write transaction) spans a **live network call** to Semantic Scholar (using the same `conn` for
  its own cache read/write) **and then** up to 500 unbatched single-item NLI calls (see §2). A cold
  model cache here means an open SQLite write lock held across real HTTP I/O plus up to ~500 failed
  local-model load attempts (see §7), all serialized.

- **Residual gap in the feature inc 561 just hardened**: `summarize_scope`'s Phase 1 (retrieval —
  `_rank_chunks_for_query`, which can call `embed_chunks`/`encode_texts` for a query-scoped
  synthesis) and Phase 3 (verify+persist — `verify_many`'s embedding lookup + NLI support/
  contradiction calls) both still run inside their own (short) `engine.begin()` write transactions.
  Inc 561 deliberately only moved the *LLM provider* call (Phase 2) out from under a held
  connection; it didn't claim, and doesn't achieve, the same for the embedding/NLI calls still
  living in Phase 1/3. In the common case (warm cache) these are fast and this is genuinely
  low-risk — but on a first-use cold cache, Phase 1 or Phase 3 can itself become a slow,
  download-triggering call sitting inside a write transaction, the identical bug class, just not
  extended to these two calls. Worth a deliberate accept-or-extend decision on this specific
  residual, rather than silently leaving it unexamined given how recently and carefully this exact
  file was restructured.

---

## 2. Unbatched-loop violations (LATENCY.md's batching invariant)

- **`citations/suggest.py:117`** (`suggest_citations`, backing `POST /citations/suggest` —
  Suggest-Citation / highlight-to-suggest) — **independently found by both the embedding-model and
  NLI-model research passes; highest-confidence finding in this audit.** Spot-checked and confirmed:
  `for hit in ranked: ... stance = scorer.classify_stance(sentence=query, passage=chunk_text) ...`
  (line 112-117) calls the NLI scorer once per candidate instead of the codebase's own pre-existing
  batched `classify_stances(scorer, pairs)` helper (`summarization/stance.py`) — every other
  multi-item NLI consumer in the codebase (citation verification's `verify_many`, Critical Review's
  `search_contested_claim_scopes`/`verify_candidates`/`verify_set_candidates`) correctly batches.
  Up to `MAX_SUGGESTIONS=20` sequential NLI calls per request, on a synchronous, frequently-fired,
  interactive endpoint (every highlight-to-suggest action).

- **`app/backend/citations/beyond_library.py:251`** (`suggest_beyond_library`) — same shape, same
  request path (`POST /citations/suggest` with `include_beyond_library=True` calls both this and the
  above), up to 20 more unbatched calls. Combined, one request to this endpoint can issue up to **40
  sequential single-pair NLI calls**, directly blocking a foreground, cite-while-you-write UI action.

- **`app/backend/methods/citation_context.py:81-99`** (`classify_citation_contexts`) — up to
  `MAX_ITEMS=500` (`:22`) individual `stance_scorer.classify_stance(...)` calls in a loop (line 92),
  instead of a batched call. Combines with §1's transaction finding on the same feature.

**Confirmed correctly batched** (stated so the fix scope reads as bounded, not systemic): citation
verification's `verify_many` (one embed batch + one NLI batch per summary), Critical Review's
`search_contested_claim_scopes`/`verify_candidates`/`verify_set_candidates`, `embed_chunks`/
`embed_papers` themselves, axis-suggestion (`axis_suggestion.py`), duplicate-detection
(`duplicate_detection.py`), discovery/relevance (`discovery/relevance.py`), My-Publications domain
decomposition, Overlooked-Work (`overlooked_work.py`/`overlooked.py`), and Publishers
(`publishers.py`) — each issues one batched `.encode_texts(...)` call for its whole item set, not
one per item.

---

## 3. Crash-uncaught on synchronous endpoints — the Wave-1 hardening never reached this layer

Increment 557's "Wave 1" sweep caught every unguarded `resolve_llm_config()` call site in the
codebase. The embedding/NLI auxiliary layer never got an equivalent pass — several everyday,
synchronous, no-JobStore endpoints call resolve→encode→search with **zero** exception handling,
relying entirely on the callees never raising:

- **`POST /citations/suggest`** (`app/backend/api/routers/citation_suggest.py:107-144`) — no
  try/except around `resolve_embedding_model`/`suggest_citations`/`suggest_beyond_library` at all.
- **`POST /discovery/relevance`** (`app/backend/api/routers/discovery.py:93-103`) — same, backs both
  Search and Feed's axis-relevance highlighting; a second everyday, high-traffic, zero-handling site.
- **`POST /papers/{id}/registration-evidence/retrieve`**
  (`app/backend/api/routers/registration_retrieval.py:71-125`) — same, plus (see §8) this is one of
  the two sites already named in inc 560's own notes as needing a friendlier `local_files_only`
  failure message, still unaddressed.

Contrast with every background-job call site audited: all have at least an outer
`except Exception: jobs.mark_error(...)`, so a model failure degrades to a job-error status rather
than an uncaught 500 — the asymmetry is specifically a **synchronous-endpoint** gap.

---

## 4. Silent systemic degradation on ingestion — a new bug class this audit surfaces

Five independent ingestion background jobs — folder scan (`library.py:114-149`), citation import
(`library.py:415-453`), bundle import (`library.py:533-563`), native Zotero import
(`library_zotero.py:89-140`), and E2E-sync share import (`sync_shares.py:305-339`) — all route their
per-paper `embed_chunks`/`embed_papers` calls through the shared `commit_each(engine, ...,
on_item_error="skip", ...)` (`persistence/sqlite_retry.py`). Individually this is good design (a
per-item committed transaction, one bad PDF doesn't sink the batch) — but `commit_each` catches
`Exception` broadly per item with **no distinction between "this one PDF's text was malformed" and
"the embedding model itself is completely broken."** A systemically-broken model (corrupted HF
cache, persistent OOM) makes *every* item in *every* one of these five jobs individually "skip" —
and the outer job still calls `jobs.mark_done(...)` with a normal-looking summary
(`imported: N`, `papers_created: N`, etc.). Nothing tells the user that vector search/retrieval is
now silently broken for everything they just imported. This is a single shared root cause reproduced
identically across five features — fixing `commit_each`'s error classification (or adding a
"systemic failure" circuit-breaker) would close all five at once.

---

## 5. Model-identity/staleness correctness gaps

- **`other_paper_chunk_embedding_ids`** (`app/backend/methods/critical_review.py:485-505`,
  single-paper Critical Read's candidate pool) has **no** `model_name`/`model_version`/
  `normalization` filter — unlike its WIP sibling `library_article_chunk_embedding_ids` (lines
  508-539, correctly filtered) and unlike every other candidate-id producer audited
  (`embeddings/retrieval.py::_candidate_embedding_ids`, `axis_scoring.py`'s
  `PaperEmbeddingRepresentation`, `verification.py::_chunk_embedding_ids`,
  `pipeline.py::_chunk_embedding_ids_for_chunks`). Since `sqlite-vec` partitions storage by vector
  *dimension* (not model identity), a foreign-model embedding of a different dimension is silently
  invisible here (reduced recall, not corruption) — but two models sharing a dimension (plausible;
  several sentence-transformers models are 384-dim, MiniLM's own size) would genuinely enter the
  same similarity search as the query vector, producing a confident-looking but meaningless cosine
  score with no signal that it happened. Concrete, minimal fix: mirror the sibling function three
  call sites away.

- **`find_stale_embeddings()`** (`app/backend/embeddings/pipeline.py`) is correctly implemented
  (detects `"embedding-model-changed"` by comparing stored `model_name`/`model_version`/
  `dimension`/`normalization` against the currently-configured model) and **entirely dead code** —
  its only callers are its own test file. No endpoint, Settings action, or `JobStore` job ever
  invokes it. `.claude/staged-harnesses/embedding-drift.md` (status `drafted`, not `active`) is the
  project's own acknowledgment of the gap, but understates that the detector itself already exists
  and works — what's missing is anything that calls it.

- **No end-user path to switch the embedding model exists at all.** Grepped the whole frontend for
  `MiniLM`/`bge-base`/`embed_model`/`local_files_only` — the only hit is a read-only display of a
  past run's recorded model name (`08x_methods_critical.jsx:331`), never a control.
  `app_settings.py` and `settings.py`'s request/response models have no embedding-model field at
  all. `bge-base-en-v1.5` (named in CLAUDE.md and the public `how-it-works.html` as "also supported")
  is real only in the sense a developer could hand-edit `SentenceTransformerEmbeddingModel(name=...)`
  in code — per `INCREMENT-04-NOTES.md`'s own original phrasing, "can be used by passing a different
  model name/version." There is no shipped path to it. This also reframes the "would a model switch
  silently mismatch?" question: since a live switch can't happen today, the real risk is what
  *would* happen if this were ever wired up without also wiring `find_stale_embeddings` to a real
  re-embed job — not silent wrong-distance math, but near-total silent search-coverage loss for any
  content left un-migrated (old-model chunks sit in a `sqlite-vec` table for the *old* dimension;
  a query encoded with the new model can never find them there).

- **`default_support_scorer`/`default_stance_scorer`** (`verification.py`, `stance.py`) — the
  fallback constructors used when `LocalCitationVerifier`/`suggest_citations` receive no explicit
  scorer — both construct their scorer with no `revision=`, bypassing `PINNED_MODEL_REVISIONS`.
  Currently dead in production (every real router call site passes the explicit, pinned
  `resolve_support_scorer`/`resolve_stance_scorer` result) — a live trap for a future caller that
  omits the argument, not an active bug today.

---

## 6. Status/progress popover gap (invariant #5)

`library_scan_jobs` sits in `STATUS_HIDDEN_STORES`
(`app/backend/api/routers/status.py:40-42`) alongside `wip_scan_jobs`, both justified by the same
"routine, high-frequency, would crowd out actionable work" rationale. Verified the two are **not
equivalent**: `wip_scan_jobs` is pure file-presence bookkeeping (no model call, exclusion is well
justified); `library_scan_jobs` does real embedding-model inference — `embed_chunks`/`embed_papers`
— for every newly discovered PDF (`library.py:141-142`), and backs **both** the manual "scan a
folder" action and the automatic watched-folder rescan, which fires on every app launch and every
window-focus event (`03_library.jsx:346-368`, `triggerWatchedRescan`). That auto-triggered path
renders **zero** UI — `rescanInFlight` is a plain `useRef`, never rendered; confirmed via grep that
no component reads it. The only place this job's progress is ever visible is the manually-opened
Watched-Folders modal (`27_scan.jsx:115`) — which satisfies invariant #5's "remains visible inline
at its source" carve-out only when the user happens to have that modal open, not for the far more
common auto-triggered case (drop files in the watched folder, switch back to the app window). This
is a real, verifiable violation of invariant #5's own stated text for this specific code path, not a
documentation nitpick — and there's no structural test catching this class of drift (the existing
regression test only asserts the two stores stay excluded, not that a hidden store contains no real
AI-model work).

---

## 7. Cold-cache first-use UX — confirmed still open, traced precisely

Increment 560's own notes explicitly left this open; confirmed still true. No UI string anywhere in
the frontend says anything like "downloading the embedding/NLI model for the first time" (grepped
broadly; the only real hits are for the unrelated managed-local **generation** LLM's own, separately
built download UX). The three `local_files_only=True` call sites inc 560 named
(`registration_comparisons.py:313`, `registration_retrieval.py:93`, and — see the correction in §9 —
`wip_critical_review.py`) still raise/propagate whatever raw `sentence-transformers`/
`huggingface_hub` exception a cold cache produces, with no translation to an actionable message,
except where §9 corrects that.

**Traced exactly where this bites a real user**: `embed_chunks`/`embed_papers` batch-encode via one
`model.encode_texts(...)` call per invocation. The first paper of a first-ever library scan/import
triggers the *first* `SentenceTransformer` construction — including any HF Hub download — inside
that single call, before any progress tick fires for that paper. The visible symptom: the scan/
import modal's progress bar reports "Processing 1/N" and then appears to hang for as long as the
download+load takes (potentially minutes), with zero explanation — visually indistinguishable from a
stall. Every subsequent paper in the same run is fast, so "slow first item, fine after" is a real,
reproducible first-run UX cliff. Onboarding doesn't pre-warm these models either — whichever
onboarding step first touches papers (`library`/`import`/`axis`) is the actual first cold load.

**A working pattern for exactly this problem already exists for a sibling feature**, making the
omission clearer: `35b_providers.jsx`'s managed-local generation LLM has a complete
`downloading_runtime`/`downloading_model`/`verifying` state machine with real byte-level progress and
friendly phase copy, wired into Status. It's Tauri/Rust-driven (a different mechanism from Python's
`sentence-transformers`), so it can't be reused directly — but it proves the UX was already designed
and shipped once, just never extended to the three auxiliary models.

---

## 8. Dev-tooling pinning bypass

Confirmed the two sites inc 560 already named — `tools/validation_harness.py` (5 direct-construction
sites) and `tools/demo/generate_demo_library_state.py` (2 sites) — both still bypass
`PINNED_MODEL_REVISIONS`. **One newly-found site, not in inc 560's list**:
`adapters/libreoffice/run_roundtrip.py:133` also constructs `SentenceTransformerEmbeddingModel(...)`
directly with no `revision=` — worth a one-line addition to that list, low urgency (CI/dev-only real
UNO round-trip harness).

**A nuance worth keeping distinct**, since it changes this from a pure non-issue to a real (if minor)
one: `tools/validation_harness.py`'s output writes only to gitignored `.local/`, genuinely never
reaching an end user — inc 560's "dev tooling, not end-user-facing" framing holds fully.
`generate_demo_library_state.py` is different: per `demo/README.md`, its output is baked into the
versioned `library-state-v1.json` fixture that ships as-is in the **public static demo** real
visitors browse on GitHub Pages (including a real cosine-scored axis this exact script computes).
No live model inference ever runs in a visitor's browser (the computation is pre-baked, by design) —
but the specific similarity scores in that public artifact were computed by a model resolved via an
*unpinned* revision, whatever happened to be cached on the maintainer's machine at generation time.
This is a real, if narrow, reproducibility gap against `demo/README.md`'s own claim that regenerating
the fixture "should produce byte-identical JSON." The other five `tools/demo/*.py` scripts that touch
embedding/NLI all construct the real app (`create_app`) and correctly get the pin automatically —
this bypass is scoped to one script, not the whole demo pipeline.

---

## 9. `NLIStanceScorer`'s retry-storm on total model failure

`stance.py`'s per-pair fallback (`_predict_with_pair_fallback`) can't distinguish "one pathological
pair" from "the model won't load at all" — on a batch failure it reruns the model load **once per
pair** in the batch (each re-entering `ManagedModelRuntime.get()`, which retries construction since a
failed load never caches `self._model`). For a total model-unavailability, this turns one failed
classification into up to N+1 failed load attempts. Combined with §2's unbatched callers, this is
concretely: `citation_context.py` up to ~500 attempts in one job; `critical_review.py`'s
`search_contested_claim_scopes` worst case (~720 pairs in one batch call) up to ~721 attempts inside
a *single* call. Contrast with `NLISupportScorer`'s better-behaved pattern: on primary-model failure
it falls back to the *already-distinct* `EmbeddingSupportScorer`, not a retry of the same broken
loader. There's no equivalent embedding-based proxy for a 3-way stance judgment, so this isn't a
simple copy-paste fix, but the retry-storm side effect looks unintentional rather than deliberately
accepted.

A second, narrower gap in the same file: `NLISupportScorer`'s "on any failure, fall back to the
embedding scorer" contract (its own docstring's framing) is not actually unconditional — if the
embedding-model fallback *itself* raises (plausible if both share one broken local-model cache), that
exception propagates uncaught. Every background-job caller has an outer `except Exception` that
absorbs this into a graceful job error, except one: `summary_reverify`
(`app/backend/api/routers/summaries.py:168-191`, a **synchronous** endpoint) only catches
`NotImportedError` — a double-model failure here would be an unhandled 500, not the friendly
"Local AI is not ready" messaging the async summarize path gives.

**`local_files_only` inconsistency, a related, cross-cutting observation**: only
`wip_critical_review.py`'s `_wip_critical_deps` explicitly forces `local_files_only=True` for both
scorers. Every other resolver call site defaults to `False`, even though several of those modules'
own docstrings promise "fully local... no egress" — meaning a cold/partial cache at those sites can
legitimately reach the Hugging Face Hub, contradicting the documented invariant. WIP is the one place
that got this right.

---

## 10. Documentation correction

`INCREMENT-560-NOTES.md` states the three `local_files_only=True` call sites "will still raise
whatever raw exception `sentence-transformers` produces when weights aren't already cached and
network access is refused." Confirmed for two of the three
(`registration_comparisons.py`/`registration_retrieval.py`) — **but not the third.**
`wip_critical_review.py`'s `_run_wip_critical_read_job` (lines 170-185, spot-checked and confirmed)
already wraps its `search_contested_claims(...)` call in its own local
`try/except Exception: search = ContestedSearchReport([], ..., "local-model-unavailable")` — a
deliberate, graceful degrade to a labeled-unavailable result, not a crash. This is the
**best-handled call site in the entire audit** — an explicit degrade rather than reliance on an
outer job-level catch. Either this was already true at inc 560 and the notes simply mis-described
it, or it was added since — either way, current `main` is better than the notes claim, and the notes
should be corrected the next time that file is touched (not urgent standalone, since the code itself
is already correct).

---

## Ranked summary

1. **`_run_set_tier2`** and **`generate_candidates`** (§1) — open write transaction spanning an LLM
   call *and* an NLI call *and* writes. Highest severity: the exact bug class inc 561 just proved
   worth a real design pass, confirmed present at two more sites, one of them already flagged
   elsewhere as the LLM audit's own highest-risk deferred item.
2. **The three crash-uncaught synchronous endpoints** (§3) — `/citations/suggest`,
   `/discovery/relevance`, `/papers/{id}/registration-evidence/retrieve` — everyday, high-traffic,
   zero model-failure handling. User-visible crash risk on ordinary use, not just an edge case.
3. **`citations/suggest.py`'s unbatched stance loop** (§2) — independently found twice, concrete,
   bounded fix (use the existing batch helper), directly improves a frequently-used interactive
   feature's latency.
4. **`commit_each`'s silent-systemic-failure blind spot** (§4) — one shared root cause across five
   ingestion features; a broken model today would make library import silently, invisibly
   non-functional while reporting success.
5. **`library_scan_jobs`'s Status/invariant-5 gap** (§6) and **the cold-cache UX gap** (§7) — real,
   traced-precisely reliability/trust issues, lower urgency than 1-4 since they're about
   discoverability/honesty of a slow operation rather than crash/correctness risk.
6. **The model-identity filter gap** (§5, `other_paper_chunk_embedding_ids`) — a real, minimal-fix
   correctness bug, currently low-probability (needs two same-dimension models in play) but cheap to
   close by mirroring the already-correct sibling.
7. **Everything else** (§5's dead `find_stale_embeddings`/no-model-switch-UI, §8's dev-tooling
   pinning, §9's retry-storm/fallback-of-fallback/`local_files_only` inconsistency, §10's doc
   correction) — confirmed real, lower urgency, a reasonable longer tail for Codex's independent
   pass to weigh in on and help prioritize.
