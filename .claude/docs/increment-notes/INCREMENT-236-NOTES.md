# Increment 236 — Library bundle SP3: re-verify an imported synthesis against my library

Completes B2. A **"Re-verify against my library"** button on an imported (relayed) synthesis re-runs the **local**
verifier over the recipient's own chunks for the same claims and **converts the synthesis in place to native** — its
statuses become the recipient's own (invariants #1/#4). This is the aligned outcome of the SP2 relay: verification
becomes the recipient's substrate's job, so the "sender's assessment" caveat is *removed* precisely because it's now
been re-checked locally. **Fully local — no egress, no LLM** (the sentences already exist; only verification runs).

Maintainer forks (AskUserQuestion): **convert in place** (the same summary becomes native); scope = **the synthesis's
source papers** (faithful — re-check the sender's evidence in my copy).

## The load-bearing reuse

The SP2 display blob already carries, per citation, the **sender's quote** + (SP3 addition) the source **identity**.
So SP3 needs no new verification machinery — it re-runs the *existing* `LocalCitationVerifier`:

- **Re-resolve** each citation's source by identity (`find_existing_paper_by_identity`) — picks up a paper added
  since import; falls back to the blob's stored `paper_id`.
- **Pick the local chunk** (`_best_chunk_for`): the chunk whose text contains the sender's quote (so the quote
  locates exactly) → else the best-by-similarity chunk in that paper → else any chunk.
- **`verifier.verify(sentence, CandidateCitation(local_chunk, sender_quote), source_chunks=[])`** — **exact**
  coordinates when the sender's quote is verbatim in my PDF (same edition), else **region**; NLI
  support/contradiction against my chunk → verified / weak / contradicted.
- **Source not in my library** → skip (no native citation). A sentence that ends with no citations is **flagged**
  (a normal native state — honest: "I can't check this claim in my library"; the claim text still shows).

## Convert in place (persist)

Recompute status (the native `summarize_scope` rule), delete any old rows, **update the same `summaries` row**
(`imported_json=NULL`, `status`, `generated_by="re-verified-from-bundle"`, `overview_json=NULL` — the sender's
overview traced *their* verified set; dropped, not re-narrated, no LLM; version stamps from `_combined_*`), write
native `summary_sentences`/`citation_mappings`/`evidence_quotes` (reuse `_persist_verification`). The summary now
reads through the **native** path — `imported` is `false`, the banner drops.

## Implemented

- **`summarization/reverify.py`** (NEW) — `reverify_imported_summary` + `_resolve_local_paper` + `_best_chunk_for` +
  `_norm` + `NotImportedError`. Reuses `LocalCitationVerifier` / `CandidateCitation` / `_persist_verification` /
  `_combined_chunk_version` / `_combined_embedding_version`.
- **`summaries.py`** — `POST /summaries/{id}/reverify` (sync; **404** unknown, **422** if not imported; reuses
  `_embedding_model` + `_vector_store` + `api.state.support_scorer` over one `engine.begin()` → `conn.commit()`).
- **`library_bundle.py`** — `_import_syntheses` now stores each blob citation's `source` identity (backward
  compatible: an older blob without it re-verifies via the stored `paper_id`).
- **`20_synthesis.jsx`** — a **"Re-verify against my library"** button in the `.synth-imported` banner → POST → on
  success set `state.result` to the response (the banner disappears; native statuses render) + refresh the history.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_reverify.py -q` → **2 passed** (hermetic, fake embed/vector/support
models): convert-to-native (`imported:false`, a chunk-backed citation, the row's `imported_json` NULL +
`generated_by="re-verified-from-bundle"`, no longer flagged; **re-resolved by identity** from a blob `paper_id:None`
+ a `source` DOI now in the library) + **422** on a native summary + **404** on a missing id; a claim whose source
paper isn't present → a **flagged sentence with no citation** (the text kept). Full suite **850 passed, 1 skipped**.
QA surface **173/173 API + 755/755 FE, 0 uncovered** (`route_54` extended; the endpoint rides `/summaries*`, the
button rides `20_synthesis.jsx`). Audit **addendum 2** to `2026-07-01_library-bundle.md` **PASS**. No egress, no LLM,
no new dependency, no migration.

**Headed-verified, no egress** (`.local/visual/drive_inc236_reverify.py`): a dest with a paper + an imported synthesis
citing it, served with fake models — open THEORY → Synthesis → load the imported synthesis → the imported banner
shows → **Re-verify against my library** → the banner **disappears** (now native) + a native citation renders; 0
console/page errors, 0 off-machine requests.

## B2 complete

SP1 (file bundle, inc 234) + SP2 (relayed syntheses, inc 235) + SP3 (re-verify, inc 236). Beyond B2 (deferred): a
*live* shared library on the account+sync layer (≈ accounts SP4). The last unstarted B-item is **B5** (mobile reading).
