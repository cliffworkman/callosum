# INCREMENT 257 — Autonomous close-out sweep (QA/experience findings + a seed-fixture gap)

**Track:** none new — this is a **cleanup sweep** of small, ready, no-decision items that had accumulated above the
`⛔ NEEDS CLIFF` cut line in `INCREMENT-BACKLOG.md` (three QA/experience findings, one honest-gating fix, one test
seed gap). Each is low-risk and closes a real dead-end or a silent failure. No new feature, no schema, no egress
posture change.

## Implemented

Five independent fixes:

1. **item_type seed gap** — `tests/api_helpers.py`. Both main-seed papers (`_seed_library`) now pass
   `item_type="article-journal"` on `create_paper`. Before, the seeded library had every `item_type` NULL, so
   `GET /papers/item-types` returned empty and the Library **Type** filter never rendered in a seeded/QA instance —
   a surface QA couldn't reach. Fixture-only; no production behavior change.

2. **statcheck page surfaced inline** — `app/frontend/js/06_methods_statcheck.jsx` + `styles.css`. Each per-test row
   already carried `raw` (the verbatim matched test) + the recomputed p + status; the **page** was tooltip-only. It
   now renders inline as a **`p. N`** locator (mono, indigo `--accent` = the page it opens — provenance/citation
   jump); a test statcheck couldn't attribute to a page shows a muted **`p. —`** (`.statcheck-page-none`), never a
   fabricated page. Coordinate honesty unchanged: clicking opens the page at **region** precision (statcheck has no
   exact bbox), never a fake exact highlight.

3. **tag add/color/remove — honest inline failure** — `app/frontend/js/25b_tags.jsx`. A rejected add / set-color /
   remove was previously **silent** (the input just cleared, the 422 vanished). `TagsRow` now holds an `error`
   state; a failed op renders the reused **`.axis-err`** box (`role="alert"`) below the chips with the server's
   message (e.g. `Couldn't add "…"`); typing in the input clears it. Reuses the existing amber error recipe (no new
   CSS, no new token).

4. **citation-equity "Find overlooked work" gated on no-DOI** — `app/frontend/js/08b_methods_citation_equity.jsx`.
   `CitationEquityPaper` already gated its **Run audit** on `hasDoi`, but **`OverlookedWork`** did not — so a no-DOI
   paper showed a *clickable* "Find overlooked work" that always 422'd. The single `/papers/{id}` meta fetch is now
   lifted to `CitationEquitySection` (one source of truth: `{ title, hasDoi }`) and threaded to both children; each
   control is hidden for a no-DOI paper and replaced with its own honest hint ("This paper has no DOI, so OpenAlex
   can't relate work to it — the overlooked-work search needs a DOI"). `hasDoi` is `null` while meta loads → no
   button/hint flash.

5. **library header wraps at narrow width** — `styles.css`. `.lib-head` / `.lib-head-actions` gain `flex-wrap: wrap`
   so the action chips (Add / saved-search / the signal-filter chips: ⚠ flagged, ⚠ retracted, 📋 to review, 🔎 open
   data) wrap to a new line instead of overflowing the pane on a phone/narrow width. A **no-op at desktop width**
   (they already fit on one line), matching how `.searchbar` already wraps.

QA routes extended in the same increment (rule #10): **route_33** (inline `p. N` / `p. —` locator + region open),
**route_20** (the inline `.axis-err` on a rejected tag op), **route_51** (both citation-equity controls gated off
for a no-DOI paper, not just the audit), **route_23** (the header chips *wrap* at 375px, all reachable). Surface-map
`check` clean: 199/199 API + 944/944 FE covered, 0 uncovered.

## Key technical detail — the fixes are "surface the finding / close the dead-end", not new signals

None of these adds a claim, score, or judgment, so none re-triggers the rule-#9 gate. Each removes a *silent* or
*dead-ended* interaction and replaces it with an honest, inspectable one:

- statcheck: the page was already computed and honest — it was just hidden in a tooltip; surfacing it inline is
  pure legibility, and it deliberately keeps **region** precision (indigo cues "jump", not "exact box").
- tags: a 422 that vanished is now an `role="alert"` line — "silence is not a certificate" applied to an error path.
- citation-equity: a control that structurally *cannot* succeed (no DOI → OpenAlex can't resolve references) is now
  declined up front with the reason, rather than inviting a click that fails. The meta fetch was de-duplicated
  (was two `/papers/{id}` calls; now one shared by both children) as a side benefit.

## Manual verification script

1. Rebuild: `python tools/build_frontend.py`. Start the app (port **8888**).
2. **statcheck:** open METHODS → Statistics check, select a paper with APA stats, run its check. Each row shows
   `p. N` inline (indigo); a row with no page shows `p. —` (muted). Click a `p. N` row → the page opens (region:
   scroll + note, no drawn rect).
3. **tags:** open a paper's Details → Tags. Type an over-long / invalid tag and blur/Enter → an amber inline
   message appears below the chips instead of the input silently clearing; start typing again → it clears.
4. **citation-equity:** select a paper **with no DOI** → THEORY → Cite → Citation concentration. Confirm **neither**
   "Run audit" nor "Find overlooked work" button shows — each is replaced by an honest no-DOI hint. Select a paper
   **with** a DOI → both buttons return.
5. **mobile header:** resize to 375×812 (or DevTools device mode). The library header action chips **wrap** to
   multiple lines; nothing overflows or is clipped; every chip is reachable. Desktop width unchanged (one line).
6. **Type filter (seed):** in a freshly seeded/QA instance the Library **Type** filter now renders (item-types is
   non-empty).

## Experience pass (rule #11)

These fixes *are* the output of prior experience/QA findings, so the pass is proportionate — inhabit each affected
user and confirm the loop closes with no new dead-end:

- **Deadline citer (statcheck):** scanning flagged rows, they can now see *which page* each inconsistent test is on
  before clicking — the page-locate step that was a hover-hunt is now at-a-glance; the region-precision open still
  lands them on the page honestly. Closes the "which page was that?" gap.
- **Corpus builder (tags):** a rejected tag now says why instead of appearing to do nothing — no more "did that
  save?" ambiguity.
- **Corpus builder (citation-equity):** a no-DOI paper no longer offers a button that fails; the honest hint tells
  them the precondition (a DOI) up front. No dead-end.
- **Mobile reader (header):** all header filters are reachable on a phone instead of running off-screen.

No blocking UX gap; nothing filed to the backlog from this pass.

## Pytest

`pytest --ignore=tests/test_mcp_server.py` — **1009 passed, 1 skipped** in 653s (exit 0). The count is **+1 over
the inc-256 baseline of 1008** — that one is the intervening QA-triage `test_oversized_search_query_rejected_at_boundary`
(committed at `add8067`, the entry above this one in `changes.md`); **inc 257 itself adds no test.** Four of the
five fixes are frontend-only (no Python surface); the fifth is a **fixture** change in `api_helpers.py` that seeds
`item_type` — the suite stays green (no test asserted the seed's item-types were empty). The optional `mcp` suite is
uncollectable without the `mcp` package here, as at baseline. Frontend built clean via esbuild.
