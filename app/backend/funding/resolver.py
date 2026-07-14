"""Opportunity resolution for Funding Discovery."""

from __future__ import annotations

from sqlalchemy import Connection

from app.backend.funding.domain import (
    ApplicationSurface,
    FundingOpportunity,
    FundingProspect,
    ProviderStatus,
    ResearchFundingProfile,
)
from app.backend.funding.providers import GrantsGovClient


class OpportunityResolver:
    """Separate current application evidence from latent prospect evidence."""

    def __init__(self, grants_gov: GrantsGovClient | None = None) -> None:
        self.grants_gov = grants_gov or GrantsGovClient()

    def resolve(
        self,
        conn: Connection,
        profile: ResearchFundingProfile,
        prospects: list[FundingProspect],
        recurring_schemes: list[FundingProspect],
    ) -> tuple[
        list[FundingOpportunity],
        list[FundingProspect],
        list[FundingProspect],
        list[ApplicationSurface],
        list[ProviderStatus],
    ]:
        opportunities, status = self.grants_gov.search_opportunities(conn, profile)
        surfaces: list[ApplicationSurface] = []
        for opp in opportunities:
            surfaces.append(
                ApplicationSurface(
                    organization_name=opp.organization_name,
                    surface_type="official_api",
                    actionability="open_opportunity" if opp.status in {"open", "forecasted"} else "unknown",
                    access_mode="open_rfp" if opp.status in {"open", "forecasted"} else "unknown",
                    url=opp.source_url,
                    details=f"Current opportunity status was provided by {opp.provider_id}.",
                    provenance=opp.provenance,
                )
            )
        for scheme in recurring_schemes:
            surfaces.append(
                ApplicationSurface(
                    organization_name=scheme.organization_name,
                    scheme_name=scheme.scheme_name,
                    surface_type="unknown",
                    actionability="recurring_scheme",
                    access_mode="unknown",
                    details="Recurring scheme detected from prior cycles. No current application window verified.",
                    provenance=[],
                )
            )
        return opportunities, recurring_schemes, prospects, surfaces, [status]
