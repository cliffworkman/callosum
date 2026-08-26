# Incumbent cloud calibration benchmark v1

This developer-only study applies the unchanged `synthesis-overview-v1` mechanics to Callosum's incumbent Gemini
model and then continues through the full qualification fixture set as descriptive calibration evidence. It does
not alter, reopen, or reinterpret the historical local-model qualification receipts.

Raw synthetic provider responses, reviewer packets, decode keys, and credentials remain outside git. The tracked
receipt index contains only time-bound provider identity, token/cost aggregates, mechanical outcomes, hashes, and
packet readiness.

The challenge holdout is deliberately unavailable to the calibration runner.

The first execution exposed an operational runner defect: Track A and Track B separately reset a study-wide retry
counter. `protocol-amendment-1.json` preserves and invalidates those pilot receipts, carries the retry budget across
tracks, and adds conservative request pacing without changing any scientific input or rule. The amended execution
then exhausted all three authorized provider quotas after six Track A responses. No valid Track A verdict, Track B
calibration set, or human packet was produced; see `provider-infrastructure-failure.json`.

`execution-freeze.json` preserves the exact amended runner identity used live. `freeze.json` is the validated
post-execution harness identity after lint-only maintenance and is the manifest to use for a future full rerun.
