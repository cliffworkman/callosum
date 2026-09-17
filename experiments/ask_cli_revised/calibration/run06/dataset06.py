"""Frozen Run 0.6 decomposition dataset: the AIB benchmark + two new user-supplied complex questions +
the four Run 0.5 app-history controls, all frozen (verbatim + per-question hash) before any inference.

The two NEW questions are user-supplied (2026-09-07 steering), not invented after seeing Run 0.6 behavior;
they are the complex multi-request stress cases Run 0.5 lacked. Their exact text is frozen here and hashed
into `00_frozen.json`. The AIB benchmark + hash come from `question.py` unchanged.
"""

from __future__ import annotations

import hashlib

from experiments.ask_cli_revised.calibration.datasets import _APP_HISTORY_QUESTIONS
from experiments.ask_cli_revised.calibration.run06.segment import segment_source_units_v2
from experiments.ask_cli_revised.question import BENCHMARK_QUESTION

# --- the two NEW user-supplied questions (verbatim; do not rewrite or "improve") ----------------------

DEPRESSION_QUESTION = (
    "Synthesize the neural and biological systems implicated in late-life depression and its relationship "
    "to cognitive decline and dementia based on the literature in my library. I am particularly interested "
    "in serotonergic function, amyloid, glucose metabolism, gray-matter structure, memory and executive "
    "function, and other relevant neurobiological or cognitive findings. Give me a structured account of "
    "the systems and processes involved, what role each appears to play, and where the literature reports "
    "mixed, null, or uncertain findings."
)

BUILT_ENV_QUESTION = (
    "I want you to do a synthesis of the brain areas involved in the human perception of built environment "
    "based on fMRI and EEG studies. I am interested in aesthetic appreciation, coherence, fascination, "
    "hominess, ceiling height, visuospatial processing and more. Give me a list of the brain areas involved "
    "and their role."
)

# Rich questions get the full treatment (selection -> freeze -> walk -> lineage). All are dev.
RICH_CASE_IDS = ("q_aib", "q_depr", "q_builtenv")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def decomposition_cases_v06() -> list[dict]:
    """The 7-question frozen Run 0.6 set. The three rich questions are dev + walked; q_h3/q_h4 held out."""
    cases = [
        {"case_id": "q_aib", "text": BENCHMARK_QUESTION, "source": "frozen-benchmark", "split": "dev", "rich": True},
        {"case_id": "q_depr", "text": DEPRESSION_QUESTION, "source": "user-supplied-2026-09-07", "split": "dev", "rich": True},
        {"case_id": "q_builtenv", "text": BUILT_ENV_QUESTION, "source": "user-supplied-2026-09-07", "split": "dev", "rich": True},
    ]
    held = {"q_h3", "q_h4"}
    for cid, text in _APP_HISTORY_QUESTIONS:
        cases.append(
            {
                "case_id": cid,
                "text": text,
                "source": "app-history",
                "split": "held_out" if cid in held else "dev",
                "rich": False,
            }
        )
    return cases


def frozen_manifest() -> dict:
    """The frozen-dataset record for 00_frozen.json (verbatim questions + hashes + segmentation preview)."""
    cases = decomposition_cases_v06()
    return {
        "cases": [
            {
                "case_id": c["case_id"],
                "source": c["source"],
                "split": c["split"],
                "rich": c["rich"],
                "text": c["text"],
                "question_hash": _hash(c["text"]),
                "n_source_units": len(segment_source_units_v2(c["text"])),
            }
            for c in cases
        ]
    }
