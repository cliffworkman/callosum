"""Standalone experimental staged-synthesis CLI.

This package is isolated from production Ask and runs only against a copied library database.

Design invariants:
- Managed-local Qwen is the only model used for intermediate natural-language interpretation.
- Qwen tasks are deliberately split into one bounded reading/judgment operation per call.
- Natural-language answer obligations are canonical; model-generated ontology labels and IDs are not load-bearing.
- Cloud synthesis is terminal-only and opt-in. The default experiment spends no cloud credits.
- The existing verifier and thresholds remain unchanged.
- Retrieval anchors and evidence anchors remain distinct and fully provenance-traced.
- Exact evidence text is selected by ID from deterministic source spans, so Qwen never has to reproduce quotes.
"""
