# callosum — Google Docs cite-while-you-write (the bridge), SP1

Cite from your local callosum library inside **Google Docs**. A Docs add-on runs in Google's cloud and can't reach
your computer, so a small bridge exposes **only the citation endpoints** of your local callosum at a stable URL:

```
Google Docs add-on (Google cloud)
   │  HTTPS + your access token
   ▼
https://callosum.clffwrkmn.net   ← Cloudflare edge (clffwrkmn.net's DNS on Cloudflare; existing records stay "DNS only" — site + email unchanged; only `callosum` is proxied to the tunnel)
   │  cloudflared tunnel (runs on YOUR pc, outbound only — no inbound port)
   ▼
http://localhost:8080            ← your callosum, CITE-ONLY ingress + a bearer token
```

**Two boundaries keep this safe:** (1) the **access token** (Settings → Remote access) — callosum requires it on
every request; (2) the **cite-only ingress** — the tunnel forwards only `/papers`, `/papers/export`,
`/citations/render-document`, `/citations/suggest`, `/citations/styles`; everything else (your app, `/settings`, the
folder-scan routes, `/papers/{id}` edit/delete) returns **404** through the tunnel. Both are verified below.

> **Status:** SP1 (this) is the bridge. The actual Google Docs **add-on** is **SP2** (next) — until it ships you can
> still stand up + verify the tunnel with `curl` (Step 6).

---

## One-time setup

### 1. callosum: turn on Remote access + get your token
- Run callosum normally (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`).
- **Settings → Remote access (Google Docs) → toggle on.** Copy the **access token** (shown once).

### 2. Cloudflare: add the ROOT domain `clffwrkmn.net` (free)
> Cloudflare's free tier manages a whole domain (a subdomain-only zone is a paid Business feature). Done carefully
> this does **not** disrupt your HostGator website or email — Cloudflare just becomes the DNS host; existing records
> stay "DNS only" so nothing about how they resolve changes. It's fully reversible (switch the nameservers back).
- Create a free account at <https://dash.cloudflare.com> → **Add a domain** → enter **`clffwrkmn.net`** (the root) →
  **Free** plan → **Import DNS records automatically**.
- **Verify every record imported before continuing** (Cloudflare's scan occasionally misses TXT/DKIM). The current
  set (confirm each is present, then set the existing ones to "DNS only" = **grey cloud**, NOT proxied):
  - **A**: `@`, `www`, `mail`, `cpanel`, `ftp` → `50.87.149.75`
  - **MX**: `@` → `mail.clffwrkmn.net` (priority 0) — **`mail` must be grey/DNS-only** (Cloudflare can't proxy email)
  - **TXT** `@` (SPF): `v=spf1 +a +mx +ip4:50.87.144.47 +include:websitewelcome.com ~all`
  - **TXT** `default._domainkey` (**DKIM**): `v=DKIM1; k=rsa; p=MIIBIjAN…` — **paste the FULL value if it didn't import**
  - (no DMARC record currently — nothing to add)
- Set `callosum` (added in step 4) to **proxied (orange)** — only that subdomain goes through Cloudflare.

### 3. Switch nameservers (the actual cutover)
- Cloudflare shows you **two nameservers** (e.g. `xxx.ns.cloudflare.com`, `yyy.ns.cloudflare.com`).
- At your **registrar** (where clffwrkmn.net is registered — possibly HostGator's domain panel), replace the current
  nameservers (`ns6051.hostgator.com`, `ns6052.hostgator.com`) with Cloudflare's two.
- Wait for Cloudflare to email **"active"** (minutes to a few hours). Then **verify your site loads + send/receive a
  test email** before relying on it. (Reversible: set the nameservers back to HostGator's.)

### 4. cloudflared: create the tunnel
- Install (once): `winget install Cloudflare.cloudflared`
- `cloudflared login` → a browser opens; **authorize the `clffwrkmn.net` zone**.
- `cloudflared tunnel create callosum` → prints a **tunnel UUID** and a **credentials file path**
  (e.g. `C:\Users\<you>\.cloudflared\<UUID>.json`).
- Open **`adapters/googledocs/cloudflared-config.yml`** and replace `<TUNNEL_ID>` (both places) + the
  `credentials-file` path with those values.
- `cloudflared tunnel route dns callosum callosum.clffwrkmn.net` → points the hostname at the tunnel.

### 5. Run it
- Keep callosum running (uvicorn :8080, Remote access ON), then in another terminal:
  ```
  python tools/run_tunnel.py
  ```
  (equivalently: `cloudflared tunnel --config adapters/googledocs/cloudflared-config.yml run`). Leave it running
  while you cite; restart it whenever you want the bridge up.

### 6. Verify (cite-only + token-gated)
```
# search works WITH the token:
curl -H "Authorization: Bearer <YOUR_TOKEN>" "https://callosum.clffwrkmn.net/papers?q=test"     # → JSON

# no token → blocked:
curl "https://callosum.clffwrkmn.net/papers?q=test"                                              # → 401

# non-cite path → blocked at the tunnel:
curl -H "Authorization: Bearer <YOUR_TOKEN>" "https://callosum.clffwrkmn.net/settings"           # → 404
```

### 7. The add-on (SP2 — next)
Install the Callosum Google Docs add-on, paste **`https://callosum.clffwrkmn.net`** + your **access token** once,
then search your library and insert/refresh citations from the sidebar.

---

## Security notes
- **Outbound-only:** cloudflared dials out from your PC; no inbound port is opened on your machine or router.
- **Cite-only:** the ingress allowlist (`cloudflared-config.yml`) is validated by
  `cloudflared tunnel --config … ingress validate` + `ingress rule <url>` — only the five cite paths reach
  localhost; `/`, `/settings`, scan routes, and `/papers/{id}` return 404.
- **Token:** required by callosum on every request (constant-time check); shown once, stored locally, never returned
  by the API. Rotate it any time (Settings → Remote access → Regenerate) and update the add-on.
- **Egress:** with Remote access on, the cited-paper metadata in your requests transits Cloudflare's edge + Google's
  cloud — the explicit opt-in you made by enabling Remote access. Turn it off (or stop the tunnel) to close it.
- **Lockout recovery:** if you lose the token, `CALLOSUM_DISABLE_REMOTE_ACCESS=1` + restart, or remove it from
  `~/.callosum/app-settings.json`.

## Credit
The bridge is **Cloudflare Tunnel** (`cloudflared`). The add-on's live-citation design (SP2) reuses the Zotero
`CSL_CITATION` embedded-CSL-JSON pattern — see the project's `THIRD-PARTY-NOTICES.md`.
