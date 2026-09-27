"""Pre-registered checks, evaluated mechanically over a run's receipts. FROZEN before any live call (see run.py prepare).

A miss is a FINDING with its upstream cause, not something to patch: each regression check reports whether the target evidence
was never read, read but not localized, localized but not judged, or judged not addressed. `review` marks what only a human can
adjudicate. Integrity checks void a run if they fail. Regression targets were identified from the baseline receipts and (c9's
Methods chunk) checked during development, so E3's chunk-level check is DEVELOPMENT-INFORMED, not a blind test; that is
stated in the report next to its result.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from experiments.ask_cli_revised.contract_directed import attribution as at
from experiments.ask_cli_revised.contract_directed import closure

PASS, FAIL, REVIEW, NOT_EVALUABLE = "pass", "fail", "review", "not_evaluable"

EXPECTATIONS_VERSION = "gate1-v2-2026-09-26"
EXPECTATIONS = {
    "I": "Integrity (a failure voids the run): frozen hashes; every packet piece verbatim; library and baseline unchanged; no parent/sibling/machine-claim leakage; raw answers preserved; NO ANSWER rates reported.",
    "E1": "c5 and c6 receive brain-relationship evidence: the abstract span linking the amygdala response to behavior/attitudes (chunk 34974) and the Discussion left-amygdala span (chunk 35111) are judged closing or partial for the neural-relationship units, or a receipt names the upstream stage that lost them.",
    "E2": "c5's answer states no direction that its cited passages do not state.",
    "E3": "c9 receives the Methods sentence naming actual scales (chunk 35019), and BOTH its evidence and its answer carry the correct instrument-to-construct pairings, not merely the scale names: the Just World Beliefs Scale with beliefs about interpersonal fairness, the Interpersonal Reactivity Index with cognitive/affective empathy (perspective taking, empathic concern), and the Three-Domain Disgust scale with pathogen-related disgust sensitivity. A scale paired with another scale's construct fails; names without pairings are a review item, never a pass. The answer must also separate constructs from named measures (human review) and expand no acronym absent from its passages. The chunk-level part is development-informed, not blind.",
    "E4": "c10/c11 receive complete (verified-seam or explicitly unresolved) sentences from paper 68 with the Hadza design and the exposure qualifier, the primary attachment preferred, and no truncated-clause span is eligible.",
    "N1": "Statements whose attribution is not own_established never close a unit; the Introduction recital U7 (chunk 34984) never closes a finding unit.",
    "N2": "A suggestion, proposal or speculation about an intervention cannot establish effectiveness. Tested OFFLINE against the real speculative sentence (U5) and an own-reported outcome; c12 is not in this pilot, so this is NOT reported as a live intervention-answer result.",
    "N3": "Every eligible (packet, child) row carries a slot-level receipt.",
    "N4": "No obligation is closed by combining unrelated passages or by independently mentioning its component concepts. A finding supported across Methods, Results or other sections is permitted only when the SOURCE ITSELF establishes the link (a definition acronym, a named measure present verbatim in both spans, an explicit table or study reference), with each exact span, its locator, its attribution and the linking rationale preserved in the bundle. Being in the same paper never establishes a relationship.",
}
EDIT_LOG = [
    {
        "recorded": "2026-09-26, at Gate 1 authorization, BEFORE any live inference",
        "edits": [
            "N4 rewritten from 'no closure across more than one packet' to source-grounded evidence bundles (linked spans allowed only with a source-established link and a preserved rationale).",
            "N2 restored as an offline negative control (suggestion or proposed intervention cannot establish effectiveness); c12 is out of scope so it is not a live result.",
            "E3 now requires the correct instrument-to-construct pairings in both the evidence and the answer, not merely the scale names.",
        ],
        "rule": "these records are frozen once inference starts; they are never changed in response to pilot results",
    }
]


def expectations_record() -> dict:
    """The pre-registration record written to every run before inference (`expectations.json`)."""
    items = dict(EXPECTATIONS)
    canonical = json.dumps({"version": EXPECTATIONS_VERSION, "items": items}, sort_keys=True, ensure_ascii=False)
    return {
        "version": EXPECTATIONS_VERSION,
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "items": items,
        "edit_log": EDIT_LOG,
    }


# ---- E3: instrument-to-construct pairings ------------------------------------------------------------------------------------

E3_INSTRUMENTS = {
    "Just World Beliefs Scale": {
        "names": re.compile(r"just[- ]world beliefs? scale|\bjwbs\b", re.I),
        "constructs": re.compile(r"fair|just[- ]world belief|\bbeliefs?\b", re.I),
    },
    "Interpersonal Reactivity Index": {
        "names": re.compile(r"interpersonal reactivity index|\biri\b", re.I),
        "constructs": re.compile(r"empath|perspective", re.I),
    },
    "Three-Domain Disgust scale": {
        "names": re.compile(r"three[- ]domain disgust|disgust scale", re.I),
        "constructs": re.compile(r"pathogen|sensitiv", re.I),
    },
}
PAIRED, UNPAIRED, MISPAIRED, ABSENT = "paired", "mentioned_unpaired", "mispaired", "absent"


def pairings_in_text(text: str) -> dict[str, str]:
    """For each instrument: is it paired with ITS OWN construct in this text (segment-limited), unpaired, or paired with another's?

    The segment after an instrument's name runs to the next instrument name (or the end of the text); the construct wording must
    fall inside that segment. A segment holding only another instrument's construct wording is `mispaired`.
    """
    occurrences = []
    for name, spec in E3_INSTRUMENTS.items():
        for m in spec["names"].finditer(text):
            occurrences.append((m.start(), m.end(), name))
    occurrences.sort()
    result = {name: ABSENT for name in E3_INSTRUMENTS}
    rank = {ABSENT: 0, UNPAIRED: 1, MISPAIRED: 2, PAIRED: 3}
    for index, (_start, end, name) in enumerate(occurrences):
        stop = occurrences[index + 1][0] if index + 1 < len(occurrences) else len(text)
        segment = text[end:stop]
        if E3_INSTRUMENTS[name]["constructs"].search(segment):
            state = PAIRED
        elif any(other != name and spec["constructs"].search(segment) for other, spec in E3_INSTRUMENTS.items()):
            state = MISPAIRED
        else:
            state = UNPAIRED
        if state == MISPAIRED and result[name] == PAIRED:
            continue
        if rank[state] > rank[result[name]]:
            result[name] = state
    return result


def answer_pairings(raw: str) -> dict[str, str]:
    """Best pairing state per instrument across the answer's sentences; a mispairing anywhere is reported."""
    result = {name: ABSENT for name in E3_INSTRUMENTS}
    mispaired: set[str] = set()
    paired: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", raw):
        for name, state in pairings_in_text(sentence).items():
            if state == MISPAIRED:
                mispaired.add(name)
            elif state == PAIRED:
                paired.add(name)
            elif state == UNPAIRED and result[name] == ABSENT:
                result[name] = UNPAIRED
    for name in E3_INSTRUMENTS:
        result[name] = MISPAIRED if name in mispaired else (PAIRED if name in paired else result[name])
    return result


# ---- offline negative controls (N2, N4): run on every evaluation, independent of any pilot result ---------------------------

_U5 = "Having knowledge about individual differences in empathy and disgust sensitivity might improve decision-making and reduce bias toward people with anomalous faces."
_OWN_OUTCOME = (
    "We found that the intervention reduced implicit bias (d = 0.42, P = 0.003) relative to the control group."
)


def _synthetic_packet(texts: list[str], roles: list[str]) -> dict:
    parts, flat, full = [], {}, {}
    for n, (text, role) in enumerate(zip(texts, roles, strict=True), start=1):
        sid = f"p{n}"
        parts.append(
            {"span_id": sid, "role": role, "unit_index": n, "open_left": False, "open_right": False, "text": text}
        )
        if role != "linked_definition":
            record = at.derive_attribution([text])  # the REAL, now clause-aware derivation — one source of truth
            flat[sid] = record["state"]
            full[sid] = record
    return {"parts": parts, "part_attribution": flat, "attribution": full}


def offline_controls() -> list[dict]:
    """Negative controls on the real closure code, using the real speculative sentence U5. Not a live result."""
    out: list[dict] = []
    spec = _synthetic_packet([_U5], ["establishing"])
    slots = {
        "finding_of_type": {"span_ids": ["p1"]},
        "outcome_reported": {"span_ids": ["p1"]},
        "on_topic": {"span_ids": ["p1"]},
    }
    status = closure.derive_status("existence", slots, spec)
    out.append(
        _result(
            "N2.offline_control_speculation_does_not_establish_effectiveness",
            PASS if status["status"] != closure.DIRECTLY and spec["part_attribution"]["p1"] == at.SPECULATION else FAIL,
            f"U5 attribution={spec['part_attribution']['p1']}, existence status={status['status']}, missing={status['missing']}",
            offline_only=True,
            live_result=False,
        )
    )
    own = _synthetic_packet([_OWN_OUTCOME], ["establishing"])
    own_status = closure.derive_status("existence", slots, own)
    out.append(
        _result(
            "N2.offline_control_an_own_reported_outcome_does_establish_it",
            PASS if own_status["status"] == closure.DIRECTLY else FAIL,
            f"attribution={own['part_attribution']['p1']}, status={own_status['status']}",
            offline_only=True,
            live_result=False,
        )
    )
    # N4 controls: relata in unrelated, distant spans; and a linked span offered for a finding-bearing slot
    far = _synthetic_packet(
        [
            "The amygdala responded to anomalous faces.",
            "Filler.",
            "Filler.",
            "Filler.",
            "Participants were less generous.",
        ],
        ["establishing"] * 5,
    )
    far_slots = {
        "relatum_a": {"span_ids": ["p1"]},
        "relatum_b": {"span_ids": ["p5"]},
        "relation_stated": {"span_ids": ["p1"]},
        "polarity": {"span_ids": ["p1"], "value": "association"},
        "direction": {"span_ids": ["p5"]},
        "on_topic": {"span_ids": ["p1"]},
    }
    far_status = closure.derive_status("relationship", far_slots, far)
    out.append(
        _result(
            "N4.offline_control_co_occurrence_is_not_a_relationship",
            PASS if far_status["status"] != closure.DIRECTLY else FAIL,
            f"status={far_status['status']}, missing={far_status['missing']}",
            offline_only=True,
            live_result=False,
        )
    )
    linked = _synthetic_packet(
        ["We found less generosity in the DG (P = 0.03).", "In the Dictator Game (DG), players split $5."],
        ["establishing", "linked_definition"],
    )
    bad_slots = {
        "relatum_a": {"span_ids": ["p1"]},
        "relatum_b": {"span_ids": ["p1"]},
        "relation_stated": {"span_ids": ["p2"]},
        "polarity": {"span_ids": ["p2"], "value": "association"},
        "direction": {"span_ids": ["p1"]},
        "on_topic": {"span_ids": ["p1"]},
    }
    bad = closure.derive_status("relationship", bad_slots, linked)
    ok_slots = {
        "instrument_named": {"span_ids": ["p2"]},
        "paired_with_construct": {"span_ids": ["p1"]},
        "on_topic": {"span_ids": ["p1"]},
    }
    ok = closure.derive_status("operation", ok_slots, linked)
    out.append(
        _result(
            "N4.offline_control_a_linked_definition_cannot_supply_the_finding_but_can_supply_the_measure",
            PASS if bad["status"] != closure.DIRECTLY and ok["status"] == closure.DIRECTLY else FAIL,
            f"finding from a linked span: {bad['status']} ({bad['reasons']}); measure from a linked span: {ok['status']}",
            offline_only=True,
            live_result=False,
        )
    )
    return out


def _jsonl(path: Path) -> list[dict]:
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.exists()
        else []
    )


def _result(cid: str, status: str, detail: str, **evidence) -> dict:
    return {"id": cid, "status": status, "detail": detail, "evidence": evidence}


def _packets(run_dir: Path) -> list[dict]:
    return [p for p in _jsonl(run_dir / "07_packets.jsonl") if p.get("state") == "built"]


def _elig(run_dir: Path) -> list[dict]:
    return [e for e in _jsonl(run_dir / "08_eligibility.jsonl") if e.get("state") == "usable"]


def _packet_with_chunk(packets: list[dict], chunk_id: int, needle: str | None = None) -> list[dict]:
    out = []
    for p in packets:
        for part in p["parts"]:
            if part["role"] == "linked_definition":
                continue
            if any(pc["chunk_id"] == chunk_id for pc in part["pieces"]) and (
                needle is None or needle.lower() in part["text"].lower()
            ):
                out.append(p)
                break
    return out


def _upstream_cause(run_dir: Path, chunk_id: int) -> str:
    """Where in the chain a target chunk stopped: never anchored, budget-capped, or read without a localized packet."""
    nbhds = [n for n in _jsonl(run_dir / "05_neighborhoods.jsonl") if chunk_id in n.get("chunk_ids", [])]
    if not nbhds:
        return "never_in_any_neighborhood"
    if not any(n["state"] == "read" for n in nbhds):
        return "neighborhood_budget_capped_not_read"
    return "read_but_no_packet_localized_from_it"


def _status_for(elig: list[dict], packet_ids: set[str], child_id: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for e in elig:
        if e["child_id"] == child_id and e["packet_id"] in packet_ids:
            for uid, entry in e["per_unit"].items():
                rank = {"directly_establishes": 2, "partially_establishes": 1, "not_addressed": 0}[entry["status"]]
                if (
                    uid not in out
                    or rank > {"directly_establishes": 2, "partially_establishes": 1, "not_addressed": 0}[out[uid]]
                ):
                    out[uid] = entry["status"]
    return out


def evaluate(
    run_dir: Path | str, *, integrity: dict | None = None, children_in_run: list[str] | None = None
) -> list[dict]:
    run = Path(run_dir)
    packets, elig = _packets(run), _elig(run)
    answers = {}
    for path in (run / "12_answers").glob("*_record.json") if (run / "12_answers").is_dir() else []:
        rec = json.loads(path.read_text(encoding="utf-8"))
        rec["raw"] = (run / "12_answers" / f"{rec['child_id']}_raw_answer.txt").read_text(encoding="utf-8")
        answers[rec["child_id"]] = rec
    scope = set(children_in_run or answers)
    results: list[dict] = []

    # ---- integrity -----------------------------------------------------------------------------------------------------------
    pieces_ok = all(pc["verbatim_ok"] for p in packets for part in p["parts"] for pc in part["pieces"])
    results.append(
        _result(
            "I.pieces_verbatim",
            PASS if pieces_ok else FAIL,
            f"{sum(len(part['pieces']) for p in packets for part in p['parts'])} pieces checked",
        )
    )
    for name, ok in (integrity or {}).items():
        results.append(_result(f"I.{name}", PASS if ok else FAIL, "checked by the runner"))
    leak = [
        c
        for c, a in answers.items()
        if a["diagnostics"]["prompt_leakage"]["contains_parent_question"]
        or a["diagnostics"]["prompt_leakage"]["contains_other_child_wording"]
        or a["diagnostics"]["prompt_leakage"]["contains_machine_claim_marker"]
    ]
    results.append(_result("I.no_leakage", PASS if not leak else FAIL, f"children with prompt leakage: {leak}"))
    results.append(
        _result(
            "I.raw_answers_preserved",
            PASS if scope and set(answers) >= scope else FAIL,
            f"answers present for {sorted(answers)}",
        )
    )
    ledger = run / "14_ledger.json"
    results.append(_result("I.no_answer_rates_reported", PASS if ledger.exists() else FAIL, "14_ledger.json"))

    # ---- E1 ---------------------------------------------------------------------------------------------------------------------
    def received(child_id: str, chunk_id: int, needle: str, units: tuple[str, ...]):
        found = _packet_with_chunk(packets, chunk_id, needle)
        if not found:
            return NOT_EVALUABLE, f"no packet was localized from chunk {chunk_id}: {_upstream_cause(run, chunk_id)}"
        statuses = _status_for(elig, {p["packet_id"] for p in found}, child_id)
        got = {u: s for u, s in statuses.items() if u in units}
        if not got:
            return (
                NOT_EVALUABLE,
                f"packet(s) {[p['packet_id'] for p in found]} exist but were not judged for {child_id}",
            )
        best = (
            "directly_establishes"
            if "directly_establishes" in got.values()
            else ("partially_establishes" if "partially_establishes" in got.values() else "not_addressed")
        )
        return (PASS if best != "not_addressed" else FAIL), f"{child_id} units {got}"

    if {"c5"} & scope:
        s, d = received("c5", 34974, "amygdala", ("M5", "M6"))
        results.append(_result("E1.c5_abstract_amygdala_span", s, d))
    if {"c6"} & scope:
        s, d = received("c6", 35111, "left amygdala", ("M7", "M8"))
        results.append(_result("E1.c6_left_amygdala_span", s, d))

    # ---- E2 ---------------------------------------------------------------------------------------------------------------------
    if "c5" in answers:
        flags = answers["c5"]["diagnostics"]["directional_terms_not_in_cited_passages"]
        results.append(
            _result(
                "E2.c5_direction_supported",
                PASS if not flags else FAIL,
                f"{len(flags)} directional claim(s) not in cited text",
                flags=flags,
            )
        )

    # ---- E3 ---------------------------------------------------------------------------------------------------------------------
    if "c9" in scope:
        s, d = received("c9", 35019, "Just World", ("M10", "W21"))
        results.append(_result("E3.c9_scales_span_received(development-informed)", s, d))
        # the evidence: pairings inside the spans c9's own slot judgments cite for its units
        cited_texts: list[str] = []
        by_packet = {p["packet_id"]: p for p in packets}
        for e in elig:
            if e["child_id"] != "c9" or e["packet_id"] not in by_packet:
                continue
            parts = {pt["span_id"]: pt for pt in by_packet[e["packet_id"]]["parts"]}
            for entry in e["per_unit"].values():
                if entry["status"] not in ("directly_establishes", "partially_establishes"):
                    continue
                for ids in entry["slot_spans"].values():
                    cited_texts += [
                        parts[i]["text"] for i in ids if i in parts and parts[i]["role"] != "linked_definition"
                    ]
        evidence = {name: ABSENT for name in E3_INSTRUMENTS}
        rank = {ABSENT: 0, UNPAIRED: 1, MISPAIRED: 2, PAIRED: 3}
        for text in dict.fromkeys(cited_texts):
            for name, state in pairings_in_text(text).items():
                if rank[state] > rank[evidence[name]]:
                    evidence[name] = state
        if not cited_texts:
            ev_status, ev_detail = (
                NOT_EVALUABLE,
                "no c9 unit cited any span (see E3.c9_scales_span_received for the upstream cause)",
            )
        elif MISPAIRED in evidence.values():
            ev_status, ev_detail = FAIL, f"an instrument is paired with another's construct: {evidence}"
        elif all(v == PAIRED for v in evidence.values()):
            ev_status, ev_detail = (
                PASS,
                f"all three instrument-to-construct pairings are present in c9's cited spans: {evidence}",
            )
        else:
            ev_status, ev_detail = REVIEW, f"not every pairing is present in c9's cited spans: {evidence}"
        results.append(
            _result("E3.c9_evidence_carries_instrument_construct_pairings", ev_status, ev_detail, pairings=evidence)
        )
        if "c9" in answers:
            paired = answer_pairings(answers["c9"]["raw"])
            bad = answers["c9"]["diagnostics"]["acronym_expansions_not_in_any_passage"]
            if MISPAIRED in paired.values():
                an_status = FAIL
            elif all(v == PAIRED for v in paired.values()) and not bad:
                an_status = PASS
            else:
                an_status = REVIEW  # names without pairings (or an unsupported expansion) are never a pass
            results.append(
                _result(
                    "E3.c9_answer_pairs_each_scale_with_its_construct",
                    an_status,
                    f"pairings in the answer: {paired}; acronym expansions absent from passages: {bad}",
                    pairings=paired,
                )
            )
            results.append(
                _result(
                    "E3.c9_constructs_vs_measures",
                    REVIEW,
                    "a human reads whether constructs are separated from named measures",
                )
            )

    # ---- E4 ---------------------------------------------------------------------------------------------------------------------
    paper68 = [p for p in packets if p["paper_id"] == 68]
    for child in ("c10", "c11"):
        if child not in scope:
            continue
        eligible = []
        for e in elig:
            if e["child_id"] == child and any(
                u["status"] in ("directly_establishes", "partially_establishes") for u in e["per_unit"].values()
            ):
                eligible.append(e["packet_id"])
        p68 = [p for p in paper68 if p["packet_id"] in eligible]
        truncated = [
            p["packet_id"]
            for p in p68
            if p["evidence_form"] == "fragments_unresolved_seam"
            and any(
                re.search(r"\b(a|an|the|of|to|and|against)$", part["text"].rstrip(), re.I)
                for part in p["parts"]
                if part["role"] != "linked_definition"
            )
        ]
        alt = [p["packet_id"] for p in p68 if not p["attachment"]["is_primary"]]
        if not p68:
            results.append(_result(f"E4.{child}_paper68_packets", FAIL, "no eligible packet from paper 68"))
        else:
            results.append(
                _result(
                    f"E4.{child}_no_truncated_clause_eligible",
                    PASS if not truncated else FAIL,
                    f"truncated eligible packets: {truncated}",
                )
            )
            results.append(
                _result(
                    f"E4.{child}_primary_attachment_preferred",
                    PASS if not alt or len(alt) < len(p68) else REVIEW,
                    f"alternate-attachment packets: {alt}",
                )
            )
        if child in answers:
            results.append(
                _result(
                    f"E4.{child}_answer_names_hadza",
                    PASS if "hadza" in answers[child]["raw"].lower() else REVIEW,
                    "answer text checked for the population named in the source",
                )
            )
    # ---- N ----------------------------------------------------------------------------------------------------------------------
    bad_close = []
    for e in elig:
        packet = next((p for p in packets if p["packet_id"] == e["packet_id"]), None)
        if not packet:
            continue
        for uid, entry in e["per_unit"].items():
            if entry["status"] != "directly_establishes":
                continue
            core = {
                sid
                for spans in entry["slot_spans"].values()
                for sid in spans
                if next(
                    (pt for pt in packet["parts"] if pt["span_id"] == sid and pt["role"] != "linked_definition"), None
                )
            }
            if any(packet["part_attribution"].get(sid) != "own_established" for sid in core):
                bad_close.append((e["packet_id"], e["child_id"], uid))
    u7 = _packet_with_chunk(packets, 34984, "anomalous-is-bad")
    u7_closed = [
        (p["packet_id"], e["child_id"], uid)
        for p in u7
        for e in elig
        if e["packet_id"] == p["packet_id"]
        for uid, entry in e["per_unit"].items()
        if entry["status"] == "directly_establishes"
    ]
    results.append(
        _result(
            "N1.unattributed_never_closes",
            PASS if not bad_close and not u7_closed else FAIL,
            f"closures on non-own attribution: {bad_close}; U7 closures: {u7_closed}",
        )
    )
    results.append(
        _result(
            "N2.live_c12_intervention_answer",
            NOT_EVALUABLE,
            "c12 is outside this pilot: N2 is reported ONLY as the offline controls below, never as a live intervention-answer result",
        )
    )
    results += offline_controls()
    thin = [
        (e["packet_id"], e["child_id"])
        for e in elig
        if any(u["status"] != "not_addressed" and "slot_spans" not in u for u in e["per_unit"].values())
    ]
    results.append(
        _result(
            "N3.slot_level_receipt_for_every_assignment",
            PASS if not thin else FAIL,
            f"rows without slot spans: {thin[:5]}",
        )
    )
    violations, stats = n4_bundle_audit(packets, elig)
    results.append(
        _result(
            "N4.source_grounded_bundles_only",
            PASS if not violations else FAIL,
            f"{stats['closures_checked']} closure(s) audited, {stats['linked_spans_used']} linked span(s) used; violations: {violations[:8]}",
            **stats,
        )
    )
    return results


def n4_bundle_audit(packets: list[dict], elig: list[dict]) -> tuple[list[dict], dict]:
    """Audit every closure: one packet only; every span located and verbatim; core spans own-attributed; every LINKED span
    backed by a verified link (basis type + designator + preserved rationale) and used only in a descriptive slot."""
    by_id = {p["packet_id"]: p for p in packets}
    violations: list[dict] = []
    checked = linked_used = 0
    for e in elig:
        packet = by_id.get(e["packet_id"])
        if packet is None:
            continue
        parts = {pt["span_id"]: pt for pt in packet["parts"]}
        verified_links = {lk["link_id"]: lk for lk in packet.get("links", []) if lk.get("verified")}
        for uid, entry in e["per_unit"].items():
            if entry["status"] != "directly_establishes":
                continue
            checked += 1
            for slot, ids in entry["slot_spans"].items():
                for sid in ids:
                    where = {
                        "packet_id": e["packet_id"],
                        "child_id": e["child_id"],
                        "unit_id": uid,
                        "slot": slot,
                        "span": sid,
                    }
                    part = parts.get(sid)
                    if part is None:
                        violations.append({**where, "violation": "span_outside_its_packet"})
                        continue
                    if not part.get("pieces") or any(
                        not pc.get("verbatim_ok") or pc.get("chunk_id") is None or pc.get("start") is None
                        for pc in part["pieces"]
                    ):
                        violations.append({**where, "violation": "locator_or_verbatim_check_missing"})
                    if part["role"] == "linked_definition":
                        linked_used += 1
                        link = verified_links.get(part.get("linked_from"))
                        if link is None:
                            violations.append({**where, "violation": "linked_span_without_a_verified_source_link"})
                        elif not (link["basis"].get("type") and link["basis"].get("designator") and part.get("note")):
                            violations.append({**where, "violation": "link_rationale_not_preserved"})
                        if slot not in closure.LINKABLE_SLOTS:
                            violations.append({**where, "violation": "linked_span_in_a_finding_bearing_slot"})
                    elif packet["part_attribution"].get(sid) != at.OWN_ESTABLISHED:
                        violations.append({**where, "violation": "core_span_not_own_established"})
    return violations, {"closures_checked": checked, "linked_spans_used": linked_used}
