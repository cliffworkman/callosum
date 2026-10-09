"""Opt-in pytest plugin: execute every historical battery API call omitted AND explicit legacy.

Load with -p experiments.ask_cli_revised.test_i4_2b3_legacy_parity_plugin.
It never changes production dispatch, fixture expectations, or the frozen batteries.
"""

import functools

import pytest

from experiments.ask_cli_revised import assertion_authority as aa

MODULES = {
    "test_assertion_authority",
    "test_assertion_authority_i4_1b",
    "test_assertion_authority_i4_1c",
    "test_assertion_authority_i4_1f",
}


@pytest.fixture(autouse=True)
def paired_legacy_calls(request, monkeypatch):
    if request.module.__name__.split(".")[-1] not in MODULES:
        return

    def paired(original):
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            if "ruleset_version" in kwargs:
                return original(*args, **kwargs)
            try:
                omitted = original(*args, **kwargs)
            except ValueError as error:
                with pytest.raises(ValueError) as explicit:
                    original(*args, **kwargs, ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F)
                assert str(error) == str(explicit.value)
                raise
            explicit = original(*args, **kwargs, ruleset_version=aa.ASSERTION_AUTHORITY_RULESET_I4_1F)
            assert omitted == explicit
            return omitted

        return wrapper

    for name in (
        "classify_assertion_authority",
        "classify_target_assertions",
        "locate_containing_assertion",
        "classify_surface",
        "classify_all_occurrences",
        "aggregation",
    ):
        monkeypatch.setattr(aa, name, paired(getattr(aa, name)))
