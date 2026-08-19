# Increment 483 — Admin-gated plugins foundation (backlog #41)

## Implemented

A small, deliberately inert foundation for a future third-party plugin system, per a scoping
conversation with Cliff (design doc: `.claude/docs/specs/2026-08-19-admin-gated-plugins-design.md`).

- `app/backend/app_settings.py` — `set_plugins_enabled`/`stored_plugins_enabled`, mirroring
  `agent_writes_enabled` exactly: default OFF, plus a `CALLOSUM_DISABLE_PLUGINS` env-var recovery
  hatch.
- `app/backend/api/routers/settings.py` — `plugins_enabled` added to `GET`/`PUT /settings`.
- `app/frontend/js/35_settings.jsx` — a new "Plugins" Settings card with a single toggle; copy is
  explicit that enabling it does nothing observable yet.
- Registry-seam marker comments at `registerPaneTab` (`app/frontend/js/05_panes.jsx`) and
  `build_default_feed_registry` (`app/backend/discovery/feed.py`) — the two real existing internal
  registries identified as candidate future extension points for panel-module and source-provider
  plugins respectively (the second one is a real finding: the original future-track doc assumed no
  "SourceProvider registry" existed yet; it does, built for the literature Feed, backlog #28).
- `.claude/docs/future-tracks/opus4.8_future-tracks_plugins.md` — pointed at the live design doc.

## Key technical detail

**This is a foundation, not a feature.** No plugin data model, no loader, no sandbox, no review/
store pipeline, no third-party code ever executes. The toggle controls nothing else in the app —
confirmed by design (the design doc's own Global Constraint), not just by omission. The actual
hard design work — code-execution sandboxing for a module that runs in-process, whether a plugin
contract can structurally enforce PRINCIPLES.md rather than merely trust the author, and keeping
first-party (trusted) modules structurally separate from third-party (store-reviewed) ones — stays
open, recorded in the design doc for whoever picks this up next, including a concrete direction
for the principle-enforcement question (constrain panel modules to typed fact/candidate data
rendered by callosum's own trusted UI components, rather than arbitrary rendering).

Note: this increment's addition put `app_settings.py` at 596/600 lines, the closest file to the
cap in the tree — the next new setting there will likely need a split first.

## Manual verification script

1. Start the app. Open Settings. Confirm a new "Plugins" card appears (after "Integrations",
   before "Your usage"), with a single off-by-default toggle and copy explaining it's a foundation
   with nothing installable yet.
2. Toggle it on. Confirm the toggle visually flips and stays on after a page reload (persisted via
   `PUT /settings`).
3. Confirm no other part of the app changes behavior with it on — this is the whole point of an
   inert foundation.
4. Toggle it back off.

## Experience pass (rule #11)

The surface is one toggle whose own copy explicitly states it changes nothing yet ("nothing is
installable yet... enabling this toggle does not change any other behavior"). Given that, a
persona-grounded experience agent was not dispatched — there is no "intended use" to inhabit
yet, since the feature has no observable effect. Worth a real pass once an actual plugin-install
flow exists to evaluate.

## Pytest

Targeted: `pytest tests/test_settings.py -k plugins -v` → 2 passed (the toggle's default/round-trip
test plus the `CALLOSUM_DISABLE_PLUGINS` recovery-hatch test; `-k plugins_enabled` alone only
matches the first by name substring, so `-k plugins` is the accurate filter for both).
`pytest tests/test_settings.py -q` → 34 passed.
`pytest tests/test_frontend_assembly.py -q` → 67 passed.
(`pytest tests/test_settings.py tests/test_frontend_assembly.py -q` together → 101 passed.)
`python tools/check_line_budget.py` → OK, all application-source files within the 600-line cap.
`python -m tach check` → OK, all modules validated.

Full suite (serial, `pytest -q`, run in the foreground after two automated parallel/backgrounded
attempts couldn't be confirmed without relying on a stall-prone notification path): **2322 passed,
1 failed, 4 skipped in 3576.87s (0:59:36).** The one failure,
`tests/test_website_how_it_works.py::test_primary_local_destinations_exist[demo/-target2]`, asserts
that `dist-demo/` (a gitignored build artifact from the separate demo/website build pipeline) exists
on disk — it doesn't in this worktree because that build was never run here. Confirmed unrelated to
this increment: this task touches only comments in `05_panes.jsx`/`feed.py` plus five doc files,
nothing under `www/`, `demo/`, or the build pipeline; `dist-demo/` is line 42 of `.gitignore`, a
local build product, not a repo artifact. Pre-existing environment gap, not a regression.
