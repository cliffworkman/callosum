"""Reference/navigation eligibility for the focused-discovery evidence routes (reference-exclusion repair).

Replaces three defects found by the q_lld reference-leakage investigation (2026-10-28), without touching any
frozen run:

* native Docling exclusions were transferred onto PyMuPDF chunks by exact ``str.find`` (82.9% of
  ``exclude_reference`` actions mapped to nothing) -> ``map_native_regions`` matches in the shared normalized
  comparison key, keeps exact original offsets, and records ambiguous/partial/failed states;
* a chunk was withheld only if it equalled ONE region -> union coverage via the shared ``decide``;
* the anchored ``chunk_structure`` labels were never consumed -> ``legacy_anchored_state`` (direct, by chunk id
  with freshness) and ``guarded_anchored_state`` (a verified text-level join; page overlap is never enough).

Policy and thresholds live in ``app.backend.summarization.evidence_eligibility`` so the application and this
research route share one implementation. Everything here is pure; ``reference_eligibility_cli`` owns file I/O.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable

from app.backend.summarization.evidence_eligibility import (
    ANCHORED_COVERAGE_THRESHOLD,
    DEMOTED_ANCHORED_ROLES,
    JOIN_VERIFIED_COVERAGE,
    NAVIGATION_DECISIONS,
    POLICY_VERSION,
    REFERENCE_DECISIONS,
    AnchoredState,
    EligibilityDecision,
    KeyedText,
    NativeCoverage,
    map_region,
    select_slots,
    union_coverage,
)

MAPPED_DECISIONS = REFERENCE_DECISIONS | NAVIGATION_DECISIONS
# Maximum tolerated fraction of native exclude_reference regions left with no confident unit mapping. Derived
# from the repaired mapper's measured corpus distribution (see REGRESSION_VALIDATION_RESULTS.json); the as-run
# exact-substring sidecar left 82.9% unmapped and would fail this check outright.
MAX_UNMAPPED_REFERENCE_FRACTION = 0.10
INCOMPATIBLE_SOURCE_ROLES = frozenset({"reference_entry", "reference_heading", "page_header", "page_footer", "heading"})


def _pages(unit: dict) -> set[int]:
    if unit.get("pages"):
        return {int(p) for p in unit["pages"]}
    if unit.get("page_start") and unit.get("page_end"):
        return set(range(int(unit["page_start"]), int(unit["page_end"]) + 1))
    return set()


def map_native_regions(units: list[dict], regions_by_attachment: dict[int, list[dict]]) -> tuple[dict, list[dict]]:
    """Map native reference/navigation regions onto units (same attachment, overlapping declared pages).

    Returns ``(coverage_by_unit_id, region_ledger)``. Every mapped region keeps its native id, decision and text
    hash; every unmapped region is listed with the reason, so an exclusion can never silently disappear.
    """
    by_attachment: dict[int, list[tuple[dict, KeyedText]]] = defaultdict(list)
    for unit in units:
        by_attachment[int(unit["attachment_id"])].append((unit, KeyedText.build(str(unit["id"]), unit["text"])))
    matches: dict[int, list] = defaultdict(list)
    ledger = []
    for attachment_id, regions in regions_by_attachment.items():
        candidates = by_attachment.get(int(attachment_id), [])
        for region in regions:
            if region["retrieval_decision"] not in MAPPED_DECISIONS:
                continue
            keyed = KeyedText.build(region["id"], region["text"])
            pages = set(region.get("declared_pages") or [])
            states: dict[str, int] = defaultdict(int)
            matched_units = []
            for unit, unit_key in candidates:
                if pages and not (pages & _pages(unit)):
                    continue
                state, match = map_region(keyed, region["retrieval_decision"], unit_key)
                states[state] += 1
                if match is not None:
                    matches[unit["id"]].append(match)
                    matched_units.append({"unit_id": unit["id"], "match_kind": match.kind})
            if matched_units:
                status = "mapped_multiple_units" if len(matched_units) > 1 else "mapped"
            elif states.get("ambiguous_repeated_in_unit"):
                status = "ambiguous_repeated_text_unmapped"
            elif states.get("region_too_short") or len(keyed.key) < 25:
                status = "region_too_short_unmapped"
            elif not states:
                status = "no_page_concordant_unit"
            else:
                status = "no_normalized_match"
            ledger.append(
                {
                    "attachment_id": int(attachment_id),
                    "region_id": region["id"],
                    "decision": region["retrieval_decision"],
                    "source_role": region.get("source_role"),
                    "declared_pages": sorted(pages),
                    "text_sha256": keyed.text_sha256,
                    "status": status,
                    "matched_units": matched_units,
                }
            )
    coverage = {}
    for unit, unit_key in (pair for pairs in by_attachment.values() for pair in pairs):
        coverage[unit["id"]] = NativeCoverage(len(unit_key.key), tuple(matches.get(unit["id"], ())))
    return coverage, ledger


def mapping_audit(ledger: list[dict], *, bound: float = MAX_UNMAPPED_REFERENCE_FRACTION) -> dict:
    """Corpus and per-document mapping accounting for native reference exclusions; ``passed`` gates preparation."""
    per_doc: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in ledger:
        if row["decision"] in REFERENCE_DECISIONS:
            per_doc[row["attachment_id"]][row["status"]] += 1
    total = sum(sum(v.values()) for v in per_doc.values())
    unmapped = sum(n for v in per_doc.values() for s, n in v.items() if not s.startswith("mapped"))
    fraction = unmapped / total if total else 0.0
    return {
        "reference_regions": total,
        "unmapped_reference_regions": unmapped,
        "unmapped_fraction": round(fraction, 4),
        "bound": bound,
        "passed": fraction <= bound,
        "status_counts": dict(
            sorted({s: sum(v.get(s, 0) for v in per_doc.values()) for d in per_doc.values() for s in d}.items())
        ),
        "worst_documents": sorted(
            (
                {
                    "attachment_id": a,
                    "reference_regions": sum(v.values()),
                    "unmapped": sum(n for s, n in v.items() if not s.startswith("mapped")),
                }
                for a, v in per_doc.items()
            ),
            key=lambda r: -(r["unmapped"] / max(r["reference_regions"], 1)),
        )[:10],
    }


def legacy_anchored_state(chunk_id: int, role_states: dict, *, text_sha256: str | None = None) -> AnchoredState:
    """Anchored evidence for a legacy chunk, joined directly by chunk id and validated for freshness.

    ``role_states`` comes from ``chunk_structure_repo.structure_role_states`` (current vs stale with reason). When
    the caller also knows the delivered text hash, a mismatch against the classified text makes the row stale.
    """
    state = role_states.get(int(chunk_id))
    if state is None:
        return AnchoredState("absent")
    detail = {"legacy_chunk_ids": [int(chunk_id)], "roles": [state.evidence_role], "chunk_types": [state.chunk_type]}
    if state.state != "current":
        return AnchoredState("stale", 0.0, {**detail, "stale_reason": state.stale_reason})
    if text_sha256 is not None and state.raw_sha != text_sha256:
        return AnchoredState("stale", 0.0, {**detail, "stale_reason": "delivered_text_hash"})
    if state.evidence_role in DEMOTED_ANCHORED_ROLES:
        return AnchoredState("current_bibliographic", 1.0, detail)
    return AnchoredState("current_other", 0.0, detail)


def guarded_anchored_state(
    unit: dict, legacy_chunks: Iterable[dict], role_states: dict, *, keyed: dict[int, KeyedText] | None = None
) -> AnchoredState:
    """Anchored evidence for a guarded (Docling) unit through a VERIFIED text-level join to legacy chunks.

    Each page-concordant legacy chunk is mapped onto the unit in comparison-key space. The join is verified only
    when matched legacy spans cover >= ``JOIN_VERIFIED_COVERAGE`` of the unit; otherwise the state is
    ``join_unresolved`` and the anchored label is not used. Being on a bibliography page is never evidence.
    """
    unit_key = KeyedText.build(str(unit["research_chunk_id"]), unit["text"])
    pages = _pages(unit)
    joined, demoted, stale, roles, ids = [], [], [], set(), []
    for chunk in legacy_chunks:
        if pages and not (pages & _pages(chunk)):
            continue
        chunk_key = (keyed or {}).get(int(chunk["id"])) or KeyedText.build(str(chunk["id"]), chunk["text"])
        state, match = map_region(chunk_key, "legacy_chunk", unit_key)
        if match is None:
            continue
        joined.append(match)
        ids.append(int(chunk["id"]))
        role = role_states.get(int(chunk["id"]))
        if role is None:
            continue
        if role.state != "current":
            stale.append({"legacy_chunk_id": int(chunk["id"]), "stale_reason": role.stale_reason})
            continue
        roles.add(role.evidence_role)
        if role.evidence_role in DEMOTED_ANCHORED_ROLES:
            demoted.append(match)
    join = union_coverage(len(unit_key.key), joined)
    coverage = union_coverage(len(unit_key.key), demoted)
    detail = {
        "join": "normalized_text",
        "join_coverage": round(join, 4),
        "legacy_chunk_ids": sorted(set(ids)),
        "roles": sorted(roles),
    }
    if stale:
        detail["stale_legacy_rows"] = stale
    if join < JOIN_VERIFIED_COVERAGE:
        return AnchoredState("join_unresolved", coverage, detail)
    if coverage >= ANCHORED_COVERAGE_THRESHOLD:
        return AnchoredState("current_bibliographic", coverage, detail)
    if coverage > 0:
        return AnchoredState("current_partial", coverage, detail)
    if not roles and stale:
        return AnchoredState("stale", 0.0, detail)
    return AnchoredState("current_other" if roles else "absent", 0.0, detail)


def continuation_flags(regions: list[dict]) -> set[str]:
    """Included native regions sandwiched between excluded reference entries (ignoring navigation regions).

    Flag-only context signal for continuation fragments such as ``a11 #/texts/130``/``#/texts/139``; it never
    withholds or demotes on its own, because its precision is unmeasured.
    """
    flagged = set()
    content = [r for r in regions if r["retrieval_decision"] not in NAVIGATION_DECISIONS]
    for previous, region, following in zip(content, content[1:], content[2:], strict=False):
        if (
            region["retrieval_decision"].startswith("include")
            and previous["retrieval_decision"] in REFERENCE_DECISIONS
            and following["retrieval_decision"] in REFERENCE_DECISIONS
        ):
            flagged.add(region["id"])
    return flagged


def authority_record(namespace: str, decisions: dict[str, EligibilityDecision], inputs: dict) -> dict:
    """Sealed, independently constructed eligibility authority (consumed by selection AND validation)."""
    body = {
        "version": "reference-eligibility-authority-v1",
        "policy_version": POLICY_VERSION,
        "namespace": namespace,
        "inputs": inputs,
        "decisions": {uid: d.as_record() for uid, d in sorted(decisions.items())},
    }
    body["authority_sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


def allocate_packet(
    order: list, ranking: dict, decisions: dict[str, EligibilityDecision], *, eligible_unit, papers=12, per_paper=6
) -> dict:
    """The frozen q_lld allocation rule (12 nominated papers x 6 whole units) with eligibility-aware slots.

    ``eligible_unit(chunk_id)`` reproduces the frozen non-eligibility filters (source availability, pages,
    frozen whole-unit skip list) so the only change is the eligibility policy. Returns per-paper selections.
    """
    selected = []
    for paper in order:
        ranked = [str(r["chunk_id"]) for r in ranking["papers"].get(str(paper), []) if eligible_unit(r["chunk_id"])]
        if not ranked:
            continue
        slots = select_slots(ranked, decisions, per_paper)
        if not slots.selected:
            selected.append({"paper_id": paper, "slots": slots, "skipped": True})
            continue
        selected.append({"paper_id": paper, "slots": slots, "skipped": False})
        if sum(not s["skipped"] for s in selected) == papers:
            break
    return {"papers": selected}


def validate_claims(parsed: dict, evidence: dict[str, dict], authority: dict[tuple[str, str], dict]) -> list[dict]:
    """Mechanical citation/quotation validation against the independent eligibility authority.

    ``evidence``: delivered records by source_id. ``authority``: ``{(namespace, unit_id): decision record}``. Every
    finding is mechanical; none asserts that a source supports a claim scientifically.
    """
    findings = []

    def add(claim, sid, kind, **extra):
        findings.append({"claim_id": claim.get("claim_id"), "source_id": sid, "finding": kind, **extra})

    def lookup(record):
        return authority.get((record["original_unit_namespace"], str(record["internal_unit_id"])))

    for claim in parsed.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for sid in claim.get("citations") or []:
            if not sid:
                add(claim, sid, "missing_source_id")
                continue
            record = evidence.get(sid)
            if record is None:
                add(claim, sid, "source_not_delivered")
                continue
            if hashlib.sha256(record["text"].encode()).hexdigest() != record["text_sha256"]:
                add(claim, sid, "text_identity_mismatch")
            decision = lookup(record)
            if decision is None:
                add(claim, sid, "eligibility_unresolved")
                continue
            if decision["anchored"]["state"] == "stale":
                add(claim, sid, "classification_stale", detail=decision["anchored"].get("stale_reason"))
            if record.get("source_role") in INCOMPATIBLE_SOURCE_ROLES:
                add(claim, sid, "incompatible_source_role", source_role=record["source_role"])
            if decision["substantive_eligibility"] == "withheld":
                add(claim, sid, "ineligible_source_cited", decision=decision["decision"])
            elif decision["substantive_eligibility"] == "disputed":
                add(claim, sid, "disputed_eligibility_cited", decision=decision["decision"])
        for quote in claim.get("source_quotes") or []:
            sid = quote.get("source_id") if isinstance(quote, dict) else None
            text = quote.get("quote") if isinstance(quote, dict) else None
            if not sid:
                add(claim, sid, "missing_source_id")
                continue
            record = evidence.get(sid)
            if record is None:
                add(claim, sid, "quote_source_not_delivered")
                continue
            exact = isinstance(text, str) and bool(text) and text in record["text"]
            decision = lookup(record)
            status = decision["substantive_eligibility"] if decision else "unresolved"
            if not exact:
                add(claim, sid, "inexact_quotation")
            if status == "withheld":
                add(
                    claim,
                    sid,
                    "exact_quote_from_ineligible_source" if exact else "inexact_quote_attributed_to_ineligible_source",
                )
            elif status == "disputed":
                add(claim, sid, "quote_from_disputed_source", exact=exact)
            elif status == "unresolved":
                add(claim, sid, "quote_eligibility_unresolved")
            elif exact and decision["excluded_spans"]:
                start = record["text"].find(text)
                end = start + len(text)
                hit = [s for s in decision["excluded_spans"] if start < s["end"] and s["start"] < end]
                if hit:
                    add(claim, sid, "exact_quote_inside_excluded_span", regions=[s["region_id"] for s in hit])
    return findings
