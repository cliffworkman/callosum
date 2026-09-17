"""Diagnostic replay of the UNCHANGED local verifier over frozen spans.

The verifier, its config, and its thresholds are used exactly as shipped. A throwaway SQLite database
(the full real schema via ``alembic upgrade head``) is seeded with ONE real ``chunks`` row per distinct
containing chunk (reconstructed from the frozen packet text) plus its ``papers``/``attachments`` parents,
so ``verify_many`` scopes retrieval to that single chunk — provably NOT a library search — while running
production code end to end. A missing PDF only degrades ``coordinate_precision``; ``quote`` stays 1.0.

Fail-closed rules honored here: the containment precheck refuses to feed a span whose exact text is not a
canonical substring of its chunk; the RTPJ wiring validation must reproduce the frozen scores within a
PREDECLARED tolerance before any new-claim replay, and STOPs otherwise; nothing in the verifier is
altered to make a check pass.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, insert

from alembic import command
from alembic.config import Config
from app.backend.pdf_processing.extraction import canonical_text_contains
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.summarization.generators import CandidateCitation, SourceChunk

ROOT = Path(__file__).resolve().parents[4]

# Sentinels for the fabricated provenance fields the frozen packets do not carry (page/attachment/version).
# None of these affect retrieval (chunk-text embedding), quote (canonical containment), or support/
# contradiction (NLI over span+claim) — they touch only page/coordinate fields we do not score.
_SENTINEL = "frozen-0.6b"
_CHUNK_VERSION = "frozen-0.6b"

# Predeclared RTPJ wiring-validation tolerance (steering #5): quote must be exactly 1.0; the three model
# scores each within this absolute band of the frozen 10_verification.jsonl values. Wide enough for GPU/
# float/batch nondeterminism, far tighter than the score shift a wrong reconstruction would cause (≫0.01).
WIRING_ABS_TOL = 0.01


def build_replay_schema(db_path: str | Path) -> None:
    """Create the full real schema on a fresh throwaway DB (the proven test path), cwd-independently."""
    import logging

    url = f"sqlite:///{Path(db_path).resolve().as_posix()}"
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    prev = logging.getLogger("alembic").level
    logging.getLogger("alembic").setLevel(logging.WARNING)  # migrations print ~80 lines; keep the run readable
    try:
        command.upgrade(config, "head")
    finally:
        logging.getLogger("alembic").setLevel(prev)


def seed_chunks(engine: Engine, chunk_records: list[dict]) -> dict[int, dict]:
    """Insert one papers/attachments row per distinct paper and one chunks row per distinct chunk.

    ``chunk_records`` items are ``{chunk_id, paper_id, text}``. Returns ``{chunk_id: {chunk_id, paper_id,
    attachment_id, text}}`` so the caller can build ``SourceChunk``s with matching ids.
    """
    distinct: dict[int, dict] = {}
    for rec in chunk_records:
        distinct.setdefault(
            int(rec["chunk_id"]),
            {"chunk_id": int(rec["chunk_id"]), "paper_id": int(rec["paper_id"]), "text": rec["text"]},
        )

    paper_ids = sorted({rec["paper_id"] for rec in distinct.values()})
    attachment_by_paper: dict[int, int] = {pid: idx + 1 for idx, pid in enumerate(paper_ids)}

    with engine.begin() as conn:
        for pid in paper_ids:
            conn.execute(insert(papers).values(id=pid, title=f"frozen paper {pid}", csl_json={}))
        for pid in paper_ids:
            conn.execute(
                insert(attachments).values(
                    id=attachment_by_paper[pid],
                    paper_id=pid,
                    storage_mode="linked",
                    availability="missing",
                    content_type="application/pdf",
                    original_path=None,
                    resolved_path=None,
                )
            )
        for cid, rec in sorted(distinct.items()):
            conn.execute(
                insert(chunks).values(
                    id=cid,
                    paper_id=rec["paper_id"],
                    attachment_id=attachment_by_paper[rec["paper_id"]],
                    text=rec["text"],
                    page_start=1,
                    page_end=1,
                    bbox_coordinate_system="pdf-points-top-left",
                    extraction_tool=_SENTINEL,
                    extraction_version=_SENTINEL,
                    chunking_strategy=_SENTINEL,
                    chunk_version=_CHUNK_VERSION,
                    source_attachment_checksum=_SENTINEL,
                )
            )

    return {
        cid: {
            "chunk_id": cid,
            "paper_id": rec["paper_id"],
            "attachment_id": attachment_by_paper[rec["paper_id"]],
            "text": rec["text"],
        }
        for cid, rec in distinct.items()
    }


def containment_ok(span_text: str, chunk_text: str) -> bool:
    """The fail-closed provenance precheck: the exact span must be a canonical substring of its chunk."""
    return canonical_text_contains(needle=span_text, haystack=chunk_text)


def _source_chunk(seed: dict) -> SourceChunk:
    return SourceChunk(
        chunk_id=int(seed["chunk_id"]),
        paper_id=int(seed["paper_id"]),
        attachment_id=int(seed["attachment_id"]),
        text=str(seed["text"]),
        page_start=1,
        page_end=1,
        chunk_version=_CHUNK_VERSION,
    )


def replay_one(verifier, conn, *, claim: str, span_text: str, seed: dict) -> dict:
    """Run the unchanged verifier for one (claim, exact span, containing chunk) triple → the four scores."""
    source = _source_chunk(seed)
    result = verifier.verify_many(
        conn,
        items=[(claim, CandidateCitation(chunk_id=source.chunk_id, quote=span_text))],
        source_chunks=[source],
    )[0]
    return {
        "retrieval_confidence": result.retrieval_confidence,
        "quote_confidence": result.quote_confidence,
        "support_confidence": result.support_confidence,
        "contradiction_confidence": result.contradiction_confidence,
        "status": result.status,
        "verified": result.verified,
        "coordinate_precision": result.coordinate_precision,
    }


def wiring_validation(verifier, conn, *, old_claim: str, old_quote: str, seed: dict, frozen: dict) -> dict:
    """Replay the OLD RTPJ claim/quote/chunk; compare to the frozen scores within the predeclared band."""
    scores = replay_one(verifier, conn, claim=old_claim, span_text=old_quote, seed=seed)
    checks = {
        "quote": (scores["quote_confidence"] == 1.0),
        "retrieval": abs(scores["retrieval_confidence"] - float(frozen["retrieval"])) <= WIRING_ABS_TOL,
        "support": abs(scores["support_confidence"] - float(frozen["support"])) <= WIRING_ABS_TOL,
        "contradiction": abs((scores["contradiction_confidence"] or 0.0) - float(frozen["contradiction"]))
        <= WIRING_ABS_TOL,
    }
    return {
        "passed": all(checks.values()),
        "abs_tol": WIRING_ABS_TOL,
        "checks": checks,
        "reproduced": scores,
        "frozen": {k: frozen.get(k) for k in ("retrieval", "quote", "support", "contradiction", "status")},
    }
