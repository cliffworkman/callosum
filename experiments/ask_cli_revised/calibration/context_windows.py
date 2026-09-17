"""Deterministic A/B/C/D context envelopes around a marked central chunk + the Qwen window-selection task.

Envelopes are built ONLY from real attachment neighbors ordered by (char_start, id) — the same ordering
`experiments.ask_cli_revised.retrieval._attachment_chunks_ordered` uses. Missing neighbors at a document
boundary are stated explicitly, never faked into symmetry and never synthesized. No retrieval reruns; this
reads a library.sqlite copy only.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, select

from app.backend.persistence.schema import chunks
from experiments.ask_cli_revised.calibration.structured_output import run_schema_call

# Fixed window radii (Run 0.5 initial hypotheses; NOT changed mid-run).
WINDOW_RADII = {"A": 0, "B": 1, "C": 2, "D": 3}
WINDOW_LABELS = ("A", "B", "C", "D", "E")
WINDOW_SCHEMA = {
    "type": "object",
    "required": ["window"],
    "additionalProperties": False,
    "properties": {"window": {"type": "string", "enum": list(WINDOW_LABELS)}},
}
_WINDOW_OUTPUT_CAP = 32


def approx_tokens(chars: int) -> int:
    """Cheap, explicitly-approximate token estimate (~4 chars/token); noted as approximate everywhere."""
    return round(chars / 4)


def _ordered_attachment_chunks(conn: Connection, attachment_id: int) -> list[dict]:
    """Ordered (char_start, id) chunks of one attachment, with page_start for boundary-crossing stats.

    Mirrors retrieval._attachment_chunks_ordered's ordering; adds page_start (which that helper omits).
    """
    rows = conn.execute(
        select(chunks.c.id, chunks.c.char_start, chunks.c.page_start, chunks.c.section, chunks.c.text)
        .where(chunks.c.attachment_id == attachment_id)
        .order_by(chunks.c.char_start, chunks.c.id)
    ).all()
    return [
        {
            "chunk_id": int(r.id),
            "char_start": r.char_start,
            "page_start": r.page_start,
            "section": r.section,
            "text": str(r.text),
        }
        for r in rows
    ]


@dataclass
class WindowCase:
    case_id: str
    anchor_chunk_id: int
    attachment_id: int
    paper_id: int
    central_index: int
    windows: dict  # label -> {chunk_ids, chunks, missing_before, missing_after, n_chunks, chars, approx_tokens,
    #                          section_crossings, page_crossings, boundary_reduced}


def windows_from_ordered(ordered: list[dict], central_index: int) -> dict:
    """Pure A/B/C/D construction from an ordered chunk list (testable from literals; no DB)."""
    windows: dict = {}
    for label, radius in WINDOW_RADII.items():
        lo = max(0, central_index - radius)
        hi = min(len(ordered) - 1, central_index + radius)
        window_chunks = ordered[lo : hi + 1]
        missing_before = radius - (central_index - lo)
        missing_after = radius - (hi - central_index)
        text_join = "\n\n".join(c["text"] for c in window_chunks)
        sections = [c.get("section") for c in window_chunks]
        pages = [c.get("page_start") for c in window_chunks]
        windows[label] = {
            "chunk_ids": [c["chunk_id"] for c in window_chunks],
            "chunks": window_chunks,
            "missing_before": missing_before,
            "missing_after": missing_after,
            "n_chunks": len(window_chunks),
            "chars": len(text_join),
            "approx_tokens": approx_tokens(len(text_join)),
            "section_crossings": len({s for s in sections}) - 1,
            "page_crossings": len({p for p in pages if p is not None}) - 1 if any(p is not None for p in pages) else 0,
            "boundary_reduced": (missing_before > 0 or missing_after > 0),
        }
    return windows


def build_window_case(conn: Connection, *, case_id: str, anchor_chunk_id: int, paper_id: int) -> WindowCase | None:
    anchor = conn.execute(select(chunks.c.attachment_id).where(chunks.c.id == anchor_chunk_id)).first()
    if anchor is None:
        return None
    attachment_id = int(anchor.attachment_id)
    ordered = _ordered_attachment_chunks(conn, attachment_id)
    index = next((i for i, c in enumerate(ordered) if c["chunk_id"] == anchor_chunk_id), None)
    if index is None:
        return None
    windows = windows_from_ordered(ordered, index)
    return WindowCase(
        case_id=case_id,
        anchor_chunk_id=anchor_chunk_id,
        attachment_id=attachment_id,
        paper_id=paper_id,
        central_index=index,
        windows=windows,
    )


def render_window(window: dict, central_id: int, *, radius: int) -> str:
    """Render one window's real text with the central chunk marked and explicit boundary notes."""
    lines: list[str] = []
    if window["missing_before"] > 0:
        lines.append("[ NO PREVIOUS CHUNK EXISTS — DOCUMENT START ]")
    for chunk in window["chunks"]:
        cid = chunk["chunk_id"]
        if cid == central_id:
            lines.append(f"[ CENTRAL CHUNK {cid} ]")
            lines.append(chunk["text"])
            lines.append(f"[ END CENTRAL CHUNK {cid} ]")
        else:
            lines.append(f"[ CHUNK {cid} ]")
            lines.append(chunk["text"])
    if window["missing_after"] > 0:
        lines.append("[ NO NEXT CHUNK EXISTS — DOCUMENT END ]")
    return "\n".join(lines)


def render_all_windows(case: WindowCase) -> dict:
    """label -> rendered text, for the prompt and the human review artifact."""
    return {
        label: render_window(case.windows[label], case.anchor_chunk_id, radius=WINDOW_RADII[label])
        for label in WINDOW_RADII
    }


_BASELINE_PROMPT_HEAD = (
    "You are deciding how much surrounding context is needed to understand ONE passage from a scholarly "
    "paper.\n\n"
    "Below are four windows (A, B, C, D) of REAL text around the SAME central passage. The central passage "
    "is marked [ CENTRAL CHUNK ... ] ... [ END CENTRAL CHUNK ... ]. Window A is the central passage alone; "
    "each larger window adds real neighboring text from the same document.\n\n"
    "Choose the SMALLEST window in which the scientific idea expressed by the CENTRAL CHUNK can be "
    "understood as a complete, interpretable thought. If even the largest window (D) is not enough, choose "
    "E.\n"
    "Do not judge relevance to any question. Do not decide whether it should be used as evidence. Judge "
    "only whether the central idea is intelligible as a complete thought.\n\n"
    'Return only JSON: {"window":"A"} where window is one of A, B, C, D, E.\n'
)


def window_prompt(rendered: dict) -> str:
    blocks = []
    for label in WINDOW_RADII:
        blocks.append(f"===== WINDOW {label} =====\n{rendered[label]}")
    return _BASELINE_PROMPT_HEAD + "\n" + "\n\n".join(blocks)


def select_window(base_config, case: WindowCase, *, mode: str, output_cap: int = _WINDOW_OUTPUT_CAP):
    """One tiny constrained judgment: return (choice or None, SchemaCall)."""
    rendered = render_all_windows(case)
    prompt = window_prompt(rendered)
    call = run_schema_call(base_config, prompt, output_cap=output_cap, json_schema=WINDOW_SCHEMA, mode=mode)
    choice = None
    if isinstance(call.parsed, dict):
        value = call.parsed.get("window")
        if isinstance(value, str) and value.strip().upper() in set(WINDOW_LABELS):
            choice = value.strip().upper()
    return choice, call, prompt
