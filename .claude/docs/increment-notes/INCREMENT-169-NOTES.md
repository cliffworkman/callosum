# Increment 169 — Google Docs SP1: the cloudflared bridge (cite-only) for callosum.clffwrkmn.net

**What the user asked for:** `callosum.clffwrkmn.net` to reach the local library from a Google Docs add-on, **only
touching the callosum element** (not moving the whole domain), and granted SSH + winget to build/deploy.

## Recon (read-only, via the granted SSH) — the decisive finding
Generated a dedicated SSH keypair, the user authorized it (cPanel), then read-only recon of clffwrkmn.net:
- It's **HostGator cPanel shared hosting** (`gator3026.hostgator.com`, shell `/usr/local/cpanel/bin/jailshell`,
  home `/home4/cliffworkman`). php 8.3 + python3 + curl present; **node/cloudflared/autossh absent**.
- **`ssh -R` (remote port forwarding) is administratively prohibited** — tested with `-R 18080:localhost:8080
  -o ExitOnForwardFailure=yes` → *"remote port forwarding failed for listen port 18080."*
- → A reverse SSH tunnel **through** clffwrkmn.net is impossible, and a persistent relay process there would be
  reaped (shared hosting) with no Node. **clffwrkmn.net cannot be the relay** — confirmed by test, not guessed.

## The chosen path: Cloudflare subdomain delegation + local cloudflared
This honors "only the callosum element": delegate **only** `callosum.clffwrkmn.net` to Cloudflare (a free
subdomain *zone* + two NS records at HostGator), leaving the rest of clffwrkmn.net on HostGator untouched; then a
**cloudflared** named tunnel runs on the user's PC (**outbound-only, no inbound port**) and serves the subdomain.

## Implemented
- **`adapters/googledocs/cloudflared-config.yml`** (new) — the named-tunnel config with a **cite-only ingress**:
  forward ONLY `/papers`, `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles`
  → `http://localhost:8080`; everything else → `http_status:404`. `<TUNNEL_ID>`/`<HOME>` placeholders (no secret
  committed; the user fills them after `cloudflared tunnel create`).
- **`tools/run_tunnel.py`** (new) — locates cloudflared (PATH or the winget install dir) + runs
  `cloudflared tunnel --config … run`; refuses while the config still has the `<TUNNEL_ID>` placeholder.
- **`adapters/googledocs/README.md`** (new) — the full setup runbook (Remote access token → add the Cloudflare
  subdomain zone → the two NS records at HostGator → `cloudflared login/create/route` → fill the config → run →
  `curl` verify), + the security notes.
- **cloudflared installed via winget** (`Cloudflare.cloudflared` 2026.5.2) — the permitted deploy.

## Key technical detail
- **Two boundaries:** the inc-168 **bearer token** is callosum's boundary (the app can't distinguish a tunnel
  request from the local browser — cloudflared forwards to localhost); the **cite-only ingress** is the tunnel's
  boundary. Cite-only can't be enforced inside callosum (it'd break the local UI), so it lives at the ingress.
- **Validated locally** (no Cloudflare account needed): `cloudflared tunnel --config … ingress validate` → OK; and
  per-URL `cloudflared tunnel --config … ingress rule <url>`:
  - `/papers`, `/papers/export`, `/citations/render-document`, `/citations/suggest`, `/citations/styles` → `http://localhost:8080` ✔
  - `/settings`, `/papers/5` (the `/papers/{id}` edit/delete path), `/` (app shell) → **404** ✔
- **GOTCHAs (carry forward):** HostGator jailshell blocks `ssh -R`; `cloudflared --config` goes **after** `tunnel`
  (`cloudflared tunnel --config <file> ingress validate`); winget's machine-PATH update doesn't reach an
  already-open shell (use the full `C:\Program Files (x86)\cloudflared\cloudflared.exe`).
- **No callosum code/endpoint/dependency/migration change** (cloudflared = external binary; this increment is config
  + a runner + docs); **no new API/FE surface** → surface map unchanged.

## Manual verification
- **Local (done):** cloudflared installed (2026.5.2); the cite-only ingress validated + per-URL routing proven
  (cite → localhost, everything else → 404), above.
- **Live (the user's, per README §6):** stand up the tunnel (Cloudflare account + the 2 NS records + login/create/
  route/run), then `curl https://callosum.clffwrkmn.net/papers?q=… -H "Authorization: Bearer <token>"` → JSON; no
  token → 401; `/settings` → 404. (Needs the user's Cloudflare account — not CI-verifiable.)

## Gates
- **Audit `.claude/security-audits/2026-06-28_googledocs-tunnel.md` PASS** (outbound-only; two boundaries; one
  delegated subdomain = minimal blast radius; no secret committed; egress is the user's opt-in, transits
  Cloudflare + Google).
- **Principles (rule #9):** the A-A consent value (explicit, opt-in, default-off egress; the user enabled it).
- **QA (rule #10):** no new API/FE surface (the tunnel reuses existing endpoints) → surface map unchanged.
- **Help corpus:** the inc-168 "Remote access" note already frames it; the README is the detailed setup.

## Pytest
**619** unchanged (config/docs/cloudflared — no Python app change; `ruff` clean on `tools/run_tunnel.py`).

## Next
**SP2 — the Apps Script Google Docs add-on** (`adapters/googledocs/`: `appsscript.json` + `Code.gs` + `sidebar.html`):
a sidebar; `UrlFetchApp` → `https://callosum.clffwrkmn.net` with the bearer token; citations as **NamedRange +
DocumentProperties** (the Zotero pattern), scanned in document order → `/citations/render-document` → write back;
reuses `/papers?q=` + `/papers/export` + `/citations/suggest` + `/citations/styles`. Manual-test-only (Google's
cloud). Then the user's live setup + the end-to-end check.
