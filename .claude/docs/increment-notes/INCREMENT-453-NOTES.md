# Increment 453 — Thumb auditability for PUBLISHERS (backlog #40)

## Implemented

PUBLISHERS' open-science weighting ("the thumb") re-ranks candidate journals by blending topical fit with an
internal openness score, but a user previously had no way to see *how much* the weighting actually moved any
given journal versus a neutral, fit-only ordering. This increment closes that gap — the original design doc
(`opus4.8_future-tracks_publishersmethodstool.md`) names it explicitly: "thumb auditability... a neutral
pre-weighting ordering viewable beside the weighted one."

`app/backend/methods/publishers.py`'s `JournalProfile` gains two required fields: `fit_rank` (1-based rank among
the full considered pool, sorted by `fit` alone) and `weighted_rank` (1-based rank in the actual blended-sort
order). Both are computed over the **full considered pool**, not just the returned `top_k` slice — a journal only
shown because the weighting elevated it still exposes its true, possibly much worse, fit-only rank. Mirrored into
`app/backend/api/routers/publishers.py`'s `JournalProfileModel`. `app/frontend/js/08e_methods_publishers.jsx`'s
`PubProfileCard` shows a new caveat line — "Ranked #N here with weighting on · #M by topical fit alone" — reusing
the existing `pub-caveat` idiom, rendered **only** when weighting is on and the two ranks actually diverge (when
they're equal, showing them would be pure noise).

**The sibling design-doc item, user exclusion/filtering, was explicitly NOT built this pass.** The same design
doc flags it as ethically fraught: "the deferred mechanism should elevate, not exclude. Hard exclusion is the
disfavored extreme — it reintroduces the 'these are bad' valence." This was surfaced to the user before any code
was written (a genuine Principles-gate reflective pause, not a rubber-stamp), and the user confirmed: build
auditability only, leave exclusion deferred — matching the design doc's own recorded intent, not a default or an
oversight.

**COPE/OASPA membership was live re-checked this session too** (the other still-open backlog #40 item) and
reconfirmed not buildable: COPE's site is behind Cloudflare bot protection (a basic request 403s outright);
OASPA runs on WordPress with a real REST API (`wp-json/wp/v2/`), but its members directory uses a Jet-Engine
listing (no structured REST endpoint) — only HTML scraping would work, which isn't the kind of real-API source
this project's other four PUBLISHERS signals were built on.

## Key technical detail

**Ranking over the full pool, not the shown slice, is the load-bearing design choice.** `rows` (the existing
blended sort) already covers every candidate in `pool` before `[:top_k]` truncates it for display — so
`weighted_rank` is simply `enumerate(rows[:top_k], start=1)`'s counter, no new computation. `fit_rank` needed a
second, independent sort (`sorted(range(len(pool)), key=lambda i: fits[i], reverse=True)`) since the fit-only
order and the blended order are different orderings of the same pool. Both are 1-based positions among
`considered` (up to `MAX_CANDIDATES`, currently 60), not among `shown` (`top_k`, default 25) — this matters
because the single most informative case is exactly the one that would be invisible if ranks were rebased to the
shown set: a journal whose real topical fit is mediocre (say, fit_rank 45 of 60) but whose openness weighting
boosted it into the visible top 25 (weighted_rank 20). Losing that "45 → 20" signal by silently re-basing
`fit_rank` to the shown window would understate exactly how much the weighting is doing — the opposite of
auditability. Verified with a dedicated 3-candidate test (`top_k=2`) where the worst-fit candidate (`fit_rank=3`
among 3 considered) is elevated to `weighted_rank=1` by a diamond+Seal boost, proving the full-pool scope holds
even when a candidate's fit-only rank falls entirely outside the returned window.

**Why this doesn't trip the no-composite-score veto (Principles #7, an explicit finding, not an afterthought).**
`fit` (the raw cosine similarity) is already shown per card today; `fit_rank`/`weighted_rank` are transparent
ordinal derivations of two already-visible values (the raw fit score and the existing blended sort), not a new
hidden metric or blend. They're phrased as explicit ordinal positions ("#3 by fit alone"), never a percentage,
normalized value, or anything `*score*`-suffixed — categorically distinct from the vetoed composite score
`route_60_publishers.md`'s standing assertions already guard against. QA's own standing assertions were extended
to make this distinction explicit and testable going forward, not just asserted in prose.

## Housekeeping / gates

- **No security-audit addendum** — no new external fetch, endpoint, schema, or migration; a pure read-out of
  already-computed backend values plus a conditional frontend display.
- **QA route**: extended `.claude/qa-routes/route_60_publishers.md`'s standing assertions (the new veto-adjacent
  ordinal-not-score line, the per-card caveat gating rule), adversarial checklist (weighting-0 equality; the
  full-pool-not-shown-slice proof), Steps (a new step 9), Frontend section, and Pass criteria.
- `.claude/docs/INCREMENT-BACKLOG.md` #40: thumb auditability marked shipped; user exclusion/filtering recorded
  as *deliberately* still deferred (not silently dropped); COPE/OASPA's live re-check recorded with the concrete
  reason each is blocked.

## Manual verification script

1. Run PUBLISHERS with `weighting: 0` (Off — best fit only). Confirm no per-card auditability caveat renders
   anywhere (ranks trivially coincide).
2. Run the same search with `weighting: 1.0` (Balanced/full) on a topic where topical fit and openness disagree.
   Confirm at least one card shows the caveat line with correct `#N`/`#M` values, and that a card whose rank
   didn't move shows no caveat.
3. Confirm the caveat line reads as an ordinal position only ("#3 by topical fit alone") — never a percentage,
   decimal, or anything resembling a score.

## Verification

- `pytest tests/test_publishers.py -q` → **30 passed** (29 pre-existing + 1 new dedicated 3-candidate test; 2
  existing tests extended with rank assertions).
- `pytest tests/test_frontend_assembly.py -q` → **64 passed**.
- `python tools/check_line_budget.py`: clean — `methods/publishers.py` 316 lines, `08e_methods_publishers.jsx`
  447 lines, both with headroom.
- `python tools/qa/build_surface_map.py check`: no new API/FE surface — additive fields + conditional display on
  an already-covered endpoint/component.
- `ruff format` + `ruff check`: clean. `python tools/build_frontend.py`: clean.

## Rollback

No schema/migration to revert. Remove the two new `JournalProfile`/`JournalProfileModel` fields and their
construction sites (each a clearly separable addition); remove the new frontend caveat block (a single
conditional JSX block, easily isolated); revert the two extended tests and drop the new one. No other source's
behavior is touched by any of this.
