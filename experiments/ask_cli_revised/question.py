"""Stage 0: the frozen benchmark question. Do not rewrite or improve it (first-run freeze)."""

from __future__ import annotations

import hashlib

BENCHMARK_QUESTION = (
    "how does the anomalous is bad bias manifest in brain, behavior, and attitudes? please return "
    "specific brain areas and whether and how they relate to behaviors, which kinds of behaviors, and "
    "whether they relate to attitudes, and which kinds of attitudes. what kind of specific personality "
    "traits relate to its manifestation? and using which scales? is there any cross-cultural evidence for "
    "the bias? which cultures and how was this measures? and are there effective interventions aimed at "
    "reducing it?"
)


def question_hash() -> str:
    return hashlib.sha256(BENCHMARK_QUESTION.encode("utf-8")).hexdigest()
