# Increment 259 — Workbench SP2b: the assisted-extraction funnel (AI proposes, the human filters)

**Future track #36 (meta-analysis workbench), SP2b.** An **egress-gated** assistant that *proposes* meta-analysis cell
values from a paper's PDF as **candidates** for the human to verify, edit, or reject — never an independent coder.
*AI is the funnel; the human is the filter.* Built via Subagent-Driven Development (5 tasks; branch `main`, base
`c41bb77`).

## Implemented

- **Data layer (migration 0034).** A new **`ma_proposals`** table — physically isolated from the trusted `ma_cells` —
  holds candidates `{id, row_id, field_key, value, quote, page, bbox_json, anchor_state, reason}`. `ma_cells` gains an
  **`origin`** column (`null` = human-entered / captured; `'assisted'` = accepted from a candidate). `workbench_repo`
  gains `replace_row_proposals` / `_proposals_for_rows` / `get_proposal` / `delete_proposal`, and `upsert_cell` an
  `origin` param. Proposals ride back on the row view (`proposals: [...]`); the converter and every export read only
  `ma_cells`. (`app/backend/persistence/workbench_repo.py`, `alembic/versions/0034_*.py`.)
- **Generator + egress seam.** `integrations/gemini/extraction_assistant.py` — an `ExtractionAssistant` Protocol +
  `GeminiExtractionAssistant.propose(*, text, fields)` (prompts the model for `{value, quote, page}` per empty field)
  + `parse_proposals(raw, *, allowed_keys)`, which tolerates markdown fences / surrounding prose, drops unknown keys +
  malformed entries, caps value ≤ 500 / quote ≤ 4000, and returns `[]` on any failure. It rides the **existing**
  `EgressGatedExtractionAssistant` (`app/backend/llm/egress.py`) — `DataEgressDisabledError` → 403 for a non-loopback
  provider without consent; loopback = honestly no-egress (endpoint-based gate, inc 256). No new dependency.
- **Local anchoring (the honesty core).** `app/backend/workbench_assist.py` — `page_tagged_text` (caps paper text at
  `MAX_TEXT_CHARS = 50_000`, reports `truncated`), `primary_pdf_path` (the server-resolved primary PDF, never a
  request path), and **`anchor_proposal(pdf_path, value, quote, claimed_page)`** → `{anchor_state, page, bbox_json,
  reason}`. It runs `locate_quote` (PyMuPDF) on the PDF and classifies **deterministically, locally**:
  **`exact`** = quote located **and** the value string appears literally in it → a bounded **union-rect** `bbox_json`;
  **`region`** = quote located but the value isn't in it → page, no bbox; **`unanchored`** = quote not found → the
  model's claimed page (unverified), no bbox. *The model never asserts a location or a confidence.*
- **Endpoints.** `app/backend/api/routers/workbench.py` — `POST /workbench/rows/{id}/propose` (422 no linked paper /
  no PDF / no extracted text; **short-circuits `{proposals:[], truncated}` with no provider call when the row has no
  empty proposable structured field**; 403 egress-off; 502 provider failure; else `{proposals, truncated}`),
  `POST /workbench/proposals/{id}/accept` (optional edited `value`; promotes into `ma_cells` with `origin='assisted'`;
  **stores `bbox_json` only when `anchor_state=='exact'` and the value was not edited** — else region), and
  `POST /workbench/proposals/{id}/reject` (deletes the candidate). 404 on unknown row/proposal.
- **Surface.** New chunk `app/frontend/js/46_workbench_propose.jsx` (hoisted across the shared IIFE — the 10b/35b
  precedent): **`WbDraftButton`** (per-row *✨ Draft from PDF*, disabled with an honest tooltip when AI features are
  off), **`WbAnchorBadge`** (exact / region / couldn't-verify — the local anchor signal), **`WbCandidate`** (the amber
  card: value + badge + *Open at anchor* + accept / edit-then-accept / reject, with the **verbatim quote shown inline**
  in both view and edit modes). Wired into `45_workbench.jsx` (`draftRow` / `acceptProposal` / `rejectProposal` /
  `openProposalAnchor`; `aiReady` gates the button; a `ProgressBar` covers the 10–30 s draft). `showCand` suppresses a
  candidate the moment a cell holds a human value (fact ≠ candidate). Amber = `--flag` (DESIGN #8, no new color
  semantics); unanchored candidates get the dashed `.speculative` treatment (invariant #2).

## Key technical detail

**Precision is derived, never claimed — at two moments.** (1) *At open* — `openProposalAnchor` passes
`precision:"exact"` + the `bbox_json` **only** when `anchor_state === "exact"`; a **region** candidate opens at
`precision:"region"` with `bboxJson:null` (scrolls to the located page, an approximate-location note, no rect); an
**unanchored** candidate — the quote was *not* found, so the model's page is an unverified claim — opens at
`precision:null` (scroll only, no rect **and no "region" note** that would imply we had located it). (2) *At accept* —
`keep_exact = anchor_state == "exact" and not edited`; the cell stores `bbox_json` only when `keep_exact`, so **editing
the value before accepting drops the anchor to region** (the exact box marked the *original* number; a value you
changed can't keep claiming it). Both honor invariant #2 end-to-end: an exact rect is drawn only when the app itself
located the quote and the value in it — the model's `page`/`quote` is a *claim* the local locator adjudicates.

**Candidate isolation is the load-bearing property.** Candidates live only in `ma_proposals`. The converter
(`cell_values`) and all four exports (CSV / metafor / RevMan / provenance) read `ma_cells`, which only ever holds
human-accepted values. Accept is the sole promotion path. Proven by `test_propose_accept_reject_candidate_safety`
(a drafted-but-unaccepted value never appears in the CSV).

**A human value is never contested (post-review fix).** A hand-entered `put_cell` now drops any live proposal for
that field (`delete_proposals_for_field`): a stale candidate can't be accepted over a human's value, and the
resurfacing-stale-candidate footgun is closed — the funnel fills gaps, it never overwrites a fact. Proven by
`test_manual_cell_write_clears_pending_candidate` (write a cell → the candidate is gone → accepting it 404s).

## Manual verification script (port 8888)

1. `$env:CALLOSUM_DB_URL=…; uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888` → open `/`.
2. Settings → enable AI features (a **loopback/local** provider = no egress, or a canned assistant — do **not** send
   library text to a real cloud host in a check).
3. Extract tab → a project (two-group continuous) → **+ Add paper** → pick a paper with a real PDF → a linked row.
4. On the row, **✨ Draft from PDF** → a progress bar → **amber candidates** appear beside the empty structured cells,
   each with a **verbatim quote** + an anchor badge (**✓ exact · p.N** / **region · p.N** / **… couldn't verify**).
5. Confirm the candidates are **not** in the cell values, not in **Convert**, and not in any **Export** yet.
6. **📎 (Open at anchor)** on an *exact* candidate → the PDF opens with the **exact passage highlighted**; on a
   *region*/*unanchored* candidate → it opens the page with **no rect** (invariant #2).
7. **✓** accept one (→ it fills the cell; the *provenance* export shows `origin:"assisted"`). **✎** edit one's number
   then **✓** → an honest note explains the anchor became **region** (the exact box was dropped); its 📎 tooltip reads
   `region`. **✗** reject one → it disappears, nothing written. In edit mode, **Esc** cancels back to the proposal.
8. Turn AI features **off** → **Draft from PDF** is disabled with a tooltip naming *Allow AI features*; a forced
   `POST …/propose` returns **403**, and **no `generativelanguage` request** is made.

## Experience pass (rule #11 — persona: the deadline meta-analyst)

Dispatched a persona-grounded agent (a postdoc coding ~30 studies who's been burned by AI that invents numbers).
**Verdict: serves-with-gaps** — the honesty foundation is sound (candidates isolated; invariant #2 enforced at accept;
the anchor classification is local + deterministic, the model asserts nothing). **Five cheap edit-flow fixes folded in
this increment** (frontend-only): (1) the **verbatim quote now stays visible while editing** a candidate (invariant #4 —
you keep the source in view while correcting a misread number; it had been hidden in edit mode); (2) **Esc cancels an
edit** non-destructively (was Enter-only; ✗ deleted the whole proposal); (3) the quote **wraps to full width** instead
of truncating at 320px (a cut quote could hide the very number you're verifying); (4) an **honest note on accept** when
an edit drops an exact anchor to region (explains *why* the highlight went away — invariant #2 transparency); (5) the
disabled-Draft tooltip **names the exact toggle** (*Allow AI features*). **Backlogged** (need a considered pass, not
one-liners; filed to #36 tagged to the persona): the "region" badge vocabulary for first-timers; and a text label so
the fact-vs-candidate distinction isn't amber-only (accessibility). (The **unanchored** Open-at-anchor footgun this
list had flagged — opening at the model's *claimed* page as if `region` — was **fixed in the post-review pass**: it
now opens at `null` precision, drawing no rect and no approximate-location note.)

## Pytest

`pytest --ignore=tests/test_mcp_server.py` → **1032 passed, 1 skipped** (+ the new `test_workbench.py` propose/accept/reject +
candidate-safety + edit-drops-to-region + egress-off-403 + 422/404/502 paths + `test_manual_cell_write_clears_pending_candidate`,
and `test_workbench_assist.py` anchor-state + defensive-parse + caps tests). `ruff check` / `ruff format --check` clean.
All touched `app/` files under the 600-line cap (`workbench.py` 319, `45_workbench.jsx` 333, `workbench_repo.py` 250,
`46_workbench_propose.jsx` 57). Frontend built clean via esbuild. Security audit
`2026-07-03_workbench-assisted-extraction.md` **PASS**; QA route 65 extended (0 uncovered — 203/203 API + 965/965 FE).

## Post-review fixes (final whole-branch review)

The SDD final whole-branch review returned **Ready to push — with fixes** (2 Important, honesty-invariant-touching; 3
Minor backlogged). Both Important fixes applied here, each strengthening (never relaxing) an invariant:
- **#1 — a human value is never contested.** `put_cell` now clears any live proposal for the field it writes
  (`delete_proposals_for_field`) — the reviewer's "simpler and cleaner" option. Closes the reachable clobber path
  (type a value → the stale candidate is gone → a later accept 404s) **and** the resurfacing-stale-candidate footgun
  (Minor #5). Test: `test_manual_cell_write_clears_pending_candidate`.
- **#2 — unanchored open honesty (invariant #2).** `openProposalAnchor` now passes `precision:null` (not `region`)
  for an unanchored candidate, so Open-at-anchor no longer implies we located an approximate region when the quote
  was never found. (This also resolves the experience-pass unanchored footgun above.)

Minors backlogged to #36 (filed to `INCREMENT-BACKLOG.md`): `_value_in_quote` substring vs. token match; keeping the
model's `claimed_page` on an unanchored candidate; the "region" badge vocabulary + a non-color fact/candidate label.
