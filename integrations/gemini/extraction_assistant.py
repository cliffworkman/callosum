"""Assisted meta-analysis extraction — the egress-gated LLM that PROPOSES cell values (workbench SP2b, inc 259).

A drafting aid, never a coder: it returns only {value, quote, page} text per field. The deterministic local locator
(app.backend.pdf_processing.quote_matching.locate_quote, applied in app.backend.workbench_assist) decides each anchor,
and a human accepts every candidate before it enters ma_cells. Sibling to research_summary/overview — rides
app.backend.llm.providers.complete(config, prompt); egress rides the existing consent gate (invariant #3).

The model response is UNTRUSTED (a user can point the roster at an arbitrary endpoint) → parse_proposals is defensive:
it tolerates markdown fences + surrounding junk, ignores unknown keys and malformed entries, caps value/quote lengths,
and yields ZERO proposals on any parse failure — never a crash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from app.backend.llm.egress import DataEgressDisabledError
from app.backend.llm.usage import log_usage
from integrations.gemini.generator import GeminiConfig

MAX_VALUE_CHARS = 500  # a proposed value (matches the SP2a-2 capture + CellPut.value cap)
MAX_QUOTE_CHARS = 4000  # a proposed quote (matches CellPut.quote)


class ExtractionAssistant(Protocol):
    def propose(self, *, text: str, fields: list[dict]) -> list[dict]: ...


@dataclass(frozen=True)
class GeminiExtractionAssistant:
    config: GeminiConfig
    name: str = "gemini-extraction-assistant"

    def propose(self, *, text: str, fields: list[dict]) -> list[dict]:
        from app.backend.llm.providers import complete, requires_egress

        if requires_egress(self.config) and not self.config.data_egress_enabled:
            raise DataEgressDisabledError("Assisted extraction requires explicit data-egress consent.")
        result = complete(self.config, _prompt(text=text, fields=fields))
        log_usage("extraction-assist", self.config.model, result)
        return parse_proposals(str(result.text or ""), allowed_keys={f["key"] for f in fields})


def _prompt(*, text: str, fields: list[dict]) -> str:
    spec = [{"key": f["key"], "label": f["label"], "type": f["type"], "options": f.get("options")} for f in fields]
    return (
        "You are a data-extraction assistant for a meta-analysis. From the paper text below, propose a value ONLY for "
        "these fields. For each field you can find, copy a VERBATIM quote from the text that reports it and give the "
        "page number shown in that quote's [p.N] tag. If a field is not reported, OMIT it — never guess, compute, or "
        "infer. Return STRICT JSON only: an object mapping each field_key to "
        '{"value": <string>, "quote": <verbatim string>, "page": <integer>}. '
        f"Fields: {json.dumps(spec, ensure_ascii=True)}\n\nPaper text:\n{text}"
    )


def parse_proposals(raw: str, *, allowed_keys: set[str]) -> list[dict]:
    """Defensive parse of the UNTRUSTED model response → [{field_key, value, quote, page}]. Unknown keys + malformed
    entries are ignored; value/quote are length-capped; any parse failure yields []."""
    obj = _loads_lenient(raw)
    if not isinstance(obj, dict):
        return []
    out: list[dict] = []
    for key, entry in obj.items():
        if key not in allowed_keys or not isinstance(entry, dict):
            continue
        value = entry.get("value")
        quote = entry.get("quote")
        if value is None and quote is None:
            continue
        out.append(
            {
                "field_key": key,
                "value": None if value is None else str(value)[:MAX_VALUE_CHARS],
                "quote": None if quote is None else str(quote)[:MAX_QUOTE_CHARS],
                "page": _int_or_none(entry.get("page")),
            }
        )
    return out


def _loads_lenient(raw: str):
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # tolerate surrounding prose: parse the outermost {...} span, if any
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return None


def _int_or_none(x):
    try:
        return int(float(str(x).strip()))
    except (TypeError, ValueError):
        return None
