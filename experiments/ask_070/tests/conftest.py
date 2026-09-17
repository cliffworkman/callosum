import pytest

from experiments.ask_070.offline_guard import offline_guard


@pytest.fixture(autouse=True)
def deny_model_and_network():
    with offline_guard():
        yield
