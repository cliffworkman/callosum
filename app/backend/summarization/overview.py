"""Overview generation interfaces (inc 124).

A second pass that narrativizes the ALREADY-VERIFIED claims of a synthesis into a short Overview, where each
Overview sentence carries the indices of the verified claims it restates (per-sentence evidence trace). The
Overview is traceable-to-evidence, not authoritative: it works only from the verified claims and adds no new
facts; its citations are inherited from those claims (never LLM-invented).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OverviewSentence:
    text: str
    claim_indices: list[int]  # indices into the ordered ``verified_claims`` passed to generate()


class OverviewGenerator(Protocol):
    name: str

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list[OverviewSentence]:
        """Return Overview sentences, each tagged with the verified-claim indices it restates."""


@dataclass(frozen=True)
class FakeOverviewGenerator:
    sentences: list[OverviewSentence]
    name: str = "fake-overview-generator"

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list[OverviewSentence]:
        return list(self.sentences)
