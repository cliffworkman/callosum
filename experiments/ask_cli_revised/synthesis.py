"""Optional UNVALIDATED terminal model candidate over the sealed verified ledger.

The writer gets no retrieval or database handle. The prompt explicitly asks for maximal usefulness from the
verified findings while forbidding background completion from model priors. Prompt
instructions did not enforce provenance in the saved run. The CLI now uses the
constrained ledger renderer for its final output; these candidates are comparisons.
"""

from __future__ import annotations

import json

from app.backend.llm.providers import ProviderError, complete


def build_prompt(sealed_ledger: dict) -> str:
    lines = [
        "Write the most useful scholarly answer you can using ONLY the verified propositions below.",
        "Do not supply background knowledge, mechanisms, synonyms, evolutionary explanations, or other facts from",
        "your own knowledge. A plausible statement is still forbidden unless a verified proposition supports it.",
        "Use every verified proposition that materially helps answer the user's subquestions. Do not merely abstain",
        "when supported findings exist. Organize the answer around the subquestions and requested information.",
        "Preserve null, mixed, qualified, and uncertain findings rather than smoothing them into a stronger claim.",
        "Every factual sentence or bullet must end with the proposition ID(s) that support it, for example [p3].",
        "State remaining gaps after the supported findings. Do not invent citations or fill unsupported fields.",
        "",
        "ORIGINAL REQUEST (user intent, not scientific evidence):",
        json.dumps(sealed_ledger.get("request_contract", {}).get("original_question"), ensure_ascii=False),
        "",
        "SUBQUESTIONS AND REQUESTED INFORMATION:",
        json.dumps(sealed_ledger["subquestions"], ensure_ascii=False, indent=2),
        "",
        "VERIFIED PROPOSITIONS - THE ONLY SCIENTIFIC FACTS YOU MAY USE:",
        json.dumps(sealed_ledger["verified_propositions"], ensure_ascii=False, indent=2),
        "",
        "COVERAGE / GAPS:",
        json.dumps(sealed_ledger["coverage"], ensure_ascii=False, indent=2),
        "",
        "Write the final answer in Markdown.",
    ]
    return "\n".join(lines)


def terminal_synthesis(config, sealed_ledger: dict) -> tuple[str, bool]:
    """Return (markdown, ok). A provider failure is recorded rather than aborting the experimental run."""
    prompt = build_prompt(sealed_ledger)
    try:
        result = complete(config, prompt)
    except ProviderError as exc:
        return f"[terminal synthesis unavailable: {exc}]", False
    note = (
        "\n\n> _(note: provider stopped at its output-token ceiling; this answer may be incomplete.)_"
        if getattr(result, "truncated", False)
        else ""
    )
    return (result.text or "") + note, True
