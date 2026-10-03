"""Exact Ioannidis acceptance PDF plus adversarial review/identity boundaries; no network."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from sqlalchemy import func, select

from app.backend.capture.provisional_evidence import _Evidence, _extract_candidates, _resolve_and_score
from app.backend.capture.provisional_review import best_candidate, explain_evidence
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import papers
from tests.test_capture import _client, _direct_pdf_capture_id, _paired
from tests.test_import_queue import (
    _assert_sidecar_mirrors_db,
    _ui_instance,  # noqa: F401 -- shared isolated capture fixture
)

FIXTURES = Path(__file__).parent / "fixtures" / "capture"
PDF = FIXTURES / "ioannidis-pmed.0020124.pdf"
DOI = "10.1371/journal.pmed.0020124"
TITLE = "Why Most Published Research Findings Are False"


class Resolver:
    def __init__(self, title=TITLE, resolved=True):
        self.calls = []
        self.title = title
        self.resolved = resolved

    def resolve_doi(self, conn, doi):
        self.calls.append(doi)
        return SimpleNamespace(
            resolved=self.resolved,
            csl_json={"DOI": doi, "title": self.title} if self.resolved else None,
            error="unresolved",
        )


def score(pdf, resolver):
    candidates, titles = _extract_candidates(pdf)
    evidence = _Evidence()
    automatic = _resolve_and_score(None, candidates, titles, crossref_client=resolver, evidence=evidence)
    return automatic, json.loads(evidence.as_json())


def synthetic(tmp_path, *, dois, section=None, metadata=None, title=TITLE, caption=None):
    path = tmp_path / "fixture.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        if metadata:
            doc.set_metadata({"title": metadata})
        page.insert_text((60, 65), title, fontsize=18)
        if section:
            page.insert_text((60, 120), section)
        for i, doi in enumerate(dois):
            text = f"{caption}\nDOI: {doi}" if caption else f"DOI: {doi}"
            page.insert_text((60, 200 + 60 * i), text)
        doc.save(path)
    return path


def test_exact_ioannidis_pdf_retains_body_gate_but_offers_article_for_review():
    original = json.loads((FIXTURES / "ioannidis-acceptance.json").read_text())
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == original["pdf_sha256"]
    resolver = Resolver()
    automatic, evidence = score(PDF, resolver)
    assert automatic is None and resolver.calls == [] and evidence["resolutions"] == []
    assert evidence["title_candidates"] == [TITLE]
    assert [(c["doi"], c["page"], c["position_class"]) for c in evidence["candidates"]] == [
        (DOI, 1, "body"),
        (DOI + ".t001", 2, "figure_table"),
        (DOI + ".t002", 2, "figure_table"),
        (DOI + ".g001", 3, "figure_table"),
        (DOI + ".t003", 3, "figure_table"),
    ]
    assert best_candidate(evidence) == {
        "doi": DOI,
        "title": None,
        "disposition": "observed_unverified",
        "page": 1,
        "position_class": "body",
    }
    assert "not been verified" in explain_evidence(evidence)


def test_original_acceptance_evidence_is_readable_without_rewriting_manual_provenance():
    evidence = json.loads((FIXTURES / "ioannidis-acceptance.json").read_text())["evidence"]
    before = copy.deepcopy(evidence)
    assert best_candidate(evidence)["doi"] == DOI
    assert "No DOI-shaped" not in explain_evidence(evidence)
    assert evidence == before
    assert evidence["title_candidates"] == ["PLME0208_696-701.indd"]
    assert evidence["resolutions"] == []
    assert evidence["user_actions"][0]["action"] == "user_entered_doi"
    assert evidence["user_actions"][0]["at"] == "2026-09-24T22:54:36.707717+00:00"


@pytest.mark.parametrize(
    "section,dois,caption",
    [
        ("References", [DOI], None),
        (None, [DOI + ".t001"], None),
        (None, [DOI + ".g001"], None),
        (None, ["10.1234/object"], "Table 1. An unrelated table"),
        (None, ["10.1234/object"], "Figure 2. An unrelated figure"),
    ],
)
def test_reference_and_component_only_never_resolve_or_offer_article(tmp_path, section, dois, caption):
    resolver = Resolver()
    automatic, evidence = score(synthetic(tmp_path, dois=dois, section=section, caption=caption), resolver)
    assert automatic is None and resolver.calls == []
    assert best_candidate(evidence) is None
    assert "No DOI-shaped" not in explain_evidence(evidence)


@pytest.mark.parametrize("section", [None, "Abstract"])
def test_ambiguous_distinct_article_dois_not_arbitrarily_selected(tmp_path, section):
    resolver = Resolver()
    automatic, evidence = score(synthetic(tmp_path, dois=[DOI, "10.1234/other"], section=section), resolver)
    assert automatic is None and best_candidate(evidence) is None
    assert "No DOI-shaped" not in explain_evidence(evidence)


def test_unresolved_doi_is_offered_as_unverified_without_another_lookup(tmp_path):
    resolver = Resolver(resolved=False)
    automatic, evidence = score(synthetic(tmp_path, dois=[DOI]), resolver)
    assert automatic is None and resolver.calls == [DOI]
    assert best_candidate(evidence)["disposition"] == "observed_unverified"
    assert "could not be resolved" in explain_evidence(evidence)
    assert resolver.calls == [DOI]


def test_misleading_internal_title_cannot_corroborate_wrong_resolved_work(tmp_path):
    wrong = "A Different Article About Research Methods"
    resolver = Resolver(title=wrong)
    automatic, evidence = score(synthetic(tmp_path, dois=[DOI], metadata=wrong), resolver)
    assert automatic is None
    assert evidence["title_candidates"] == [TITLE]
    assert evidence["resolutions"][0]["disposition"] == "insufficient_corroboration"


def test_visible_title_can_corroborate_actual_front_matter_despite_filename_metadata(tmp_path):
    resolver = Resolver()
    automatic, evidence = score(synthetic(tmp_path, dois=[DOI], metadata="layout-123.indd"), resolver)
    assert automatic == DOI
    assert evidence["title_candidates"] == [TITLE]


def test_body_doi_matching_title_stays_review_only(tmp_path):
    resolver = Resolver()
    automatic, evidence = score(synthetic(tmp_path, dois=[DOI], section="Abstract"), resolver)
    assert automatic is None and resolver.calls == []
    assert best_candidate(evidence)["disposition"] == "observed_unverified"


@pytest.mark.parametrize("position", ["front_matter", "body", "references", "figure_table", "unknown"])
def test_any_recorded_observation_never_says_not_found(position):
    assert "No DOI-shaped" not in explain_evidence({"candidates": [{"doi": DOI, "position_class": position}]})


def test_real_pdf_preview_and_confirmation_preserve_evidence_and_require_admission(temp_db_url):
    client = _client(temp_db_url)
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    response = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=PDF.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert response.json()["status"] == "direct_pdf_queued_for_review"
    item = client.get("/library/import-queue").json()["items"][0]
    assert item["best_candidate"]["doi"] == DOI
    assert item["best_candidate"]["page"] == 1
    assert item["best_candidate"]["position_class"] == "body"
    artifact_id = item["artifact_id"]
    path = f"/library/import-queue/{artifact_id}"
    before = client.get(path).json()["evidence"]
    client.app.state.crossref_client = Resolver(resolved=False)
    assert client.post(path + "/preview-doi", json={"doi": DOI}).json()["status"] == "unresolved"
    # Even a direct request cannot bypass resolver admission merely because text was observed.
    assert (
        client.post(path + "/confirm", json={"doi": DOI, "source": "candidate"}).json()["promotion_state"]
        == "pending_review"
    )
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == 0
    unresolved = _assert_sidecar_mirrors_db(client, artifact_id)
    assert unresolved["user_actions"][0]["action"] == "user_confirmed_candidate"
    client.app.state.crossref_client = Resolver()
    preview_before = client.get(path).json()["evidence"]
    assert client.post(path + "/preview-doi", json={"doi": DOI}).json()["title"] == TITLE
    assert client.get(path).json()["evidence"] == preview_before
    response = client.post(path + "/confirm", json={"doi": DOI, "source": "candidate"})
    assert response.json()["promotion_state"] == "promoted"
    after = client.get(path).json()["evidence"]
    for field in ("candidates", "title_candidates", "resolutions"):
        assert after[field] == before[field]
    assert len(after["user_actions"]) == 2
    assert all(a["action"] == "user_confirmed_candidate" for a in after["user_actions"])
    assert after["user_actions"][:-1] == unresolved["user_actions"]
    assert _assert_sidecar_mirrors_db(client, artifact_id) == after
    engine.dispose()


@pytest.mark.parametrize("failure", [None, "extraction", "resolution"])
def test_pipeline_failure_is_not_a_successful_scan_with_no_doi(temp_db_url, tmp_path, monkeypatch, failure):
    from app.backend.acquisition.fetch import library_dir
    from app.backend.capture import provisional

    sensitive = "/Users/private/secret-folder/document.pdf session_token=must-not-be-exposed"

    def fail(*args, **kwargs):
        raise RuntimeError(sensitive)

    # Fail after bytes were saved, at the actual extraction/resolution seam. The
    # no-failure case uses a genuinely inspected PDF containing no identifier.
    pdf = synthetic(tmp_path, dois=[DOI] if failure == "resolution" else [])
    if failure == "extraction":
        monkeypatch.setattr(provisional, "_extract_candidates", fail)
    client = _client(temp_db_url)
    if failure == "resolution":
        monkeypatch.setattr(client.app.state.crossref_client, "resolve_doi", fail)
    headers = _paired(client)
    capture_id = _direct_pdf_capture_id(client, headers)
    result = client.post(
        f"/capture/item/{capture_id}/pdf",
        content=pdf.read_bytes(),
        headers={**headers, "content-type": "application/pdf"},
    )
    assert result.json()["status"] == "direct_pdf_queued_for_review"
    item = client.get("/library/import-queue").json()["items"][0]
    detail = client.get(f"/library/import-queue/{item['artifact_id']}")
    evidence = detail.json()["evidence"]
    assert sensitive not in detail.text and "secret-folder" not in item["explanation"]
    assert item["identity_state"] == "unresolved" and item["promotion_state"] == "pending_review"
    assert evidence["schema_version"] == 1
    assert (
        item["explanation"]
        == {
            None: "No DOI-shaped text was found in this PDF's first pages.",
            "extraction": "Callosum couldn't inspect this PDF for identifiers. The PDF is saved for review.",
            "resolution": "DOI text was found, but its metadata lookup could not be completed. The PDF is saved for review.",
        }[failure]
    )
    if failure == "resolution":
        assert evidence["candidates"][0]["doi"] == DOI
        assert item["best_candidate"]["disposition"] == "observed_unverified"
    else:
        assert evidence["candidates"] == [] and item["best_candidate"] is None
    assert list(provisional.queue_dir(library_dir()).glob("*.pdf"))[0].read_bytes() == pdf.read_bytes()
    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(papers)).scalar_one() == 0
    engine.dispose()


def test_schema_one_empty_evidence_does_not_invent_extraction_failure():
    assert "No DOI-shaped text" in explain_evidence({"schema_version": 1, "candidates": [], "resolutions": []})
    assert "couldn't inspect" in explain_evidence(
        {
            "schema_version": 1,
            "candidates": [],
            "resolutions": [],
            "decision_reason": "extraction failed; treated as unresolved",
        }
    )
