# Increment 423 — fix: a second, independent ACL gate (local/remote origin scoping)

## Implemented

Cliff finished installing v0.3.5 (which carries inc 421's ACL-grant fix) and hit the **exact same error**:
`Couldn't check for updates: Command check_for_updates_now not allowed by ACL`. This directly falsified inc
421's own verification method — the permission grant was confirmed present and correct
(`git merge-base --is-ancestor` confirms the inc-421 commit is an ancestor of the v0.3.5 tag), yet the real
installed binary still rejected the call.

Root cause: Tauri v2 capabilities gate on **two independent axes**, not one. Inc 421 fixed the
permission/command axis (`commands.allow` in `permissions/*.toml`, referenced by identifier in
`capabilities/default.json`'s `permissions` array). The **second** axis is origin scoping — a capability's
`local` field (default `true`) only covers windows whose content is served from Tauri's own bundled/asset
origin; content loaded via `WebviewUrl::External` to a genuine HTTP URL is **not** "local" in Tauri's ACL sense,
even when that URL is loopback.

`app/desktop-shell/src-tauri/src/lib.rs:39-40` creates the app's real UI window this way on purpose (it's
loading callosum's own bundled backend server, not Tauri's asset protocol):
```rust
let url = format!("http://127.0.0.1:{port}").parse().expect("valid loopback URL");
WebviewWindowBuilder::new(&app, "main", WebviewUrl::External(url))...
```
Confirmed directly (not guessed) by inspecting the real, build-time-generated `gen/schemas/capabilities.json`:
it showed `"local":true` with **no `remote` key at all** on our one capability. Without a `remote.urls` entry
matching that origin, every `invoke()` call from the `main` window is rejected by this second gate regardless
of whether the command has a permission grant — which is every one of the shell's user-facing update commands
(`check_for_updates_now`, `install_update_now`, `open_release_page`). Only `retry_backend` was ever unaffected,
since it's invoked exclusively from the `splash` window, which genuinely does load bundled `frontendDist`
content and so is legitimately "local."

This exactly matches a documented Tauri upstream discussion
([tauri-apps/tauri#11622](https://github.com/tauri-apps/tauri/discussions/11622)) — a webview loading a
dynamically-ported `http://localhost:PORT` origin, solved with a wildcard-port `remote.urls` pattern using
WHATWG URLPattern syntax.

**Fix:** `app/desktop-shell/src-tauri/capabilities/default.json` gained:
```json
"remote": {
  "urls": ["http://127.0.0.1:*/*"]
}
```
`lib.rs` always builds this URL as literally `127.0.0.1` (never `localhost`/`::1`), so one pattern covers it;
the wildcard port matches the backend's dynamically-chosen port. No permission/command changes — this closes
the second gate for the same four already-granted commands from inc 421.

## Key technical detail

Why inc 421's own verification didn't catch this: checking that `gen/schemas/acl-manifests.json` gained the
`__app-acl__` entry only proves a permission **parses and registers at compile time** — it says nothing about
whether a specific window's *content origin* is in scope for that capability at runtime. The two checks are
orthogonal; a command can be fully, correctly permission-granted and still be rejected purely on origin scope.
This time, the same empirical method (regenerate `gen/schemas/capabilities.json` via `cargo check`, confirm the
new `"remote"` key is present) was re-run, but this bug is a reminder that schema-presence checks alone can't
prove a runtime grant — only an actual click against a real installed build definitively can, which is exactly
what surfaced it.

## Housekeeping

- Not a security-audit-gate trigger (no new endpoint/fetch/ingestion/auth path, not 300+ LOC, no new
  dependency) — but worth stating plainly: this widens IPC access to any content served from loopback on any
  port, not just the backend's current port. The `main` window never navigates anywhere else, and the backend
  already binds only to `127.0.0.1` with no network exposure (any other local process could already reach it
  directly over HTTP regardless of Tauri's ACL) — so this doesn't meaningfully expand the existing local-only
  threat model.
- `cargo check` clean; the regenerated `gen/schemas/capabilities.json` confirmed the `"remote"` key is now
  present on the `default` capability. No Rust unit tests added (config-only, same rationale as inc 421).
- Folded into the already-in-flight v0.3.6 bump (originally a deliberate no-op test release Cliff requested to
  exercise the inc-421 fix) rather than a separate version — v0.3.6 is now the first build where the full
  update flow (check → download → install/restart) should work end-to-end from the UI, not just from the
  background Rust task that never calls `invoke()` at all.

## Manual verification (owed until v0.3.6 ships and Cliff can click through live)

Once v0.3.6 ships: Cliff's already-installed, ACL-permission-fixed v0.3.5 should, on "Check for updates"
(Settings → Account & sync → Desktop app), get a real result — "up to date" / "Downloading…" / an honest
error — never the ACL rejection again, on either gate this time.
