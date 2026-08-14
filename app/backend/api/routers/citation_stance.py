"""Pairwise stance classification (inc 461, backlog #33/#34 P2 #20): given an explicit claim sentence and an
explicit passage, what's the local NLI stance (support/contrast/mention) of the passage toward the claim?

Split out as its own sibling router because `citations.py` (home of `POST /citations/suggest`, the ONLY other
place this codebase calls `classify_stance`) was already at the 600-line cap (rule #1) -- the inc-226/262 sibling-
router precedent (`paper_enrich.py`, `methods_retraction.py`). `POST /citations/suggest` itself later moved out to
its own sibling `citation_suggest.py` (inc 479), which is where `StanceResponse`/`_suggest_stance_scorer` are
imported from below now. Every existing stance call site in this codebase
bundles classification with a retrieval/search step first; this is the one place a caller supplies BOTH texts
directly (built for the LibreOffice "Insert evidence…" command checking a typed claim against an already-picked
saved annotation, but usable by any future caller with the same shape). Reuses the exact cached `NLIStanceScorer`
singleton `/citations/suggest` already warms via `_suggest_stance_scorer` -- no new model, no new egress class;
same local-only posture already audited in `.claude/security-audits/2026-06-27_citation-suggest.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.backend.api.routers.citation_suggest import StanceResponse, _suggest_stance_scorer
from app.backend.citations.suggest import MAX_TEXT_LEN

router = APIRouter(tags=["citations"])


class ClassifyStanceRequest(BaseModel):
    sentence: str = Field(min_length=1, max_length=MAX_TEXT_LEN)
    passage: str = Field(min_length=1, max_length=MAX_TEXT_LEN)


@router.post("/citations/classify-stance", response_model=StanceResponse | None)
def classify_stance_endpoint(payload: ClassifyStanceRequest, request: Request) -> StanceResponse | None:
    scorer = _suggest_stance_scorer(request)
    stance = scorer.classify_stance(sentence=payload.sentence, passage=payload.passage)
    if (
        stance is None
    ):  # model unavailable / inference failed -- never a guessed verdict, matches classify_stance's own contract
        return None
    return StanceResponse(label=stance.label, confidence=stance.confidence, probs=stance.probs)
