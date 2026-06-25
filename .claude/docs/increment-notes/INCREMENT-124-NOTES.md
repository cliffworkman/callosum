# Increment 124 — synthesis evidence-traceable Overview (Part B)

Part B of the inc-123/124 synthesis-overview design
(`.claude/docs/specs/2026-06-25-synthesis-overview-design.md` §3). Completes the user's "synthesis should provide
a summary, too" request: a synthesis now shows a short **Overview** above the verified claims — a narration *of
the verified claims* where **each Overview sentence links back to the verified claim(s) it restates**. (Part A,
inc 123, made the verified claims real body text rather than mastheads.)

## Implemented

- **`app/backend/summarization/overview.py`** — `OverviewSentence{text, claim_indices}`, the `OverviewGenerator`
  Protocol, and `FakeOverviewGenerator` (hermetic tests).
- **`integrations/gemini/overview.py`** — `GeminiOverviewGenerator` (mirrors `research_summary.py`): prompts over
  NUMBERED verified claims, returns JSON `[{text, claim_indices}]`, parsed defensively (`_parse_overview_response`
  — drops non-dict items, empty text, non-list/non-int refs; caps counts/chars). `OVERVIEW_PROMPT_VERSION`.
- **`app/backend/llm/egress.py`** — `EgressGatedOverviewGenerator` (the inc-58 seam): library-derived text →
  rides the library egress gate.
- **`pipeline.py`** — `summarize_scope(..., overview_generator=None)` + `_maybe_store_overview`: after
  verification, collect the `status==verified` sentences (ordered), call the generator, **validate each
  `claim_indices` ⊆ the verified set**, map to those sentences' **ordinals**, and store
  `summaries.overview_json = [{text, claim_ordinals}]`. 0 verified → no overview; any generator error
  (egress-off included) → no overview (never fails the synthesis).
- **`summaries.overview_json`** column (schema.py + migration **0015**, guarded/additive; head derived by tests,
  inc 99). Exposed as `overview: [{text, claim_ordinals}]` on the summary response (`OverviewItemResponse`);
  `_overview_generator(api)` factory injects the egress-gated Gemini generator (or `None` without egress+key);
  `create_app(overview_generator=…)` + `_summarization_app(..., overview_generator=…)` seams for tests.
- **Frontend (`20_synthesis.jsx`)** — `OverviewBlock` renders above `GroupedSummarySentences` with the label
  **"Overview — synthesized from the verified claims below"**; each line shows trace refs `[n]` and on click
  `flashClaims` scrolls-to + flashes `#summary-claim-<ordinal>`. Each claim card gained that anchor id. CSS in
  `styles.css` (tokens only — `.synth-overview`/`.overview-line`/`.overview-trace`/`.claim-flash`).

## Key technical detail

- **Traceable, not "unverified blob"** (the user's refinement): the Overview narrativizes ONLY the verified
  claims, and its per-sentence `claim_indices` are validated and mapped to the verified sentences' ordinals — so
  every Overview line points at a real verified claim (which carries quote/page/confidence). Citations are
  **inherited from verified claims, never LLM-invented**; out-of-range refs are dropped, and a line left with no
  valid refs is dropped entirely.
- **Egress posture** (My-Pubs inc-81 pattern): the Overview pass sends library-derived text → egress-gated. With
  egress off, summary generation already raised upstream, so the Overview pass is never reached; the verified
  claims stand alone. No new external service (reuses the Gemini provider).
- **Principles gate (#9): aligned** — traceable-to-evidence, restates only verified claims, secondary/above the
  evidence, egress-gated, omitted when nothing verified. Audit `2026-06-25_synthesis-overview.md` **PASS**.

## Manual verification

- Hermetic: `tests/test_summary_overview.py` (column; Fake/egress/parse; pipeline storage with mapped ordinals +
  out-of-range drop + 0-verified→none; e2e response includes the traceable overview).
- Headed (no egress): `.local/visual/drive_inc124_overview.py` seeds an `overview_json` onto a verified saved
  summary and confirms the Overview renders **above** the claims with the right label, clicking a line flashes
  `#summary-claim-0`, and **0 console/page errors, 0 genai requests**.
- The **real Gemini overview prose quality** check is deferred to the user (needs egress + a key): enable egress
  and run a papers-scope synthesis.

## Pytest

449 passed, 1 skipped (440 + 9 new overview tests). `ruff` clean; QA surface check 0 uncovered (88 API / 462 FE).
