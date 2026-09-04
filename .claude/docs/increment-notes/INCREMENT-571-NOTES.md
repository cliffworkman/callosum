# Increment 571 Notes — the macOS verify step was watching the wrong process (#74)

## The symptom

The macOS desktop-shell CI verify step had **never once** printed `healthy on port N after Ns`, while
Linux and Windows both did. Not a regression from the inc-570 runtime work — the v0.5.3 release run
warned too, before any of it existed. Real macOS users ran the app fine, so the gate was left as a
`::warning::` (Cliff's call) while Linux was blocking.

## The cause: macOS App Translocation

The step deliberately quarantines the installed app to face the same Gatekeeper posture a real
download does, opens it once to record what Gatekeeper actually does, then removes the quarantine and
opens it again — and the health poll waits on that second launch.

But **macOS runs a quarantined app from a randomised read-only copy**, not from `/Applications`:

```
/private/var/folders/.../T/AppTranslocation/<uuid>/d/Callosum.app/Contents/MacOS/callosum-shell
```

That translocated instance stayed alive, so the second `open` merely re-activated it rather than
starting a fresh trusted process. **The health poll was watching an instance that was never the one
under test.** The decisive evidence was a single PID persisting across all three probes twenty minutes
apart, on both architectures.

Stopping the quarantined instance before the trusted launch fixed it outright:

```
app processes:  … /AppTranslocation/…/Callosum.app/…      ← quarantined
--- after stopping the quarantined instance ---
app processes:  (none)
app processes:  23843 /Applications/Callosum.app/Contents/MacOS/callosum-shell
healthy on port 49265 after 45s        (arm64: 33s)
```

The app was never broken. The observation was.

## Two hypotheses disproven, both by evidence rather than argument

1. **`ps` column truncation** (inc 570). The theory was that macOS truncates the command column while
   Linux does not, so a port at the end of a long argv could never match. `ps auxww` changed nothing —
   both jobs still ran the full 20-minute budget. `ps auxww` was kept anyway; strictly more
   informative, no downside.
2. **A hung `open`.** Plausible, since inc 395 recorded one hanging 25+ minutes on a Gatekeeper dialog,
   and the ambiguous `pgrep -f "Callosum.app"` could not tell the app from the `open` command that
   launches it. The instrumented probe reported `open processes: (none)` — `open` exits cleanly. Wrong
   again, but the probe that disproved it is what revealed the translocation path.

Recording both so nobody spends them a third time.

## The silences that hid it, now closed

The reason this took an investigation rather than a glance is that **every channel that could have
carried the answer was shut**. Each of these is a fix in its own right, independent of #74:

- **`smoke_test` discarded the interpreter's output** — `Stdio::null()` on both streams, reporting only
  "did not pass its import check" with no reason, at the single most likely place for a
  platform-specific failure to vanish (first execution of a freshly downloaded, unsigned binary). It
  now captures output to a file — a file rather than a pipe, because the wait loop uses `try_wait` and
  a full pipe with no reader would deadlock — and includes a bounded last line plus the exit status.
- **A failed startup existed only as pixels.** On failure the app stays alive showing the reason on the
  splash and never writes `backend.log`, because that file is only created *after* the backend spawns.
  `emit_status("failed")` now also writes `startup-error.log` (app-data dir, falling back to temp,
  since failing to resolve that dir is itself a plausible cause). This matters most for real users: a
  person who can only say "it says starting forever" now has a file to send.
- **A panic in the startup task was swallowed.** `setup()` fired `start_backend_and_show_main` via
  `tauri::async_runtime::spawn` and never looked at the handle, so a panic produced no crash report, no
  status, and no log — indistinguishable from a slow first-run download. The task is now supervised and
  a dead task becomes a visible, recorded failure.
- **The workflow probe could not name what it found.** It now prints what is really in
  `Contents/MacOS/`, probes on the executable path rather than the bundle name, reports app and `open`
  liveness separately, and on failure dumps the unified log, crash reports, `startup-error.log`, and
  whether `python-runtimes/` was ever created.

## The gate

Promoted from `::warning::` to `::error::` + `exit 1`, matching Linux and Windows. That is the actual
deliverable: an unblocked but permanently-excused platform was the status quo, not a fix — and #71
already demonstrated what a gate that cannot fail costs.

## Verification

- macOS CI printed `healthy on port` for the first time on **both** architectures: x64 45s, arm64 33s.
  That also retires inc 570's honest caveat — **first-run provisioning is now proven on all three
  platforms** on fresh runners, not two.
- `cargo test` 48 passed / 0 failed / 6 ignored; `clippy -D warnings` clean; `fmt` clean.
- The blocking gate is verified by the run that follows this change actually passing, not by reading
  the YAML.

## Honest limits

- The fix is verified on GitHub's macOS runners. Translocation behaviour depends on how an app arrives
  and whether Finder moved it, so a real user's path may differ — though a user who drags the app to
  Applications in Finder does not get translocated at all, which is the more forgiving case.
- Nothing here touched the Rust startup path's *behaviour*; the app was working the whole time. The
  three silence fixes are improvements to diagnosability, not to correctness.
