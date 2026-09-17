"""Run 0.6a — blinded Cliff fidelity-adjudication reference slice.

Deterministic, offline generator for the *independent human adjudication reference slice*
used before Run 0.7. Builds a blinded 28-specimen worksheet (Markdown) plus a machine-readable
JSON template and an integrity manifest, from the frozen Run 0.6 candidate pool ONLY.

No model inference, no retrieval, no scientific answering, no new fidelity judgments. This is
NOT "ground truth" — Run 0.7 measures agreement against this reference slice.
"""
