# Portable Library Bundle — B2 SP3: re-verify an imported synthesis against my library

**Status:** approved (brainstorm 2026-07-01, AskUserQuestion). Extends SP2 (relayed syntheses, inc 235).
**Maintainer forks:** **convert in place** (the imported synthesis becomes native); scope = **the synthesis's source
papers** (faithful — re-check the sender's evidence in my copy).

## Goal

A **"Re-verify against my library"** action on an imported synthesis re-runs the **local** verification pipeline
over the recipient's own chunks for the same claims, turning the relayed artifact into a native, locally-verified
synthesis. **Fully local — retrieval + NLI + quote-location; no egress, no LLM** (the sentences already exist; only
verification runs). This is the aligned outcome of the SP2 relay: verification becomes the recipient's substrate's
job (invariants #1/#4 satisfied — the statuses are now *mine*, not the sender's).

## How (per imported sentence + citation)

The SP2 display blob (`summaries.imported_json`) already carries, per citation, the **sender's quote** + the resolved
local `paper_id`. **SP2 blob addition (backward-compatible):** `_import_syntheses` now also stores each citation's
**source identity** (`"source": {identity}`) so re-verify can *re-resolve* (a paper added since import is picked up;
an old blob without it falls back to the stored `paper_id`).

For each imported sentence's citation:
1. **Resolve the source paper locally** — `find_existing_paper_by_identity(source)` (else the blob's `paper_id`).
2. **Source not in my library** → **skip** (no native citation written). If a sentence ends with zero citations it is
   **flagged** (a native flagged sentence with no verified citation — honest: "I can't check this claim in my
   library"; the claim text still shows).
3. **Source present** → pick the local chunk to check: the chunk whose text **contains the sender's quote**
   (normalized substring) else the **best-by-similarity** chunk in that paper (`search_similar` filtered to the
   paper) else any chunk. Then `LocalCitationVerifier.verify(conn, sentence=<text>,
   citation=CandidateCitation(chunk_id=<local chunk>, quote=<sender quote>), source_chunks=[])`:
   - `verify` locates the sender's quote in **my** copy → **exact** coordinates when present (same edition), else
     **region**; NLI support/contradiction against my chunk → `verified` / `weak` / `contradicted`; retrieval
     confidence = sentence↔chunk similarity.

## Convert in place (persist)

- Recompute `status` = `verified` iff every sentence has ≥1 citation and all its citations `verified` (the native
  `summarize_scope` rule); else `flagged`.
- Clear any existing native rows for the summary (none for an imported one), then **update the same `summaries` row**:
  `imported_json = NULL`, `status`, `generated_by = "re-verified-from-bundle"` (provenance survives), `overview_json =
  NULL` (the sender's overview traced *their* verified set — dropped, not re-narrated; no LLM), and the version stamps
  from the verifications (reuse `_combined_chunk_version` / `_combined_embedding_version` / `_embedding_version`, with a
  `"reverify"` sentinel when there are zero verifications).
- Write real `summary_sentences` + `citation_mappings` + `evidence_quotes` (reuse `_persist_verification`).

The summary now reads through the **native** path — `_persisted_summary_response` no longer branches to the blob,
`imported` is `false`, the pane drops the "Imported" banner and shows **my own** verified/flagged statuses (exact
highlights where the quote matched).

## Endpoint + engine (`summaries.py`)

`POST /summaries/{summary_id}/reverify` → `SummarizeJobResponse` (the updated, now-native summary). **404** if no such
summary; **422** if it isn't imported (`imported_json` NULL). Sync (verification of a handful of sentences is fast; no
generation/egress). Reuses `_embedding_model(api)` + `_vector_store(api)` + `api.state.support_scorer` (the same
models the summarize job uses) over `request.app.state.engine.begin()`.

New module `app/backend/summarization/reverify.py` (`reverify_imported_summary(conn, summary_id, *, model,
vector_store, support_scorer=None, config=None)` + `_resolve_local_paper` + `_best_chunk_for` + `_norm`), reusing
`LocalCitationVerifier` / `CandidateCitation` / `_persist_verification` / `_combined_*` / `get_summary`. No new
dependency.

## Frontend (`20_synthesis.jsx`)

The `.synth-imported` banner gains a **"Re-verify against my library"** button → `POST /summaries/{id}/reverify` →
on success set `state.result` to the response (the banner disappears; native statuses render) + refresh the history
(the entry is no longer flagged `imported`). A spinner/"Re-verifying…" while in flight; a failure surfaces a toast,
never a crash. Tokens-only CSS (rule #8) — reuse `.btn-link`.

## Gates

- **Security audit** — addendum to `2026-07-01_library-bundle.md`: a new endpoint (#1) but **no egress, no external
  fetch, no new dependency, no migration**; verification is fully local; bound-param SQL; the convert is all-or-nothing
  in one transaction. **Principles gate — aligned** (re-verification is the honest native path; a claim my library
  doesn't support flips to flagged, a source I don't have stays unverified — silence≠certificate; no new claim *type*,
  the existing local verifier re-run).
- **Rule #10 (QA):** extend `route_54_library_bundle.md` — the re-verify endpoint + the convert-to-native +
  banner-drops + a-claim-without-a-local-source-is-flagged assertions.
- **Rule #1:** new `reverify.py` (small); `summaries.py` gains one endpoint (re-measure — it's at 458). No migration.

## Verification

- **pytest** (`tests/test_reverify.py`, hermetic — a fake embed model + a fake support scorer, real chunks): seed a
  library with a paper + chunk containing a quote; import a synthesis citing it (SP2); `reverify` → the summary is
  now native (`imported_json` NULL, `status` set, `generated_by="re-verified-from-bundle"`), real `summary_sentences`
  /`citation_mappings`/`evidence_quotes` rows, `GET /summaries/{id}` → `imported:false` + a chunk-backed citation with
  the local verdict; a claim whose source paper isn't present → the sentence is **flagged with no citation** (kept,
  not verified); the endpoint is **422** on a native summary and **404** on a missing id; re-resolve picks up a
  source paper added after import (the blob's `source` identity).
- **Headed, no egress** (extend/clone the inc-235 driver): a dest with a paper + an imported synthesis citing it →
  open THEORY → Synthesis → load it → **Re-verify against my library** → the banner disappears, the citation shows a
  native status; 0 console/page/off-machine.
- Full suite; `ruff` + `format`; `build_frontend` (+ assembly); QA `check` 0-uncovered; help corpus "Sharing a
  library" notes the re-verify action; commit (excl. `www/`), push, CI.

## Deferred

Re-verify is **verification only** — it never re-*generates* prose (no egress). Re-verifying a query/cluster-scope
synthesis works the same per-citation (each citation still carries its source identity); the source-paper scope is
the citations' resolved papers regardless of the original scope_type.
