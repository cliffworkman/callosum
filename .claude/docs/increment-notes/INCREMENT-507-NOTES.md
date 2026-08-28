# Increment 507 — GROBID accessible from Settings: Docker install/start/stop (closes backlog #58)

## Implemented

Backlog #58 asked: don't bundle GROBID into callosum's installer, but make its existing opt-in Docker-based
setup dramatically more accessible — a user shouldn't need to already know Docker CLI commands.

**Research first, not assumed:** verified GROBID's actual distribution options directly against its own docs/
GitHub releases rather than trusting training knowledge. Conclusion: no ready-to-run standalone download
exists (GitHub releases publish only raw JARs, not the `grobid-home` model bundle the service needs); the only
non-Docker path is building from source via Gradle, which GROBID's own docs flag as having "platform-specific
issues" on Windows — too fragile to wrap in a button. The realistic path is Docker orchestration, and GROBID
conveniently ships two image tiers: `grobid/grobid:0.9.1-crf` (~500MB, CPU-only) and `-full` (~8GB,
GPU-optional). The lightweight `-crf` tag is the only one offered — the right default for "just make it work."

**New backend (`app/backend/grobid_lifecycle.py`, pure functions, no FastAPI/pydantic):**
`docker_available()` (installed/daemon-running via `shutil.which`+`docker info`), `container_state()` (`docker
inspect`, mapped to absent/running/stopped — the container's own existence under the fixed name
`callosum-grobid` is the sole "is this ours" source of truth, no separately persisted flag), `install_and_start()`
(clears any stale leftover container → `docker pull` the fixed, pinned image → `docker run -d` on the default
port 8070, falling back to an auto-picked free port on a detected "port is already allocated" conflict →
polls GROBID's own real `/api/isalive` endpoint, reusing `grobid.py::test_connection`'s exact ping shape,
until ready or a bounded timeout), `stop_and_remove()` (`docker rm -f`, always the fixed container name —
structurally incapable of targeting anything else). Every subprocess argv element is a fixed code constant
except the locally-determined bind port — no injection surface. No byte-level download progress (no
precedent anywhere in this codebase's other "download a public artifact" jobs — TOP Factor/AJOL/Retraction
Watch mirrors all go straight running→done too); an indeterminate progress bar is honest, not a missing
feature.

**New sibling router (`app/backend/api/routers/grobid_docker.py`, the `paper_enrich.py`/`methods_retraction.py`
precedent — `grobid.py` itself is 348 lines with headroom, but this is a distinct concern, infra lifecycle vs.
content parsing):** `GET /grobid/docker/status`, `POST /grobid/docker/install` (a new `grobid_lifecycle_jobs`
JobStore, the standard create→background-task→poll shape, refuses a second concurrent attempt), `GET
/grobid/docker/install/{job_id}`, `POST /grobid/docker/stop`. On install success, `app_settings.set_grobid_url()`
is called with the new instance's URL — the **only** integration point with the rest of the app; since a
callosum-managed instance is always bound to `127.0.0.1`, it automatically satisfies the existing
loopback-vs-egress-gate distinction (`is_loopback_url`) with zero special-casing, and the existing parse
endpoints/UI needed no changes at all.

**Frontend (`app/frontend/js/35e_maintenance.jsx`'s `GrobidSettings()`):** a new `GrobidDockerLifecycle`
sub-component branches on Docker/container state: Docker not installed → a plain guide-to-installer note
(never auto-installed — a deliberate scope boundary, matching how LibreOffice/`cloudflared` prerequisites are
handled elsewhere); Docker installed but daemon down → a plain note; available with no managed container → a
primary "Install & Start GROBID (~500MB download)" button, explicit about the size before the click; running →
"Running (managed by callosum)" + Stop. **A working, already-configured GROBID (the common case once used
once) stays the quiet path** — the Docker section demotes to a small secondary link ("Or let callosum manage a
local GROBID instance for you instead") rather than nagging to replace a setup that already works. Reuses
every existing recipe (`settings-field`/`settings-sub`/`settings-note`/`btn btn-ghost`/`ProgressBar
managedBy="backend-job"`) — no new CSS.

**Principles/A-A gate (rule #9), run because this touches the egress posture literally (a new outbound
fetch):** not a claim/signal/judgment-about-the-literature feature — infrastructure/tooling. Reasoned
conclusion: pulling callosum's own tooling dependency from Docker Hub is not the class of egress invariant #3
protects (that gate exists for *library text* leaving to a summarization/generation service; this is the same
category as `npm install`/`uv sync`, never gated). The aligned response is transparency in the UI copy, not a
consent dialog — implemented that way.

## Key technical detail

Docker's own `docker run -p` failure text for a port conflict is a stable, well-known CLI string ("...Bind for
0.0.0.0:PORT failed: port is already allocated") — matched via substring, verified against real Docker
behavior during live testing (Cliff's own separately-named `grobid` container occupying port 8070 was a live,
not hypothetical, test case for this exact fallback path).

## A real bug found and fixed by live verification (not a security issue, a UI staleness bug)

After the real end-to-end install→stop cycle, clicking Stop left the frontend's `autoReachable` flag stale
(still `true` from the just-removed instance), so the UI briefly showed the quiet "already configured" branch
for a URL that was now genuinely unreachable — confirmed live (`docker ps` showed the container gone, a direct
HTTP request to the port was refused, yet the UI implied a working setup). Fixed: `stopManaged()` now calls
`load()` (which re-runs the reachability check) alongside `loadDockerStatus()`. Re-verified live after the fix:
Stop now correctly falls back to the primary "Install & Start" state immediately.

## Manual verification script

1. Settings → GROBID document structure → Run GROBID for me.
2. With no GROBID configured and Docker available: confirm the primary "Install & Start GROBID (~500MB
   download)" button appears with the size disclosed in copy.
3. Click it; confirm a real pull→run→ready sequence completes (a genuine ~500MB download, several minutes on
   first pull, much faster once Docker's layer cache is warm) and the section flips to "Running (managed by
   callosum)" with a Stop button; confirm the GROBID URL field above now shows the new `http://127.0.0.1:<port>`
   URL and Test succeeds.
4. Click Stop; confirm it correctly returns to the "Install & Start" primary state (not a stale "already
   configured" note) and `docker ps -a` shows no `callosum-grobid` container.
5. With a real working GROBID already configured (test-connection succeeds): confirm the Docker section demotes
   to the quiet secondary link, not a nagging primary action.
6. With Docker not installed, or installed-but-daemon-down: confirm the correct plain guidance note (no crash,
   no hang) — both states were live-verified on this machine (Docker's own engine was genuinely down partway
   through this increment's own verification, an unplanned but useful real test of this exact path).

## Live end-to-end verification (real Docker, real ~500MB pull, Cliff's explicit go-ahead)

Performed for real on this machine, not simulated: full install (`grobid/grobid:0.9.1-crf` pulled and run,
`/api/isalive` genuinely returned 200), Stop (container genuinely removed), the staleness bug above found and
fixed mid-verification, then re-verified clean. Cliff's own separately-named, pre-existing `grobid` container
was incidentally stopped by a Docker Desktop engine restart needed to run this verification (not by any code
in this feature) — restarted afterward and his original `grobid_url` (`http://localhost:8070`) restored and
re-confirmed reachable via the Settings UI's own Test button before finishing.

## Pytest

`pytest tests/test_grobid_lifecycle.py tests/test_grobid_docker_endpoints.py tests/test_frontend_assembly.py
tests/test_grobid_endpoints.py tests/test_grobid_pipeline.py tests/test_status.py -q` → all green (18 + 8 new
hermetic tests). Full suite `pytest -n 4 -q` → **2561 passed, 3 skipped** (2535 + 26 new tests from this
increment).

See `.claude/security-audits/2026-08-28_grobid-docker-lifecycle.md` for the full threat review (PASS).
