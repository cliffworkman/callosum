"""Latent funding-fit signal generation and deterministic diversification."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.backend.funding.domain import FundingMatchSignal, FundingProspect, HistoricalAward, ResearchFundingProfile
from app.backend.funding.irs import ui_award_record
from app.backend.funding.profile import FACET_KEYS

STRENGTH_VALUE = {"strong": 4.0, "moderate": 3.0, "weak": 2.0, "unresolved": 1.0, "conflict": -2.0}
FACET_SIGNAL = {
    "subjects": "portfolio_topic_overlap",
    "conditionsOrPhenomena": "portfolio_topic_overlap",
    "populations": "population_alignment",
    "methods": "method_modality_overlap",
    "dataModalities": "method_modality_overlap",
    "interventionModalities": "intervention_alignment",
    "supportStrategies": "support_strategy_fit",
    "activityTypes": "activity_type_fit",
    "disciplines": "portfolio_topic_overlap",
    "geographies": "geography_signal",
}


class LatentFundingFitEngine:
    def generate(
        self,
        profile: ResearchFundingProfile,
        awards: list[HistoricalAward],
    ) -> tuple[list[FundingProspect], list[FundingProspect]]:
        by_org: dict[str, list[HistoricalAward]] = defaultdict(list)
        for award in awards:
            by_org[award.organization_name].append(award)
        recipient_signals = _recipient_neighborhood_signals(profile, awards)
        cofunding_signals = _cofunding_neighborhood_signals(profile, awards)
        prospects: list[FundingProspect] = []
        schemes: list[FundingProspect] = []
        for org, org_awards in by_org.items():
            signals = _signals_for_org(profile, org_awards)
            signals.extend(recipient_signals.get(org, []))
            signals.extend(cofunding_signals.get(org, []))
            signals = sorted(signals, key=lambda s: s.ordering_value, reverse=True)
            recurrence = _recurrence_signals(org_awards)
            if recurrence:
                schemes.extend(
                    FundingProspect(
                        organization_name=org,
                        scheme_name=item["scheme_name"],
                        prospect_kind="scheme",
                        signals=[item["signal"]],
                        evidence_freshness=_freshness(org_awards),
                        identity_resolution_quality="medium",
                    )
                    for item in recurrence
                )
            if signals:
                prospects.append(
                    FundingProspect(
                        organization_name=org,
                        prospect_kind="organization",
                        signals=signals,
                        evidence_freshness=_freshness(org_awards),
                        identity_resolution_quality="medium",
                    )
                )
        return _diversify(prospects), _diversify(schemes)


def _signals_for_org(profile: ResearchFundingProfile, awards: list[HistoricalAward]) -> list[FundingMatchSignal]:
    matches_by_type: dict[str, list[tuple[str, str, HistoricalAward]]] = defaultdict(list)
    for key in FACET_KEYS:
        for facet in profile.facets.get(key, []):
            needle = facet.normalized_value.lower()
            for award in awards:
                haystack = " ".join([award.title or "", award.purpose_text or "", award.scheme_name or ""]).lower()
                if needle and needle in haystack:
                    matches_by_type[FACET_SIGNAL.get(key, "portfolio_topic_overlap")].append(
                        (key, facet.normalized_value, award)
                    )
    signals: list[FundingMatchSignal] = []
    for signal_type, matches in matches_by_type.items():
        distinct_facets = {(k, v) for k, v, _ in matches}
        evidence = _unique_awards([m[2] for m in matches])
        strength = "strong" if len(distinct_facets) >= 3 else "moderate" if len(distinct_facets) == 2 else "weak"
        label = _signal_label(signal_type)
        explanation = f"{len(evidence)} historical award record(s) matched {label} evidence."
        if signal_type == "scholarly_lineage":
            explanation = f"{len(evidence)} related work(s) were linked to award evidence from this funder."
        signals.append(
            FundingMatchSignal(
                signal_type=signal_type,
                strength=strength,
                explanation=explanation,
                matched_profile_facets=[{"facet": k, "value": v} for k, v in sorted(distinct_facets)],
                matched_evidence=[ui_award_record(a) for a in evidence[:5]],
                provenance=[p.to_dict() for a in evidence for p in a.provenance][:5],
                ordering_value=_ordering(signal_type, strength, distinct_facets, evidence),
            )
        )
    if awards and signals:
        signals.append(
            FundingMatchSignal(
                signal_type="scholarly_lineage",
                strength="weak",
                explanation=f"{len(awards)} funding lineage or historical award record(s) contributed evidence.",
                matched_evidence=[ui_award_record(a) for a in _unique_awards(awards)[:3]],
                provenance=[p.to_dict() for a in awards for p in a.provenance][:5],
                ordering_value=1.2,
            )
        )
    return sorted(signals, key=lambda s: s.ordering_value, reverse=True)


def _cofunding_neighborhood_signals(
    profile: ResearchFundingProfile,
    awards: list[HistoricalAward],
) -> dict[str, list[FundingMatchSignal]]:
    matched_funders = {award.organization_name for award in awards if _award_matches_profile(profile, award)}
    if not matched_funders:
        return {}
    recipients_by_funder = _recipients_by_funder(awards)
    matched_recipients = {
        recipient
        for funder, recipients in recipients_by_funder.items()
        if funder in matched_funders
        for recipient in recipients
    }
    if not matched_recipients:
        return {}
    signals: dict[str, list[FundingMatchSignal]] = {}
    for funder, recipients in recipients_by_funder.items():
        if funder in matched_funders:
            continue
        shared = recipients & matched_recipients
        if not shared:
            continue
        evidence = _awards_for_recipients(awards, funder, shared)
        signals[funder] = [
            FundingMatchSignal(
                signal_type="cofunding_proximity",
                strength="weak" if len(shared) == 1 else "moderate",
                explanation=(
                    f"This funder appears in recipient neighborhoods also supported by {len(matched_funders)} "
                    "funder(s) with direct profile-matched evidence."
                ),
                matched_evidence=[ui_award_record(a) for a in evidence[:5]],
                provenance=[p.to_dict() for a in evidence for p in a.provenance][:5],
                ordering_value=2.2 + min(len(shared), 3) * 0.2,
            )
        ]
    return signals


def _recipient_neighborhood_signals(
    profile: ResearchFundingProfile,
    awards: list[HistoricalAward],
) -> dict[str, list[FundingMatchSignal]]:
    matched = [award for award in awards if _award_matches_profile(profile, award)]
    related_recipients = {_recipient_key(award): award for award in matched if _recipient_key(award) is not None}
    if not related_recipients:
        return {}
    by_org: dict[str, list[HistoricalAward]] = defaultdict(list)
    for award in awards:
        key = _recipient_key(award)
        if key is None or key not in related_recipients:
            continue
        if award in matched:
            continue
        by_org[award.organization_name].append(award)
    signals: dict[str, list[FundingMatchSignal]] = {}
    for org, rows in by_org.items():
        evidence = _unique_awards(rows)
        recipients = sorted({a.ui_recipient() for a in evidence if a.ui_recipient()})
        signals[org] = [
            FundingMatchSignal(
                signal_type="recipient_similarity",
                strength="weak" if len(recipients) == 1 else "moderate",
                explanation=(
                    f"This funder supported {len(recipients)} organization(s) that also appear in related "
                    "historical funding evidence."
                ),
                matched_evidence=[ui_award_record(a) for a in evidence[:5]],
                provenance=[p.to_dict() for a in evidence for p in a.provenance][:5],
                ordering_value=2.4 + min(len(recipients), 3) * 0.25,
            )
        ]
    return signals


def _recurrence_signals(awards: list[HistoricalAward]) -> list[dict[str, Any]]:
    by_scheme: dict[str, list[HistoricalAward]] = defaultdict(list)
    for award in awards:
        if award.scheme_name:
            by_scheme[award.scheme_name].append(award)
    out: list[dict[str, Any]] = []
    for scheme, rows in by_scheme.items():
        years = sorted({a.tax_year for a in rows if a.tax_year})
        if len(years) < 2:
            continue
        cadence = "annual" if all((b - a) == 1 for a, b in zip(years, years[1:], strict=False)) else "irregular"
        strength = "strong" if len(years) >= 3 and cadence == "annual" else "moderate"
        evidence = _unique_awards(rows)
        signal = FundingMatchSignal(
            signal_type="scheme_recurrence",
            strength=strength,
            explanation="Recurring scheme detected from prior cycles. No current application window verified.",
            matched_evidence=[ui_award_record(a) for a in evidence],
            provenance=[p.to_dict() for a in evidence for p in a.provenance][:5],
            ordering_value=3.0 + min(len(years), 4) * 0.2,
        )
        out.append({"scheme_name": scheme, "signal": signal})
    return out


def _ordering(
    signal_type: str,
    strength: str,
    distinct_facets: set[tuple[str, str]],
    evidence: list[HistoricalAward],
) -> float:
    base = STRENGTH_VALUE[strength]
    specificity = len({k for k, _ in distinct_facets}) * 0.6
    support_bonus = 0.8 if signal_type == "support_strategy_fit" else 0.0
    capped_quantity = math.log1p(min(len(evidence), 4)) * 0.2
    broad_penalty = -0.4 if len(distinct_facets) <= 1 and len(evidence) > 20 else 0.0
    return base + specificity + support_bonus + capped_quantity + broad_penalty


def _diversify(items: list[FundingProspect]) -> list[FundingProspect]:
    def key(item: FundingProspect) -> float:
        best = max((s.ordering_value for s in item.signals), default=0.0)
        breadth = len({f["facet"] for s in item.signals for f in s.matched_profile_facets})
        return best + min(breadth, 4) * 0.15

    return sorted(items, key=key, reverse=True)[:20]


def _unique_awards(awards: list[HistoricalAward]) -> list[HistoricalAward]:
    seen: set[str] = set()
    out: list[HistoricalAward] = []
    for award in awards:
        key = f"{award.source_kind}:{award.source_record_id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(award)
    return out


def _recipients_by_funder(awards: list[HistoricalAward]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for award in awards:
        key = _recipient_key(award)
        if key is not None:
            out[award.organization_name].add(key)
    return out


def _awards_for_recipients(
    awards: list[HistoricalAward],
    funder: str,
    recipients: set[str],
) -> list[HistoricalAward]:
    return [
        award
        for award in awards
        if award.organization_name == funder and (key := _recipient_key(award)) is not None and key in recipients
    ]


def _award_matches_profile(profile: ResearchFundingProfile, award: HistoricalAward) -> bool:
    text = " ".join([award.title or "", award.purpose_text or "", award.scheme_name or ""]).lower()
    for values in profile.facets.values():
        if any(f.normalized_value.lower() in text for f in values):
            return True
    return False


def _recipient_key(award: HistoricalAward) -> str | None:
    if award.recipient_is_individual:
        return None
    recipient = award.ui_recipient()
    if not recipient:
        return None
    normalized = " ".join(str(recipient).lower().split())
    return normalized or None


def _freshness(awards: list[HistoricalAward]) -> str:
    years = [a.tax_year for a in awards if a.tax_year]
    if not years:
        return "unknown"
    return "fresh" if max(years) >= 2023 else "stale"


def _signal_label(signal_type: str) -> str:
    return signal_type.replace("_", " ")
