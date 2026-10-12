"""Experimental evidence-admission policy for the reviewed Ask route (Phase 34 B2 pilot).

B2 is the minimal policy the evidence-admission bakeoff identified: the chunk-similarity admission gate
is disabled and NLI support must reach 0.90. Exact-quote verification and the contradiction veto are the
shared verifier's own, unchanged. Nothing selects this policy by default: a caller opts in by passing it
to ``runtime.build_runtime(verification_config=...)``. The shared ``VerificationConfig`` defaults, the
application's summarize path and every historical runner keep the 0.70 / 0.55 thresholds.

Setting ``retrieval_threshold`` to 0.0 disables the logical gate only. The verifier still embeds the claim
and still computes and records the claim-to-chunk similarity; no model work is avoided. One side effect:
with the gate always satisfied, a non-admitted record is labelled ``weak`` and never ``unverified``.
"""

from app.backend.summarization.verification import VerificationConfig

B2_PILOT_VERIFICATION_CONFIG = VerificationConfig(retrieval_threshold=0.0, support_threshold=0.90)
