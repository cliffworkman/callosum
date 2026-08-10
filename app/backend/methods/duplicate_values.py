"""Repeated-values checker (inc 469) — a blunt data-fabrication smell: how often does each exact reported
value repeat within one paper's own table? Inspired by `scrutiny`'s duplicate_count/duplicate_tally
(Lukas Jung), which the package's own docs call "a blunt tool... not too informative" — unlike GRIM/GRIMMER/
DEBIT, there is no peer-reviewed method behind this, so it deliberately carries no consistent/flagged verdict,
just a plain frequency breakdown (Principles #2 — signal, not verdict; nothing here rises to a claim).

Assisted, per-value, deterministic, local, no-LLM: the user pastes the specific values they're reading (we do
NOT scan the paper) — inherently non-accusatory, same posture as GRIM/GRIMMER/DEBIT.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

MAX_VALUES = 500


@dataclass(frozen=True)
class RepeatedValuesResult:
    total: int
    distinct: int
    repeats: list[dict]  # [{"value": str, "count": int}, ...] — count > 1 only, sorted by count desc then value
    note: str


def count_repeated_values(values: list[str]) -> RepeatedValuesResult:
    cleaned = [v.strip() for v in values if v.strip()]
    if not cleaned or len(cleaned) > MAX_VALUES:
        raise ValueError(f"enter between 1 and {MAX_VALUES} values")
    counts = Counter(cleaned)
    repeats = sorted(
        ({"value": v, "count": c} for v, c in counts.items() if c > 1),
        key=lambda r: (-r["count"], r["value"]),
    )
    note = (
        "No exact value repeats more than once."
        if not repeats
        else (
            f"{len(repeats)} value{'s' if len(repeats) != 1 else ''} repeat{'s' if len(repeats) == 1 else ''}. "
            "Repeated values are common in real bounded/rounded data and are not, by themselves, evidence of "
            "anything — a blunt heuristic with no peer-reviewed method behind it, unlike GRIM/GRIMMER/DEBIT. A "
            "prompt to double-check your own transcription or look closer, never a verdict."
        )
    )
    return RepeatedValuesResult(len(cleaned), len(counts), repeats, note)
