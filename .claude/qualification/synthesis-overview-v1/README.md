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

Phase 4.1 kept this profile byte-for-byte frozen and tested a separately frozen seven-artifact CUDA cohort recorded
in `phase4-1-candidates.json` and `phase4-1-freeze.json`. All seven exact configurations failed Stage 1, so Stage 2,
human candidate adjudication, and the challenge holdout remained closed. Privacy-safe aggregate outcomes and external
raw-receipt hashes are recorded in `phase4-1-receipt-index.json`; model weights and raw outputs remain outside git.

## Re-freeze 2026-09-04 (inc 575) — `providers.py` hash only; no qualified configuration changed

`freeze.json` was regenerated because `app/backend/llm/providers.py` — one of the ten frozen inputs —
changed while fixing a user-facing synthesis failure (a truncated model answer surfacing as a raw
`JSONDecodeError`). Recording it here because a silently-updated hash on a preregistered profile is
exactly what this file exists to prevent.

**What changed in that file**

1. `CompletionResult.truncated`, a defaulted field, plus `_is_truncation_reason()` — read the
   `finish_reason` / `stop_reason` the provider *already returned* and previously discarded. No request
   field is altered by any of this.
2. `_MAX_TOKENS` 2048 → 4096 — a real generation-setting change, but **only on the `messages`
   (Anthropic) wire**.

**Why the prior receipts remain valid.** The README's own rule is that a changed generation setting
requires a new exact receipt. None of this battery's candidates is affected:

- All eight candidates (and Phase 4.1's seven) are **local publisher-owned GGUF artifacts** executed
  through llama.cpp, so they run the managed-local `chat_completions` path — never the Anthropic wire
  that `_MAX_TOKENS` governs.
- The Overview contract's own output cap is `256` (`managed_local.py`, `cap = 256 if contract ==
  _OVERVIEW_CONTRACT`) and is **unchanged**. Overview generation settings are therefore byte-identical
  to what produced `receipt-index.json` and `phase4-1-receipt-index.json`.

`starting_head` is deliberately left at `2ba735a`: the profile genuinely *was* frozen before candidate
output at that commit, and rewriting it to today's HEAD would assert a re-establishment that did not
happen. Only the file hashes move.

No gate was weakened, no fixture, control, codebook, candidate manifest, or preregistration was touched,
and no qualification outcome changes: the 2026-08-25 search and Phase 4.1 both still granted none.
