"""Sentence units with exact offsets, and the join of a sentence split across a verified chunk seam.

A unit is a navigation aid for the localizer and a locator for the packet: each `Piece` is an exact slice of one chunk's text
(`chunk.text[start:end] == piece.text`). A unit that spans a chunk boundary is built ONLY when the seam verifier established
continuity; otherwise both halves stay separate, flagged as open fragments. Pure: no connection, no model, no network.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_ABBREVIATIONS = frozenset(
    {
        "al", "fig", "figs", "eq", "eqs", "vs", "cf", "dr", "mr", "ms", "mrs", "prof", "no", "nos", "approx", "ca",
        "etc", "sec", "ref", "refs", "vol", "pp", "p", "st", "inc", "ltd", "e.g", "i.e", "resp", "ed", "eds",
    }
)  # fmt: skip
_BOUNDARY = re.compile(r"""[.!?]+["”’')\]]*(?:\d{1,3}(?:[,–\-]\d{1,3})*)?\s+|\n{2,}""")
_TERMINAL_TAIL = re.compile(r"""[.!?]["”’')\]]*(?:\s*\d{1,3}(?:[,–\-]\d{1,3})*)?\s*$""")
_LAST_WORD = re.compile(r"([A-Za-z][A-Za-z.]*)$")


@dataclass(frozen=True)
class Piece:
    chunk_id: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class SentenceUnit:
    unit_id: str
    pieces: tuple[Piece, ...]
    text: str  # display text: pieces joined by one space; never used as a single verbatim quotation
    join: str  # "none" | "verified_seam"
    seam: dict | None  # the verdict record behind a join, or the unresolved verdict behind an open fragment
    open_left: bool  # begins as a continuation of text we could not join to (fragment)
    open_right: bool  # ends without terminal punctuation and no verified join (fragment)


def ends_terminal(text: str) -> bool:
    return bool(_TERMINAL_TAIL.search(text.rstrip()))


def starts_as_continuation(text: str) -> bool:
    for ch in text:
        if ch.isalpha():
            return ch.islower()
        if ch.isdigit() or ch in "\"“‘'([":
            return False
    return False


def _is_boundary(text: str, match: re.Match) -> bool:
    if match.group(0).startswith("\n"):
        return True
    before = text[: match.start()]
    tail = text[match.start() : match.end()]
    if before and before[-1].isdigit() and re.match(r"[.!?]\d", tail):
        return False  # a decimal such as 1.5, not a sentence end followed by a citation numeral
    word = _LAST_WORD.search(before)
    if word:
        token = word.group(1).rstrip(".").lower()
        if token in _ABBREVIATIONS or (len(token) == 1 and word.group(1)[0].isupper()):
            return False
    rest = text[match.end() :]
    for ch in rest:
        if ch.isspace():
            continue
        return not ch.islower()
    return True


def segment(text: str) -> list[tuple[int, int]]:
    """Exact (start, end) offsets of sentence-ish units; `text[start:end]` never includes surrounding whitespace."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        if not _is_boundary(text, match):
            continue
        end = match.start() + len(match.group(0).rstrip())
        if match.group(0).startswith("\n"):
            end = match.start()
        _push(text, spans, start, end)
        start = match.end()
    _push(text, spans, start, len(text))
    return spans or ([(0, len(text.rstrip()))] if text.strip() else [])


def _push(text: str, spans: list, start: int, end: int) -> None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        spans.append((start, end))


def chunk_pieces(chunk_id: int, text: str) -> list[Piece]:
    return [Piece(chunk_id, s, e, text[s:e]) for s, e in segment(text)]


SeamVerifier = Callable[[dict, dict], object]  # (chunk_a, chunk_b) -> SeamVerdict-like with .state / .reasons / .checks


def _verdict_record(verdict) -> dict:
    return {"state": verdict.state, "reasons": list(verdict.reasons), "checks": dict(verdict.checks)}


def build_units(chunks: list[dict], verify_seam: SeamVerifier) -> list[SentenceUnit]:
    """Units over ordered chunks. `chunks[i]` needs `chunk_id` and `text`; the verifier gets the full chunk dicts.

    A sentence that runs past the end of a chunk is a CHAIN: it is joined across chunks only if EVERY adjacent seam in the chain
    verifies (the verifier decides; line-level chunking can put one sentence across many chunks). If any seam fails, the chain
    is cut there into separate open fragments, each flagged, and nothing is merged across the failed seam.
    """
    per_chunk = [chunk_pieces(c["chunk_id"], c["text"]) for c in chunks]
    out: list[SentenceUnit] = []
    counter = 0
    chain: dict | None = None

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"s{counter}"

    def flush(open_right: bool, seam: dict | None = None) -> None:
        nonlocal chain
        if chain is None:
            return
        pieces = tuple(chain["pieces"])
        joined = len(pieces) > 1
        record = {"state": "established", "joins": chain["seams"]} if joined else seam
        out.append(
            SentenceUnit(
                next_id(), pieces, " ".join(p.text for p in pieces), "verified_seam" if joined else "none", record,
                chain["open_left"], open_right,
            )
        )  # fmt: skip
        chain = None

    for index, pieces in enumerate(per_chunk):
        if not pieces:
            continue
        start = 0
        if chain is not None:
            first = pieces[0]
            if index == chain["last_index"] + 1 and starts_as_continuation(first.text):
                verdict = verify_seam(chunks[chain["last_index"]], chunks[index])
                record = _verdict_record(verdict)
                if verdict.state == "established":
                    chain["pieces"].append(first)
                    chain["seams"].append(record)
                    chain["last_index"] = index
                    start = 1
                    if len(pieces) == 1 and not ends_terminal(first.text) and index + 1 < len(chunks):
                        continue  # the sentence is still open: wait for the next chunk
                    flush(open_right=not ends_terminal(first.text))
                else:
                    flush(open_right=True, seam=record)
            elif index == chain["last_index"] + 1:
                # the next chunk visibly starts a NEW sentence: the carried unit is complete without terminal punctuation
                # (a heading, a list item, a reference entry), not an open fragment
                flush(open_right=False)
            else:
                flush(open_right=True, seam={"state": "not_established", "reasons": ["not_adjacent"], "checks": {}})
        for i in range(start, len(pieces)):
            piece = pieces[i]
            is_last = i == len(pieces) - 1
            open_left = start == 0 and i == 0 and starts_as_continuation(piece.text)
            if is_last and not ends_terminal(piece.text) and index + 1 < len(chunks):
                chain = {"pieces": [piece], "seams": [], "last_index": index, "open_left": open_left}
            else:
                out.append(
                    SentenceUnit(
                        next_id(), (piece,), piece.text, "none", None, open_left, not ends_terminal(piece.text)
                    )
                )
    flush(open_right=True, seam={"state": "not_established", "reasons": ["last_chunk"], "checks": {}})
    return out
