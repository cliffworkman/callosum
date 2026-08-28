# Increment 510 — desktop Word can carry the Remote Access token too (real bug found live-testing inc 509)

## Implemented

While live-testing inc 509's composer, Cliff reported the citation-style dropdown empty in desktop Word.
Ctrl+F5, closing/reopening Word, and a full `%LOCALAPPDATA%\Microsoft\Office\16.0\Wef\` cache clear were all
tried first (the standard Office Add-in staleness fixes) — none helped, confirming it wasn't a caching issue.

**Root cause (confirmed via direct `curl` against the running `:8443` server, not guessed):**
`/citations/styles`, `/papers`, and every other real API call returned **401 "Remote access requires a valid
access token"** — because **Remote Access was still ON** from setting up the Word-on-the-web tunnel earlier
this session (inc 508), and `AccessControlMiddleware` (inc 168) gates every non-exempt endpoint once Remote
Access is on, **regardless of request origin** — including desktop Word's own same-origin
`https://localhost:8443` calls, which `taskpane.js` was designed to never send a token on. Not an inc-509
defect: the static files themselves served correctly (confirmed the served `taskpane.js` contained the new
composer functions); only the API calls were blocked.

Cliff confirmed the underlying scenario is a real, plausible one worth fixing properly rather than just
toggling Remote Access off: a Google Docs collaborator needing the tunnel on while he's using desktop Word at
the same time is entirely plausible, and today that's impossible without manually disabling Remote Access.

**A course-correction during design, not just implementation:** the first framing of "the real fix" (asked of
Cliff, and initially approved) was making `AccessControlMiddleware` trust loopback-originated requests. Reading
`access_control.py` before writing any code revealed this was already a known non-option — the file's own
docstring explains why: *"cloudflared forwards to `localhost`, so the app cannot tell a tunnel request from the
local browser (both are loopback, and the `Host` header is attacker-controllable) — therefore the token is the
only safe boundary for everything else, applied uniformly."* `cloudflared`'s local forward makes tunnel-relayed
traffic and genuinely-local traffic **indistinguishable at the TCP layer** — both arrive at the FastAPI server
as connections from 127.0.0.1. Trusting "loopback" would have silently reopened the exact hole the token gate
exists to close. This was surfaced back to Cliff (not silently built around) before any code was written, with
the safe alternative below proposed in its place.

**The actual fix — client-side only, zero security-boundary changes:** desktop Word's task pane can now *also*
carry the Bearer token when one is actually needed, reusing the exact same mechanism the Word-on-the-web/Google
Docs tunnel path already uses — just no longer gated behind `isTunneled`. `AccessControlMiddleware` itself is
**completely unchanged** — it stays exactly as strict as before, uniformly, for every origin. No new auth logic,
no security-audit stub needed (CLAUDE.md's audit gate triggers on new/changed auth logic; this reuses inc 168's
already-audited mechanism from a second UI entry point).

### Files

- `adapters/word/taskpane.js`:
  - `authToken()` — drops the `isTunneled` gate; always reads any saved token from `localStorage` (empty when
    none saved — identical no-op behavior to before for the common desktop-with-Remote-Access-off case).
  - `callosumFetch()` — new: after the response returns, if `r.status === 401`, calls the new
    `revealTokenSection(message)` (shows the token field + an explanatory status) instead of leaving whichever
    caller's own generic error as the only signal. Centralized in the one shared fetch wrapper every API call
    already goes through, so every caller (search, suggest, the composer, refresh, styles) gets this for free
    with no per-call-site changes.
  - `initTunnelSection()` — always pre-fills the token field from any prior save on this origin; still shows
    the section immediately, unconditionally, only when tunneled (Word-on-the-web needs it far more often).
  - `wire()` — the Save-token button binding is now unconditional (was `if (isTunneled)`), since desktop's
    revealed field needs it to work too.
  - Top-of-file doc comment updated to describe the real Remote-Access-coexistence scenario.
- `adapters/word/README.md` — new short note under "Word on the web" explaining the reveal-on-401 flow for
  anyone using desktop Word alongside an active tunnel.

**No changes to** `app/backend/api/access_control.py`, `app_settings.py`, or any other backend file.

## Key technical detail

Putting the 401-reveal logic inside `callosumFetch()` itself — rather than each caller's own try/catch — means
every existing call site (`loadStyles`, `search`, `suggestSentence`, `onPick`, `insertOrUpdateCitation`,
`refreshDocument`) gets the reveal automatically, even ones (like `loadStyles`) whose own error handling
silently swallows a failed request by design ("styles are optional polish"). The reveal fires as a side effect
of the shared wrapper before the caller's own `if (!r.ok)`/`catch` ever runs.

## Manual verification script

With Remote Access ON (as it already is on this machine from inc 508's tunnel setup): open desktop Word's task
pane, confirm the style dropdown is empty AND a revealed token field + explanatory message appear (not a silent
failure); paste the existing Remote Access token, Save; confirm styles populate and search/insert/suggest/
refresh/the inc-509 composer all work. Confirm Word-on-the-web is unaffected (same token flow as before).
Finally, with Remote Access OFF, confirm desktop shows no token section at all and needs no token (unchanged
from before inc 509/510) — this is the common case and must stay a true no-op.

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 19/19 passed (unchanged — this fix touches only
`taskpane.js`'s untested Office.js glue layer, per the project's documented "no headless Word" policy).
