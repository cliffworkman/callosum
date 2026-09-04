# Increment 574 Notes — the auto-updater was invisible, and then it lied

## The report

Cliff, on 0.5.5, one hour after 0.5.6 published:

> 0.5.5 isn't seeing 0.5.6, and "Check for updates" from settings incorrectly suggested it
> downloaded and would be applied on restart, but after restarting, mousing over the Callosum logo
> suggests 0.5.5 is still installed.

and then, decisively:

> regardless of what settings says and does, the automatic update isn't showing up in status as
> downloading/downloaded with no modal with a button to restart/install.

Two symptoms. **One cause**, plus a second, independent honesty bug that made the first one land badly.

## What was NOT wrong (checked first, so the search stayed narrow)

- `latest.json` serves `0.5.6`, with real URLs pointing at assets that exist.
- Its three platform signatures are present, and their **minisign key id matches** the `pubkey` in
  `tauri.conf.json` byte-for-byte (`BA24330C18A3F3ED`). A key rotation would have looked identical
  from the outside, so this was worth proving rather than assuming.
- `install_update_now` **does** have its ACL grant *and* the `remote.urls` origin scoping — both
  axes inc 421 and inc 423 established. The toast's button was never broken.

So the manifest and the install command were fine. The failure was entirely in *surfacing*.

## Cause: the events fire before any window is listening, and are never replayed

`setup()` spawns `run_periodic_check`, which sleeps **30 seconds** and then checks. In parallel,
`start_backend_and_show_main` provisions the runtime, spawns the backend, waits for health — and only
*then* creates the `main` window, which loads the UI, mounts React, and finally registers
`useDesktopUpdate`'s listeners. The splash's own copy says that cold start "can take a minute the
first time."

So `update-downloading` → `update-progress` → `update-ready` are routinely broadcast **into a window
that does not exist yet**. Tauri does not replay events. Nothing appears in Status; no toast.

Then the state machine made it permanent for the session: `check_desktop` early-returns
`CheckOutcome::Ready` when `state.ready` is already populated — **without re-emitting**. So every
later check, periodic *or* the Settings button, returned "ready" and never emitted the event again.
The toast could not appear for the rest of that run no matter how many times Cliff clicked.

This is the same defect class backlog #78 independently flagged for the splash's `backend-status`
event ("startup state needs a queryable/replayable snapshot so an early event cannot be lost before
`splash.js` registers its listener"). Two surfaces, one hazard.

### Fix: make the state askable, not only announced

New `current_update_state` command returns the updater's phase in **exactly the shape
`useDesktopUpdate` already keeps in state**, so seeding is indistinguishable from having received
the events live. `useDesktopUpdate` now polls it once on mount, and a live event always wins over
the seed. Listening alone can only narrow the race; asking closes it. A longer `STARTUP_DELAY` was
considered and rejected for exactly that reason — it would have made the window smaller and the bug
rarer, which is worse than fixing it.

Belt and braces: the early-return paths now re-emit before returning, so even a client that never
polls recovers on the next check.

The new command got its own `allow-current-update-state` permission and capability entry, verified
empirically via `gen/schemas/acl-manifests.json` and `capabilities.json` rather than by reading the
TOML — the check inc 421 established after four commands were silently unreachable for two releases.

## The second bug: Settings asserted something false, and he acted on it

> **"Update ready — v0.5.6. Restart to install."**

The downloaded bytes live in `Mutex<Option<(Update, Vec<u8>)>>` — **memory**. They are installed only
by `install_update_now`. Quitting and relaunching **discards them**. Cliff did exactly what the text
said and lost the download; the tooltip still read 0.5.5, correctly.

On Linux the same string was false twice over: `CheckOutcome::Ready` there means *"a newer version
exists, open the release page"* — nothing is downloaded at all.

Settings also offered **no way to install** — only the toast had the button, and the toast was the
thing that never appeared. So the one working path was invisible and the visible path was a lie.

Now: when an update is ready, Settings renders the action that actually installs it
(`Install v0.5.6 and restart`, or `Get v0.5.6` on Linux), and says plainly that quitting without
installing discards the download and it will be offered again. The one-shot `CheckOutcome` carries no
`action`, so it is used only as a version fallback and never as the basis for telling someone which
action installs — the live event is the only source trusted for that.

## Also: the running version is now stated in Settings

Cliff's request, and the same incident is the argument for it: he could only discover he was still on
0.5.5 by hovering the logo. Settings → Desktop app now shows `Version 0.5.6` outright, read from
`/health`'s `app_version` (inc 417) — the same source the feedback dialog uses, so a bug report and
this label can never disagree.

## Housekeeping

`DesktopUpdateSettings` moved from `35_settings.jsx` to `04d_update.jsx`, beside the rest of the
updater surface — the inc-208/222/256 shared-IIFE hoist. Both because every "what is the updater
doing" string now lives in one file, and because `35_settings.jsx` was at **580/600** with no room
for this fix. It is now **540**.

## Verification

- `cargo check`, `clippy -D warnings`, `cargo fmt` clean; **48 passed / 0 failed / 6 ignored**.
- ACL resolution confirmed on both axes from the generated schemas, not the source TOML.
- The Settings decision logic exercised across six states (idle / ready-restart / downloading /
  up-to-date / linux-ready / failed); Cliff's exact case yields `Install v0.5.6 and restart`.
- Frontend rebuild + `test_frontend_assembly.py`: 87 passed.
- Minisign key-id match and manifest URL existence verified against the live release.

## Honest limits

- **The race fix is reasoned and unit-checked, not observed failing-then-passing in a packaged
  build.** Reproducing the original required a cold start slower than 30s on a real install; I
  verified the mechanism by reading the ordering and the absent replay, not by instrumenting a
  packaged run. The seed-on-mount path is defensive either way: if the events *were* arriving, the
  seed is a no-op because a live event wins.
- **Cliff's 0.5.5 install cannot benefit from this** — the fix ships *in* the update he cannot
  currently see. Getting from 0.5.5 to 0.5.6 needs the toast (wait ~30s after launch, then check
  Settings) or a manual installer download. From 0.5.6 onward the flow is fixed.
- Whether an install-on-quit would be better than discarding the download is a real open question,
  deliberately not answered here: it would need a packaged build to test, and shipping an untested
  installer-on-exit path is exactly how you get an app that hangs when the user quits.
