# Security audit — analytic-flexibility surfacing (backlog #37)

**Date:** 2026-08-17
**Status:** complete — PASS

## Scope

The whole 12-task analytic-flexibility-surfacing plan's security-relevant surface, reviewed together at the
plan's close (Task 12), covering:

- `app/backend/pdf_processing/quote_matching.py::anchor_quote` — a deterministic, local, no-network quote
  locator (Task 1) that classifies a candidate quote's coordinate honesty (`exact` / `region` / `unanchored`)
  against an already-resolved on-disk PDF path. Never fetches anything, never accepts a request-supplied path.
- `integrations/gemini/analytic_flexibility_assistant.py` — the egress-gated LLM assistant (Task 2) that
  proposes `{category, quote}` candidates from methods-section text over the existing, already-audited
  `llm/providers.py::complete()` seam. No new provider, no new wire protocol.
- `app/backend/citations/section_scope.py::paper_methods_text` (Task 3, Library) and
  `app/backend/wip/analytic_flexibility_text.py::wip_methods_text` (Task 5, WIP) — pure local text assembly
  from already-extracted chunks/blocks. No new file read, no new external fetch.
- `app/backend/analytic_flexibility.py` + `app/backend/api/routers/analytic_flexibility.py` — the Library
  orchestration module and its single `POST /papers/{paper_id}/analytic-flexibility` endpoint (Task 4).
- `app/backend/api/routers/wip_checks.py`'s `analytic_flexibility_run` — the WIP orchestration endpoint
  `POST /wip/manuscripts/{manuscript_id}/checks/analytic-flexibility` (Task 6), reusing the pre-existing
  `require_local_wip` dependency (loopback-only, no change).
- `app/backend/persistence/findings_repo.py` (Library `paper_findings`, unmodified by this plan beyond being
  called) and `app/backend/persistence/wip_checks_repo.py::store_analytic_flexibility_run` (Task 6/7) — the
  `wip_findings.coordinate_precision` CHECK-constraint mapping.
- `app/backend/api/routers/findings.py` — one additive, optional `?source=` query parameter on the existing
  `GET /papers/{paper_id}/findings` endpoint (Task 7/9), no new endpoint.
- `app/frontend/js/08n_methods_analytic_flexibility.jsx` (Task 9, Library Checklists panel),
  `app/frontend/js/10k_wip_checks.jsx`'s `WipAnalyticFlexibilitySection`/`WipAnalyticFlexibilityResult`
  (Task 10, WIP Checks-tab panel), `app/frontend/js/04c_status.jsx` (Status wiring), and the `FindingCard`
  fix in `app/frontend/js/08x_methods_critical.jsx` (Task 8).
- No new migration — `wip_findings`/`paper_findings`/`tool_runs`/`wip_tool_runs` are all pre-existing tables;
  this feature only adds a new `source`/`tool_id` value into rows shaped exactly like every sibling Checklists
  tool.

## Principles-gate note (rule #9)

This feature is the first Checklists-family tool that is LLM-assisted rather than deterministic/local — the
gate's live worked example is PRINCIPLES.md's "AI funnel, human filter" pattern (the assisted-extraction
funnel, inc 259) rather than any of the deterministic auditors (statcheck/transparency/LMM/Bayes/meta-analysis)
its own sibling panel groups it with. Verified directly against the code, not asserted: the model's structured
output is `{category, quote}` only (`analytic_flexibility_assistant.py:52`, the fixed prompt) — it never emits
a page, bbox, or confidence value. Every quote is then anchored **after** the model call, entirely locally, by
`anchor_quote` (`app/backend/analytic_flexibility.py:54-58`, `wip_checks.py:302-308`) — the model has no
opportunity to assert a location, honoring invariant #2 structurally, not just by convention. Candidates persist
as `kind="candidate", tier="speculative"` (Library) / `kind="candidate", disposition="open"` (WIP) — never a
`fact` — so a human review step is required before anything is treated as established (PRINCIPLES.md's
fact-vs-candidate distinction). The one genuinely new inspectability question this audit re-verified rather
than took on faith: does the UI ever imply an aggregate (a count, index, or "flexibility score")? **Verified
NO** — `08n_methods_analytic_flexibility.jsx`'s own header comment states "No count, index, tally, or aggregate
score appears anywhere in this panel, by design" (line 8) and the rendered copy repeats the same point three
separate times (lines 47, 84-85, 97); read directly, not merely quoted from the comment.

## Threat review

### 1. Zero new external-fetch surface

**Confirmed by direct trace of every network-capable call in this feature.** The only network call anywhere in
this plan is the existing, already-audited `llm/providers.py::complete()` seam
(`analytic_flexibility_assistant.py:42`) — the same dispatch every other LLM feature in the codebase already
routes through (gemini-SDK / `/v1/messages` / `/v1/chat/completions` / `/v1/responses`, all via plain `httpx.post`,
confirmed by direct read of `providers.py:252`). Note this seam is a pre-existing gap, not one this feature
introduces or widens: inc 480's response-size caps (`integrations/http_bounds.py`) were wired into the 15
metadata-lookup/mirror-download adapters, not into `complete()`'s own provider-completion calls — those are a
different response shape (a conversational completion, not a metadata/mirror-download fetch) that inc 480's own
scope never claimed to cover. Out of scope for this audit (this feature adds no new call site to `complete()`
beyond what every other LLM feature already has), but worth naming rather than silently passing over.
`anchor_quote`, `paper_methods_text`, and `wip_methods_text` are all pure local functions with no `httpx`/
`requests`/socket call anywhere in their modules (confirmed by direct read of all three files — none imports
any HTTP client). No new integration, no new adapter, no new third-party dependency.

### 2. Zero new file-read surface — reuses existing trusted-path resolution

**Library side:** `primary_pdf_path` (`app/backend/workbench_assist.py:173-193`, called unchanged from
`analytic_flexibility.py:49`) resolves a PDF path **only from the paper's own trusted attachment rows** — its
own docstring states this explicitly ("resolved ONLY from its trusted attachment rows (rule #4) — never from a
request-supplied path"). The endpoint (`routers/analytic_flexibility.py`) takes no path parameter of any kind;
`paper_id` is the only input, and it is used solely as a DB lookup key.

**WIP side:** `wip_checks.py:297-301` resolves the manuscript's PDF via `trusted_child(manuscript["root_path"],
prepared.relative_path)` — both arguments come from server-side state (`get_manuscript`'s DB row and
`prepare_snapshot`'s already-registered file identity), never from the request body. `trusted_child`
(`app/backend/wip/paths.py:25-33`) resolves the candidate path and calls `candidate.relative_to(root_path)`,
raising `ValueError` on any containment escape (a `../` traversal or a symlink resolving outside the root)
before the path is ever handed to `anchor_quote`/`fitz.open`. This is the same helper every other WIP file-read
path in the codebase already uses — no new resolution logic was written for this feature.

**Negative-path check (code-inspected, not merely asserted):** a manuscript whose registered primary file is
non-PDF short-circuits before `trusted_child` is even called (`Path(prepared.relative_path).suffix.casefold()
== ".pdf"` gate at `wip_checks.py:299`) — `pdf_path` is `None`, `anchor_quote` never runs, and the candidate is
honestly `anchor_state="unanchored"` (see item 4). `test_analytic_flexibility_run_maps_unanchored_to_null_
coordinate_precision` (`tests/test_wip_analytic_flexibility_checks.py:52-97`) exercises exactly this path with
a real `.md` file and confirms it end-to-end (200 response, `anchor_state == "unanchored"`,
`coordinate_precision is None`).

### 3. Egress-gate ordering — verified to win over both a missing-record 404 and any local scoping work

**Library** (`routers/analytic_flexibility.py:34-36`): `GeminiConfig.from_environment()` +
`requires_egress(config) and not config.data_egress_enabled` is the **first** statement in the handler body,
before `get_paper(conn, paper_id)`. `test_endpoint_refused_when_egress_not_consented`
(`tests/test_analytic_flexibility.py:102-109`) posts against paper id `1` in a fresh, empty temp DB and still
gets **403**, not 404 — re-run live in this audit (see Negative-path checks below), not taken on the test
file's word alone.

**WIP** (`wip_checks.py:260-262`): the identical check is the first statement in `analytic_flexibility_run`,
before `get_manuscript` is even called. `test_analytic_flexibility_run_refuses_before_any_network_call_when_
egress_off` (`tests/test_wip_analytic_flexibility_checks.py:100-109`) posts against manuscript id `1` in a
fresh DB and gets **403**. A second WIP-specific test,
`test_analytic_flexibility_run_missing_manuscript_short_circuits_before_llm_work`
(`tests/test_wip_analytic_flexibility_checks.py:112-118`), separately confirms the ordinary 404 path (egress
consent granted by the suite's default fixture, manuscript genuinely absent) never reaches
`AnalyticFlexibilityAssistant.propose` — the assistant is deliberately left unmocked in that test, so any
accidental network attempt would fail loudly rather than silently pass.

Both endpoints additionally carry a defense-in-depth catch (`DataEgressDisabledError` → 403) around the
downstream call in case the pre-check and the assistant's own internal check (`analytic_flexibility_
assistant.py:39-41`) ever drift out of sync — the same double-gate pattern `routers/grobid.py` established and
this plan explicitly mirrors (both routers' own comments cite `grobid.py`'s ordering directly).

### 4. Coordinate-honesty contract — `anchor_quote` never fabricates a location; `unanchored`→NULL preserves detail

`anchor_quote` (`quote_matching.py:139-163`) has exactly three return shapes, all traced directly:
- Quote not found in the PDF at all → `anchor_state="unanchored"`, `bbox_json=None`. The `page` field carries
  through only `claimed_page` (a caller-supplied *fallback*, always `None` in this feature — neither call site
  passes one) — never a page invented from the search itself.
- Quote found but no line rectangles resolved (a `_line_rectangles` degenerate case) → `anchor_state="region"`,
  `bbox_json=None`, real matched page.
- Quote found with resolvable rectangles → `anchor_state="exact"`, `bbox_json` = the real matched rectangle
  list, real matched page.
There is no fourth path and no code path that sets `bbox_json` to a non-`None` value without `rectangles`
actually being non-empty. When no PDF exists at all (WIP non-PDF file, or a Library paper whose
`primary_pdf_path` returns `None`), both call sites construct the anchor dict **inline** with
`anchor_state="unanchored"` themselves (`analytic_flexibility.py:57`, `wip_checks.py:306`) — `anchor_quote` is
never even called, so there is no path where a missing PDF could produce a false `exact`/`region` result.

**The `wip_findings.coordinate_precision` CHECK-constraint mapping** (`schema_wip_provenance.py:100-103`
constrains it to `NULL | 'exact' | 'region'` — no `'unanchored'` literal). `store_analytic_flexibility_run`
(`wip_checks_repo.py:374`) maps `anchor_state != "unanchored"` straight through, and `"unanchored"` → `None`,
with an inline comment explaining exactly why. **Verified this does not silently drop information**: the full,
un-narrowed `candidate` dict (including the real `anchor_state` value) is written unmodified into
`details_json` (`wip_checks_repo.py:368`, `details_json=candidate`) — confirmed by
`test_analytic_flexibility_run_maps_unanchored_to_null_coordinate_precision`, which asserts **both**
`finding["details_json"]["anchor_state"] == "unanchored"` **and** `finding["coordinate_precision"] is None` in
the same test, i.e. the narrower column is NULL while the fuller value stays inspectable one field over. The
Library side has no equivalent constraint problem — `paper_findings` has no `coordinate_precision` column at
all; `anchor_state`/`page`/`bbox_json` live inside its own free-form `payload` JSON blob
(`analytic_flexibility.py:67-70`), so no narrowing happens there in the first place. The `FindingCard` fix
(Task 8, `08x_methods_critical.jsx:39-41`) is what makes the Library side's `exact` anchors reach the UI
correctly — before this fix, every candidate's "show in paper" action hardcoded `precision: "region"`
regardless of the payload's real `anchor_state`, which would have **understated** this feature's own `exact`
anchors (never overstated a `region`/`unanchored` one as `exact` — the fix is a correctness improvement in the
safe direction, not a coordinate-honesty regression that was live before it).

### 5. LLM output is untrusted input — defensive parsing verified against real malformed shapes

`parse_proposals` (`analytic_flexibility_assistant.py:60-80`) is the single entry point for the model's raw
text response. Traced every failure mode:
- Non-JSON garbage (`"not json at all"`), empty string, and a bare `"{}"` (valid JSON, wrong shape) all yield
  `[]`, never an exception — re-run live in this audit (see below), matching
  `test_parse_proposals_never_raises_on_garbage`.
- An item whose `category` is outside the fixed 5-value `ANALYTIC_FLEXIBILITY_CATEGORIES` frozenset is dropped
  silently, not coerced to the nearest valid value or passed through — re-run live with a fabricated
  `"researcher-freedom-index"` category (see below), matching
  `test_parse_proposals_drops_invalid_category_not_raises`. This is the closed-taxonomy invariant named in the
  task brief, verified directly rather than inferred from the frozenset's existence alone.
- An item missing `quote`, or whose `quote` is not a non-blank string, is dropped, not defaulted to an empty
  string that would later reach `anchor_quote` with nothing to search for.
- Markdown code-fence wrapping (`` ```json\n[...]\n``` ``, a common real-world LLM response shape) is stripped
  before parsing, and a JSON array embedded in surrounding prose is extracted by locating the outermost `[`/`]`
  span — both defensive, not required for correctness of a well-behaved provider, but bound the damage an
  unusual or adversarial custom-provider endpoint (any user can point the roster at an arbitrary
  OpenAI-compatible URL) could do beyond "produces fewer or zero candidates."
- Every quote is length-capped at `MAX_QUOTE_CHARS=4000` and the list capped at `MAX_CANDIDATES=12`
  (`analytic_flexibility_assistant.py:27-28`) — bounds a pathological or hostile response from producing an
  unbounded number of DB rows or an oversized single payload, mirroring the same shape
  `extraction_assistant.py`'s sibling parser already uses.

No code path in `parse_proposals` can raise past its own boundary — every dict/string type-check uses
`isinstance`, and the only `try/except` (`_loads_lenient`) catches exactly `ValueError`/`TypeError`, the two
`json.loads` can raise, converting to `None`/`[]` rather than letting a `json.JSONDecodeError` propagate to the
caller.

### 6. SQL injection / parameterization (rule #3)

`analytic_flexibility.py`, `wip_checks_repo.py::store_analytic_flexibility_run`, and `findings_repo.py` all use
SQLAlchemy Core (`insert().values(...)`, `select(...).where(...)`) exclusively — confirmed by direct read, no
string-built SQL anywhere in the new/touched code. The new `?source=` query parameter on
`GET /papers/{paper_id}/findings` (`routers/findings.py`) is passed straight into
`get_paper_findings(conn, paper_id, source=source)`, which uses it only as a bound `.where(paper_findings.c.
source == source)` predicate (`findings_repo.py:86`) — never string-interpolated, and an unrecognized value
simply matches zero rows rather than erroring or exposing anything.

### 7. Resource caps on the operation itself

Both endpoints process exactly one paper/manuscript's text per call — no unbounded loop, no batch mode.
`paper_methods_text`/`wip_methods_text` both cap at `max_chars=20000` before the prompt is built
(`section_scope.py:70`, `analytic_flexibility_text.py:26`); the assistant caps candidates at 12 and quote
length at 4000 chars (item 5). `anchor_quote` runs at most once per surfaced candidate (≤12 times per request),
each a bounded local PDF text search over an already-open-and-closed-per-call `fitz.open` — the same per-call
cost every other quote-anchoring call site in the codebase (`workbench_assist.py::anchor_proposal`) already
accepts.

### 8. Data exposure / secret handling

No secret is introduced by this feature. `GeminiConfig.from_environment()` is the same unmodified accessor
every other LLM feature already uses; no key is logged, returned in a response, or persisted anywhere new. The
persisted candidate payload (Library `payload` JSON / WIP `details_json`) contains only `category`, `quote`
(verbatim text already present in the user's own PDF/manuscript — not new exposure), `anchor_state`, `page`,
`bbox_json`, and `reason` — no prompt, no raw model response, no file path (confirmed by direct read of both
`propose_analytic_flexibility` and `wip_checks.py`'s candidate-assembly loop).

## Negative-path checks (executed, not assumed)

Re-ran the following directly in this audit session, not taken on the implementers' word:

```
pytest tests/test_quote_matching.py tests/test_analytic_flexibility_assistant.py tests/test_section_scope.py \
       tests/test_analytic_flexibility.py tests/test_wip_analytic_flexibility_text.py \
       tests/test_wip_analytic_flexibility_checks.py tests/test_wip_checks.py tests/test_frontend_assembly.py -v
```
Result: **122 passed**, 0 failed, 0 skipped, no regressions in `test_wip_checks.py`'s 16 pre-existing tests
(statcheck/transparency/LMM/Bayes/meta-analysis, unrelated to this feature but sharing the same repo module).
Separately also ran `tests/test_findings.py` (touched by this plan's additive `?source=` query parameter but
not part of the brief's Step-2 command) — **8 passed**, including the two new source-filter tests
(`test_get_paper_findings_source_filter`, `test_findings_endpoint_source_query_param`), confirming the
unfiltered/backward-compatible path is unchanged alongside the new scoped-read behavior.

Specific negative-path assertions confirmed by this run:
- **Malformed/garbage LLM JSON** (`test_parse_proposals_never_raises_on_garbage`) → `[]`, never a crash.
- **Invalid category** (`test_parse_proposals_drops_invalid_category_not_raises`) → the offending item is
  dropped; the well-formed sibling item in the same array survives.
- **Egress off, Library** (`test_endpoint_refused_when_egress_not_consented`) → 403 against a nonexistent
  paper id, confirming the gate wins over a 404.
- **Egress off, WIP** (`test_analytic_flexibility_run_refuses_before_any_network_call_when_egress_off`) → 403
  against a nonexistent manuscript id, same ordering.
- **Non-loopback WIP request** (`test_analytic_flexibility_route_remains_local_only`) → 403 via the pre-existing
  `require_local_wip` dependency, `host: example.com` header.
- **Paper/manuscript with no methods text** — Library:
  `test_propose_analytic_flexibility_reports_no_methods_text_honestly` (the assistant is deliberately left
  unmocked; a real network attempt would fail loudly if the short-circuit didn't hold) →
  `{"candidates_found": 0, "methods_text_found": False}`. WIP:
  `test_analytic_flexibility_run_missing_manuscript_short_circuits_before_llm_work` → 404 before any snapshot/
  LLM work, same unmocked-assistant guard.
- **`unanchored` → NULL CHECK-constraint mapping with full detail preserved**
  (`test_analytic_flexibility_run_maps_unanchored_to_null_coordinate_precision`) → `coordinate_precision is
  None` **and** `details_json["anchor_state"] == "unanchored"` asserted in the same test.

Also independently spot-checked outside the test suite, against the real current code (not re-deriving from
the tests' own assertions):
```python
from integrations.gemini.analytic_flexibility_assistant import parse_proposals
parse_proposals('[{"category": "researcher-freedom-index", "quote": "x"}, {"category": "outcome-choice", "quote": "y"}]')
# -> [{'category': 'outcome-choice', 'quote': 'y'}]   (the invalid-category item silently dropped, not coerced)
parse_proposals("<html>not json</html>")
# -> []
```

## Result

Every threat category named in the task brief was traced to real, current code rather than accepted on the
implementers' summary: zero new external-fetch surface (only the pre-existing, already-audited `complete()`
seam is ever called), zero new file-read surface (both call sites resolve a PDF path exclusively through
already-trusted mechanisms — `primary_pdf_path`'s attachment-row lookup and `trusted_child`'s containment
check — never a request-supplied path), the egress gate fires before any paper/manuscript lookup on both
endpoints (confirmed to win over a 404, matching the `grobid.py` precedent both routers cite), `anchor_quote`
structurally cannot fabricate a location (traced all three return shapes plus both no-PDF inline fallbacks),
and the `unanchored`→NULL CHECK-constraint narrowing on the WIP side is confirmed lossless — the fuller
`anchor_state` value survives unmodified in `details_json`. No new dependency, no new migration, no SQL
built from string interpolation anywhere in the touched code. No finding rises to a severity requiring a fix
or a disclosed-and-accepted risk entry — this audit closes clean.

**Security Audit: PASS**
