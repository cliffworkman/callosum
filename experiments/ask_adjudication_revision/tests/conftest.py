import pytest

from experiments.ask_adjudication_revision.guard import offline_guard


@pytest.fixture(autouse=True)
def synthetic_offline_boundaries():
    with offline_guard():
        yield
