# Increment 193 — Google Docs setup automation: Quick Tunnel + one-file add-on bundle

The Google Docs install was "migrate a domain + paste three Apps Script files" — too much for an end user. Two of
the steps are Google's platform constraints (a cloud add-on can't reach localhost → a bridge must exist; Google has
no "install a local add-on" button short of Marketplace publishing). The rest was setup tax — this increment cuts it.
User-approved scope: **both** (quick-tunnel mode + the one-file bundle).

## Implemented

- **`tools/run_tunnel.py --quick [--port N]`** (default 8080): runs a **Cloudflare Quick Tunnel**
  (`cloudflared tunnel --url http://localhost:<port>`) — **zero setup** (no account, no domain migration, no
  nameserver cutover, no `tunnel create`/`route dns`, no config). cloudflared prints a throwaway
  `https://<random>.trycloudflare.com` URL the user pastes into the add-on. The named-tunnel mode (stable URL +
  cite-only ingress) stays the default/no-flag path. Argparse; the runner prints the security tradeoff up front.
- **`tools/build_gdocs_addon.py`** → **`adapters/googledocs/callosum-gdocs.gs`** (committed): concatenates the three
  Apps Script sources — `gdocs_core.js` + `Code.gs` + `sidebar.html` — into **one** file the user pastes once. The
  sidebar HTML is inlined as a JSON-encoded JS string served via `HtmlService.createHtmlOutput(_callosumSidebarHtml())`
  (replacing `createHtmlOutputFromFile("sidebar")`), since Apps Script's one global scope makes `gdocs_core`'s
  `globalThis.CallosumCore` visible to `Code.gs`. Install drops from 3 files + naming → "replace Code.gs with this one
  file."
- **`adapters/googledocs/README.md`**: a new **"Easiest setup (Quick Tunnel — no Cloudflare account)"** section leads
  with the 4-step easy path (callosum+token → `--quick` tunnel → build the bundle → paste URL+token); the named-tunnel
  setup is retitled the "stable URL + cite-only ingress" alternative; step 7 leads with the one-paste bundle.

## Key technical detail

- **Quick tunnel = the big UX win, with one posture tradeoff:** a quick tunnel takes no ingress config, so it can't
  enforce the cite-only allowlist → the **bearer token is the sole boundary** (already the primary one; cite-only was
  defense-in-depth). It's opt-in + non-default + token-gated + informed (the runner prints the tradeoff); the
  cite-only named path remains for a hardened setup. (Audit addendum below.)
- **The bundle is drift-safe:** generated from the three sources; `tests/test_gdocs_bundle.py` re-runs the builder and
  asserts the committed `.gs` matches (mirrors `test_frontend_assembly`). `node --check` (as `.js`) confirms it's valid
  JS; the inlined-sidebar + `CallosumCore` markers are asserted.

## Manual verification script

`python tools/build_gdocs_addon.py` → `callosum-gdocs.gs` (node-checks as valid JS; 28 `CallosumCore` refs, the
`_callosumSidebarHtml()` inline-sidebar fn, 0 leftover `createHtmlOutputFromFile`). `python tools/run_tunnel.py --help`
shows `--quick`/`--port`. The **real** quick-tunnel + in-Docs round-trip is the user's manual check (it needs live
cloudflared egress + Google's cloud — un-automatable from the repo, same as the named tunnel).

## Gates

- **pytest 656** (+2 `tests/test_gdocs_bundle.py`: bundle-in-sync + inlines-core-and-sidebar). `ruff` check +
  `format --check` clean.
- **Audit:** addendum to `.claude/security-audits/2026-06-28_googledocs-tunnel.md` **PASS** — the `--quick` mode is an
  opt-in, token-gated, informed-consent convenience mode that drops the cite-only ingress (documented; named path
  remains). The bundle is not a security change (same code, one paste). **A-A consent value** honored (explicit,
  non-default, informed).
- **QA (rule #10):** no new API/FE surface (a `tools/` launcher option + an adapter bundle file) → surface map
  unchanged (132 API / 657 FE). No help-corpus change (this is dev/setup tooling, not in-app behavior).
- **No app code, no frontend, no migration, no new dependency** (cloudflared already required).

## Limits / future

- True one-click "install from the Workspace Marketplace" is the only thing the bundle/quick-tunnel can't replace —
  it needs Google Marketplace publishing (a GCP project, OAuth verification, a privacy policy, Google review); a big
  separate effort, deliberately not taken for a local-first single-user tool.
- An app-level "cite-only when remote" mode (to restore the allowlist under a quick tunnel) is deferred — the app
  can't distinguish tunnel vs. local requests (inc-168 loopback-indistinguishability).
