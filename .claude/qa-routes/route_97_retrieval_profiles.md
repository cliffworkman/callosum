<!-- qa-coverage
api: /verification-nli-profiles, /verification-nli-profiles/active, /embedding-profiles, /embedding-profiles/active, /embedding-profiles/{key}/index, /embedding-profiles/index/{job_id}, /embedding-profiles/index/{job_id}/cancel, /embedding-profiles/{key}/index/pause, /embedding-profiles/{key}/index/resume, /embedding-profiles/{key}/index/cancel, /modernization, /modernization/pause, /modernization/resume, /modernization/models/{track}/retry
fe: 35i_retrieval_profiles.jsx, 35j_modernization.jsx, 04f_modernization_logic.jsx, 04c_status.jsx, 04e_whatsnew.jsx, 20e_model_provenance.jsx, 20c_synthesis_results.jsx
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
- **Status.** In a build without automatic modernization, a build shows one row ("Retrieval index build", Local AI)
  that clicks to Settings. With automatic modernization on, that row is folded into the single "Library
  modernization" entry (see the inc-620 section). The inline
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
  Inc 620 closed the settings-panel gap: `waiting_disk` is an active state there too, so the panel keeps refreshing
  (every 5 s), shows required/free space, and returns to the running display when space is freed.
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

- **Model "Try again" (inc 622, recovery contract F8).** With a provisioned model in `invalid`, Settings → Library
  modernization shows an alert explaining the failure and a **Try again** button named for that model. No button appears
  while a model is absent, downloading or waiting on network, disk or memory, or once verified. Clicking it runs one
  forced attempt for that model: the button goes away, the panel and the one Status entry say "trying again", and the
  panel never reads "downloaded and verified" until the provisioner has verified the files. A failure that persists brings
  the button back with "The last Try again did not fix this." `POST /modernization/models/{track}/retry` returns 404 for
  an unknown model, 409 when no retry applies, 403 in read-only mode, and 401 without the Remote access token. Honesty
  invariants: Pause stays paused after a repair, Ask stays on MiniLM until the model is verified and existing conditions
  allow Arctic, a repaired DeBERTa does not turn on automatic DeBERTa, and no response carries a path or exception text.

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
  unverified weights. (Inc 617 alone kept MiniLM effective; inc 618 below adds automatic activation.)
- **Automatic Arctic S activation and fallback (inc 618).** `PUT /embedding-profiles/active` also accepts
  `{"key": "automatic"}`, which removes the user's choice. `GET /embedding-profiles` adds `preference`
  (`automatic` or the chosen key), `preference_source` (`user` / `modernization` / null), `legacy_preference`,
  `fallback_reason`, `explanation` (one sentence) and `ask_blocked` (set only when a user-forced Arctic S index is
  incomplete). `active` is now the profile Ask would use right now. With automatic selection on (packaged app or
  `CALLOSUM_MODERNIZATION=1`), Ask uses Arctic S only while its checkpoint is verified **and** its index covers every
  eligible passage; otherwise MiniLM with a reason (`model_unavailable`, `indexing`, `catching_up`, `paused`,
  `cancelled`, `failed`). `GET /modernization` adds `retrieval_preference` (`profile`, `source`, `legacy`,
  `arctic_activated`). Every saved synthesis records the resolution in `scope_ref_json.retrieval_embedding`
  (`preference`, `intended_profile`, `fallback_reason`, `index_verified_complete`), and the result's provenance line
  explains a fallback in one past-tense sentence. No percentage, no ETA. A manually requested build while the
  checkpoint is unverified waits ("Waiting for the model download…") and loads nothing.

## Adversarial checklist

- Load Settings → exactly one `GET /embedding-profiles`; no POST is issued.
- Click Build index twice quickly → one job (the second POST joins the active job).
- Cancel mid-build, reload Settings → partial coverage, Resume available, radio still disabled.
- Resume → completes; radio enables; select → `active` becomes `arctic-s`; switch back to MiniLM → works without
  any rebuild.
- Select DeBERTa, run Ask → citations show DeBERTa support values; switch back to MiniLM2 → next Ask uses MiniLM2.
- Import a new full-text paper while Arctic is **explicitly selected** → Ask fails closed with the coverage message,
  which names Automatic and MiniLM as ways back; `ask_blocked` is set.
- Automatic selection, Arctic active, import a paper → the next Ask uses MiniLM, its provenance line says new
  passages were being indexed; the catch-up runs with no click; the following Ask is on Arctic S again.
- Automatic selection, choose MiniLM explicitly → stays MiniLM after the Arctic index completes; choose Automatic →
  `active` becomes `arctic-s` immediately if the index is complete.
- Automatic selection, Pause modernization with a complete index → Ask stays on Arctic S (Pause stops work, not use).
- Settings → Build index before the Arctic model is verified (packaged app) → the build shows "Waiting for the model
  download…", no worker starts and no network request is made; it starts by itself once verified.
- Mid-build, end the worker process from Task Manager → Settings shows "interrupted … will retry automatically", the
  count does not drop, and the build resumes and completes without duplicate vectors.
- Mid-build, quit Callosum and relaunch → the build resumes on its own; Pause first, quit, relaunch → it stays paused.
- Packaged app on a 0.5.16 library → `GET /modernization` shows classification `running` then `complete`; with the
  Arctic model verified the index build starts by itself; Library and Ask stay usable throughout.
- `POST /modernization/pause`, quit, relaunch → `intent` is still `paused`; no classification or build starts.
  Resume → both continue from stored rows; nothing already current is redone.
- Open two Callosum windows on one library → only one reports `coordinating_here: true`.

## Verification model (inc 619)

- **Automatic is the default.** Settings → Verification model shows Automatic selected and one sentence. In this
  release the production gate is unarmed, so it reads "Using MiniLM2: automatic DeBERTa verification is not enabled in
  this release yet." `GET /verification-nli-profiles` returns `preference: "automatic"`, `active: "minilm2"`,
  `fallback_reason: "not_qualified"`. Selecting a profile and then Automatic deletes the stored choice.
- **Explicit DeBERTa** whose checkpoint is not verified (packaged app) → `PUT` returns **409**; no request leaves the
  machine. A choice made earlier whose checkpoint was later lost → Ask fails with "Nothing was saved. Choose
  Automatic or MiniLM2 in Settings → Verification model…"; Settings shows the same sentence as an alert.
- **Provenance line** after a MiniLM2 fallback names the reason in past tense; its tooltip lists support ≥ 0.55,
  contradiction ≥ 0.55. A DeBERTa result's `contradicted` pill reads "⚠ possible disagreement" with the note "The
  model flags a possible disagreement with the source. Review the cited passage."; a MiniLM2 result keeps "⚠ source
  disagrees". Older syntheses show no new fields.
- **Status.** The verification stage of a DeBERTa synthesis shows elapsed time only (no range) until it has receipts.

## Inc 620 — Library modernization visibility (B9)

Run with automatic modernization on (packaged app, or `CALLOSUM_MODERNIZATION=1`) on a 0.5.16-shaped library copy.

- **One entry.** Status shows exactly one **Library modernization** row (Local AI) while work remains, never a separate
  "Retrieval index build" row beside it. It has no dismiss button and no elapsed/remaining time; it shows the current
  activity, grounded counts (papers classified of papers with passages; passages indexed of eligible passages) and
  one note per stage (model, classification, indexing). **Clear finished** never removes it. It disappears when all
  stages are complete and reappears after an import needs catch-up.
- **Concurrent, not sequential.** With classification and indexing both running, the headline names indexing and the
  classification note still shows its own counts. There is no combined percentage and no time estimate anywhere.
- **Navigation.** Clicking the row opens Settings and scrolls to **Library modernization**. The 0.6.0 notice's
  **See progress and controls** action does the same.
- **Waits recover; terminal states don't claim to.** Network loss, low disk, low memory and a busy database read
  as waits with their cause and recover by themselves. A paused intent, a cancelled or failed build, and model files
  that failed verification read as needing the user (the Status row shows as an error, except paused) and never say
  they resume automatically. One terminal stage never hides a stage that is still working.
- **Pause/Resume.** Pause and Resume in the modernization panel are durable across restarts and idempotent, and never
  change the retrieval or verification preference (check both selectors before and after).
- **Effective models.** The panel states the retrieval model Ask uses right now and why (Automatic → MiniLM while
  Arctic S is incomplete), and the verifier the next synthesis uses and why. With the DeBERTa release gates off it
  says automatic DeBERTa verification is not enabled; it never claims DeBERTa is downloading or about to activate.
- **Responsive during a pass.** `GET /modernization` and `GET /status/jobs` answer promptly while a classification
  pass is running (they report the counts cached at `checked_at`).
- **Settings polling is one bounded loop.** One timer refreshes both panels: 2 s while a build is busy, 5 s during
  build waits, 3 s / 10 s for other working / waiting states, a 15 s idle tick when paused, complete or action-required
  (inc 621: an import or another window can change those with no action in this panel). The idle tick reads only
  `GET /modernization` and does the full read when something changed. It stops when disabled; leaving Settings stops it.
- **Privacy.** No path, filename, paper title, passage text, exception or model-cache detail appears in either
  response or in the UI.
- **Notice.** On first run of 0.6.0 an upgraded library sees the upgrade wording (usable, untouched, may take several
  sessions and extra disk, resumes by itself, controls in Status/Settings); a library with no papers sees the short
  fresh-install wording. Dismissing it records 0.6.0 as seen. No completion time or library size is promised.
  (The app is still 0.5.16 in this increment, so verify the notice via the node tests until the version bump.)

Pinned by `tests/test_modernization_status.py` (backend + node logic). Not yet driven in a real browser: the Playwright
session was unavailable in the implementing session.
