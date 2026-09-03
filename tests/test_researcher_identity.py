"""Regression coverage for first-class ORCID identity and safe OpenAlex linkage."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.researcher_identity import InvalidOrcid, normalize_orcid, normalize_person_name
from integrations.openalex.author import OpenAlexAuthorClient

VASILIKI_NAME = "Vasiliki Meletaki"
VASILIKI_ORCID = "0000-0002-3521-7707"
VASILIKI_OPENALEX = "A5085857730"


def _vasiliki_author() -> dict:
    return {
        "id": f"https://openalex.org/{VASILIKI_OPENALEX}",
        "display_name": VASILIKI_NAME,
        "orcid": f"https://orcid.org/{VASILIKI_ORCID}",
        "works_count": 21,
    }


class _VasilikiFetcher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url, *, params, headers, timeout):
        self.calls.append((url, params))
        if "/authors/orcid:" in url:
            return 200, _vasiliki_author()
        if url.endswith("/works"):
            return 200, {"results": [], "meta": {"next_cursor": None}}
        if url.endswith("/authors"):
            return 200, {"results": [_vasiliki_author()], "meta": {"count": 1}}
        return 404, None


@pytest.mark.parametrize(
    "value",
    [
        VASILIKI_ORCID,
        f"https://orcid.org/{VASILIKI_ORCID}",
        f"  https://www.orcid.org/{VASILIKI_ORCID}/  ",
    ],
)
def test_vasiliki_orcid_forms_normalize(value):
    assert normalize_orcid(value) == VASILIKI_ORCID


def test_orcid_checksum_is_validated_independently_of_openalex():
    with pytest.raises(InvalidOrcid):
        normalize_orcid("0000-0002-3521-7708")


def test_name_comparison_tolerates_bibliographic_variation():
    assert normalize_person_name("  VASILIKI  MELETÁKI ") == normalize_person_name(VASILIKI_NAME)


def test_valid_orcid_establishes_identity_before_openalex(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.put(
        "/my-publications/profile",
        json={"display_name": None, "orcid": f" https://orcid.org/{VASILIKI_ORCID} "},
    )
    assert response.status_code == 200
    assert response.json() == {
        "display_name": None,
        "name_variants": [],
        "orcid": VASILIKI_ORCID,
        "has_author_id": False,
        "identity_established": True,
        "identity_method": "orcid",
        "enrichment_status": "not_started",
        "dismissed": False,
    }


def test_invalid_orcid_is_rejected_without_persistence(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    response = client.put(
        "/my-publications/profile", json={"display_name": VASILIKI_NAME, "orcid": "0000-0002-3521-7708"}
    )
    assert response.status_code == 422
    assert client.get("/my-publications/profile").json()["orcid"] is None


def test_vasiliki_orcid_links_to_known_openalex_record(temp_db_url):
    fetcher = _VasilikiFetcher()
    author_client = OpenAlexAuthorClient(fetcher=fetcher)
    api = TestClient(create_app(db_url=temp_db_url, openalex_author_client=author_client))
    saved = api.put(
        "/my-publications/profile",
        json={"display_name": VASILIKI_NAME, "orcid": f"https://orcid.org/{VASILIKI_ORCID}"},
    )
    assert saved.status_code == 200 and saved.json()["identity_established"] is True

    started = api.post("/my-publications/refresh").json()
    finished = api.get(f"/my-publications/refresh/{started['job_id']}").json()
    assert finished["status"] == "done"
    assert finished["summary"]["status"] == "ok"
    assert finished["summary"]["openalex_author_id"] == VASILIKI_OPENALEX
    assert finished["summary"]["enrichment_status"] == "linked"
    profile = api.get("/my-publications/profile").json()
    assert profile["identity_established"] is True
    assert profile["has_author_id"] is True
    assert profile["enrichment_status"] == "linked"


@pytest.mark.parametrize("provider_behavior", ["not_found", "timeout"])
def test_openalex_failure_does_not_invalidate_orcid_identity(temp_db_url, provider_behavior):
    def fetcher(url, *, params, headers, timeout):
        if provider_behavior == "timeout":
            raise TimeoutError("simulated")
        return 404, None

    api = TestClient(create_app(db_url=temp_db_url, openalex_author_client=OpenAlexAuthorClient(fetcher=fetcher)))
    assert (
        api.put("/my-publications/profile", json={"display_name": None, "orcid": VASILIKI_ORCID}).json()[
            "identity_established"
        ]
        is True
    )
    started = api.post("/my-publications/refresh").json()
    result = api.get(f"/my-publications/refresh/{started['job_id']}").json()["summary"]
    assert result["identity_established"] is True
    assert result["status"] == ("enrichment-not-found" if provider_behavior == "not_found" else "enrichment-failed")
    assert result["diagnostic"]["code"] == (
        "IDENTITY_ENRICHMENT_OPENALEX_NOT_FOUND"
        if provider_behavior == "not_found"
        else "IDENTITY_ENRICHMENT_OPENALEX_FAILED"
    )
    assert api.get("/my-publications/profile").json()["identity_established"] is True


def test_openalex_orcid_mismatch_is_rejected_with_reason(temp_db_url):
    wrong = _vasiliki_author() | {"orcid": "https://orcid.org/0000-0002-1825-0097"}
    client = OpenAlexAuthorClient(fetcher=lambda url, **kwargs: (200, wrong))
    with make_engine(temp_db_url).begin() as conn:
        result = client.resolve_author_result(conn, orcid=VASILIKI_ORCID)
    assert result.author is None
    assert result.state == "candidate_rejected"
    assert result.rejection_reason == "returned_orcid_mismatch"
    assert result.candidate_orcid_match is False


def test_ambiguous_surname_does_not_block_exact_full_name_variant(temp_db_url):
    def fetcher(url, *, params, headers, timeout):
        query = params.get("filter", "")
        if query.endswith(":Meletaki"):
            return 200, {
                "results": [
                    {"id": "https://openalex.org/A1", "display_name": "Anna Meletaki"},
                    _vasiliki_author(),
                ],
                "meta": {"count": 2},
            }
        if query.endswith(f":{VASILIKI_NAME}"):
            return 200, {"results": [_vasiliki_author()], "meta": {"count": 1}}
        return 404, None

    client = OpenAlexAuthorClient(fetcher=fetcher)
    with make_engine(temp_db_url).begin() as conn:
        result = client.resolve_author_result(conn, names=["Meletaki", VASILIKI_NAME])
    assert result.state == "matched"
    assert result.author is not None and result.author.author_id == VASILIKI_OPENALEX


def test_ambiguous_surname_alone_fails_safely(temp_db_url):
    body = {
        "results": [
            {"id": "https://openalex.org/A1", "display_name": "Anna Meletaki"},
            {"id": "https://openalex.org/A2", "display_name": "Maria Meletaki"},
        ],
        "meta": {"count": 2},
    }
    client = OpenAlexAuthorClient(fetcher=lambda url, **kwargs: (200, body))
    with make_engine(temp_db_url).begin() as conn:
        result = client.resolve_author_result(conn, names=["Meletaki"])
    assert result.author is None
    assert result.state == "candidate_rejected"
    assert result.rejection_reason == "ambiguous_name"
