<!-- qa-coverage
api: /verification-nli-profiles, /verification-nli-profiles/active, /embedding-profiles, /embedding-profiles/active, /embedding-profiles/{key}/index, /embedding-profiles/index/{job_id}, /embedding-profiles/index/{job_id}/cancel
fe: 35i_retrieval_profiles.jsx, 20e_model_provenance.jsx
-->

# ROUTE 97 — Retrieval model profiles (MiniLM baseline / Arctic S)

**Tier:** 2 (local AI; no provider egress)
**Goal:** Exercise Settings → Library behavior → **Retrieval model**. It lists each embedding profile with its
exact model and revision and its index coverage over this library's article-fulltext passages. It also builds a
profile's index as a resumable, cancellable Status-tracked job (`embedding_index_jobs`, Local AI), and selects the
library's retrieval profile only once that profile's index is complete. Only Ask's evidence retrieval follows the
selection; citation verification always stays on the MiniLM baseline. Backend invariants are pinned by
`tests/test_embedding_profiles.py`.

## Environment

Seeded instance with ≥2 full-text papers and ≥1 metadata-only paper. Arctic S weights are already cached (or the
instance is online for the one-time pinned-model fetch). **Egress OFF.** Register console, pageerror and request
listeners before navigation.

## Standing assertions

- **Exact identity shown.** Each row shows `model_name@revision` (Arctic S: `Snowflake/snowflake-arctic-embed-s@e596f507…`)
  and its qualification text; Arctic S says it is experimental.
- **Coverage is honest.** `indexed of eligible passages` uses article-fulltext chunks of live papers only.
  Metadata-only papers are reported as "have no full text to index", never counted as index gaps.
- **No selection of an incomplete index.** The Arctic radio is disabled until coverage is complete; a direct
  `PUT /embedding-profiles/active` returns **409**. An unknown key returns 404. Building the baseline returns 400.
- **Status.** A build shows one row ("Retrieval index build", Local AI) that clicks to Settings. The inline
  ProgressBar is `managedBy="backend-job"`, so no duplicate client row appears. Progress is per paper, with a
  real current/total.
- **Cancel keeps work.** "Stop after the current paper" ends the job with `cancelled: true`. Coverage then shows a
  partial index, the button reads **Resume index build**, and a resumed build only indexes what is missing.
- **Corpus unchanged.** Building or switching never changes papers, chunks or the MiniLM vectors; the baseline row's
  coverage is unchanged by an Arctic build.
- **Verification unchanged.** After selecting Arctic S, an Ask's citations still verify against the MiniLM gate.
  The persisted synthesis records `scope_ref_json.retrieval_embedding` (profile, model_version,
  verification_embedding).
- **Fails closed.** If Arctic S is active and its index becomes incomplete (new papers imported), Ask returns an
  error naming the coverage gap and both remedies (build the index, or switch back). It never searches a partial
  index and never embeds on the fly.
- **Zero egress.** Nothing on this route contacts a provider/genai host.
- **Verification NLI model.** The same panel lists MiniLM2 NLI (baseline) and DeBERTa-v3 base NLI with pinned revisions.
  Selecting DeBERTa loads and verifies its checkpoint (label order entailment/neutral/contradiction, deberta-v2
  architecture, DebertaV2 tokenizer). A mismatch returns **409** and leaves the baseline active; while loading, the
  panel shows a ProgressBar that registers in Status. The copy states the thresholds were calibrated on MiniLM2 and are
  unchanged. A synthesis verified with DeBERTa records `scope_ref_json.verification_nli`. Stance features
  (Suggest/Critical Read) are unaffected.

- **Result-screen provenance (inc 609).** Under the retrieved-chunk line, a synthesis shows
  `Retrieval: <profile> · Verification: <profile>`, marking a non-baseline profile "(experimental)" and DeBERTa
  "thresholds calibrated on MiniLM2". The hover text gives exact model ids and revisions. The values come from that
  synthesis's `model_provenance` (its recorded run), never from the current Settings: switch profiles, then reopen
  an older synthesis, and its line must not change. A synthesis saved before inc 609 says "Models: not recorded for
  this synthesis". An imported synthesis shows no model line until re-verified, then shows MiniLM / MiniLM2.
- **NLI failure is visible (inc 609).** If the verification model fails to load or errors (either profile), Ask ends
  in an error that starts "Citation verification failed, so no synthesis was saved." No result appears, and no
  claim is ever scored by embedding similarity in NLI's place. Re-verify of an imported synthesis returns **503** and
  leaves it imported.

## Adversarial checklist

- Load Settings → exactly one `GET /embedding-profiles`; no POST is issued.
- Click Build index twice quickly → one job (the second POST joins the active job).
- Cancel mid-build, reload Settings → partial coverage, Resume available, radio still disabled.
- Resume → completes; radio enables; select → `active` becomes `arctic-s`; switch back to MiniLM → works without
  any rebuild.
- Select DeBERTa, run Ask → citations show DeBERTa support values; switch back to MiniLM2 → next Ask uses MiniLM2.
- Import a new full-text paper while Arctic is active → Ask fails closed with the coverage message.
