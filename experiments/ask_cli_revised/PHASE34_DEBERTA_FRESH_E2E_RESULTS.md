# Phase 34 — DeBERTa integration and fresh full q_aib run

**Disposition: INTEGRATION COMPLETE; FRESH E2E NOT COMPLETED.** The one authorized run was stopped by
the host-side safety monitor 8 minutes in, when JUNO's CPU reached the 88 °C abort limit during the first
coverage-audit call. No child synthesis, parent synthesis or final answer was produced. This is not a
scientific result about Ask, and it is not presented as an end-to-end evaluation. No retry was made.

## 1. What was built (commit `555a1d31`)

**DeBERTa verifier, opt-in (`--nli-verifier deberta`).** Every Ask NLI call shares one scorer
(`rt.verifier.support_scorer`): source verification calls it through the verifier, and the child-synthesis
and parent-synthesis screens receive the same callable. `nli_verifier.py` replaces that one scorer, so no
stage can stay on MiniLM.

| Setting | Value |
|---|---|
| Checkpoint | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` |
| Label order | entailment / neutral / contradiction, checked at load; a mismatch refuses to load |
| Direction | premise = source passage, hypothesis = claim (shared code, unchanged) |
| Entailment threshold | 0.50 at the source verifier and at both synthesis screens |
| Unchanged gates | similarity 0.70, exact quote 1.0, contradiction 0.55 and above support |
| Precision | FP32 (the hub file is FP16; it loads as float32) |
| Device | auto (CUDA, then MPS, then CPU), CPU fallback if an accelerator fails to load or infer |
| Receipt | model, revision, labels, dtype, device, pairs scored, embedding-fallback pairs, in the run manifest |

The synthesis screens read their threshold from the shared default (0.55), so a model swap alone would
have left them on MiniLM's value. `overview_guards.nli_screen_config` sets the run's thresholds for the
screens and for the mechanical re-derivation that audits them. The default verifier is still MiniLM; the
application's own summarize path is untouched.

**Hierarchical narrative answer, opt-in (`--parent-narrative`).** The presentation contract was not
implemented: the parent answer was a claim-by-claim list (`15_parent_answer.md`), and no document combined
the parent with the children. `hierarchical_answer.py` adds:

- Stage S3: one call to the unchanged overview stage (same prompt, schema, lexical screens, NLI screen,
  record and audit as a child synthesis) over the sealed ledger restricted to passages cited by displayed
  child statements. Existing limits apply: 12 passages, 6 statements, 1–3 citations each.
- `19_hierarchical_answer.md`: overview paragraph, then each approved subquestion in approved order under
  its approved wording with its child synthesis, open requirements under their subquestion, sources, and
  pointers to the inspection files. Quotations and scores go to `19b_hierarchical_answer_evidence.md`.
- A parent statement that fails screening is withheld. If none passes, the document says so; no claim list
  is substituted. The deterministic parent claim ledger is unchanged and remains an inspection artifact.

## 2. Verification before the run

- **Offline parity.** Through the runtime exactly as `run_topology` builds it, the scorer reproduced the
  frozen bakeoff on all 99 pairs: largest difference 1.2e-06, 45 supported and 2 negatives admitted at 0.50.
  Status checks: support 0.52 verified, 0.49 weak, contradiction 0.90 over support 0.20 contradicted; the
  screens accept 0.52 inside a DeBERTa run and reject it outside one.
- **Tests.** Ask suite, offline with every socket refused, the `contract_directed` subfolder excluded and
  one network-dependent test deselected: 4,754 passed, 2 failed. Both failures are hierarchy pin drift
  and both reproduce on the unmodified baseline `a6cfeec6`. Twenty new tests cover the verifier and the
  hierarchical answer, including the real `execute()` path with scripted clients.
- **Commit.** The line-budget hook was skipped, with Cliff's authorization, because it fails on
  `app/frontend/js/20_synthesis.jsx` (615 lines), which the commit does not touch. All other hooks ran.

## 3. Run configuration and provenance

| | |
|---|---|
| Run id | `phase34-deberta-fresh-e2e-20261012` |
| HEAD | `555a1d319a640c69f12d88b53fa4c4bf89df48e0`, clean tree |
| Call | `run_topology("T5C", "aib", hierarchy, model-assist, recovery, parent synthesis, parent narrative, nli_verifier="deberta")` |
| Generators | qwen3.5:9b (thinking off), phi4:14b, gemma3:12b on JUNO's isolated Ollama 0.34.3, CUDA |
| NLI | DeBERTa on the laptop CPU |
| Library | fresh working copy of the preserved Sept-30 copy; sha256 `4f2e98a5…2523` before and after, preserved copy also unchanged |
| Contract | `pins=None` (same disclosed departure as Phase 28); v9 sufficiency hash `9c72dc6a…5586` |
| Authorization | Cliff's GO of 2026-10-12, recorded and accepted by the real gate |

Nothing from an earlier run was read.

## 4. What happened

JUNO's preflight was healthy: up 4 h 33 min since the morning reset, CPU 41 °C, GPU 42 °C at 120 MiB,
11.1 GB RAM available, swap unused, load 0.14, kernel log free of GPU, thermal, memory and hardware errors.
A monitor ran on JUNO under the user's systemd manager, independent of the laptop, sampling every two
seconds with limits fixed beforehand: CPU warn 85 / abort 88 °C, GPU warn 75 / abort 80 °C, available
memory below 700 MB, swap growth over 4 GB, a new kernel error line, or 90 minutes. On abort it stops
the isolated Ollama.

| Time (EDT) | Stage | CPU peak | GPU peak | Note |
|---|---|---|---|---|
| 19:45–19:51 | W1, qwen3.5:9b, all on GPU | 86 °C (one sample at 19:49:58) | 61 °C | 213 calls, all usable |
| 19:51:07 | C1 begins, phi4:14b loads | | | 23 of 41 layers on GPU, 6 CPU threads |
| 19:52:27–19:53:10 | C1 | 85, 85, 86, 87 °C | 53 °C | warnings |
| 19:53:19 | C1 | **88 °C** | 45 °C | abort; Ollama stopped by 19:53:23 |

The laptop's coverage-audit call then failed with a closed connection and the run ended after 483 s.
Afterwards: CPU 55 °C within a minute, GPU 120 MiB with no compute process, no kernel error, no throttle
event, no reset, uptime continuous, the shared Ollama idle and contacted only by two read-only
resident-model listings (preflight and post-abort check), nine containers still up, tunnel closed.

**Cause.** phi4:14b does not fit the 8 GB card, so 18 of its 41 layers run on the CPU with six threads.
That load took the package from about 54 °C to 88 °C in about two minutes. This is the same CPU thermal limit
the hardware bakeoff measured, now met by a generator the pipeline requires. gemma3:12b is also split
across GPU and CPU and would meet it too. GPU temperature and memory were never close to a limit.

## 5. What the partial record contains

- `run/qwen_calls.jsonl`: 214 calls with full prompts and raw outputs — 110 context-gate decisions,
  47 evidence selections, 56 claim formations (all parsed and valid), and the one failed coverage audit.
- `run/decisions.jsonl` (48 context decisions), the request contract, the initial ownership context.
- `juno/`: 260 monitor samples, the monitor log and script, the post-abort host state.
- Not on disk: retrieved passages, the claim ledger and the DeBERTa verification records. The pipeline
  writes those when the first pass seals, after the coverage audit, and the run ended before that. So the
  run leaves **no record that DeBERTa scored a live pair**, and no manifest receipt. The only evidence of
  DeBERTa in the integrated path is the offline parity check in section 2.

## 6. Scientific assessment

None is possible. No evidence was sealed, no synthesis was written and no answer was rendered. Sections
4–8 of the requested report (child syntheses, parent synthesis, final answer, fidelity, observed failure
cases) have no content, and nothing here bears on Ask's usefulness or scientific readiness.

## 7. What blocks a release-relevant run

1. **JUNO cannot run the current generator set within the 88 °C CPU limit.** Any stage whose model spills
   onto the CPU will reach it within minutes; qwen alone touched 86 °C. This is a decision about hardware
   or limits, not about Ask. The choices, none taken here:
   - repair or improve the CPU cooling (one PyTorch thread reaching 81–88 °C suggests a cooling fault);
   - set a different abort limit knowingly (the i7-8700's rated maximum is 100 °C);
   - cap the CPU threads Ollama uses, which changes the runtime configuration and lengthens the run, and
     may still not hold given the one-thread measurements;
   - bind the coverage and planning roles to models that fit the GPU, which changes the pipeline's models.
2. **Intermediate evidence is not durable until the first pass seals.** A stop during the coverage audit
   loses the retrieval, claim and verification records of the whole first pass. Writing them as they are
   produced would make a partial run inspectable. Not changed here.
3. The parent narrative stage and the hierarchical document have run only against scripted clients.

## 8. Artifacts

- Run: `.local/e2e-runs/phase34-deberta-fresh-e2e-20261012/` (driver, authorization, console log, `run/`,
  `juno/`, library verification).
- Preparation: `.local/phase34-deberta-e2e-20261012/` (predeclaration, offline parity check and output,
  suite logs, layout dry-render over preserved Phase 28 records, which was a renderer check only).
- On JUNO: `/media/brain/JUNO/callosum-ask-exp/deberta-e2e-20261012/` (32 KB: monitor script and logs).
- Working library copy: `C:/Users/cliff/callosum-data/ask-deberta-e2e-20261012/` (665 MB).
- The DeBERTa checkpoint was copied from the bakeoff store into the default Hugging Face cache.
