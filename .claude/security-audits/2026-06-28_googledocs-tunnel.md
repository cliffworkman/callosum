# Security audit — Google Docs bridge: cloudflared tunnel + cite-only ingress (inc 169, SP1)

**Date:** 2026-06-28
**Feature:** The bridge that makes local callosum reachable by the Google Docs add-on: a **cloudflared** named tunnel
(runs on the user's PC, outbound-only) serving `https://callosum.clffwrkmn.net` with a **cite-only ingress
allowlist**. This is the **live-egress / exposure** step that builds on the inc-168 token gate (SP0). Artifacts:
`adapters/googledocs/cloudflared-config.yml` (the ingress), `adapters/googledocs/README.md` (the runbook),
`tools/run_tunnel.py` (a thin runner). **No callosum code/endpoint/dependency change** (cloudflared is an external
binary the user installs via winget; the config + helper + docs are the increment).
**Audit triggers:** new external-facing exposure of the app (the Security baseline's deployment gate).

## What is exposed, and what is NOT
The tunnel's ingress (`cloudflared-config.yml`) forwards to `http://localhost:8080` **only** these paths:
`/papers`, `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles`. **Everything
else returns 404 at the tunnel** — verified with `cloudflared tunnel --config … ingress validate` (OK) +
`ingress rule <url>`:
- `/papers`, `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` → `localhost:8080`. ✔
- `/settings` → **404**, `/papers/5` (the `/papers/{id}` edit/delete + sub-routes) → **404**, `/` (app shell) → **404**. ✔

So through the tunnel: no app UI, no `/settings` (no token/egress controls), **no folder-scan/file-read routes**
(the Security-baseline server-file-read concern), no paper edit/delete/annotate. The required SP1 control recorded in
the inc-168 audit (the ingress allowlist) is now **shipped + validated**.

## Threat review
- **Auth (the second boundary).** Every forwarded request still hits callosum's inc-168 `AccessControlMiddleware`,
  which requires a constant-time bearer token (Remote access must be ON for the tunnel to be useful). A tunnel caller
  without the token → 401 even on the five allowed paths. Two independent boundaries (token + cite-only ingress).
- **Network exposure.** cloudflared dials **outbound** to Cloudflare's edge — **no inbound port** on the user's
  machine or router. The persistent process runs locally (not on shared hosting). Stopping `run_tunnel.py` closes
  the bridge entirely.
- **Blast radius on clffwrkmn.net.** Only `callosum.clffwrkmn.net` is delegated to Cloudflare (two NS records at
  HostGator); the rest of the domain (website, email, all other records) stays on HostGator, untouched.
- **TLS.** Terminated at Cloudflare's edge (valid cert for `callosum.clffwrkmn.net`); cloudflared↔origin is over the
  Cloudflare-secured tunnel; origin is localhost. No self-signed-cert handling.
- **Egress (invariant #3 posture).** With Remote access on + the tunnel up, the cited-paper metadata in add-on
  requests transits Cloudflare's edge + Google's cloud — **the explicit, opt-in egress the user chose** by enabling
  Remote access (default-off; A-A consent value). No library *full text* is sent (the cite endpoints return
  citation metadata + rendered strings; the suggest endpoint returns the user's own quotes — same data the in-app
  Cite pane shows). Trusting Cloudflare + Google with that transit is inherent to choosing this bridge; documented.
- **Secrets.** The cloudflared tunnel **credentials file** (`<UUID>.json`) lives in `~/.cloudflared/` (outside the
  repo); the config references it by path. The committed `cloudflared-config.yml` has only **placeholders**
  (`<TUNNEL_ID>`/`<HOME>`) — no secret is committed. The access token is the inc-168 secret (keychain/file).
- **Supply chain.** cloudflared is Cloudflare's signed binary (winget `Cloudflare.cloudflared`); not vendored, not a
  Python dependency. `tools/run_tunnel.py` only shells out to it with a fixed config path (no request input).
- **Resource exhaustion.** The inc-168 rate limiter (429) applies to forwarded requests; Cloudflare also fronts
  abuse at the edge.

## Negative-path checks
- Ingress allowlist validated (`ingress validate` → OK) + per-URL routing proven (cite → localhost; everything else
  → 404), above. ✔
- `run_tunnel.py` refuses to run with the placeholder config still in place (forces the user through setup). ✔
- No token → 401 at the origin even for allowed paths (inc-168 tests). ✔
- (User's live check, per README §6): `curl` the tunnel with/without the token + a non-cite path.

## Residual risk / required posture
- The cite-only guarantee depends on the **ingress allowlist staying intact** — if a user widens it, more of the
  local app becomes reachable (still token-gated). Documented; the committed config is the safe default.
- The live tunnel can't be exercised in CI (needs the user's Cloudflare account) — verified by config validation +
  the documented `curl` check. The Apps Script add-on (SP2) is manual-test-only.

## Result
**Security Audit: PASS** — outbound-only, two independent boundaries (constant-time token + validated cite-only
ingress), minimal blast radius (one delegated subdomain), no secret committed, no new code/dependency in callosum.
The egress is the user's explicit opt-in; trusting Cloudflare + Google for transit is inherent to the chosen bridge
and documented.

---

## Addendum (inc 193) — the Quick-Tunnel convenience mode (`run_tunnel.py --quick`)

To spare a new user the whole Cloudflare-account + domain-migration + named-tunnel setup, `tools/run_tunnel.py
--quick --port <p>` runs a **Cloudflare Quick Tunnel** (`cloudflared tunnel --url http://localhost:<p>`) — zero
account/domain/config; it prints a throwaway `https://<random>.trycloudflare.com` URL.

**The one real posture change — call it out:** a quick tunnel takes **no ingress config**, so it **cannot enforce
the cite-only allowlist**. Through a quick tunnel, *every* endpoint is reachable (gated only by the bearer token),
including the file-read/scan routes (`/library/scan`, watched-folder rescan) and `/papers/{id}` edit/delete — not
just the five cite paths. So in `--quick` mode the **constant-time bearer token is the SOLE boundary** (it is already
the *primary* one — see the inc-168 remote-access audit — but the cite-only ingress's defense-in-depth is gone).

**Why this is acceptable as an explicit, opt-in mode (A-A consent value):**
- It is **opt-in + non-default**: the named tunnel (cite-only) remains the documented stable path; `--quick` is a
  separate flag a user runs knowingly. Remote access itself is still default-OFF + requires a minted token (inc 168).
- The token is a `secrets.token_urlsafe(32)`, constant-time-compared, never returned by the API; a quick-tunnel URL
  is an unguessable random `trycloudflare.com` host that changes each launch and exists only while the process runs.
  The runner **prints the tradeoff** ("your bearer token is the only boundary — keep it secret + turn Remote access
  off when done") so the consent is informed.
- **No new code path in callosum** — the app + its token gate are unchanged; this is a `tools/` launcher option +
  docs. No new dependency (cloudflared already required by the named path). The README leads with this as the "try
  it fast" path and keeps the named-tunnel (cite-only) path for a stable/hardened setup.

**Addendum decision: PASS** (opt-in, token-gated, informed-consent convenience mode; the cite-only-ingress reduction
is documented + the named path remains). A future hardening idea (not built): an app-level "cite-only when remote"
mode — deferred because the app can't distinguish tunnel vs. local requests (the inc-168 loopback-indistinguishability),
so it would also restrict the local browser.

(The single-file add-on bundle — `tools/build_gdocs_addon.py` → `callosum-gdocs.gs` — is **not** a security change:
it concatenates the existing three Apps Script sources [inlining the sidebar HTML as a string served via
`HtmlService.createHtmlOutput`] into one paste; same code, same cite contracts, no new endpoint/egress.)
