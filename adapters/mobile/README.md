# Reading your callosum library on your phone (B5, inc 237)

callosum's UI is **responsive** — open it on a phone-width screen and it collapses to a single column with a bottom
nav (**Library · Panels · Details**). You browse the library, open a paper (metadata + abstract + the PDF, rendered
by your phone's own viewer) and read its verified syntheses. This is a **read-only** companion: you can't scan,
import, edit, tag, or delete from the phone — reading only.

You reach it over a **cloudflared tunnel** (the same outbound-only bridge the Google Docs add-on uses), with **two
boundaries** that together make it read-only:

1. **The method gate — `CALLOSUM_READ_ONLY=1`** (the real boundary). The tunnel-facing callosum, run with this env
   var, returns **403** for every mutating request (anything but GET/HEAD/OPTIONS). A path like `/papers/5` serves a
   GET read *and* a DELETE write, and cloudflared can only filter by path — so the method gate is what actually
   blocks writes.
2. **The read-only ingress allowlist** (defense in depth). The tunnel forwards only the read paths (`/`, `/papers`,
   `/papers/{id}`, `/papers/{id}/pdf`, `/summaries*`, `/help/corpus`); `/settings`, the scan/import routes, `/axes`,
   `/tags` are **404** at the tunnel — never reachable.

Plus the **bearer token** (Settings → Remote access) gates all access, as always.

## Recommended: a second, read-only instance

Run a **second callosum instance** just for the tunnel, pointed at your library DB, in read-only mode — your desktop
instance stays fully read-write, and the phone reads the same library (SQLite WAL handles concurrent readers):

```
# in a second terminal
$env:CALLOSUM_READ_ONLY = "1"
$env:CALLOSUM_DB_URL    = "sqlite:///C:/…/your/library.sqlite"   # your real DB
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Then in that instance's Settings → **Remote access**: enable it and mint an access token (you'll enter the token on
the phone the first time it loads over the tunnel).

## The tunnel

1. **Install cloudflared** once: `winget install Cloudflare.cloudflared`.
2. **Set up the tunnel** exactly as in [`../googledocs/README.md`](../googledocs/README.md) (Cloudflare account +
   your domain on Cloudflare, `cloudflared login` / `tunnel create callosum` / `route dns`). Use a distinct hostname,
   e.g. `callosum-mobile.clffwrkmn.net`.
3. **Fill the config:** copy `cloudflared-config.yml` → `cloudflared-config.local.yml` (in this folder, gitignored)
   and set your `<TUNNEL_ID>` + credentials path + hostname.
4. **Run it:** `python tools/run_tunnel.py --mobile` (it prefers your `.local.yml` and reminds you to set
   `CALLOSUM_READ_ONLY=1`).
5. **On your phone:** open `https://callosum-mobile.clffwrkmn.net`, enter your access token when prompted, and read.

### Quick path (no domain)

`python tools/run_tunnel.py --quick --mobile` gives a throwaway `trycloudflare.com` URL with **zero setup** — but a
Quick Tunnel can't enforce the ingress allowlist, so the **method gate (`CALLOSUM_READ_ONLY=1`) + the token** are then
your only boundaries. Keep the token secret and stop the tunnel when you're done.
