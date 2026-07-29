# Increment 417 — auto-updater follow-up: real app version + progress visibility + on-demand check

## Implemented

Prompted directly by watching v0.3.2's release go live and the auto-updater's first-ever real test
against a running v0.3.1 install, Cliff asked for three small, related fixes:

1. **The brand-logo connection tooltip now shows the real app version.** It previously showed
   `verification_version` (`app/backend/summarization/verification.py`'s `VERIFICATION_VERSION`
   constant, `"local-verifier-v1"`) — an internal, never-changing identifier for the local NLI/
   quote-verification pipeline, completely unrelated to the app's own release number. This
   happened because `/health` had no real app-version field at all, so the frontend's fallback
   chain (`r.data.verification_version || r.data.version`) always resolved to the former. Fixed at
   the source: `HealthResponse` gains `app_version: str | None`, read via
   `os.getenv("CALLOSUM_APP_VERSION")`. The desktop shell sets this env var itself — `backend.rs`'s
   `spawn_backend` now takes an `app_version: &str` parameter and sets it on the uvicorn child
   process; `lib.rs`'s `start_backend_and_show_main` supplies `app.package_info().version.to_string()`
   at the one call site. A plain `uvicorn` dev run or the remote-access tunnel never sets this env
   var, so `app_version` is honestly `None` there — no version invented for a non-packaged run,
   consistent with `read_only`/`onboarding_completed`'s existing precedent of being real-vs-absent
   rather than defaulted. The frontend (`40_app.jsx`'s health effect) now reads `r.data.app_version`
   exclusively.

2. **Update-download progress now surfaces in the Status popover.** The auto-updater (`updater.rs`)
   lives entirely in the Tauri/Rust process — it is *not* a backend `JobStore`, so it can never
   appear via the existing `GET /status/jobs` aggregator (inc 406/415's reflection-over-`api.state`
   design has no way to see across the process boundary, by construction). Instead: `updater.rs`
   now emits two new events during the silent Windows/macOS download — `update-downloading` (once,
   when the download starts) and `update-progress` (`{version, downloaded, total}`, throttled to
   ~256KB-or-completion steps so the webview isn't flooded with an event per network chunk). The
   frontend's Tauri-event listening moved out of `UpdateNotice` (the toast) into a new shared hook,
   `useDesktopUpdate()` (`04d_update.jsx`) — a single source of truth for "what is the desktop
   update doing right now," read by both the toast (which still only renders once truly `"ready"`,
   unchanged) and the new `04c_status.jsx`'s `desktopUpdateStatusJob()`, which shapes that shared
   state into the exact row shape a real `StatusJob` has — a synthetic, frontend-only entry, merged
   into the popover's displayed list but never sent to or dismissed via the backend (there is no
   backend job to dismiss). Deliberately **not** added to `STATUS_NAVIGABLE_STORES` (inc 415's
   click-to-navigate allowlist): the `"ready"` phase already has its own dedicated toast with the
   restart action, and a second click-to-restart path in Status could drift out of sync with it.
   The synthetic row's own dismiss is component-local (`updateDismissedPhase`, keyed by phase — so
   dismissing "downloading" doesn't suppress the later, genuinely-new "ready" transition).

3. **A new Settings → Desktop app → "Check for updates" button.** Previously the only way to check
   was to wait for the periodic cycle (on launch, then every 6h) — exactly the gap Cliff hit
   ("restarted 5 minutes ago, nothing yet") with zero way to get an honest answer either way.
   `updater.rs` gained a `CheckOutcome` enum (`UpToDate` / `Downloading{version}` / `Ready{version}`
   / `Failed{detail}`) and a new `#[tauri::command] check_for_updates_now`, which reuses the *exact
   same* `check_desktop`/`check_linux` functions the silent periodic loop already calls — the only
   difference is the caller now reads the result. The check itself resolves quickly (one network
   round-trip); if a newer version is found, the actual download is handed off to a new
   `spawn_download` background task (so a manual click never blocks on a potentially large
   transfer) — its progress/completion ride the exact same `update-downloading`/`update-progress`/
   `update-ready` events described above. `DesktopUpdateSettings` (`35_settings.jsx`) renders
   nothing outside the desktop shell (`!("__TAURI__" in window)`) — a plain browser tab or the
   remote-access tunnel never shows a dead button — and its status text prefers the *live* shared
   `desktopUpdate` state over its own one-shot `invoke()` result once a download it kicked off
   actually starts progressing (so leaving Settings open still shows the real state, not a stale
   snapshot from the moment of the click).

## Key technical detail

A new `downloading: Mutex<Option<String>>` field on `UpdateState` (Windows/macOS) prevents the
manual command from starting a second concurrent download if the periodic loop's own download is
already in flight — a real (if previously unlikely, since nothing but the 6h loop could ever
trigger a check) race the original single-shot design never had to consider before an on-demand
trigger existed. `check_desktop` now checks this guard (and the existing `ready` guard) before ever
calling `updater.check()`, returning `CheckOutcome::Downloading{version}` / `Ready{version}`
immediately if either is already true.

## Housekeeping

- Security audit: addendum to `.claude/security-audits/2026-07-28_desktop-shell-auto-updater.md`
  (no new egress channel or trust boundary — see the addendum for the full threat-delta walkthrough).
  Verdict unchanged: PASS.
- Also fixed in the same session, immediately before this increment: `tests/e2e/test_smoke.py`'s
  server fixture now isolates `CALLOSUM_SETTINGS_PATH` with `onboarding_completed` pre-set — inc
  416's first-run wizard was silently failing 4 of 6 browser smoke tests in CI because a fresh
  runner has no prior `~/.callosum/app-settings.json`, so the wizard overlay rendered over the
  seeded app and intercepted every test's clicks. Caught by watching v0.3.2's own CI run.
- `python tools/qa/build_surface_map.py check` still reports the same 4 API + 12 frontend uncovered
  surfaces `INCREMENT-416-NOTES.md` already flagged as pre-existing debt (grim-checks/funding-runs/
  journal-runs endpoints; the tags panel; the pre-existing toast buttons in `04d_update.jsx`) — no
  new surface from this increment appears in that list. No new QA route added: this whole feature
  family (the auto-updater, since inc 409) has never had one, since it's desktop-shell/Tauri-only
  and untestable through the existing Codex/Playwright QA harness (which drives a plain browser with
  no `window.__TAURI__`) — consistent with inc 409's own notes never mentioning a QA route either.
  Flagged, not invented here.
- `python tools/check_line_budget.py` — all 418 application-source files still within the 600 cap.

## Manual verification (owed — no live desktop-shell/browser automation ran this session)

Once a future release ships this code: launch the packaged app, hover the brand logo and confirm
the tooltip reads "Connected (0.3.x)" (the real shell version, not "local-verifier-v1"); open
Settings → Desktop app and click "Check for updates" — confirm it reports "You're up to date"
against the current release; and (the harder one to rehearse deliberately) watch the Status popover
during a real update download and confirm a "Downloading update vX.Y.Z" row with a real MB-progress
bar appears, then flips to "Update ready — vX.Y.Z" once done.

## Pytest / build gates

- `pytest tests/test_health.py tests/test_frontend_assembly.py -q` → **65 passed** (3 new: the
  `app_version` env-var round-trip, the connection-tooltip-source assertion, and the desktop-update-
  in-Status/Settings assertion).
- Full suite: `pytest -n auto -q` → **1707 passed, 1 skipped** (up from 1704 post-inc-416; +3 here),
  run in the foreground per this session's established workaround for backgrounded full-suite runs
  getting killed by an apparent session-level resource constraint — this run completed cleanly in
  16m23s with zero failures.
- Rust: `cargo check` and `cargo test` both clean against the full `updater.rs`/`backend.rs`/
  `lib.rs` diff (4/4 existing unit tests still pass; no new Rust tests needed — the new logic is
  either a straightforward env-var passthrough or a thin reuse of already-tested check functions).
- `python tools/build_frontend.py` re-run after every frontend edit; `check_line_budget.py` clean.
