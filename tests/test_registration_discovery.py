"""Increment 427: explicit metadata-only registration candidate discovery."""

from __future__ import annotations

from urllib.parse import unquote

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.registration_links_repo import list_registration_links, upsert_registration_candidates
from app.backend.persistence.repository import create_paper
from app.backend.registration_discovery.datacite_provider import DataCiteRegistrationProvider
from app.backend.registration_discovery.direct_provider import DirectReferenceProvider
from app.backend.registration_discovery.domain import (
    DiscoveryReference,
    DiscoveryRequest,
    ProviderReport,
    RegistrationCandidate,
    RegistrationDiscoveryRegistry,
    contextual_class,
    contextual_evidence,
)
from app.backend.registration_discovery.http import RegistryHttpError, _validate_registry_url
from app.backend.registration_discovery.osf_provider import OsfRegistrationProvider


def _request(*, references=(), doi="10.5555/publication", title="Attention and memory") -> DiscoveryRequest:
    return DiscoveryRequest(
        paper_id=1,
        doi=doi,
        title=title,
        authors=("Ada Lovelace", "Grace Hopper"),
        year=2024,
        references=tuple(references),
    )


def _candidate(external_id: str = "ab12c") -> RegistrationCandidate:
    return RegistrationCandidate(
        provider="osf",
        external_id=external_id,
        registration_doi=f"10.17605/osf.io/{external_id}",
        canonical_url=f"https://osf.io/{external_id}/",
        title="Attention and memory registration",
        contributors=("Ada Lovelace",),
        registered_at="2023-05-04T00:00:00Z",
        registration_status="public",
        schema_name="OSF Preregistration",
        linkage_class="explicit-linkage",
        match_method="paper-osf-reference",
        match_evidence=({"kind": "paper-reference", "printed": True},),
        source_metadata={"public": True},
    )


def _osf_fetch(payloads: dict[str, dict]):
    def fetch(url: str) -> dict:
        path = url.removeprefix("https://api.osf.io/v2")
        if path not in payloads:
            raise RegistryHttpError(404, f"fixture has no {path}")
        return payloads[path]

    return fetch


def test_osf_direct_reference_is_explicit_and_preserves_metadata() -> None:
    reference = DiscoveryReference("osf", "ab12c", "https://osf.io/ab12c/", "text", True, "registered at OSF")
    provider = OsfRegistrationProvider(
        _osf_fetch(
            {
                "/registrations/ab12c/": {
                    "data": {
                        "id": "ab12c",
                        "attributes": {
                            "title": "Attention and memory plan",
                            "date_registered": "2023-04-01T00:00:00Z",
                            "public": True,
                            "embargoed": False,
                            "withdrawn": False,
                            "registration_supplement": "OSF Preregistration",
                        },
                    }
                },
                "/registrations/ab12c/contributors/?embed=users": {
                    "data": [{"embeds": {"users": {"data": {"attributes": {"full_name": "Ada Lovelace"}}}}}]
                },
                "/registrations/ab12c/identifiers/": {
                    "data": [{"attributes": {"category": "doi", "value": "10.17605/OSF.IO/AB12C"}}]
                },
                "/registrations/ab12c/resources/": {"data": []},
            }
        )
    )

    report = provider.discover(_request(references=(reference,)))

    assert report.status == "ok"
    candidate = report.candidates[0]
    assert candidate.linkage_class == "explicit-linkage"
    assert candidate.registration_doi == "10.17605/osf.io/ab12c"
    assert candidate.contributors == ("Ada Lovelace",)
    assert candidate.schema_name == "OSF Preregistration"


def test_osf_project_candidates_require_confirmation_and_preserve_withdrawn_state() -> None:
    reference = DiscoveryReference("osf", "node1", "https://osf.io/node1/", "text", True, "OSF project")
    provider = OsfRegistrationProvider(
        _osf_fetch(
            {
                "/nodes/node1/registrations/": {
                    "data": [
                        {
                            "id": "reg11",
                            "attributes": {
                                "title": "Attention and memory registration",
                                "date_registered": "2023-04-01",
                                "public": False,
                                "withdrawn": True,
                            },
                        }
                    ]
                },
                "/registrations/reg11/contributors/?embed=users": {"data": []},
                "/registrations/reg11/identifiers/": {"data": []},
                "/registrations/reg11/resources/": {"data": []},
            }
        )
    )

    candidate = provider.discover(_request(references=(reference,))).candidates[0]

    assert candidate.linkage_class == "strong-contextual-match"
    assert candidate.registration_status == "withdrawn"
    assert candidate.match_method == "osf-project-registration"


def test_datacite_reverse_lookup_preserves_relation_type() -> None:
    calls: list[str] = []

    def fetch(url: str) -> dict:
        calls.append(unquote(url))
        if "relatedIdentifiers.relatedIdentifier" in unquote(url):
            return {
                "data": [
                    {
                        "id": "10.17605/osf.io/z4752",
                        "attributes": {
                            "doi": "10.17605/osf.io/z4752",
                            "types": {"resourceTypeGeneral": "StudyRegistration", "resourceType": "Registration"},
                            "titles": [{"title": "Attention and memory"}],
                            "creators": [{"name": "Lovelace, Ada"}],
                            "relatedIdentifiers": [
                                {
                                    "relatedIdentifier": "10.5555/publication",
                                    "relatedIdentifierType": "DOI",
                                    "relationType": "References",
                                }
                            ],
                            "url": "https://osf.io/z4752/",
                        },
                    }
                ]
            }
        return {"data": []}

    candidate = DataCiteRegistrationProvider(fetch).discover(_request()).candidates[0]

    assert candidate.provider == "osf"
    assert candidate.external_id == "z4752"
    assert candidate.linkage_class == "explicit-linkage"
    assert candidate.source_metadata["datacite_relation_types"] == ["References"]
    assert any("10.5555/publication" in call for call in calls)


def test_overlapping_title_and_author_stays_similarity_only_when_date_order_conflicts() -> None:
    candidate = RegistrationCandidate(
        **{
            **_candidate().__dict__,
            "registered_at": "2026-02-01",
            "linkage_class": "similarity-candidate",
            "match_evidence": (),
        }
    )
    evidence = contextual_evidence(_request(), candidate)

    assert {item["kind"] for item in evidence} == {"title-terms", "contributor-overlap", "date-order"}
    assert contextual_class(evidence) == "similarity-candidate"


def test_multiple_candidates_stay_separate_unattached_records(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Multiple registrations", csl_json={"title": "Multiple registrations"})
        upsert_registration_candidates(conn, paper_id, [_candidate("ab12c"), _candidate("xy789")])
        rows = list_registration_links(conn, paper_id)
    engine.dispose()

    assert {row["external_id"] for row in rows} == {"ab12c", "xy789"}
    assert all(row["link_status"] == "candidate" for row in rows)
    assert all(row["attachment_id"] is None for row in rows)


def test_one_registration_identity_can_link_to_multiple_papers(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        first = create_paper(conn, title="Report one", csl_json={"title": "Report one"})
        second = create_paper(conn, title="Report two", csl_json={"title": "Report two"})
        upsert_registration_candidates(conn, first, [_candidate("shared1")])
        upsert_registration_candidates(conn, second, [_candidate("shared1")])
        first_link = list_registration_links(conn, first)[0]
        second_link = list_registration_links(conn, second)[0]
    engine.dispose()

    assert first_link["external_id"] == second_link["external_id"] == "shared1"
    assert first_link["id"] != second_link["id"]
    assert first_link["paper_id"] != second_link["paper_id"]


def test_registry_keeps_direct_candidates_when_another_provider_fails() -> None:
    class BrokenProvider:
        id = "broken"

        def discover(self, request: DiscoveryRequest) -> ProviderReport:
            raise RegistryHttpError(503, "provider unavailable")

    reference = DiscoveryReference(
        "aspredicted", "xy12", "https://aspredicted.org/xy12.pdf", "text", True, "AsPredicted xy12"
    )
    registry = RegistrationDiscoveryRegistry().register(BrokenProvider()).register(DirectReferenceProvider())

    candidates, reports = registry.discover(_request(references=(reference,)))

    assert [(item.provider, item.external_id) for item in candidates] == [("aspredicted", "xy12")]
    assert [(item.provider, item.status) for item in reports] == [("broken", "error"), ("direct-reference", "ok")]


def test_registry_http_allows_only_fixed_https_provider_origins() -> None:
    _validate_registry_url("https://api.osf.io/v2/registrations/ab12c/")
    _validate_registry_url("https://api.datacite.org/dois?query=registration")
    for unsafe in (
        "http://api.osf.io/v2/registrations/ab12c/",
        "https://api.osf.io.evil.example/v2/registrations/ab12c/",
        "https://user:secret@api.datacite.org/dois",
        "https://api.osf.io/internal",
        "https://127.0.0.1/v2/registrations/ab12c/",
    ):
        try:
            _validate_registry_url(unsafe)
        except RegistryHttpError as exc:
            assert exc.status == 400
        else:
            raise AssertionError(f"unsafe registry URL accepted: {unsafe}")


class _RecordingProvider:
    id = "fixture"

    def __init__(self) -> None:
        self.requests: list[DiscoveryRequest] = []

    def discover(self, request: DiscoveryRequest) -> ProviderReport:
        self.requests.append(request)
        return ProviderReport(provider=self.id, status="ok", candidates=(_candidate(),))


def _paper_and_client(temp_db_url: str):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Attention and memory",
            doi="10.5555/publication",
            year=2024,
            abstract="This full paper text must never enter a discovery request.",
            csl_json={
                "title": "Attention and memory",
                "author": [{"given": "Ada", "family": "Lovelace"}],
            },
        )
    engine.dispose()
    provider = _RecordingProvider()
    registry = RegistrationDiscoveryRegistry().register(provider)
    return paper_id, provider, TestClient(create_app(db_url=temp_db_url, registration_discovery_registry=registry))


def _discover(client: TestClient, paper_id: int, *, fresh: bool = False) -> dict:
    started = client.post(
        f"/papers/{paper_id}/registration-discovery",
        json={"metadata_consent": True, "fresh": fresh},
    )
    assert started.status_code == 202, started.text
    result = client.get(f"/registration-discovery/{started.json()['job_id']}")
    assert result.status_code == 200
    assert result.json()["status"] == "done", result.json()
    return result.json()


def test_preview_is_local_and_consent_is_required(temp_db_url: str) -> None:
    paper_id, provider, client = _paper_and_client(temp_db_url)

    preview = client.get(f"/papers/{paper_id}/registration-discovery/preview").json()

    assert preview["metadata_fields"] == ["paper DOI", "paper title"]
    assert preview["local_match_fields"] == ["author names", "publication year"]
    assert provider.requests == []
    refused = client.post(
        f"/papers/{paper_id}/registration-discovery",
        json={"metadata_consent": False},
    )
    assert refused.status_code == 422
    assert provider.requests == []


def test_discovery_persists_candidates_without_attaching_and_sends_no_document_text(temp_db_url: str) -> None:
    paper_id, provider, client = _paper_and_client(temp_db_url)

    result = _discover(client, paper_id)

    assert result["providers"] == [{"provider": "fixture", "status": "ok", "detail": None, "candidate_count": 1}]
    candidate = result["candidates"][0]
    assert candidate["linkage_label"] == "Explicitly linked"
    assert candidate["link_status"] == "candidate"
    assert candidate["attachment_id"] is None
    assert len(provider.requests) == 1
    sent = provider.requests[0]
    assert sent.doi == "10.5555/publication"
    assert sent.title == "Attention and memory"
    assert not hasattr(sent, "abstract")
    assert "full paper text" not in repr(sent)


def test_confirm_reject_and_fresh_search_lifecycle(temp_db_url: str) -> None:
    paper_id, _provider, client = _paper_and_client(temp_db_url)
    candidate = _discover(client, paper_id)["candidates"][0]

    confirmed = client.post(f"/papers/{paper_id}/registration-links/{candidate['id']}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["link_status"] == "confirmed"
    assert confirmed.json()["attachment_id"] is None

    rejected = client.post(f"/papers/{paper_id}/registration-links/{candidate['id']}/reject")
    assert rejected.status_code == 200
    assert _discover(client, paper_id)["candidates"] == []
    resurfaced = _discover(client, paper_id, fresh=True)["candidates"]
    assert len(resurfaced) == 1
    assert resurfaced[0]["link_status"] == "candidate"
