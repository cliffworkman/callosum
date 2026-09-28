"""Stable evidence identity and collision detection for the c9+c11 vertical slice's integration layer
(2026-09-27).

**Why this module exists, verified against the real packet-building code, not assumed:** `packet.py::_part`
assigns `span_id` (`"p1"`, `"p2"`, ...) as a pure, packet-local sequential label -- `build_packet` calls it as
`_part(f"p{n}", ...)` for `n` starting at 1 for every packet, with no relationship to the underlying chunk or
offset. Confirmed directly on the real c11 packet: `p1`..`p4` are four *different*, contiguous, non-overlapping
character ranges within the *same* chunk (43327: p1 248-436, p2 437-617, p3 618-699, p4 700-820) -- so
`(paper_id, chunk_id, span_id)` genuinely is not a stable global identity; a *different* packet's own "p1"
could land on a wholly different text range of the same chunk. `packet.py::packet_id_for` already treats
`f"{chunk_id}:{start}:{end}"` as the real, stable per-piece identity for exactly this reason -- this module
applies the same principle to the evidence this arc's own bridge projects.

**What this module intentionally does not do:** it does not, and must not, change the meaning of an
already-saved overview run's own `U1`/`U2`/`U3` unit ids -- those are local to the one run that produced them,
frozen in that run's own saved record, and untouched. It only strengthens how *new* code joins fresh manifest
evidence against a saved record's locators, and checks the manifest's own internal consistency before it does.
"""

from __future__ import annotations


class SpanIdentityCollision(RuntimeError):
    """Two accepted spans share the same coarse `(paper_id, chunk_id, span_id)` key but represent different
    text -- the packet-local `span_id` label failed to disambiguate them. Raised rather than silently picking
    one (by order, by first match, or by text) -- see this module's own docstring for why the coarse key can
    collide at all."""


class SavedRecordTextMismatch(RuntimeError):
    """A saved overview run's unit matched a manifest span by locator, but the two texts differ. This is
    exactly the failure mode `SpanIdentityCollision` exists to catch when it reaches all the way through to an
    already-saved record -- raised instead of trusting the locator match alone."""


class DuplicateOverviewUnitLocator(RuntimeError):
    """A saved overview run's own `units[]` list has two different unit ids claiming the same locator -- an
    inconsistency in the saved record itself, not something this module can resolve by picking one."""


def canonical_locator(span: dict) -> tuple:
    """`(paper_id, chunk_id, start, end)` when the span carries offsets; the coarser
    `(paper_id, chunk_id, span_id, None)` otherwise (a span built or read without offsets -- e.g. a saved
    pre-fix record's own locator). The two shapes are never compared against each other directly; callers key
    on `coarse_key`/`fine_key` separately, below."""
    if span.get("start") is not None and span.get("end") is not None:
        return (span["paper_id"], span["chunk_id"], span["start"], span["end"])
    return (span["paper_id"], span["chunk_id"], span.get("span_id"), None)


def coarse_key(span: dict) -> tuple:
    """`(paper_id, chunk_id, span_id)` -- the packet-local key every saved overview run to date actually
    stores. Two spans sharing this key are the same evidence only if they also share the same fine-grained
    offsets; `assert_no_coarse_key_collision` checks exactly that."""
    return (span["paper_id"], span["chunk_id"], span.get("span_id"))


def assert_no_coarse_key_collision(spans: list[dict]) -> None:
    """Group `spans` by their coarse `(paper_id, chunk_id, span_id)` key. A group with more than one distinct
    `(start, end)` pair is a genuine collision -- the packet-local label failed to disambiguate two different
    text ranges -- and raises `SpanIdentityCollision` naming exactly which spans and how they differ. A group
    whose members all share the same `(start, end)` (or all lack offsets and share the same text) is legitimate
    sharing -- e.g. the same span cited by two different manifest rows -- and is not an error.
    """
    groups: dict[tuple, list[dict]] = {}
    for span in spans:
        groups.setdefault(coarse_key(span), []).append(span)
    for key, group in groups.items():
        offsets = {(s.get("start"), s.get("end")) for s in group}
        texts = {s["text"] for s in group}
        if len(offsets) > 1 or (offsets == {(None, None)} and len(texts) > 1):
            raise SpanIdentityCollision(
                f"coarse key {key!r} matches spans with different content: "
                f"offsets={sorted(offsets, key=str)} texts={sorted(texts)[:2]!r}"
            )


def build_locator_index(saved_units: list[dict]) -> dict[tuple, str]:
    """`{(paper_id, chunk_id, span_id): unit_id}` from a saved overview run's own `units[]`. Raises
    `DuplicateOverviewUnitLocator` if two different unit ids in the SAME saved record claim the same locator --
    an inconsistency in that record, never silently resolved by keeping the first or last one seen."""
    index: dict[tuple, str] = {}
    for unit in saved_units:
        for locator in unit["locators"]:
            key = (unit["paper_id"], locator["chunk_id"], locator["span_id"])
            existing = index.get(key)
            if existing is not None and existing != unit["unit_id"]:
                raise DuplicateOverviewUnitLocator(
                    f"locator {key!r} claimed by both {existing!r} and {unit['unit_id']!r} in the same saved record"
                )
            index[key] = unit["unit_id"]
    return index


def match_span_to_saved_unit(
    span: dict, locator_index: dict[tuple, str], saved_units_by_id: dict[str, dict]
) -> str | None:
    """The saved unit id matching `span`'s coarse locator, or `None` if none does. When a match is found, cross-
    checks that the saved unit's own passage text equals `span["text"]` exactly -- raising
    `SavedRecordTextMismatch` otherwise, rather than trusting the locator match alone (this is the second half
    of this module's collision defense: the packet-local key matched, but the content didn't). Raises
    `SavedRecordTextMismatch` too if the matched unit is missing its own `passage` field entirely -- a
    malformed/incomplete saved record, not something to proceed past silently."""
    unit_id = locator_index.get(coarse_key(span))
    if unit_id is None:
        return None
    saved_unit = saved_units_by_id[unit_id]
    if "passage" not in saved_unit:
        raise SavedRecordTextMismatch(
            f"locator match for {coarse_key(span)!r} -> {unit_id!r}, but the saved unit has no 'passage' field "
            "to cross-check against -- refusing to trust the locator match alone"
        )
    saved_text = saved_unit["passage"]
    if saved_text != span["text"]:
        raise SavedRecordTextMismatch(
            f"locator match for {coarse_key(span)!r} -> {unit_id!r}, but text differs: "
            f"manifest={span['text']!r} saved={saved_text!r}"
        )
    return unit_id
