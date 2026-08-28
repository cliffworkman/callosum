# Security audit — GROBID Docker lifecycle management (backlog #58)

**Date:** 2026-08-28
**Scope:** new `app/backend/grobid_lifecycle.py` (Docker CLI orchestration) + new sibling router
`app/backend/api/routers/grobid_docker.py` (`GET /grobid/docker/status`, `POST /grobid/docker/install`,
`GET /grobid/docker/install/{job_id}`, `POST /grobid/docker/stop`) + a new `grobid_lifecycle_jobs` JobStore.

## Threat review

| Area | Finding |
|---|---|
| Command injection | Every `subprocess` argv element is a fixed module-level constant (`GROBID_IMAGE`, `GROBID_CONTAINER_NAME`, `GROBID_INTERNAL_PORT`) except the local bind port, which is either the fixed `GROBID_DEFAULT_PORT` or the result of `_free_port()` (an OS-assigned ephemeral port read back from a local socket bind — never derived from request/user input). No endpoint accepts an image tag, container name, or port from the client; `GrobidInstallResponse`/`GrobidStatusResponse` request bodies carry no fields at all. Confirmed by reading every `subprocess.run` call site in `grobid_lifecycle.py`. |
| Resource caps | Every Docker subprocess call has a bounded `timeout=` (`_DOCKER_CMD_TIMEOUT=10s` for info/inspect, `_PULL_TIMEOUT=20min` for the ~500MB pull, `_RUN_TIMEOUT=15s` for container start, `_STOP_TIMEOUT=20s` for removal). The readiness poll is separately bounded by `_READY_TIMEOUT=120s`. A `subprocess.TimeoutExpired` is caught and surfaced as a clean `GrobidInstallError`, never an unhandled hang. |
| Egress transparency | The download is disclosed in the UI copy before the click ("Install & Start GROBID (~500MB download)", plus a `settings-sub` explanation) — confirmed live via Playwright. This does **not** go through `CALLOSUM_ALLOW_DATA_EGRESS`: reasoned in the plan and confirmed correct — invariant #3 protects *library text* leaving the machine to a summarization/generation service; pulling callosum's own tooling dependency from Docker Hub sends no library content anywhere (the same category as `npm install`/`uv sync`, never gated). |
| Blast radius of `stop_container()` | `stop_and_remove()` takes no parameters and always targets the module constant `GROBID_CONTAINER_NAME` ("callosum-grobid") — structurally incapable of touching any other container. Verified live: after installing and stopping, `docker ps -a --filter name=callosum-grobid` showed nothing, and Cliff's own separately-named `grobid` container (a real, pre-existing, differently-named container) was never touched by any call in this feature. |
| "Detect, never auto-install Docker" boundary | `docker_available()` only ever calls `docker info` (a read-only query) and `shutil.which`; no code path invokes an installer, downloads a Docker binary, or modifies system PATH/services. Confirmed by reading the full module — no such call exists. |
| Resource exhaustion via repeated install attempts | `start_install()` checks `jobs.list_all()` for any existing `pending`/`running` job before creating a new one, returning 409 if found — verified by a hermetic test (`test_install_refuses_a_second_concurrent_attempt`) and live reasoning about the JobStore's thread-safe lock. |
| File-write safety | The only persisted write in this feature is `app_settings.set_grobid_url(url)`, where `url` is always `f"http://127.0.0.1:{port}"` built from the fixed loopback host + an integer port this code itself determined — never a user-supplied string. This reuses the already-audited `app_settings.py` write path unchanged. No new file-write path is introduced. |
| Loopback/egress-gate correctness | A callosum-managed instance is always bound to `127.0.0.1`, so it automatically satisfies `is_loopback_url()` (`llm/providers.py`) with zero special-casing — confirmed live: the parse endpoints' existing `_egress_refused()` gate was not modified and continues to work correctly against the new instance's URL. |
| Stale-state UI bug (found and fixed during live verification) | Not a security issue, but recorded here since it was caught by this audit's own negative-path testing: after clicking Stop, the frontend's `autoReachable` flag stayed stale (true), briefly showing a misleading "already configured" UI state for a URL that was genuinely unreachable. Fixed in `35e_maintenance.jsx::stopManaged` to re-run the reachability check (`load()`) alongside the Docker-state refresh. No backend/security implication — purely a UI staleness bug — but noted for completeness since it was surfaced by this feature's own verification pass. |

## Negative-path checks (run)

- **Docker not installed** — `docker_available()` returns `(False, False)`; `POST /grobid/docker/install` returns 409 with a clear message; hermetic test coverage (`test_docker_available_not_installed`, `test_install_refused_when_docker_not_installed`).
- **Docker installed but daemon not running** — genuinely reproduced live on this machine (Docker Desktop's engine was down mid-session): `docker_available()` correctly returned `(True, False)`; the Settings UI correctly rendered "Docker is installed but not running. Start Docker Desktop, then reopen this page." — confirmed via Playwright screenshot-equivalent DOM read.
- **Port 8070 already occupied by a different (non-callosum) container** — the real, live scenario on this machine (Cliff's own manually-run `grobid` container). Hermetic test (`test_install_and_start_falls_back_to_free_port_on_conflict`) proves the code detects Docker's "port is already allocated" stderr and retries on an auto-picked free port rather than failing or hanging.
- **`docker pull` fails** — hermetic test (`test_install_and_start_pull_failure_surfaces_stderr`) confirms the real stderr detail is surfaced (invariant #4), never hidden.
- **`docker run` fails after a successful pull, for a non-port reason** — hermetic test (`test_install_and_start_run_failure_for_other_reason_does_not_retry`) confirms it fails immediately with the real detail, no blind retry.
- **GROBID never becomes ready within the bounded readiness timeout** — hermetic test (`test_install_and_start_never_becomes_ready`) confirms a clean, actionable `GrobidInstallError` rather than an infinite wait.
- **`POST /grobid/docker/stop` called when no `callosum-grobid` container exists** — `_remove()` swallows the resulting non-zero exit / OSError as a best-effort no-op; hermetic test (`test_stop_and_remove_is_a_noop_when_absent`).
- **Two concurrent install attempts** — hermetic test (`test_install_refuses_a_second_concurrent_attempt`) via direct JobStore seeding (real request-level concurrency isn't reproducible through `TestClient`, which runs FastAPI `BackgroundTasks` synchronously — documented in the test).
- **Real end-to-end live run** (with Cliff's explicit go-ahead): a genuine ~500MB pull of `grobid/grobid:0.9.1-crf`, container start, readiness poll against the real `/api/isalive` endpoint, `grobid_url` correctly saved, confirmed reachable (HTTP 200), then Stop correctly removed the container and the UI correctly fell back to the "Install & Start" state (after the fix above). Cliff's own pre-existing `grobid` container — incidentally stopped by a Docker Desktop engine restart needed to run this verification, not by any code in this feature — was restarted and his original `grobid_url` (`http://localhost:8070`) restored and re-verified reachable afterward.

## Result

**Security Audit: PASS.** No command-injection surface, all subprocess calls bounded, the "detect never
auto-install Docker" boundary holds structurally, `stop_and_remove()` cannot target any container but its own
fixed name, and the egress-transparency reasoning is sound. One real (non-security) UI staleness bug was found
by this audit's own live verification and fixed before this PASS was recorded.
