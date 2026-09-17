"""Run 0.5 component-calibration harness (decomposition + minimum-sufficient-context).

Replay-and-calibration only: it reuses the completed baseline's frozen DB copy and stage artifacts so no
embeddings / discovery / retrieval / NLI / verification / coverage / recovery / terminal work reruns
while the two upstream Qwen control tasks are tuned. Production code is imported read-only and never
modified. See `.claude/docs/research/2026-09-07_ask-run-0.5-control-plane-pivot.md`.
"""
