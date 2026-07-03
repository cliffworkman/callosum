# Design — Assisted-extraction funnel (workbench SP2b)

**Status:** approved (2026-07-03). The SP2b slice of the meta-analysis extraction workbench
(`future-tracks/opus4.8_future-tracks_metaanalysisextractionworkbench.md`, component #4 — "assisted extraction with
mandatory provenance + verification, the heart and the danger"). Builds on the manual workspace: SP2a-1 (grid, inc 253)
+ SP2a-2 (select-in-PDF capture, inc 255) + SP2b-dataset-loop (Convert-all + metafor/RevMan exports, inc 258). This is
the **egress + heavy-A-A slice** the SP2 spec deferred: the consent-gated LLM **drafts** candidate cell values that a
human **verifies against the shown source** before they are trusted. Target increment: **259**.

## What it is

An **assistant that proposes, a human who disposes.** For a row linked to a library paper, one click —
**"Draft from PDF →"** — sends the paper's extracted text to the consent-gated LLM, which proposes values for the row's
empty **structured** cells, each with a **verbatim quote**. The app then **independently anchors each proposal locally**
(via `pdf_processing.quote_matching.locate_quote`) and renders it as an **amber candidate** the researcher accepts,
edits, or rejects **per cell**. A proposal never enters the trusted dataset (`ma_cells`) — and therefore never reaches
the converter or any export — until a human accepts it. "AI is the funnel; the human is the filter." (PRINCIPLES: facts
≠ candidates; the human is the filter / the AI is the funnel; the deterministic substrate is the source of truth, the
model only narrates it.)

**Maintainer scope (AskUserQuestion + design nods, 2026-07-03):**
- **Loop granularity = per-row, on demand** (one paper's egress at a time; the human stays paced with the source). The
  **batch "draft all un-filled rows"** escalation is **deferred** to a later increment behind its own confirm + the same
  per-cell verify gate (no rubber-stamp path).
- **Un-anchored proposals are shown, flagged** (amber), never pre-trusted and never drawn as an exact highlight — the
  honesty lives in the marking, not in hiding it (invariant #4: evidence always shown). Accept → region precision, edit,
  or reject. The failure reason is available on hover (not an always-on block — the leaner surface).
- **Which cells = structured columns only** — every template field whose `type ∈ {number, choice}` (the role/converter
  inputs **plus** simple moderators like Year/Country). Free-text (`type == text`) columns stay hand-entered. This maps
  the "simple moderators, not free text" line onto a field already in the template.
- **Fills gaps, never contests a human:** propose runs only for **empty** structured cells; a cell already holding a
  value is left untouched.
- **`origin` audit column:** a small nullable `origin` column on `ma_cells` (`assisted` on accept) so the provenance
  export can honestly show **"AI-drafted, human-verified"** — the extraction audit trail the track doc requires.
- **Synchronous per-row propose** (one blocking LLM call, like `POST /methods/effect-size`) — no async job in v1.

## The load-bearing boundary (extends SP2a; the reason the gate clears)

The funnel **only proposes candidates**; it changes nothing about extract/structure/convert/export — it never pools,
models, or adjudicates. Four properties make it safe, and it clears the Principles gate **because of** them:

1. **Candidates are physically isolated from facts.** Proposals live in a **separate `ma_proposals` table**. The
   converter (`workbench_repo.cell_values`) and all four exports (`workbench_export`) read `ma_cells`, which only ever
   holds **human-accepted** values — so convert/export are candidate-safe with **zero change** to that boundary code.
2. **The model never asserts a location or a confidence.** It returns only `{value, quote, page}` text; the
   **deterministic local locator** (`locate_quote`) decides the anchor. The honest signal is the anchor state
   (`exact` / `region` / `unanchored`), not an opaque model score (principle #7 — no opaque composite).
3. **Nothing is trusted without a human act.** Acceptance is an **explicit per-cell** step; there is no auto-fill and no
   accept-all-blind path. Coordinate honesty (invariant #2) is preserved: an accepted proposal's precision is derived
   from what was actually located, never from the model's claim.
4. **The LLM is a drafting aid, never a second coder.** One drafting pass; double-coding/IRR stays a human-only deferred
   slice (track veto). Egress rides the **existing** consent gate (invariant #3) — no new bypass; the feature is fully
   usable gated-off (manual + select-in-PDF paths untouched); loopback/local providers are honestly no-egress.

**Declined misaligned paths (recorded):** auto-filling cells (removes the human); drawing the model's self-reported
bbox or showing its confidence (invariant #2 / #7); letting a proposal flow into convert/export before acceptance (a
candidate masquerading as a fact); calling a second LLM pass the "second coder" (launders correlated unreliability).

## Data model (migration 0034, additive/guarded; extends `persistence/schema_workbench.py`)

- **`ma_proposals`** (new) — `id` PK, `row_id` INT FK→`ma_rows` **CASCADE**, `field_key` TEXT, `value` TEXT nullable
  (proposed value, stored **verbatim as string** — never coerced here; convert coerces later, exactly like a manual
  cell), `quote` TEXT nullable (the model's verbatim quote), `page` INT nullable (the **located** page, or the model's
  claimed page when un-anchored), `bbox_json` TEXT nullable (rectangles from `locate_quote` — **set only when
  `exact`**), `anchor_state` TEXT (`exact` | `region` | `unanchored`), `reason` TEXT nullable (`value_not_in_quote` |
  `quote_not_found`), `created_at`; **UNIQUE(row_id, field_key)** — re-drafting a cell replaces its live proposal.
- **`ma_cells`** — add a nullable **`origin`** TEXT column (NULL = manual/capture; `assisted` set on accept). Surfaced in
  the provenance export only when set. This is the **only** change to `ma_cells`, and it does not touch `cell_values`
  (convert) or the metafor/RevMan/CSV export shapes.

## The generator + egress seam

- **`integrations/gemini/extraction_assistant.py`** (new) — a provider-neutral generator (sibling to
  `research_summary`/`overview`; rides `app.backend.llm.providers.complete(config, prompt)`). `.propose(*, text, fields)`
  builds a **strict-JSON** prompt: *"You are a data-extraction assistant for a meta-analysis. Propose values ONLY for
  these fields: `[{key, label, type, options?}]`. For each field you can find, return its value and a **VERBATIM quote
  copied exactly** from the text that contains it, plus the page number. If a field is not reported, **omit it — never
  guess or compute**. Return strict JSON `{field_key: {value, quote, page}}`."* Response is **untrusted** (a custom
  endpoint is possible) → defensive JSON parse (tolerate junk/markdown fences; ignore unknown keys and malformed
  entries; a parse failure yields **zero** proposals, never a crash).
- **`EgressGatedExtractionAssistant`** (new, in `app/backend/llm/egress.py`) — mirrors the other five gated wrappers:
  holds `inner` + `data_egress_enabled` + `provider`/`wire_format`/`base_url`; raises `DataEgressDisabledError` when
  `_egress_needed(...)` and not consented; else delegates. Wired at the `create_app` DI seam like the summary generator.
- **Local anchoring (the honesty engine).** For each parsed `{value, quote, page}`, `locate_quote(pdf_path, quote)`:
  - quote located **and** the value string appears in the located (normalized) quote → **`exact`**, store `rectangles`
    as `bbox_json`, `page` = the located page.
  - quote located, value not literal in it → **`region`**, `page` = located page, `reason = value_not_in_quote`.
  - quote not found → **`unanchored`**, `page` = the model's claimed page (rendered with a "?"), `bbox = None`,
    `reason = quote_not_found`.
  The value/quote/page string lengths are capped before storage (proposal value ≤ 500, like the SP2a-2 capture).

## Surface (frontend)

`app/frontend/js/45_workbench.jsx` is at 293 lines; the funnel UI is **extracted into a new chunk**
`app/frontend/js/46_workbench_propose.jsx` up front (rule #1; the shared-IIFE function-hoist precedent —
`10b_libmenus`/`35b_providers`). `.wb-*` CSS reuses existing tokens + the `--flag` amber for candidate/region states
(rule #8 — no new color semantics; amber already = unresolved/uncertain/region).

- **Per-row "Draft from PDF →"** — shown only when the row has a linked `paper_id`; otherwise a muted "link a paper to
  draft" hint. When AI is **gated-off** (egress off + a cloud provider, or no key), the button is **disabled** with an
  **"Enable AI features to draft"** hint (the existing AI-surface pattern); a 403 from the endpoint is surfaced as an
  honest inline note, never a crash. Manual entry + select-in-PDF capture are unchanged in every state.
- **Amber candidate overlay** on each empty structured cell that has a proposal: the proposed value in a candidate style
  (`✎`, amber), an **anchor badge** — **✓ exact · p.7** / **region · p.7** / **p.7? — couldn't verify** (the `reason` on
  hover) — and inline **✓ (accept) / edit / ✗ (reject)**. The 📎 **Open at anchor** works **before** accepting — the
  "verify against the shown source" affordance: `exact` draws the highlight rect; `region`/`unanchored` scroll to the
  page and draw nothing (invariant #2, precision derived from `anchor_state`).
- **Accept** writes the value into the real cell (green, like any accepted cell) and clears the amber overlay; **edit**
  opens the value inline (accepting an edited value drops `exact`→`region`); **reject** removes the overlay.

## Endpoints (`app/backend/api/routers/workbench.py`; under the `/workbench*` QA wildcard)

All local, **sync**, bound-param. New repo functions in `persistence/workbench_repo.py` (`insert_proposals`,
`get_proposal`, `delete_proposal`, `proposals_for_project`/`_row`); `project_view` gains a `proposals` block per row.

- `POST /workbench/rows/{row_id}/propose` — resolve the row → its `paper_id` → the paper's PDF path + extracted text
  (**capped ~50k chars**, resource guard #4; note when truncated). **404** unknown row; **422** if the row has no linked
  paper or the paper has no processed PDF/text; **403** (`DataEgressDisabledError` → honest "AI features are off"
  message) if egress-gated + off. Runs the gated assistant, anchors each proposal locally, **replaces** the row's live
  proposals for the targeted fields, returns the created proposals (+ a `truncated` flag).
- `POST /workbench/proposals/{proposal_id}/accept` `{value?}` — promote into `ma_cells` via `upsert_cell`
  (`page`/`quote` always; `bbox_json` **only if `anchor_state == exact`** and no `value` override), set
  `origin='assisted'`, **clear the row's `converted_json`** (a new value invalidates the stale g — the inc-256/258
  cell-edit rule), delete the proposal. A `{value}` override (edit-before-accept) drops the exact bbox → region. Returns
  the refreshed project view. **404** unknown proposal.
- `POST /workbench/proposals/{proposal_id}/reject` — delete the proposal; return the refreshed view. **404** unknown.

`create_app` wires the new gated assistant (default: the resolved provider from the roster) exactly as it wires the
summary generator; tests inject a canned assistant so no network is touched.

## Gates

- **Security audit** `.claude/security-audits/2026-07-03_workbench-assisted-extraction.md` (triggered: a new endpoint +
  a new external-fetch/egress path + a migration + 3+ files). Cover: the **library-text egress channel** (the paper's
  text is sent to the LLM — this is the consent-gated channel; document that it rides the existing gate and is off by
  default); bound-param SQL (rule #3); typed/validated bodies + `proposal_id`/`row_id` int path params (rule #4);
  **untrusted model-response parsing** (defensive JSON, zero-proposals-on-junk, no crash); the proposed value/quote/page
  **length caps** + the **~50k text cap** (resource exhaustion); `locate_quote` runs on the **already-validated
  server-side PDF path** (no request-derived path); proposed quotes rendered as **text, not HTML**; accepted values ride
  the existing number-aware `_csv_safe` on export; secret handling unchanged (key write-only, never logged — the
  provider seam already redacts). Negative paths: egress-off → 403; malformed JSON → 0 proposals; oversized text →
  capped; row without a paper → 422. End **PASS**.
- **Principles + A-A (rule #9):** run above — clears **because of** the isolate-candidates / anchor-locally /
  human-accepts / never-a-coder properties. Resembles the summarization worked example (propose → verify → shown with
  evidence). No A-A veto in play (no accusation, no paywall circumvention, no reaching into another tool's store; the
  paper is the user's own library item). Credit-the-lineage: the hand-off tools + the assisted-extraction-with-
  verification pattern are already credited in the track; no new method needs a citation beyond SP1's.
- **QA (rule #10):** extend `route_65_workbench.md` — assert **a proposal never appears in convert or any export until
  accepted** (candidate-safety), **un-anchored proposals are shown flagged, never drawn exact** (invariant #2 + #4), the
  **egress gate** (no genai host when off), and **gated-off disables the button**. `build_surface_map.py check` at
  0-uncovered (the `/workbench*` wildcard covers the new endpoints).
- **Rule #1:** `45_workbench.jsx` split → `46_workbench_propose.jsx` (both < 600); `routers/workbench.py` (276) +
  `workbench_repo.py` + `extraction_assistant.py` each < 600 (split the router by concern if it approaches the cap). **No
  new dependency** (reuses `httpx`/`google-genai` via the provider seam + `fitz` via `locate_quote`).

## Verification

- **pytest `tests/test_workbench.py` + `tests/test_workbench_assist.py` (hermetic, injected assistant + a small real PDF
  fixture so `locate_quote` runs):**
  - **anchor-state derivation** — a proposal whose quote locates + value-in-quote → `exact` (with bbox); quote locates,
    value not literal → `region`; quote absent → `unanchored` (bbox None, model's page kept with reason).
  - **the boundary test (candidate-safety)** — after propose, the row's `converted` is unchanged and **metafor/CSV/RevMan
    exports contain no proposed value**; only after **accept** does the value appear.
  - **accept** promotes with correct precision (`exact` keeps bbox; edit-before-accept + `region`/`unanchored` → bbox
    None), sets `origin='assisted'`, clears `converted_json`; **reject** discards.
  - **egress-off + a cloud provider → 403 / `DataEgressDisabledError`** (mirrors `test_egress_gate`); a loopback provider
    proposes with no gate.
  - **malformed model JSON → 0 proposals, clean error**; **only empty structured (number/choice) cells** are proposed
    (text columns + already-filled cells skipped).
- **Full suite green; ruff check + format; QA check 0-uncovered; `test_frontend_assembly`** (frontend rebuilt).
- **Headed** `.local/visual/drive_inc259_assist.py` (**egress opt-in via a fake/loopback provider** so no real network):
  link a paper → **Draft from PDF** → amber candidates appear → **Open at anchor** shows an exact highlight for a located
  proposal (no rect for a region/unanchored one) → **accept** one, **edit** one (→ region), **reject** one → **Convert**
  → g reflects only accepted cells → confirm **no proposed value in any export** pre-accept; 0 console/page errors; with
  AI off, the button is disabled with the enable hint and **0 genai-host requests**.
- **Experience pass (rule #11):** persona = the **deadline meta-analyst** drafting a study from its PDF — does the
  amber/exact distinction read; is "verify against the source" one obvious click; does the gated-off path explain
  itself; is accept/edit/reject discoverable. Fix-cheap or backlog; record in the increment notes.
- **Docs:** `INCREMENT-259-NOTES.md`; `changes.md`; CLAUDE (count 258→259, the LLM/egress-channel note, the new
  router/generator/chunk + `ma_proposals`); help corpus "Extracting a meta-analysis dataset" gains a
  **"Drafting cells with AI (you verify each one)"** subsection (`HELP-DOCS-SYNCED` → 259); backlog (SP2b-funnel shipped;
  batch-draft + retrieval-narrowing named as the next escalations). Commit (excluding `www/`), push, watch CI.

## Out of scope (deferred)

The **batch "draft all un-filled rows"** escalation (its own confirm + the same per-cell verify gate); **retrieval-
narrowed** text (Approach 3 — embed field labels, send only top-k chunks; an egress optimization once full-text is
proven); **double-coding / IRR** (human-only — the track veto: two correlated LLM passes are not independent coders);
screening/PRISMA; RoB instruments; figure/plot digitizing (point at WebPlotDigitizer); re-drafting a cell that already
holds a human value (the funnel fills gaps, it does not contest).
