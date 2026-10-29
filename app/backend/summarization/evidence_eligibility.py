"""Substantive-evidence eligibility for reference and navigation material (reference-exclusion repair).

A reference-list entry can establish that a paper was *cited*; it cannot establish that the citing paper
*observed* the finding its title describes. This module decides, per evidence unit, whether the unit may fill a
substantive-evidence reading slot. Navigation eligibility (bibliography browsing, citation lookup) is a separate
property and is never revoked here: nothing in this module deletes, truncates or rewrites source text.

Pure by design -- no connection, file read or network call. Callers resolve classifications and hand them in,
which keeps every decision reproducible from literals (``tests/test_evidence_eligibility.py``).

Precedence (``decide``), strongest first:

1. **Verified native exclusion** -- the union of confidently mapped native ``exclude_reference`` (or reference +
   navigation-only) regions covers >= ``NATIVE_COVERAGE_THRESHOLD`` of the unit's comparison key. Withheld from
   substantive slots. Units shorter than ``MIN_UNIT_KEY_CHARS`` are only *disputed*, never withheld on coverage.
2. **Current anchored ``bibliographic`` label** (``chunk_structure``, Crossref DOI/title anchored). Documented
   ~77% precision, so it only *demotes* (``disputed``) and records the disagreement; it never withholds.
3. Native inclusion / partial (mixed) coverage -- eligible; excluded spans stay attached with their provenance.
4. Stale classifications and unresolved joins are recorded and ignored for the decision.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from app.backend.pdf_processing.extraction import _canonicalize_text

POLICY_VERSION = "reference-evidence-eligibility-v1"

# Investigation candidate (q_lld reference-leakage investigation, 2026-10-28): normalized union coverage at 0.85
# withheld 44/75 confirmed bibliography units with no false positive among the 335 delivered units checked. That
# zero applies to that sample only: elsewhere in the same corpus native exclusion withholds genuine Methods/Results
# prose (known-limitation fixtures in experiments/.../test_reference_eligibility_frozen.py). A candidate, not a
# universally validated constant -- it is named here so tests and receipts can pin it.
NATIVE_COVERAGE_THRESHOLD = 0.85
# A guarded (Docling) unit counts as anchored-bibliographic only when current-bibliographic legacy text covers
# this much of it. Same value as the native threshold so the two authorities are judged on one scale.
ANCHORED_COVERAGE_THRESHOLD = 0.85
# A cross-extractor text join is "verified" only when the matched legacy spans cover this much of the unit.
JOIN_VERIFIED_COVERAGE = 0.90
# Shorter comparison keys (page numbers, panel labels, "Table 2") cannot be uniquely matched...
MIN_MATCH_KEY_CHARS = 25
# ...and units shorter than this are never withheld on coverage alone (table labels, short captions): disputed.
MIN_UNIT_KEY_CHARS = 60

REFERENCE_DECISIONS = frozenset({"exclude_reference"})
NAVIGATION_DECISIONS = frozenset({"retain_navigation"})
DEMOTED_ANCHORED_ROLES = frozenset({"bibliographic"})

MATCH_KINDS = ("region_within_unit", "unit_within_region", "region_tail_at_unit_start", "region_head_at_unit_end")
FAILED_STATES = ("region_too_short", "unit_too_short", "ambiguous_repeated_in_unit", "no_match")


def comparison_key(text: str) -> tuple[str, list[int]]:
    """Lower-cased alphanumeric comparison key plus, per key character, its offset in the ORIGINAL text.

    Built on the production quote canonicalizer (ligatures, soft hyphens, dash equivalents, hyphenated line
    breaks), then reduced to alphanumerics so extractor whitespace/punctuation/"Wash- ington" differences vanish.
    The offset list is what lets a key-space match be reported as exact original character offsets.
    """
    canonical, origin = _canonicalize_text(text or "", list(range(len(text or ""))))
    chars: list[str] = []
    offsets: list[int] = []
    for char, position in zip(canonical, origin, strict=True):
        for lowered in char.lower():
            if lowered.isalnum():
                chars.append(lowered)
                offsets.append(int(position))  # type: ignore[arg-type]
    return "".join(chars), offsets


@dataclass(frozen=True)
class KeyedText:
    """A text with its comparison key and identity, computed once and reused across many comparisons."""

    identity: str
    text: str
    key: str
    offsets: tuple[int, ...]
    text_sha256: str

    @classmethod
    def build(cls, identity: str, text: str) -> KeyedText:
        key, offsets = comparison_key(text)
        return cls(identity, text, key, tuple(offsets), hashlib.sha256((text or "").encode("utf-8")).hexdigest())

    def original_span(self, key_start: int, key_end: int) -> tuple[int, int]:
        return self.offsets[key_start], self.offsets[key_end - 1] + 1


@dataclass(frozen=True)
class SpanMatch:
    region_id: str
    region_decision: str
    region_text_sha256: str
    kind: str
    key_start: int  # in the unit's key
    key_end: int
    start: int  # exact offsets in the unit's ORIGINAL text
    end: int

    def as_record(self) -> dict:
        return {
            "region_id": self.region_id,
            "region_decision": self.region_decision,
            "region_text_sha256": self.region_text_sha256,
            "match_kind": self.kind,
            "start": self.start,
            "end": self.end,
        }


def _tail_at_start(region: str, unit: str) -> int:
    """Longest proper suffix of ``region`` that is a prefix of ``unit`` (>= MIN_MATCH_KEY_CHARS), else 0."""
    anchor, best = unit[:MIN_MATCH_KEY_CHARS], 0
    position = region.find(anchor, 1)
    while position != -1:
        length = len(region) - position
        if length <= len(unit) and unit.startswith(region[position:]):
            best = max(best, length)
        position = region.find(anchor, position + 1)
    return best


def _head_at_end(region: str, unit: str) -> int:
    """Longest proper prefix of ``region`` that is a suffix of ``unit`` (>= MIN_MATCH_KEY_CHARS), else 0."""
    anchor, best = unit[-MIN_MATCH_KEY_CHARS:], 0
    position = region.find(anchor)
    while position != -1:
        length = position + MIN_MATCH_KEY_CHARS
        if length < len(region) and length <= len(unit) and unit.endswith(region[:length]):
            best = max(best, length)
        position = region.find(anchor, position + 1)
    return best


def map_region(region: KeyedText, decision: str, unit: KeyedText) -> tuple[str, SpanMatch | None]:
    """Map one native region onto one unit in comparison-key space. Returns ``(state, match)``.

    ``state`` is a ``MATCH_KINDS`` value with a match, or a ``FAILED_STATES`` value with ``None``. A region that
    occurs more than once inside the unit is ambiguous and contributes nothing: repeated similar text is never
    treated as a uniquely verified location. No character alignment is ever fabricated -- offsets come only from
    key characters that actually matched.
    """
    rk, uk = region.key, unit.key
    if len(rk) < MIN_MATCH_KEY_CHARS:
        return "region_too_short", None
    if len(uk) < MIN_MATCH_KEY_CHARS:
        return "unit_too_short", None

    def match(kind: str, key_start: int, key_end: int) -> SpanMatch:
        start, end = unit.original_span(key_start, key_end)
        return SpanMatch(region.identity, decision, region.text_sha256, kind, key_start, key_end, start, end)

    first = uk.find(rk)
    if first != -1:
        if uk.find(rk, first + 1) != -1:
            return "ambiguous_repeated_in_unit", None
        return "region_within_unit", match("region_within_unit", first, first + len(rk))
    if rk.find(uk) != -1:
        return "unit_within_region", match("unit_within_region", 0, len(uk))
    tail = _tail_at_start(rk, uk)
    if tail:
        return "region_tail_at_unit_start", match("region_tail_at_unit_start", 0, tail)
    head = _head_at_end(rk, uk)
    if head:
        return "region_head_at_unit_end", match("region_head_at_unit_end", len(uk) - head, len(uk))
    return "no_match", None


def union_coverage(key_length: int, matches: Iterable[SpanMatch]) -> float:
    """Fraction of a unit's key covered by the union of the given matches (overlaps counted once)."""
    if key_length <= 0:
        return 0.0
    covered, last_end = 0, 0
    for start, end in sorted((m.key_start, m.key_end) for m in matches):
        start = max(start, last_end)
        if end > start:
            covered += end - start
            last_end = end
    return covered / key_length


@dataclass(frozen=True)
class NativeCoverage:
    """Confidently mapped native regions on one unit, split by authority."""

    key_length: int
    matches: tuple[SpanMatch, ...] = ()

    def fraction(self, decisions: frozenset[str]) -> float:
        return union_coverage(self.key_length, (m for m in self.matches if m.region_decision in decisions))


@dataclass(frozen=True)
class AnchoredState:
    """The anchored ``chunk_structure`` evidence for one unit, after identity/freshness/join checks.

    ``state``: ``current_bibliographic`` | ``current_partial`` | ``current_other`` | ``stale`` | ``absent`` |
    ``join_unresolved``. ``coverage`` is the fraction of the unit covered by current demoted-role text.
    """

    state: str
    coverage: float = 0.0
    detail: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityDecision:
    unit_id: str
    substantive: str  # eligible | disputed | withheld
    decision: str
    reasons: tuple[str, ...]
    native_reference_coverage: float
    native_nonsubstantive_coverage: float
    anchored: AnchoredState
    native_unit_role: str | None
    excluded_spans: tuple[SpanMatch, ...]
    disagreements: tuple[dict, ...]
    navigation_eligible: bool = True
    policy_version: str = POLICY_VERSION

    def as_record(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "policy_version": self.policy_version,
            "substantive_eligibility": self.substantive,
            "navigation_eligibility": "eligible" if self.navigation_eligible else "ineligible",
            "decision": self.decision,
            "reasons": list(self.reasons),
            "native_reference_coverage": round(self.native_reference_coverage, 4),
            "native_nonsubstantive_coverage": round(self.native_nonsubstantive_coverage, 4),
            "anchored": {
                "state": self.anchored.state,
                "coverage": round(self.anchored.coverage, 4),
                **self.anchored.detail,
            },
            "native_unit_role": self.native_unit_role,
            "excluded_spans": [m.as_record() for m in self.excluded_spans],
            "disagreements": list(self.disagreements),
        }


def decide(
    unit_id: str,
    *,
    key_length: int,
    native: NativeCoverage | None,
    anchored: AnchoredState,
    native_unit_role: str | None = None,
) -> EligibilityDecision:
    """Apply the documented precedence. Never returns ``withheld`` on an anchored label alone."""
    native = native or NativeCoverage(key_length)
    ref = native.fraction(REFERENCE_DECISIONS)
    nonsub = native.fraction(REFERENCE_DECISIONS | NAVIGATION_DECISIONS)
    spans = tuple(sorted(native.matches, key=lambda m: (m.start, m.end, m.region_id)))
    reasons: list[str] = []
    disagreements: list[dict] = []
    anchored_bib = anchored.state == "current_bibliographic"
    if anchored.state == "stale":
        reasons.append("anchored_classification_stale_ignored")
    elif anchored.state == "join_unresolved":
        reasons.append("anchored_join_unresolved_ignored")
    elif anchored.state == "current_partial":
        reasons.append("anchored_partial_bibliographic_not_enforced")

    def result(substantive: str, decision: str) -> EligibilityDecision:
        return EligibilityDecision(
            unit_id,
            substantive,
            decision,
            tuple(reasons),
            ref,
            nonsub,
            anchored,
            native_unit_role,
            spans,
            tuple(disagreements),
        )

    native_says_reference = ref >= NATIVE_COVERAGE_THRESHOLD
    native_says_nonsubstantive = nonsub >= NATIVE_COVERAGE_THRESHOLD
    if native_says_reference or native_says_nonsubstantive:
        kind = "native_reference_exclusion" if native_says_reference else "native_navigation_only"
        if (
            anchored.state == "current_other"
            and anchored.detail.get("roles")
            and "scientific" in anchored.detail["roles"]
        ):
            disagreements.append({"native": kind, "anchored": "scientific", "resolution": "native_verified_wins"})
        if key_length < MIN_UNIT_KEY_CHARS:
            reasons.append("short_unit_coverage_not_enforced")
            return result("disputed", f"{kind}_short_unit_disputed")
        return result("withheld", kind)
    if anchored_bib:
        disagreements.append(
            {
                "native": native_unit_role or "not_independently_classified",
                "anchored": "bibliographic",
                "resolution": "demoted_not_withheld",
            }
        )
        return result("disputed", "anchored_bibliographic_disputed")
    if nonsub > 0:
        reasons.append("mixed_unit_excluded_spans_preserved")
        return result("eligible", "eligible_mixed")
    return result("eligible", "eligible")


@dataclass(frozen=True)
class SlotSelection:
    selected: tuple[tuple[str, str], ...]  # (unit_id, substantive status)
    withheld: tuple[str, ...]
    demoted_unused: tuple[str, ...]
    disputed_fallback: tuple[str, ...]
    shortage: int

    def as_record(self) -> dict:
        return {
            "selected": [{"unit_id": u, "substantive_eligibility": s} for u, s in self.selected],
            "withheld": list(self.withheld),
            "demoted_unused": list(self.demoted_unused),
            "disputed_fallback": list(self.disputed_fallback),
            "shortage": self.shortage,
        }


def select_slots(
    ranked_unit_ids: Sequence[str], decisions: dict[str, EligibilityDecision], budget: int
) -> SlotSelection:
    """Fill a fixed reading budget: eligible units in rank order, then disputed units only to backfill.

    Withheld units never take a substantive slot. A disputed unit is used only when eligible candidates run out,
    and is then reported as ``disputed_fallback`` rather than silently passing as ordinary evidence. A unit with no
    decision is treated as eligible (silence is not a certificate either way). Any unfilled remainder is reported
    as ``shortage`` -- the budget is never padded with known-excluded material.
    """
    eligible, disputed, withheld = [], [], []
    for unit_id in ranked_unit_ids:
        status = decisions[unit_id].substantive if unit_id in decisions else "eligible"
        (withheld if status == "withheld" else disputed if status == "disputed" else eligible).append(unit_id)
    chosen = [(u, "eligible") for u in eligible[:budget]]
    fallback = disputed[: max(0, budget - len(chosen))]
    chosen += [(u, "disputed") for u in fallback]
    return SlotSelection(
        tuple(chosen),
        tuple(withheld),
        tuple(disputed[len(fallback) :]),
        tuple(fallback),
        max(0, budget - len(chosen)),
    )
