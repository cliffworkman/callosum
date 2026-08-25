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


def validated_overview_items(produced: object, verified_ordinals: list[int]) -> list[dict[str, object]]:
    """Apply the production sentence/reference filter to untrusted Overview output."""
    items: list[dict[str, object]] = []
    for sentence in produced if isinstance(produced, list) else []:
        ordinals = sorted(
            {verified_ordinals[index] for index in sentence.claim_indices if 0 <= index < len(verified_ordinals)}
        )
        if sentence.text.strip() and ordinals:
            items.append({"text": sentence.text.strip(), "claim_ordinals": ordinals})
    return items
