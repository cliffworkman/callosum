"""Transparency-signals auditor (backlog #44 increment 1, inc 250).

Hermetic: a chunk is any object with `.text` + `.page_start`. Covers all 7 detectors (present/not-found), the
repository-link path, the registration + upon_request precondition scoping, the "not detected ≠ absent"
silence≠certificate wording, the no-accusatory-language contract, the no-verdict/no-score contract, and the read-only
endpoint. No gate: the auditor always returns the 7 checks.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.transparency import detect_transparency
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper


@dataclass
class _Chunk:
    text: str
    page_start: int | None = 1


def _detect(*texts):
    return detect_transparency([_Chunk(t) for t in texts])


def _by_key(report, key):
    return next(c for c in report.checks if c.key == key)


# A paper with a full open-science footer (data at OSF, code on GitHub, COI, funding, preregistration).
_OPEN_TEXT = (
    "Data availability: all data are openly available at https://osf.io/ab12c/. Analysis code is available at "
    "https://github.com/lab/study. Conflict of interest: the authors declare no competing interests. Funding: this "
    "work was funded by NIH grant R01-12345. This study was preregistered on AsPredicted (#98765)."
)


def test_full_open_footer_all_present():
    r = _detect(_OPEN_TEXT)
    for key in ("data_availability", "code_availability", "conflict_of_interest", "funding", "preregistration"):
        assert _by_key(r, key).status == "present", key


def test_report_is_exactly_seven_checks():
    r = _detect(_OPEN_TEXT)
    keys = [c.key for c in r.checks]
    assert keys == [
        "data_availability",
        "code_availability",
        "conflict_of_interest",
        "funding",
        "registration",
        "preregistration",
        "upon_request",
    ]


def test_bare_repo_link_trips_data_availability():
    # a repository URL with no "data available" phrase still counts as a data-availability signal
    r = _detect("The materials are hosted at osf.io/xy99z with no further statement.")
    assert _by_key(r, "data_availability").status == "present"


def test_each_detector_not_found():
    bare = "We conducted a survey of 200 participants and report descriptive statistics."
    r = _detect(bare)
    for key in ("data_availability", "code_availability", "conflict_of_interest", "funding", "preregistration"):
        c = _by_key(r, key)
        assert c.status == "not-found", key
        assert "check the paper" in (c.note or "")
        for banned in ("absent", "missing", "concealed", "no open data", "not shared"):
            assert banned not in (c.note or "").lower()


def test_registration_na_for_non_trial():
    r = _detect("We ran a lab experiment on memory with 40 undergraduates.")
    assert _by_key(r, "registration").status == "not-applicable"


def test_registration_present_for_registered_trial():
    r = _detect("This randomized controlled trial was registered at ClinicalTrials.gov (NCT01234567).")
    assert _by_key(r, "registration").status == "present"


def test_registration_not_found_for_unregistered_trial():
    r = _detect("We ran a randomized controlled trial comparing two treatments in 120 patients.")
    assert _by_key(r, "registration").status == "not-found"


def test_upon_request_present_and_na():
    r1 = _detect("Data are available from the corresponding author upon reasonable request.")
    assert _by_key(r1, "upon_request").status == "present"
    r2 = _detect("Data are openly available at osf.io/ab12c.")
    assert _by_key(r2, "upon_request").status == "not-applicable"


def test_no_verdict_no_score():
    r = _detect(_OPEN_TEXT)
    assert not hasattr(r, "score") and not hasattr(r, "grade")
    for c in r.checks:
        d = c.to_dict()
        assert "score" not in d and "grade" not in d
        assert c.status in ("present", "not-found", "not-applicable")


def test_no_accusatory_language():
    src = pathlib.Path("app/backend/methods/transparency.py").read_text(encoding="utf-8").lower()
    assert src  # module exists
    r = _detect("We conducted a survey; no statements were provided.")
    emitted = " ".join((c.note or "") + " " + (c.explainer or "") for c in r.checks).lower()
    for banned in ("concealed", "failed to", "hiding", "no open data", "not shared"):
        assert banned not in emitted, f"emitted status must not accuse: {banned}"
    nf = _by_key(r, "data_availability").note.lower()
    assert "not detected in the extracted text" in nf


def test_evidence_and_basis_on_present_row():
    c = _by_key(_detect(_OPEN_TEXT), "data_availability")
    assert c.status == "present"
    assert c.evidence and c.basis and c.explainer
    assert c.page == 1


# --- the endpoint ------------------------------------------------------------


def test_endpoint_404_unknown(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/99999/transparency").status_code == 404


def test_endpoint_no_chunks_returns_seven_all_not_detected(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="No text", csl_json={"title": "No text"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.get(f"/papers/{pid}/transparency")
    assert r.status_code == 200
    body = r.json()
    # no chunks → all detectors run over empty text: 7 checks, none 'present'
    assert len(body["checks"]) == 7
    assert all(c["status"] != "present" for c in body["checks"])
