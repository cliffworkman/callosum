"""The question tree: nesting, inherited obligations, dependencies and joint answers, as data.

A flat parent -> children list cannot say that one question is asked ABOUT the answer to another ("return brain areas, and
whether they relate to behaviors"). The tree records that without any depth limit in the data model:

* the ORIGINAL REQUEST is the root (``R``); every question is a node with exactly one ``parent`` (``R`` or another node);
  depth is derived by walking parents, so deeper nesting needs no schema change;
* each node lists its OWN obligations (the ones only it answers), the obligations it INHERITS from an ancestor (context it
  uses but does not own), and its DEPENDENCIES on other nodes, kept apart from nesting;
* a nesting or a dependency is created only from an APPROVED fact: a user clarification that names the exact request
  words a reference or fragment points at. A candidate reading is recorded as a candidate dependency and never nests;
* a JOINT ANSWER group records answers that must be reported as pairs (a trait with its scale, a culture with how the bias
  was measured), which two independent lists cannot satisfy;
* reconciliation rolls up from subordinate nodes through their ancestors to the request, with one closure rule: a node's own
  obligations are closed only by that node; a subordinate never closes its parent, and a parent never closes a subordinate.

Nothing here answers anything or executes recursively; it is only the representation and the roll-up over it.
"""

from __future__ import annotations

ROOT = "R"
CLOSURE_RULE = (
    "A node's own obligations are closed only by that node's own answer. A subordinate node never closes its parent's "
    "obligations and a parent never closes a subordinate's. A node has no open flag only when its own obligations and "
    "every subordinate node have none. Identifying an item and establishing its relationship with an outcome are "
    "separate obligations owned by separate nodes."
)
JOINT_RULE = (
    "report each value together with its counterpart, one entry per pairing; two independent lists do not satisfy this"
)
_ANCHORS = ("requested_item", "relationship", "existence")


def _by_id(parent: dict) -> dict:
    return {r["id"]: r for r in [*parent["requirements"], *parent["ambiguities"], *parent.get("referents", [])]}


def _owner(plans: list[dict], rid: str) -> dict | None:
    return next((p for p in plans if rid in p["owns"]), None)


def _antecedent(parent: dict, plans: list[dict], span: list[int]) -> dict | None:
    """The obligation (or background referent) whose words contain the exact antecedent words, and the node that owns it."""
    lo, hi = span
    holders = [
        r
        for r in parent["requirements"]
        if not r.get("superseded")
        and r["origin"] != "source_unit_floor"
        and r["kind"] in _ANCHORS
        and any(s[0] <= lo and hi <= s[1] for s in r["spans"])
    ]
    if holders:
        best = min(holders, key=lambda r: sum(s[1] - s[0] for s in r["spans"]))
        owner = _owner(plans, best["id"])
        return {
            "obligation": best["id"],
            "kind": best["kind"],
            "text": best["text"],
            "node": owner["child_id"] if owner else None,
        }
    for ref in parent.get("referents", []):
        if any(s[0] <= lo and hi <= s[1] for s in ref["spans"]):
            return {"obligation": ref["id"], "kind": ref["kind"], "text": ref["text"], "node": ROOT}
    return None


def _member_node(parent: dict, plans: list[dict], span: list[int]) -> str | None:
    """The node that owns the request words at ``span`` (largest overlap with its owned obligations)."""
    by = _by_id(parent)
    best, size = None, 0
    for p in plans:
        got = sum(max(0, min(span[1], s[1]) - max(span[0], s[0])) for i in p["owns"] for s in by[i]["spans"])
        if got > size:
            best, size = p["child_id"], got
    return best


def annotate_plans(parent: dict, plans: list[dict]) -> None:
    """Give every plan a ``node``: its parent, depth, inherited obligations and dependencies (approved facts only)."""
    clarifications = {c["id"]: c for c in parent.get("clarifications", [])}
    for plan in plans:
        rc = plan.get("relation")
        parsed = bool(rc and rc.get("parse_status") == "parsed")
        links: list[tuple[str, dict]] = []  # (role, {"span", "text", "clarification", "slot"})
        if parsed:
            for ref in rc["clarified_referents"]:
                if ref.get("antecedent"):
                    links.append(
                        (
                            f"{ref['slot']}_antecedent",
                            {
                                "antecedent": ref["antecedent"],
                                "clarification": ref["clarification"],
                                "word": ref["word"],
                            },
                        )
                    )
        fragment = clarifications.get(plan.get("clarified_fragment") or "")
        if fragment and fragment.get("refers_to"):
            links.append(
                (
                    "fragment_target",
                    {
                        "antecedent": fragment["refers_to"],
                        "clarification": fragment["id"],
                        "word": fragment["target_text"],
                    },
                )
            )
        inherited, depends, nest = [], [], None
        for role, link in links:
            hit = _antecedent(parent, plans, link["antecedent"]["span"])
            if hit is None:
                depends.append(
                    {
                        "kind": "antecedent_not_owned",
                        "clarification": link["clarification"],
                        "basis": "user_clarification",
                        "note": "the clarified words point at request words no obligation holds",
                    }
                )
                continue
            if hit["node"] == plan["child_id"]:
                continue  # it points inside its own words: nothing inherited
            inherited.append(
                {
                    "obligation": hit["obligation"],
                    "text": hit["text"],
                    "spans": [link["antecedent"]["span"]],
                    "from_node": hit["node"],
                    "role": role,
                    "clarification": link["clarification"],
                    # every obligation the owning question owns: context for THIS question, never to be asked again
                    "owner_obligations": next((p["owns"] for p in plans if p["child_id"] == hit["node"]), []),
                }
            )
            if hit["node"] not in (None, ROOT):
                depends.append(
                    {
                        "node": hit["node"],
                        "kind": "antecedent_of_reference" if role != "fragment_target" else "fragment_target",
                        "via": link["clarification"],
                        "basis": "user_clarification",
                        "obligation": hit["obligation"],
                    }
                )
                if nest is None and role in ("subject_antecedent", "fragment_target"):
                    nest = {
                        "parent": hit["node"],
                        "kind": "clarified_antecedent",
                        "clarification": link["clarification"],
                        "obligation": hit["obligation"],
                    }
        candidates = []
        if parsed:
            for ref in rc["unresolved_referents"]:
                for cand in ref.get("candidates") or []:
                    owner = _owner(plans, cand["id"])
                    candidates.append(
                        {
                            "reference": ref["word"],
                            "span": ref["span"],
                            "candidate_obligation": cand["id"],
                            "candidate_node": owner["child_id"] if owner else ROOT,
                            "role": cand.get("role"),
                            "basis": "unapproved_candidate",
                        }
                    )
        for rid in plan.get("context_referents", []):
            ref = next((r for r in parent.get("referents", []) if r["id"] == rid), None)
            if ref:
                inherited.append(
                    {
                        "obligation": rid,
                        "text": ref["text"],
                        "spans": ref["spans"],
                        "from_node": ROOT,
                        "role": "background_referent",
                        "clarification": None,
                    }
                )
        plan["node"] = {
            "parent": nest["parent"] if nest else ROOT,
            "nesting_basis": nest or {"kind": "top_level"},
            "inherited": inherited,
            "depends_on": depends,
            "candidate_dependencies": candidates,
        }
    _depths(plans)


def _depths(plans: list[dict]) -> None:
    """Depth = parents walked to the root. A parent chain that loops is cut at the offending link and reported."""
    by = {p["child_id"]: p for p in plans}
    for p in plans:
        seen, cur, depth = {p["child_id"]}, p, 1
        while cur["node"]["parent"] != ROOT:
            nxt = by.get(cur["node"]["parent"])
            if nxt is None or nxt["child_id"] in seen:
                cur["node"]["parent"] = ROOT
                cur["node"]["nesting_basis"] = {
                    "kind": "top_level",
                    "note": "a nesting that pointed at itself or at a missing node was cut",
                }
                break
            seen.add(nxt["child_id"])
            cur, depth = nxt, depth + 1
        p["node"]["depth"] = depth


def joint_groups(parent: dict, plans: list[dict]) -> list[dict]:
    out = []
    for c in parent.get("clarifications", []):
        if not c.get("pairs"):
            continue
        out.append(
            {
                "id": f"J-{c['id']}",
                "clarification": c["id"],
                "means": c["means"],
                "rule": JOINT_RULE,
                "members": [
                    {"span": m["span"], "text": m["text"], "node": _member_node(parent, plans, m["span"])}
                    for m in c["pairs"]
                ],
            }
        )
    return out


def question_tree(parent: dict, plans: list[dict]) -> dict:
    """The tree as one artifact: the root, every node, and the joint-answer groups. A pure function of the plans."""
    by = _by_id(parent)
    q = parent["original_question"]
    groups = joint_groups(parent, plans)
    kids: dict[str, list[str]] = {}
    for p in plans:
        kids.setdefault(p["node"]["parent"], []).append(p["child_id"])
    nodes = []
    for p in plans:
        n = p["node"]
        nodes.append(
            {
                "node_id": p["child_id"],
                "parent": n["parent"],
                "depth": n["depth"],
                "nesting_basis": n["nesting_basis"],
                "kind": p["kind"],
                "anchor_id": p["anchor_id"],
                "own_obligations": [
                    {"id": i, "kind": by[i]["kind"], "text": by[i]["text"], "spans": by[i]["spans"]} for i in p["owns"]
                ],
                "folded_from": p.get("folded", []),
                "shared_frames": p["carries_shared"],
                "inherited": n["inherited"],
                "depends_on": n["depends_on"],
                "candidate_dependencies": n["candidate_dependencies"],
                "joint_answer_groups": [
                    g["id"] for g in groups if any(m["node"] == p["child_id"] for m in g["members"])
                ],
                "subordinates": kids.get(p["child_id"], []),
                "clarified_fragment": p.get("clarified_fragment"),
            }
        )
    return {
        "version": "question-tree/1",
        "root": {
            "node_id": ROOT,
            "kind": "original_request",
            "text": q,
            "source_spans": [[0, len(q)]],
            "subordinates": kids.get(ROOT, []),
        },
        "nodes": nodes,
        "joint_answer_groups": groups,
        "max_depth": max((n["depth"] for n in nodes), default=0),
        "closure_rule": CLOSURE_RULE,
        "note": "nesting and dependencies come only from approved user clarifications; candidate readings are listed apart",
    }


def _descendants(tree: dict, node_id: str) -> list[str]:
    kids = {n["node_id"]: n["subordinates"] for n in tree["nodes"]}
    out, stack, seen = [], list(kids.get(node_id, [])), set()
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
        stack.extend(kids.get(cur, []))
    return out


def reconcile_tree(tree: dict, children: list[dict], summary: dict) -> dict:
    """Roll question-writing state up from subordinates through their ancestors to the request. This is the same shape a
    later answer stage would use; ``state`` is a writing state today and is never a certificate."""
    by_child = {c["child_id"]: c for c in children}
    passed = set(summary.get("passed_through_children", []))
    ok = set(summary["successful_children"]) | passed

    def state(cid: str) -> str:
        if cid in passed:
            return "passed_through_unchanged_ask_pending"
        return "no_open_flag" if cid in ok else by_child[cid]["status"]

    nodes = {}
    for n in tree["nodes"]:
        cid = n["node_id"]
        below = _descendants(tree, cid)
        nodes[cid] = {
            "parent": n["parent"],
            "depth": n["depth"],
            "own_state": state(cid),
            "own_open": cid not in ok,
            "subordinates": n["subordinates"],
            "subtree_open": [d for d in below if d not in ok],
            "no_open_flag_in_subtree": cid in ok and all(d in ok for d in below),
            "blocked_by": [
                {"node": d["node"], "state": state(d["node"])}
                for d in n["depends_on"]
                if d.get("node") and d["node"] not in ok
            ],
        }
    joint = []
    for g in tree["joint_answer_groups"]:
        members = [m["node"] for m in g["members"]]
        joint.append(
            {
                "id": g["id"],
                "members": g["members"],
                "status": "open" if (None in members or any(m not in ok for m in members)) else "no_open_flag",
                "rule": g["rule"],
            }
        )
    top = tree["root"]["subordinates"]
    open_nodes = [n["node_id"] for n in tree["nodes"] if n["node_id"] not in ok]
    return {
        "closure_rule": tree["closure_rule"],
        "nodes": nodes,
        "joint_answer_groups": joint,
        "root": {
            "top_level": top,
            "open_nodes": open_nodes,
            "unresolved_rows": summary["unresolved_count"],
            "state": "open" if open_nodes or summary["unresolved_count"] else "no_open_flag",
            "answer_state": summary.get("answer_state", "not_executed"),
            "note": "no_open_flag means no structural flag remains in the QUESTION-WRITING state; it never means the request was "
            "answered, retrieved or synthesized (answer_state), and semantic fidelity is never certified",
        },
    }


def verify(parent: dict, tree: dict) -> list[str]:
    """VERIFIED TRACEABILITY of the tree: ids, parents, spans and the words the links quote. No semantics."""
    q, bad = parent["original_question"], []
    ids = {n["node_id"] for n in tree["nodes"]}
    known = {r["id"] for r in [*parent["requirements"], *parent["ambiguities"], *parent.get("referents", [])]}
    parents = {n["node_id"]: n["parent"] for n in tree["nodes"]}
    for n in tree["nodes"]:
        if n["parent"] != ROOT and n["parent"] not in ids:
            bad.append(f"tree {n['node_id']}: unknown parent {n['parent']}")
        seen, cur = set(), n["node_id"]
        while cur != ROOT and cur in parents:
            if cur in seen:
                bad.append(f"tree {n['node_id']}: the parent chain loops")
                break
            seen.add(cur)
            cur = parents[cur]
        for o in n["own_obligations"]:
            if o["id"] not in known:
                bad.append(f"tree {n['node_id']}: owns unknown obligation {o['id']}")
        for i in n["inherited"]:
            if i["obligation"] not in known:
                bad.append(f"tree {n['node_id']}: inherits unknown obligation {i['obligation']}")
            for lo, hi in i["spans"]:
                if not 0 <= lo < hi <= len(q):
                    bad.append(f"tree {n['node_id']}: inherited span {[lo, hi]} outside the request")
        for d in n["depends_on"]:
            if d.get("node") and d["node"] not in ids:
                bad.append(f"tree {n['node_id']}: depends on unknown node {d['node']}")
    for g in tree["joint_answer_groups"]:
        for m in g["members"]:
            if q[m["span"][0] : m["span"][1]] != m["text"]:
                bad.append(f"tree {g['id']}: member words do not match the request at {m['span']}")
    return bad
