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

## Follow-on (same session): first Tier-0 run + 3 supervisor fixes + seed enrichment + route calibration

Ran the first real Tier-0 pass (`supervisor.py --tier 0`) and closed the loop:

- **3 Windows-portability bugs in the bundled `supervisor.py`** — all caught BEFORE any Codex credits were spent
  (each crashed pre-dispatch): (1) cp1252 stdout can't encode the progress glyphs → force UTF-8; (2) bare `codex`
  isn't found by `subprocess` (npm `codex.CMD` shim) → `shutil.which`; (3) a large multi-line prompt as a `.CMD`
  arg is mangled by cmd.exe → pipe it via **stdin** (`codex exec … -`). Commit `5adc5e6`.
- **The Tier-0 run itself: clean.** Codex stood up the seeded throwaway server (egress unset), drove every
  read-only surface in Chromium, captured 10 screenshots, deposited a report. **The honesty invariants held under a
  real browser run: 0 Gemini/genai requests with egress off, 0 page errors** (73 browser requests). No real app
  bugs — all 4 findings were the route over-assuming the seed/menu. Triaged + moved to `qa-inbox/_processed/`.
- **Seed enrichment (B) — commit `ce934ed`.** The canonical seed had no on-disk PDF, so the PDF viewer + the
  **coordinate-honesty invariant** (Core #2) couldn't be QA-exercised. Added a **`Renderable Seed Paper`** backed by
  a committed `tests/fixtures/seed.pdf` (a real 2-page PDF, generated with PyMuPDF) with **truthful chunk bboxes**,
  plus a `social-perception` **tag**. The facial paper is untouched (it keeps testing the path edge-cases + the
  honest "PDF not available locally" 404). A `.gitignore` exception (`!tests/fixtures/seed.pdf`) commits the
  fixture; 3 dependent count-assertions updated; a pinning test (`test_seed_renderable_paper_serves_real_pdf_with_truthful_bbox`)
  locks the fixture. pytest **437**. **Verified headed (free, via `qa_server` + Playwright):** the renderable PDF
  renders ("Seed Fixture Document", Page 1/2) and the Tags panel shows the seeded tag.
- **Route calibration (A) — same commit.** `route_00` + a new **"Seed contract"** block in `_TEMPLATE.md` document
  the renderable-vs-facial paper distinction + the real Add-menu items, so all 13 routes (and future Codex authoring)
  target the right paper and stop the first run's false positives recurring.

## Next

Phase 3 deeper tiers are the user's call (`supervisor.py` without `--tier 0`). The Tier-0 pipeline is now proven
end-to-end and the seed/routes are calibrated, so a re-run should be clean signal. Steady state: rule #10 keeps the
gate green as new surfaces land; kickoff step #10 triages each deposit.
