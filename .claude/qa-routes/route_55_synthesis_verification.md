<!-- qa-coverage
api: /summarize*, /summaries*
fe: 19_synthesis_failures.jsx, 20_synthesis.jsx
-->

# ROUTE 55 - Synthesize → Ask and verification

**Tier:** 2 egress/external
**Goal:** Exhaust summary generation, polling, persisted summary browsing/deletion, verification/citation honesty,
and the inc-124 evidence-traceable Overview (a narration OF the verified claims, with per-sentence trace links).

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Run hermetically by default:** stand up the app through `create_app(...)` with an injected fake summary generator/support scorer/vector dependencies so the route does not call Gemini or external services. Keep `CALLOSUM_ALLOW_DATA_EGRESS` unset unless running an explicit real-provider integration pass. Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.
- **Contradicted = signal, not a "false" verdict (inc 203, A9).** A citation whose source actively disagrees shows
  the distinct `contradicted` pill ("⚠ source disagrees", red `.cite-status.contradicted`) **with** its quote/page/
  confidence like any other evidence — never a pronouncement that the claim is false. A contradicted citation
  presented WITHOUT its evidence, or as a true/false verdict, is **High**. (Hermetically: a `support_scorer` exposing
  `support_and_contradiction()` with contradiction > support ≥ 0.55 → the cited sentence's status is `contradicted`.)

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open **Synthesize → Ask** (`20_synthesis.jsx`) and existing summaries (`GET /summaries`). Confirm empty/list states.
2. Generate a paper-scope summary (`POST /summarize`) using the fake generator. Poll (`GET /summarize/{job_id}`) through completion; navigate away mid-job and return.
   - **inc 145 (Skeptical synthesizer):** select papers in the Library → the selection bar shows a **"Focus on…" input**; typing a question + **summarize** sends `scope_type:"papers"` **with `query=<focus>`** (a query-RANKED synthesis of just the selection) and the Synthesize → Ask scope-note reads "… · focused on '…'" (the focus also reflects into the Ask textarea). Blank focus → a general selection summary (no `query`). Confirm the focus is honest — it ranks coverage, never fabricates a claim the evidence doesn't support.
3. Generate cluster and query summaries, including an empty/whitespace query. Confirm validation and no orphaned spinners.
4. Open persisted summary detail (`GET /summaries/{summary_id}`). Confirm every sentence shows visible verification status and every citation shows confidence, quote, page, and coordinate precision.
5. Click citations. Assert exact/region/null coordinate honesty in the PDF viewer.
6. **Overview (inc 124):** with a fake overview generator injected (and a verified sentence), confirm a summary's
   `overview` renders **above** the verified claims, labeled **"Overview — synthesized from the verified claims
   below"** (NOT "authoritative"); each Overview line shows its trace refs `[n]` and clicking it
   scrolls-to/flashes the verified claim(s) it restates. Assert every Overview line traces to >=1 verified claim
   and presents no claim the verified set doesn't support (signal-not-verdict; the Overview is secondary to the
   evidence, never on its own authority).
7. **Overview egress + degenerate:** with `CALLOSUM_ALLOW_DATA_EGRESS` unset (no overview generator), confirm a
   summary has **no** overview and the verified claims stand alone — and zero genai-host requests. A summary with
   0 verified claims shows no overview.
8. Delete a disposable summary (`DELETE /summaries/{summary_id}`) and confirm it disappears from the list.
9. In a separate egress-unset negative pass without fake generator, trigger summarize and confirm a graceful egress-disabled/provider-required message and zero genai network requests.
10. **Failure recovery actions.** Force representative synthesis failures and confirm the pane shows actionable recovery without hiding the technical detail:
    - egress/key failure -> **Open Settings**.
    - malformed cached citation id / `chunk_1`-style error -> **Repair cache and retry** (`POST /settings/repair-summary-cache`) then retries the same request.
    - no retrievable/source chunks -> **Open Text Health**. If the failed synthesis came from a selected-paper
      scope, Text Health opens scoped to those source papers, offers **Show all text-health items** / **Return to
      synthesis scope**, shows **Reprocess scoped papers** only for scoped papers with missing section labels or stale
      extraction, and after a reprocess completes offers **Retry synthesis** for the same request.
      Before opening Text Health, Synthesize → Ask should show a compact diagnostic such as selected-paper count,
      no local PDF, no extracted text, stale extraction, or missing section labels; query/all-library zero-source
      cases should say no source chunks matched the query or active section filter.
    - provider timeout/rate/HTTP failure -> **Retry** plus an optional Settings link.
    The wording must not say the repair verified, improved, or certified the synthesis; it only removes malformed cached AI draft rows or routes the user to existing maintenance surfaces.

## Pass criteria

- Summary start, polling, persisted detail, citation navigation, and delete complete.
- Hermetic default uses injected fakes; no genai-host requests with egress unset.
- Verification is always visible; no hidden composite reproducibility score or verdict language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_55_synthesis_verification.md` + `screenshots/` (see `_TEMPLATE.md`).
