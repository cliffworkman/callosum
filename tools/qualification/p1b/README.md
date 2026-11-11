# P1b: packaged DeBERTa performance and resource qualification (Windows x64)

Inc 636. One hosted GitHub Actions run (`.github/workflows/p1b-qualification.yml`, triggered only by a push to
`qualify/p1b-0.6.0`) answers one question: on the signed Windows packaged runtime, does the app's own verifier path
with DeBERTa meet the predeclared warm-latency and memory limits, alone and alongside the real Arctic S index worker?

The method, the limits and every aggregation rule are fixed in `P1B_PREDECLARATION.md` before any measurement. The
driver refuses to run if that file or the fixture differs from the SHA-256 pinned in `p1b_qualify.ps1`.

**Revision 2 (inc 637).** The first attempt (run 41948518913) is INCONCLUSIVE and ran DeBERTa in float16.
`P1B_PREDECLARATION_V2.md`, also pinned, revises v1 for the corrected application:
- DeBERTa is loaded with `dtype=torch.float32` and verified on its loaded parameters;
- a `precision` stage checks float32 on the loaded model and P1 float32 parity, and stops the run before anything is
  timed;
- every DeBERTa measurement process repeats the check on its own model.

Limits, fixture and measurement rules are unchanged. The app and tests trees are pinned to the corrected source.

| File | Role |
|---|---|
| `P1B_PREDECLARATION.md` | v1: method, conditions, measurement definitions, acceptance, verdict rules, scope |
| `P1B_PREDECLARATION_V2.md` | v2 (inc 637): code under test, precision stage, per-process dtype checks; everything else unchanged |
| `fixtures/p1b-pairs-v1.json` | 21 public synthetic quote/claim pairs, 9 distractor chunks, the indexing-corpus recipe |
| `p1b_qualify.ps1` | the driver: runtime verification (P1 scripts, unchanged), firewall boundary, serial stages, receipt |
| `p1b_probe.py` | one phase per process inside the packaged `python.exe -I -B` |
| `p1b_worker.py` | starts the production `index_worker.main` under `-I -B` |
| `p1b_selftest.py` | local, model-free self-test of the harness (fake checkpoints; never a measurement) |
| `p1b_driver_selftest.ps1` | model-free test of the driver's process bookkeeping (run by `p1b_selftest.py`) |

Run the self-test before publishing a change to this directory, with an interpreter that has the locked
dependencies:

    python -B tools/qualification/p1b/p1b_selftest.py

The receipt (`p1b-receipt.json`), per-process outputs and samples are uploaded as the run's artifact
`p1b-qualification-<run id>-<attempt>`. The verdict is PASS, FAIL or INCONCLUSIVE (exit 0, 1 or 2).

P1b never arms `DEBERTA_RELEASE_GATES.packaged_runtime_acceptance`, never covers G1 categorical parity (private
material is not uploaded) and does not modify the P1 harness, workflow or evidence (`tools/qualification/p1/`).
