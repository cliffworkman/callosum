"""Funding Discovery vertical-slice tests."""

from __future__ import annotations

import csv
import io
import json

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app.backend.acquisition.registry import PaperRef
from app.backend.api import create_app
from app.backend.funding.domain import ApplicationSurface, HistoricalAward, ProvenanceRecord
from app.backend.funding.engine import LatentFundingFitEngine
from app.backend.funding.identity import OrganizationCandidate, resolve_organization
from app.backend.funding.irs import parse_990pf_xml, parse_eo_bmf_csv, ui_award_record
from app.backend.funding.llm_triage import FundingLlmTriageEvaluator
from app.backend.funding.profile import profile_from_text
from app.backend.funding.providers import (
    CrossrefFundingProvider,
    FixtureAwardHistoryProvider,
    GrantsGovClient,
    OpenAlexFundingProvider,
    RorIdentityProvider,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import funding_opportunities, saved_funding_refresh_events
from integrations.openalex import OpenAlexClient


def _prov(rid="r1"):
    return [ProvenanceRecord("fixture", rid, "2026-07-10T00:00:00Z", extraction_method="deterministic_parse")]


def test_ui_award_record_exposes_source_metadata_without_individual_pii():
    award = HistoricalAward(
        "Careful Foundation",
        "irs_990_pf",
        "pf-source-1",
        purpose_text="pilot awards for community implementation",
        amount={"value": 75000, "currency": "USD"},
        tax_year=2024,
        recipient_name_raw="Jane Recipient",
        recipient_is_individual=True,
        scheme_name="Pilot Awards",
        award_number="A-1",
        provenance=[
            ProvenanceRecord(
                "irs-990-pf",
                "pf-source-1",
                "2026-07-12T00:00:00Z",
                source_url="https://example.org/pf-source-1",
                source_field="grants_paid",
                extraction_method="deterministic_parse",
            )
        ],
    )

    row = ui_award_record(award)

    assert row["source_url"] == "https://example.org/pf-source-1"
    assert row["provider_id"] == "irs-990-pf"
    assert row["source_field"] == "grants_paid"
    assert row["scheme_name"] == "Pilot Awards"
    assert row["award_number"] == "A-1"
    assert row["amount"] == {"value": 75000, "currency": "USD"}
    assert row["recipient_withheld"] is True
    assert row["recipient_name"] is None
    assert "Jane Recipient" not in json.dumps(row)


def test_research_funding_profile_facets_and_provenance():
    profile = profile_from_text(
        "Pilot community-based adolescent mental health implementation using neuroimaging and secondary analysis.",
        field="clinical neuroscience",
    )
    facets = {k: [f.normalized_value for f in v] for k, v in profile.facets.items()}
    assert "adolescents" in facets["populations"]
    assert "neuroimaging" in facets["methods"]
    assert "pilot" in facets["supportStrategies"]
    assert "community partnership" in facets["supportStrategies"]
    assert profile.provenance[0].extraction_method == "deterministic_parse"
    assert not profile.applicant_context


def test_short_field_description_and_missing_abstract_paper_profile(temp_db_url):
    profile = profile_from_text("manuscript digitization", field="humanities")
    assert any(f.normalized_value == "humanities" for f in profile.facets["disciplines"])
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Freshwater eDNA infrastructure", csl_json={"title": "x"}, abstract=None)
        from app.backend.funding.profile import profile_from_paper

        paper_profile = profile_from_paper(conn, pid)
    engine.dispose()
    assert paper_profile is not None
    assert any(f.normalized_value == "environmental dna" for f in paper_profile.facets["methods"])


def test_organization_identity_keeps_ambiguity_and_exact_ids():
    candidates = [
        OrganizationCandidate("Alpha Foundation", {"ein": "123456789"}, ["Alpha"]),
        OrganizationCandidate("Alpha Trust", {"ror": "https://ror.org/abc"}, ["Alpha"]),
    ]
    assert resolve_organization("x", candidates, ein="12-3456789")[0].resolution_basis == "exact_ein"
    assert resolve_organization("x", candidates, ror="https://ror.org/abc")[0].resolution_basis == "exact_ror"
    ambiguous = resolve_organization("Alpha", candidates)
    assert len(ambiguous) == 2 and all(c.resolution_status == "ambiguous" for c in ambiguous)
    unresolved = resolve_organization("Unknown Funder", candidates)
    assert unresolved[0].resolution_status == "unresolved"


def test_grants_gov_success_empty_failure_and_private_text_minimization(temp_db_url):
    calls = []

    def fetcher(url, *, json, params, timeout):
        calls.append(json)
        return 200, {
            "data": {
                "oppHits": [
                    {
                        "id": "123",
                        "title": "Pilot implementation opportunity",
                        "agencyName": "Agency",
                        "oppStatus": "posted",
                        "closeDate": "2026-09-01",
                    }
                ]
            }
        }

    token = "SECRETABSTRACTTOKEN"
    profile = profile_from_text(f"{token} pilot implementation adolescent work", field="neuroscience")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        opportunities, status = GrantsGovClient(fetcher=fetcher).search_opportunities(conn, profile)
    engine.dispose()
    assert status.status == "success" and opportunities[0].status == "open"
    assert opportunities[0].deadlines[0]["date"] == "2026-09-01"
    assert token not in json.dumps(calls)

    def bad_fetcher(url, *, json, params, timeout):
        return 500, {"error": "nope"}

    failure_profile = profile_from_text("equipment ecology field work", field="ecology")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        failed, failed_status = GrantsGovClient(fetcher=bad_fetcher).search_opportunities(conn, failure_profile)
    engine.dispose()
    assert failed == [] and failed_status.status == "failed"


def test_ror_identity_provider_resolves_and_retains_ambiguity(temp_db_url):
    def fetcher(url, *, params, headers, timeout):
        assert params["query"] == "Example Foundation"
        return 200, {
            "items": [
                {
                    "id": "https://ror.org/abc",
                    "names": [{"value": "Example Foundation", "types": ["ror_display"]}],
                    "external_ids": [{"type": "fundref", "all": ["100000001"]}],
                    "locations": [{"geonames_details": {"country_name": "United States", "name": "Boston"}}],
                }
            ]
        }

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        org, status = RorIdentityProvider(fetcher=fetcher).resolve(conn, "Example Foundation")
    engine.dispose()
    assert status.status == "success"
    assert org["resolution_status"] == "resolved"
    assert org["identifiers"]["ror"] == "https://ror.org/abc"
    assert org["identifiers"]["crossrefFunderId"] == "100000001"


def test_openalex_funding_provider_extracts_grants_and_failures(temp_db_url):
    def fetcher(url, *, params, headers, timeout):
        assert params["filter"] == "has_funder:true"
        return 200, {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "title": "Pilot adolescent implementation study",
                    "publication_year": 2024,
                    "grants": [
                        {
                            "funder_display_name": "Example Foundation",
                            "award_id": "OA-1",
                        }
                    ],
                },
                {"id": "https://openalex.org/W2", "title": "Malformed", "grants": [{"award_id": "missing"}]},
            ]
        }

    profile = profile_from_text("pilot adolescent implementation", field="education policy")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        awards, status = OpenAlexFundingProvider(fetcher=fetcher).search_awards(conn, profile)
    engine.dispose()
    assert status.status == "success" and status.result_count == 1
    assert awards[0].organization_name == "Example Foundation"
    assert awards[0].source_kind == "openalex_award"
    assert awards[0].tax_year == 2024

    def bad_fetcher(url, *, params, headers, timeout):
        return 429, {"error": "rate limited"}

    profile2 = profile_from_text("freshwater equipment", field="ecology")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        failed, failed_status = OpenAlexFundingProvider(fetcher=bad_fetcher).search_awards(conn, profile2)
    engine.dispose()
    assert failed == [] and failed_status.status == "failed"


def test_openalex_funding_provider_uses_selected_paper_related_work_lineage(temp_db_url):
    class RelatedFetcher:
        def __call__(self, path, *, params, headers, timeout):
            if path.startswith("/doi:"):
                return 200, {
                    "id": "https://openalex.org/W0",
                    "title": "Focal work",
                    "related_works": ["https://openalex.org/W10"],
                }
            if params.get("filter") == "openalex_id:W10":
                return 200, {
                    "results": [
                        {
                            "id": "https://openalex.org/W10",
                            "title": "Related adolescent implementation work",
                            "publication_year": 2024,
                            "grants": [{"funder_display_name": "Lineage Foundation", "award_id": "L-1"}],
                        }
                    ]
                }
            return 200, {"results": []}

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(
            conn,
            title="Adolescent implementation",
            csl_json={"title": "x", "DOI": "10.1/focal"},
            doi="10.1/focal",
            abstract="Implementation research with adolescents.",
        )
        from app.backend.funding.profile import profile_from_paper

        profile = profile_from_paper(conn, pid)
        awards, status = OpenAlexFundingProvider(
            fetcher=lambda *a, **k: (200, {"results": []}),
            client=OpenAlexClient(fetcher=RelatedFetcher(), mailto="test@example.org"),
        ).search_awards(conn, profile)
    engine.dispose()
    assert status.status == "success"
    assert [a.organization_name for a in awards] == ["Lineage Foundation"]
    assert awards[0].provenance[0].source_field == "related_works.grants"


def test_openalex_adapter_meta_preserves_grants(temp_db_url):
    body = {
        "id": "https://openalex.org/W1",
        "title": "Funded work",
        "publication_year": 2025,
        "grants": [{"funder_display_name": "Meta Foundation", "award_id": "M-1"}],
    }
    with make_engine(temp_db_url).begin() as conn:
        meta = OpenAlexClient(fetcher=lambda *a, **k: (200, body), mailto="test@example.org").fetch_work_meta_for(
            conn, PaperRef(doi="10.1/meta")
        )
    assert meta["grants"] == [{"funder_display_name": "Meta Foundation", "award_id": "M-1"}]


def test_crossref_funding_provider_extracts_awards_and_handles_missing_optional_fields(temp_db_url):
    def fetcher(url, *, params, headers, timeout):
        assert params["filter"] == "has-funder:true"
        return 200, {
            "message": {
                "items": [
                    {
                        "DOI": "10.1/example",
                        "title": ["Community partnership implementation"],
                        "issued": {"date-parts": [[2023]]},
                        "URL": "https://doi.org/10.1/example",
                        "funder": [{"name": "Community Foundation", "award": ["CR-1", "CR-2"]}],
                    },
                    {"DOI": "10.1/malformed", "title": ["No funder name"], "funder": [{"award": ["x"]}]},
                ]
            }
        }

    profile = profile_from_text("community partnership implementation", field="education policy")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        awards, status = CrossrefFundingProvider(fetcher=fetcher).search_awards(conn, profile)
    engine.dispose()
    assert status.status == "success" and status.result_count == 2
    assert {a.award_number for a in awards} == {"CR-1", "CR-2"}
    assert all(a.organization_name == "Community Foundation" for a in awards)


def test_eo_bmf_parse_watermark_and_duplicate_identity_fields():
    batch = parse_eo_bmf_csv(
        "EIN,NAME,CITY,STATE,FOUNDATION_CODE\n123456789,Example Foundation,Boston,MA,02\n",
        dataset_key="may-2026",
    )
    assert batch.records[0].ein == "123456789"
    assert batch.records[0].organization_type == "foundation"
    assert batch.records[0].geography["state"] == "MA"
    assert batch.watermark["dataset_key"] == "may-2026"


def test_990pf_parser_extracts_awards_surfaces_and_suppresses_individual_pii():
    xml = """
    <Return>
      <TaxYr>2024</TaxYr><EIN>123456789</EIN><BusinessNameLine1Txt>Example Foundation</BusinessNameLine1Txt>
      <GrantOrContributionPdDurYrGrp>
        <RecipientBusinessNameLine1Txt>University Lab</RecipientBusinessNameLine1Txt>
        <PurposeOfGrantTxt>pilot community partnership infrastructure</PurposeOfGrantTxt><Amt>75000</Amt>
      </GrantOrContributionPdDurYrGrp>
      <GrantOrContributionApprvFutGrp>
        <PersonNm>Jane Doe</PersonNm><PurposeOfGrantTxt>training fellowship</PurposeOfGrantTxt><Amt>5000</Amt>
      </GrantOrContributionApprvFutGrp>
      <ApplicationInfoTxt>We do not accept unsolicited applications.</ApplicationInfoTxt>
    </Return>
    """
    parsed = parse_990pf_xml(xml, source_record_id="filing-1")
    assert parsed.tax_year == 2024 and parsed.errors == []
    assert len(parsed.awards) == 2
    individual = next(a for a in parsed.awards if a.recipient_is_individual)
    assert ui_award_record(individual)["recipient_name"] is None
    assert ui_award_record(individual)["recipient_withheld"] is True
    assert parsed.surfaces[0].access_mode == "unknown"
    assert "unsolicited" in parsed.surfaces[0].details.lower()
    malformed = parse_990pf_xml("<Return>", source_record_id="bad")
    assert malformed.awards == [] and malformed.errors


def test_prospect_generation_support_strategy_recurrence_and_no_open_from_history():
    profile = profile_from_text(
        "creative arts intervention pilot for trauma and mood after brain injury among military collaborators",
        field="neuroscience",
    )
    awards = [
        HistoricalAward(
            "NeuroArts Veterans Initiative",
            "irs_990_pf",
            "a1",
            purpose_text="pilot creative arts intervention for trauma mood and brain injury",
            tax_year=2023,
            scheme_name="Pilot Arts Awards",
            provenance=_prov("a1"),
        ),
        HistoricalAward(
            "NeuroArts Veterans Initiative",
            "irs_990_pf",
            "a2",
            purpose_text="creative arts intervention pilot with military-connected collaborators",
            tax_year=2024,
            scheme_name="Pilot Arts Awards",
            provenance=_prov("a2"),
        ),
    ]
    prospects, schemes = LatentFundingFitEngine().generate(profile, awards)
    assert prospects and prospects[0].prospect_kind == "organization"
    assert any(s.signal_type == "support_strategy_fit" for s in prospects[0].signals)
    assert schemes and schemes[0].prospect_kind == "scheme"
    assert "No current application window verified" in schemes[0].signals[0].explanation


def test_recipient_neighborhood_surfaces_funder_without_direct_topic_match():
    profile = profile_from_text("pilot adolescent community partnership implementation", field="education policy")
    awards = [
        HistoricalAward(
            "Direct Fit Foundation",
            "irs_990_pf",
            "d1",
            purpose_text="pilot adolescent community partnership implementation",
            recipient_name_raw="Neighborhood University",
            provenance=_prov("d1"),
        ),
        HistoricalAward(
            "Recipient Neighbor Fund",
            "irs_990_pf",
            "n1",
            purpose_text="general research infrastructure",
            recipient_name_raw="Neighborhood University",
            provenance=_prov("n1"),
        ),
    ]
    prospects, _ = LatentFundingFitEngine().generate(profile, awards)
    neighbor = next(p for p in prospects if p.organization_name == "Recipient Neighbor Fund")
    signal = next(s for s in neighbor.signals if s.signal_type == "recipient_similarity")
    assert signal.strength == "weak"
    assert "organization(s) that also appear" in signal.explanation
    assert signal.matched_evidence[0]["recipient_name"] == "Neighborhood University"


def test_recipient_neighborhood_ignores_individual_recipients():
    profile = profile_from_text("pilot adolescent community partnership implementation", field="education policy")
    awards = [
        HistoricalAward(
            "Direct Fit Foundation",
            "irs_990_pf",
            "d-ind",
            purpose_text="pilot adolescent community partnership implementation",
            recipient_name_raw="Jane Doe",
            recipient_is_individual=True,
            provenance=_prov("d-ind"),
        ),
        HistoricalAward(
            "Recipient Neighbor Fund",
            "irs_990_pf",
            "n-ind",
            purpose_text="general research infrastructure",
            recipient_name_raw="Jane Doe",
            recipient_is_individual=True,
            provenance=_prov("n-ind"),
        ),
    ]
    prospects, _ = LatentFundingFitEngine().generate(profile, awards)
    assert all(p.organization_name != "Recipient Neighbor Fund" for p in prospects)


def test_cofunding_neighborhood_surfaces_shared_recipient_funder():
    profile = profile_from_text("pilot adolescent implementation", field="education policy")
    awards = [
        HistoricalAward(
            "Direct Fit Foundation",
            "irs_990_pf",
            "d1",
            purpose_text="pilot adolescent implementation",
            recipient_name_raw="Shared University",
            provenance=_prov("d1"),
        ),
        HistoricalAward(
            "Direct Fit Foundation",
            "irs_990_pf",
            "d2",
            purpose_text="pilot adolescent implementation",
            recipient_name_raw="Second Clinic",
            provenance=_prov("d2"),
        ),
        HistoricalAward(
            "Cofunding Neighbor",
            "irs_990_pf",
            "c1",
            purpose_text="general research support",
            recipient_name_raw="Shared University",
            provenance=_prov("c1"),
        ),
        HistoricalAward(
            "Cofunding Neighbor",
            "irs_990_pf",
            "c2",
            purpose_text="general research support",
            recipient_name_raw="Second Clinic",
            provenance=_prov("c2"),
        ),
    ]
    prospects, _ = LatentFundingFitEngine().generate(profile, awards)
    neighbor = next(p for p in prospects if p.organization_name == "Cofunding Neighbor")
    signal = next(s for s in neighbor.signals if s.signal_type == "cofunding_proximity")
    assert signal.strength == "moderate"
    assert "recipient neighborhoods also supported" in signal.explanation
    assert len(signal.matched_evidence) == 2


def test_cofunding_neighborhood_ignores_individual_recipients():
    profile = profile_from_text("pilot adolescent implementation", field="education policy")
    awards = [
        HistoricalAward(
            "Direct Fit Foundation",
            "irs_990_pf",
            "d1",
            purpose_text="pilot adolescent implementation",
            recipient_name_raw="Jane Doe",
            recipient_is_individual=True,
            provenance=_prov("d1"),
        ),
        HistoricalAward(
            "Cofunding Neighbor",
            "irs_990_pf",
            "c1",
            purpose_text="general research support",
            recipient_name_raw="Jane Doe",
            recipient_is_individual=True,
            provenance=_prov("c1"),
        ),
    ]
    prospects, _ = LatentFundingFitEngine().generate(profile, awards)
    assert all(not any(s.signal_type == "cofunding_proximity" for s in p.signals) for p in prospects)


def test_long_tail_specificity_beats_metadata_volume_but_one_vague_record_does_not():
    profile = profile_from_text("pilot adolescent community partnership implementation", field="education policy")
    major = [
        HistoricalAward(
            "Major Indexed Funder", "openalex_award", f"m{i}", purpose_text="broad research", provenance=_prov(f"m{i}")
        )
        for i in range(100)
    ]
    small = [
        HistoricalAward(
            "Specific Small Funder",
            "irs_990_pf",
            f"s{i}",
            purpose_text="pilot adolescent community partnership implementation",
            provenance=_prov(f"s{i}"),
        )
        for i in range(4)
    ]
    vague = [
        HistoricalAward("Tiny Vague Funder", "irs_990_pf", "v1", purpose_text="pilot research", provenance=_prov("v1"))
    ]
    prospects, _ = LatentFundingFitEngine().generate(profile, [*major, *small, *vague])
    assert prospects[0].organization_name == "Specific Small Funder"
    assert [p.organization_name for p in prospects].index("Tiny Vague Funder") > 0


def test_llm_triage_annotates_items_without_replacing_full_pool():
    class _Result:
        text = json.dumps(
            {
                "items": [
                    {
                        "item_key": "opportunity:10",
                        "label": "possible_fit",
                        "show_in_triage": True,
                        "rationale": "The opportunity mentions community implementation.",
                        "fit_dimensions": ["support_strategy", "population"],
                        "concerns": ["Eligibility still requires review."],
                    },
                    {
                        "item_key": "prospect:20",
                        "label": "lower_apparent_fit",
                        "show_in_triage": False,
                        "rationale": "The surfaced evidence is broad and not close to the research context.",
                    },
                ]
            }
        )

    def complete_fn(config, prompt):
        assert config is not None
        assert "adolescent mental health" in prompt
        assert "Return JSON only" in prompt
        return _Result()

    report = {
        "profile": {"facets": {"populations": [{"normalized_value": "adolescents"}]}},
        "open_opportunities": [
            {
                "id": 10,
                "title": "Community implementation pilot",
                "organization_name": "Pilot Agency",
                "status": "open",
                "signals": [],
            }
        ],
        "recurring_schemes": [],
        "funding_prospects": [
            {
                "id": 20,
                "organization_name": "Broad Funder",
                "prospect_kind": "organization",
                "signals": [],
            }
        ],
        "application_surfaces": [],
    }
    status = FundingLlmTriageEvaluator(config=object(), complete_fn=complete_fn).evaluate(
        report=report, research_context="adolescent mental health implementation"
    )
    assert status["status"] == "success"
    assert report["open_opportunities"][0]["llm_evaluation"]["show_in_triage"] is True
    assert report["funding_prospects"][0]["llm_evaluation"]["show_in_triage"] is False
    payload = json.dumps(report).lower()
    assert "funding probability" not in payload
    assert "recommended grant" not in payload


def test_llm_triage_bounds_total_input_for_managed_local_without_dropping_silently():
    """Funding triage previously had NO total-character cap at all (only an 80-item count cap) -- real measured
    worst-case input was 641,896 chars, nearly two orders of magnitude past the managed Local AI preview's
    ~10,240-token budget. A managed_local run must bound total input and disclose any dropped items via the
    warning, never silently."""
    from types import SimpleNamespace

    class _Result:
        text = json.dumps({"items": []})

    def complete_fn(config, prompt):
        assert len(prompt) < 20_000  # comfortably under the managed_local budget, not the 200k cloud default
        return _Result()

    report = {
        "profile": {},
        "open_opportunities": [
            {
                "id": i,
                "title": f"Opportunity {i}",
                "organization_name": "Org",
                "status": "open",
                "summary": "x" * 5000,  # each item alone would blow a tiny total budget without per-field clipping
                "signals": [],
            }
            for i in range(20)
        ],
        "recurring_schemes": [],
        "funding_prospects": [],
        "application_surfaces": [],
    }
    status = FundingLlmTriageEvaluator(
        config=SimpleNamespace(provider="managed_local"), complete_fn=complete_fn
    ).evaluate(report=report, research_context="test")
    assert status["status"] == "success"
    assert status["evaluated_count"] < 20  # some items were dropped to fit the managed_local budget
    assert status["warning"] and "bounded item" in status["warning"]  # disclosed, not silent


def test_llm_triage_endpoint_reviews_current_pool_without_rerunning_discovery(temp_db_url):
    class _Evaluator:
        def evaluate(self, *, report, research_context):
            assert "implementation" in research_context
            assert len(report["open_opportunities"]) == 1
            assert "unexpected" not in report
            report["open_opportunities"][0]["llm_evaluation"] = {
                "label": "possible_fit",
                "show_in_triage": True,
                "rationale": "The surfaced opportunity mentions implementation.",
                "basis": "test evaluator",
            }
            report["funding_prospects"][0]["llm_evaluation"] = {
                "label": "lower_apparent_fit",
                "show_in_triage": False,
                "rationale": "The prospect is broad.",
                "basis": "test evaluator",
            }
            return {
                "provider_id": "configured-llm",
                "status": "success",
                "evaluated_count": 2,
                "annotated_count": 2,
                "warning": None,
                "prompt_version": "test",
            }

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_llm_triage_evaluator = _Evaluator()
    report = {
        "unexpected": "not forwarded",
        "open_opportunities": [
            {"id": 10, "title": "Implementation pilot", "organization_name": "Agency", "status": "open"}
        ],
        "recurring_schemes": [],
        "funding_prospects": [{"id": 20, "organization_name": "Broad Funder", "signals": []}],
        "application_surfaces": [],
    }

    response = client.post(
        "/funding-discovery/llm-triage",
        json={"report": report, "description": "community implementation research"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["llm_triage_status"]["status"] == "success"
    assert body["report"]["open_opportunities"][0]["llm_evaluation"]["show_in_triage"] is True
    assert body["report"]["funding_prospects"][0]["llm_evaluation"]["show_in_triage"] is False
    assert "unexpected" not in body["report"]


def test_llm_triage_persists_to_run_reload_and_csv(temp_db_url):
    class _Evaluator:
        def evaluate(self, *, report, research_context):
            assert "implementation" in research_context
            report["open_opportunities"][0]["llm_evaluation"] = {
                "label": "possible_fit",
                "show_in_triage": True,
                "rationale": "Current opportunity mentions implementation.",
                "fit_dimensions": ["activity_type"],
                "concerns": ["Eligibility remains unresolved."],
                "basis": "bounded test evaluator",
            }
            report["funding_prospects"][0]["llm_evaluation"] = {
                "label": "lower_apparent_fit",
                "show_in_triage": False,
                "rationale": "Prospect evidence is broad.",
                "fit_dimensions": [],
                "concerns": ["Weak subject overlap."],
                "basis": "bounded test evaluator",
            }
            return {
                "provider_id": "configured-llm",
                "status": "success",
                "evaluated_count": 2,
                "annotated_count": 2,
                "prompt_version": "test-v2",
            }

    def fetcher(url, *, json, params, timeout):
        return 200, {
            "data": {
                "oppHits": [
                    {
                        "id": "TRIAGE1",
                        "title": "Implementation pilot opportunity",
                        "agencyName": "NIH",
                        "oppStatus": "posted",
                        "closeDate": "2026-12-15",
                    }
                ]
            }
        }

    awards = [
        HistoricalAward(
            "Triage Foundation",
            "irs_990_pf",
            "pf-triage",
            purpose_text="community implementation pilot support",
            provenance=_prov("pf-triage"),
        )
    ]
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_llm_triage_evaluator = _Evaluator()
    client.app.state.funding_award_provider = FixtureAwardHistoryProvider(awards=awards)
    client.app.state.funding_grants_gov_client = GrantsGovClient(fetcher=fetcher)
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    run = client.post(
        "/funding-discovery/run",
        json={"description": "community implementation pilot research", "field": "public health"},
    )
    job_id = run.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done

    triage = client.post(
        "/funding-discovery/llm-triage",
        json={"report": done["report"], "description": "community implementation pilot research"},
    )

    assert triage.status_code == 200
    run_id = done["report"]["run_id"]
    reloaded = client.get(f"/funding-discovery/runs/{run_id}")
    assert reloaded.status_code == 200
    report = reloaded.json()["report"]
    assert report["open_opportunities"][0]["llm_evaluation"]["label"] == "possible_fit"
    assert report["open_opportunities"][0]["llm_evaluation"]["status"] == "current"
    assert report["funding_prospects"][0]["llm_evaluation"]["label"] == "lower_apparent_fit"
    assert report["funding_prospects"][0]["llm_evaluation"]["status"] == "current"
    assert report["llm_triage_status"]["prompt_version"] == "test-v2"
    export = client.get(f"/funding-discovery/runs/{run_id}/export.csv")
    rows = list(csv.DictReader(io.StringIO(export.text)))
    exported_opp = next(row for row in rows if row["item_kind"] == "open_opportunity")
    assert exported_opp["llm_triage_label"] == "possible_fit"
    assert exported_opp["llm_triage_status"] == "current"
    prospect = next(row for row in rows if row["item_kind"] == "funding_prospect")
    assert prospect["llm_triage_rationale"] == "Prospect evidence is broad."
    assert prospect["llm_triage_prompt_version"] == "test-v2"
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(funding_opportunities)
            .where(funding_opportunities.c.id == report["open_opportunities"][0]["id"])
            .values(status="forecasted", deadlines_json=[{"kind": "application", "date": "2027-01-15"}])
        )
    engine.dispose()

    stale = client.get(f"/funding-discovery/runs/{run_id}").json()["report"]
    stale_eval = stale["open_opportunities"][0]["llm_evaluation"]
    assert stale_eval["label"] == "possible_fit"
    assert stale_eval["status"] == "stale"
    assert "earlier run evidence" in stale_eval["stale_reason"]
    stale_export = client.get(f"/funding-discovery/runs/{run_id}/export.csv")
    stale_rows = list(csv.DictReader(io.StringIO(stale_export.text)))
    stale_opp = next(row for row in stale_rows if row["item_kind"] == "open_opportunity")
    assert stale_opp["llm_triage_label"] == "possible_fit"
    assert stale_opp["llm_triage_status"] == "stale"


def test_endpoint_persistence_save_and_segmented_report(temp_db_url):
    provider_urls = []

    def fetcher(url, *, json, params, timeout):
        provider_urls.append(url)
        if "fetchOpportunity" in url:
            return 200, {
                "data": {
                    "id": "F1",
                    "opportunityTitle": "Federal pilot grant",
                    "docType": "synopsis",
                    "agencyDetails": {"agencyName": "NIH"},
                    "synopsis": {
                        "agencyName": "NIH",
                        "responseDateDesc": "2026-12-01",
                        "synopsisDesc": "Updated federal opportunity detail.",
                        "awardFloor": "10000",
                        "awardCeiling": "50000",
                    },
                }
            }
        return 200, {
            "data": {
                "oppHits": [
                    {
                        "id": "F1",
                        "title": "Federal pilot grant",
                        "agencyName": "NIH",
                        "oppStatus": "forecasted",
                        "closeDate": "2026-11-15",
                    }
                ]
            }
        }

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_grants_gov_client = GrantsGovClient(fetcher=fetcher)
    r = client.post(
        "/funding-discovery/run",
        json={
            "description": "pilot adolescent mental health community partnership implementation",
            "field": "education policy",
        },
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    report = done["report"]
    runs = client.get("/funding-discovery/runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["run_id"] == report["run_id"]
    assert runs.json()["runs"][0]["result_counts"]["prospects"] >= 1
    reloaded_run = client.get(f"/funding-discovery/runs/{report['run_id']}")
    assert reloaded_run.status_code == 200
    assert reloaded_run.json()["report"]["run_id"] == report["run_id"]
    assert report["open_opportunities"] and report["open_opportunities"][0]["status"] == "forecasted"
    assert "funding_prospects" in report and "recurring_schemes" in report
    opportunity_id = report["open_opportunities"][0]["id"]
    save_opp = client.post(
        "/funding-discovery/save", json={"item_kind": "opportunity", "canonical_item_id": opportunity_id}
    )
    assert save_opp.status_code == 200
    assert save_opp.json()["last_known_status"] == "forecasted"
    assert save_opp.json()["last_known_deadline"] == "2026-11-15"
    item_id = report["funding_prospects"][0]["id"]
    save = client.post("/funding-discovery/save", json={"item_kind": "prospect", "canonical_item_id": item_id})
    assert save.status_code == 200 and save.json()["workflow_state"] == "saved"
    save_again = client.post("/funding-discovery/save", json={"item_kind": "prospect", "canonical_item_id": item_id})
    assert save_again.status_code == 200
    saved = client.get("/funding-discovery/saved")
    assert saved.status_code == 200
    items = saved.json()["items"]
    assert {item["item_kind"] for item in items} >= {"opportunity", "prospect"}
    saved_opp = next(item for item in items if item["item_kind"] == "opportunity")
    assert saved_opp["title"] == "Federal pilot grant"
    assert saved_opp["organization_name"] == "NIH"
    assert saved_opp["last_known_deadline"] == "2026-11-15"
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            update(funding_opportunities)
            .where(funding_opportunities.c.id == opportunity_id)
            .values(status="open", deadlines_json=[{"kind": "application", "date": "2026-12-01"}])
        )
    engine.dispose()
    refreshed = client.post("/funding-discovery/saved/refresh")
    assert refreshed.status_code == 200
    assert any("fetchOpportunity" in url for url in provider_urls)
    opp_refresh = next(c for c in refreshed.json()["changes"] if c["saved_item_id"] == saved_opp["id"])
    assert opp_refresh["status"] == "changed"
    assert {"field": "status", "before": "forecasted", "after": "open"} in opp_refresh["changes"]
    assert {"field": "deadline", "before": "2026-11-15", "after": "2026-12-01"} in opp_refresh["changes"]
    assert opp_refresh["provider_status"] == "refreshed"
    refreshed_saved = client.get("/funding-discovery/saved").json()["items"]
    refreshed_opp = next(item for item in refreshed_saved if item["id"] == saved_opp["id"])
    assert refreshed_opp["last_known_status"] == "open"
    assert refreshed_opp["last_known_deadline"] == "2026-12-01"
    saved_prospect = next(item for item in items if item["item_kind"] == "prospect")
    assert saved_prospect["last_known_status"] == "prospect"
    updated_saved = client.patch(
        f"/funding-discovery/saved/{saved_prospect['id']}",
        json={"workflow_state": "reviewing", "notes": "Check fit with the pilot language."},
    )
    assert updated_saved.status_code == 200
    assert updated_saved.json()["item"]["workflow_state"] == "reviewing"
    assert updated_saved.json()["item"]["notes"] == "Check fit with the pilot language."
    saved_after_update = client.get("/funding-discovery/saved")
    updated_list_item = next(item for item in saved_after_update.json()["items"] if item["id"] == saved_prospect["id"])
    assert updated_list_item["workflow_state"] == "reviewing"
    assert updated_list_item["notes"] == "Check fit with the pilot language."
    bad_update = client.patch(
        f"/funding-discovery/saved/{saved_prospect['id']}", json={"workflow_state": "not-a-state"}
    )
    assert bad_update.status_code == 422
    unsave = client.delete(f"/funding-discovery/saved/{saved_prospect['id']}")
    assert unsave.status_code == 200
    assert unsave.json()["unsaved"]["canonical_item_id"] == item_id
    saved_after_unsave = client.get("/funding-discovery/saved")
    assert saved_after_unsave.status_code == 200
    assert all(item["id"] != saved_prospect["id"] for item in saved_after_unsave.json()["items"])
    assert client.delete(f"/funding-discovery/saved/{saved_prospect['id']}").status_code == 404
    missing = client.post("/funding-discovery/save", json={"item_kind": "opportunity", "canonical_item_id": 999999})
    assert missing.status_code == 404
    export = client.get(f"/funding-discovery/runs/{report['run_id']}/export.csv")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert "funding-discovery-run-" in export.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert {row["item_kind"] for row in rows} >= {"open_opportunity", "funding_prospect"}
    exported_opp = next(row for row in rows if row["item_kind"] == "open_opportunity")
    assert exported_opp["title"] == "Federal pilot grant"
    assert exported_opp["next_deadline"] == "2026-12-01"
    exported_prospect = next(row for row in rows if row["item_kind"] == "funding_prospect")
    assert "support strategy fit" in exported_prospect["top_signals"]
    assert "community" in exported_prospect["matched_facets"]
    lowered_export = export.text.lower()
    assert "recommended grant" not in lowered_export
    assert "funding probability" not in lowered_export
    assert client.get("/funding-discovery/runs/999999/export.csv").status_code == 404


def test_saved_prospect_refresh_can_link_current_application_surface(temp_db_url):
    provider_urls = []
    awards = [
        HistoricalAward(
            "Federal Pilot Institute",
            "irs_990_pf",
            "pf-application-refresh",
            purpose_text="pilot implementation grants for community research partnerships",
            scheme_name="Pilot Partnership Grants",
            provenance=_prov("pf-application-refresh"),
        )
    ]

    def fetcher(url, *, json=None, params=None, timeout=10):
        provider_urls.append(url)
        if "federal" not in str(json or "").lower():
            return 200, {"data": {"oppHits": []}}
        return 200, {
            "data": {
                "oppHits": [
                    {
                        "id": "APP1",
                        "title": "Federal Pilot Institute Pilot Partnership Grants",
                        "agencyName": "Federal Pilot Institute",
                        "oppStatus": "posted",
                        "closeDate": "2026-10-15",
                    }
                ]
            }
        }

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_award_provider = FixtureAwardHistoryProvider(awards=awards)
    client.app.state.funding_grants_gov_client = GrantsGovClient(fetcher=fetcher)
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    run = client.post(
        "/funding-discovery/run",
        json={"description": "pilot community research partnership implementation", "field": "public health"},
    )
    job_id = run.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    prospect_id = done["report"]["funding_prospects"][0]["id"]
    saved = client.post("/funding-discovery/save", json={"item_kind": "prospect", "canonical_item_id": prospect_id})
    saved_id = saved.json()["id"]
    assert saved.json()["last_known_status"] == "prospect"

    refreshed = client.post("/funding-discovery/saved/refresh")

    assert refreshed.status_code == 200
    assert any("search2" in url for url in provider_urls)
    change = next(c for c in refreshed.json()["changes"] if c["saved_item_id"] == saved_id)
    assert change["status"] == "changed"
    assert change["provider_status"].startswith("application_surface_refreshed:")
    assert {"field": "status", "before": "prospect", "after": "open_opportunity"} in change["changes"]
    assert {"field": "deadline", "before": None, "after": "2026-10-15"} in change["changes"]
    item = next(i for i in refreshed.json()["items"] if i["id"] == saved_id)
    assert item["item_kind"] == "prospect"
    assert item["display_status"] == "open_opportunity"
    assert item["linked_opportunity_title"] == "Federal Pilot Institute Pilot Partnership Grants"
    assert item["source_url"] == "https://www.grants.gov/search-results-detail/APP1"
    assert item["refresh_events"][0]["outcome"] == "current_opportunity_found"
    assert item["refresh_events"][0]["linked_opportunity_id"] == item["linked_opportunity_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        count = conn.execute(select(func.count()).select_from(saved_funding_refresh_events)).scalar_one()
    engine.dispose()
    assert count >= 1


def test_saved_prospect_refresh_provider_failure_is_non_destructive(temp_db_url):
    awards = [
        HistoricalAward(
            "Surface Failure Foundation",
            "irs_990_pf",
            "pf-application-failure",
            purpose_text="pilot implementation grants for community research partnerships",
            provenance=_prov("pf-application-failure"),
        )
    ]
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_award_provider = FixtureAwardHistoryProvider(awards=awards)
    client.app.state.funding_grants_gov_client = GrantsGovClient(fetcher=lambda *a, **k: (500, {"error": "down"}))
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    run = client.post(
        "/funding-discovery/run",
        json={"description": "pilot community research partnership implementation", "field": "public health"},
    )
    job_id = run.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    prospect_id = done["report"]["funding_prospects"][0]["id"]
    saved = client.post("/funding-discovery/save", json={"item_kind": "prospect", "canonical_item_id": prospect_id})
    saved_id = saved.json()["id"]

    refreshed = client.post("/funding-discovery/saved/refresh")

    change = next(c for c in refreshed.json()["changes"] if c["saved_item_id"] == saved_id)
    assert change["status"] == "unchanged"
    assert change["provider_status"] == "provider_unavailable"
    item = next(i for i in refreshed.json()["items"] if i["id"] == saved_id)
    assert item["item_kind"] == "prospect"
    assert item["last_known_status"] == "prospect"
    assert item.get("linked_opportunity_id") is None
    assert item["refresh_events"][0]["outcome"] == "provider_unavailable"


def test_endpoint_exposes_application_surface_posture_for_prospects(temp_db_url):
    awards = [
        HistoricalAward(
            "Posture Foundation",
            "irs_990_pf",
            "pf-1",
            purpose_text="pilot adolescent community partnership implementation",
            recipient_name_raw="Neighborhood University",
            provenance=_prov("pf-1"),
        )
    ]
    surfaces = [
        ApplicationSurface(
            organization_name="Posture Foundation",
            surface_type="structured_html",
            access_mode="unknown",
            actionability="prospect_only",
            details="Source text indicates unsolicited applications are not accepted.",
            provenance=_prov("pf-surface"),
        )
    ]
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_award_provider = FixtureAwardHistoryProvider(awards=awards, surfaces=surfaces)
    client.app.state.funding_grants_gov_client = GrantsGovClient(
        fetcher=lambda *a, **k: (200, {"data": {"oppHits": []}})
    )
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    r = client.post(
        "/funding-discovery/run",
        json={
            "description": "pilot adolescent community partnership implementation",
            "field": "education policy",
        },
    )
    job_id = r.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    surface = done["report"]["application_surfaces"][0]
    assert surface["organization_name"] == "Posture Foundation"
    assert surface["actionability"] == "prospect_only"
    assert "unsolicited applications are not accepted" in surface["details"]


def test_selected_paper_mode_and_provider_partial_failure_visibility(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(
            conn,
            title="Freshwater microbial ecology using environmental DNA",
            csl_json={"title": "x"},
            abstract="Field sampling and environmental DNA infrastructure.",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.funding_award_provider = FixtureAwardHistoryProvider(
        awards=[
            HistoricalAward(
                "Freshwater Research Foundation",
                "irs_990_pf",
                "pf-selected-paper",
                purpose_text="field sampling and environmental DNA infrastructure",
                provenance=_prov("pf-selected-paper"),
            )
        ]
    )
    client.app.state.funding_grants_gov_client = GrantsGovClient(fetcher=lambda *a, **k: (500, {"error": "down"}))
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    r = client.post("/funding-discovery/run", json={"paper_id": pid})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    done = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    statuses = done["report"]["provider_statuses"]
    assert any(s["provider_id"] == "grants-gov" and s["status"] == "failed" for s in statuses)
    assert any(s["provider_id"] == "local-funding-history" and s["status"] == "success" for s in statuses)
    assert done["report"]["funding_prospects"]


def test_frontend_registration_and_forbidden_language_absent():
    text = (
        open("app/frontend/js/08jz_funding_helpers.jsx", encoding="utf-8").read()
        + open("app/frontend/js/08k_funding_discovery.jsx", encoding="utf-8").read()
        + open("app/frontend/js/08l_funding_saved.jsx", encoding="utf-8").read()
        + open("app/frontend/js/08m_funding_results.jsx", encoding="utf-8").read()
    )
    assert 'label: "Funding"' in text  # inc 280: relocated to the Discover workspace as the "Funding" tab
    assert "order: 40" in text
    assert "Open Opportunities" in text and "Recurring Schemes" in text and "Funding Prospects" in text
    assert "Application route" in text and "fundingSurfacesFor" in text
    assert "Saved funding" in text and "/funding-discovery/saved" in text
    assert "Export CSV" in text and "/funding-discovery/runs/" in text
    assert "Unsave" in text and "/funding-discovery/saved/${item.id}" in text
    assert "Linked opportunity" in text and "linked_opportunity_title" in text
    assert "Current opportunity found" in text and "Provider unavailable" in text
    assert "Status changed" in text and "Deadline changed" in text
    assert "No current application window verified" in text and "savedRefreshOutcome" in text
    assert "fundingCoverageMeaning" in text and "What was not covered" in text
    assert "not evidence that no funding mechanism exists" in text
    assert "Commercial or licensed philanthropic databases are not part of the open-data path unless configured" in text
    assert "fundingGroupedItems" in text and "FundingGroupSummary" in text
    assert "Grouped for display; run and export records stay separate." in text
    assert (
        "Why grouped?" in text
        and "Grouping uses exact provider opportunity, funder+scheme, or funder identity keys" in text
    )
    assert "Show Lower-Signal Prospects" in text and "fundingIsLowerSignalProspect" in text
    assert "display-only signal filter" in text
    assert "Refresh history" in text and "refresh_events" in text and "savedRefreshEventLabel" in text
    assert "Save changes" in text and "FUNDING_WORKFLOW_STATES" in text and "What needs review next?" in text
    assert "Refresh saved funding" in text and "/funding-discovery/saved/refresh" in text
    assert "Signal trail" in text and "fundingSignalBoundary" in text
    assert "categorical, not a probability" in text
    assert "not a forecast and do not verify a current application window" in text
    assert "Open source record" in text and "FundingEvidenceRow" in text
    assert "Source:" in text and "Record:" in text and "Scheme cue:" in text
    assert "SavedFundingRefreshPill" in text and "funding-refresh-pill" in text
    assert "SAVED_FUNDING_FILTERS" in text and "savedFundingFilterCounts" in text
    assert "Open / current" in text and "Prospects" in text and "Changed since saved" in text
    assert "Needs review" in text and "Provider issue" in text and "Applying / planning" in text and "Archived" in text
    assert "open_current" in text and "changed_since_saved" in text
    assert "SavedFundingQueueSummary" in text and "funding-saved-summary" in text
    assert "Current opportunity found" in text and "Workflow:" in text and "Review saved evidence" in text
    assert "SAVED_FUNDING_SORTS" in text and "SavedFundingSort" in text and "savedFundingSortResults" in text
    assert "Sort saved funding" in text and "Recently saved" in text and "Deadline soon" in text
    assert "Changed since saved first" in text and "Open/current first" in text and "Archived last" in text
    assert "Sorting changes display order only; saved records and workflow states are unchanged." in text
    assert "SavedFundingBulkActions" in text and "funding-saved-bulk" in text
    assert "Applies to {count} visible saved item" in text
    assert "Mark visible reviewing" in text and "Archive visible" in text
    assert "workflow_state: workflowState" in text and "/funding-discovery/saved/${item.id}" in text
    assert "No saved funding items match this filter." in text
    assert "Ask AI to triage apparent fit after discovery" in text
    assert "Evaluate apparent fit with AI" in text and "/funding-discovery/llm-triage" in text
    assert "This does not remove records, alter saved items, or create recommendations." in text
    assert "AI fit triage failed" in text and "Evaluating apparent funding fit" in text
    assert "LLM-triaged" in text and "All surfaced" in text
    assert "AI-fit label based on earlier run evidence" in text
    assert "FundingFitTriagePanel" in text and "funding-fit-triage" in text
    assert "What may need review" in text and "fundingTriageReviewNotes" in text
    assert "Evidence class:" in text and "fundingEvidenceClassLabel" in text
    assert "This summary is display-only; it does not alter ranking" in text
    assert "No current application surface was verified in this run." in text
    assert "Eligibility evidence was not assessed." in text
    assert "AI-fit label is stale because the underlying funding evidence changed." in text
    assert "FUNDING_RESULT_FILTERS" in text and "FundingResultFilters" in text
    assert "fundingResultFilterCounts" in text and "fundingResultMatchesFilter" in text
    assert "Eligibility review" in text and "fundingNeedsEligibilityReview" in text
    assert "No current surface" in text and "fundingHasNoCurrentSurface" in text
    assert "Identity uncertain" in text and "fundingIdentityIsUncertain" in text
    assert "Stale AI-fit" in text and "fundingHasStaleAiFit" in text
    assert "Display filters narrow the visible pool only" in text
    assert "run evidence, exports, and saved records remain intact" in text
    assert "Recent runs" in text and "/funding-discovery/runs?limit=8" in text
    assert "FundingRunHistory" in text and "Reload" in text
    assert "Strong / moderate" in text and "Weak / unresolved" in text
    assert "Scholarly lineage" in text and "Historical grantmaking" in text
    assert "Federal" in text and "Application route" in text
    assert "Saved" in text and "Unsaved" in text and "LLM triaged" in text
    assert "No funding prospects match the current display filter." in text
    assert "fundingSavedItemFor" in text and "savedItem={fundingSavedItemFor" in text
    assert "funding-card-saved" in text and "funding-card-save" in text
    assert "Unsave ${kind} from funding workflow" in text
    assert "FUNDING_RESULT_SORTS" in text and "FundingResultSort" in text
    assert "fundingSortResults" in text and "fundingDeadlineTime" in text
    assert "Default evidence order" in text and "Application route first" in text
    assert "Saved first" in text and "Upcoming deadlines" in text
    assert "Strong signals first" in text and "Recently surfaced" in text
    assert "Sorting changes display order only; result lanes and evidence records are unchanged." in text
    assert "FundingResultSummary" in text and "funding-result-summary" in text
    assert "visible of {displayPool} in the current display pool" in text
    assert "grouped results in the full saved run" in text
    assert "lower-signal prospects hidden" in text
    assert "These controls change display only." in text
    assert "Open Opportunities (${opportunities.length})" in text
    assert "Recurring Schemes (${schemes.length})" in text
    assert "Funding Prospects (${prospects.length})" in text
    assert "FUNDING_VIEW_PREFS_KEY" in text and "callosum.fundingDiscovery.viewPrefs.v1" in text
    assert "fundingLoadViewPrefs" in text and "fundingSaveViewPrefs" in text
    assert "validFilters.has(parsed.resultFilter)" in text and "validSorts.has(parsed.resultSort)" in text
    assert "storage failures must not affect evidence rendering" in text
    assert "effectiveTriageOnly = triageOnly && triageReady" in text
    lowered = text.lower()
    assert "92% match" not in lowered
    assert "likely to fund" not in lowered
    assert "expected to reopen" not in lowered
    assert "recommended grant" not in lowered
    assert "funding probability" not in lowered
    assert "goodness of match" not in lowered


def test_run_without_award_seam_surfaces_no_fabricated_awards(temp_db_url):
    """Regression: with no funding_award_provider configured (the production default), no fabricated
    fixture foundations may leak into the report.

    Previously the production fallback was ``FixtureAwardHistoryProvider()``, whose ``default_awards()``
    emitted hardcoded ``irs_990_pf`` foundations that were matched against the profile and surfaced as
    real prospects. The award-history seam is intentionally left unset here so the production fallback
    is exercised; the other providers are stubbed to empty so no network call is made. The description
    deliberately overlaps the old fixtures' purpose text, so this test would FAIL against the old
    fallback and passes only once the fallback contributes zero awards.
    """
    client = TestClient(create_app(db_url=temp_db_url))
    # funding_award_provider intentionally NOT set -> exercises the production fallback.
    client.app.state.funding_grants_gov_client = GrantsGovClient(
        fetcher=lambda *a, **k: (200, {"data": {"oppHits": []}})
    )
    client.app.state.funding_openalex_provider = OpenAlexFundingProvider(fetcher=lambda *a, **k: (200, {"results": []}))
    client.app.state.funding_crossref_provider = CrossrefFundingProvider(
        fetcher=lambda *a, **k: (200, {"message": {"items": []}})
    )
    run = client.post(
        "/funding-discovery/run",
        json={
            "description": (
                "pilot creative arts and brain injury intervention using neuroimaging for trauma and mood; "
                "community partnership implementation pilot for adolescent mental health in schools; "
                "freshwater microbial ecology field sampling"
            ),
            "field": "clinical neuroscience",
        },
    )
    assert run.status_code == 202
    job_id = run.json()["job_id"]
    done: dict = {}
    for _ in range(30):
        done = client.get(f"/funding-discovery/run/{job_id}").json()
        if done["status"] in {"done", "error"}:
            break
    assert done["status"] == "done", done
    report_text = json.dumps(done["report"])
    for fabricated in (
        "Green River Foundation",
        "Heritage Futures Trust",
        "Community Learning Fund",
        "NeuroArts Veterans Initiative",
    ):
        assert fabricated not in report_text, f"fabricated fixture award leaked into production report: {fabricated}"
    assert "irs_990_pf" not in report_text and "irs-990-pf" not in report_text
