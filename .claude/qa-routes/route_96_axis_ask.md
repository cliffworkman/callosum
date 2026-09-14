<!-- qa-coverage
api: /axes/{axis_id}/ask-scope
fe: 15c_axis_ask.jsx, 20d_scoped_ask.jsx
-->

# ROUTE 96 — Axis-scoped Ask ("ask across a semantic axis")

**Tier:** 2 (canonical Ask; provider AI when egress is on)
**Goal:** Exercise the axis-hosted Ask — an **ordinary production Ask with an explicit corpus boundary**, not a
new Ask. The axis card's **✦** action opens an interstitial that resolves the axis to a concrete paper set and
shows the corpus (a live paper count + a full-text-eligible count per tier) BEFORE running, then runs the
ORDINARY Ask: the request carries `{scope_type:"axis", axis_id, membership_tier, query, top_k:8}` and the router
resolves it to `scope_type:"papers"` with exactly the axis's eligible papers → the shared
`observeJobUntilTerminal` poller → the SAME result/evidence/failure components (`GroupedSummarySentences`,
`SynthesisFailure`, via `ScopedAskResult`) as Synthesize → Ask and reader Ask. Inc 602 (#82).
**The read-only `GET /axes/{axis_id}/ask-scope`** is the pre-run disclosure; the `/summarize` surface itself is
covered by `route_55_synthesis_verification`. The shared shell `20d_scoped_ask.jsx` is exercised here and by
`route_95_reader_ask` (reader Ask rides the same shell — one Ask interaction, two scope selectors).

## Environment

Clean seeded instance with an axis whose members have extracted chunks, plus **at least one full-text paper
OUTSIDE the axis** (the scope-falsification fixture). To exercise a real answer, **egress ON** with a provider
key; for the honesty/failure paths, **egress OFF**. Register console/pageerror/request listeners before nav.

## Standing assertions

- **Ordinary Ask, explicit boundary — no axis Ask variant.** The run MUST reach `POST /summarize` and resolve to
  `scope_type:"papers"` with exactly the resolved axis corpus. There is NO axis-specific retrieval, prompt,
  generator, verification, evidence schema, coverage calc, artifact type, or provenance representation. (The
  backend hard-boundary + provenance-snapshot invariants are pinned by `tests/test_axis_scoped_ask.py`.)
- **Hard corpus boundary (falsification).** A question whose answering fact lives in a full-text paper OUTSIDE
  the axis MUST NOT be answered from that paper — no citation may resolve to a non-member. A run never falls back
  to the whole library; a sparse-but-bounded answer is the correct outcome.
- **Scope legible before the run.** The interstitial shows the axis label and, per tier, `N papers · M with
  usable full text`. `M` uses the SAME retrieval eligibility as production Ask (`papers_with_usable_fulltext`),
  so the disclosed count and the actual retrieval corpus cannot drift. The **Ask** button is disabled when the
  selected tier's `eligible_count` is 0, with an honest reason shown — never a silent widen.
- **Preview vs execution (c4).** `GET /axes/{id}/ask-scope` is the CURRENT resolved count; the POST re-resolves
  at execution and the persisted run records the EXACT executed set (`scope_ref_json.paper_ids` +
  `scope_origin={kind:"axis",id,label,policy}`). A membership change after a run never rewrites a historical
  run's corpus.
- **Faithful tier wording (c6).** Default is **Assigned only** (excludes uncertain); **Include uncertain** adds
  the below-cutoff "candidate to confirm" tier. Copy must NOT imply "Assigned" means researcher endorsement — it
  is the axis's similarity/display tier. No node/multi-axis/boolean/WIP scope in v1.
- **Empty scope is honest, never widened.** An axis with no members (or no full text) → an honest interstitial
  state and (on a direct POST) a 422; retrieval is never broadened to the library.
- **Explicit egress.** `/summarize` fires ONLY on the explicit **Ask** click (or Ctrl/Cmd+Enter). Opening the
  interstitial and reading counts issues **0** `/summarize`. The `/axes/{id}/ask-scope` GET is local/no-genai.
- **Failure stays failure.** A backend/provider failure renders the canonical `SynthesisFailure` (working **Open
  Settings** on the AI-off case); `sentences.length === 0` → the canonical "No groundable summary produced…".
  Coordinate honesty inherited unchanged from `CitationCard`.
- **No scope leakage.** Running axis Ask does not change the Library selection, the Synthesize scope, or any
  saved-search/focus state.

## Adversarial checklist

- Open the interstitial, do NOT submit → **0** `/summarize`; the `ask-scope` GET is local (no genai host)
- Toggle Assigned only ↔ Include uncertain → the count line changes; the toggle never issues `/summarize`
- Submit → exactly one `/summarize` with `scope_type:"axis"`, the chosen `membership_tier`, `top_k:8`
- Falsification: ask a question answerable only by a full-text NON-member → no citation resolves to that paper
- Empty axis / no-full-text tier → **Ask** disabled with an honest reason; a direct POST → 422 (not widened)
- Egress OFF (or provider error) → canonical `SynthesisFailure`; **Open Settings** works
- Membership change after a run → the prior run's persisted `scope_ref_json.paper_ids` is unchanged
- Narrow/mobile width → the interstitial + result are usable (responsive `axis-modal`)
- ~50KB pasted into the question field; empty/whitespace-only submit blocked

## Steps

1. Open the Axes panel. On an axis with members, confirm the **✦** ("Ask a question across this axis's papers")
   action. Click it → the interstitial opens with "Asking across: {label}" and both tier count lines.
2. Confirm no `/summarize` fired. Toggle the tier → the `N papers · M with usable full text` line updates.
3. Submit a question (egress ON) → one `POST /summarize` with `{scope_type:"axis", axis_id, membership_tier,
   query, top_k:8}`; the answer + evidence render via `GroupedSummarySentences`; open a citation → the correct
   member paper's PDF opens.
4. **Falsification:** with a discriminating question whose fact is only in a full-text NON-member, confirm no
   citation resolves to that paper and the answer stays bounded to the axis.
5. Point at an empty axis (or a tier with `eligible_count` 0) → **Ask** is disabled with an honest state; a
   direct `POST /summarize {scope_type:"axis"...}` returns 422 and never widens.
6. Turn egress OFF → submit → canonical `SynthesisFailure`; **Open Settings** navigates to Settings.
7. Add a paper to the axis after a completed run → confirm the prior run's persisted corpus is unchanged.

## Pass criteria

- Axis Ask is provably ordinary Ask with an explicit, legible corpus boundary (same endpoint/poller/result+
  failure components; resolves to `scope_type:"papers"`); the hard boundary holds under falsification; scope is
  disclosed before the run with retrieval-exact counts; empty/no-full-text states are honest and never widened;
  explicit egress; provenance snapshot survives membership change; no scope leakage.
- 0 console/page errors; no genai-host requests with egress unset.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_96_axis_ask.md` + `screenshots/` (see `_TEMPLATE.md`).
