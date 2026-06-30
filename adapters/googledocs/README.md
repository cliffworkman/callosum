# callosum — Google Docs cite-while-you-write (the bridge), SP1

Cite from your local callosum library inside **Google Docs**. A Docs add-on runs in Google's cloud and can't reach
your computer, so a small bridge exposes **only the citation endpoints** of your local callosum at a stable URL:

```
Google Docs add-on (Google cloud)
   │  HTTPS + your access token
   ▼
https://callosum-tunnel.clffwrkmn.net   ← Cloudflare edge (clffwrkmn.net's DNS on Cloudflare; existing records stay "DNS only" — site + email unchanged; only `callosum-tunnel` is proxied to the tunnel)
   │  cloudflared tunnel (runs on YOUR pc, outbound only — no inbound port)
   ▼
http://localhost:8080            ← your callosum, CITE-ONLY ingress + a bearer token
```

**Two boundaries keep this safe:** (1) the **access token** (Settings → Remote access) — callosum requires it on
every request; (2) the **cite-only ingress** — the tunnel forwards only `/papers`, `/papers/export`,
`/citations/render-document`, `/citations/suggest`, `/citations/styles`; everything else (your app, `/settings`, the
folder-scan routes, `/papers/{id}` edit/delete) returns **404** through the tunnel. Both are verified below.

> **Status:** SP1 (the bridge, steps 1–6) and SP2 (the Google Docs **add-on**, step 7) both ship. The bridge was
> verified live end-to-end (token gate + cite-only ingress); the in-Docs add-on glue is your manual check (it runs
> in Google's cloud).

---

## Easiest setup (Quick Tunnel — no Cloudflare account, no domain) — inc 193

If you just want to cite from Docs without the domain migration below, use a **Cloudflare Quick Tunnel** + the
**one-file add-on bundle**. Four steps:

1. **callosum:** run it, then **Settings → Remote access → ON**, copy the **token**.
2. **Tunnel:** `python tools/run_tunnel.py --quick --port 8888` (use your port). cloudflared prints a
   `https://<random>.trycloudflare.com` URL — copy it. (Leave it running; the URL changes each launch.)
3. **Add-on (one paste):** `python tools/build_gdocs_addon.py` writes **`adapters/googledocs/callosum-gdocs.gs`**.
   In a Google Doc → **Extensions → Apps Script** → select-all in `Code.gs` and **replace it with that one file** →
   Save → reload the Doc → **Extensions → Callosum → Open Callosum**.
4. **Connect:** in the sidebar's Connection settings paste the **trycloudflare URL** + your **token** → Save. Cite.

**Tradeoff vs. the named tunnel below:** the URL is throwaway (re-paste each session), and a quick tunnel can't
enforce the cite-only ingress allowlist — your **bearer token is the only boundary** (it already is the primary one;
keep it secret, turn Remote access off when done). For a **stable URL + cite-only ingress**, do the one-time setup
below instead. Either way, the one-file bundle (step 3) replaces the three-file paste in step 7.

---

## One-time setup (named tunnel — stable URL + cite-only ingress)

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
- Set `callosum-tunnel` (added in step 4) to **proxied (orange)** — only that subdomain goes through Cloudflare.

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
- **Copy** `adapters/googledocs/cloudflared-config.yml` → `adapters/googledocs/cloudflared-config.local.yml`
  (this `.local.yml` copy is **gitignored** — it holds your tunnel id, so it never gets committed; the committed
  `cloudflared-config.yml` stays a placeholder template). In the copy, replace `<TUNNEL_ID>` (both places) + the
  `credentials-file` path with the values above. `run_tunnel.py` automatically prefers the `.local.yml` copy.
- `cloudflared tunnel route dns callosum callosum-tunnel.clffwrkmn.net` → points the hostname at the tunnel.

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
curl -H "Authorization: Bearer <YOUR_TOKEN>" "https://callosum-tunnel.clffwrkmn.net/papers?q=test"     # → JSON

# no token → blocked:
curl "https://callosum-tunnel.clffwrkmn.net/papers?q=test"                                              # → 401

# non-cite path → blocked at the tunnel:
curl -H "Authorization: Bearer <YOUR_TOKEN>" "https://callosum-tunnel.clffwrkmn.net/settings"           # → 404
```

### 7. The Google Docs add-on (SP2)
The add-on lives in this folder: `Code.gs` + `gdocs_core.js` + `sidebar.html` + `appsscript.json`. It runs in
**Google's cloud** and reaches your local callosum through the bridge above — so the tunnel + callosum must be
running with **Remote access ON**.

**Install (bound to a document — no publishing needed):**

*Recommended (one paste):* `python tools/build_gdocs_addon.py` → bundles the three sources into
**`callosum-gdocs.gs`**. Open a Google Doc → **Extensions → Apps Script** → select-all in `Code.gs`, replace it with
that one file → Save → reload → **Extensions → Callosum → Open Callosum** (authorize on first run).

*Or, by hand (three files):*
1. Open a Google Doc → **Extensions → Apps Script**.
2. Add the files: paste `Code.gs` into the default `Code.gs`; **＋ → Script** named `gdocs_core` ← `gdocs_core.js`;
   **＋ → HTML** named `sidebar` ← `sidebar.html`. (Or push all four with
   [`clasp`](https://github.com/google/clasp): `clasp push` — `appsscript.json` carries the OAuth scopes.)
3. Save → reload the Doc → **Extensions → Callosum → Open Callosum** (authorize on first run).

**Use:**
- In the sidebar's **Connection settings**, enter `https://callosum-tunnel.clffwrkmn.net` + your access token → **Save**.
- Pick a **citation style**.
- **Search** your library → **Insert** at the cursor. Or **select a sentence** and **Suggest from selection** —
  the local engine ranks library papers to cite, each row showing its stance + a verbatim quote (the reason);
  Insert drops it *after* the selected sentence.
- **Refresh** renumbers every citation and rebuilds the **References** block; switching the style re-renders the
  whole document. **Flatten** turns the live citations into plain text (one-way) when you're done.

**What it sends:** only your search text + the cited works' metadata, to your bridge with your token — the same
cite endpoints the bridge allows (§6). Formatting happens server-side in citeproc; the add-on only places fields.

> **Verification reality:** the in-Docs glue (`Code.gs`) runs only in Google's cloud, so it ships
> best-effort-correct per the Apps Script docs; the request/response mapping it depends on lives in `gdocs_core.js`
> and is unit-tested (`node --test "adapters/googledocs/*.test.js"`). The in-Docs round-trip is your manual check.
>
> **v1 limit:** citations renumber in **insertion order** (reordering them by cut/paste isn't yet reflected on
> Refresh) — true document-order scanning is the remaining follow-up.

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
