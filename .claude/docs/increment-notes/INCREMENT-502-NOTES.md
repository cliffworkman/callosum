# Increment 502 — Incumbent cloud calibration infrastructure

**Date:** 2026-08-25/26
**Production behavior:** unchanged

## Outcome

Added a developer-only, privacy-safe cloud calibration harness for the frozen `synthesis-overview-v1` battery. It
uses the production Overview prompt, parser, and reference filter; applies the historical Stage 1 mechanics
literally; forbids holdout access; accounts for tokens/retries/cost; and can prepare a genuinely mixed blinded
Gemini/local packet without putting identity in the reviewer artifact.

The first live execution exposed a process-bound retry-counter defect and then a sustained Gemini quota wall. The
pilot was excluded from evidence. A frozen operational amendment carried the retry budget across Track A/Track B
and paced requests without changing scientific semantics. On the clean rerun, six Track A requests succeeded and
all three authorized credentials then returned quota errors until the 12-retry ceiling was reached.

Therefore the result is **GEMINI PROVIDER/INFRASTRUCTURE FAILURE**. There is no valid Gemini qualification verdict,
complete Track B calibration run, blinded packet, or scientific inference. The challenge holdout remains unopened.

## Invariants

- Historical Phase 4/4.1 receipts and battery hashes are unchanged.
- Only frozen synthetic fixtures may leave the machine.
- Raw provider output and credentials remain outside git.
- Calibration continuation cannot mutate the formal Track A verdict.
- Human review remains the only semantic authority.
- Production provider defaults, routing, and Overview behavior are untouched.

## Resume condition

Resume by rerunning both tracks from the beginning with sufficient Gemini paid quota under the amended frozen
manifest. Do not reuse the invalidated pilot or partial amended Track A as scientific evidence.
