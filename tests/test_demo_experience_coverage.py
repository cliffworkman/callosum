from __future__ import annotations

from tools.qa.check_demo_experience_coverage import validate


def test_every_public_capability_claim_has_an_explicit_demo_disposition() -> None:
    counts = validate()

    assert counts["total"] == 121
    assert counts["homepage_links"] == 12
    assert counts["missing-snapshot"] > 0  # Wave 1 records gaps honestly instead of silently declaring coverage.
