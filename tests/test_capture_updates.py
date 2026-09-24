from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.backend import app_settings
from app.backend.api import create_app
from app.backend.api.capture_updates import CaptureUpdates


def test_change_wakes_all_waiters_without_waiting_for_timeout():
    async def run():
        signal = CaptureUpdates()
        before = signal.revision
        tasks = [asyncio.create_task(signal.wait(before, 20)) for _ in range(2)]
        await asyncio.sleep(0)
        assert len(signal._waiters) == 2
        await asyncio.to_thread(signal.changed)  # Worker-thread publishers are also safe.
        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=1)
        assert all(value == signal.revision and value != before for value in results)
        assert not signal._waiters

    asyncio.run(run())


def test_change_before_subscription_or_during_authoritative_fetch_is_not_lost():
    async def run():
        signal = CaptureUpdates()
        before = signal.revision
        signal.changed()
        assert await asyncio.wait_for(signal.wait(before, 20), timeout=1) == signal.revision
        assert not signal._waiters

    asyncio.run(run())


def test_timeout_and_cancellation_release_waiters():
    async def run():
        signal = CaptureUpdates()
        assert await signal.wait(signal.revision, 0.001) == signal.revision
        assert not signal._waiters
        task = asyncio.create_task(signal.wait(signal.revision, 20))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not signal._waiters

    asyncio.run(run())


def test_waiter_budget_is_bounded():
    async def run():
        signal = CaptureUpdates()
        tasks = [asyncio.create_task(signal.wait(signal.revision, 20)) for _ in range(64)]
        await asyncio.sleep(0)
        with pytest.raises(HTTPException) as error:
            await signal.wait(signal.revision, 20)
        assert error.value.status_code == 503
        signal.changed()
        await asyncio.gather(*tasks)
        assert not signal._waiters

    asyncio.run(run())


def test_endpoint_initial_snapshot_bounds_and_app_isolation(temp_db_url):
    first = create_app(db_url=temp_db_url)
    second = create_app(db_url=temp_db_url)
    client = TestClient(first)
    result = client.get("/library/capture-updates").json()
    assert result == {"revision": first.state.capture_updates.revision}
    assert result["revision"] != second.state.capture_updates.revision
    before = result["revision"]
    first.state.capture_updates.changed()
    assert client.get("/library/capture-updates", params={"after": before}).json()["revision"] != before
    for params in [{"after": "x"}, {"after": "a" * 33}, {"wait_seconds": -1}, {"wait_seconds": 26}]:
        assert client.get("/library/capture-updates", params=params).status_code == 422


def test_endpoint_preserves_remote_access_gate(temp_db_url, monkeypatch):
    monkeypatch.setattr(app_settings, "_keyring", lambda: None)
    app_settings.set_access_token("capture-updates-test-token")
    app_settings.set_remote_access_enabled(True)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/capture-updates").status_code == 401
    assert client.get("/library/capture-updates", headers={"Authorization": "Bearer wrong"}).status_code == 401
    result = client.get("/library/capture-updates", headers={"Authorization": "Bearer capture-updates-test-token"})
    assert result.status_code == 200
    assert set(result.json()) == {"revision"}
    assert "capture-updates-test-token" not in result.text


def test_endpoint_preserves_disabled_tunnel_gate(temp_db_url, monkeypatch):
    monkeypatch.setenv("CALLOSUM_TUNNEL_TARGET", "1")
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/capture-updates").status_code == 403
