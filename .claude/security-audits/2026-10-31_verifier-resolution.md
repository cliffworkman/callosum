# Security audit: per-operation synthesis verifier resolution (inc 619)

**Date:** 2026-10-31.
**Review type:** self-review by the implementing session (threat review + automated negative-path tests). No
independent automated review has run: the plugin security-review hook reviews fresh commits only and has no manual
mode, so the independent review of this commit is **pending**, as it is for incs 616–618.

**Scope:**
- `app/backend/summarization/verifier_resolution.py` (new);
- `summarization/nli_profiles.py` (selection helpers removed, qualification text);
- `api/dependencies.py` (`verifier_inputs`, offline DeBERTa load, per-profile test injection);
- `api/routers/summaries.py`, `embedding_profiles.py`, `summaries_provenance.py`, `summaries_response.py`;
- `api/job_timing.py`; `model_provisioning/runner.py` (two gate facts);
- three frontend chunks.

**Triggers:** changed request contract (`PUT /verification-nli-profiles/active` accepts `automatic`), changed
response schemas (NLI profiles, summary citations, verification provenance), a net-new feature over 3+ files.

## Threat review
| Area | Finding |
|---|---|
| **Data egress / network** | None added. **Two network paths removed:** a DeBERTa load in synthesis previously used `local_files_only_for(model)` (False when unverified, so a Hub fetch was possible); the Settings contract check used the registry default (False). Both now load with `local_files_only=True`. Selection in the packaged app is also refused while the provisioner does not report `verified`. Resolution only reads the inc-615 status file; it never starts the provisioner (tested). Production automatic use and download stay unarmed (`packaged_runtime_acceptance` false). |
| **Scientific integrity** | One verifier per operation; a failure after scoring starts raises `NLIInferenceError` and the job saves nothing (tested: no MiniLM2 call, no row). A load/contract failure before scoring is recorded `not_verified`. Thresholds, labels, statuses and the MiniLM similarity gate are unchanged; they are recorded, not read back. A MiniLM2 result is never labelled DeBERTa: the cautious note and the `cautious_contradictions` flag derive from the recorded profile. Historical rows are not rewritten; missing fields read as null. |
| **User authority** | Explicit choices are kept (legacy unmarked rows count as the user's); an unavailable or memory-unsafe explicit DeBERTa is refused with a way back, never swapped. `automatic` deletes the stored choice under SQLite's writer lock. |
| **Resource use** | The memory precheck uses `resources.measure()` (no psutil); free = min(physical, commit); unmeasurable fails the check. No memory exhaustion was induced: tests use simulated snapshots. |
| **Input validation** | `key` is `automatic` or a known profile key (404 otherwise). Stored values are compared to constants. SQL is SQLAlchemy Core; the one `text()` is a constant. |
| **Output / disclosure** | New fields are enums, fixed sentences, thresholds and MB integers (free memory and need). No path, passage or exception text reaches the response; the job error for an unavailable verifier is a fixed sentence. |
| **Authorization** | Unchanged: `AccessControlMiddleware`; `PUT` blocked by `CALLOSUM_READ_ONLY`. |
| **Secrets / dependencies** | None added. |

## Negative-path checks (automated, `tests/test_verifier_resolution.py`, 28 passed)
- Gate off; checkpoint absent/downloading/waiting/interrupted; invalid/unverified/unknown state; corrupt label
  contract at load (loaded offline only); low memory; unmeasurable memory; commit-starved; running Arctic worker.
- Explicit DeBERTa with checkpoint gone or memory short → job error, no scorer called, no row.
- Injected DeBERTa inference failure → error, no MiniLM2 call, no row; the next operation resolves again.
- Provisioner `run` patched to raise: never called; `PUT` of DeBERTa while not provisioned → 409.
- Historical row without inc-619 fields → readable, nulls, unchanged in storage.

**Security Audit: PASS** (self-review for the scope above; the independent review is recorded as pending).
