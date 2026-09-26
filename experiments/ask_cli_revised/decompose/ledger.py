"""Source-edit ledger: an AUDIT of how a child question differs from the request's own words.

Decomposition is a minimal source transformation: copy the researcher's words, leave out the other threads, keep shared
wording, and restore only the context a question needs to stand alone. This module reads a written child back against the
source spans the engine recorded for it and lists, compactly:

* ``copied`` / ``context_carried``: wording found in the child's RECORDED spans (its owned and shared words, the background
  referent, an inherited antecedent), with those exact spans;
* ``sibling_removed``: words the plan gave to other questions, left out of this one (from the plan, not from the text);
* ``antecedent_resolved`` / ``clarification_supplied``: wording that comes from an identified approved clarification;
* ``grammatical``: adjustments that cannot change what is asked (capitals, an article, do/is support, an inflection);
* ``request_form_change``: the researcher's request FORM changed (an imperative made a question, a "whether" clause recast as
  a yes/no question, a final "?" added to a request that is not a question, an operation word dropped or added). Reported for
  review, never treated as harmless;
* ``operation_change``: a protected question word or qualifier (whether, how, which, what, any, not, effective...) dropped
  or added;
* ``relation_word_added`` / ``unsupported``: wording no recorded span or clarification supports;
* ``authorized_expression``: an exact run of words a clarification's requirement record permits, used in qualifier position (never
  by exempting a word class: ``where`` stays a protected question word everywhere else). An expression or joining words whose
  permission is only ENGINE-RECORDED (the researcher has not confirmed it) makes the child ``pending_researcher_confirmation``;
* ``detail_pending``: words of an approved meaning whose treatment (required / permitted / background) nobody has decided;
* ``connective_unestablished``: a relative "that" or an isolated connective whose neighbouring pieces are not related by the same
  stretch of the source, a recorded relationship or an approved clarification. Adjacency in the source alone never licenses one.

It is an AUDIT, not proof. Token matching is post hoc and can find one word at several places, so attribution is only ever
to the child's recorded spans, and a match that could belong to more than one piece, or is a single common word, is marked
``uncertain`` with its alternatives. A clean ledger means no source-edit problem was DETECTED; it never certifies
provenance or semantic fidelity. Every table below is generic English, not tied to any request.
"""

from __future__ import annotations

import re

from experiments.ask_cli_revised.decompose import lexical as lx
from experiments.ask_cli_revised.decompose import requirements as req
from experiments.ask_cli_revised.decompose.parent import CUES

AUDIT_NOTE = (
    "an audit of DETECTED source-edit problems from post-hoc token matching against the recorded spans; a clean ledger "
    "is not proof of provenance and does not certify semantic fidelity"
)
_WORD = re.compile(r"[A-Za-z0-9]+")
Tok = tuple[str, int, int]

# Harmless when ADDED: they cannot change what is asked or what relates to what.
HARMLESS = {
    **dict.fromkeys(("a", "an", "the"), "article"),
    **dict.fromkeys("do does did is are was were be been being has have had".split(), "auxiliary"),
    "there": "existential",
    "please": "politeness",
    "s": "possessive",  # the s of 's
}
# The researcher's operation words ("return", "list", "describe"...): they set the request FORM. Dropping or adding one is a
# form change to review; a stem-equal swap (measures -> measured) is only an inflection.
FORM_WORDS = frozenset(w for w in CUES["operation"] if " " not in w)
# Protected: question words and qualifiers that ARE what the researcher asked. Dropping or adding one changes it.
NEGATION = frozenset("not no never none nor without cannot except".split())
OPERATORS = (
    frozenset(w for kind in ("polarity", "manner", "qualifier") for w in CUES[kind] if " " not in w)
    | NEGATION
    | frozenset(
        "whether if how what which who whom whose when where why some both either neither kind kinds type types sort sorts variety".split()
    )
) - FORM_WORDS
QUALIFIER_WORDS = frozenset(w for w in CUES["qualifier"] if " " not in w)
INFLECTABLE = FORM_WORDS | QUALIFIER_WORDS  # a stem-equal swap of one of these is an inflection, never a change
# Relation-bearing when ADDED: a preposition, conjunction or modal can introduce or change a relationship.
RELATION_WORDS = {
    **dict.fromkeys(
        (
            "in on at by for of to with from about into onto within over under between among through during after "
            "before against toward via per as than"
        ).split(),
        "preposition",
    ),
    **dict.fromkeys("and or but so then that".split(), "conjunction"),
    **dict.fromkeys("can could may might must shall should will would".split(), "modal"),
}
ADDS_WORDS = {"manner": {"how"}, "polarity": {"whether", "if"}}
# findings that are a GAP (the question lacks something the request has) rather than a DEPARTURE (the writer changed something)
GAP_KINDS = frozenset({"context_missing", "context_link_unstated"})
WH_WORDS = frozenset("what which who whom whose when where why".split())
IMPERATIVE_WORDS = FORM_WORDS
POLAR_START = frozenset("do does did is are can could was were has have will would should".split())
QUESTION_START = WH_WORDS | {"how"} | POLAR_START
RUN_LIMIT = (
    6  # this many consecutive words copied from a clarification's explanation is pasted prose, not a needed word
)


_LEAD_IN = re.compile(r"\s*(?:in|for|about|regarding|given|within|on|as|with)\b[^,]*,\s*(?P<rest>.+)", re.I | re.S)


def request_form(text: str) -> str:
    """imperative | question | whether_clause | fragment, read from the first word after any please/and/but and after a
    leading context clause ("In the context of X, ...")."""
    lead = _LEAD_IN.match(text)
    if lead:
        rest = request_form(lead.group("rest"))
        if rest != "fragment":
            return rest
    toks = [t for t, _, _ in _tokens(text)]
    while toks[:1] and toks[0] in ("please", "and", "but", "then", "also", "or"):
        toks = toks[1:]
    if not toks:
        return "fragment"
    if toks[0] in FORM_WORDS:
        return "imperative"
    if toks[0] in QUESTION_START:
        return "question"
    return "whether_clause" if toks[0] in ("whether", "if") else "fragment"


def _tokens(text: str, base: int = 0) -> list[Tok]:
    return [(m.group(0).lower(), base + m.start(), base + m.end()) for m in _WORD.finditer(text)]


def _inside(lo: int, hi: int, spans) -> bool:
    return any(s[0] <= lo and hi <= s[1] for s in spans)


def _ranges(toks: list[Tok]) -> list[list[int]]:
    """Source character ranges of consecutive tokens (a seam between two spliced spans starts a new range)."""
    out: list[list[int]] = []
    for _, lo, hi in toks:
        if out and lo - out[-1][1] <= 2:
            out[-1][1] = hi
        else:
            out.append([lo, hi])
    return out


def _subseq(hay: list[str], needle: list[str]) -> bool:
    return any(hay[i : i + len(needle)] == needle for i in range(len(hay) - len(needle) + 1))


def _pieces(parent: dict, plan: dict, ctx: dict, by_id: dict) -> list[dict]:
    """The wording the child is ENTITLED to use, each piece with its exact recorded spans. Nothing else is authorized."""
    q = parent["original_question"]
    owned = [tuple(s) for i in plan["owns"] for s in by_id[i]["spans"]]
    rc = plan.get("relation")
    if rc and rc.get("parse_status") == "parsed":
        owned += [tuple(s) for k in ("subject", "relation", "target", "answer_form") for s in rc[k]["spans"]]
    shared = [tuple(s) for i in plan["carries_shared"] for s in by_id[i]["spans"]]
    pieces: list[dict] = []
    for e in ctx["extract"]:
        toks: list[Tok] = []
        for lo, hi in e.get("spans") or [e["span"]]:
            toks += _tokens(q[lo:hi], lo)
        roles = [
            "owned" if _inside(lo, hi, owned) else "shared" if _inside(lo, hi, shared) else "scaffold"
            for _, lo, hi in toks
        ]
        pieces.append(
            {
                "kind": "extract",
                "tokens": toks,
                "roles": roles,
                "label": "extract",
                "priority": 0,
                "spliced": bool(e.get("spliced")),
                "text": e["text"],
            }
        )
    seen: dict[tuple, dict] = {}

    def add(kind: str, spans: list, label: str, clarification: str | None = None, priority: int = 1) -> None:
        key = tuple(tuple(s) for s in spans)
        if key in seen:
            seen[key]["clarification"] = seen[key]["clarification"] or clarification
            return
        toks: list[Tok] = []
        for lo, hi in spans:
            toks += _tokens(q[lo:hi], lo)
        piece = {
            "kind": kind,
            "tokens": toks,
            "roles": [kind] * len(toks),
            "label": label,
            "clarification": clarification,
            "priority": priority,
        }
        seen[key] = piece
        pieces.append(piece)

    for ref in ctx["subject"]:
        add("background", ref["spans"], f"background referent {ref['id']}", priority=2)
    for u in ctx["unresolved"]:
        for cand in u["candidates"]:
            if cand["id"] in by_id and by_id[cand["id"]]["spans"]:
                add(
                    "candidate",
                    by_id[cand["id"]]["spans"],
                    f'candidate reading of "{u["word"]}" (not approved)',
                    priority=3,
                )
    for owner in ctx.get("inherited_extracts", []):
        # the words of the question this fragment continues, minus the operators that made THAT question a request: the
        # fragment may name what it is about, never ask the owner's question again
        toks: list[Tok] = []
        for e in owner["entries"]:
            for lo, hi in e.get("spans") or [e["span"]]:
                toks += [
                    tk
                    for tk in _tokens(q[lo:hi], lo)
                    if tk[0] not in OPERATORS
                    and tk[0] not in FORM_WORDS
                    and tk[0] not in WH_WORDS
                    and tk[0] not in POLAR_START
                ]
        if toks:
            pieces.append(
                {
                    "kind": "inherited",
                    "tokens": toks,
                    "roles": ["inherited"] * len(toks),
                    "label": f"source words of {owner['from_node']} (context only)",
                    "clarification": None,
                    "priority": 1,
                }
            )
    for inh in (plan.get("node") or {}).get("inherited", []):
        role = "background" if inh["role"] == "background_referent" else "inherited"
        add(
            role, inh["spans"], f"{inh['role']} {inh['obligation']} (from {inh['from_node']})", inh.get("clarification")
        )
    return pieces


def _applicable(parent: dict, plan: dict, by_id: dict) -> list[dict]:
    """Clarifications that bear on this child: their words overlap what it owns, or it is the fragment one clarifies."""
    spans = [tuple(s) for i in [*plan["owns"], *plan["carries_shared"]] for s in by_id[i]["spans"]]
    out = []
    for c in parent.get("clarifications", []):
        lo, hi = c["target_span"]
        if c["id"] == plan.get("clarified_fragment") or any(max(lo, s[0]) < min(hi, s[1]) for s in spans):
            out.append(c)
    return out


CONNECTIVES = frozenset(RELATION_WORDS) - {"that"}
_ADJACENT_SLOTS = frozenset({("subject", "relation"), ("relation", "target")})


def _contracts(plan: dict, plans: list[dict], ctx: dict) -> list[dict]:
    """The PARSED relationships that legitimately bear on this child: its own, and the owner's of a question it continues."""
    out = []
    rc = plan.get("relation")
    if rc and rc.get("parse_status") == "parsed":
        out.append(rc)
    for owner in ctx.get("inherited_extracts", []):
        op = next((p for p in plans if p["child_id"] == owner["from_node"]), None)
        orc = (op or {}).get("relation")
        if orc and orc.get("parse_status") == "parsed":
            out.append(orc)
    return out


def _support(left: Tok, right: Tok, contracts: list[dict], applicable: list[dict]) -> str | None:
    """Why two neighbouring source words are related by MORE than sitting near each other: a recorded relationship that puts them
    in adjacent slots, or an approved clarification whose words cover both. None when that cannot be established."""
    for rc in contracts:
        pair = (req.slot_of(rc, left[1], left[2]), req.slot_of(rc, right[1], right[2]))
        if pair in _ADJACENT_SLOTS:
            return f"recorded relationship {rc['obligation_id']} ({pair[0]} -> {pair[1]})"
    for c in applicable:
        lo, hi = c["span"]
        if lo <= left[1] and right[2] <= hi:
            return f"approved clarification {c['id']}"
    return None


def _find_tolerant(words: list[str], needle: list[str]) -> list[tuple[int, int]]:
    """Runs of ``words`` equal to ``needle`` word for word, an inflection of a joining word ("measure" ~ "measured") allowed."""
    n = len(needle)
    return [
        (i, i + n)
        for i in range(len(words) - n + 1)
        if n
        and all(a == b or lx.stems_match(lx.stem(a), lx.stem(b)) for a, b in zip(words[i : i + n], needle, strict=True))
    ]


def _auth_runs(words: list[str], applicable: list[dict], pieces: list[dict]) -> list[dict]:
    """Exact contiguous runs of the child's words that an applicable clarification authorizes, each by ROLE: the approved joining
    words (link), a permitted expression (only in qualifier position), or the words a reference points at (antecedent). A clarification's
    other words authorize nothing. A link/expression that is also a stretch of the researcher's own sentence is attributed there."""
    piece_words = [[t for t, _, _ in p["tokens"]] for p in pieces]
    runs: list[dict] = []
    for c in applicable:
        link = c.get("context_link")
        cands = []
        if link:
            cands.append(("link", link["text"], link.get("authority"), None, True))
        for r in c.get("requirements", []):
            if r["kind"] == "qualifier_expression":
                cands.append(("expression", r["text"], r["authority"], r, False))
            if r["kind"] == "scope_item":  # the researcher's approved words for a scope they decided must be preserved
                cands.extend(("scope", phrase, r["authority"], r, False) for phrase in r["phrases"])
        for role, text, authority, rec, _ in cands:
            found = _find_tolerant(words, req.words(text)) if role == "link" else req.find_runs(words, req.words(text))
            for lo, hi in found:
                valid = True
                if (
                    role == "expression"
                ):  # qualifier position: it qualifies a content word to its left, it does not open the request
                    valid = lo > 0 and lx.is_content_token(words[lo - 1]) and words[lo - 1] not in OPERATORS
                sourced = any(_subseq(pw, words[lo:hi]) for pw in piece_words)
                runs.append(
                    {
                        "role": role,
                        "clarification": c["id"],
                        "authority": authority,
                        "lo": lo,
                        "hi": hi,
                        "text": text,
                        "requirement": rec["id"] if rec else None,
                        "valid": valid,
                        "masked": valid and not sourced,
                    }
                )
        for r in c.get("requirements", []):
            if r["kind"] != "operation_added":
                continue
            for i, w in enumerate(
                words
            ):  # the cue word a clarification adds, with the "and" that joins it to a source cue word
                if w != r["text"]:
                    continue
                joined = i >= 2 and words[i - 1] in ("and", "or") and words[i - 2] in ("whether", "if", "how")
                lo = i - 1 if joined else i
                runs.append(
                    {
                        "role": "adds",
                        "clarification": c["id"],
                        "authority": req.APPROVED,
                        "lo": lo,
                        "hi": i + 1,
                        "text": " ".join(words[lo : i + 1]),
                        "requirement": r["id"],
                        "valid": True,
                        "masked": not any(_subseq(pw, words[lo : i + 1]) for pw in piece_words),
                    }
                )
        ant = c.get("refers_to") if c["kind"] == "reference" else None
        if ant:
            for lo, hi in req.find_runs(words, req.words(ant["text"])):
                runs.append(
                    {
                        "role": "antecedent",
                        "clarification": c["id"],
                        "authority": req.APPROVED,
                        "lo": lo,
                        "hi": hi,
                        "text": ant["text"],
                        "requirement": None,
                        "valid": True,
                        "masked": False,
                    }
                )
    return runs


def _tile(ct: list[Tok], pieces: list[dict], masked: frozenset | set = frozenset()):
    """Greedy longest-run tiling of the child's tokens onto the authorized pieces (handles moved phrases). ``masked`` child tokens
    (an authorized clarification run) are not tiled: their attribution is the clarification's, not a source piece's."""
    words = [t for t, _, _ in ct]
    used_c: list[int | None] = [-1 if i in masked else None for i in range(len(ct))]
    used_p = [[False] * len(p["tokens"]) for p in pieces]
    segments: list[dict] = []
    while True:
        best = None
        for pi, p in enumerate(pieces):
            pt = [t for t, _, _ in p["tokens"]]
            for ci in range(len(ct)):
                if used_c[ci] is not None:
                    continue
                for pj in range(len(pt)):
                    if used_p[pi][pj] or words[ci] != pt[pj]:
                        continue
                    n = 1
                    while (
                        ci + n < len(ct)
                        and pj + n < len(pt)
                        and used_c[ci + n] is None
                        and not used_p[pi][pj + n]
                        and words[ci + n] == pt[pj + n]
                    ):
                        n += 1
                    key = (n, -p["priority"], -ci)
                    if best is None or key > best[0]:
                        best = (key, ci, pi, pj, n)
        if best is None:
            return segments, used_c, used_p
        _, ci, pi, pj, n = best
        for k in range(n):
            used_c[ci + k] = len(segments)
            used_p[pi][pj + k] = True
        run = words[ci : ci + n]
        alternatives = [
            {"piece": o["label"], "spans": _ranges(o["tokens"])}
            for oi, o in enumerate(pieces)
            if oi != pi and _subseq([t for t, _, _ in o["tokens"]], run)
        ]
        segments.append(
            {
                "c0": ci,
                "c1": ci + n,
                "piece": pi,
                "p0": pj,
                "alternatives": alternatives,
                "uncertain": bool(alternatives) or (n == 1 and run[0] in lx.FUNCTION_WORDS),
            }
        )


def build(parent: dict, child: dict, plan: dict, plans: list[dict], ctx: dict, by_id: dict) -> dict:
    q, text = parent["original_question"], child["question"]
    ct = _tokens(text)
    words = [t for t, _, _ in ct]
    pieces = _pieces(parent, plan, ctx, by_id)
    applicable = _applicable(parent, plan, by_id)
    runs = _auth_runs(words, applicable, pieces)
    masked = {i for r in runs if r["masked"] for i in range(r["lo"], r["hi"])}
    segments, used_c, used_p = _tile(ct, pieces, masked)
    run_at = {i: r for r in runs if r["masked"] or r["role"] == "antecedent" for i in range(r["lo"], r["hi"])}
    authorized_idx = set(run_at)
    adds_words: dict[str, list[str]] = {}
    detail_words: dict[str, list[tuple[str, dict]]] = {}
    explained: dict[
        str, set
    ] = {}  # words that occur in a clarification's EXPLANATION: used for notes only, never as authorization
    for c in applicable:
        for a in c.get("adds", []):
            for w in ADDS_WORDS[a]:
                adds_words.setdefault(w, []).append(c["id"])
        for r in c.get("requirements", []):
            if r["kind"] == "detail":
                for w in r["evidence_words"]:
                    detail_words.setdefault(w, []).append((c["id"], r))
        for w, _, _ in _tokens(c["means"]):
            explained.setdefault(w, set()).add(c["id"])
    contracts = _contracts(plan, plans, ctx)
    detail_used: dict[str, dict] = {}

    def source_token(k: int) -> Tok | None:
        sid_ = used_c[k]
        seg_ = segments[sid_] if sid_ is not None and sid_ >= 0 else None
        return pieces[seg_["piece"]]["tokens"][seg_["p0"] + (k - seg_["c0"])] if seg_ else None

    def tiled(k: int) -> bool:
        return used_c[k] is not None and used_c[k] >= 0

    def neighbour(k: int, step: int) -> int | None:
        k += step
        while 0 <= k < len(ct) and words[k] in HARMLESS and not tiled(k):
            k += step
        return k if 0 <= k < len(ct) and tiled(k) else None

    def relation_between(left_idx: int | None, right_idx: int | None) -> dict | None:
        """Is the relation between two neighbouring tiled words SUPPORTED (same stretch of the source, a recorded relationship,
        or an approved clarification)? None = not evaluable (an untiled neighbour): the ordinary chain judges the word."""
        if left_idx is None or right_idx is None:
            return None
        lt, rt = source_token(left_idx), source_token(right_idx)
        sl, sr = segments[used_c[left_idx]], segments[used_c[right_idx]]
        if (
            sl["piece"] == sr["piece"]
            and pieces[sl["piece"]]["kind"] in ("extract", "inherited")
            and rt[1] >= lt[2]
            and not any(lx.is_content_token(w) for w, _, _ in _tokens(q[lt[2] : rt[1]]))
        ):
            return {"basis": "the same stretch of the source"}
        return {"basis": _support(lt, rt, contracts, applicable)}

    sibling_words: dict[str, set] = {}
    for p in plans:
        if p["child_id"] != child["child_id"]:
            for i in p["owns"]:
                for lo, hi in by_id[i]["spans"]:
                    for t, _, _ in _tokens(q[lo:hi], lo):
                        sibling_words.setdefault(t, set()).add(p["child_id"])
    own_stems = {lx.stem(t) for p in pieces for t, _, _ in p["tokens"]}
    extract_tokens = [
        (t, r, used_p[pi][k])
        for pi, p in enumerate(pieces)
        if p["kind"] == "extract"
        for k, ((t, _, _), r) in enumerate(zip(p["tokens"], p["roles"], strict=False))
    ]
    src_text = " ".join(e["text"] for e in ctx["extract"])
    src_form, child_form = request_form(src_text), request_form(text)
    form_reasons: list[tuple[str, str]] = []  # (key, note): why the request FORM changed
    # a "whether" the researcher wrote, stated as a polar question ("Does ...", "..., and if so, ..."): the operation is kept,
    # the FORM is not, so it is reported (never treated as harmless)
    if_so = next((k for k in range(len(words) - 1) if words[k] == "if" and words[k + 1] == "so"), None)
    conversion = (
        any(t == "whether" for t, _, _ in extract_tokens)
        and "whether" not in words
        and bool((words and words[0] in POLAR_START) or if_so is not None)
    )
    conv_idx = set()
    if conversion and if_so is not None:
        conv_idx = {if_so, if_so + 1} | ({if_so - 1} if if_so and words[if_so - 1] in ("and", "but") else set())
    dropped = list(
        dict.fromkeys(
            t
            for t, _, used in extract_tokens
            if not used and (t in OPERATORS or t in FORM_WORDS) and not (conversion and t == "whether")
        )
    )
    swapped: set[str] = set()  # dropped words the child kept in another inflection (measures -> measured)
    ops: list[dict] = []
    flags: list[dict] = []
    ci = 0
    while ci < len(ct):
        sid = used_c[ci]
        if sid is not None and sid >= 0:
            seg = segments[sid]
            piece = pieces[seg["piece"]]
            n = seg["c1"] - seg["c0"]
            toks = piece["tokens"][seg["p0"] : seg["p0"] + n]
            op = {
                "op": {"extract": "copied", "candidate": "candidate_reading_adopted"}.get(
                    piece["kind"], "context_carried"
                ),
                "text": text[ct[seg["c0"]][1] : ct[seg["c1"] - 1][2]],
                "source_spans": _ranges(toks),
                "roles": sorted(set(piece["roles"][seg["p0"] : seg["p0"] + n])),
                "attribution": "uncertain" if seg["uncertain"] else "recorded_span",
                "_seg": sid,
            }
            if piece["kind"] != "extract":
                op["source"] = piece["label"]
                if piece.get("clarification"):
                    op["clarification"] = piece["clarification"]
            if seg["alternatives"]:
                op["alternatives"] = seg["alternatives"]
            seg_words = words[seg["c0"] : seg["c1"]]
            if (
                n <= 2
                and all(w in CONNECTIVES or w in HARMLESS for w in seg_words)
                and any(w in CONNECTIVES for w in seg_words)
            ):
                # an isolated connective borrowed from somewhere in the source: it must sit between two words the source (or a
                # recorded relationship, or an approved clarification) actually relates; adjacency alone is not a relationship
                rel = relation_between(neighbour(seg["c0"], -1), neighbour(seg["c1"] - 1, 1))
                if rel is not None and not rel["basis"]:
                    op["op"], op["relationship"], op["attribution"] = (
                        "connective_unestablished",
                        "unestablished",
                        "uncertain",
                    )
                    flags.append(
                        {
                            "kind": "connective_relationship_unestablished",
                            "class": "review",
                            "words": seg_words,
                            "note": f'"{" ".join(seg_words)}" comes from another place in the source and now joins two pieces; no same-stretch source wording, recorded relationship or approved clarification relates them, so the new relationship is for review',
                        }
                    )
            ops.append(op)
            ci = seg["c1"]
            continue
        t, lo, hi = ct[ci]
        item = {"text": text[lo:hi], "child_span": [lo, hi]}
        run = run_at.get(ci)
        twin = next(
            (d for d in dropped if d not in swapped and d in INFLECTABLE and t != d and lx.stem(t) == lx.stem(d)), None
        )
        if ci in conv_idx:
            ops.append({**item, "op": "request_form_change", "kind": "whether_recast_as_polar_question"})
        elif (
            run is not None
        ):  # words an applicable clarification authorizes BY ROLE (joining words, permitted expression, antecedent)
            ops.append(
                {
                    **item,
                    "op": "authorized_expression" if run["role"] == "expression" else "clarification_supplied",
                    "clarification": [run["clarification"]] if run["role"] == "adds" else run["clarification"],
                    "role": run["role"],
                    "authority": run["authority"],
                }
            )
        elif t in HARMLESS:  # never credited to a clarification whose prose happens to contain the same word
            ops.append({**item, "op": "grammatical", "kind": HARMLESS[t]})
        elif t == "that" and (rel := relation_between(neighbour(ci, -1), neighbour(ci, 1))) is not None:
            if rel[
                "basis"
            ]:  # a relative "that" only makes explicit a relation the source or a recorded relationship already has
                ops.append(
                    {**item, "op": "grammatical", "kind": "relative_pronoun", "relationship_basis": rel["basis"]}
                )
            else:
                ops.append({**item, "op": "connective_unestablished", "kind": "relative_pronoun"})
                flags.append(
                    {
                        "kind": "connective_relationship_unestablished",
                        "class": "review",
                        "words": [t],
                        "note": 'the relative "that" joins two pieces of source wording; no same-stretch source wording, recorded relationship or approved clarification says they are related, so the relationship is for review (the grammar is not rejected)',
                    }
                )
        elif twin:
            swapped.add(twin)
            ops.append({**item, "op": "grammatical", "kind": "inflection", "of": twin})
        elif t in adds_words:
            ops.append(
                {**item, "op": "clarification_supplied", "clarification": sorted(set(adds_words[t])), "role": "adds"}
            )
        elif t in detail_words:
            ops.append({**item, "op": "detail_pending", "clarification": sorted({c for c, _ in detail_words[t]})})
            for cid_, rec_ in detail_words[t]:
                detail_used.setdefault(rec_["id"], {"rec": rec_, "clarification": cid_, "words": []})["words"].append(t)
        elif t in OPERATORS:
            ops.append({**item, "op": "operation_change", "kind": "operator_added", "negation": t in NEGATION})
            flags.append(
                {
                    "kind": "operator_added",
                    "class": "conflict",
                    "words": [t],
                    "note": f'the wording adds "{t}", a word that changes the operation requested',
                }
            )
        elif t in FORM_WORDS:
            ops.append({**item, "op": "request_form_change", "kind": "operation_word_added"})
            form_reasons.append((f"added:{t}", f'the operation word "{t}" was added'))
        elif t in lx.DEIXIS_WORDS:
            ops.append({**item, "op": "unsupported", "kind": "reference_word_added"})
            flags.append(
                {
                    "kind": "unsupported_substitution",
                    "class": "review",
                    "words": [t],
                    "note": f'the wording adds the reference word "{t}", which the source does not use here',
                }
            )
        elif t in RELATION_WORDS:
            ops.append({**item, "op": "relation_word_added", "kind": RELATION_WORDS[t]})
            flags.append(
                {
                    "kind": "relation_word_added",
                    "class": "review",
                    "words": [t],
                    "note": f'the wording adds the {RELATION_WORDS[t]} "{t}", which can introduce or change a relationship; no recorded span or clarification supplies it',
                }
            )
        elif t in sibling_words:
            ops.append(
                {**item, "op": "unsupported", "kind": "borrowed_from_other_thread", "nodes": sorted(sibling_words[t])}
            )
            flags.append(
                {
                    "kind": "borrowed_from_other_thread",
                    "class": "review",
                    "words": [t],
                    "note": f'"{t}" belongs to another question ({", ".join(sorted(sibling_words[t]))})',
                }
            )
        elif lx.stem(t) in own_stems:
            ops.append({**item, "op": "grammatical", "kind": "inflection", "attribution": "uncertain"})
        elif t in lx.FUNCTION_WORDS:
            ops.append({**item, "op": "additional_scaffolding"})
        else:
            ops.append({**item, "op": "unsupported", "kind": "explanation_word" if t in explained else "content_word"})
            flags.append(
                {
                    "kind": "unsupported_substitution",
                    "class": "review",
                    "words": [t],
                    "note": f'"{t}" is in no recorded span or clarification'
                    if t not in explained
                    else f'"{t}" appears only in the explanation of {", ".join(sorted(explained[t]))}; a clarification\'s explanation does not authorize wording',
                }
            )
        if t in explained and "role" not in ops[-1]:
            ops[-1]["in_explanation_of"] = sorted(explained[t])  # counted toward pasted prose; never an authorization
        ci += 1
    if conversion:
        ops.append({"op": "request_form_change", "kind": "whether_recast_as_polar_question", "text": ""})
        form_reasons.append(("whether_recast", 'the researcher\'s "whether" clause was recast as a yes/no question'))
    # protected words the researcher wrote that the child no longer carries
    for t in dropped:
        if t in swapped:
            continue
        if t in FORM_WORDS:
            ops.append({"op": "request_form_change", "kind": "operation_word_dropped", "text": t})
            form_reasons.append((f"dropped:{t}", f'the researcher\'s operation word "{t}" was dropped'))
            continue
        ops.append({"op": "operation_change", "kind": "operator_dropped", "text": t, "negation": t in NEGATION})
        flags.append(
            {
                "kind": "operator_dropped",
                "class": "conflict",
                "words": [t],
                "note": f'the wording drops "{t}", a word of the operation the researcher requested',
            }
        )
    # an imperative recast as a wh-question ("please return X" -> "What X ...?"): the new question word is part of that FORM
    # change, not a separate conflict, provided nothing else the researcher asked for was dropped
    wh_added = [
        f for f in flags if f["kind"] == "operator_added" and f["words"][0] in WH_WORDS and words[:1] == f["words"]
    ]
    if wh_added and src_form == "imperative" and not any(f["kind"] == "operator_dropped" for f in flags):
        flags[:] = [f for f in flags if f not in wh_added]
        for o in ops:
            if o["op"] == "operation_change" and o["text"].lower() == wh_added[0]["words"][0]:
                o["op"], o["kind"] = "request_form_change", "imperative_recast_as_question"
        form_reasons.append(("imperative_to_question", "an imperative request was rewritten as a question"))
    elif (
        src_form == "imperative"
        and child_form != "imperative"
        and not any(k.startswith("dropped:") for k, _ in form_reasons)
    ):
        form_reasons.append(("imperative_changed", f"an imperative request became a {child_form.replace('_', ' ')}"))
    elif src_form == "question" and child_form != "question":
        form_reasons.append(("question_changed", f"a question became a {child_form.replace('_', ' ')}"))
    elif src_form in ("fragment", "whether_clause") and child_form == "question" and not conversion:
        form_reasons.append(("statement_to_question", f"a {src_form.replace('_', ' ')} was rewritten as a question"))
    if text.rstrip().endswith("?") and "?" not in src_text and src_form != "question":
        form_reasons.append(
            ("final_question_mark", "a final '?' was added to a request that is not phrased as a question")
        )
    if form_reasons:
        flags.append(
            {
                "kind": "request_form_changed",
                "class": "review",
                "words": list(dict.fromkeys(k for k, _ in form_reasons)),
                "note": "the researcher's request form was changed: " + "; ".join(n for _, n in form_reasons),
            }
        )

    # capitals and a final question mark are punctuation-level adjustments
    first, last = source_token(0) if ct else None, source_token(len(ct) - 1) if ct else None
    if first and text[:1].isupper() and q[first[1]].islower():
        ops.append({"op": "grammatical", "kind": "capitalization"})
    if text.rstrip().endswith("?") and not (last and q[last[2] : last[2] + 1] == "?"):
        ops.append({"op": "grammatical", "kind": "terminal_punctuation", "text": "?"})
    # coordinate splitting must keep shared wording as one unbroken run, the connecting words included
    broken = False
    for piece in (p for p in pieces if p.get("spliced")):
        run = [t for t, _, _ in piece["tokens"]]
        if not _subseq(words, run):
            broken = True
            flags.append(
                {
                    "kind": "shared_wording_changed",
                    "class": "review",
                    "words": run,
                    "note": f'the source wording "{piece["text"]}" (the shared frame joined to this item) is not kept as one unbroken run',
                }
            )
    for i in plan["carries_shared"]:
        r = by_id[i]
        frame = [t for lo, hi in r["spans"] for t, _, _ in _tokens(q[lo:hi], lo)] if r["kind"] == "shared_frame" else []
        if frame and not broken and not _subseq(words, frame):
            flags.append(
                {
                    "kind": "shared_wording_changed",
                    "class": "review",
                    "words": frame,
                    "note": f'the shared wording "{r["text"]}" is not kept as one unbroken run',
                }
            )
    # an antecedent replaces a reference word only through an identified clarification
    for c in applicable:
        ant = c.get("refers_to")
        if c["kind"] == "reference" and ant and c["target_text"].lower() not in words:
            for o in ops:
                if o["op"] == "context_carried" and all(
                    ant["span"][0] <= s[0] and s[1] <= ant["span"][1] for s in o["source_spans"]
                ):
                    o["op"], o["replaces"], o["clarification"] = "antecedent_resolved", c["target_text"], c["id"]
    consecutive = longest = 0
    for o in ops:  # a clarification explains the meaning; a long run of its words in the request is pasted prose
        if o.get("in_explanation_of") or o["op"] == "detail_pending":
            consecutive += 1
            longest = max(longest, consecutive)
        elif not (o["op"] == "grammatical" and o.get("kind") in HARMLESS.values()):
            consecutive = 0
    if longest >= RUN_LIMIT:
        flags.append(
            {
                "kind": "clarification_prose_pasted",
                "class": "review",
                "words": [str(longest)],
                "note": f"{longest} consecutive words come from a clarification's explanation; use only the words the request needs, not the explanation",
            }
        )
    link_available = bool(ctx.get("link")) or any(c.get("context_link") for c in applicable)
    unresolved = _context(
        parent, ctx, ops, segments, pieces, words, used_c, applicable, authorized_idx, flags, link_available
    )
    # requirement records: results the wording lets us check, the states of the annotated ones, and the LIMITS of a lexical check
    results, req_flags, limits = req.check_child(parent, words, plan, plans, ctx, applicable)
    flags += req_flags
    for r_ in runs:
        if r_["masked"] and r_["authority"] == req.PENDING and r_["role"] in ("link", "expression"):
            flags.append(
                {
                    "kind": "pending_authority_used",
                    "class": "pending",
                    "words": [r_["text"]],
                    "note": f'the wording relies on "{r_["text"]}" ({r_["role"]}, {r_["clarification"]}); the words are in the approved meaning, but the engine author recorded that they may be used and the researcher has not confirmed it',
                }
            )
    for d in detail_used.values():
        flags.append(
            {
                "kind": "clarification_detail_pending",
                "class": "review",
                "words": d["words"],
                "note": f"the wording uses words of {d['clarification']}'s approved meaning ({d['rec']['text']!r}); whether a child must contain, may contain or should leave out this detail is the researcher's pending decision",
            }
        )
    for c in applicable:
        for r_ in c.get("requirements", []):
            if r_["kind"] == "qualifier_expression":
                used_ = any(x["requirement"] == r_["id"] and x["valid"] for x in runs)
                if r_["required_in_child"] == "required" and not used_:
                    # only a researcher can make an expression required; when they have, silently dropping it is a conflict
                    flags.append(
                        {
                            "kind": "required_qualification_missing",
                            "class": "conflict",
                            "words": [r_["text"]],
                            "note": f'{c["id"]} requires the qualification "{r_["text"]}" (approved by {r_["provenance"]["approved_by"]}); the wording drops it',
                        }
                    )
                results.append(
                    {
                        "id": r_["id"],
                        "kind": r_["kind"],
                        "text": r_["text"],
                        "authority": r_["authority"],
                        "expression": r_["expression"],
                        "required_in_child": r_["required_in_child"],
                        "state": "used" if used_ else "not_present",
                    }
                )
            elif r_["kind"] == "detail":
                results.append(
                    {
                        "id": r_["id"],
                        "kind": r_["kind"],
                        "text": r_["text"],
                        "authority": r_["authority"],
                        "expression": r_["expression"],
                        "required_in_child": r_["required_in_child"],
                        "state": "used_pending" if r_["id"] in detail_used else "not_present",
                    }
                )
            elif r_["kind"] in req.DECIDED_KINDS:
                if r_["kind"] == "scope_item":
                    present = any(x["requirement"] == r_["id"] and x["valid"] for x in runs)
                    state = "approved_words_present" if present else "meaning_not_lexically_verified"
                    if r_.get("amended_by") and not present:
                        state = "optional_by_amendment"
                else:  # constraint: the relationship checks (subject, relation, target, direction, whether/how) are all it can rely on
                    rel_ = (child.get("diagnostics") or {}).get("relation") or {}
                    state = (
                        "relationship_check_flagged"
                        if rel_.get("violations") or rel_.get("review")
                        else "no_violation_detected"
                    )
                limits.append(req.LIMITS["scope"])
                results.append(
                    {
                        "id": r_["id"],
                        "kind": r_["kind"],
                        "text": r_["text"],
                        "authority": r_["authority"],
                        "expression": r_["expression"],
                        "required_in_child": r_["required_in_child"],
                        "literal_wording": r_["literal_wording"],
                        "state": state,
                        "decision": r_["provenance"].get("decision"),
                        **({"amended_by": r_["amended_by"]} if r_.get("amended_by") else {}),
                    }
                )
    limits = list(dict.fromkeys(limits))
    human_review = any(x.get("human_review_required") for x in results)
    if human_review:
        flags.append(
            {
                "kind": "human_review_required",
                "class": "info",
                "words": [],
                "note": "the researcher kept a human read of this relationship or pairing; no lexical check replaces it",
            }
        )
    order = [
        pieces[s["piece"]]["tokens"][s["p0"]][1]
        for s in sorted(segments, key=lambda s: s["c0"])
        if pieces[s["piece"]]["kind"] == "extract"
    ]
    if any(b < a for a, b in zip(order, order[1:], strict=False)):
        flags.append(
            {
                "kind": "reordered",
                "class": "info",
                "words": [],
                "note": "the copied wording appears in a different order than in the request",
            }
        )
    if any(o.get("attribution") == "uncertain" for o in ops):
        flags.append(
            {
                "kind": "uncertain_alignment",
                "class": "info",
                "words": [],
                "note": "some copied wording could come from more than one recorded piece, or is one common word; attribution is uncertain",
            }
        )
    ops += _sibling_removed(parent, child, plans, pieces, by_id)
    for o in ops:
        o.pop("_seg", None)
    carried = sorted(
        {
            tuple(s)
            for o in ops
            if o["op"] in ("copied", "context_carried", "antecedent_resolved")
            for s in o["source_spans"]
        }
    )
    count = lambda *kinds: sum(1 for o in ops if o["op"] in kinds)  # noqa: E731
    return {
        "audit_note": AUDIT_NOTE,
        "status": "problems_detected"
        if any(f["class"] in ("conflict", "review") for f in flags)
        else (
            "source_gap"
            if any(f["class"] == "gap" for f in flags)
            else (
                "pending_researcher_confirmation"
                if any(f["class"] == "pending" for f in flags)
                else "no_detected_problem"
            )
        ),
        "source_spans_carried": [list(s) for s in carried],
        "clarifications_used": sorted(
            {
                c
                for o in ops
                for c in (
                    [o["clarification"]] if isinstance(o.get("clarification"), str) else o.get("clarification") or []
                )
            }
        ),
        "ops": ops,
        "flags": flags,
        "requirements": results,
        "human_review_required": human_review,
        "verification_limits": limits,
        "unresolved": unresolved,
        "summary": {
            "copied": count("copied"),
            "context_carried": count("context_carried", "antecedent_resolved"),
            "sibling_removed": count("sibling_removed"),
            "grammatical": count("grammatical"),
            "request_form_change": count("request_form_change"),
            "clarification_supplied": count("clarification_supplied"),
            "operation_change": count("operation_change"),
            "unsupported": count("unsupported", "relation_word_added", "connective_unestablished"),
            "uncertain_alignments": sum(1 for o in ops if o.get("attribution") == "uncertain"),
        },
    }


def _context(
    parent, ctx, ops, segments, pieces, words, used_c, applicable, authorized_idx, flags, link_available
) -> list[dict]:
    """Can the question stand alone, and is its link to the request's subject SUPPORTED (never invented)?

    Restored context is copied exact wording. It may sit next to the question joined only by punctuation, which leaves the
    link unstated (reported, never chosen), or be joined by wording the source or a named clarification supplies. Any other
    connecting wording is an invented relation.

    When no approved clarification supplies joining words, a question that lacks the subject (or that only sets it beside the
    question) reflects a GAP in the request, not a writer failure: the flag is class ``gap`` and waits for the researcher.
    When approved joining words exist, the same omission is a writer failure (class ``review``)."""
    klass = "review" if link_available else "gap"
    if not ctx["subject"]:
        return []
    ref = ctx["subject"][0]
    stems = lx.content_stems(ref["text"])
    unresolved: list[dict] = []
    if lx.coverage_fraction(stems, lx.content_stems(" ".join(words))) < 0.6:
        flags.append(
            {
                "kind": "context_missing",
                "class": klass,
                "words": [ref["text"]],
                "note": f'the question does not state what the request is about ("{ref["text"]}"), so it cannot stand alone',
            }
        )
        unresolved.append(
            {
                "kind": "item_subject_link_unstated",
                "words": [ref["text"]],
                "note": "how this question relates to the request's subject is not stated by the request or an approved clarification",
            }
        )
        return unresolved
    stated = any(lx.coverage_fraction(stems, lx.content_stems(c["means"])) >= 0.6 for c in applicable)
    restored = {o["_seg"] for o in ops if o["op"] == "context_carried" and o.get("source", "").startswith("background")}
    order = sorted(segments, key=lambda s: s["c0"])
    for at, seg in enumerate(order):
        if segments.index(seg) not in restored:
            continue
        for nb in (order[at - 1] if at else None, order[at + 1] if at + 1 < len(order) else None):
            if nb is None or pieces[nb["piece"]]["kind"] != "extract":
                continue
            lo, hi = sorted(
                (seg["c1"] if nb["c0"] > seg["c0"] else nb["c1"], nb["c0"] if nb["c0"] > seg["c0"] else seg["c0"])
            )
            between = [k for k in range(lo, hi) if used_c[k] is None or used_c[k] < 0]
            if not between:
                if not stated:
                    flags.append(
                        {
                            "kind": "context_link_unstated",
                            "class": klass,
                            "words": [ref["text"]],
                            "note": "the subject's words sit next to the question with no connecting word; neither the request nor an approved clarification says how they relate",
                        }
                    )
                    unresolved.append(
                        {
                            "kind": "item_subject_link_unstated",
                            "words": [ref["text"]],
                            "note": "juxtaposed, not connected; the link was not chosen",
                        }
                    )
                continue
            added = [words[k] for k in between if k not in authorized_idx and words[k] not in ("a", "an", "the")]
            if added:
                flags.append(
                    {
                        "kind": "link_introduced",
                        "class": "review",
                        "words": added,
                        "note": f'"{" ".join(added)}" connects the question to its subject; neither the source nor an approved clarification supplies it',
                    }
                )
    return unresolved


def _sibling_removed(parent: dict, child: dict, plans: list[dict], pieces: list[dict], by_id: dict) -> list[dict]:
    """Other questions' words that lie inside this question's own source units and that this question does not carry."""
    q = parent["original_question"]
    units = [u for u in parent["source_units"] if u["source_unit_id"] in child["origin"]["source_unit_ids"]]
    authorized = [(lo, hi) for p in pieces for _, lo, hi in p["tokens"]]
    out = []
    for p in plans:
        if p["child_id"] == child["child_id"]:
            continue
        spans = sorted(
            {
                tuple(s)
                for i in p["owns"]
                if by_id[i]["kind"] != "source_unit"
                for s in by_id[i]["spans"]
                if any(u["start"] <= s[0] and s[1] <= u["end"] for u in units)
            }
        )
        merged: list[list[int]] = []
        for lo, hi in spans:
            if any(a_lo < hi and lo < a_hi for a_lo, a_hi in authorized):
                continue
            if merged and lo - merged[-1][1] <= 2:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        out += [
            {"op": "sibling_removed", "nodes": [p["child_id"]], "source_span": m, "text": q[m[0] : m[1]]}
            for m in merged
        ]
    return sorted(out, key=lambda o: o["source_span"][0])
