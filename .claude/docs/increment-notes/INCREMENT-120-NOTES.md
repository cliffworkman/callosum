# Increment 120 — QA mechanism: surface-coverage gate + Codex-exec supervisor + watched inbox

Installed the QA mechanism delivered as `qa_routes.zip` (authored out-of-band by "browser claude"), stood it up
per its `QA-BUILD-GUIDE.md`, and had **Codex author the full route suite** until the coverage gate went green.
A new **rule #10** (`.claude/QA-POLICY.md`) joins DESIGN.md (#8) and PRINCIPLES.md (#9) as a read-before-you-change
gate — here, before altering any **end-user surface**.

## Implemented

- **`tools/qa/build_surface_map.py`** — the linchpin: a pure-stdlib static extractor (AST of `@router.<m>("path")`
  across `routers/`; regex of interactive elements/handlers across `app/frontend/js/*.jsx`) + a `check` that diffs
  the surfaces declared in `.claude/qa-routes/*.md` `qa-coverage` blocks against the real ones. **API is a hard
  gate; FE is a checklist** (`--strict-fe` to enforce). `extract` writes `surface-map.json` (gitignored).
- **`tools/qa/supervisor.py`** — dispatches each route to a headless `codex exec` (the route file is the contract),
  waits for the deposit in `.claude/qa-inbox/<run-id>/`, retries, and writes a `run-summary.md` (Critical/High first
  + the coverage result); **Tier-0 gates the deeper tiers**. `--tier`/`--routes`/`--max`/`--dry-run`.
- **`tools/qa/_qa_serve.py`** — the fixture contract: spins `app.backend.api.app:app` against a **freshly
  migrated + seeded throwaway SQLite** (reuses `tests.api_helpers._seed_library`, mirrors `tests/e2e/test_smoke.py`)
  on a free `127.0.0.1` port, **egress unset by default**, auto-teardown. Never touches the real library.
- **`tools/qa/route_runner_prompt.md`** + **`tools/qa/__init__.py`** (the latter so `from tools.qa._qa_serve …`
  resolves — `tools/` is a real package).
- **`.claude/QA-POLICY.md`** — the charter (fixture contract, the computed coverage gate, the honesty-invariant
  assertions [egress gate / coordinate honesty / signal-not-verdict], severity rubric, the deposit+triage loop).
- **`.claude/qa-routes/`** — `_TEMPLATE.md` + **15 routes**: the 2 seeds (`00` read-only smoke, `30` detail pane)
  + **13 Codex-authored** (`15` axes, `20` tags, `24` duplicates, `27` scan/import, `32` viewer/annotations,
  `33` methods/statcheck, `34` citations, `35` settings, `40` papers-CRUD/trash [T1]; `55` synthesis,
  `56` acquisition/wanted, `57` my-publications, `58` help-assistant [T2, hermetic]).
- **CLAUDE.md:** rule #10, kickoff step #10 (QA-inbox triage), directory-layout rows, a reference-docs row.
- **`.gitignore`:** `.claude/qa-inbox/`, `tools/qa/surface-map.json`, `qa_routes.zip` (all local/generated/transient).
- **CI:** a report-only `build_surface_map.py check || true` step (flip to enforcing once routes stay green).

## Key technical detail

- **Coverage is a *computed* property, not a discipline.** `check` re-extracts the surface map fresh each run
  (no committed file needed), so an unmapped endpoint can't silently drift in. Current tree: **88 API / 460 FE**;
  after Codex's authoring, **88/88 API + 460/460 FE covered → `check` exits 0**.
- **Two Codex roles, distinct perspectives:** the *author* run (this increment) is a test-writer (writes the spec
  files, never opens the app); the *route-runner* runs the supervisor will dispatch (Phase 3) act as an
  **adversarial end user** driving the seeded app in Playwright — but instrumented to also assert the honesty
  invariants (capture every outbound request for the egress gate, inspect bbox rendering for coordinate honesty,
  zero console-error budget) that a real user couldn't see.
- **Repo-fit fixes applied to the bundle:** added `tools/qa/__init__.py`; ran `ruff --fix`/`format` on the three
  scripts (3 unused imports + formatting — CI would have failed otherwise).

## Manual verification (all run; Phase 3 deferred to the user)

1. `python tools/qa/build_surface_map.py extract` → writes the map (88 api / 460 fe).
2. `python tools/qa/build_surface_map.py check` → **OK, exits 0** (every gated surface claimed).
3. `python tools/qa/_qa_serve.py` → printed a `127.0.0.1:<port>` base URL, `/health` 200, dashboard `no-identity`
   (fresh seed, egress unset), clean teardown on kill.
4. `python tools/qa/supervisor.py --tier 0 --dry-run` → emitted a valid `codex exec … route_00 …` command.

**NOT run (the user's to trigger — spends Codex credits):** Phase 3 — `python tools/qa/supervisor.py --tier 0`
(the real browser-driven QA pass), then deeper tiers. The first deposit lands in `.claude/qa-inbox/`, triaged at
the next session kickoff (rule #10 / kickoff step #10).

## Pytest

**436 passed, 1 skipped** (unchanged — the install is additive; no app/test code touched). `ruff format`/`check`
clean (incl. `tools/qa/`).

## Commits (on main)

`c95b791` (mechanism install + policy + CLAUDE.md patch + gitignore + CI) · this commit (the 13 Codex-authored
routes + docs).

## Next

Phase 3 is the user's call: run `supervisor.py --tier 0` (cheap smoke) to validate the full pipeline end-to-end,
then deeper tiers occasionally. Steady state: rule #10 keeps the gate green as new surfaces land; kickoff step #10
triages each deposit.
