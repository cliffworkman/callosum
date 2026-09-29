"""Span-linked user clarifications: an authorized human resolves a specific piece of ambiguous wording.

A clarification is INPUT, not inference. It names the exact words it clarifies (a span whose text the engine verifies),
says what they mean, and records who authorized it. The engine never judges whether the meaning is right; it applies it
consistently to every question whose words contain the clarified span and keeps every OTHER ambiguity open. Nothing is
resolved unless a clarification names it, and a clarification is always shown as the user's decision, never as an
interpretation the engine made.

Two kinds, told apart by whether ``reference_word`` is given:

* ``reference``: one reference word ("they", "its", "it") is settled. Overlapping ambiguities become
  ``resolved_by_user_clarification``.
* ``meaning``: a stretch of wording (an elliptical fragment, a phrase) is given the meaning the user intended. It resolves
  no ambiguity by itself; it is shown to every question that owns those words, and a fragment it covers becomes writable.
  ``adds`` (``manner`` / ``polarity``) says the relationship there ALSO asks how / whether although the source words do not:
  that part of the contract is recorded as coming from the clarification, never as source wording.

Optional links, both verified against the request text:

* ``refers_to``: the exact request words the clarified words POINT AT (an antecedent). This is what lets the engine record
  a dependency or a nesting between questions from an approved fact instead of a guess.
* ``pairs``: two or more exact spans whose answers must be reported together as pairs (each value with its counterpart).

File format (JSON): ``{"clarifications": [{"id", "span": [lo, hi], "phrase", "reference_word"?, "target_span"?, "means",
"authorized_by", "authorization"?, "authorized_at"?, "refers_to"?: {"span", "phrase"}, "pairs"?: [{"span", "phrase"}]}]}``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from experiments.ask_cli_revised.decompose import requirements as req


class ClarificationError(ValueError):
    pass


def load(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ClarificationError(f"clarification file unreadable: {exc}") from exc
    rows = data.get("clarifications") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ClarificationError("clarification file must be an object with a 'clarifications' list")
    return rows


def _exact(question: str, cid: str, item, what: str) -> dict:
    """A {span, phrase} pair whose phrase must equal the request text at the span."""
    span = item.get("span") if isinstance(item, dict) else None
    if not (
        isinstance(span, list)
        and len(span) == 2
        and all(isinstance(i, int) for i in span)
        and 0 <= span[0] < span[1] <= len(question)
    ):
        raise ClarificationError(f"{cid}: {what} needs a [lo, hi] span inside the request")
    if question[span[0] : span[1]] != item.get("phrase"):
        raise ClarificationError(
            f"{cid}: {what} phrase does not equal the request text at {span} ({question[span[0] : span[1]]!r})"
        )
    return {"span": span, "text": item["phrase"]}


def _validate(question: str, row: dict) -> dict:
    cid = row.get("id")
    if not isinstance(cid, str) or not cid.strip():
        raise ClarificationError("a clarification needs an id")
    whole = _exact(question, cid, row, "the clarified")
    span, phrase = whole["span"], whole["text"]
    if not isinstance(row.get("means"), str) or not row["means"].strip() or len(row["means"]) > 600:
        raise ClarificationError(f"{cid}: 'means' must be a nonempty string of at most 600 characters")
    adds = row.get("adds") or []
    if not (isinstance(adds, list) and set(adds) <= {"manner", "polarity"}):
        raise ClarificationError(f"{cid}: 'adds' may only list 'manner' and/or 'polarity'")
    if not isinstance(row.get("authorized_by"), str) or not row["authorized_by"].strip():
        raise ClarificationError(f"{cid}: authorized_by is required (a clarification is a human decision)")
    if row.get("reference_word"):
        kind = "reference"
        hits = list(
            re.finditer(r"(?<![A-Za-z0-9])" + re.escape(row["reference_word"]) + r"(?![A-Za-z0-9])", phrase, re.I)
        )
        if len(hits) != 1:
            raise ClarificationError(
                f"{cid}: reference_word {row['reference_word']!r} must occur exactly once in the phrase (found {len(hits)})"
            )
        target = [span[0] + hits[0].start(), span[0] + hits[0].end()]
    else:
        kind = "meaning"
        target = row.get("target_span") or span
        if not (isinstance(target, list) and len(target) == 2 and span[0] <= target[0] < target[1] <= span[1]):
            raise ClarificationError(f"{cid}: target_span must lie inside the span")
    refers_to = _exact(question, cid, row["refers_to"], "refers_to") if row.get("refers_to") else None
    pairs = [_exact(question, cid, p, "a pair member") for p in row.get("pairs") or []]
    if row.get("pairs") is not None and not 2 <= len(pairs) <= 6:
        raise ClarificationError(f"{cid}: pairs needs between two and six member spans")
    return {
        "id": cid,
        "kind": kind,
        "span": span,
        "phrase": phrase,
        "target_span": target,
        "target_text": question[target[0] : target[1]],
        "means": row["means"].strip(),
        "refers_to": refers_to,
        "pairs": pairs,
        "adds": sorted(set(adds)),
        "authorized_by": row["authorized_by"].strip(),
        "authorization": row.get("authorization"),
        "authorized_at": row.get("authorized_at"),
        # a row whose authorizer is marked PENDING is a proposal for the user to approve, never an approval
        "status": "pending_user_approval"
        if row["authorized_by"].strip().upper().startswith("PENDING")
        else "user_authorized",
    }


def apply(parent: dict, rows: list[dict] | None) -> list[dict]:
    """Validate and record the clarifications on the parent contract; mark exactly the ambiguities a reference names."""
    parent["clarifications"] = []
    seen: set[str] = set()
    for row in rows or []:
        clar = _validate(parent["original_question"], row)
        if clar["id"] in seen:
            raise ClarificationError(f"duplicate clarification id {clar['id']}")
        seen.add(clar["id"])
        parent["clarifications"].append(clar)
        if clar["kind"] != "reference":
            continue  # a meaning clarification resolves no ambiguity by itself
        lo, hi = clar["target_span"]
        for amb in parent["ambiguities"]:
            if amb["spans"] and max(lo, amb["spans"][0][0]) < min(hi, amb["spans"][0][1]):
                amb["status"] = "resolved_by_user_clarification"
                amb["clarification"] = clar["id"]
    req.derive(parent)
    return parent["clarifications"]


def pending(parent: dict) -> list[str]:
    """Ids of clarifications that are proposals awaiting the user's approval (they may not be used unless explicitly allowed)."""
    return [c["id"] for c in parent.get("clarifications", []) if c["status"] != "user_authorized"]


def covering(parent: dict, span: list[int]) -> dict | None:
    """The REFERENCE clarification whose target word contains ``span`` (a word the child is being asked to keep or resolve)."""
    for c in parent.get("clarifications", []):
        if c["kind"] == "reference" and c["target_span"][0] <= span[0] and span[1] <= c["target_span"][1]:
            return c
    return None


def meanings_touching(parent: dict, spans: list[list[int]]) -> list[dict]:
    """MEANING clarifications whose words overlap any of ``spans`` (they are shown to the question that owns those words)."""
    return [
        c
        for c in parent.get("clarifications", [])
        if c["kind"] == "meaning"
        and any(max(c["target_span"][0], s[0]) < min(c["target_span"][1], s[1]) for s in spans)
    ]


def fragment_clarification(parent: dict, spans: list[list[int]]) -> dict | None:
    """A meaning clarification that covers every letter and digit of ``spans``: the user has said what an otherwise
    unstated fragment asks, so the fragment may be written instead of left unresolved."""
    q = parent["original_question"]
    chars = {i for lo, hi in spans for i in range(lo, hi) if q[i].isalnum()}
    if not chars:
        return None
    for c in parent.get("clarifications", []):
        if c["kind"] == "meaning" and all(c["target_span"][0] <= i < c["target_span"][1] for i in chars):
            return c
    return None


# ---- annotations: additions to an approved clarification that never change or replace it ---------------------------------------------
#
# An annotation file sits BESIDE an approved clarification file and names clarifications by id; the approved rows are never
# edited. Two kinds of annotation exist:
#   * ``context_link``: the words that join the request's subject to the question. It must be a verbatim substring of the
#     clarification's approved ``means``, so it is the researcher's own wording, never a connection invented by the engine.
#   * ``brief``: a shorter statement of the approved meaning. It is a CONDENSATION written by someone other than the
#     researcher, so it carries provenance back to the clarification and is ``proposed`` until the researcher approves it.
#     A proposed brief is shown to a model only in a run explicitly marked as a what-if, and it never authorizes any wording.
BRIEF_MAX = 160
LINK_MAX = 60


def load_annotations(path: str | Path) -> list[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ClarificationError(f"annotation file unreadable: {exc}") from exc
    rows = data.get("annotations") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ClarificationError("annotation file must be an object with an 'annotations' list")
    return rows


def annotate(parent: dict, rows: list[dict] | None) -> None:
    by_id = {c["id"]: c for c in parent.get("clarifications", [])}
    for row in rows or []:
        cid = row.get("clarification")
        clar = by_id.get(cid)
        if clar is None:
            raise ClarificationError(f"annotation names an unknown clarification {cid!r}")
        link = row.get("context_link")
        if link is not None:
            if not isinstance(link, str) or not link.strip() or len(link) > LINK_MAX:
                raise ClarificationError(f"{cid}: context_link must be a short nonempty string")
            if link.lower() not in clar["means"].lower():
                raise ClarificationError(
                    f"{cid}: context_link {link!r} is not verbatim in the approved meaning; the engine may not invent a connection"
                )
            approved_by = str(row.get("context_link_approved_by") or "").strip()
            clar["context_link"] = {
                "text": link,
                "basis": "verbatim_in_approved_means",
                # the words are the researcher's own, but that they may JOIN the subject to a question is the engine author's
                # record until the researcher confirms it: a child that relies on them is reported as pending, never as clean
                "authority": req.APPROVED if approved_by else req.PENDING,
                "approved_by": approved_by or None,
                "decision": row.get("context_link_decision"),
            }
        brief = row.get("brief")
        if brief is not None:
            text = brief.get("text") if isinstance(brief, dict) else None
            if not isinstance(text, str) or not text.strip() or len(text) > BRIEF_MAX:
                raise ClarificationError(
                    f"{cid}: brief.text must be a nonempty string of at most {BRIEF_MAX} characters"
                )
            if brief.get("condensed_from") != cid:
                raise ClarificationError(f"{cid}: a brief must name the clarification it condenses (condensed_from)")
            status = brief.get("status", "proposed")
            if status not in ("proposed", "approved"):
                raise ClarificationError(f"{cid}: brief.status must be 'proposed' or 'approved'")
            if status == "approved" and not str(brief.get("approved_by") or "").strip():
                raise ClarificationError(
                    f"{cid}: an approved brief needs approved_by (only the researcher can approve wording)"
                )
            clar["brief"] = {
                "text": text.strip(),
                "status": status,
                "condensed_from": cid,
                "authored_by": brief.get("authored_by", "unknown"),
                "approved_by": brief.get("approved_by"),
                "authorizes_wording": False,
            }
        review = row.get("human_review")
        if review is not None:
            if not (isinstance(review, dict) and str(review.get("approved_by") or "").strip()):
                raise ClarificationError(
                    f"{cid}: human_review records a researcher decision (approved_by is mandatory)"
                )
            clar["human_review"] = {
                "of": list(review.get("of") or []),
                "decision": review.get("decision"),
                "approved_by": review["approved_by"],
            }
        rows_req = row.get("requirements")
        if rows_req is not None:
            try:
                new = req.validate_annotated(clar, rows_req)
            except ValueError as exc:
                raise ClarificationError(str(exc)) from exc
            known = {r["id"] for r in clar.setdefault("annotated_requirements", [])}
            dup = [r["id"] for r in new if r["id"] in known]
            if dup:
                raise ClarificationError(f"{cid}: requirement ids already recorded: {dup}")
            clar["annotated_requirements"].extend(new)
        amendments = row.get("amendments")
        if amendments is not None:
            known_req = {r["id"]: r for r in clar.get("annotated_requirements", [])}
            for a in amendments:
                target = known_req.get(a.get("amends"))
                if target is None:
                    raise ClarificationError(f"{cid}: an amendment names an unknown requirement {a.get('amends')!r}")
                approved_by = str(a.get("approved_by") or "").strip()
                if not approved_by:
                    raise ClarificationError(
                        f"{cid}: an amendment records a researcher decision (approved_by is mandatory)"
                    )
                if a.get("effect") != "optional_scope_expansion" or target["kind"] != "scope_item":
                    raise ClarificationError(f"{cid}: the only amendment is 'optional_scope_expansion' of a scope_item")
                phrases = [str(x).lower() for x in a.get("optional_phrases") or []]
                if not phrases or any(x not in target["phrases"] for x in phrases):
                    raise ClarificationError(f"{cid}: optional_phrases must be phrases of the amended scope_item")
                clar.setdefault("amendments", []).append(
                    {
                        "amends": target["id"],
                        "decision": a.get("decision"),
                        "effect": a["effect"],
                        "optional_phrases": phrases,
                        "approved_by": approved_by,
                        "note": a.get("note"),
                    }
                )
    req.derive(parent)


def load_decisions(path: str | Path) -> list[dict]:
    """The researcher's recorded DECISIONS (id, the decision in words, who authorized it, and the machine-readable effect it has on
    the engine's data). They are provenance: the engine data they change lives in the annotation rows of the same file."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ClarificationError(f"decisions file unreadable: {exc}") from exc
    rows = data.get("decisions") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ClarificationError("a decisions file must be an object with a nonempty 'decisions' list")
    out, seen = [], set()
    for raw in rows:
        row = {
            **raw,
            "authorized_by": raw.get("authorized_by") or data.get("authorized_by"),
        }  # the file's authorizer by default
        for key in ("id", "decision", "authorized_by"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ClarificationError(f"a decision needs a nonempty {key}")
        if row["id"] in seen:
            raise ClarificationError(f"duplicate decision id {row['id']}")
        seen.add(row["id"])
        out.append(
            {
                "id": row["id"],
                "decision": row["decision"],
                "authorized_by": row["authorized_by"],
                "authorization": row.get("authorization") or data.get("authorization"),
                "recorded": row.get("recorded") or data.get("recorded"),
                "applies_to": row.get("applies_to"),
                "effect": row.get("effect") or {},
            }
        )
    return out


def proposed_briefs(parent: dict) -> list[str]:
    """Ids of clarifications whose brief is still a proposal (usable only in a run marked as a what-if)."""
    return [c["id"] for c in parent.get("clarifications", []) if c.get("brief") and c["brief"]["status"] != "approved"]


def context_link(parent: dict, spans: list[list[int]]) -> dict | None:
    """The researcher-approved words that join the subject to a question whose words overlap ``spans`` (if any)."""
    for c in parent.get("clarifications", []):
        if c.get("context_link") and any(
            max(c["target_span"][0], s[0]) < min(c["target_span"][1], s[1]) for s in spans
        ):
            return {"clarification": c["id"], **c["context_link"]}
    return None
