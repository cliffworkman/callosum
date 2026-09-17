"""The two tiny linguistic primitives under test.

P1 — proposition screen: "does THIS EXACT SPAN contain a scientific proposition?" → YES/NO.
P2 — source-local claim formation: "state ONE atomic claim the EXACT SPAN supports" → string|null.

Neither prompt EVER contains the user question, subquestion, or obligation text (asserted by selfcheck).
One Qwen call = one linguistic judgment/transformation. Qwen emits no ids, no provenance, no quote.
"""

from __future__ import annotations

from experiments.ask_cli_revised.calibration.structured_output import SchemaCall, run_schema_call

# ---- output caps (per-request only; the global 4096 descriptor cap is never mutated) ----------------
P1_OUTPUT_CAP = 16
P2_OUTPUT_CAP = 256

# ---- schemas ----------------------------------------------------------------------------------------
P1_SCHEMA = {
    "type": "object",
    "required": ["answer"],
    "additionalProperties": False,
    "properties": {"answer": {"type": "string", "enum": ["YES", "NO"]}},
}
# P2 primary: a claim string, or explicit null. Some strict validators reject a ["string","null"] union;
# the fallback expresses the same meaning with a boolean gate. The run picks ONE at smoke time and freezes it.
P2_SCHEMA_NULLABLE = {
    "type": "object",
    "required": ["claim"],
    "additionalProperties": False,
    "properties": {"claim": {"type": ["string", "null"]}},
}
P2_SCHEMA_GATED = {
    "type": "object",
    "required": ["has_claim", "claim"],
    "additionalProperties": False,
    "properties": {"has_claim": {"type": "boolean"}, "claim": {"type": "string"}},
}
P2_SCHEMA_NULLABLE_NAME = "claim_nullable"
P2_SCHEMA_GATED_NAME = "claim_gated"

# ---- prompt versions (V1 frozen; a single bounded V2 revision per primitive is allowed on DEV only) --
P1_PROMPT_VERSION = "p1-proposition-v1"
P2_PROMPT_VERSION = "p2-claim-v1"

_NO_CONTEXT = "(no surrounding context available)"


def build_p1_prompt(*, span_text: str, context_text: str, context_available: bool) -> str:
    context = context_text if (context_available and context_text.strip()) else _NO_CONTEXT
    return (
        "You are inspecting one exact excerpt from a scholarly document.\n\n"
        "Decide whether THIS EXACT EXCERPT contains at least one scientific proposition — a statement\n"
        "that could be written as a factual scientific claim. Scientific propositions include: an\n"
        "empirical result, an observed association, an experimental effect, a null result, a stated\n"
        "uncertainty, a sample or property, a measurement/result relationship, a biological/neural/\n"
        "behavioral/cognitive phenomenon, a methodological scientific fact, or a scientific\n"
        "interpretation explicitly stated by the source.\n\n"
        "The following, by themselves, are NOT scientific propositions: a section heading, a paper\n"
        "title, author or address metadata, a reference-list entry, an isolated keyword list, an\n"
        "abbreviation list, a page or footer artifact, or an isolated label with no propositional\n"
        "content.\n\n"
        "Judge the EXACT EXCERPT only. Context may resolve linguistic meaning or references, but\n"
        "scientific content appearing only in CONTEXT does not make the excerpt proposition-bearing. A\n"
        "YES must be defensible from meaning asserted by the exact excerpt itself after reference\n"
        "resolution.\n\n"
        "Prefer YES when the excerpt plausibly contains a scientific proposition even if the wording is\n"
        "awkward or incomplete. Do NOT answer NO merely because the proposition seems minor, surprising,\n"
        "or would need later verification.\n\n"
        'Return only JSON: {"answer":"YES"} or {"answer":"NO"}.\n\n'
        f"CONTEXT (for interpretation only):\n{context}\n\n"
        f"EXACT EXCERPT:\n{span_text}"
    )


def build_p2_prompt(*, span_text: str, context_text: str, context_available: bool) -> str:
    context = context_text if (context_available and context_text.strip()) else _NO_CONTEXT
    return (
        "You are given ONE exact excerpt from a scholarly document plus surrounding context.\n\n"
        "State ONE atomic scientific claim that is directly supported by the EXACT EXCERPT.\n"
        "- State what the source says; preserve direction, negation, uncertainty/hedging, and\n"
        "  population/condition/task qualifiers.\n"
        '- Do not turn a correlation into a cause; do not strengthen "may"/"suggests"/"associated\n'
        '  with" into certainty.\n'
        "- Do not introduce any construct that is absent from the excerpt.\n"
        "- Use the context ONLY to resolve local linguistic meaning (a pronoun, a sentence fragment, an\n"
        "  abbreviation, a truncated boundary). Do NOT import a neighboring finding that appears only in\n"
        "  the context.\n"
        "- Keep the claim atomic (one claim, not several combined).\n"
        "- Do not quote the source, attach identifiers, explain, or say why the claim matters.\n\n"
        "If the excerpt does not support a scientific claim without adding unsupported meaning, return\n"
        "null — returning null is safer than inventing a claim.\n\n"
        'Return only JSON: {"claim":"<one atomic claim>"} or {"claim":null}.\n\n'
        f"CONTEXT (for interpretation only):\n{context}\n\n"
        f"EXACT EXCERPT:\n{span_text}"
    )


def parse_answer(call: SchemaCall) -> str | None:
    """YES/NO from a P1 call, or None if the model did not emit a valid enum answer."""
    parsed = call.parsed
    if isinstance(parsed, dict):
        answer = parsed.get("answer")
        if answer in ("YES", "NO"):
            return answer
    return None


def parse_claim(call: SchemaCall, schema_name: str) -> str | None:
    """The claim string from a P2 call, or None (explicit null / unparseable / gated-off)."""
    parsed = call.parsed
    if not isinstance(parsed, dict):
        return None
    if schema_name == P2_SCHEMA_GATED_NAME:
        if not parsed.get("has_claim"):
            return None
        claim = parsed.get("claim")
        return claim.strip() if isinstance(claim, str) and claim.strip() else None
    claim = parsed.get("claim")
    return claim.strip() if isinstance(claim, str) and claim.strip() else None


def run_proposition_screen(
    base_config, *, span_text: str, context_text: str, context_available: bool, mode: str, prompt: str | None = None
) -> tuple[SchemaCall, str | None]:
    prompt = (
        prompt
        if prompt is not None
        else build_p1_prompt(span_text=span_text, context_text=context_text, context_available=context_available)
    )
    call = run_schema_call(base_config, prompt, output_cap=P1_OUTPUT_CAP, json_schema=P1_SCHEMA, mode=mode)
    return call, parse_answer(call)


def run_claim_form(
    base_config,
    *,
    span_text: str,
    context_text: str,
    context_available: bool,
    mode: str,
    schema_name: str,
    prompt: str | None = None,
) -> tuple[SchemaCall, str | None]:
    prompt = (
        prompt
        if prompt is not None
        else build_p2_prompt(span_text=span_text, context_text=context_text, context_available=context_available)
    )
    schema = P2_SCHEMA_GATED if schema_name == P2_SCHEMA_GATED_NAME else P2_SCHEMA_NULLABLE
    call = run_schema_call(base_config, prompt, output_cap=P2_OUTPUT_CAP, json_schema=schema, mode=mode)
    return call, parse_claim(call, schema_name)


# ---- P2 schema smoke: pick and freeze one claim schema before dataset inference (steering #5) --------
_P2_SMOKE_STRING = 'Return JSON with the claim field set to the exact sentence: "Water boils at 100 C at sea level."'
_P2_SMOKE_NULL = "Return JSON representing that there is NO claim to state (an explicit null / absent claim)."


def choose_claim_schema(base_config, mode: str) -> tuple[str, list[dict]]:
    """Probe both claim schemas on neutral prompts; return the name of the first that ENFORCES a real
    string AND a real null (gated: has_claim false), with all probe results. Prefer the nullable form."""
    results: list[dict] = []
    for name, schema in ((P2_SCHEMA_NULLABLE_NAME, P2_SCHEMA_NULLABLE), (P2_SCHEMA_GATED_NAME, P2_SCHEMA_GATED)):
        string_call = run_schema_call(base_config, _P2_SMOKE_STRING, output_cap=64, json_schema=schema, mode=mode)
        null_call = run_schema_call(base_config, _P2_SMOKE_NULL, output_cap=64, json_schema=schema, mode=mode)
        string_claim = parse_claim(string_call, name)
        null_claim = parse_claim(null_call, name)
        enforced = (
            string_call.schema_ok and null_call.schema_ok and isinstance(string_claim, str) and null_claim is None
        )
        results.append(
            {
                "schema_name": name,
                "enforced": enforced,
                "string_probe": {
                    "parsed": string_call.parsed,
                    "schema_ok": string_call.schema_ok,
                    "claim": string_claim,
                },
                "null_probe": {"parsed": null_call.parsed, "schema_ok": null_call.schema_ok, "claim": null_claim},
            }
        )
        if enforced:
            return name, results
    return "", results
