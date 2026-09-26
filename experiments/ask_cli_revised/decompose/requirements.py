"""Clarification requirements: what an approved clarification means for a child, with provenance, and how each can be checked.

A clarification's ``means`` is prose. This module turns what is ESTABLISHED about it into records a check can use, and keeps what is
NOT established visibly undecided. Three questions are kept apart, because they are different decisions:

* ``in_approved_clarification``: are these words in the researcher-approved meaning? (verified verbatim, never assumed)
* ``expression``: may the words be used to express that meaning in a child? ``permitted`` / ``permitted_pending_confirmation`` /
  ``undecided`` / ``not_applicable``
* ``required_in_child``: must the child explicitly contain it? ``required`` / ``not_required`` / ``undecided``, or
  ``required_in_meaning`` (the researcher decided the SCOPE must be preserved but the literal words are not required; only the
  researcher's approved words are authorized, and whether the meaning survived in other words is for human review)

Records derived from FIELDS THE RESEARCHER APPROVED (``adds``, a reference clarification's ``refers_to``, ``pairs``) are required,
authority ``researcher_approved``. Records from an ANNOTATION file are recorded by the engine author and can never be required or
approved by themselves: an expression is at most ``permitted_pending_confirmation`` and an explanatory detail is ``undecided``,
until the researcher (``approved_by``) decides. A pending record is never silently promoted; a child that relies on one is reported
as ``pending_researcher_confirmation`` (never an unqualified clean result), and a child that uses an undecided detail is a review.

Every check here is LEXICAL. ``LIMITS`` says so, and each check reports what it cannot verify.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import lexical as lx

_WORD = re.compile(r"[A-Za-z0-9]+")
PENDING = "engine_recorded_pending_confirmation"
APPROVED = "researcher_approved"
EXPRESSION_FUNCTIONS = ("conditional_qualification",)
ANNOTATED_KINDS = ("qualifier_expression", "detail", "scope_item", "constraint")
DECIDED_KINDS = ("scope_item", "constraint")  # only the researcher can record these (approved_by is mandatory)
LIMITS = {
    "pairing": "both members of a recorded pair are checked for presence in the wording; whether the intended pairing (each value with its counterpart) survived is not verifiable by a lexical check",
    "reference": "a clarified reference is checked as replaced by, or accompanied by, the words it points at; that those words are the intended referent is the researcher's decision",
    "referent_relationship": "the relationship a fragment must carry is checked by its relation and slot words being present; whether they still relate the same way is not verifiable by a lexical check",
    "scope": "scope the researcher approved to be preserved in meaning is recognised only by the researcher's approved words; whether it survived in other words, and whether nothing was presupposed, is not verifiable by a lexical check and is for human review",
    "referent_relationship_unparsed": "the question this fragment continues has no parsed relationship (the relation-verb list is closed and English-only), so the qualification of the referent cannot be checked",
}


KNOWN_LIMITATIONS = (
    "relationships are detected through a closed, English-only relation-verb list; a relationship stated with another verb that the inventory labels a requested item is not checked as a relationship",
    "ONE background subject is derived from the first source unit only; a request about several unrelated subjects is not modelled",
    "every cue, function-word and operator table is English-only, and the length, run and threshold constants are fixed",
    "every check is lexical: it can find a dropped, added or borrowed word, but not whether meaning, a pairing or a relationship survived",
    "a clean ledger means no source-edit problem was DETECTED; it never certifies provenance or semantic fidelity",
)


def words(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text)]


def find_runs(hay: list[str], needle: list[str]) -> list[tuple[int, int]]:
    """Every [lo, hi) where ``needle`` occurs as a contiguous run of ``hay``."""
    if not needle:
        return []
    return [(i, i + len(needle)) for i in range(len(hay) - len(needle) + 1) if hay[i : i + len(needle)] == needle]


def _row_error(cid: str, msg: str) -> ValueError:
    return ValueError(f"{cid}: {msg}")


def validate_annotated(clar: dict, rows: list) -> list[dict]:
    """Annotation rows for one approved clarification. Verbatim-in-approved-means is enforced; the engine author can never make
    a record required or approved: only a row naming ``approved_by`` can carry researcher authority."""
    cid, means = clar["id"], clar["means"].lower()
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        kind, text = row.get("kind"), row.get("text")
        if kind not in ANNOTATED_KINDS:
            raise _row_error(cid, f"a requirement kind must be one of {ANNOTATED_KINDS}")
        if not isinstance(text, str) or not text.strip():
            raise _row_error(cid, "a requirement needs its exact words (text)")
        if text.lower() not in means:
            raise _row_error(
                cid, f"requirement text {text!r} is not verbatim in the approved meaning; the engine may not invent one"
            )
        rid = row.get("id") or f"{cid}#{kind}:{'-'.join(words(text))}"
        if rid in seen:
            raise _row_error(cid, f"duplicate requirement id {rid}")
        seen.add(rid)
        approved_by = str(row.get("approved_by") or "").strip()
        authority = APPROVED if approved_by else PENDING
        if kind in DECIDED_KINDS and not approved_by:
            raise _row_error(cid, f"a {kind} records a researcher decision: approved_by is mandatory")
        if kind == "scope_item":
            phrases = row.get("phrases")
            if not (isinstance(phrases, list) and phrases and all(isinstance(x, str) and words(x) for x in phrases)):
                raise _row_error(cid, "a scope_item needs the approved phrases that show it in a child")
            if any(x.lower() not in means for x in phrases):
                raise _row_error(cid, "every scope_item phrase must be verbatim in the approved meaning")
            rec = {
                "id": rid,
                "clarification": cid,
                "kind": kind,
                "text": text,
                "phrases": [x.lower() for x in phrases],
                "in_approved_clarification": True,
                "expression": "permitted",
                "required_in_child": "required_in_meaning",
                "literal_wording": "not_required",
                "authority": authority,
                "authorizes_wording": True,
            }
        elif kind == "constraint":
            rec = {
                "id": rid,
                "clarification": cid,
                "kind": kind,
                "text": text,
                "in_approved_clarification": True,
                "expression": "not_applicable",
                "required_in_child": "required_in_meaning",
                "literal_wording": "not_required",
                "check": "relationship_conformance",
                "authority": authority,
                "authorizes_wording": False,
            }
        elif kind == "qualifier_expression":
            if row.get("function") not in EXPRESSION_FUNCTIONS:
                raise _row_error(cid, f"an expression needs a declared function, one of {EXPRESSION_FUNCTIONS}")
            required = row.get("required_in_child", "undecided")
            if required not in ("undecided", "required", "not_required"):
                raise _row_error(cid, "required_in_child must be 'undecided', 'required' or 'not_required'")
            if required != "undecided" and not approved_by:
                raise _row_error(
                    cid, "only the researcher can make wording required or not required (approved_by is missing)"
                )
            rec = {
                "id": rid,
                "clarification": cid,
                "kind": kind,
                "text": text,
                "function": row["function"],
                "qualifies": row.get("qualifies"),
                "in_approved_clarification": True,
                "expression": "permitted" if approved_by else "permitted_pending_confirmation",
                "required_in_child": required,
                "authority": authority,
                "authorizes_wording": True,
            }
        else:  # detail: meaning the approved text carries whose treatment nobody has decided
            evidence = row.get("evidence_words") or words(text)
            if not (
                isinstance(evidence, list) and evidence and all(isinstance(w, str) and w.strip() for w in evidence)
            ):
                raise _row_error(cid, "a detail needs evidence_words (the words that show it in a child)")
            if any(w.lower() not in set(words(means)) for w in evidence):
                raise _row_error(cid, "every evidence word must occur in the approved meaning")
            if approved_by or row.get("expression") or row.get("required_in_child"):
                raise _row_error(
                    cid,
                    "a detail is undecided until the researcher decides; record the decision as an approved scope_item, expression or constraint instead",
                )
            rec = {
                "id": rid,
                "clarification": cid,
                "kind": kind,
                "text": text,
                "evidence_words": [w.lower() for w in evidence],
                "in_approved_clarification": True,
                "expression": "undecided",
                "required_in_child": "undecided",
                "authority": "none",
                "authorizes_wording": False,
            }
        rec["provenance"] = {
            "source": "annotation_file",
            "recorded_by": row.get("recorded_by", "unknown"),
            "basis": "verbatim_in_approved_means",
            "approved_by": approved_by or None,
            "decision": row.get("decision"),
        }
        out.append(rec)
    return out


def derive(parent: dict) -> None:
    """Attach ``requirements`` to every clarification: the records the approved fields establish plus the validated annotations.
    Nothing is invented: each record names the field or annotation it came from."""
    for c in parent.get("clarifications", []):
        recs: list[dict] = []
        base = {
            "clarification": c["id"],
            "in_approved_clarification": True,
            "authority": APPROVED,
            "authorizes_wording": False,
        }
        for a in c.get("adds", []):
            word = "how" if a == "manner" else "whether"
            recs.append(
                {
                    **base,
                    "id": f"{c['id']}#adds:{a}",
                    "kind": "operation_added",
                    "text": word,
                    "expression": "not_applicable",
                    "required_in_child": "required",
                    "provenance": {
                        "source": "approved_clarification",
                        "field": "adds",
                        "authorized_by": c["authorized_by"],
                    },
                }
            )
        if c["kind"] == "reference" and c.get("refers_to"):
            recs.append(
                {
                    **base,
                    "id": f"{c['id']}#reference",
                    "kind": "reference_resolved",
                    "text": c["target_text"],
                    "antecedent": c["refers_to"]["text"],
                    "expression": "not_applicable",
                    "required_in_child": "required",
                    "provenance": {
                        "source": "approved_clarification",
                        "field": "refers_to",
                        "authorized_by": c["authorized_by"],
                    },
                }
            )
        if c.get("pairs"):
            recs.append(
                {
                    **base,
                    "id": f"{c['id']}#pair",
                    "kind": "paired_answer",
                    "members": [m["text"] for m in c["pairs"]],
                    "expression": "not_applicable",
                    "required_in_child": "required",
                    "provenance": {
                        "source": "approved_clarification",
                        "field": "pairs",
                        "authorized_by": c["authorized_by"],
                    },
                }
            )
        recs.extend(c.get("annotated_requirements", []))
        amended: dict[str, list[dict]] = {}
        for a in c.get("amendments", []):
            amended.setdefault(a["amends"], []).append(a)
        c["requirements"] = [{**r, "amended_by": amended[r["id"]]} if r["id"] in amended else r for r in recs]


def pending_decisions(parent: dict) -> list[dict]:
    """Everything an approved clarification touches that the researcher has NOT decided (never decided here)."""
    out = []
    for c in parent.get("clarifications", []):
        for r in c.get("requirements", []):
            if r["authority"] == PENDING:
                out.append(
                    {
                        "id": r["id"],
                        "clarification": c["id"],
                        "what": f"confirm that {r['text']!r} may express the approved meaning",
                        "kind": r["kind"],
                    }
                )
            if r["kind"] == "qualifier_expression" and r["required_in_child"] == "undecided":
                out.append(
                    {
                        "id": r["id"],
                        "clarification": c["id"],
                        "what": f"decide whether a child must explicitly contain {r['text']!r}",
                        "kind": r["kind"],
                    }
                )
            if r["kind"] == "detail":
                out.append(
                    {
                        "id": r["id"],
                        "clarification": c["id"],
                        "what": f"decide whether {r['text']!r} is required content, permitted wording or background",
                        "kind": r["kind"],
                    }
                )
        link = c.get("context_link")
        if link and link.get("authority") == PENDING:
            out.append(
                {
                    "id": f"{c['id']}#context_link",
                    "clarification": c["id"],
                    "what": f"confirm the joining words {link['text']!r}",
                    "kind": "context_link",
                }
            )
        if c.get("brief") and c["brief"]["status"] != "approved":
            out.append(
                {
                    "id": f"{c['id']}#brief",
                    "clarification": c["id"],
                    "what": "approve, edit or reject the proposed brief (it never authorizes wording)",
                    "kind": "brief",
                }
            )
    seen, unique = set(), []
    for d in out:
        key = (d["id"], d["what"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def missing_words(text: str, child_stems: list[str]) -> list[str]:
    """The content WORDS of ``text`` (not stems) whose stem the child lacks."""
    return [
        w for w in dict.fromkeys(lx.tokens(text)) if lx.is_content_token(w) and not lx.has_stem(child_stems, lx.stem(w))
    ]


# ---- checks (all lexical; each reports the limit of what it can verify) --------------------------------------------------------------------
def _overlaps(a: list[int], b: list[int]) -> bool:
    return max(a[0], b[0]) < min(a[1], b[1])


def slot_of(contract: dict, lo: int, hi: int) -> str | None:
    for slot in ("subject", "relation", "target"):
        if any(s[0] <= lo and hi <= s[1] for s in contract[slot]["spans"]):
            return slot
    return None


def _own_spans(ctx: dict) -> list[list[int]]:
    spans: list[list[int]] = []
    for e in ctx["extract"]:
        spans += [list(s) for s in (e.get("spans") or [e["span"]])]
    return spans


def _result(r: dict, state: str, **extra) -> dict:
    return {
        "id": r["id"],
        "kind": r["kind"],
        "text": r.get("text") or ", ".join(r.get("members", [])),
        "authority": r["authority"],
        "expression": r["expression"],
        "required_in_child": r["required_in_child"],
        "state": state,
        **extra,
    }


def _unparsed_relationship_over(parent: dict, plans: list[dict], span: list[int]) -> bool:
    """Does a relationship the request states around ``span`` exist that the closed relation-verb list could not parse?"""
    for r in parent["requirements"]:
        if r["kind"] == "relationship" and not r.get("superseded") and any(_overlaps(span, s) for s in r["spans"]):
            owner = next((p for p in plans if r["id"] in p["owns"]), None)
            if owner and owner.get("relation") and owner["relation"].get("parse_status") != "parsed":
                return True
    return False


def check_child(
    parent: dict, words_: list[str], plan: dict, plans: list[dict], ctx: dict, applicable: list[dict]
) -> tuple[list, list, list]:
    """Results, ledger flags and verification limits for the requirements that bear on one child's wording.

    ``operation_added``, ``reference_resolved``, ``paired_answer`` and the fragment's ``referent_relationship_carried`` are checked
    here; ``qualifier_expression`` and ``detail`` states come from the ledger, which sees the wording token by token."""
    results: list[dict] = []
    flags: list[dict] = []
    limits: list[str] = []
    child_stems = lx.content_stems(" ".join(words_))
    own = _own_spans(ctx)
    for c in applicable:
        for r in c.get("requirements", []):
            kind = r["kind"]
            if kind == "operation_added":
                results.append(_result(r, "met" if r["text"] in words_ else "not_met"))
            elif kind == "reference_resolved":
                if not any(_overlaps(c["target_span"], s) for s in own):
                    results.append(_result(r, "not_applicable"))
                    continue
                if not find_runs(words_, words(r["text"])):
                    results.append(_result(r, "met", how="replaced by the words it points at, or absent"))
                    continue
                missing = lx.missing_stems(lx.content_stems(r["antecedent"]), child_stems)
                if missing:
                    flags.append(
                        {
                            "kind": "clarified_reference_unresolved",
                            "class": "review",
                            "words": [r["text"]],
                            "note": f'"{r["text"]}" was clarified ({c["id"]}) to mean "{r["antecedent"]}", but the wording still uses "{r["text"]}" and does not state those words, so it is not independently intelligible',
                        }
                    )
                    results.append(_result(r, "not_met", missing=missing))
                else:
                    results.append(_result(r, "met", how="the reference word stays beside the words it points at"))
                limits.append(LIMITS["reference"])
            elif kind == "paired_answer":
                # both halves in this question's own words, OR this question is the fragment the pairing clarifies and owns one half
                # (the other half is what it continues): either way it must keep BOTH
                holds = any(j["clarification"] == c["id"] for j in ctx["joint"]) or (
                    plan.get("clarified_fragment") == c["id"]
                    and any(_overlaps(m["span"], s) for m in c["pairs"] for s in own)
                )
                if not holds:
                    results.append(_result(r, "not_applicable"))
                    continue
                state, absent, partial = "members_present", [], []
                for m in r["members"]:
                    need = lx.content_stems(m)
                    if not need:
                        state = "unverifiable"
                        continue
                    lacking = lx.missing_stems(need, child_stems)
                    if lacking and len(lacking) == len(need):
                        absent.append(m)
                    elif lacking:
                        partial.append(m)
                if absent:
                    state = "member_missing"
                    flags.append(
                        {
                            "kind": "pair_member_missing",
                            "class": "conflict",
                            "words": absent,
                            "note": f"the recorded pairing {c['id']} keeps {' and '.join(repr(m) for m in r['members'])} together; the wording has nothing of {', '.join(repr(m) for m in absent)}",
                        }
                    )
                elif partial:
                    state = "member_partial"
                    flags.append(
                        {
                            "kind": "pair_member_partial",
                            "class": "review",
                            "words": partial,
                            "note": f"the recorded pairing {c['id']}: only part of {', '.join(repr(m) for m in partial)} is in the wording",
                        }
                    )
                results.append(_result(r, state))
                if state in ("members_present", "member_partial"):
                    limits.append(LIMITS["pairing"])
    frag = plan.get("clarified_fragment")
    if frag and ctx["inherited_extracts"]:
        clar = next((c for c in parent["clarifications"] if c["id"] == frag), None)
        ant = (clar or {}).get("refers_to")
        for owner in ctx["inherited_extracts"]:
            owner_plan = next((p for p in plans if p["child_id"] == owner["from_node"]), None)
            rc = (owner_plan or {}).get("relation")
            asked_relation = owner_plan is not None and any(
                r_["id"] == owner_plan["anchor_id"] and r_["kind"] == "relationship" for r_ in parent["requirements"]
            )
            rec = {
                "id": f"{frag}#referent_relationship:{owner['from_node']}",
                "kind": "referent_relationship_carried",
                "text": f"the relationship {owner['from_node']} asks about the referent",
                "authority": APPROVED,
                "expression": "not_applicable",
                "required_in_child": "required",
            }
            if not (ant and rc and rc.get("parse_status") == "parsed"):
                if asked_relation or (ant and _unparsed_relationship_over(parent, plans, ant["span"])):
                    limits.append(LIMITS["referent_relationship_unparsed"])
                    results.append(_result(rec, "unverifiable"))
                continue
            slot = slot_of(rc, *ant["span"])
            if slot not in ("subject", "target"):
                continue
            other = "target" if slot == "subject" else "subject"
            need = {"the relation": rc["relation"]["text"], f"the {other}": rc[other]["text"]}
            refs = rc[other].get("references") or ([rc[other]["reference"]] if rc[other].get("reference") else [])
            for ref in refs:
                if ref and ref.get("status") == "clarified_by_user" and ref.get("antecedent"):
                    need[f"the words '{ref['word']}' points at"] = ref["antecedent"]["text"]
            missing = {k: missing_words(v, child_stems) for k, v in need.items()}
            missing = {k: v for k, v in missing.items() if v}
            if missing:
                flags.append(
                    {
                        "kind": "referent_relationship_incomplete",
                        "class": "review",
                        "words": [w for v in missing.values() for w in v],
                        "note": f"the referent ({ant['text']!r}) is defined by {owner['from_node']}'s relationship ({rc['subject']['text']!r} {rc['relation']['text']!r} {rc['target']['text']!r}); the wording lacks "
                        + "; ".join(f"{k}: {', '.join(v)}" for k, v in missing.items())
                        + ". It may now ask about a generic set. Context is carried WITHOUT restating the ancestor's own question",
                    }
                )
                results.append(_result(rec, "not_met", missing=missing))
            else:
                results.append(_result(rec, "met_lexically"))
                limits.append(LIMITS["referent_relationship"])
    review = {c["id"]: c["human_review"] for c in applicable if c.get("human_review")}
    for r_ in results:
        cid_ = r_["id"].split("#")[0]
        if (
            cid_ in review
            and r_["kind"] in ("paired_answer", "referent_relationship_carried")
            and r_["state"] != "not_applicable"
        ):
            r_["human_review_required"] = (
                True  # the researcher kept a human read of this relationship; no check replaces it
            )
            r_["decision"] = review[cid_].get("decision")
    return results, flags, list(dict.fromkeys(limits))
