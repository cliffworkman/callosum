# Admin-gated plugins — design doc (backlog #41)

**Status:** scoping conversation, foundation-only build authorized. The plugin system itself
(data model, loader, sandbox, review pipeline, store) is **not** being built now — this doc
records the vision, the open questions that block it, and what a small, honest first slice
looks like: an admin-gated toggle that does nothing observable yet.

**Source:** `.claude/docs/future-tracks/opus4.8_future-tracks_plugins.md` (the original
deferral record — its own "record-and-mark" task was never actually completed; this doc
supersedes it) + a scoping conversation with Cliff, 2026-08-18/19.

---

## The idea

Let users author and add their own THEORY/METHODS panel modules — and, by extension, new
*source providers* (a new bibliographic database, a new preprint server, etc.) — so the tools
callosum ships are a starting point, not a ceiling.

**Confirmed scope for this design pass:** modules are genuinely **third-party** — written and
distributed by people other than the maintainer, not just the maintainer's own future
first-party additions (which already ship through the internal registries, no plugin system
needed). This is the harder case the source doc itself flagged as maybe not shippable — see
"The crux" below.

## The motivation

The anti-foisting principle: defaults and prioritization should be the user's, not one
curator's (or one AI's) view of what matters — an extensible tool avoids imposing that. This is
a genuine extension of an already-revealed value, not an invented one: see
`.claude/APPROACH-AVOIDANCE.md` A1 ("the user's judgment is the product; the tool's is not")
and A8 (access/equity — a shipped tool's fixed feature set is itself a kind of gatekeeping).

## The distribution model (new in this scoping pass)

Cliff's own framing: **a curated plugin "store," not an open marketplace.** Plugins are
evaluated before being made available to download inside callosum — closer to how the VS Code
Marketplace or the Chrome Web Store combine *human/automated review* with *technical limits*,
not a Sci-Hub-style "anyone publishes, users beware" model. This materially changes the trust
calculus versus the source doc's original framing (which only considered technical sandboxing
in isolation): a review gate is a real, additional layer of defense, though — same as browser
extension stores — it is not a substitute for technical limits, since review is imperfect and
can be gamed. Both layers are needed; neither alone is sufficient.

## Module-kind decomposition (new in this scoping pass)

The source doc named two different things under one word, "modules." They have different
capability needs and should not be designed as one problem:

1. **THEORY/METHODS panel modules** — an analysis/display layer. Mostly needs to render UI and
   read data already in callosum (papers, findings, chunks). Doesn't inherently need its own
   network access. **Narrower, more tractable trust problem** — closer to browser-extension/
   VS-Code-webview "run untrusted UI code safely," which has real, working prior art.
2. **Source providers** — a data-fetching layer (a plugin that adds a new external database/
   feed to search or follow). Inherently needs outbound network access — a fundamentally
   different, **egress-centric** trust problem: does a third-party module's own network calls
   bypass the egress gate (invariant #3 / A5)? Who's accountable for what it sends?

**Decision: sequence, don't solve simultaneously.** Panel modules first (once this design
resumes beyond the foundation stage); source providers explicitly later, once the panel-module
trust model is proven. Trying to design one sandbox/review model that fits both well would
likely produce a worse answer for each.

## The three blocking open questions (from the source doc, sharpened here)

### (a) Code execution / sandboxing
A third-party module runs in-process and renders in callosum's own panes. Unresolved in
general — but scoping to **panel modules first** narrows it: if a panel module never needs its
own network access or arbitrary backend code execution, the sandboxing question shrinks from
"how do we safely run untrusted Python in our own server process" (very hard — no real sandbox
exists for that without heavy infra: containers, WASM, a subprocess with strict OS permissions)
to "how do we safely run untrusted JS in a browser context" (real, working prior art: iframe +
strict CSP + `postMessage`-only communication + no direct DOM access to the host page, the
shape VS Code webviews, Figma plugins, and browser extensions already use). **Still not solved,
but the panel-modules-first sequencing makes it a tractable problem instead of an open-ended one.**

### (b) Principle enforcement — the crux
Can the module contract *enforce* `PRINCIPLES.md`/`APPROACH-AVOIDANCE.md` (require fact/
candidate declarations, forbid opaque scores and freelance verdicts), or can it only enforce
output *shape* and trust the rest? The source doc's own words: unresolved, and a system that
can't guarantee its modules behave "may not be shippable" for third-party code at all.

**A concrete direction worth writing down now** (not building — this is what the *next* design
pass should evaluate first), surfaced by running the A-A gate on this conversation: rather than
letting a panel module render arbitrary UI — which cannot be technically prevented from
violating Part II's "no opaque composite score, no AI output as authority" refusal — **constrain
a panel module to emit typed fact/candidate data**, in the same shape the existing
`paper_findings`/`wip_findings` schema already uses (`kind: "fact"|"candidate"`, a `payload`,
review state), and let callosum's own already-trusted `FindingCard`-style components do *all*
the rendering. The plugin never gets a raw canvas — it emits data, callosum decides how
confidence/uncertainty/candidacy get shown.

This is attractive because it partially answers **both** open questions at once:
- **Sandboxing shrinks further**: a module that only emits typed JSON doesn't need arbitrary
  DOM access at all — even less surface than a generic "run untrusted JS" problem.
- **Principle enforcement shifts from unverifiable to reviewable**: the review-store process
  doesn't need to prove a module's *rendering* behaves (it can't render anything on its own) —
  it only needs to check the module's *data claims* are honestly fact-vs-candidate labeled,
  which a human reviewer reading the module's code and its actual outputs against known test
  documents can meaningfully assess. This is exactly the kind of review that already works for
  browser-extension stores (automated checks + human review), applied to a narrower, more
  legible contract than "arbitrary code."

This does **not** fully resolve (b) — a module could still lie about what its data means, or a
reviewer could miss something — but it converts an open-ended "can we prove arbitrary code
behaves" question into a bounded "can we review a typed data contract" question, which is a
real, meaningful narrowing worth recording before it's lost.

### (c) Trusted vs. untrusted
Cliff's own future first-party modules (already served by the internal registries, additive, no
new trust question) and genuinely third-party store-reviewed modules are different problems and
must stay structurally separate — first-party built-ins should never be forced through
whatever review/sandbox machinery third-party modules eventually need, and the reverse: a
third-party module should never get first-party-equivalent trust just because it's listed in
the store. Confirmed unchanged by this scoping pass; the panel-modules-first sequencing doesn't
weaken this separation.

## Existing extension-point seams (a real finding this pass — the source doc assumed some of
## these didn't exist yet; they do)

- **Panel modules** → `registerPaneTab` (`app/frontend/js/05_panes.jsx`) — the existing internal
  registry every built-in Methods/Checklists/WIP-panel tool already goes through.
- **Source providers** → the source doc said "the SourceProvider registry once it exists" — it
  now does: `FeedSource`/`FeedRegistry` (`app/backend/discovery/feed.py`, built for the
  literature Feed, backlog #28 SP2, inc 187+), which the module's own docstring says "mirrors
  the Search SourceRegistry + the acquisition-resolver registry" — i.e. there are likely
  **three** existing internal registries sharing this same `register()`-a-`Protocol`-dataclass
  shape, all candidate seams for a future source-provider plugin. Their exact files weren't all
  individually confirmed in this pass (worth doing before the source-provider design phase, not
  now).

Each of these seams gets a short marker comment (this pass's Section 2 below) — **a comment
only**, no loader, no contract, nothing that changes behavior.

## What this pass actually builds (the foundation)

Per Cliff's explicit steer: narrowest possible slice. **A settings toggle that does nothing
observable when turned on, plus this design record, plus registry-seam markers.** No plugin
data model, no loader, no sandbox, no store, no review pipeline — all of that stays open,
recorded above, for a future design pass to resume from (this doc, not a blank slate).

1. **`app/backend/app_settings.py`** — `set_plugins_enabled(enabled: bool)` /
   `stored_plugins_enabled() -> bool`, mirroring `agent_writes_enabled`/`remote_access_enabled`
   exactly: default `False`, plus a `CALLOSUM_DISABLE_PLUGINS` env-var recovery hatch (the same
   defense-in-depth pattern every other gate uses, established now even though nothing yet
   depends on it — establishing the right pattern early costs nothing and avoids a later
   "the recovery hatch doesn't exist for this one" gap).
2. **`app/backend/api/routers/settings.py`** — add `plugins_enabled` to the `GET /settings`
   response model, the `PUT /settings` update model, the read, and the write — identical shape
   to `agent_writes_enabled`'s four touch points.
3. **`app/frontend/js/35_settings.jsx`** — a new, plainly-labeled "Plugins" section (not folded
   into any "Advanced" grouping — none exists today, and every other gate gets its own clear
   section). Copy is explicit that enabling it does nothing observable yet: foundation for a
   future curated plugin store, not a working feature. No download/install UI of any kind.
4. **Registry-seam markers** — a short comment at `registerPaneTab`
   (`app/frontend/js/05_panes.jsx`) and at `build_default_feed_registry()`'s `.register(...)`
   chain (`app/backend/discovery/feed.py`, ~lines 110-121), noting each as the intended future
   extension point for user-authored modules, that user-facing plugins are **deferred** pending
   this design doc's open questions, and that no plugin-loading is to be added without resolving
   them.
5. **This design doc** replaces the future-track file's own stale "record-and-mark" task
   (never completed) as the live reference — the future-track file gets a short pointer to here
   rather than staying the sole record.

## What is explicitly NOT built now

No plugin data model/table. No loader. No sandbox (browser or otherwise). No review/store
pipeline. No third-party code ever executes. No new attack surface beyond a boolean flag that,
today, controls nothing — this is a deliberate, honest "the switch exists, nothing is wired to
it yet" foundation, not a feature with hidden scope.

## Principles / A-A gate (rule #9 — run in full, this being novel/value-level work)

**Principles touched:** #2 (signal not verdict), #5 (the human is the filter, the AI/module is
the funnel), #7 (no opaque composite scores), #8 (inspectability over authority). No existing
PRINCIPLES.md worked example fits directly — this is genuinely novel, which is exactly the case
`APPROACH-AVOIDANCE.md` exists for.

**A-A values touched:** A1 (user's judgment is the product), A2 (a claim is earned against its
source — can a third-party module's output even meet this bar without callosum's own
verification infrastructure?), A3 + Part II's explicit "no opaque composite score, no AI output
as authority" refusal, A6 (deterministic, inspectable mechanism first), A8 (access/equity — the
generative motivation). Part III's own "Divergent" section already names this exact risk:
*"the scoring temptation vs. no-opaque-score... a divergence risk, fenced by PRINCIPLES' worked
examples — keep watching it."* A third-party plugin author has none of that fencing unless the
contract structurally enforces it.

**Misalignment this is most at risk of:** the easy, demo-friendly version is "let modules render
whatever HTML they want" — fast to build, immediately flexible, and structurally unable to
guarantee no opaque score, no unearned authority, no hidden uncertainty ever ships inside
callosum's own trusted UI chrome.

**Aligned alternative proposed** (for the *next* design phase, not built now): the typed
fact/candidate data contract described under open question (b) above — a module emits data,
callosum's own trusted components render it. This is the "propose what could be right" half of
the gate, recorded so the next phase starts from a real direction instead of a blank page.

**This pass's own actual build (the toggle) does not itself violate anything** — it gates a
capability that, right now, does not exist. The gate's job here was to make sure the *next*
phase inherits a real, evidence-linked starting point rather than rediscovering these tensions
from scratch — which is what actually happened once before (the original future-track task's
own findings were never carried forward into a live design doc).

## Testing / verification

The toggle itself: unit-test the setter/getter pair (mirrors the existing
`test_access_control.py`-style coverage for `agent_writes_enabled`/`remote_access_enabled`) and
the `/settings` GET/PUT round-trip. Frontend: confirm the section renders, toggles, and persists
across reload — no new Playwright/manual-verification burden beyond what any other Settings
toggle already gets, since nothing else changes behavior.

No security audit is triggered by the toggle alone under CLAUDE.md's own audit-gate criteria (no
new endpoint's *behavior* changes beyond a boolean field on an existing endpoint, no new
external fetch, no new file-ingestion path, no new auth logic, well under the 300-LOC/3-file
"net-new feature" threshold) — but the **next** phase (any actual loader/sandbox/review-store
work) absolutely will trigger it, likely several times over, given the surface it touches.
