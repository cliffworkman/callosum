"""Deterministic rendering of the overview artifact: the researcher-facing answer, and the separate detailed inspection.

Both are pure functions of ``(sealed ledger, overview record)``, so the final audit can re-render and compare them exactly.
Nothing here judges, scores or certifies. The researcher-facing answer is short (Overview, Supporting findings, Unresolved
parts); the detailed inspection is the existing ledger rendering, unchanged, followed by a construction record that keeps
every claim disposition, exclusion, withheld statement and execution receipt. No provenance is dropped, only relocated.
"""

from __future__ import annotations

from collections import Counter

from experiments.ask_cli_revised.ledger_renderer import _literal, render_answer
from experiments.ask_cli_revised.overview import SCREENING_NOTE

ANSWER_FILE = "14_final_answer.md"
DETAIL_FILE = "14b_detailed_inspection.md"
RECORD_FILE = "14a_overview.json"

_SCOPE = (
    "This overview restates passages retrieved in this run. It makes no statement about what the library or the "
    "literature holds."
)
_STATE_MESSAGE = {
    "no_eligible_evidence": "No overview was produced: no retrieved passage was eligible for synthesis in this run{why}. "
    "This describes this run's retrieved evidence, not the library or the literature.",
    "model_no_answer": "No overview was produced: the overview model returned no usable answer (mechanical: {why}). "
    "This is not a scientific result.",
    "model_returned_empty": "The overview model returned no statements from the eligible passages. The passages are listed below.",
    "no_grounded_sentences": "No overview statement passed screening ({n} proposed statement(s) were withheld; see the "
    "detailed inspection). The passages are listed below.",
}
_FLAG_LABELS = {
    "hedged": "hedged wording (for example might, may or suggest)",
    "negated": "reports a null or negated result",
    "correlational": "reports an association",
    "fragment": "the passage is cut off mid-sentence",
    "starts_mid_sentence": "the passage begins mid-sentence",
    "study_description": "describes what a study set out to do, not a finding",
    "absence_statement": "states that something was not examined",
}
_ATTACH_NOTE = (
    "Attachment of a passage to a request part is the coverage model's topical judgment. It does not establish that the "
    "passage answers the part, and this run did not assess whether any part is fully answered."
)


def _cites(numbers) -> str:
    return "".join(f"[{n}]" for n in sorted(set(numbers)))


def _unit_by_id(overview: dict) -> dict:
    return {u["unit_id"]: u for u in overview["units"]}


def _cite_numbers(overview: dict) -> dict[str, int]:
    """Reader-facing citation numbers: contiguous from 1, in the order the overview first cites each passage.

    (Internal ids stay stable in the record; a reader must not see [1] and [3] because a withheld statement owned [2], nor
    meet the citations out of order.) With no overview every passage is listed and keeps its own contiguous number."""
    order: list[str] = []
    for item in overview["items"]:
        order.extend(u for u in item["unit_ids"] if u not in order)
    if not order:
        return {u["unit_id"]: u["number"] for u in overview["units"]}
    return {u: n for n, u in enumerate(order, start=1)}


def _flag_text(unit: dict) -> str:
    flags = unit["flags"]
    labels = [label for key, label in _FLAG_LABELS.items() if flags.get(key)]
    if flags.get("causal_cues"):
        labels.append(f"causal wording ({', '.join(flags['causal_cues'])})")
    return "; ".join(labels) if labels else "none detected"


def _locator(unit: dict) -> str:
    first, rest = unit["locators"][0], len(unit["locators"]) - 1
    page = (unit.get("verification") or {}).get("page_start")
    text = f"Paper {unit['paper_id']}, chunk {first['chunk_id']}, {first['span_id']}" + (
        f", page {page}" if page else ""
    )
    return text + (f" (also found in {rest} other chunk(s))" if rest else "")


def _exclusion_summary(units: list[dict]) -> str:
    counts = Counter(r for u in units if not u["eligibility"]["eligible"] for r in u["eligibility"]["reasons"])
    return ", ".join(f"{n} {reason}" for reason, n in sorted(counts.items()))


def _finding_block(unit: dict, number: int) -> list[str]:
    lines = [f"**[{number}]** {_locator(unit)}; source-verified.", "", "> " + _literal(unit["passage"]), ""]
    lines.append(f"Qualifications: {_flag_text(unit)}.")
    lines.append(f"Restated by ledger claim(s) {', '.join(unit['proposition_ids'])}.")
    return [*lines, ""]


def _unresolved(overview: dict) -> list[str]:
    parts = overview["parts"]
    by_status: dict[str, list[dict]] = {}
    for part in parts:
        by_status.setdefault(part["status"], []).append(part)
    lines = ["## Unresolved parts", ""]

    def group(title: str, statuses: tuple[str, ...], render) -> None:
        rows = [p for s in statuses for p in by_status.get(s, [])]
        if rows:
            lines.extend([f"**{title}**", "", *[render(p) for p in rows], ""])

    group(
        "No responsive evidence was found for these parts in this run",
        ("no_responsive_evidence", "not_assessed"),
        lambda p: f"- {_literal(p['note'])}",
    )

    def topical(p: dict) -> str:
        why = sorted({r for rs in p["attached_not_used"].values() for r in rs})
        return f"- {_literal(p['note'])}" + (f" (attached passage(s) were not used: {', '.join(why)})" if why else "")

    group("Judged topically responsive only; no overview statement bears on these parts", ("topical_only",), topical)
    stmt = {i: n for n, i in enumerate(overview["displayed"], start=1)}

    def stated(p: dict) -> str:
        return f"- {_literal(p['note'])} (statement {', '.join(str(stmt[i]) for i in p['statement_indices'])})"

    group("Only hedged statements bear on these parts", ("hedged_only",), stated)
    group(
        "Statements the overview makes bear on these parts (whole-part answers were not assessed)",
        ("passage_stated",),
        stated,
    )
    return [*lines, _ATTACH_NOTE, "", "**Completeness remains unresolved** for the request as a whole.", ""]


def _state_message(overview: dict) -> str:
    state, code = overview["state"], overview["reason_code"]
    if state == "no_eligible_evidence":
        why = _exclusion_summary(overview["units"]) if overview["units"] else (code or "")
        return _STATE_MESSAGE[state].format(why=f" ({why})" if why else "")
    if state == "model_no_answer":
        return _STATE_MESSAGE[state].format(why=code or "unknown")
    return _STATE_MESSAGE[state].format(n=len(overview["proposals"]))


def researcher_answer(
    sealed: dict, overview: dict, *, detail_file: str = DETAIL_FILE, record_file: str = RECORD_FILE
) -> tuple[str, dict]:
    """The primary artifact: Overview, concise Supporting findings, Unresolved parts. Everything else is in the inspection.

    ``detail_file``/``record_file`` name the footer's own "Full inspection" pointer -- purely
    referential, no evidentiary or rendering-semantic effect. Every existing (flat) caller that
    omits them gets today's exact `DETAIL_FILE`/`RECORD_FILE` text, unchanged; Stage B's per-child
    loop (e2e.py) passes the real per-child filenames so the footer names the file that actually
    exists on disk for that child, not the generic flat-run name."""
    units = _unit_by_id(overview)
    items, state = overview["items"], overview["state"]
    nums = _cite_numbers(overview)
    lines = ["# Overview of the retrieved evidence", ""]
    if overview["partial"]:
        withheld = len(overview["proposals"]) - len(overview["displayed"])
        lines += [
            f"> **Partial overview.** {withheld} proposed statement(s) were withheld by screening and are listed in the "
            "detailed inspection. This overview may omit findings the passages support.",
            "",
        ]
    if state == "ok" and overview["single_passage"]:
        lines += [
            "> This overview rests on one retrieved passage. See Unresolved parts for what it does not address.",
            "",
        ]
    lines += ["## Overview", ""]
    if state == "ok":
        for n, item in enumerate(items, start=1):
            lines.append(f"{n}. {_literal(item['text'])} {_cites(nums[u] for u in item['unit_ids'])}")
        lines += [
            "",
            f"_{_SCOPE} {SCREENING_NOTE} Every statement cites the exact passage it restates, shown below._",
            "",
        ]
    else:
        lines += [_state_message(overview), "", f"_{_SCOPE}_", ""]

    cited = sorted({u for item in items for u in item["unit_ids"]}, key=lambda u: nums[u])
    lines += ["## Supporting findings", ""]
    shown = [units[u] for u in cited] if cited else list(units.values())
    if shown:
        for unit in shown:
            lines += _finding_block(unit, nums[unit["unit_id"]])
            if not cited and not unit["eligibility"]["eligible"]:
                lines += [f"Not used in the overview: {', '.join(unit['eligibility']['reasons'])}.", ""]
    else:
        lines += ["No source-verified passages were retrieved.", ""]
    if shown:
        lines += [
            "Several ledger claims restating one passage are not independent support; each passage above is authoritative "
            "and a claim can say more or less than its passage.",
            "",
        ]
    unused = [u for u in units.values() if u["unit_id"] not in cited]
    if cited and unused:
        lines += [
            f"Not used in the overview: {len(unused)} retrieved passage(s) ({_exclusion_summary(unused) or 'eligible but not cited'}). "
            "See the detailed inspection.",
            "",
        ]
    lines += _unresolved(overview)
    lines += [
        "---",
        f"Full inspection: `{detail_file}` (every claim, exclusion, withheld statement, contract and receipt) and `{record_file}`.",
        "",
    ]
    manifest = {
        "mode": "researcher-answer-v1",
        "state": state,
        "partial": overview["partial"],
        "single_passage": overview["single_passage"],
        "statements": [
            {
                "text": i["text"],
                "citation_numbers": sorted(nums[u] for u in i["unit_ids"]),
                "unit_ids": i["unit_ids"],
                "proposition_ids": i["proposition_ids"],
            }
            for i in items
        ],
        "passages_shown": [nums[u["unit_id"]] for u in shown],
        "overview_hash": overview["overview_hash"],
        "sealed_ledger_hash": overview["sealed_ledger_hash"],
    }
    return "\n".join(lines).rstrip() + "\n", manifest


# ---- the detailed inspection ----------------------------------------------------------------------------------------------
def claim_dispositions(overview: dict) -> list[dict]:
    units = _unit_by_id(overview)
    cited = {u for i in overview["displayed"] for u in overview["proposals"][i]["unit_ids"]}
    rows = []
    for claim in overview["claims"]:
        unit = units[claim["unit_id"]]
        if overview["state"] != "ok":
            disposition = "overview_unavailable"
        elif claim["unit_id"] in cited:
            # The overview cites this claim's PASSAGE. If the claim added terms the passage lacks, the overview followed the
            # passage and did not carry them: the claim's own wording was not used.
            disposition = (
                "passage_used_claim_wording_not_used" if claim["novel_terms"] else "passage_restated_in_overview"
            )
        elif not unit["eligibility"]["eligible"]:
            disposition = "passage_not_used:" + ",".join(unit["eligibility"]["reasons"])
        elif not unit["sent_to_model"]:
            disposition = "passage_not_sent:" + str(unit["not_sent_reason"])
        else:
            disposition = "passage_not_cited_by_any_displayed_statement"
        rows.append({**claim, "disposition": disposition})
    return rows


def construction_record(sealed: dict, overview: dict) -> str:
    call = overview["call"] or {}
    lines = [
        "## Overview construction record",
        "",
        "Everything the overview stage did, kept out of the researcher-facing answer. Model-written text lives only in "
        f"`{RECORD_FILE}` and in the statements below; the sealed evidence ledger above is unchanged.",
        "",
        f"- Overview state: {overview['state']}"
        + (f" ({overview['reason_code']})" if overview["reason_code"] else "")
        + ("; PARTIAL (some proposed statements were withheld)" if overview["partial"] else ""),
        f"- Overview artifact hash: {overview['overview_hash']}",
        f"- Sealed evidence ledger hash (referenced, not modified): {overview['sealed_ledger_hash']}",
        f"- Model: {overview['model']} (thinking {overview['think']}); contract {overview['contract_sha256']}",
        f"- Options (explicit, fixed): {overview['options']}",
        f"- Call: outcome {call.get('outcome')}, done_reason {call.get('done_reason')}, prompt tokens {call.get('prompt_tokens')}, "
        f"generated tokens {call.get('generated_tokens')} (allowance {call.get('allowance')}), wall seconds {call.get('wall_seconds')}, "
        f"thinking chars {call.get('thinking_chars')}, repetition ratio {call.get('repetition_ratio')}",
        f"- {SCREENING_NOTE}",
        "",
        "### Passages",
        "",
        "| passage | locator | eligible | qualifications | reasons | sent | restated by |",
        "|---|---|---|---|---|---|---|",
    ]
    nums = _cite_numbers(overview)
    for u in overview["units"]:
        cited_as = f" (cited as [{nums[u['unit_id']]}])" if u["unit_id"] in nums and overview["items"] else ""
        lines.append(
            f"| {u['unit_id']}{cited_as} | {_literal(_locator(u))} | {u['eligibility']['eligible']} | {_literal(_flag_text(u))} | "
            f"{', '.join(u['eligibility']['reasons']) or '-'} | {u['sent_to_model']}{'' if u['sent_to_model'] else ' (' + str(u['not_sent_reason']) + ')'} | "
            f"{', '.join(u['proposition_ids'])} |"
        )
    lines += [
        "",
        "### What the overview did with each ledger claim",
        "",
        "| claim | passage | terms the claim adds beyond its passage | disposition |",
        "|---|---|---|---|",
    ]
    for row in claim_dispositions(overview):
        lines.append(
            f"| {row['proposition_id']} | {row['unit_id']} | {_literal(', '.join(row['novel_terms'])) or '-'} | {row['disposition']} |"
        )
    lines += [
        "",
        "`passage_used_claim_wording_not_used`: the overview cites this claim's passage but does not carry the terms the claim "
        "adds beyond it, so the claim's own wording was not used.",
        "",
        "### Proposed statements",
        "",
    ]
    if not overview["proposals"]:
        lines += ["None.", ""]
    stmt_no = {
        i: n for n, i in enumerate(overview["displayed"], start=1)
    }  # the numbers the researcher-facing answer uses
    for p in overview["proposals"]:
        nli = p["nli"]
        score = f"support {nli['support']}, contradiction {nli['contradiction']}" if nli else "not scored"
        label = f"statement {stmt_no[p['index']]}" if p["index"] in stmt_no else "not shown"
        lines += [
            f"- **{p['status'].upper()}** ({label}; passages {', '.join(map(str, p['unit_ids'] or []))}; bears on {p['bears_on']}): "
            f"{_literal(str(p['text']))}",
            f"  - reasons: {', '.join(p['reasons']) or 'none'}; NLI {score}",
        ]
    lines += ["", "### Request parts", "", "| part | status | attached passages | statements |", "|---|---|---|---|"]
    for part in overview["parts"]:
        lines.append(
            f"| {part['child_id']} {_literal(part['note'])} | {part['status']} | {', '.join(part['attached_unit_ids']) or '-'} | "
            f"{', '.join(str(stmt_no[i]) for i in part['statement_indices']) or '-'} |"
        )
    lines += [
        "",
        "Status vocabulary: passage_stated, hedged_only, topical_only, no_responsive_evidence, not_assessed. None is a "
        "completeness verdict; a tag is the overview model's reading of what a screened statement addresses.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def detailed_inspection(sealed: dict, overview: dict) -> str:
    """The existing ledger rendering, byte-for-byte, then the construction record."""
    base, _ = render_answer(sealed)
    return base.rstrip("\n") + "\n\n" + construction_record(sealed, overview)
