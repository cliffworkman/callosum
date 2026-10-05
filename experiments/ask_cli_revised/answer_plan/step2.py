"""Phase-30 Step 2: consolidation, qualification recall, grounded expansion. Pure: no model, no I/O.

`finalize` runs after the per-node facet build (plan.py) and, in order:
  1. Limitation discovery at paper level. Every sealed sentence from a paper that contributes displayed evidence to a node
     and carries a generic limitation or scope cue is attached to that node as a Layer-2 limitation. Attachment never
     depends on shared words. Background (prior work, stated aims, literature, design rationale) is excluded and recorded.
  2. Promotion. An attached limitation enters Layer 1 only when it stands on its own (closed and complete) AND directly
     interprets a displayed finding of its own paper: it shares two or more content words with that finding, or it refers
     back to "these findings". Anything else stays in Layer 2, with a fixed pointer.
  3. Grounded expansion. An acronym gains "Long Form (ACRONYM)" on its first Layer-1 use only when exactly one explicit
     definitional construction for it occurs in the same paper's sealed text. Otherwise it stays unexpanded and the reason
     is recorded.
  4. Disclosure consolidation. Facets that share a fixed state are worded in one sentence. Each generic explanation appears
     once per answer; the node keeps its own copy in Layer 2. No facet state is dropped; Layer 3 keeps every item.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.answer_plan import text as tx

LIMITATION_CUE = re.compile(
    r"\b(?:limit\w*|caveats?|cannot|may not|might not|not generaliz\w*|generaliz\w*|further research|future research|"
    r"future studies|preliminary|tentative\w*|durabilit\w*|alternative explanations?|interpret\w*|proxies|proxy|"
    r"directly test\w*)\b",
    re.IGNORECASE,
)
FINDING_REFERENCE = re.compile(
    r"\b(?:these|this|the present|such) (?:findings?|results?|effects?|associations?|differences?)\b", re.IGNORECASE
)
LITERATURE = re.compile(
    r"\b(?:meta-analys\w*|systematic review|(?:many|several|other|multiple|previous|prior|earlier|recent|existing)\s+"
    r"(?:studies|study|research|work|reports?|findings|investigations?)|studies (?:on|of)|the literature)\b",
    re.IGNORECASE,
)
RATIONALE = re.compile(
    r"\b(?:motivated|we expected|expected|predict\w*|prediction|hypothes\w*|agnostic|anticipat\w*|expectation)\b",
    re.IGNORECASE,
)
LIMITATION_SECTIONS = frozenset({"limitations"})
POINTER = "The paper adds a qualification to this result; it is listed in the supporting evidence."
CLOSED_END = '.!?)"”'
_STOP = frozenset(
    "about after again against among because before being between could during every from have into more most other "
    "over same should some such than that their there these they this those through under until very when where which "
    "while with within would participants study research results were found been also".split()
)


def loose(text: str) -> str:
    """Comparison-only normalization: joins PDF line-break hyphens, drops punctuation, lowercases. Decides containment in a
    verified quote; never used for display."""
    joined = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", joined).lower().split())


def content_tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[A-Za-z]{5,}", text) if t.lower() not in _STOP}


def paper_of(statement: dict, props: dict) -> int:
    return (
        statement["paper_id"] if statement.get("paper_id") is not None else props[statement["prop_ids"][0]]["paper_id"]
    )


def discover_limitations(ctx) -> list[dict]:
    """Every sealed sentence carrying a generic limitation cue, with its background verdict. Corpus-wide; per-node attachment
    filters these by paper. `excluded` is None for a candidate that may attach."""
    records = []
    for span in ctx.span_rows:
        for sentence in tx.split_sentences(span["text"]):
            cues = sorted({m.group(0).lower() for m in LIMITATION_CUE.finditer(sentence)})
            if not cues:
                continue
            kind = tx.attribution_kind(sentence, caption=False)
            excluded = None
            if kind in ("prior_work", "aim_or_hypothesis"):
                excluded = f"background ({kind})"
            elif LITERATURE.search(sentence):
                excluded = "background (literature)"
            elif RATIONALE.search(sentence):
                excluded = "background (design rationale)"
            records.append(
                {
                    "span_id": span["span_id"],
                    "paper_id": span["paper_id"],
                    "text": sentence,
                    "norm": tx.normalized_key(sentence),
                    "span_text": span["text"],
                    "cues": cues,
                    "attribution": kind,
                    "structural": span.get("section_family") in LIMITATION_SECTIONS,
                    "section_metadata_present": span.get("section_family") is not None,
                    "excluded": excluded,
                }
            )
    return records


def _promotion(entry: dict, displayed: list[dict], props: dict, promoted_norms: set) -> None:
    """Sets promoted, promotion_basis, shared_content_words, and not_promoted_reason on one attached entry. The entry's
    text is already heading-free (see finalize), so its normalized key matches the sentence that would be displayed."""
    stripped = entry["text"]
    closed = not tx.closure_failures(stripped) and stripped.rstrip()[-1:] in CLOSED_END
    same_paper = [s for s in displayed if paper_of(s, props) == entry["paper_id"]]
    shared_words = max(
        (sorted(content_tokens(stripped) & content_tokens(s["text"])) for s in same_paper), key=len, default=[]
    )
    refers = bool(FINDING_REFERENCE.search(stripped))
    basis = []
    if closed:
        basis.append("closed and complete on its own")
    if len(shared_words) >= 2:
        basis.append(f"shares {len(shared_words)} content words with a displayed finding of its paper")
    if refers:
        basis.append("refers back to the paper's own findings")
    promote = closed and (len(shared_words) >= 2 or refers)
    reason = None
    if not closed:
        reason = "not closed and complete on its own"
    elif not promote:
        reason = "does not directly interpret a displayed finding of its paper"
    elif entry["norm"] in promoted_norms:
        promote, reason = False, "already stated under an earlier item"
    if promote:
        promoted_norms.add(entry["norm"])
    entry.update(
        shared_content_words=shared_words,
        promotion_basis=basis,
        promoted=promote,
        not_promoted_reason=None if promote else reason,
    )


def _promoted_statement(entry: dict, displayed: list[dict], props: dict) -> dict:
    same_paper = [s for s in displayed if paper_of(s, props) == entry["paper_id"]]
    best = max(same_paper, key=lambda s: len(content_tokens(entry["text"]) & content_tokens(s["text"])))
    return {
        "claim_id": f"limitation:{entry['span_id']}:{entry['norm'][:16]}",
        "facet_id": best["facet_id"],
        "kind": "qualification_sentence",
        "text": entry["text"],
        "prop_ids": [],
        "attribution": "limitation",
        "edits": entry["edits"],
        "facet_state": None,
        "subject": None,
        "span_id": entry["span_id"],
        "paper_id": entry["paper_id"],
        "span_text": entry["span_text"],
        "values": None,
    }


def _ground_node(node: dict, ctx, introduced: dict, grounded: set) -> None:
    """First Layer-1 use of each grounded acronym gets its explicit same-paper long form. Later uses stay bare."""
    for statement in node["statements"]:
        pid = (
            statement["paper_id"]
            if statement.get("paper_id") is not None
            else ctx.props[statement["prop_ids"][0]]["paper_id"]
        )
        same_spans = [s for s in ctx.span_rows if s["paper_id"] == pid]
        for term in tx.acronyms(statement["text"]):
            hits = tx.definition_hits(term, same_spans)
            longs = sorted({h["long_form"] for h in hits})
            if len(longs) != 1:
                continue
            grounded.add(term)
            if term in introduced:
                continue
            long_form = longs[0]
            defined_here = re.search(
                re.escape(long_form) + r"\s*\(\s*" + re.escape(term) + r"\s*\)", statement["text"]
            ) or re.search(re.escape(term) + r"\s*\(\s*" + re.escape(long_form) + r"\s*\)", statement["text"])
            if defined_here:
                introduced[term] = {"term": term, "long_form": long_form, "applied": "already_defined_in_sentence"}
                continue
            match = re.search(r"(?<![\w\-(])" + re.escape(term) + r"(?![\w\-)])", statement["text"])
            if not match:
                continue
            hit = next(h for h in hits if h["long_form"] == long_form)
            replacement = f"{long_form} ({term})"
            edit = {
                "kind": "acronym_expansion_introduced",
                "from": term,
                "to": replacement,
                "long_form": long_form,
                "span_id": hit["span_id"],
                "paper_id": pid,
            }
            statement["text"] = statement["text"][: match.start()] + replacement + statement["text"][match.end() :]
            statement["edits"] = list(statement.get("edits") or []) + [edit]
            introduced[term] = {**edit, "applied": "expanded_at_first_use"}


def _definition_record(term: str, node_papers: set, ctx) -> dict:
    hits = tx.definition_hits(term, ctx.span_rows)
    same = [h for h in hits if h["paper_id"] in node_papers]
    cross = [h for h in hits if h["paper_id"] not in node_papers]
    longs = sorted({h["long_form"] for h in same})
    if not hits:
        why = "no explicit definition in the sealed text; left unexpanded"
    elif not same:
        why = "defined only in another paper's sealed text; not applied to this item"
    elif len(longs) > 1:
        why = "more than one explicit definition in the paper; not applied"
    else:
        why = "explicit definition in the paper's sealed text"
    return {
        "term": term,
        "long_form": longs[0] if len(longs) == 1 else None,
        "supporting_span_ids": [h["span_id"] for h in same],
        "other_paper_span_ids": [h["span_id"] for h in cross],
        "why": why,
    }


def _listed(lead: str, phrases: list[str]) -> str:
    if len(phrases) == 1:
        return f"{lead} {phrases[0]}."
    return f"{lead} any of the following: " + "; ".join(phrases) + "."


def _unique(values) -> list:
    out: list = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _consolidate(node: dict, generic_shown: set, pointer: bool) -> list[str]:
    items = node["disclosure_items"]
    out: list[str] = []
    not_established = _unique(i["phrase"] for i in items if i["kind"] == "not_established")
    searched = _unique(i["phrase"] for i in items if i["kind"] == "searched_empty")
    if not_established:
        out.append(_listed("The retrieved evidence does not establish", not_established))
    if searched:
        out.append(_listed("The scoped search completed without establishing", searched))
    for item in items:
        if item["kind"] in ("relation_unwitnessed", "role_missing") and item["text"] not in out:
            out.append(item["text"])
    for item in items:
        if item["kind"] == "reason" and item["text"] not in generic_shown:
            generic_shown.add(item["text"])
            out.append(item["text"])
    if pointer and POINTER not in generic_shown:
        generic_shown.add(POINTER)
        out.append(POINTER)
    return out


def finalize(nodes: list[dict], ctx, props: dict, set_aside: dict) -> dict:
    """Mutates nodes in overlay order: adds promoted Layer-1 statements, grounded expansions, consolidated disclosures, and
    the Layer-2 and Layer-3 records. Returns plan-level Step-2 records. `set_aside` maps node label -> Layer-2 entries."""
    discovered = discover_limitations(ctx)
    promoted_norms: set = set()
    introduced: dict = {}
    grounded: set = set()
    generic_shown: set = set()
    for node in nodes:
        displayed = list(node["statements"])
        papers = {paper_of(s, props) for s in displayed}
        displayed_norms = {tx.normalized_key(s["text"]) for s in displayed}
        decisions, attached = [], []
        listed: set = set()
        for record in discovered:
            if record["paper_id"] not in papers:
                continue
            entry = dict(record)
            stripped, heading_edit = tx.strip_run_in_heading(entry["text"])
            entry["text"] = stripped
            entry["edits"] = [heading_edit] if heading_edit else []
            entry["norm"] = tx.normalized_key(stripped)
            if entry["excluded"] is None and entry["norm"] in displayed_norms:
                entry["excluded"] = "already stated in this answer"
            elif entry["excluded"] is None and entry["norm"] in listed:
                entry["excluded"] = "same sentence already listed for this item (overlapping source span)"
            if entry["excluded"] is not None:
                entry["promoted"] = False
                entry["not_promoted_reason"] = entry["excluded"]
                decisions.append(entry)
                continue
            listed.add(entry["norm"])
            _promotion(entry, displayed, props, promoted_norms)
            decisions.append(entry)
            attached.append(entry)
        for entry in attached:
            if entry["promoted"]:
                node["statements"].append(_promoted_statement(entry, displayed, props))
        _ground_node(node, ctx, introduced, grounded)
        node_terms = _unique(t for s in node["statements"] for t in tx.acronyms(s["text"]))
        definitions = [_definition_record(term, papers, ctx) for term in node_terms]
        node["disclosures"] = _consolidate(node, generic_shown, any(not e["promoted"] for e in attached))
        node["not_assessed"] = _unique(node["not_assessed"])
        passages = [
            {
                "claim_id": s["claim_id"],
                "text": s["text"],
                "quote": props[s["prop_ids"][0]]["quote"],
                "paper_id": paper_of(s, props),
                "page": (props[s["prop_ids"][0]].get("verification") or {}).get("page_start"),
                "statistics": tx.has_statistics(props[s["prop_ids"][0]]["quote"]),
            }
            for s in displayed
            if s.get("prop_ids")
        ]
        node["layer2"] = {
            "passages": passages,
            "limitations": [_limitation_view(e) for e in attached],
            "definitions": definitions,
            "set_aside": set_aside.get(node["label"], []),
            "not_assessed": node["not_assessed"],
        }
        node["layer3"] = {
            "limitation_decisions": decisions,
            "disclosure_items": node["disclosure_items"],
        }
    return {
        "grounded_terms": sorted(grounded),
        "introduced_terms": {term: introduced[term] for term in sorted(introduced)},
        "promoted_count": len(promoted_norms),
        "discovered_candidate_count": len(discovered),
        "structural_metadata_available": any(r["section_metadata_present"] for r in discovered),
    }


def _limitation_view(entry: dict) -> dict:
    cues = ", ".join(f"“{c}”" for c in entry["cues"])
    return {
        "span_id": entry["span_id"],
        "paper_id": entry["paper_id"],
        "text": entry["text"],
        "promoted": entry["promoted"],
        "why_attached": [
            "same paper as displayed evidence on this item",
            f"generic limitation or scope cue: {cues}",
            "structural section metadata"
            if entry["structural"]
            else "lexical cue only (no section metadata in the sealed spans)",
        ],
        "promotion_basis": entry["promotion_basis"],
        "shared_content_words": entry["shared_content_words"],
        "not_promoted_reason": entry["not_promoted_reason"],
    }
