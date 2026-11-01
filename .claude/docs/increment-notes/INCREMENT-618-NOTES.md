# Increment 618 — Automatic Arctic S activation and complete-index fallback

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `8f9f3aad`.
Local only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 618: Automatic Arctic S Activation and Complete-Index Fallback" instruction.
It implements release blockers **B5** and **B6** and closes the manual-build download path left open in inc 617.
Status: **implemented and focused-tested on disposable libraries with synthetic encoders; not release-validated; the
full Status UI is a later increment.**

## Implemented
- **`app/backend/embeddings/retrieval_resolution.py`** (new): the single resolution policy, the preference model,
  `set_user_preference`, `activate_arctic`, and the user-facing explanation sentences.
- **`embeddings/profiles.py`:** removed `active_retrieval_profile` / `set_active_retrieval_profile` (no other
  callers remain; everything reads and writes the preference through the new module). The incomplete-index error now
  says Callosum does not search a partial index and names the ways back (build, MiniLM, automatic selection).
- **`api/routers/modernization.py`:** `resolve_retrieval(app, conn)` feeds `resolve` the coordinator's gating, the
  inc-615 model status, the Pause intent and the Arctic run row. `GET /modernization` adds `retrieval_preference`.
- **`api/routers/summaries.py`:** `_retrieval_model` calls `resolve_retrieval` once per operation, for every scope
  (library query, selected papers, cluster, faceted; faceted receives the already-resolved model). Provenance is read
  from the model object that ranked. An `IncompleteEmbeddingIndexError` on an automatic resolution (the library
  changed mid-operation) gets its own message: nothing saved, ask again, MiniLM until catch-up.
- **`modernization/coordinator.py`:** `_activate()` on each leader check (before the Pause check) calls
  `activate_arctic` only when the cached coverage is complete and the model is verified; `model_status()` is public.
  The aggregate signature now checksums `chunk_version` with a per-connection CRC UDF and sums the ids of classified
  chunks and live papers.
- **`api/routers/embedding_profiles.py`:** `{"key": "automatic"}` clears the choice; the response adds `preference`,
  `preference_source`, `legacy_preference`, `fallback_reason`, `explanation`, `ask_blocked`; `active` is now the
  effective profile.
- **`api/routers/summaries_provenance.py` + `20e_model_provenance.jsx`:** the result line adds one past-tense
  sentence when MiniLM was a fallback (or "Selected explicitly in Settings.").
- **`35i_retrieval_profiles.jsx`:** an Automatic option and the one-sentence explanation; a profile's radio shows the
  user's choice and "in use for Ask" shows the effective one.
- **Manual-build guard:** `model_provisioning.checkpoint_pending(model)`; `index_supervisor._maybe_launch` holds the
  build via `index_runs.hold_for_model` (state unchanged, `failure_kind = model_not_ready`, re-check in 60 s);
  `embedding_index._message` says "Waiting for the model download to finish and be verified…".
- **Second instance of the same loophole, found during this increment:** a complete index outlives its checkpoint's
  verification (a damaged or deleted model cache). A user-forced Arctic Ask would then load the model in the app
  process with `local_files_only=False`. `resolve` now raises the existing `IncompleteEmbeddingIndexError` with
  `CHECKPOINT_PENDING_MESSAGE` in that case (no load; Settings shows `ask_blocked`); automatic selection already falls
  back on `model_unavailable`.
- **QA route 97** extended; blocker matrix and architecture doc annotated; security audit (self-review).

## Resolution contract
| Stored preference | Automatic on? | Arctic model | Arctic coverage | Ask uses | `fallback_reason` |
|---|---|---|---|---|---|
| user MiniLM | any | any | any | MiniLM | — |
| user Arctic S (or legacy unmarked) | any | verified, or provisioning off | complete | Arctic S | — |
| user Arctic S (or legacy unmarked) | any | managed and not verified | complete | **error**, no model load | — |
| user Arctic S (or legacy unmarked) | any | any | incomplete | **error** (inc 608), nothing saved | — |
| none / modernization | no (source checkout) | any | any | MiniLM | — |
| none / modernization | yes | not verified | any | MiniLM | `model_unavailable` |
| none / modernization | yes | verified | complete | **Arctic S** | — |
| none | yes | verified | incomplete | MiniLM | `indexing` / `paused` / `cancelled` / `failed` |
| modernization | yes | verified | incomplete | MiniLM | `catching_up` / `paused` / `cancelled` / `failed` |

Pause and cancel reasons come from the modernization intent and the run row. Coverage is always computed from stored
vectors at operation start; a `completed` run row or a finished download proves nothing.

## Activation and preference contract
- **Activation** (`activate_arctic`, one `run_write`): take the writer lock (no-op UPDATE) → read the preference →
  `user_preference` if explicit → `model_unavailable` if not verified → `incomplete` if coverage is not complete →
  `already_active` → otherwise write key `arctic-s` + source `modernization` → `activated`.
- **User selection** (`set_user_preference`) takes the same lock, so the two serialize; whichever commits last is
  stored, and activation never overwrites a stored user choice.
- **Legacy policy.** A key without a source predates 618, when only Settings wrote it: it is treated as the user's
  choice (`legacy: true` in the API) and never auto-switched. A key unknown to this build is ignored (automatic).
- **Way back.** Settings → Automatic, or `PUT /embedding-profiles/active {"key": "automatic"}`, or choose MiniLM.

## Import, catch-up and recovery results (tests)
- Import after activation → next Ask MiniLM `catching_up` → coordinator schedules the catch-up with no click →
  next Ask Arctic S. Import during the first build is included before activation.
- In-place `chunk_version` change of equal length → the signature changes; Ask falls back at once; catch-up returns
  to Arctic S. An equal-count attachment-role swap also changes the signature.
- Restart mid catch-up → the next session reports `catching_up`, the supervisor recovers, Arctic S returns.
- Pause with a complete index → Arctic S still used; Pause with new material → `paused`; Cancel → `cancelled`.
- Papers, chunks, annotations, citation mappings and existing MiniLM vectors unchanged throughout (byte compare).

## Scientific invariance
The same effective model retrieves identical ordered evidence whether chosen automatically or explicitly (the
second operation is an inc-493 cache hit, which requires identical ordered inputs) with identical citation status
and confidences. Ranking, thresholds, eligibility, the AST isolation test, the MiniLM verification gate and model
identities are unchanged. No DeBERTa activation; `app/backend/llm` untouched.

## Residuals
- An Arctic vector removed without any chunk change is not in the signature; per-Ask resolution still falls back at
  once and the 30-minute refresh re-schedules the build.
- A `paused` or `cancelled` state set on a build the user started manually is reported with the same reasons.
- Help does not yet describe automatic selection (left for the UI/Status increment, B9, with inc 616/617 text).
- The website coverage drift now also includes the two frontend chunks changed here; the demo does not serve the
  new fields. Both gates still fail on their pre-existing staleness; neither was refreshed or declined.

## Manual verification script
1. Copy a 0.5.16 library to a scratch folder. Start
   `CALLOSUM_MODERNIZATION=1 CALLOSUM_DB_URL=sqlite:///<copy> uvicorn app.backend.api.app:app --port 8890`.
2. Settings → Retrieval model shows **Automatic** selected and "Using MiniLM until the Arctic S model has finished
   downloading…" (or "…while the Arctic S index is being built").
3. Once the index completes, ask a question: the provenance line shows Arctic S with no note;
   `GET /modernization` shows `retrieval_preference.arctic_activated: true`.
4. Import one PDF, ask again: MiniLM, with "MiniLM was used while newly added or changed passages were indexed…".
   Wait for the catch-up; ask again: Arctic S.
5. Choose MiniLM: stays MiniLM. Choose Arctic S, import a PDF, ask: the error names Automatic and MiniLM. Choose
   Automatic: works immediately.

## Pytest
- `tests/test_arctic_activation.py` (new): **28 passed**; resource checks use a fixed snapshot so results do not
  depend on machine load (two tests had failed when run alongside a full parallel suite before that fix).
- Neighbours (embedding profiles, modernization, index recovery, provisioning, disk guard, NLI provenance, summaries,
  selected, faceted, frontend assembly, structure currentness, overview, migrations): **301 passed**.
- Full suite: see the commit report (known pre-existing demo/website failures listed separately).
