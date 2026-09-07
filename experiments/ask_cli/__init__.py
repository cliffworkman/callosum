"""Standalone experimental staged-synthesis CLI (scoping report REV 2, 2026-09-07).

This package is an ISOLATED EXPERIMENT, not production. It lives outside `app/` (the `tools/` precedent),
reuses production read/inference code from `app.backend.*`, never modifies production behaviour, and runs
against a COPY of a library database. See `.claude/docs/research/2026-09-07_ask-cli-experiment-scoping.md`.

Design invariants enforced here:
- ALL intermediate model-mediated work is managed-local Qwen; a failed Qwen task is experimental evidence
  (preserved + failed-closed), never masked by a cloud model.
- Cloud (Gemini) is terminal-synthesis ONLY, over the same SEALED verified ledger as a parallel Qwen synthesis.
- The verifier and its thresholds are unchanged; every proposition cites an exact verbatim quote of its
  evidence-anchor chunk.
- Retrieval anchor (why we read here) is distinct from evidence anchor (the chunk whose quote supports a claim).
"""
