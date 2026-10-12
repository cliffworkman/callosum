"""The reader-facing hierarchical answer: a narrative parent overview, then every approved subquestion in its
approved order with its own cited child synthesis.

Two parts, both additive and off unless a run asks for them:

1. ``parent_view`` builds the evidence the parent overview may draw on. It is the sealed ledger restricted to
   the source passages that at least one *displayed* (screened, grounded) child-synthesis statement cites. The
   parent overview is then produced by the unchanged ``overview.build_overview`` -- the same prompt, schema,
   lexical screens, local NLI screen, record and audit the child syntheses use -- over that view. So the parent
   overview is a synthesis across what the child syntheses rest on; its authority is the source passages, never
   a child statement or a ParentClaim; and a statement that fails screening is withheld, not shown.
2. ``render`` assembles the document deterministically from records the run already produced. It writes no
   scientific content of its own. A subquestion with no grounded statement stays in the document and says so.

The deterministic ParentClaim ledger and its realization (``parent_synthesis``) are unchanged and remain an
inspection artifact; this module reads only that record's gap report, to say what remains unresolved.
"""

from __future__ import annotations

from experiments.ask_cli_revised import overview_render as ovr
from experiments.ask_cli_revised.ledger_renderer import _literal

VERSION = "hierarchical-answer-v1"
STAGE_LABEL = "S3"
ANSWER_FILE = "19_hierarchical_answer.md"
EVIDENCE_FILE = "19b_hierarchical_answer_evidence.md"
RECORD_FILE = "19a_parent_overview.json"
PARENT_DETAIL_FILE = "19c_parent_overview_inspection.md"
MANIFEST_FILE = "19d_hierarchical_answer_manifest.json"

_GAP_PHRASE = {
    "missing": "not established in the retrieved evidence",
    "partial": "only partly established",
    "provisional_corroboration": "one usable finding; corroboration still open",
    "relationship_unverified": "the ingredients may be present, but the relationship is not established",
    "open_list_breadth": "findings exist; the breadth of the list remains open",
}
SCOPE_NOTE = (
    "This answer reports the evidence retrieved and verified in this run. It makes no statement about what the "
    "library or the literature holds, and completeness is not certified. Screening can withhold a statement but "
    "cannot prove one correct; every statement cites the passages it restates."
)


def parent_view(sealed: dict, child_records: dict[str, dict]) -> dict:
    """The sealed ledger restricted to passages cited by displayed child-synthesis statements (ledger order kept)."""
    cited = {pid for record in child_records.values() for item in record["items"] for pid in item["proposition_ids"]}
    propositions = [row for row in sealed["verified_propositions"] if row["proposition_id"] in cited]
    wanted: set[tuple] = set()
    for row in propositions:
        wanted.add((row["paper_id"], row["evidence_anchor_chunk_id"], row["evidence_span_id"]))
        for anchor in row.get("anchors") or ():
            wanted.add((row["paper_id"], anchor["chunk_id"], anchor["span_id"]))
    return {
        "request_contract": {
            "original_question": sealed["request_contract"]["original_question"],
            "question_hash": sealed["request_contract"]["question_hash"],
            "scope": "passages_cited_by_displayed_child_statements",
        },
        # Every approved child stays a request part; each lists only the claims this view actually holds.
        "obligation_states": [
            {**state, "proposition_ids": [pid for pid in state["proposition_ids"] if pid in cited]}
            for state in sealed["obligation_states"]
        ],
        "verified_propositions": propositions,
        "evidence_spans": [
            s for s in sealed.get("evidence_spans", []) if (s["paper_id"], s["chunk_id"], s["span_id"]) in wanted
        ],
    }


class _Sources:
    """One citation number per source passage across the whole document, in order of first use."""

    def __init__(self) -> None:
        self.order: list[tuple] = []
        self.units: dict[tuple, dict] = {}

    def number(self, unit: dict) -> int:
        key = (unit["paper_id"], " ".join(unit["passage"].split()))
        if key not in self.units:
            self.order.append(key)
            self.units[key] = unit
        return self.order.index(key) + 1


def _narrative(record: dict, sources: _Sources) -> tuple[list[str], list[dict]]:
    """A synthesis record as one cited paragraph plus the honest notes about what screening did."""
    units = {u["unit_id"]: u for u in record["units"]}
    lines: list[str] = []
    statements: list[dict] = []
    if record["state"] == "ok":
        sentences = []
        for item in record["items"]:
            numbers = sorted({sources.number(units[u]) for u in item["unit_ids"]})
            sentences.append(f"{_literal(item['text'])} {''.join(f'[{n}]' for n in numbers)}")
            statements.append({"text": item["text"], "citation_numbers": numbers, "unit_ids": item["unit_ids"]})
        lines += [" ".join(sentences), ""]
        withheld = len(record["proposals"]) - len(record["displayed"])
        if withheld:
            lines += [
                f"_{withheld} further proposed statement(s) were withheld by screening and are not shown; "
                "this synthesis may omit findings the passages support._",
                "",
            ]
    else:
        lines += [f"_{ovr._state_message(record)}_", ""]
    return lines, statements


def _gap_lines(gaps: list[dict]) -> list[str]:
    seen: list[str] = []
    for gap in gaps:
        what = "; ".join(gap.get("category_descriptions") or gap.get("target_roles") or ["an unnamed requirement"])
        line = f"- {_literal(what)}: {_GAP_PHRASE.get(gap.get('reason'), gap.get('reason') or 'unresolved')}."
        if line not in seen:
            seen.append(line)
    return seen


def render(
    *,
    question: str,
    subquestions: list[dict],
    child_records: dict[str, dict],
    child_files: dict[str, dict],
    wordings: dict[str, str],
    parent_record: dict,
    gap_report: list[dict] | None,
    paper_labels: dict[int, str] | None = None,
    parent_claims_file: str | None = None,
) -> tuple[str, str, dict]:
    """``(answer_markdown, evidence_markdown, manifest)``. Deterministic; reads records only."""
    sources = _Sources()
    paper_labels = paper_labels or {}
    lines = ["# Answer", "", "> " + _literal(question), "", "## Overview", ""]
    overview_lines, parent_statements = _narrative(parent_record, sources)
    lines += overview_lines
    capped = sum(1 for u in parent_record["units"] if u.get("not_sent_reason") == "omitted_by_prompt_cap")
    if capped:
        lines += [
            f"_{capped} cited passage(s) did not fit the overview's evidence limit and were not offered to it._",
            "",
        ]
    silent = [sq for sq in subquestions if child_records[sq["subquestion_id"]]["state"] != "ok"]
    open_children = sorted({g["search_child_id"] for g in gap_report or [] if g.get("search_child_id")})
    lines += ["**What remains unresolved.**", ""]
    if silent:
        lines.append(
            "No synthesis statement passed screening for: "
            + "; ".join(f'"{_literal(wordings[sq["subquestion_id"]])}"' for sq in silent)
            + "."
        )
    if gap_report is None:
        lines.append("The structured account of open evidence requirements was not produced in this run.")
    elif open_children:
        lines.append(
            f"{len(gap_report)} evidence requirement(s) remain open across {len(open_children)} subquestion(s); "
            "they are listed under each subquestion below."
        )
    else:
        lines.append("No open evidence requirement was recorded. This is not a certificate of completeness.")
    lines.append("")

    manifest_children = []
    for number, sq in enumerate(subquestions, start=1):
        child_id = sq["subquestion_id"]
        record = child_records[child_id]
        lines += [f"## {number}. {_literal(wordings[child_id])}", ""]
        child_lines, statements = _narrative(record, sources)
        lines += child_lines
        gaps = _gap_lines([g for g in gap_report or [] if g.get("search_child_id") == child_id])
        if gaps:
            lines += ["Not established for this subquestion:", "", *gaps, ""]
        files = child_files[child_id]
        lines += [f"_Evidence and screening detail: `{files['answer_file']}`, `{files['detail_file']}`._", ""]
        manifest_children.append(
            {"child_id": child_id, "wording": wordings[child_id], "state": record["state"], "statements": statements}
        )

    lines += ["## Sources", ""]
    evidence = ["# Evidence for the hierarchical answer", "", "Each numbered source is the exact verified passage.", ""]
    for number, key in enumerate(sources.order, start=1):
        unit = sources.units[key]
        label = paper_labels.get(unit["paper_id"])
        page = (unit.get("verification") or {}).get("page_start")
        where = (f"{_literal(label)} (paper {unit['paper_id']})" if label else f"Paper {unit['paper_id']}") + (
            f", p. {page}" if page else ""
        )
        lines.append(f"[{number}] {where}")
        evidence += [f"**[{number}]** {ovr._locator(unit)}; source-verified.", "", "> " + _literal(unit["passage"]), ""]
        verification = unit.get("verification") or {}
        evidence += [
            "Verification: "
            + ", ".join(
                f"{k} {verification[k]:.3f}"
                for k in ("retrieval", "quote", "support", "contradiction")
                if k in verification
            )
            + f". Qualifications: {ovr._flag_text(unit)}.",
            "",
        ]
    if not sources.order:
        lines.append("No statement was displayed, so no source is cited.")
    lines += [
        "",
        "## Inspecting this answer",
        "",
        f"- Exact quotations and verification scores for every source above: `{EVIDENCE_FILE}`.",
        f"- The overview's own record, withheld statements and screening reasons: `{RECORD_FILE}`, `{PARENT_DETAIL_FILE}`.",
    ]
    if parent_claims_file:
        lines.append(
            f"- The deterministic parent claim ledger and the full list of open requirements: `{parent_claims_file}`."
        )
    lines += ["", f"_{SCOPE_NOTE}_", ""]
    manifest = {
        "version": VERSION,
        "parent_overview": {
            "state": parent_record["state"],
            "overview_hash": parent_record["overview_hash"],
            "sealed_ledger_hash": parent_record["sealed_ledger_hash"],
            "statements": parent_statements,
            "units_offered": sum(1 for u in parent_record["units"] if u.get("sent_to_model")),
            "units_omitted_by_cap": capped,
        },
        "children": manifest_children,
        "sources": [
            {"number": n, "paper_id": sources.units[k]["paper_id"], "locators": sources.units[k]["locators"]}
            for n, k in enumerate(sources.order, start=1)
        ],
    }
    return "\n".join(lines).rstrip() + "\n", "\n".join(evidence).rstrip() + "\n", manifest


def audit(
    answer: str, subquestions: list[dict], wordings: dict[str, str], child_records: dict[str, dict], parent_record: dict
) -> list[str]:
    """Problems with the rendered document; empty means every structural promise holds."""
    problems: list[str] = []
    position = answer.find("## Overview")
    if position < 0:
        problems.append("no overview section")
    for number, sq in enumerate(subquestions, start=1):
        heading = f"## {number}. {_literal(wordings[sq['subquestion_id']])}\n"
        found = answer.find(heading, max(position, 0))
        if found < 0:
            problems.append(f"subquestion {sq['subquestion_id']} missing or out of order")
            continue
        position = found
    displayed = [i["text"] for i in parent_record["items"]] + [
        i["text"] for sq in subquestions for i in child_records[sq["subquestion_id"]]["items"]
    ]
    for text in displayed:
        if _literal(text) not in answer:
            problems.append(f"a displayed statement is missing from the answer: {text[:60]}")
    withheld = [
        p["text"]
        for record in [parent_record, *child_records.values()]
        for p in record["proposals"]
        if p["status"] != "grounded" and isinstance(p.get("text"), str)
    ]
    for text in withheld:
        if text not in displayed and _literal(text) in answer:
            problems.append(f"a withheld statement appears in the answer: {text[:60]}")
    return problems
