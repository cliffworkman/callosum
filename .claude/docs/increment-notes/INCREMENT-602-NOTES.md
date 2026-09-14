# Increment 602 — Axis-scoped Ask (GitHub #82)

Reader paper-scoped Ask (inc 596) showed that narrowing Ask's retrieval universe to one paper markedly improves
pre-0.6 coherence. This adds the next scope rung — **one semantic axis → a resolved canonical paper set →
ordinary production Ask** — as both a real capability and a bounded test of the "corpus scoping is a major
Ask-quality lever" hypothesis, **without touching the frozen 0.6/0.7 experiment**.

**Core principle:** axis Ask is ordinary canonical Ask with an explicit corpus boundary. The axis changes WHICH
canonical papers are eligible, not HOW Ask reasons — there is **no** axis-specific prompt, retrieval, generator,
verifier, or evidence schema. The pipeline's `scope_type` Literal stays `papers|cluster_node|query`; "axis" is a
request/provenance concept resolved *above* the pipeline into the existing `scope_type="papers"` contract.

## Backend
- **`app/backend/clustering/axis_membership.py` (new, pure — the one place "which papers are in this axis" lives):**
  `axis_member_paper_ids_select(axis_id)` (correlated subquery for `.in_()`), `classify_member(confidence, cutoff)`
  (the exact `manual`/`assigned`/`uncertain` rule the axes read endpoint uses), `axis_cutoff(scoring_gain)`,
  `papers_with_usable_fulltext(conn, paper_ids)` (the EXACT Ask retrieval-eligibility clause —
  `attachment_document_role_clause(ARTICLE_DOCUMENT_ROLES)` + live filter), and
  `resolve_axis_corpus(conn, axis_id, tier, *, cutoff)` (`"assigned"` = manual+assigned; `"all"` adds uncertain).
- **c2 — actual shared code, not copied SQL:** `gapfinder.py`'s `_scoped_paper_rows`/`_scope_total` and
  `routers/axes.py`'s `_cluster_paper_response` now consume the shared resolver/classifier instead of inline
  copies of the inc-63 subquery + the tier rule.
- **c1 — generic run provenance:** `SummaryScope.scope_origin: dict|None` (additive; **only `to_ref()` reads it**,
  retrieval keys solely on `scope_type`). Persisted as `{kind:"axis", id, label, policy}` — a generic shape wip/
  idea can reuse via `kind`, never an axis-special field.
- **`routers/summaries.py`:** `SummarizeRequest` gains `scope_type="axis"` + `axis_id` + `membership_tier`
  (`"assigned"` default). `_resolve_axis_scope` resolves the axis → concrete paper set **at execution time**,
  404s a missing axis, **422s an empty scope (never widened to the library)**, builds the server-side
  `scope_origin`, and `model_copy`s to `scope_type="papers"`. The pipeline only ever sees a paper-id set.
- **`GET /axes/{axis_id}/ask-scope` (`routers/axes.py`):** read-only pre-run disclosure — both tiers'
  `{count, eligible_count}` in one call, so the interstitial toggles instantly and the count is honest.

## Frontend
- **`20d_scoped_ask.jsx` (new, c3 — shared Ask shell):** `useScopedAsk()` (POST /summarize →
  `observeJobUntilTerminal` → state machine + cleanup) and `ScopedAskResult` (the retrieved-chunk line, the
  incomplete notice, the honest no-groundable state, and the SAME `GroupedSummarySentences` as Synthesize → Ask).
  **Reader Ask (`30j_reader_ask.jsx`) was refactored onto it** (behavior-preserving) so there is one Ask
  interaction, two scope selectors — not a forked client.
- **`15c_axis_ask.jsx` (new):** `AxisAskModal` — an **interstitial** that shows the corpus before running
  (`N papers · M with usable full text` per tier), a tier toggle (**Assigned only** default; **Include
  uncertain**), honest empty / no-full-text states, then the shared shell. `AxisAskModalHost` is a self-hosted
  controller (the CriticalReadModalHost pattern) listening for `callosum:open-axis-ask`.
- **`15b_axis_card.jsx` / `15_axes.jsx`:** an **✦** "Ask this axis" action on the axis card → `handlers.askAxis`
  dispatches the window event (gated `!readOnly`, since Ask is a write).
- **`40d_modal_hosts.jsx` (new):** `AppEventModalHosts` groups the two self-hosted event-driven controllers
  (critical-read + axis-ask) so `40_app.jsx` stays ≤600 — a genuine "self-hosted modal controllers" concern
  split, not cap-gaming.

## Approved-constraint compliance (c1–c8)
- **c1** generic `scope_origin={kind,id,label,policy}` (not `axis_provenance`); retrieval never reads it.
- **c2** one shared membership/tier/eligibility implementation; gapfinder + the axes endpoint consume it.
- **c3** shared `useScopedAsk`/`ScopedAskResult`; reader Ask migrated onto it; each caller supplies only its scope.
- **c4** `ask-scope` GET = CURRENT resolved count; POST re-resolves at execution and snapshots the exact set into
  `scope_ref_json.paper_ids`; negligible race accepted, no locking subsystem.
- **c5** the "usable full text" count reuses the pipeline's own eligibility clause (`papers_with_usable_fulltext`),
  so disclosure and retrieval cannot drift.
- **c6** v1 boundary preserved (whole axis, one at a time, Assigned-only default + explicit Include-uncertain);
  wording faithful — "Assigned is the axis's similarity/display tier, not researcher endorsement."
- **c7** the scope-falsification test is a **pre-release manual gate for 0.5.15** (a separate task) — not claimed
  done here.
- **c8** the 0.5.15 release is a separate task after this is green, manually scope-falsified, and accepted.

## Gates
- **Security audit:** `2026-09-13_axis-scoped-ask.md` — **PASS** (local-only read endpoint, bound-param SQL, no
  new egress channel — axis Ask rides the existing `/summarize` egress gate, honest 404/422 fail-closed,
  server-side provenance, resource bound within the packaged `SQLITE_MAX_VARIABLE_NUMBER` at realistic scale with
  a documented shared-batching follow-up if libraries grow past it).
- **Principles (#9):** the hard corpus boundary is epistemic (retrieval genuinely narrows); scope is legible
  before the run; empty/partial states honest; no silent widening; provenance preserved; no new score/verdict.
- **Latency (#12):** no new per-item inference; scope resolution is one bounded SQL query per tier.
- **QA (#10):** `route_96_axis_ask.md` (declares `15c`/`20d` + the `ask-scope` endpoint); surface-map check green.
- **Tests:** `tests/test_axis_scoped_ask.py` (6 — tiers, retrieval-exact eligibility, endpoint both-tiers,
  provenance snapshot survives a membership change, empty-422, validation-400); assembly + reader-ask +
  axes + summarization + gapfinder + status regressions green (188 in the affected run); ruff + tach + line
  budget clean (40_app.jsx, pipeline.py, schema.py, app_settings.py all at exactly 600).

## Manual verification (owed — pre-release gate for 0.5.15, c7)
Run a **discriminating** question whose answering fact lives in a full-text paper OUTSIDE the axis; confirm the
scoped Ask does **not** use it (a bounded, sparser answer is correct). Toggle Assigned ↔ Include-uncertain and
confirm the count changes; confirm an empty / no-full-text axis shows the honest state and never widens.

Not part of a shipped release yet — rides the 0.5.15 cut (a separate task). 0.5.14 is immutable.
