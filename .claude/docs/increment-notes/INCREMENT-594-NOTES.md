# Increment 594 — Startup loader: structured state + queryable snapshot (#39, bounded subset)

The desktop startup splash could sit on one static line for ~a minute (a real 0.5.5 upgrade), and — the
architecturally important part — an early `backend-status` event could be **lost** if the splash's JS listener
registered after it fired (Tauri never replays events; the same backlog-#78 hazard `updater::current_update_state`
already documents for the `main` window). This increment fixes the timing boundary and makes the splash branded,
stateful, and honest. **It is a bounded subset of #39 — the issue stays open** (remaining obligations below).

## The timing-boundary fix (the core)
- **`startup.rs` (new):** Rust **owns** the current startup state in an app-managed `StartupState`
  (`Mutex<StartupSnapshot>` + a fixed `started_at`). `record(app, state, detail, downloaded, total)` is the
  **single seam** that both updates the snapshot AND broadcasts `backend-status` — so the queryable snapshot and
  the live event can never diverge. `current_startup_state` (a `#[tauri::command]`, mirroring
  `updater::current_update_state`) returns the latest snapshot with a fresh `elapsed_ms`.
- **`lib.rs::emit_status` and `python_runtime.rs::emit_progress`** now route through `startup::record` (their
  direct `emit_to` calls removed). The command is registered + ACL-gated (`allow-current-startup-state`, on the
  splash+main capability; the ACL manifest resolves it) + `StartupState` managed.
- **`splash.js`** now **seeds** from `current_startup_state` on load, THEN listens for live updates (a live event
  wins over the seed) — so a late-registered listener never loses the first stage.

## Structured state, honest progress, branding, a11y
- **Structured stage rendering (no prose parsing):** `STAGE_LABELS` maps each real `state` the shell records
  (`runtime_check → runtime_manifest → runtime_migration | runtime_download → runtime_extract → runtime_ready →
  starting`, plus `failed`) to a human stage line. The splash switches on `state`; `detail` is secondary copy,
  never parsed for control flow. A pytest pins that **every** emitted state has a label (drift fails loudly).
  Only stages the startup path actually distinguishes appear — no invented ones.
- **Progress honesty:** a determinate bar only when byte totals exist (the download); a slow non-measurable
  phase (hash/verify/reuse/starting) shows an **honest elapsed timer** (ticking locally so it advances during an
  event-quiet phase) — **no fabricated percentage/ETA**, and no pre-walking 40k files to manufacture a
  denominator.
- **Branding:** the app's own brain mark (`128x128.png` copied to `splash/logo.png`, a **bundled local asset**
  via `frontendDist: "../splash"`, not a hand-maintained base64 blob), and "Callosum" capitalization.
- **Failure/retry:** the `retry_backend` path is preserved; the splash shows the shell's **sanitized** message
  (the full diagnostic is written to a log by `record_startup_failure`, never surfaced on the splash).
- **Accessibility:** the stage line is an `aria-live="polite"` `role="status"` region.
- **Bug fixed in passing:** the inherited `formatBytes` used `["B","MB","GB"]` while dividing by 1024 — it
  mislabelled every value one unit too large (1 MB → "1.0 GB"). Now `["B","KB","MB","GB"]`.

## Verification
- **Rust:** `cargo check` clean; `startup` unit tests (3) — default snapshot is idle; the snapshot serializes
  with the exact splash field names (a rename would silently break progress). ACL manifest resolves
  `current_startup_state`.
- **Contract (`tests/test_splash_startup_states.py`, 4):** every recorded state has a `STAGE_LABELS` entry;
  `failed` is emitted + handled distinctly; the splash seeds-then-listens and both emit paths route through
  `record`; no-fake-progress + aria-live present.
- **Pure JS:** `formatBytes`/`formatElapsed` verified standalone (incl. the ~1.2 GB runtime case).

## Remaining #39 obligations (why the issue stays OPEN)
1. **Finer emit stages the current path doesn't distinguish** — a distinct "starting Local AI", "waiting for
   backend health", and "smoke-testing runtime" would need **new emit sites** in the Rust startup flow (they
   currently fold into `starting`/`runtime_extract`). Deliberately not invented here (the steering: don't add
   stages the path can't distinguish) — adding the emit sites is follow-up work.
2. **Live packaged-app verification** — the splash is a **native window, not scriptable**; branding + staged
   messages + the alive indicator + late-listener seed + retry must be confirmed on a **real first-launch/update**
   against the 0.5.13 installer (the main-push desktop-shell CI screenshot covers branding; the timing/seed
   behavior needs a real slow start).
