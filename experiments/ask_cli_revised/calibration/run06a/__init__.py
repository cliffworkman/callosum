"""Run 0.6a — offline decomposition-fidelity + selection-policy reanalysis.

Deterministic re-analysis of the FROZEN Run 0.6 candidate material. NO new model inference (no Qwen, Juno,
Ollama, Gemini), no retrieval, no discovery, no context selection. The only model used is the local
all-MiniLM embedder for the deterministic cosine audit of newly-assembled hybrids (the same primitive Run
0.5/0.6 `audit.py` uses) — never a provider call. See the approved Run 0.6a plan
(`~/.claude/plans/you-are-working-in-curious-papert.md`).
"""
