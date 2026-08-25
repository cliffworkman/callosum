# Synthesis Overview qualification profile v1

This developer-only battery qualifies exact local runtime/model/execution configurations for the supplementary
Synthesis Overview task. It does not qualify a model family, other Callosum features, or any user-facing Automatic
AI target.

The preregistration, synthetic fixtures, controls, semantic codebook, candidate manifest, production contract files,
and runner were frozen before candidate output. `freeze.json` records their hashes. `receipt-index.json` records only
privacy-safe identities and aggregate outcomes; raw synthetic outputs stay in gitignored external research storage.

Run the local harness checks with:

```text
python tools/qualification/overview_battery.py validate-controls
pytest tests/test_overview_qualification.py -q
```

The 2026-08-25 search tested eight pinned candidates. None survived all preregistered reliability gates, so no human
candidate adjudication or challenge holdout was run and no synthesis-Overview qualification was granted. Extend the
candidate search without weakening gates or changing this frozen profile. A changed prompt, runtime bundle, model
artifact, quantization, chat template, generation setting, or observed backend requires a new exact receipt.
