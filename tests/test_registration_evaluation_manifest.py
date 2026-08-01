"""The registration workflow's curated cases and evaluation dimensions remain explicit and non-composite."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "registration_evaluation_cases.json"


def test_registration_evaluation_manifest_covers_required_failure_modes_without_composite_metric() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ids = {case["id"] for case in cases}
    assert ids == {
        "printed-osf-url",
        "printed-osf-doi",
        "hidden-here-link",
        "multiple-registration-candidates",
        "registration-multiple-papers",
        "false-overlapping-title-authors",
        "multi-study-one-registered",
        "different-sample-sizes",
        "different-exclusion-threshold",
        "primary-outcome-changed",
        "planned-outcome-not-located",
        "new-reported-outcome",
        "disclosed-deviation",
        "registration-after-data-collection",
        "underspecified-registration",
        "manual-local-pdf",
        "registration-amendment",
        "inaccessible-withdrawn-registration",
    }
    assert len(ids) == len(cases)
    assert {case["stage"] for case in cases} >= {
        "reference-extraction",
        "candidate-discovery",
        "candidate-ranking",
        "acquisition",
        "commitment-extraction",
        "publication-retrieval",
        "comparison",
        "timing",
    }
    raw = FIXTURE.read_text(encoding="utf-8").casefold()
    assert "composite" not in raw
    assert "compliance-score" not in raw
