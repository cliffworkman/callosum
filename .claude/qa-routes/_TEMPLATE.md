<!-- qa-coverage
api:
fe:
-->
<!--
TEMPLATE — copy to route_NN_<name>.md and fill in. The NN encodes complexity order
(00–09 = Tier 0 read-only smoke; 10–49 = Tier 1 local stateful; 50+ = Tier 2 egress/external).
Fill the qa-coverage block above with the surface ids this route exercises:
  api: GET /papers, POST /papers/export, /papers/{paper_id}/*   (exact id, bare path, or trailing-* glob)
  fe:  10_pdf_layer.jsx, 25_detail.jsx#L42                       (whole chunk, or chunk#Lnn)
Run `python tools/qa/build_surface_map.py check` to see what's still uncovered.
-->

# ROUTE NN — <human title>

**Tier:** <0 read-only | 1 local-stateful | 2 egress/external>
**Goal:** <one sentence — what end-user surface this route exhausts>

## Environment (every route is self-contained — assume a cold agent)

You are a meticulous QA tester for **callosum**, a local-first, single-user, AI-assisted reference
manager for scholarly PDFs. Stand up a clean instance and drive it in a real browser:

1. From the repo root, create a throwaway DB and seed it (mirror `tests/e2e/test_smoke.py`):
   - `python -m alembic upgrade head` against a temp `sqlite:///` set in `CALLOSUM_DB_URL`, then seed
     via `tests.api_helpers._seed_library`. (A helper `tools/qa/_qa_serve.py` is provided — see the
     build guide — that does spin-up + seed + free-port + teardown; call it if present.)
   - **Keep `CALLOSUM_ALLOW_DATA_EGRESS` UNSET** unless this route is explicitly a Tier-2 egress route.
2. Start `uvicorn app.backend.api.app:app` on a free `127.0.0.1` port; wait for `/health` 200.
3. Open `/` in headless Chromium via Playwright. Register listeners BEFORE navigating:
   - `page.on("console", …)` — collect every `type=="error"`.
   - `page.on("pageerror", …)` — collect every uncaught error.
   - `page.on("request", …)` — collect every outbound URL (for the egress assertion).

## Reporting format (every issue)

1. **Severity:** Critical / High / Medium / Low / Visual (see `.claude/QA-POLICY.md` rubric)
2. **Location:** exact route surface id + URL/component
3. **Steps to reproduce:** numbered, replayable
4. **Expected vs Actual:** include exact error text / console errors / what the screenshot shows
5. **Evidence:** screenshot filename under `screenshots/`

## Standing assertions (apply to EVERY step)

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.** Any visible control that can't be completed through the UI is a bug.
- **Egress gate.** With egress unset, **any** request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` → bbox rect; `region` → scroll + note; `null` → page-open, no rect.
  An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist (the curious, motivated end user)

Apply the relevant ones to this route's surfaces:

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected (bad DOI on re-resolve, garbage file on import/scan)
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh — no horizontal overflow

## Steps

1. <baseline screenshot>
2. <surface-by-surface walk — every button, field, dropdown, toggle declared in qa-coverage>
3. …

## Pass criteria

- Every declared surface exercised and reachable.
- 0 console errors / 0 page errors.
- No unexpected 4xx/5xx.
- All standing assertions hold.
- Mobile viewport: no horizontal overflow.

## Deposit (REQUIRED — this is how the supervisor knows you finished)

Write your consolidated, severity-ordered report to:

    .claude/qa-inbox/<RUN_ID>/route_NN_<name>.md

and put all screenshots under:

    .claude/qa-inbox/<RUN_ID>/screenshots/

`<RUN_ID>` is provided in the dispatch prompt. Lead the report with Critical/High; collapse the rest.
