"""Final audit of the overview artifact against the sealed ledger and the rendered files.

Everything deterministic is RE-DERIVED from the sealed ledger and compared with the stored artifact: the passage units and
their eligibility, every proposal's deterministic screen result, the NLI verdict from the stored scores, the derived state,
part statuses and items, and both rendered files byte-for-byte. The NLI scores themselves are recorded values (a model was
run), exactly as source verification's scores are recorded values. A pass means the artifact is internally consistent and
was produced by these rules; it is screening, not proof that any statement is semantically correct.

Every check runs through ``_check``: a malformed or tampered record that makes a re-derivation raise is a FAILED check,
never an audit crash (an audit that can be crashed can be bypassed).
"""

from __future__ import annotations

import hashlib
import json

from experiments.ask_cli_revised import overview as ov
from experiments.ask_cli_revised import overview_evidence as oe
from experiments.ask_cli_revised import overview_guards as guards
from experiments.ask_cli_revised.ledger_renderer import _literal
from experiments.ask_cli_revised.overview_render import detailed_inspection, researcher_answer


def sealed_hash_of(sealed: dict) -> str:
    return hashlib.sha256(json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _norm(value):
    return json.loads(json.dumps(value))


def audit_overview(sealed: dict, sealed_hash: str, overview: dict, answer_md: str, detail_md: str) -> dict:
    checks: dict[str, bool] = {}
    problems: list[str] = []

    def _check(name: str, fn) -> None:
        try:
            checks[name] = bool(fn())
        except Exception as exc:  # noqa: BLE001 - a record that breaks a re-derivation has failed the audit
            checks[name] = False
            problems.append(f"{name}: could not be re-derived from the stored record ({type(exc).__name__})")

    states = sealed["obligation_states"]
    question = sealed["request_contract"]["original_question"]
    units, claims = oe.build_units(sealed)
    ov.select_for_prompt(units, claims, question, states)
    sent = {u["unit_id"]: u for u in units if u["sent_to_model"]}
    part_ids = {s["field_id"] for s in states}

    _check("overview_hash_matches_content", lambda: ov.canonical_hash(overview) == overview.get("overview_hash"))
    _check(
        "references_the_sealed_ledger",
        lambda: overview.get("sealed_ledger_hash") == sealed_hash == sealed_hash_of(sealed),
    )
    _check(
        "passages_and_claims_match_the_ledger",
        lambda: _norm(units) == overview["units"] and _norm(claims) == overview["claims"],
    )

    def proposals_rescreen() -> bool:
        ok = True
        for p in overview["proposals"]:
            screen = guards.screen(
                {"text": p["text"], "unit_ids": p["unit_ids"], "bears_on": p["bears_on"]}, units=sent, part_ids=part_ids
            )
            nli = p.get("nli")
            nli_expected = guards.nli_reasons(nli["support"], nli["contradiction"]) if nli else []
            status = "withheld" if [*screen, *nli_expected] else "grounded"
            if screen != p["screen_reasons"] or nli_expected != p["nli_reasons"] or status != p["status"]:
                ok = False
                problems.append(f"proposal {p['index']}: stored screen/status differ from re-derivation")
            if nli is None and status == "grounded":
                ok = False
                problems.append(f"proposal {p['index']}: grounded without an NLI score")
        return ok

    _check("every_proposal_rescreens_to_its_stored_status", proposals_rescreen)

    def derived_consistent() -> bool:
        proposals = overview["proposals"]
        displayed = [p["index"] for p in proposals if p["status"] == "grounded"]
        cited = {u for i in displayed for u in proposals[i]["unit_ids"]}
        return (
            overview["displayed"] == displayed
            and overview["partial"] == (bool(displayed) and len(displayed) < len(proposals))
            and overview["single_passage"] == (len(cited) == 1)
            and _norm(overview["parts"]) == _norm(ov.parts_status(states, units, proposals))
            and (overview["state"] == "ok") == bool(displayed)
        )

    _check("derived_fields_consistent", derived_consistent)
    _check(
        "displayed_statements_cite_sent_passages",
        lambda: all(u in sent for i in overview["displayed"] for u in overview["proposals"][i]["unit_ids"]),
    )
    _check("researcher_answer_matches_render", lambda: answer_md == researcher_answer(sealed, overview)[0])
    _check("detailed_inspection_matches_render", lambda: detail_md == detailed_inspection(sealed, overview))

    def no_withheld_in_answer() -> bool:
        leaked = [
            p["index"]
            for p in overview["proposals"]
            if p["status"] == "withheld" and _literal(str(p["text"])) in answer_md
        ]
        if leaked:
            problems.append(f"withheld statement(s) {leaked} appear in the researcher-facing answer")
        return not leaked

    _check("no_withheld_statement_in_the_answer", no_withheld_in_answer)
    _check(
        "scope_statement_in_the_answer",
        lambda: "makes no statement about what the library or the literature holds" in answer_md,
    )
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "problems": problems,
        "screening_not_proof": True,
        "note": ov.SCREENING_NOTE,
    }
