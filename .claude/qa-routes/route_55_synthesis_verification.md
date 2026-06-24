<!-- qa-coverage
api: /summarize*, /summaries*
fe: 20_synthesis.jsx
-->

# ROUTE 55 - Synthesis and verification

**Tier:** 2 egress/external
**Goal:** Exhaust summary generation, polling, persisted summary browsing/deletion, and verification/citation honesty.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Run hermetically by default:** stand up the app through `create_app(...)` with an injected fake summary generator/support scorer/vector dependencies so the route does not call Gemini or external services. Keep `CALLOSUM_ALLOW_DATA_EGRESS` unset unless running an explicit real-provider integration pass. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open the Synthesis pane (`20_synthesis.jsx`) and existing summaries (`GET /summaries`). Confirm empty/list states.
2. Generate a paper-scope summary (`POST /summarize`) using the fake generator. Poll (`GET /summarize/{job_id}`) through completion; navigate away mid-job and return.
3. Generate cluster and query summaries, including an empty/whitespace query. Confirm validation and no orphaned spinners.
4. Open persisted summary detail (`GET /summaries/{summary_id}`). Confirm every sentence shows visible verification status and every citation shows confidence, quote, page, and coordinate precision.
5. Click citations. Assert exact/region/null coordinate honesty in the PDF viewer.
6. Delete a disposable summary (`DELETE /summaries/{summary_id}`) and confirm it disappears from the list.
7. In a separate egress-unset negative pass without fake generator, trigger summarize and confirm a graceful egress-disabled/provider-required message and zero genai network requests.

## Pass criteria

- Summary start, polling, persisted detail, citation navigation, and delete complete.
- Hermetic default uses injected fakes; no genai-host requests with egress unset.
- Verification is always visible; no hidden composite reproducibility score or verdict language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_55_synthesis_verification.md` + `screenshots/` (see `_TEMPLATE.md`).

