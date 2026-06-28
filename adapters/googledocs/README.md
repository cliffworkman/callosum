# callosum — Google Docs cite-while-you-write (the bridge), SP1

Cite from your local callosum library inside **Google Docs**. A Docs add-on runs in Google's cloud and can't reach
your computer, so a small bridge exposes **only the citation endpoints** of your local callosum at a stable URL:

```
Google Docs add-on (Google cloud)
   │  HTTPS + your access token
   ▼
https://callosum.clffwrkmn.net   ← Cloudflare edge (a subdomain you delegate; the rest of clffwrkmn.net is untouched)
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

### 2. Cloudflare: add `callosum.clffwrkmn.net` as a delegated subdomain zone (free)
- Create a free account at <https://dash.cloudflare.com>.
- **Add a domain** → enter **`callosum.clffwrkmn.net`** (the subdomain, not `clffwrkmn.net`) → choose the **Free**
  plan. Cloudflare creates a zone for just that subdomain and shows you **two nameservers**
  (e.g. `xavier.ns.cloudflare.com`, `dana.ns.cloudflare.com`).

### 3. HostGator: delegate ONLY the subdomain (this is the only change to clffwrkmn.net)
- HostGator cPanel → **Zone Editor** → manage `clffwrkmn.net` → **Add Record** ×2, type **NS**:
  - Name `callosum` (→ `callosum.clffwrkmn.net`), NS = the **first** Cloudflare nameserver.
  - Name `callosum`, NS = the **second** Cloudflare nameserver.
- Nothing else in clffwrkmn.net changes; your website + email keep working.
- Verify (wait a few minutes): `nslookup -type=ns callosum.clffwrkmn.net` → the Cloudflare nameservers.

### 4. cloudflared: create the tunnel
- Install (once): `winget install Cloudflare.cloudflared`
- `cloudflared login` → a browser opens; **authorize the `callosum.clffwrkmn.net` zone**.
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
