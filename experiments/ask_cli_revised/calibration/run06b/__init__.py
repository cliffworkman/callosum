"""Run 0.6b — frozen evidence-screen + source-local claim-formation calibration.

A bounded, read-only downstream-component experiment. It replaces the old overloaded
``select_evidence`` control with two tiny linguistic primitives evaluated on FROZEN candidate spans
from the completed revised baseline, then replays the UNCHANGED verifier as a diagnostic.

Nothing here runs retrieval, decomposition, context growth, obligation mapping, coverage, recovery, or
terminal synthesis; nothing modifies production code, verifier code/thresholds, or any prior-run
artifact. See ``.claude`` plan and ``RUN_0_6B_REPORT.md`` for the full contract.
"""
