# P1b predeclaration, version 2 (inc 637), frozen before the second hosted P1b run

Version 2 revises `P1B_PREDECLARATION.md` (version 1, SHA-256 `6a5a2d85…e063`), which stays in the tree unchanged.
Everything in version 1 still applies except where a section below replaces it. The driver pins both files by
SHA-256 and refuses to run if either differs. Nothing here is revised after the second run's measurements.

This is a new experiment on corrected application code. It is not a rerun of the first attempt, and nothing measured
in the first attempt is counted here.

## 1. Why a revision

The first hosted attempt (run 41948518913, commit `7998ea63f329792dd5105a0e33d6885b83377a04`, predeclaration v1) is
**INCONCLUSIVE**: a driver defect stopped it after one counted DeBERTa process. That verdict stands. The process it
completed, `deberta_solo_1`, is kept as historical evidence for the code it ran:

- warm values 68.6168, 68.4668, 68.5399, 68.3507, 68.3577, 68.6085, 68.4733, 68.4786 s, median 68.476 s;
- cold 86.8 s;
- peak working set 1,080 MB and peak commit 1,517 MB;
- noise rule satisfied, statuses stable across all 9 calls.

That code loaded DeBERTa in float16. The pinned checkpoint stores float16 weights, transformers 5.14.1 loads a
checkpoint's own precision by default, and the application requested none. G1 and G2 had measured float32. The
evidence is:
- the source code;
- all 378 recorded DeBERTa probabilities being exact float16 values;
- memory.

The first attempt did not inspect the loaded dtype.

Two corrections follow, and both are in the code under test:

1. **Driver:** inc 636 follow-up. A `$name` loop variable overwrote the `$Name` parameter. Measurement names are now
   preserved, and a missing process record is an explicit infrastructure failure. `p1b_driver_selftest.ps1` guards
   this.
2. **Application:** inc 637. DeBERTa is loaded with `dtype=torch.float32` and refused unless the loaded model's
   floating-point parameters and buffers are float32.

## 2. Code under test (replaces v1 §2)

The application is the integration head `da47c81bcbd928da2d7a2ab7f596d0cecc7d54f9` plus the inc 637 correction and
nothing else:

| Path | Tree | Relation to the integration head |
|---|---|---|
| `app` | `aabc1618d81a62054eaa8e9245dbf36a8c263e59` | `39edfb6a…` plus `app/backend/model_runtime.py`, `app/backend/summarization/verification.py`, `app/backend/summarization/stance.py` |
| `tests` | `6372b3ae068618cd171901c2a5063b8054ae3efd` | `2ab60bee…` plus `tests/test_nli_precision.py` (new) and `tests/test_desktop_packaging.py` |
| `integrations` | `f02b9dbad694cceee0f109d454465922380e8fa9` | equal |
| `alembic` | `88d476b99486fe22716b6156437006d4cc31f525` | equal |
| `pyproject.toml` | `53edf2b51b86385154bac5ed1840512ca026caca` | equal |
| `uv.lock` | `e5966c320bb5e4f113fd18c58de2ec8ef8e1f74b` | equal |

The qualification branch still starts from the qualified P1 commit `f1d6c4302af3350146676fd79b7c62bacf3495c7`. The
driver's changed-file allowlist is `tools/qualification/p1b/`, `.github/workflows/p1b-qualification.yml` and the
five files named above, and every tree above is pinned. The run's checkout therefore cannot exercise the
uncorrected loader or any other application change. The P1 harness, its fixture, its workflow and its evidence are
unchanged.

The runtime, model revisions, manifests and dependency pins are those of version 1 and are unchanged:
- runtime `win-x86_64-py3.11-s1-2094b5a287a1dd54`, tree `a51f65b3…f2fc`;
- sentence-transformers 5.6.1, transformers 5.14.1, torch 2.13.0, Python 3.11.15.

## 3. Precision stage (new; runs after `tokenize` and before `seed`, before anything is timed)

One offline process, the `precision` phase, loads DeBERTa through the application's own resolver
(`resolve_support_scorer` with the DeBERTa profile, offline, no fallback). It records:
- the requested dtype;
- the parameter, floating-buffer and other-buffer dtype counts, from the probe's own walk of the loaded module;
- the devices, the backend and the model class;
- the configuration dtype;
- the snapshot commit hash;
- the library versions, the torch default dtype and the thread count.

It then requires every check below:

| Check | Kind | Requirement |
|---|---|---|
| `profile_identity`, `label_order` | contract | the profile, the P1b fixture and the P1 fixture name the same checkpoint and label order `[entailment, neutral, contradiction]` |
| `thresholds_unchanged` | scientific | retrieval 0.70, quote 1.00, support 0.55, contradiction 0.55 |
| `float32_requested_by_app` | contract | the application's required dtype for DeBERTa is `float32` |
| `app_load_in_float32` | contract | the application's load succeeds, including its own parameter-dtype check and the label/architecture/tokenizer contract |
| `loaded_parameters_float32` | contract | the probe's independent walk finds floating-point parameters, all `torch.float32`, and no floating-point buffer of another dtype; integer buffers (position and token-type ids) are reported, not judged |
| `effective_device_cpu`, `effective_backend_torch` | contract | every parameter is on `cpu`; backend `torch` |
| `loaded_checkpoint_identity` | integrity | model and revision `6f5cf0a2…90eb`, the configuration's snapshot commit hash equals that revision, offline load |
| `p1_reference_parity`, `p1_app_extraction_parity` | scientific | on the 2 frozen P1 pairs, the raw probabilities and the application's (entailment, contradiction) extraction are within the P1 limit (0.001) of the P1 float32 development reference |
| `p1_outputs_not_float16` | contract | the 6 P1 probabilities are not all exact float16 values |
| `p1_statuses_unchanged` | scientific | the 4 frozen P1 statuses, through the application's own status rule |

**What the P1 parity does and does not show.** The 0.001 limit is P1's, inherited unchanged rather than chosen for
this run. The historical float16 packaged outputs also lie within it (largest difference 2.6 × 10⁻⁵), so parity
alone cannot tell float32 from float16. The precision evidence is the loaded-parameter check. The float16
signature check is a second, one-sided test: float16 inference fails it, and float32 inference passes it with
near certainty. Both differences are recorded:
- `max_abs_vs_float32_reference`;
- `max_abs_vs_historical_float16_packaged`.

Two synthetic pairs are not G1 parity (§6).

A failed check in this stage ends the run before `seed`, so no process is warmed up or measured. Each failure's kind
sets the verdict as in v1 §8.

## 4. Additions to every measured process (adds to v1 §4 and §6)

Each `measure` process (warm-up, solo and concurrent) records the dtype counts of its own loaded verifier model.
A DeBERTa process additionally requires two contract checks:
- `deberta_parameters_float32`, the same requirement as `loaded_parameters_float32`;
- `deberta_outputs_not_float16`: its 9 calls' 378 support and contradiction probabilities are not all exact float16
  values.

These checks are not timed. They run outside the `perf_counter` interval, so they change no measurement definition.

## 5. Unchanged (v1 §§3, 5, 6, 7, 8, 10 apply as written)

- **Fixture:** `fixtures/p1b-pairs-v1.json`, SHA-256 `acd2723c…9920`, and the indexing corpus `cb488cde…16bc`.
- **Conditions and order:** 3 fresh processes per DeBERTa condition, 8 warm repetitions after 1 cold call. Real
  overlap with the production Arctic index worker is required for condition B.
- **Measurement and resource accounting:** v1 §6, and the noise-discard rule and timeouts of v1 §7.
- **Acceptance:** limits unchanged, numbers as in v1 §7:

| Criterion | Statistic | Limit |
|---|---|---|
| Warm, DeBERTa alone | the **largest** of the 3 per-process medians | ≤ 7.2 s |
| Warm, DeBERTa with Arctic indexing | the **largest** of the 3 per-process medians | ≤ 8.8 s |
| Peak working set | over the 6 measured DeBERTa processes | ≤ 2,520 MB |
| Peak commit | over the 6 measured DeBERTa processes | ≤ 2,870 MB |

- **Runner and threads:** the runner (`windows-2025`) and the thread settings (torch defaults, never overridden) are
  unchanged. Nothing is tuned for speed.
- **Verdict rules and the single-run rule:** v1 §8.

## 6. Scope (adds to v1 §10)

A PASS shows that the corrected float32 loader meets the operational limits on the packaged Windows runtime, with
float32 established on the loaded model. It does not show:
- **G1 parity for the float32 loader.** The private G1 evaluation (Set A 99 and Set B 209 pairs, 308 in all) is never
  uploaded to GitHub Actions. G1 was accepted on development-environment float32 scores. Because the corrected loader
  restores float32, a later isolated G1 re-run against the packaged runtime is still required before automatic
  DeBERTa preference. That re-run must keep the gold labels and thresholds unchanged.
- **Other platforms.** It says nothing about macOS or Linux. Intel macOS (transformers 4.57.6) honours the same
  `dtype` argument, but was not run.
- **Release-gate arming.** `DEBERTA_RELEASE_GATES.packaged_runtime_acceptance` stays unarmed.
