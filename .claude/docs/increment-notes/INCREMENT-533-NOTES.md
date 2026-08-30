# Increment 533 — packaged Quick Tunnel convenience (backlog #33/#34 phase 3)

**Date:** 2026-08-29
**Scope:** explicit packaged-app Cloudflare Quick Tunnel lifecycle for Google Docs and Word on the web. No
adapter document semantics, named-tunnel behavior, provider behavior, model behavior, schema, or default egress
change.

## Product outcome

After turning on **Remote access** and copying its one-time bearer token, a packaged-app user can click **Start
Quick Tunnel**, copy the temporary `https://*.trycloudflare.com` URL, and connect Google Docs or Word on the web
without opening a terminal. The same control stops the tunnel. Turning Remote access off stops it first; app exit
also removes every owned process. Source checkouts retain `tools/run_tunnel.py --quick`, and the advanced named
tunnel remains the stable/cite-only option.

Quick Tunnel's security tradeoff stays visible beside the button: it cannot carry the named tunnel's
cloudflared-level path allowlist, so the existing bearer token is its sole boundary. The URL changes each launch
and may take a moment to propagate at Cloudflare's edge.

## The security-driven architecture change

The initial plan proposed pointing cloudflared at the ordinary packaged backend. Inspection found that this is
unsafe during opt-out: cloudflared forwards into loopback, so if the existing Remote-access setting becomes OFF
while the connector survives, the ordinary backend resumes trusting loopback and the public tunnel would become
unauthenticated.

Increment 533 therefore uses a dedicated Tauri-owned Uvicorn target with `CALLOSUM_TUNNEL_TARGET=1`. Its access
middleware has two states:

- Remote access ON: the unchanged bearer gate, exemptions, and rate limiter apply.
- Remote access OFF: only GET/HEAD `/health` remains reachable; every other request is 403.

The flag is process-local and fail-closed. Setting it accidentally on an ordinary backend can only deny access;
it cannot broaden access. The tunnel child shares the exact resolved database, library, app version, settings,
and Word storage paths but does not inherit managed-local-AI owner variables. It binds literal `127.0.0.1` on an
ephemeral port and disables Uvicorn access logging.

## Tauri ownership

`src-tauri/src/quick_tunnel.rs` owns both processes:

1. verify the persisted Remote-access opt-in;
2. locate an installed `cloudflared` (known package paths first, then PATH);
3. start the dedicated tunnel target with direct argv;
4. prove local `/health` is 200 and unauthenticated `/settings` is 401;
5. start cloudflared at info log level against that exact literal-loopback target;
6. accept only a strict lowercase/digit/hyphen `https://*.trycloudflare.com` URL from its output;
7. publish immutable in-memory status to Settings;
8. on stop, crash observation, or app exit, terminate connector and target with the existing Windows Job Object /
   Unix process-group contract.

The URL is not persisted. No token enters argv, logs, Rust state, status, or frontend responses. Cloudflared gets
an app-owned non-secret config so it cannot load or log an existing named-tunnel credential path. Info logging is
fixed because Cloudflare documents that debug logging includes request URLs and headers.

## Cloudflare readiness boundary

The real Windows acceptance showed Cloudflare Quick Tunnel edge propagation is nondeterministic: one isolated run
reached public `/health` 200 and token-gated `/settings` 401, while another issued and registered a URL that did not
become publicly reachable within 90 seconds. Cloudflare documents Quick Tunnels as testing/development facilities
with no uptime guarantee. Callosum therefore treats strict URL issuance plus a live connector as the external
boundary it can honestly observe, tells the user propagation may take a moment, and does not kill a valid connector
solely because Cloudflare's edge is temporarily unavailable.

The retained opt-in acceptance test gates Callosum-owned correctness: real target startup, 200 health, 401 bearer
gate, immediate 403 after settings opt-out, real cloudflared URL issuance, no inherited credentials/config path,
and cleanup. It is ignored in ordinary CI because it requires installed cloudflared and external service access.

## Verification

- Python fail-closed access tests cover OFF target denial, normal ON bearer behavior, and the recovery-disable
  environment not opening a target.
- Rust unit tests cover strict URL parsing and explicit settings opt-in; an opt-in live Windows test exercises the
  real target and installed cloudflared.
- Frontend assembly tests pin packaged-only status/start/stop commands, stop-before-opt-out ordering, the explicit
  bearer-only warning, URL copy, and the rebuilt artifact.
- Focused affected Python/frontend suite: **193 passed**. Full Python suite: **2588 passed, 3 skipped** in
  1441.99s (24:01), normal `pytest -n auto -q --tb=short` mode, no retries.
- Rust: complete serial suite **29 passed, 4 ignored**; the opt-in live Windows Quick-Tunnel acceptance separately
  passed. `cargo check`, strict all-target Clippy, and touched-file rustfmt passed. Crate-wide rustfmt remains
  blocked only by pre-existing untouched `updater.rs` drift.
- Ruff, Bandit, Tach, the 571-file line budget, QA surface map (435/435 gated API surfaces), website review,
  targeted pre-commit, staged secret/private-path scan, and `git diff --check`: clean.
- Actual Google Docs and Word-web host interaction remains in the consolidated manual adapter checklist requested
  by the maintainer; it is not claimed live-verified here.

## Revert

Revert the increment commit. No migration or persisted tunnel state exists. Source Quick Tunnel, named tunnel,
desktop Word, LibreOffice, and ordinary local backend behavior remain independently available.
