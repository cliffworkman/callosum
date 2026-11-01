# Increment 619 — Automatic DeBERTa verification with resource-safe compatibility

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `c6253a9a`.
Local only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 619: Automatic DeBERTa Verification With Resource-Safe Compatibility"
instruction. It implements release blocker **B8** up to arming. Status: **implemented and focused-tested on
disposable libraries with fake scorers, a fake checkpoint factory and simulated memory; production automatic use is
NOT armed; the packaged-runtime check is NOT done.**

## Implemented
- **`app/backend/summarization/verifier_resolution.py`** (new): preference read/write (`automatic` clears it), the
  memory precheck (`memory_check`), the decision (`decide`), the pre-scoring load-failure rule (`load_failed`), the
  provenance record, and the user-facing refusal sentences.
- **`api/routers/summaries.py`:** `_verifier()` runs once per synthesis, right after the retrieval profile is resolved
  and before retrieval/generation, for every scope (library query, selected papers, cluster, faceted). It loads the
  chosen checkpoint (and its contract check) there, so a DeBERTa that will not load is known before any claim is
  scored. One scorer is passed to the whole operation. `VerifierUnavailableError` ends the job with a fixed sentence.
- **`api/dependencies.py`:** `verifier_inputs(app)` (gates, provisioning state, whether provisioning manages the
  checkpoint, memory probe, DeBERTa residency, Arctic worker allowance — each injectable via `app.state`); a
  contract-checked profile always loads with `local_files_only=True`; tests may inject `nli_support_scorers` per
  profile.
- **`api/routers/embedding_profiles.py`:** `PUT /verification-nli-profiles/active` accepts `automatic`; DeBERTa is
  refused (409) while the provisioner does not report it verified; the contract check loads offline. `GET` adds
  `preference`, `legacy_preference`, `fallback_reason`, `explanation`, `synthesis_blocked`; `active` is the verifier the
  next synthesis would use (previewed without loading).
- **`summaries_provenance.py` / `summaries_response.py`:** verification provenance adds `preference`,
  `preferred_profile`, `fallback_reason`, thresholds, a past-tense `note`, `cautious_contradictions`; citations add
  `status_note`.
- **`api/job_timing.py`:** `stage_reporter(..., verifier=)` keys the `verifying_citations` stage by verifier.
- **`model_provisioning/runner.py`:** `operation_memory_guard` and `verifier_provenance_and_failure` recorded true;
  `packaged_runtime_acceptance` stays false, so `deberta_auto_provisioning_armed()` is still false.
- **`nli_profiles.py`:** removed `active_nli_profile` / `set_active_nli_profile` (no remaining callers); DeBERTa's
  qualification text now says it is the preferred verifier once its gates pass.
- **Frontend (minimal):** `35i_retrieval_profiles.jsx` (Automatic option + explanation), `20e_model_provenance.jsx`
  (fallback note, thresholds in the tooltip), `20c_synthesis_results.jsx` (cautious pill + `.cite-note`).

## Selection table (per synthesis)
| Stored preference | Gates armed | Checkpoint state | Memory | Verifier | `fallback_reason` |
|---|---|---|---|---|---|
| user MiniLM2 (or legacy) | any | any | any | MiniLM2 | `user_choice` |
| user DeBERTa (or legacy) | any | verified (or not managed) | ok | DeBERTa | — |
| user DeBERTa | any | managed, not verified | any | **refused**, nothing saved | — |
| user DeBERTa | any | verified | short / unmeasurable | **refused**, nothing saved | — |
| user DeBERTa | any | verified, fails load/contract | ok | **refused**, nothing saved | — |
| automatic | no (production today) | any | any | MiniLM2 | `not_qualified` |
| automatic | yes | absent / downloading / waiting / interrupted / insufficient_resources | — | MiniLM2 | `not_provisioned` |
| automatic | yes | present_unverified / invalid / unknown / unreadable | — | MiniLM2 | `not_verified` |
| automatic | yes | verified | short | MiniLM2 | `insufficient_memory` |
| automatic | yes | verified | unmeasurable | MiniLM2 | `memory_unmeasured` |
| automatic | yes | verified, fails load/contract | ok | MiniLM2 | `not_verified` |
| automatic | yes | verified | ok | **DeBERTa** | — |

After the decision the verifier is fixed: an inference failure (including out of memory) fails the operation with
"Citation verification failed, so no synthesis was saved." The next operation resolves again.

"Managed" = automatic provisioning is on (packaged app). In a source checkout an explicit DeBERTa may use an
already-cached snapshot, offline only (the inc-608 developer path, now without network).

## Memory contract
- Free = min(available physical, available commit) from `embeddings/resources.measure()` (Windows
  `GlobalMemoryStatusEx`, Linux `/proc/meminfo`, macOS `vm_stat`). Free already excludes this process (not
  double-counted). No total-RAM assumption. A running worker's current use is also outside free; reserving its full
  recorded peak on top over-counts that part, deliberately (conservative, as G2 was).
- Need = 1,500 MB if DeBERTa is not resident (G2: 540 MB before load → 2,016 MB peak, rounded up; above the G2
  condition of ~1.1 GB over MiniLM2), 512 MB if it is resident (G2: ~415 MB inference growth after load), plus a
  queued/running Arctic worker's recorded peak (or the 1,200 MB default estimate). `ResourcePolicy.can_start` adds the
  reserve (max(512 MB, 5 % of RAM)).
- Unmeasurable → fails. Automatic → MiniLM2 with the reason; explicit → refused.
- Tests use simulated snapshots only; the workstation was never pushed toward exhaustion.

## Provenance and display
`scope_ref_json.verification_nli` now also records `preference`, `preferred_profile`, `fallback_reason`,
`support_threshold` (0.55), `contradiction_threshold` (0.55), `similarity_threshold` (0.7), `memory_check`; `profile`,
`model_name`, `revision`, `thresholds_calibrated_on`, `embedding_fallback: false` are unchanged. Older rows lack the
new keys and read as null. The cautious wording follows the **recorded** verifier: MiniLM2 results (old or new) keep
"⚠ source disagrees"; any result recorded as DeBERTa — including a pre-619 explicitly selected one — shows "⚠ possible
disagreement" with the note. The machine status stays `contradicted`.

## Scope boundaries
Changed: synthesis verification (ordinary, selected-paper, clustered, faceted Ask). Unchanged and pinned by the AST
test: Suggest-citation/stance, Critical Read, citation context, beyond-library stance, imported re-verification
(MiniLM2). **Ambiguous boundary reported:** the Settings selection previously could download weights; it is now offline
only, so a source-checkout developer without a cached DeBERTa must fetch it outside the app (or via provisioning).

## Manual verification script
1. Start the app on a disposable library. Settings → Verification model: Automatic selected, "Using MiniLM2:
   automatic DeBERTa verification is not enabled in this release yet."
2. Ask a question: provenance tooltip shows support ≥ 0.55, contradiction ≥ 0.55 and the not-enabled note.
3. With a cached DeBERTa snapshot, select DeBERTa; Ask; a contradicted citation shows "⚠ possible disagreement" and
   the review note. Choose Automatic: back to MiniLM2 with the reason.

## Pytest
- `tests/test_verifier_resolution.py` (new): **28 passed** (22 scenarios plus memory edge cases and gate pins).
- Neighbours (NLI profiles/failure, provisioning, summaries, selected, faceted, embedding profiles, Arctic activation,
  frontend assembly, modernization, index recovery, Status, overview, Critical Read, suggest, stance): **391 passed**.
- Full suite: see the commit report.
