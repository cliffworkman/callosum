# Staged harness: tach (module-boundary contracts)

**SUPERSEDED (activated inc 472) — this draft's own trigger fired.** The live config is `tach.toml` at the
repo root, wired into `.pre-commit-config.yaml` + `.github/workflows/ci.yml` + `pyproject.toml`/
`requirements-dev.txt`/`uv.lock`. Kept here for the original design rationale (the "why deferred" reasoning
below is still accurate history); see `REGISTRY.md`'s entry for the exact fences shipped.

**Checks:** import-direction / module-boundary rules — e.g. `sync_server/` must never import from
`app/backend/` (an existing, audited architectural fence — see `.claude/security-audits/2026-06-29_sync-server.md`),
or `app/backend/persistence/` should never import from `app/backend/api/routers/`. This is closer to the
project's own "file-containment" instinct (CLAUDE.md rule #1's 600-line cap, the fenced `sync_server/`) than a
generic layered-architecture lint — which is why tach (boundary/module contracts) is slightly favored here over
import-linter (layer contracts).

**Why deferred:** with one primary author (Cliff, assisted by Claude/Codex), the existing boundaries are held
by convention + review, not tooling — and they've held. A boundary-contract tool pays for itself once a second
set of hands starts pushing code the primary author isn't reading line-by-line, or once module count grows
enough that a boundary violation could land without anyone noticing the import.

**Activation trigger:** an outside contributor ("Jeff") begins contributing, **or** module count/coupling
crosses a threshold where the file-containment rule becomes hard to eyeball manually (a concrete signal: the
600-line-budget script's file count, `tools/check_line_budget.py --list`, crossing ~500 files, or a second
fenced subsystem like `sync_server/` being added).

## Draft config (moves to `tach.toml` at the repo root on activation)

```toml
[modules]
[[modules]]
path = "app.backend.api"
depends_on = ["app.backend.persistence", "app.backend.pdf_processing", "app.backend.methods", "app.backend.llm"]

[[modules]]
path = "app.backend.persistence"
depends_on = []  # the repository layer must not reach back up into routers/api

[[modules]]
path = "sync_server"
depends_on = []  # fenced: sync_server must never import from app.backend (audited invariant)

[[modules]]
path = "app.backend"
depends_on = []  # app.backend must never import sync_server (the fence cuts both ways)
```

## Activation steps
1. `pip install tach` (or add to the `dev` dependency group).
2. Move this draft to `tach.toml`; run `tach check` and fix any surfaced violations (or explicitly allowlist a
   known, accepted exception with a comment explaining why).
3. Add a pre-commit hook + CI step (`tach check`).
4. Update this registry's status to `active` and remove this file (or mark it superseded).
