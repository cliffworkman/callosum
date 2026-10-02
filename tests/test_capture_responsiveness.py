"""Real request scheduling with controlled blocking work, not a wall-clock benchmark."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import anyio
from sqlalchemy import func, select
from starlette.requests import Request

from app.backend.api.routers import capture
from app.backend.persistence.schema import (
    attachments,
    capture_events,
    chunks,
    embeddings,
    papers,
    provisional_artifacts,
)
from tests.test_capture import _client, _direct_pdf_capture_id, _envelope, _paired, _ui_instance  # noqa: F401

PDF = Path(__file__).parent / "fixtures/capture/ioannidis-pmed.0020124.pdf"
URL = "https://journals.plos.org/plosmedicine/article/file?id=10.1371/journal.pmed.0020124&type=printable"


class ResponseProbe:
    """Observe the actual ASGI response, not TestClient's later background-task completion."""

    def __init__(self, app, sent):
        self.app = app
        self.sent = sent

    async def __call__(self, scope, receive, send):
        async def observe(message):
            await send(message)
            if (
                scope.get("path") == "/capture/item"
                and message["type"] == "http.response.body"
                and not message.get("more_body")
            ):
                self.sent.set()

        await self.app(scope, receive, observe)


def test_cold_index_does_not_hold_response_health_or_repeat_admission(temp_db_url, monkeypatch):
    entered, release, sent = Event(), Event(), Event()
    original = capture.ensure_paper_indexed
    calls = []

    def blocked_index(*args, **kwargs):
        calls.append(args[1])
        entered.set()
        assert release.wait(15), "test must release model work"
        return original(*args, **kwargs)

    monkeypatch.setattr(capture, "ensure_paper_indexed", blocked_index)
    with _client(temp_db_url) as client, ThreadPoolExecutor(max_workers=3) as pool:
        # TestClient has initialized the stack; wrap the ASGI app without changing routes.
        client.app = ResponseProbe(client.app, sent)
        client._transport.app = client.app
        app = client.app.app
        headers = {**_paired(client), "Idempotency-Key": "cold-index-one-intent"}
        before = app.state.capture_updates.revision
        first = pool.submit(client.post, "/capture/item", json=_envelope(), headers=headers)
        try:
            assert entered.wait(10)
            assert sent.wait(5), "metadata response must precede model completion"
            health = pool.submit(client.get, "/health").result(timeout=5)
            assert health.status_code == 200 and health.json()["db_reachable"]
            assert app.state.capture_updates.revision != before
            repeated = pool.submit(client.post, "/capture/item", json=_envelope(), headers=headers).result(timeout=5)
            assert repeated.status_code == 200
            assert len(calls) == 1
            with app.state.engine.connect() as conn:
                assert conn.scalar(select(func.count()).select_from(papers)) == 1
        finally:
            release.set()
        assert first.result(timeout=10).json() == repeated.json()
        with app.state.engine.connect() as conn:
            assert conn.scalar(select(func.count()).select_from(embeddings)) == 1


def test_concurrent_same_key_admission_waits_without_blocking_health(temp_db_url, monkeypatch):
    entered, release = Event(), Event()
    original = capture.admit
    calls = []

    def blocked_admit(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(15)
        return original(*args, **kwargs)

    monkeypatch.setattr(capture, "admit", blocked_admit)
    with _client(temp_db_url) as client, ThreadPoolExecutor(max_workers=3) as pool:
        headers = {**_paired(client), "Idempotency-Key": "concurrent-one-intent"}
        first = pool.submit(client.post, "/capture/item", json=_envelope(), headers=headers)
        try:
            assert entered.wait(10)
            second = pool.submit(client.post, "/capture/item", json=_envelope(), headers=headers)
            assert pool.submit(client.get, "/health").result(timeout=5).status_code == 200
        finally:
            release.set()
        assert first.result(timeout=10).json() == second.result(timeout=10).json()
        assert len(calls) == 1


def test_original_pdf_concurrent_encounters_queue_once_without_loading_model(temp_db_url, monkeypatch):
    def forbidden_index(*args, **kwargs):
        raise AssertionError("Unverified provisional PDF must not require metadata indexing")

    monkeypatch.setattr(capture, "ensure_paper_indexed", forbidden_index)
    with _client(temp_db_url) as client, ThreadPoolExecutor(max_workers=3) as pool:
        # Real model inference is forbidden even if accidentally reached by another pipeline.
        monkeypatch.setattr(type(client.app.state.embedding_model), "encode_texts", forbidden_index)
        headers = _paired(client)
        ids = [_direct_pdf_capture_id(client, headers, source_url=URL) for _ in range(2)]
        data = PDF.read_bytes()
        uploads = [
            pool.submit(client.post, f"/capture/item/{capture_id}/pdf", content=data, headers=headers)
            for capture_id in ids
        ]
        for future in uploads:
            result = future.result(timeout=15)
            assert result.status_code == 200
            assert result.json()["status"] == "direct_pdf_queued_for_review"
        replay = client.post(f"/capture/item/{ids[0]}/pdf", content=data, headers=headers)
        assert replay.status_code == 200
        queue = client.get("/library/import-queue").json()["items"]
        assert len(queue) == 1 and queue[0]["encounter_count"] == 2
        detail = client.get(f"/library/import-queue/{queue[0]['artifact_id']}").json()
        assert detail["best_candidate"]["disposition"] == "observed_unverified"
        assert detail["best_candidate"]["doi"] == "10.1371/journal.pmed.0020124"
        assert detail["evidence"]["title_candidates"] == ["Why Most Published Research Findings Are False"]
        assert detail["evidence"]["resolutions"] == []
        with client.app.state.engine.connect() as conn:
            for table in [papers, attachments, chunks, embeddings]:
                assert conn.scalar(select(func.count()).select_from(table)) == 0
            assert conn.scalar(select(func.count()).select_from(provisional_artifacts)) == 1
            assert conn.scalar(select(func.count()).select_from(capture_events)) == 2


def test_index_failure_keeps_successful_admission_and_notifies(temp_db_url, monkeypatch, caplog):
    def failed_index(*args, **kwargs):
        raise RuntimeError("controlled unavailable model")

    monkeypatch.setattr(capture, "ensure_paper_indexed", failed_index)
    with _client(temp_db_url) as client:
        before = client.app.state.capture_updates.revision
        response = client.post("/capture/item", json=_envelope(), headers=_paired(client))
        assert response.status_code == 200 and response.json()["created"]
        assert client.app.state.capture_updates.revision != before
        assert "metadata indexing unavailable" in caplog.text
        assert len(client.get("/papers").json()) == 1


def test_pdf_worker_keeps_health_live_and_owns_temp_until_completion(temp_db_url, monkeypatch):
    entered, release = Event(), Event()
    original = capture._process_capture_pdf
    paths = []

    def blocked_pdf(capture_id, request, engine, temp_path, total):
        paths.append(temp_path)
        entered.set()
        assert release.wait(15)
        assert temp_path.exists(), "upload must remain owned until the worker completes"
        return original(capture_id, request, engine, temp_path, total)

    monkeypatch.setattr(capture, "_process_capture_pdf", blocked_pdf)
    with _client(temp_db_url) as client, ThreadPoolExecutor(max_workers=2) as pool:
        headers = _paired(client)
        capture_id = _direct_pdf_capture_id(client, headers, source_url=URL)
        upload = pool.submit(client.post, f"/capture/item/{capture_id}/pdf", content=PDF.read_bytes(), headers=headers)
        try:
            assert entered.wait(10)
            assert paths[0].exists()
            assert pool.submit(client.get, "/health").result(timeout=5).status_code == 200
        finally:
            release.set()
        assert upload.result(timeout=15).json()["status"] == "direct_pdf_queued_for_review"
        assert not paths[0].exists()


def test_structured_cancellation_waits_for_pdf_worker_cleanup(monkeypatch):
    entered, release = Event(), Event()
    paths = []
    capture_id = "a" * 32
    monkeypatch.setitem(capture._pending, capture_id, object())

    def blocked_pdf(_id, _request, _engine, temp_path, _total):
        paths.append(temp_path)
        entered.set()
        assert release.wait(15)
        assert temp_path.exists()
        return None

    monkeypatch.setattr(capture, "_process_capture_pdf", blocked_pdf)

    async def exercise():
        async def receive():
            return {"type": "http.request", "body": b"%PDF-test", "more_body": False}

        app = SimpleNamespace(state=SimpleNamespace(capture_work_lock=anyio.Lock()))
        request = Request({"type": "http", "headers": [], "app": app}, receive)
        async with anyio.create_task_group() as group:
            group.start_soon(capture.capture_pdf, capture_id, request, None, None)
            try:
                assert await anyio.to_thread.run_sync(entered.wait, 10)
                group.cancel_scope.cancel()
                with anyio.CancelScope(shield=True):
                    await anyio.sleep(0)
                    assert paths[0].exists()
            finally:
                release.set()
        assert not paths[0].exists()

    anyio.run(exercise)
