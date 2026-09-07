"""Stage 12: terminal synthesis fork over the SEALED verified ledger.

Both 12A (Qwen) and 12B (Gemini) receive exactly the same ledger and instruction. The synthesis step is
given the ledger only — no engine/DB handle — so it structurally cannot rerun retrieval, add propositions,
or touch coverage/gaps. It organizes what is verified and states the gaps; it never fills unsupported fields.
"""

from __future__ import annotations

import json

from app.backend.llm.providers import ProviderError, complete


def build_prompt(sealed_ledger: dict) -> str:
    lines = [
        "You are writing the final answer to a scholarly question using ONLY the verified evidence below.",
        "Organize the answer around the sub-questions. Cite the paper_id for each claim. State clearly which",
        "requested fields remain unanswered (see gaps). Do NOT add any fact that is not in the verified",
        "propositions. Do NOT fill unsupported fields. Do NOT invent citations.",
        "",
        "SUB-QUESTIONS:",
        json.dumps(sealed_ledger["subquestions"], ensure_ascii=False, indent=2),
        "",
        "VERIFIED PROPOSITIONS (the only evidence you may use):",
        json.dumps(sealed_ledger["verified_propositions"], ensure_ascii=False, indent=2),
        "",
        "COVERAGE / GAPS (state these honestly):",
        json.dumps(sealed_ledger["coverage"], ensure_ascii=False, indent=2),
        "",
        "Write the final answer in Markdown.",
    ]
    return "\n".join(lines)


def terminal_synthesis(config, sealed_ledger: dict) -> tuple[str, bool]:
    """Return (markdown, ok). Never raises — a provider failure is recorded, not fatal to the run."""
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
