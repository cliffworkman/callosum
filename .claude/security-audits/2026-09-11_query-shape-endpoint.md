# Security audit — `POST /summarize/query-shape` (issue #30)

**Date:** 2026-09-11
**Scope:** one new API endpoint added for the Ask "How Ask reads your question" guidance — a
pre-submission query-shape classifier the frontend debounces against. Triggered by the audit gate
(#1 "a new API endpoint").

## What it is

`POST /summarize/query-shape` (`app/backend/api/routers/summaries.py`), body `{query: str}`, returns
`{routing: "narrow"|"broad_candidate", show_broadening_hint: bool}`. It runs **only** the two pure,
deterministic functions in `summarization/query_planner.py` (`classify_breadth`,
`broadening_hint_applies`) over the string and returns their result. It exists so the UI can disclose,
before submission, how a question would currently be routed, and show a gentle broadening hint for a
short/open-ended question.

## Threat review

- **Input validation (rule #4):** `QueryShapeRequest.query` is a pydantic `str` capped at
  `max_length=_QUERY_SHAPE_MAX_CHARS` (4000). An over-long body is rejected with 422 before any code
  runs (regression-tested). The classifier does only `.strip()/.lower()/.count()` and one linear
  `re.findall(r"\band\b", ...)` — all O(n) over a ≤4000-char string, so there is no
  catastrophic-backtracking or resource-exhaustion surface. No other field is accepted.
- **Data egress (invariant #3):** none. The endpoint calls **no LLM/provider** and makes **no network
  request** — it is not the planner (`plan_query`), only the deterministic pre-gate. A `generativelanguage`
  /Gemini request from this path would be a QA-Critical regression; route 55 asserts it.
- **Database / filesystem:** none. It reads no DB and touches no file; it needs no `Request`/app state.
- **Injection:** no SQL, no shell, no path construction — the string is only measured, never interpolated
  anywhere. Output is a fixed enum + bool (never echoes the input back).
- **Output encoding:** the response is a typed pydantic model with a `Literal` routing field and a bool;
  it cannot carry arbitrary or reflected content.
- **Auth/rate-limiting:** inherits the app-wide `AccessControlMiddleware` posture unchanged (local-only
  by default; behind the bearer gate when Remote access is on) — it is not added to any gate-exemption
  list, so it is as protected as every other endpoint. It is cheap and stateless; the existing sliding-
  window limiter covers it with no special handling.
- **Frontend `dangerouslySetInnerHTML`:** the `AskGuideModal` renders the served help corpus section's
  HTML the same way `18_help.jsx` already does. That HTML is **server-rendered from repo-authored
  markdown** (`help_content.md` → `corpus.py::render_html`), i.e. trusted first-party content, never
  user input — identical trust posture to the existing Help center. No new untrusted-HTML surface.

## Negative-path checks

- Over-long input (`"x"*5000`) → **422** (asserted in `tests/test_summaries.py::test_query_shape_endpoint_...`).
- Empty/whitespace query → `{"routing":"narrow","show_broadening_hint":false}` (no error, no work).
- Broad enumerated question → `broad_candidate`, hint false; short open-ended → `narrow`, hint true —
  deterministic, no provider call (hermetic test uses a fake generator app but the endpoint never calls it).

## Conclusion

The endpoint is a bounded, deterministic, read-only, zero-egress classifier over a length-capped string,
returning a fixed-shape enum+bool. No new data-egress, injection, or resource-exhaustion surface.

**Security Audit: PASS**
