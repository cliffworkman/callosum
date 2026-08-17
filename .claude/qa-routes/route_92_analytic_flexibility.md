<!-- qa-coverage
api: POST /papers/{paper_id}/analytic-flexibility, POST /wip/manuscripts/{manuscript_id}/checks/analytic-flexibility, GET /papers/{paper_id}/findings, POST /findings/{finding_id}/review, PATCH /wip/findings/{finding_id}
api: POST /manuscripts/{manuscript_id}/checks/analytic-flexibility
fe: 08n_methods_analytic_flexibility.jsx, 10k_wip_checks.jsx, 04c_status.jsx, 08x_methods_critical.jsx
-->

# ROUTE 92 - Analytic-flexibility surfacing (backlog #37, LLM-assisted Checklists tool)

**Tier:** 2 local-stateful + egress-gated
**Goal:** Exhaust analytic-flexibility surfacing on both the Library Methods -> Checklists panel and the WIP Checks
tab while preserving the load-bearing postures unique to this feature: the model only ever proposes a bare
`{category, quote}` pair -- it never asserts a location, page, or confidence; a local, deterministic
`anchor_quote`/`locate_quote` call independently decides exact/region/unanchored (invariant #2, extended to a
brand-new LLM-assisted surface); the category is drawn from a **closed, five-value taxonomy**
(`exclusion-criteria` / `covariate-choice` / `test-selection` / `outcome-choice` / `other-branch-point`) and
anything else is dropped server-side, never coerced or invented; **no aggregate, count, percentile, or
"flexibility level" ever renders anywhere on either panel** -- this is the single most load-bearing invariant
unique to this feature; a WIP finding whose local anchor comes back `unanchored` is persisted with
`coordinate_precision: NULL` (the `wip_findings` CHECK constraint has no `'unanchored'` literal), with the fuller
`anchor_state` still inspectable in `details_json`; and the WIP-side PDF-vs-non-PDF methods-section-scoping
asymmetry is disclosed in the run's own result text (`scoped: false`), never silently presented as equivalent
coverage to real per-block scoping. Every trigger on both surfaces is an explicit button click -- unlike its
deterministic Checklists siblings (transparency/LMM/Bayesian/meta-analysis), analytic-flexibility is LLM-assisted
and egress-gated, so **nothing here auto-runs**, ever, on either surface.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** unless a step explicitly says otherwise.
Register listeners before navigation.

**No app-level fake-injection seam exists for this feature.** Unlike several other Tier-2 routes (which lean on
`create_app(summary_generator=..., extraction_assistant=..., ...)` constructor injection), both
`routers/analytic_flexibility.py` and `routers/wip_checks.py` construct `GeminiConfig.from_environment()` and
instantiate `AnalyticFlexibilityAssistant(config)` directly inline -- there is no `create_app(...)` parameter for
this assistant to override. The verified hermetic-by-default technique is instead the same one GROBID (route 91)
and the Meta-Analyze assisted-extraction funnel (route 65) already establish: **configure a loopback provider.**
`requires_egress()` returns `False` for any loopback `base_url` regardless of the `data_egress_enabled` toggle
(invariant #3's endpoint-based rule) -- so a request to a provider whose `base_url` is `127.0.0.1`/`localhost`
makes **zero real network egress**, never touches a real cloud host, and needs no consent on the backend. Stand
up a small local stub HTTP server on any free `127.0.0.1` port that answers a chat-completions-shaped POST with a
fixed JSON body wrapping `[{"category": "...", "quote": "..."}]` as the assistant's own `parse_proposals` expects
(plain JSON, or fenced in ```` ```...``` ````, or with surrounding prose -- see
`integrations/gemini/analytic_flexibility_assistant.py::_loads_lenient`). In Settings -> AI features, either edit
the builtin **Local** provider's base URL (default `http://localhost:11434`) to point at your stub, or add a
custom provider with a loopback `base_url` and `wire_format: chat_completions`, then make it the active provider.

**Toggle "Data egress consent" ON in Settings anyway**, even for the loopback provider. Both Checklists surfaces'
frontend gates its own button purely on `GET /settings`'s `data_egress_enabled` flag
(`08n_methods_analytic_flexibility.jsx`'s `aiReady`) -- more conservatively than the backend actually requires for
a loopback provider. This is not dishonest (the button's own copy literally says "Enable AI features in Settings
(data-egress consent)"), just stricter than the backend needs; note it if you hit it, don't file it as a
contradiction.

Reserve a **real** cloud provider (Gemini/OpenAI/Anthropic with a real key + `CALLOSUM_ALLOW_DATA_EGRESS=1`) for
an explicit, separate integration pass only. Never use one by default in a QA run, and never send real
library/manuscript text to a real cloud host from QA (route 65's own rule for its own funnel, reused here).

## Seed contract

`_seed_library`'s three default papers (`_TEMPLATE.md` -> Seed contract) carry **no `chunks.section` value at
all** (confirmed by reading `tests/api_helpers.py`) -- every one of them will honestly report
`methods_text_found: false` from `paper_methods_text()` with **zero extra setup**. This directly exercises the
"no methods-section chunks at all" adversarial case; don't build a fixture for it.

To reach the positive candidate/anchor path (needed for Step 4's exact-anchor regression check, Task 8's fix),
mutate the **Renderable Seed Paper**'s own page-1 chunk directly in the disposable DB -- safe, the fixture
contract makes the seeded DB disposable/mutable:

```sql
UPDATE chunks SET section = 'methods'
WHERE paper_id = <renderable_paper_id> AND page_start = 1;
```

That chunk's attachment role is `"primary"`, which normalizes to `article-fulltext` at read time (inc 425), so
it is eligible for `get_chunks_for_paper`'s `ARTICLE_AND_SUPPLEMENT_DOCUMENT_ROLES` filter, and its real text
("Facial anomalies influence social judgments in observers.") genuinely exists on the real on-disk
`tests/fixtures/seed.pdf` at the documented bbox. Configure the stub provider to echo that exact string back as
the proposed `quote` (any valid category) -- `anchor_quote` will then find a real match in a real PDF, producing
a genuine `exact` anchor. Do not mutate Facial Anomaly Perception's or Signal Detection Theory's chunks -- the
base seed contract already reserves the Renderable Seed Paper for exactly this kind of coordinate-honesty check.

`_seed_library` creates **no WIP manuscript at all** (confirmed; WIP manuscripts only exist via the watch-root
scan mechanism -- `route_75_wip_workspace.md`'s own Environment). Create two throwaway folders, register them as
watch roots (`POST /wip/watch-roots`, "folder-as-manuscript" mode), rescan, and mark each one's primary file:

- **Manuscript A (non-PDF, exercises `scoped: true`).** One `.html` file with a real `<h1>Methods</h1>` (or
  `<h2>`) heading followed by a decision-point-shaped paragraph (e.g. "Participants under 18 were excluded from
  analysis."). `.html`/`.htm`/`.xml`/`.jats`/`.odt` are the confirmed per-block-section-carrying formats
  (`app/backend/wip/analytic_flexibility_text.py`'s own docstring).
- **Manuscript B (PDF, exercises `scoped: false`).** One real, parseable `.pdf` (a copy of
  `tests/fixtures/seed.pdf` is fine) with any prose in it. PDF blocks always carry `section: None`
  (`app/backend/wip/content.py`), so this manuscript's run must honestly degrade to the whole-file search.

Configure the same loopback stub provider for both WIP runs.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate (Critical, invariant #3).** With the active provider loopback: zero refusal, zero real outbound
  request captured by the request listener. With the active provider non-loopback/cloud and `data_egress_enabled`
  false: **both** `POST /papers/{id}/analytic-flexibility` and `POST /wip/manuscripts/{id}/checks/analytic-flexibility`
  return **403** with the exact detail `"Analytic-flexibility surfacing requires explicit data-egress consent
  (Settings -> AI features)."`, **before** any paper/manuscript-existence check (the gate must win even against a
  nonexistent id -- a 404 instead of 403 there is a bug, mirroring GROBID/route 91's own ordering rule), and the
  configured cloud host is never contacted.
- **The model never asserts location (Critical).** Every persisted candidate's `page`/`bbox_json`/`anchor_state`
  comes from the local `anchor_quote` call, never from the model's own response -- the stub server never receives
  or returns a page/confidence/location field the app could have used; verify by inspecting what the stub
  actually received/returned versus what got persisted.
- **No aggregate, anywhere (Critical).** Neither panel ever shows a count, tally, percentile, or "flexibility
  level" as a standalone badge/chip/score widget -- not next to the panel title, not in the Status entry, not as
  part of the button. (A plain sentence stating what happened, e.g. a WIP run's own
  `result_summary` = "N candidate decision points surfaced from the methods section," is prose, not a score
  widget -- the assertion is about a badge/score UI element, not about the word "N" ever appearing in a sentence.)
- **Closed taxonomy (Critical).** Configure the stub to return one item with an invalid/unlisted category (e.g.
  `"category": "researcher-bias"`) alongside one item with a valid category. Confirm only the valid one is ever
  persisted or rendered -- the invalid one is dropped server-side (`parse_proposals`,
  `integrations/gemini/analytic_flexibility_assistant.py`) and never appears as a 6th, made-up category label
  anywhere in the UI.
- **Coordinate honesty, extended (Critical).** An exact-anchored candidate's "show in paper · p.N" link draws a
  **real** highlighted bbox rectangle -- Task 8's fix (`08x_methods_critical.jsx`'s `FindingCard` reading the
  candidate's real `payload.anchor_state === "exact"` instead of a hardcoded region). A quote the model returns
  that cannot be located in the source text produces `anchor_state: "unanchored"`, `page: null` -- confirm **no**
  "show in paper" link renders at all for that candidate (the link is conditioned on `page != null`). On the WIP
  side, that same unanchored candidate's persisted `wip_findings.coordinate_precision` is **NULL** -- never the
  literal string `"unanchored"` (the CHECK constraint has no such literal; confirmed in
  `wip_checks_repo.py::store_analytic_flexibility_run`) -- while `details_json.anchor_state` still honestly says
  `"unanchored"` when inspected directly via the API response.
- **PDF-vs-non-PDF WIP scoping disclosure (High).** Manuscript A's run reports `scoped: true` in
  `structured_result_json` and shows **no** degrade caveat. Manuscript B's run reports `scoped: false` and the
  `WipAnalyticFlexibilityResult` caveat ("This file type has no per-block section scoping, so the whole
  manuscript text was searched rather than just its methods section.") renders -- confirm the live wording rather
  than assuming it matches this description verbatim.
- **Status findability (invariant #5).** Both endpoints' Status popover entries appear while running, labeled
  exactly **"Provider AI + local anchoring"** (`04c_status.jsx`'s `TRACKED_AI_REQUESTS`). The Library entry's nav
  carries the real `paper_id`; the WIP entry's nav carries the real `manuscript_id` (injected by
  `_startTrackedApiOperation`'s regex match against `/^\/wip\/manuscripts\/(\d+)\//`) -- confirm each entry clicks
  back to the correct paper/manuscript, not just a bare "Library" landing.
- **Facts vs. candidates (High, PRINCIPLES.md's human-filter/AI-funnel).** Every surfaced item is
  `kind: "candidate", tier: "speculative"` -- never a fact -- reviewable via **Confirmed** / **Accepted…** /
  **Noted** on the Library side (`POST /findings/{id}/review`) or the seven-state disposition select on the WIP
  side (`PATCH /wip/findings/{id}`: `open`/`acknowledged`/`resolved`/`dismissed`/`false-positive`/`deferred`/
  `superseded`, the same generic vocabulary every other WIP Checklists tool already uses). The two vocabularies
  are **deliberately different** across the two surfaces -- that is not a bug to file.
- **No LLM call on the honest "nothing to surface" path (Medium+).** Running against a paper/manuscript with no
  methods text never calls the assistant at all (`propose_analytic_flexibility`/`analytic_flexibility_run` both
  short-circuit before constructing `AnalyticFlexibilityAssistant` when there's no text) -- confirm via the stub
  server's own request log staying empty for that specific run.

## Adversarial checklist

- A paper/manuscript with no methods-section chunks/blocks at all -> the honest "nothing to surface" state
  (Library: "No methods-section text was found to check…"; WIP: "No manuscript text was found; nothing to
  surface." or "No methods-section text was found in the primary manuscript file; nothing to surface."), never an
  empty list indistinguishable from "checked, found none."
- A quote the stub returns that is real prose but **not** a verbatim substring anywhere in the source text ->
  `parse_proposals` still structurally accepts it (only `anchor_quote` downstream decides anchoring, not the
  taxonomy/format check) -> confirm it renders as a legitimate `unanchored` candidate, not a second silent drop.
- Double-submit, Library ("Surface again" clicked twice quickly with the identical stub response) -> the same
  candidate set persists (no duplicate cards) -- `upsert_findings`'s `content_key`-keyed replace-set semantics
  make the second call a no-op that preserves the first call's review state.
- Double-submit, WIP ("Surface again" clicked twice) -> this is **genuinely different behavior, not a bug**: each
  run is its own exact-snapshot-bound receipt (`tool_run_id`), matching every sibling Checklists tool's own
  "one receipt per run" design (route 75's own precedent) -- two runs legitimately produce two tool-run rows in
  the manuscript's history. The check here is that the UI handles two receipts gracefully (no crash, no
  incorrect merge/dedup), not that a second run is suppressed.
- Egress-refused path fires 403 even for a nonexistent paper/manuscript id (gate wins over 404).
- Reload the Library panel after confirming/dismissing a candidate -> review state persisted
  (`GET /papers/{id}/findings?source=analytic-flexibility`).
- Mobile viewport (375x812) -> no horizontal overflow on either panel.

## Steps

### Library (Methods -> Checklists -> Analytic flexibility)

1. Complete the Seed contract's Library setup (mutate the Renderable Seed Paper's chunk, stand up + register the
   loopback stub provider, toggle Data egress consent ON). Confirm `GET /settings` reports the loopback provider
   active.
2. Select the Renderable Seed Paper. Open Methods -> Checklists -> **Analytic flexibility**. Confirm the intro
   copy names the candidate categories, states "never a flexibility count or score," and that the model only
   proposes a quote while a local check decides anchoring. Configure the stub to return one valid item echoing
   the real page-1 text ("Facial anomalies influence social judgments in observers.", category e.g.
   `test-selection`) plus one item with an invalid category. Click **Surface decision points**. Confirm a Status
   popover entry appears labeled "Provider AI + local anchoring" and clicks back to this paper's Checklists
   section.
3. Confirm exactly **one** candidate card renders (the invalid-category item silently dropped) with its category
   label + quote + `speculative` tier badge, and no count/index/tally anywhere on the panel.
4. Click **show in paper · p.1** -> confirm a real highlighted bbox rectangle draws on page 1 (Task 8's fix), not
   a vague region note.
5. Confirm or dismiss the candidate via **Confirmed** / **Accepted…** / **Noted**; reload the panel; confirm the
   review state persisted (`GET /papers/{id}/findings?source=analytic-flexibility`).
6. Click **Surface again** twice quickly with the same stub response; confirm still exactly one candidate and the
   prior review state is preserved, not reset.
7. Reconfigure the stub to return a real-looking quote that is **not** present verbatim anywhere in the source
   text. Run again; confirm the new candidate renders with an honest unanchored state and **no** "show in paper"
   link.
8. Switch the active provider to a non-loopback/cloud one (any hostname) with Data egress consent OFF. Click
   **Surface again**. Confirm **403** with the exact detail text, the panel shows the honest "Enable AI features
   in Settings (data-egress consent)…" unavailable state, and the request listener shows the configured cloud
   host was never contacted. Separately, call `POST /papers/999999/analytic-flexibility` directly and confirm
   403 (not 404) for the nonexistent paper.
9. Select a paper with no methods text (Facial Anomaly Perception or Signal Detection Theory, unmodified). Open
   the Checklists tab; confirm the honest "no methods-section text" message and that the stub server's request
   log stays empty for this run.

### WIP (Checks tab / Methods -> Checklists -> Analytic flexibility, manuscript branch)

10. Restore the loopback provider + Data egress consent ON. Create Manuscript A and Manuscript B per the Seed
    contract (watch root + rescan; mark each manuscript's primary file explicitly).
11. Open Manuscript A. From either the manuscript's own **Checks** tab or Methods -> Checklists -> Analytic
    flexibility (the WIP branch), click **Surface decision points**. Configure the stub to return one valid
    candidate from the Methods-heading paragraph's text. Confirm the run reports `scoped: true` with no degrade
    caveat, and the candidate renders with the seven-state disposition select.
12. Change that candidate's disposition via the select (`PATCH /wip/findings/{id}`). Confirm both the manuscript's
    own Checks tab and the Methods-panel mount reflect the change without a manual reload (the shared
    `ctx.wipRefresh` counter).
13. Open Manuscript B. Click **Surface decision points**. Confirm the run reports `scoped: false` and the exact
    disclosed degrade caveat renders (confirm the live wording).
14. Reconfigure the stub to return a quote not locatable in either manuscript's source text. Re-run on Manuscript
    A or B. Confirm the resulting `wip_findings` row's `coordinate_precision` is **NULL** (inspect the raw API
    response -- never the literal string `"unanchored"`), while `details_json.anchor_state` still honestly reads
    `"unanchored"`.
15. Switch to a non-loopback/cloud provider with Data egress consent OFF. Click **Surface again** on either
    manuscript. Confirm **403** with the exact detail text, before any manuscript lookup (repeat against
    `POST /wip/manuscripts/999999/checks/analytic-flexibility` directly and confirm 403, not 404).
16. Adversarial pass: double-submit on WIP (confirm two receipts appear, no crash/incorrect merge); mobile
    viewport 375x812 on both the Checks tab and the Methods-panel mount; a manuscript with no extractable text at
    all (if constructible) shows the honest "No manuscript text was found; nothing to surface" state.

## Pass criteria

- Every declared surface (both trigger endpoints, both review endpoints, the findings read, all four fe chunks)
  is exercised and reachable on both the Library panel and the WIP Checks tab.
- All standing assertions hold, with special attention to: no aggregate ever renders; the closed taxonomy never
  leaks an invalid category; the model never supplies a location and `anchor_quote` alone decides exact/region/
  unanchored; `unanchored` maps to `coordinate_precision: NULL` on the WIP side while remaining inspectable in
  `details_json`; the PDF-vs-non-PDF scoping degrade is disclosed, not silently presented as equivalent.
- The egress gate holds with zero real requests to a configured non-loopback host, wins over a 404 for a
  nonexistent id, and a loopback provider makes zero real network egress.
- 0 console/page errors; mobile viewport has no horizontal overflow on either surface.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_92_analytic_flexibility.md` + `screenshots/` (see `_TEMPLATE.md`).
