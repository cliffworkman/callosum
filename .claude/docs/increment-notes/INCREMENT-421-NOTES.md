# Increment 421 — fix: the desktop shell's own commands had no ACL grant at all

## Implemented

A real bug report from live use: Cliff clicked the newly-relocated "Check for updates" button (v0.3.4) and
got `Couldn't check for updates: Command check_for_updates_now not allowed by ACL`.

Root cause, confirmed empirically (compiling locally and inspecting the real, build-time-generated ACL
manifest — not guessed): `app/desktop-shell/src-tauri/capabilities/default.json` only ever granted
`"core:default"` — Tauri's own built-in core APIs (window, event, app, etc.). Tauri v2's ACL system requires
a **separate, explicit permission grant for every custom `#[tauri::command]`**, generated from
`src-tauri/permissions/*.toml` files. This app never had a `permissions/` directory at all — confirmed by
inspecting the pre-fix `gen/schemas/acl-manifests.json`, whose top-level keys were only `core`, `core:app`,
…, `updater` (the plugin), with no entry at all for the app's own commands.

**This means all four of the shell's own commands were equally unreachable from day one** — not just the
newly-added `check_for_updates_now`: `retry_backend` (the splash screen's Retry button), `install_update_now`
(the "Restart now" action on a ready update toast — never yet reached in the field, so never caught), and
`open_release_page` (the Linux fallback). This has shipped, silently broken, since inc 409 (v0.3.0) — every
release through v0.3.4 carries it. Caught only now because `check_for_updates_now` (inc 417) was the first of
the four ever actually clicked by a real user.

**Fix:** new `app/desktop-shell/src-tauri/permissions/default.toml`, following the exact schema used by the
real `tauri-plugin-updater` dependency's own permission files (read directly from the installed crate source
for a proven-correct reference, not guessed) — four `[[permission]]` blocks (`allow-retry-backend`,
`allow-install-update-now`, `allow-open-release-page`, `allow-check-for-updates-now`), each with
`commands.allow = ["<command_name>"]`, plus a `[default]` table listing all four. `capabilities/default.json`
now references all four identifiers (bare, no namespace prefix — these are the app's own commands, not a
plugin's) alongside `"core:default"`.

## Key technical detail

Verified the fix empirically rather than trusting the schema reading alone: after `cargo check`, the
regenerated `gen/schemas/acl-manifests.json` gained a brand-new top-level `__app-acl__` key (absent before
the fix) containing exactly the four permissions defined, each correctly resolving to its real command name.
The regenerated `gen/schemas/capabilities.json`'s `default` capability's `permissions` array now echoes all
four new identifiers alongside `core:default`. Both are gitignored, build-time-generated artifacts — the
`__app-acl__` key's *existence* is itself proof the app-level permission file was discovered and processed
correctly, not just that the TOML parsed without error.

## Housekeeping

- No security audit triggered per the letter of the gate (no new API endpoint, no new external integration, no
  new file-ingestion path, no new auth logic, no new third-party dependency) — but worth stating the risk
  posture plainly since this IS access-control-adjacent: this fix *grants* capability, it doesn't add any. All
  four commands take no user-supplied arguments from the frontend at all (`check_for_updates_now`,
  `install_update_now`, `open_release_page` take only the implicit `AppHandle`; `retry_backend` likewise) — so
  there's no new injection/scope surface opened by allowing them, only the ability to invoke the exact same
  fixed, parameter-free actions the app was always designed to expose to its own UI.
- `cargo check` clean; `cargo test` — 4/4 existing unit tests still pass, no new Rust tests needed (this is
  config, not logic — the empirical ACL-manifest inspection above is the real verification for this kind of
  change, the same way a schema migration is verified by inspecting the resulting schema, not by a unit test).

## Manual verification (owed until the next release ships and Cliff can click through live)

Once this ships: Settings → Account & sync → Desktop app → "Check for updates" should return a real
"You're up to date" / "Downloading vX.Y.Z…" / an honest error — never the ACL error again. If a future update
ever reaches the "ready" toast, "Restart now" (`install_update_now`) should now actually install and restart
instead of silently failing the same way.
