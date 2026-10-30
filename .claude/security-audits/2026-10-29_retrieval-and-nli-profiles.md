# Security audit — selectable retrieval embedding profiles (Arctic S) + verification NLI profiles (DeBERTa)

**Date:** 2026-10-29 · **Status:** uncommitted (main working tree) · **Triggers:** new API endpoints (7), new
persisted setting table (migration 0085), feature spanning 3+ files / ~900 LOC. No new third-party dependency.

## Surface

| Endpoint | Purpose | Writes |
|---|---|---|
| `GET /embedding-profiles` | profile identities + coverage | none |
| `PUT /embedding-profiles/active` | select retrieval profile (409 unless index complete) | `library_settings` row |
| `POST /embedding-profiles/{key}/index` | start resumable/cancellable index build (`embedding_index_jobs`) | `embeddings` + vec rows for that profile's identity only |
| `GET /embedding-profiles/index/{job_id}` | job status | none |
| `POST /embedding-profiles/index/{job_id}/cancel` | stop after the current paper commits | in-memory cancel set |
| `GET /verification-nli-profiles` | NLI profile identities | none |
| `PUT /verification-nli-profiles/active` | select NLI profile (loads + verifies checkpoint first; 409 on mismatch) | `library_settings` row |

## Threat review

- **Input validation / injection.** Profile keys are looked up in fixed in-code dicts (`PROFILES`, `NLI_PROFILES`);
  an unknown key → 404 before any work. Request bodies are pydantic-bounded (`key` 1–40 chars). Job ids index an
  in-memory `JobStore`; no id or key reaches SQL text or a filesystem path. All SQL is SQLAlchemy Core with bound
  parameters (rule #3); the coverage query is a fixed statement over constant columns.
- **Vector-space integrity (the feature's main correctness risk).** Same-dimension profiles share one sqlite-vec
  table. Every production `vector_store.search` passes `candidate_embedding_ids` built from the querying model's full
  identity (`model_name`, `model_version`, `dimension`, `normalization`). An AST test fails if a new `.search(` on a
  store omits it (and asserts it still sees ≥6 call sites, so it cannot go vacuous). A behavioral test with
  deliberately reversed vectors in one shared store proves no mixing. A pre-existing gap was closed:
  `critical_review_set.set_chunk_embedding_ids` had no model-identity filter at all.
- **Fail closed, never silently degrade.** A profile with `lazy_indexing=False` never embeds on the fly inside Ask;
  an incomplete index raises `IncompleteEmbeddingIndexError` (Ask fails with a message naming the gap and both
  remedies). Selection of an incomplete index is refused (409). An unknown stored key falls back to the baseline.
  A checkpoint whose pooling / max sequence length (Arctic) or label order / architecture / tokenizer (DeBERTa)
  differs from the profile contract is refused before any vector or score is produced.
- **No silent scoring-scale substitution.** Verification similarity stays on MiniLM (its 0.70 gate is never applied
  to Arctic cosines); NLI thresholds are unchanged per profile and the UI/provenance state they were calibrated on
  MiniLM2. A synthesis records `retrieval_embedding` / `verification_nli` provenance when a non-baseline profile ran.
- **Data egress.** None of library content. All inference is local. First use of a profile whose pinned weights are
  not cached would fetch those weights from the Hugging Face Hub at the pinned revision — the same model-fetch
  posture the existing MiniLM/NLI loaders already have; no library text, query or identifier is sent.
  `use_safetensors=True` is retained (no pickle loading). Verified offline (`HF_HUB_OFFLINE=1`) on this machine.
- **Resource caps.** One index build at a time (`create_or_get_active`); per-paper commits bound transaction size;
  `embed_chunks` batches through `sql_batch`. Cancellation is cooperative between papers. Coverage queries are
  aggregate counts. NLI selection loads one ~700 MB checkpoint synchronously; it is tracked in Status as Local AI.
- **Corpus immutability.** Index builds add rows for the new identity only; no paper/chunk row and no baseline vector
  is modified or deleted. Measured on a disposable copy of the 251-paper DEV library: MiniLM coverage 42,044/42,044
  before and after; Arctic rows added only under its own identity.
- **Secrets / auth.** No secrets involved. Endpoints sit behind the existing `AccessControlMiddleware` (gated when
  Remote access is on; read-only mode 403s the PUT/POSTs like any mutating route).

## Negative-path checks (concrete results)

| Check | Result |
|---|---|
| PUT retrieval profile `../../etc` | 404 |
| PUT empty key / 41-char key | 422 / 422 |
| PUT `arctic-s` with incomplete index | 409 |
| POST index for unknown profile (`';--`) | 404 |
| POST index for baseline | 400 |
| GET / cancel unknown job id | 404 / 404 |
| PUT unknown NLI profile | 404 |
| PUT NLI with mislabelled checkpoint (fake `LABEL_0..2`) | 409, baseline stays active (test) |
| PUT NLI malformed JSON / non-UTF-8 JSON body | 422 / 422 |
| Ask with active Arctic profile and 0 indexed chunks | job `error`, "Arctic S index covers 0 of …" (test) |
| Real Arctic checkpoint vs research encoding | max abs diff 0.0, CLS pooling, max_seq 512 |
| Real DeBERTa checkpoint with wrong expected label order | refused |
| Active profiles after all negatives | `minilm` / `minilm2` (unchanged) |

Pre-existing, out of scope: a non-UTF-8 body sent with **no** content-type header makes FastAPI's own
validation-error encoder raise (500) on any JSON endpoint; not introduced here.

**Security Audit: PASS**

## Addendum (2026-10-29, recovery pass) — NLI failure fallback

Review found that `NLISupportScorer` silently substitutes embedding cosine similarity when NLI inference raises, and
the verifier then reads that cosine against the 0.55 NLI support threshold with no persisted signal. This is
**pre-existing baseline behaviour** (MiniLM2, unchanged here). For the DeBERTa profile it would also have made the
recorded `verification_nli` provenance false. Fix: `resolve_support_scorer` builds the DeBERTa scorer with
`fallback_scorer=None` over the same shared runtime, so an inference failure fails the Ask job (status `error`, the
exception in `detail`) instead of persisting embedding-derived "NLI" scores. Regression test:
`test_deberta_inference_failure_fails_the_job_instead_of_falling_back_to_embeddings`. The baseline's silent fallback
is out of scope for this change and is recorded as a follow-up.

Stored vs visible provenance: `retrieval_embedding` / `verification_nli` are persisted in `scope_ref_json` but are not
returned by the summary response or shown on the result screen. Treat this as a release-qualification gap.

**Security Audit (addendum): PASS**
