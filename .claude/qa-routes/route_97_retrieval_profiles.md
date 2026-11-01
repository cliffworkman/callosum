<!-- qa-coverage
api: /verification-nli-profiles, /verification-nli-profiles/active, /embedding-profiles, /embedding-profiles/active, /embedding-profiles/{key}/index, /embedding-profiles/index/{job_id}, /embedding-profiles/index/{job_id}/cancel, /embedding-profiles/{key}/index/pause, /embedding-profiles/{key}/index/resume, /embedding-profiles/{key}/index/cancel, /modernization, /modernization/pause, /modernization/resume
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
  ProgressBar is `managedBy="backend-job"`, so no duplicate client row appears. Progress is stored passages over
  eligible passages, re-derived from the vectors (inc 610), never a session counter.
- **Supervised build (inc 610).** The build runs in a separate worker process. Its row (`index_run`) shows the state
  (queued / running / pausing / paused / waiting for resources / waiting for disk / interrupted / retrying / failed / completed /
  cancelled), a plain message, attempts, and only the actions that apply (Pause, Resume, Cancel). "Technical details"
  holds the bounded diagnostic; the message never shows an exception, a path or passage text.
- **Low disk is a wait, not a failure (inc 616).** When the library's drive lacks room for the next batches plus a
  1 GB reserve, the row is `waiting_disk`: "Waiting for disk space: needs about X GB free, Y GB free now. Completed
  work is saved. Callosum checks again every minute and resumes automatically." Pause and Cancel are offered; no
  worker runs. `index_run.disk` carries `required_free_bytes`, `free_bytes` and `estimated_remaining_bytes` as byte
  counts only: no path, drive or filename anywhere in the response or in Status. A full disk reported by SQLite gives
  the same state ("the disk holding your library filled up"). Repeated disk waits never end in **failed**, never
  shrink the batch, and never delete MiniLM vectors or user data; freeing space resumes the build with no action.
  Known gap: the settings panel does not yet treat `waiting_disk` as active (no polling/progress bar); the Status
  popover does.
- **Pause/Cancel keep work and are durable.** Both stop after the batch in progress; coverage keeps every committed
  batch. A paused or cancelled build stays so after an app restart (no automatic resume). Resume continues from the
  stored vectors and re-indexes nothing already current.
- **Low memory is a wait, not a failure.** With little free memory the row says "Indexing paused because available
  memory is low. Completed work is saved. Callosum will resume automatically when safe." and no worker is running.
  After a resource exit the next attempt uses a smaller batch ("Indexing resumed with a smaller batch size").
- **Bounded recovery.** An interrupted worker (killed, crashed, app closed) is detected and retried automatically
  with backoff. Three attempts without new stored vectors stop the build in **failed** ("Indexing stopped after
  repeated unsuccessful attempts…", or the not-enough-memory message at one passage per batch); only Resume restarts
  it. A model that cannot load is never retried automatically.
- **The app survives the worker.** Killing the worker process leaves Library, Settings and Status responsive.
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

- **Background modernization (inc 617, backend contract only; no UI yet).** `GET /modernization` reports three
  separate groups: `classification` (source-role v2 papers current / pending / failed this session), `indexing`
  (Arctic S eligible / indexed / missing passages, with the supervised run's state) and `model` (provisioning
  state, `verified`). Each group carries `state`, `automatic_recovery` and `needs_user`; there is no combined
  percentage and no ETA, and the response holds no path, passage or exception text. In a source checkout
  `enabled` is false (`disabled_reason: development_checkout`) and nothing runs; the packaged app (or
  `CALLOSUM_MODERNIZATION=1`) enables it, and `CALLOSUM_DISABLE_MODERNIZATION=1` turns it off.
  `POST /modernization/pause` is durable across restarts and stops both classification and automatic Arctic
  indexing; `POST /modernization/resume` returns `intent: auto`. A Settings Pause or Cancel of the index build is
  never restarted automatically, even after an import or a restart; only Resume (here or in Settings) restarts it.
  Indexing waits as `waiting_for_model` until the Arctic checkpoint is verified; nothing downloads or loads
  unverified weights. MiniLM stays the effective retrieval model throughout.

## Adversarial checklist

- Load Settings → exactly one `GET /embedding-profiles`; no POST is issued.
- Click Build index twice quickly → one job (the second POST joins the active job).
- Cancel mid-build, reload Settings → partial coverage, Resume available, radio still disabled.
- Resume → completes; radio enables; select → `active` becomes `arctic-s`; switch back to MiniLM → works without
  any rebuild.
- Select DeBERTa, run Ask → citations show DeBERTa support values; switch back to MiniLM2 → next Ask uses MiniLM2.
- Import a new full-text paper while Arctic is active → Ask fails closed with the coverage message.
- Mid-build, end the worker process from Task Manager → Settings shows "interrupted … will retry automatically", the
  count does not drop, and the build resumes and completes without duplicate vectors.
- Mid-build, quit Callosum and relaunch → the build resumes on its own; Pause first, quit, relaunch → it stays paused.
- Packaged app on a 0.5.16 library → `GET /modernization` shows classification `running` then `complete`; with the
  Arctic model verified the index build starts by itself; Library and Ask stay usable throughout.
- `POST /modernization/pause`, quit, relaunch → `intent` is still `paused`; no classification or build starts.
  Resume → both continue from stored rows; nothing already current is redone.
- Open two Callosum windows on one library → only one reports `coordinating_here: true`.
