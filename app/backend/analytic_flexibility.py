"""Analytic-flexibility surfacing orchestration for Library papers (backlog #37).

LLM-assisted, egress-gated -- deliberately NOT under app/backend/methods/, which CLAUDE.md documents as
deterministic/local/no-LLM only. Wires together three already-built pieces: ``paper_methods_text``
(citations/section_scope.py, Task 3 -- local retrieval of a paper's methods-section text, GROBID-preferred
with a heuristic fallback), ``AnalyticFlexibilityAssistant`` (integrations/gemini/analytic_flexibility_assistant.py,
Task 2 -- the egress-gated LLM that PROPOSES ``{category, quote}`` candidates, never a location or confidence),
and ``anchor_quote`` (pdf_processing/quote_matching.py, Task 1 -- the deterministic local locator that decides
exact/region/unanchored). The model never asserts a location; the locator does, honoring the coordinate-honesty
contract (invariant #2). Candidates persist into the shared ``paper_findings`` store as
``kind="candidate", tier="speculative"`` (AI funnel, human filter -- PRINCIPLES.md): a candidate is not a
finding until a human reviews it against its independently-anchored source text.
"""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.citations.section_scope import paper_methods_text
from app.backend.pdf_processing.quote_matching import anchor_quote
from app.backend.persistence.findings_repo import upsert_findings
from app.backend.workbench_assist import primary_pdf_path
from integrations.gemini.analytic_flexibility_assistant import AnalyticFlexibilityAssistant
from integrations.gemini.generator import GeminiConfig

SOURCE = "analytic-flexibility"

# Human-readable labels for ANALYTIC_FLEXIBILITY_CATEGORIES (integrations/gemini/analytic_flexibility_assistant.py),
# used only to compose the finding's display "desc" -- the raw category key is always preserved in the payload too.
_CATEGORY_LABELS = {
    "exclusion-criteria": "exclusion criteria",
    "covariate-choice": "covariate/control choice",
    "test-selection": "statistical test/model selection",
    "outcome-choice": "outcome/measure choice",
    "other-branch-point": "other reported branch point",
}


def propose_analytic_flexibility(conn: Connection, paper_id: int, config: GeminiConfig) -> dict:
    """Draft analytic-flexibility candidates for ``paper_id``'s methods section, anchor each quote locally, and
    persist them into ``paper_findings``. Honestly reports ``methods_text_found=False`` -- and never calls the
    LLM at all -- when this paper has no methods-section text to draft from (no egress on a paper the assistant
    couldn't help with anyway)."""
    text = paper_methods_text(conn, paper_id)
    if text is None:
        return {"candidates_found": 0, "methods_text_found": False}

    proposals = AnalyticFlexibilityAssistant(config).propose(text=text)
    pdf_path = primary_pdf_path(conn, paper_id)
    findings = []
    for proposal in proposals:
        quote = proposal["quote"]
        category = proposal["category"]
        anchor = (
            anchor_quote(pdf_path, quote)
            if pdf_path is not None
            else {"anchor_state": "unanchored", "page": None, "bbox_json": None, "reason": "no_pdf"}
        )
        findings.append(
            {
                "kind": "candidate",
                "tier": "speculative",
                "payload": {
                    "desc": f"Possible analytic-flexibility decision point: {_CATEGORY_LABELS.get(category, category)}",
                    "category": category,
                    "quote": quote,
                    "anchor_state": anchor["anchor_state"],
                    "page": anchor["page"],
                    "bbox_json": anchor["bbox_json"],
                    "reason": anchor["reason"],
                },
            }
        )
    upsert_findings(conn, paper_id, SOURCE, findings)
    return {"candidates_found": len(findings), "methods_text_found": True}
