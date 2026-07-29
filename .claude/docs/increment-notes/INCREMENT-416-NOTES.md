# Increment 416 — first-run onboarding wizard (wizard core; guided tour deferred)

## Implemented

Callosum had no first-run experience — a new install landed directly on an empty Library with no guidance
toward the handful of settings that matter most. Cliff asked for a wizard covering: My Publications identity
(respecting any already-entered data — two existing testers have real profiles), an AI/BYOK opt-in screen, the
watched library folder(s), an import opportunity, and an initial axis, deliberately leaving the exact mechanics
to be designed. Three Explore passes + a Plan pass found the wizard is fundamentally an **orchestration layer**
— all five steps already have working, reusable settings screens; the only wholly novel piece (a guided
spotlight tour of the app's sections) has zero precedent anywhere in this codebase and its own distinct failure
surface (mobile incompatibility, DOM-positioning edge cases) — **deferred to a follow-up increment** rather than
bundled in, so this one ships a fully self-sufficient wizard without waiting on a second, unrelated novel
mechanism.

**Backend — one narrow flag, riding the one fetch the app already makes unconditionally at launch:**
`app_settings.py` gains `set_onboarding_completed`/`stored_onboarding_completed` (plain bool, file-only, no env
override — matches `remote_access_enabled`/`agent_writes_enabled`'s shape, not the two-part
`publisher_defaults_set` gate). Exposed on `GET /health`'s `HealthResponse` (mirroring the existing `read_only`
field's exact precedent — the only endpoint `App()` fetches unconditionally at launch; `GET /settings` is only
ever fetched lazily by individual panels) and on `GET`/`PUT /settings` (for a future "redo setup" Settings
control, through the same endpoint every other flag already uses).

**A real pre-existing bug found and fixed, independent of the wizard:** `MyPubsSettings`
(`app/frontend/js/35a_mypubs.jsx`) had its Save/Add/Refresh actions enabled *before* the initial `GET
/my-publications/profile` resolved — a fast click, or pressing Enter in the variant-draft field (which calls
`addVariant` directly, bypassing the Add button's own `disabled` attribute), before that fetch completed would
`PUT` blank values and **wipe an existing profile**. Fixed with a `loading` state (default `true`, flipped
regardless of GET success/failure) gating every mutating action, not just a button attribute. This protects the
two testers' real data both inside the wizard and on the ordinary Settings page — same component, one fix.

**Five modal components split into bare `*Body` + thin overlay wrapper** (`ScanModal`, `ImportModal`,
`BundleImportModal`, `AxisEditModal`, `SuggestAxesModal`) so the wizard can embed each step's real tool without
nesting a second `.axis-modal-overlay` inside its own. Every existing standalone caller (Settings, the library
"+Add" menu, the axis editor/suggester triggers) is completely unaffected — the wrapper's external signature and
behavior are unchanged; this is a pure internal split, confirmed by the frontend-assembly test suite (no test
asserted the old fused shape) and by every existing render call site working unchanged.

**New `OnboardingWizard`** (`app/frontend/js/04e_onboarding.jsx`) — a full-screen overlay cloned from
`AccessLockOverlay`'s visual/structural template (`01_recovery.jsx`, the only prior full-screen, blocking,
app-root-mounted overlay), reusing the shared `.axis-modal-overlay`/`.axis-modal` shell every modal already uses.
Six internal steps (`identity → ai → library → import → axis → done`), a simple `[step, setStep]` index (no
prior multi-step convention existed in this codebase — kept deliberately simple, not a premature generic
`Wizard` component). Import and axis steps each offer a real choice between two working tools (file-import vs.
bundle-import; AI-suggested axes vs. a manual one), plus "Skip this step". **"Skip setup" is a persistent,
always-visible exit at every step** — derived from `APPROACH-AVOIDANCE.md`'s A1 ("the user's judgment is the
product; the tool's is not"): nothing here pressures completion, and skipping marks the same
`onboarding_completed=true` as finishing, since re-nagging on a future launch after an explicit skip would
itself be exactly the pressure A1 warns against — everything offered stays permanently reachable via Settings
regardless.

**The AI/BYOK step is the one place invariant #3 is directly at stake, and it was designed to that gate
deliberately, not incidentally.** The wizard renders the existing `AiSettings` component verbatim — it never
sets, defaults, or pre-checks `data_egress_enabled` itself. Since neither `PRINCIPLES.md` nor
`APPROACH-AVOIDANCE.md` names "onboarding" anywhere, this is a **derived** requirement (per A-A's own
instruction: "when a future-track has no principle covering it yet, derive the right one from the value") from
A5 ("Local-first, and the user is sovereign over what leaves the machine... the egress gate is enforced even
where a cloud call was the easy path") and its veto-level line ("No egress without consent, and no bypass of
the gate by cache or convenience"). Confirmed by a new test asserting no hardcoded `data_egress_enabled: true`
appears anywhere in the assembled frontend.

**Existing testers will see this wizard once** — `onboarding_completed` has no prior value to backfill from
(defaults `False` for every existing install). Not a bug: the identity step (with the race-condition fix above)
correctly shows their real profile rather than blanks, and "Skip setup" is one click away. Pre-release,
one-or-two-user project (CLAUDE.md rule #5) — no migration warranted for two people.

## Key technical detail

`onboardingDone` (the frontend gate state in `40_app.jsx`) **defaults `true`, not `undefined`/falsy** — a
deliberately verified detail. A *failed* `/health` (e.g. DB unreachable) still sets `healthLoaded=true`; if
`onboardingDone` defaulted falsy, the wizard would incorrectly render over a broken instance instead of the
connection-error state. It only flips `false` once a real `/health` response says the wizard genuinely hasn't
run or been skipped yet.

The wizard's own refresh callbacks (`onScanned`/`onImported`/`onImportedBundle`/`onAxisSaved`) reuse the
**exact same** `setLibRefresh`/`setAxisRefresh`/`libraryBits.onPage(0)` calls the standalone modals already make
— not no-ops — so a paper or axis added during onboarding actually appears once the user reaches Library,
avoiding the same class of staleness bug the identity-step fix also guards against.

## Housekeeping

- Security audit: `.claude/security-audits/2026-07-29_onboarding-wizard.md`, PASS.
- QA route: `.claude/qa-routes/route_77_onboarding_wizard.md` (new). Confirmed via `python tools/qa/
  build_surface_map.py check` that this feature's own new surfaces are now covered; the remaining 4 API + 12
  frontend uncovered surfaces are pre-existing debt unrelated to this feature (the auto-updater toast, the tags
  panel, GRIM checks, funding/journal-runs) — flagged, not fixed here (unrelated scope).
- Deleted a stray leftover `app/frontend/js/28b_bundle.jsx.tmp.31216.a15eeee51ffe` (a crashed-editor temp file)
  while touching `28b_bundle.jsx` anyway (rule #5).
- EXPERIENCE-PASS (rule #11) applies — a newly-rolled-out user-facing surface; closest persona is the Migrator
  ("a day-one user... trust that it worked, without babysitting a black box"). A live persona-driven pass is
  still owed (see Manual verification below — no browser automation run this session, though a local Playwright
  MCP registration exists for this project and should be checked via `ToolSearch` before assuming it's
  unavailable, per the note added to CLAUDE.md's MCP section earlier this session).

## Manual verification (owed, not yet run)

Per `.claude/qa-routes/route_77_onboarding_wizard.md`: load the wizard fresh (no `onboarding_completed`), step
through all five tools, confirm Status-popover visibility for the scan/import/axis-suggest jobs, confirm "Skip
setup" reaches `onboarding_completed=true` at every step, and — the sharpest check — seed an existing profile
first and confirm the identity step shows it rather than blanks.

## Pytest / build gates

- `pytest tests/test_settings.py tests/test_health.py -q` → **39 passed** (3 new: settings-endpoint round-trip,
  a direct `app_settings` store round-trip, and the `/health` reflects-a-settings-change test).
- `pytest tests/test_frontend_assembly.py -q` → **55 passed** (2 new: the wizard-orchestration/egress-honesty
  test, and the `MyPubsSettings` race-condition-fix regression test).
- Full suite: `pytest -n auto -q` → **1704 passed** (up from 1699 post-inc-415; +5 new here), run in 4 batches
  of ~33 test files each after several consecutive backgrounded full-suite attempts got killed mid-run by an
  apparent session-level resource/time constraint unrelated to this code (confirmed via zero test failures
  across every partial run, each cut off at a different, unpredictable point) — foreground execution in
  smaller batches completed cleanly with no failures in any of the four.
- `python tools/build_frontend.py` re-run after every frontend edit; line budgets checked directly (`wc -l`) —
  all touched files comfortably under 600 (`app_settings.py` 564, `40_app.jsx` 569 — both worth a future watch,
  neither over cap).

## Deferred to a follow-up increment

A guided spotlight tour of the menu-bar workspace tabs — no precedent anywhere in this codebase (no step-state,
no coachmark/spotlight CSS). Sequencing it in later is one new array entry in the wizard's step list plus one
`onOpenTour` wire-up — no rework of anything shipped here.
