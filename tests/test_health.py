from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from tests.api_helpers import (
    _seed_library,
    alembic_head,
)

HEAD = alembic_head()  # the real Alembic head — never a hardcoded revision string (see api_helpers.alembic_head)


def _iter_api_routes(app) -> list[APIRoute]:
    """Every ``APIRoute`` mounted on the app, flattened. FastAPI 0.139 / starlette 1.x restructured routing:
    each ``include_router`` now sits behind a lazy ``_IncludedRouter`` container instead of copying its routes
    flat onto ``app.routes``, so a plain ``for route in app.routes`` sees only the top-level ``/`` shell. We
    descend the ``original_router`` each ``_IncludedRouter`` wraps (callosum includes every router bare — no
    ``prefix`` — so those routes already carry their full paths), plus any generic ``.routes`` container, and
    collect the ``APIRoute`` leaves. Keeps the mutation-surface lockdown below framework-version-independent."""
    out: list[APIRoute] = []

    def walk(routes) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                out.append(route)
            included = getattr(route, "original_router", None)
            if included is not None and getattr(included, "routes", None):
                walk(included.routes)
            elif getattr(route, "routes", None):
                walk(route.routes)

    walk(app.routes)
    return out


def test_health_reports_reachable_and_migrated(temp_db_url: str) -> None:
    response = TestClient(create_app(db_url=temp_db_url)).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["app"] == "callosum"
    assert body["verification_version"] == "local-verifier-v1"
    assert body["db_reachable"] is True
    assert body["db_migrated"] is True  # at head
    assert body["db_revision"] == HEAD
    assert body["db_head_revision"] == HEAD


def test_health_reports_behind_db_as_not_at_head(tmp_path: Path) -> None:
    # A DB stamped one revision behind head must report db_migrated=False with the gap visible.
    db_url = f"sqlite:///{(tmp_path / 'behind.sqlite').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "0001_persistence_core")

    # No `with` → the lifespan startup auto-migrate does NOT run, so the DB stays behind.
    body = TestClient(create_app(db_url=db_url)).get("/health").json()

    assert body["db_reachable"] is True
    assert body["db_migrated"] is False
    assert body["db_revision"] == "0001_persistence_core"
    assert body["db_head_revision"] == HEAD


def test_health_reports_onboarding_completed_and_reflects_settings_change(temp_db_url: str) -> None:
    # inc 416: onboarding_completed rides this same unconditional launch fetch (mirrors read_only's precedent).
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/health").json()["onboarding_completed"] is False
    client.put("/settings", json={"onboarding_completed": True})
    assert client.get("/health").json()["onboarding_completed"] is True


def test_health_app_version_prefers_desktop_shell_env_over_the_dev_git_fallback(temp_db_url: str, monkeypatch) -> None:
    # The desktop shell sets CALLOSUM_APP_VERSION when it spawns this backend as a child process
    # (backend.rs); when it's set, it wins over the dev-only git fallback below.
    monkeypatch.setenv("CALLOSUM_APP_VERSION", "0.3.2")
    assert TestClient(create_app(db_url=temp_db_url)).get("/health").json()["app_version"] == "0.3.2"


def test_health_app_version_falls_back_to_a_dev_git_identifier_outside_the_shell(temp_db_url: str, monkeypatch) -> None:
    # A plain uvicorn/dev run or the remote-access tunnel never sets CALLOSUM_APP_VERSION — this repo
    # IS a real git checkout during tests, so app_version should be a "dev-<sha>" identifier (never
    # verification_version, an unrelated internal pipeline-version constant the connection tooltip
    # used to show by mistake, and never a fabricated release version).
    from app.backend.api.routers import health as health_module

    health_module._dev_git_version.cache_clear()
    monkeypatch.delenv("CALLOSUM_APP_VERSION", raising=False)
    version = TestClient(create_app(db_url=temp_db_url)).get("/health").json()["app_version"]
    assert version is not None
    assert re.fullmatch(r"dev-[0-9a-f]+\+?", version), version


def test_health_app_version_dev_fallback_is_none_when_git_is_unavailable(temp_db_url: str, monkeypatch) -> None:
    from app.backend.api.routers import health as health_module

    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not found")

    health_module._dev_git_version.cache_clear()
    monkeypatch.delenv("CALLOSUM_APP_VERSION", raising=False)
    monkeypatch.setattr(health_module.subprocess, "run", _boom)
    assert TestClient(create_app(db_url=temp_db_url)).get("/health").json()["app_version"] is None
    health_module._dev_git_version.cache_clear()  # don't leak the mocked-None result into later tests


def test_frontend_root_serves_configured_html_file(temp_db_url: str, tmp_path: Path) -> None:
    frontend = tmp_path / "callosum-app.html"
    frontend.write_text("<!doctype html><html><head><title>Callosum</title></head><body>Callosum shell</body></html>")
    client = TestClient(create_app(db_url=temp_db_url, frontend_path=frontend))

    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Callosum</title>" in response.text
    assert "Callosum shell" in response.text


def test_frontend_static_route_does_not_shadow_json_endpoints(temp_db_url: str, tmp_path: Path) -> None:
    _seed_library(temp_db_url)
    frontend = tmp_path / "callosum-app.html"
    frontend.write_text("<!doctype html><title>Callosum</title>")
    client = TestClient(create_app(db_url=temp_db_url, frontend_path=frontend))

    health = client.get("/health")
    papers = client.get("/papers")

    assert health.status_code == 200
    assert health.headers["content-type"].startswith("application/json")
    assert health.json()["db_migrated"] is True
    assert papers.status_code == 200
    assert papers.headers["content-type"].startswith("application/json")
    assert [paper["title"] for paper in papers.json()] == [
        "Facial Anomaly Perception",
        "Signal Detection Theory",
        "Renderable Seed Paper",  # inc 120: the real-PDF QA fixture paper
    ]


def test_missing_frontend_file_is_graceful_and_api_still_works(temp_db_url: str, tmp_path: Path) -> None:
    client = TestClient(create_app(db_url=temp_db_url, frontend_path=tmp_path / "missing.html"))

    frontend = client.get("/")
    health = client.get("/health")

    assert frontend.status_code == 200
    assert frontend.headers["content-type"].startswith("text/html")
    assert "Callosum frontend file not found" in frontend.text
    assert "CALLOSUM_FRONTEND_PATH" in frontend.text
    assert health.status_code == 200
    assert health.json()["db_reachable"] is True


def test_api_exposes_only_read_only_get_routes(temp_db_url: str) -> None:
    app = create_app(db_url=temp_db_url)
    client = TestClient(app)
    allowed_route_paths = {
        "/",
        "/health",
        "/papers",
        "/papers/item-types",
        "/papers/{paper_id}",
        "/papers/{paper_id}/chunks",
        "/papers/{paper_id}/annotations",
        "/papers/{paper_id}/pdf",
        "/papers/duplicates/{job_id}",
        "/papers/duplicates/dismissed",
        "/axes",
        "/axes/{axis_id}/clusters",
        "/axes/score/{job_id}",
        "/axes/suggest/{job_id}",
        "/summarize/{job_id}",
        "/summaries",
        "/summaries/{summary_id}",
        "/help/corpus",
        "/settings",
        "/tags",
        "/papers/{paper_id}/suggested-tags",
        "/papers/{paper_id}/statcheck",
        "/papers/{paper_id}/statcheck/cached",
        "/papers/{paper_id}/grim-checks",
        "/methods/statcheck/summary",
        "/methods/statcheck/run/{job_id}",
        "/methods/pcurve/run/{job_id}",
        "/papers/{paper_id}/retraction",
        "/methods/retraction/run/{job_id}",
        "/methods/retraction/summary",
        "/methods/retraction/database",
        "/methods/retraction/database/refresh/{job_id}",
        "/papers/{paper_id}/reference-integrity",
        "/reference-integrity/overview",
        "/reference-integrity/run/{job_id}",
        "/papers/{paper_id}/findings",
        "/findings/overview",
        "/gaps",
        "/gaps/refresh/{job_id}",
        "/citations/styles",
        "/papers/acquire-oa/{job_id}",
        "/wanted",
        "/wanted/coverage",
        "/wanted/recheck/{job_id}",
        "/my-publications/profile",
        "/my-publications/refresh/{job_id}",
        "/my-publications/dashboard",
        "/my-publications/domains/{job_id}",
        "/my-publications/citing/{work_id}",
        "/library/scan/{job_id}",
        "/library/import/{job_id}",
        "/library/watched",
        "/library/watched/rescan/{job_id}",
        "/wip/watch-roots",
        "/wip/scan/{job_id}",
        "/wip/manuscripts",
        "/wip/manuscripts/{manuscript_id}",
        "/wip/manuscripts/{manuscript_id}/files",
        "/wip/manuscripts/{manuscript_id}/activity",
        "/wip/manuscripts/{manuscript_id}/sections",
        "/wip/manuscripts/{manuscript_id}/tasks",
        "/wip/manuscripts/{manuscript_id}/references",
        "/wip/manuscripts/{manuscript_id}/funding-runs",
        "/wip/manuscripts/{manuscript_id}/journal-runs",
        "/wip/papers/{paper_id}",
    }
    allowed_mutation_routes = {
        ("/summarize", frozenset({"POST"})),
        ("/summaries/{summary_id}", frozenset({"DELETE"})),
        ("/papers/{paper_id}", frozenset({"PATCH"})),
        ("/papers/{paper_id}", frozenset({"DELETE"})),
        ("/papers/{paper_id}/urls", frozenset({"POST"})),
        ("/papers/{paper_id}/urls/{url_id}", frozenset({"DELETE"})),
        ("/papers/{paper_id}/permanent", frozenset({"DELETE"})),
        ("/papers/trash/empty", frozenset({"POST"})),
        ("/papers/export", frozenset({"POST"})),
        ("/papers/{paper_id}/re-resolve", frozenset({"POST"})),
        ("/papers/{paper_id}/restore", frozenset({"POST"})),
        ("/papers/duplicates", frozenset({"POST"})),
        ("/papers/duplicates/dismiss", frozenset({"POST"})),
        ("/papers/duplicates/undismiss", frozenset({"POST"})),
        ("/papers/{paper_id}/acquire-oa", frozenset({"POST"})),
        ("/papers/{paper_id}/annotations", frozenset({"POST"})),
        ("/annotations/{annotation_id}", frozenset({"DELETE"})),
        ("/annotations/{annotation_id}", frozenset({"PATCH"})),
        ("/axes", frozenset({"POST"})),
        ("/axes/suggest-terms", frozenset({"POST"})),
        ("/axes/suggest", frozenset({"POST"})),
        ("/axes/merge", frozenset({"POST"})),
        ("/axes/{axis_id}", frozenset({"PATCH"})),
        ("/axes/{axis_id}", frozenset({"DELETE"})),
        ("/axes/{axis_id}/score", frozenset({"POST"})),
        ("/axes/{axis_id}/papers", frozenset({"POST"})),
        ("/axes/{axis_id}/papers/{paper_id}", frozenset({"DELETE"})),
        ("/help/ask", frozenset({"POST"})),
        ("/papers/{paper_id}/tags", frozenset({"POST"})),
        ("/papers/{paper_id}/tags/{tag_id}", frozenset({"DELETE"})),
        ("/wanted", frozenset({"POST"})),
        ("/wanted/{item_id}", frozenset({"DELETE"})),
        ("/wanted/sync-library", frozenset({"POST"})),
        ("/wanted/recheck", frozenset({"POST"})),
        ("/my-publications/profile", frozenset({"PUT"})),
        ("/my-publications/refresh", frozenset({"POST"})),
        ("/my-publications/decide", frozenset({"POST"})),
        ("/my-publications/summary/generate", frozenset({"POST"})),
        ("/my-publications/summary", frozenset({"PUT"})),
        ("/my-publications/domains", frozenset({"POST"})),
        ("/my-publications/domains/rename", frozenset({"POST"})),
        ("/my-publications/citing/import", frozenset({"POST"})),
        ("/my-publications/star", frozenset({"POST"})),
        ("/my-publications/works/import", frozenset({"POST"})),
        ("/my-publications/works/dismiss", frozenset({"POST"})),
        ("/my-publications/works/undismiss", frozenset({"POST"})),
        ("/my-publications", frozenset({"DELETE"})),
        ("/library/scan", frozenset({"POST"})),
        ("/library/import", frozenset({"POST"})),
        ("/library/watched/{folder_id}", frozenset({"DELETE"})),
        ("/library/watched/rescan", frozenset({"POST"})),
        ("/wip/watch-roots", frozenset({"POST"})),
        ("/wip/watch-roots/{root_id}", frozenset({"PATCH"})),
        ("/wip/watch-roots/{root_id}", frozenset({"DELETE"})),
        ("/wip/watch-roots/{root_id}/scan", frozenset({"POST"})),
        ("/wip/rescan", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}", frozenset({"PATCH"})),
        ("/wip/manuscripts/{manuscript_id}", frozenset({"DELETE"})),
        ("/wip/manuscripts/{manuscript_id}/relink", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/files/{file_id}", frozenset({"PATCH"})),
        ("/wip/manuscripts/{manuscript_id}/files/{file_id}/open", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/files/{file_id}/reveal", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/sections", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/sections/{section_id}", frozenset({"PATCH"})),
        ("/wip/manuscripts/{manuscript_id}/sections/{section_id}", frozenset({"DELETE"})),
        ("/wip/manuscripts/{manuscript_id}/sections/order", frozenset({"PUT"})),
        ("/wip/manuscripts/{manuscript_id}/tasks", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/tasks/{task_id}", frozenset({"PATCH"})),
        ("/wip/manuscripts/{manuscript_id}/tasks/{task_id}", frozenset({"DELETE"})),
        ("/wip/manuscripts/{manuscript_id}/references", frozenset({"POST"})),
        ("/wip/manuscripts/{manuscript_id}/references/{paper_id}", frozenset({"DELETE"})),
        ("/methods/statcheck/run", frozenset({"POST"})),
        ("/papers/{paper_id}/statcheck/rescan", frozenset({"POST"})),
        ("/methods/pcurve/run", frozenset({"POST"})),
        ("/methods/grim", frozenset({"POST"})),
        ("/papers/{paper_id}/grim-checks", frozenset({"POST"})),
        ("/papers/{paper_id}/grim-checks/{check_id}", frozenset({"DELETE"})),
        ("/methods/retraction/run", frozenset({"POST"})),
        ("/methods/retraction/database/refresh", frozenset({"POST"})),
        ("/papers/{paper_id}/reference-integrity/run", frozenset({"POST"})),
        ("/reference-integrity/run-selected", frozenset({"POST"})),
        ("/reference-integrity/instances/{instance_id}/review", frozenset({"POST"})),
        ("/findings/{finding_id}/review", frozenset({"POST"})),
        ("/gaps/refresh", frozenset({"POST"})),
        ("/gaps/add", frozenset({"POST"})),
        ("/gaps/dismiss", frozenset({"POST"})),
        ("/citations/render", frozenset({"POST"})),
        ("/citations/render-document", frozenset({"POST"})),
        ("/citations/suggest", frozenset({"POST"})),  # inc 156: highlight-to-suggest / evaluate
        ("/settings", frozenset({"PUT"})),  # BYOK: set key + egress consent (inc 146)
        ("/settings/test-key", frozenset({"POST"})),  # BYOK: validate the key (inc 147)
        ("/settings/access-token", frozenset({"POST"})),  # remote access: mint the bearer token (inc 168)
    }
    api_routes = [
        route
        for route in _iter_api_routes(app)
        if route.path in allowed_route_paths | {path for path, _ in allowed_mutation_routes}
    ]
    write_routes = [route for route in api_routes if not (route.methods or set()) <= {"GET"}]

    assert api_routes
    assert {route.path for route in api_routes} == allowed_route_paths | {path for path, _ in allowed_mutation_routes}
    assert all(
        (route.methods or set()) <= {"GET"}
        or (route.path, frozenset(route.methods or set())) in allowed_mutation_routes
        for route in api_routes
    )
    assert {(route.path, frozenset(route.methods or set())) for route in write_routes} == allowed_mutation_routes
    assert client.post("/papers").status_code == 405
