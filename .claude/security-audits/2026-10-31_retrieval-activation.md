# Security audit: automatic Arctic S activation and complete-index fallback (inc 618)

**Date:** 2026-10-31.
**Review type:** self-review by the implementing session (threat review + automated negative-path tests). No
independent automated review has run: the plugin security-review hook reviews fresh commits only and has no manual
mode, so the independent review of this commit is **pending**, as it is for incs 616 and 617.

**Scope:**
- `app/backend/embeddings/retrieval_resolution.py` (new);
- `embeddings/profiles.py` (helpers removed, error text);
- `modernization/coordinator.py` (activation, signature);
- `api/routers/summaries.py`, `embedding_profiles.py`, `modernization.py`, `summaries_provenance.py`,
  `embedding_index.py`;
- `embeddings/index_runs.py`, `index_supervisor.py`, `model_provisioning/runner.py` (manual-build guard);
- two frontend chunks.

**Triggers:** a changed request contract (`PUT /embedding-profiles/active` accepts `automatic`), changed response
schemas (three endpoints), a net-new feature over 3+ files and ~300+ LOC.

## Threat review
| Area | Finding |
|---|---|
| **Data egress / network** | None added. Resolution and activation read local rows and the inc-615 state file only. **One network path removed:** a manually queued build can no longer launch a worker that loads an unverified, provisioning-managed checkpoint (which could fetch from the Hugging Face Hub). An unreadable provisioning state is treated as pending (fail closed). A user-forced Arctic choice whose checkpoint lost verification fails closed instead of loading (same fetch risk, in the app process). Source checkouts without automatic provisioning keep the documented developer path. |
| **Scientific integrity** | No partial index is ever queried: resolution requires `profile_coverage` complete, and the unchanged ranking-time check refuses a non-lazy profile with any missing candidate vector, so an operation that raced an import fails closed and saves nothing. Ranking, thresholds, eligibility, the MiniLM verification gate and model identities are unchanged; the same effective model returns identical evidence whether chosen automatically or explicitly (tested). Historical syntheses are not rewritten; new provenance fields are absent on old rows and reported as unknown, not guessed. |
| **User authority** | A user choice is never overwritten: activation and the user's write are serialized by SQLite's writer lock, and activation rechecks the stored choice inside its transaction. Legacy unmarked choices are kept as the user's. A forced incomplete Arctic choice keeps failing closed, with a stated way back. |
| **Input validation** | `key` is either the literal `automatic` or must name a known profile (404 otherwise; 409 for an incomplete non-lazy profile, unchanged). Stored values are compared to fixed constants; an unknown stored key means no preference. SQL is SQLAlchemy Core with bound parameters; the one `text()` statement is a constant. |
| **Concurrency / locks** | The write lock is held only for the activation or selection transaction (a few reads), never around inference. `run_write` retries on lock contention. Two real processes activating at once produce one write. |
| **Output / disclosure** | Responses add enum reasons, fixed English sentences and booleans. No path, passage, exception text or count-derived percentage. |
| **Resource use** | The signature UDF adds work to the existing single aggregate scan (synthetic 700k chunks: about 1.65 s vs 1.19 s per check, at most once per 60 s when idle); no per-tick full coverage scan was added. |
| **Authorization** | Unchanged: every endpoint stays behind `AccessControlMiddleware`; `PUT` is blocked by `CALLOSUM_READ_ONLY`. |
| **Secrets / dependencies** | None added. No `psutil`. |

## Negative-path checks (automated, `tests/test_arctic_activation.py`, 28 passed)
- Partial index → MiniLM, and Arctic's query side is never called.
- Model absent / downloading / corrupt / status read raising → MiniLM `model_unavailable`; no activation.
- A `completed` run row whose vectors were deleted → MiniLM; activation returns `incomplete`.
- An import between resolution and ranking → error, plain message, no synthesis row.
- A user choice committed during activation → the user's choice stands; later activation returns `user_preference`.
- Two processes → `activated` + `already_active`.
- Manual build with an unverified managed checkpoint → no load, no worker, `model_not_ready`; it starts once verified.
- User-forced Arctic, complete index, checkpoint no longer verified → error, the model is never loaded.
- Papers, chunks, annotations, citation mappings and existing MiniLM vectors byte-compared before and after.

**Security Audit: PASS** (self-review for the scope above; the independent review is recorded as pending).
