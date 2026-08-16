<!-- qa-coverage
api: /grobid/*
fe: 35e_maintenance.jsx, 25a_detail_actions.jsx, 25_detail.jsx
-->

# ROUTE 91 - GROBID document structure (opt-in section parsing, backlog #30 Stage 2)

**Tier:** 1 local-stateful
**Goal:** Exhaust the GROBID settings + per-paper + bulk parse surfaces while preserving the load-bearing
postures: GROBID is a separately-run, opt-in, user-configured Docker service (never bundled, never assumed
running); a **loopback** configured URL needs no consent, a **non-loopback** one is egress-gated exactly like a
custom AI provider endpoint (invariant #3); and the coordinate-overlap mapping this pipeline writes
(`chunks.grobid_section_id`) must **never fabricate** a section match — an unmapped chunk stays honestly
`NULL` (the same exact/region/**null** discipline invariant #2 applies elsewhere, extended here to
"mapped section" vs. "no mapping found," never a guessed one).

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** unless a step explicitly says
otherwise. Register listeners before navigation. **Do not assume a real GROBID server is reachable** — this
route's harness has no bundled GROBID and does not start one; treat "GROBID unreachable" (connection
refused/timeout against whatever loopback URL you configure) as the expected default environment, exactly like
route 52 (OCR) treats a missing Tesseract binary — the pass criterion is a **graceful, honest error**, not a
successful parse. If a real GROBID instance happens to be reachable at the URL you configure (e.g. a
`docker run -p 8070:8070 lfoppiano/grobid` left running on the host), a successful parse is also acceptable —
report which branch you actually observed.

## Seed contract

Use the **Renderable Seed Paper** (real on-disk PDF, `/pdf` resolves) for the per-paper parse action. The
**Facial Anomaly Perception** paper's PDF is not on disk — its "Parse document structure…" button, if clicked,
must fail with "no local PDF" (422), not a crash. **Signal Detection Theory** is metadata-only (no PDF
attachment at all) — the button must not render there. See `_TEMPLATE.md` for the full seed contract.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate (Core invariant #3), GROBID-URL-scoped, not the LLM-provider gate.** With egress unset, saving
  a **loopback** GROBID URL (`http://127.0.0.1:*`, `http://localhost:*`) and starting either parse action must
  fire **no** consent-refusal — the request either reaches GROBID or fails with a connection error, never a 403.
  Saving a **non-loopback** URL (any real hostname, e.g. `https://example.com:8070`) and starting either parse
  action with egress unset must return **403** with the exact detail
  `"AI features are off. Enable data egress in Settings to send this PDF to a non-loopback GROBID server."`
  **before** any outbound network request to that host — confirm via the request listener that the configured
  non-loopback host is never contacted. The 403 must win even for a **nonexistent** paper id (the egress check
  runs before the paper-existence check) — a 404 instead of 403 in that combination is a bug.
- **Unconfigured fails closed, not silently.** With no GROBID URL saved, both parse endpoints return **409**
  with `"Configure a GROBID server URL in Settings before parsing."`, surfaced inline in the UI (not a silent
  no-op button).
- **Test connection needs no egress gate — by design, not an oversight.** `POST /grobid/test-connection` is a
  bare liveness ping (`GET {url}/api/isalive`) carrying zero library content; it must succeed or fail based
  purely on reachability, with **no** 403/consent gate at all, even against a non-loopback URL. This is a
  disclosed, deliberate scope reading (see `.claude/security-audits/2026-08-15_grobid-integration.md`) — do
  **not** flag its absence of an egress gate as a finding on its own; DO flag it if the ping's request/response
  ever appears to carry more than a bare GET with no body (that WOULD be a real regression).
- **Coordinate/mapping honesty (invariant #2's discipline, extended).** A parse job's result only ever reports
  `sections_found`/`chunks_mapped` **counts** — never a per-chunk "this chunk is definitely in the Methods
  section" claim beyond what coordinate overlap actually produced. `chunks_mapped` must never exceed the
  paper's actual chunk count. A paper with real GROBID output that maps 0 chunks (no coordinate overlap found)
  must report `chunks_mapped: 0` plainly — not omit the field, not silently retry as a heuristic-tagged
  success, not surface an error for what is actually a correct empty result.
- **Status findability (invariant #5).** Both the per-paper and bulk parse jobs run through the same
  `grobid_parse_jobs` `JobStore` and must appear in the global Status popover while running, labeled exactly
  **"Local processing + self-hosted GROBID"** (a deliberately distinct compute-kind label — this is neither
  pure "Local AI" nor "Provider AI," since it calls an external-but-self-hosted service the user runs
  themselves). The per-paper job's Status entry must click through to that paper's Methods → Details section.
  The Settings page's own bulk-parse `ProgressBar` uses `managedBy="backend-job"` — confirm it does **NOT**
  also create a second, duplicate Status entry for the same bulk job (one backend job = one Status row).
- **Signal not verdict.** A completed parse never presents a "document quality" score, a "well-structured"
  verdict, or any per-paper judgment — only sections-found/chunks-mapped counts.

## Adversarial checklist

- paste ~50KB into the GROBID URL field; submit whitespace-only → treated as clear (matches `local_base_url`'s
  own trim-to-empty precedent) — confirm no crash either way
- double-click **Save**; rapid-click **Test connection**; double-click **Parse document structure…**
- navigate away from Settings (or the paper) mid-parse-job, then return — the job must still be tracked/
  reachable via Status, and re-opening the same view must not double-submit a second job
- `GET /grobid/papers/{id}/parse/{job_id}` and `GET /grobid/library/parse/{job_id}` with a **fabricated** job id
  → 404, not a 500 or a hang
- click **Parse document structure…** for the Facial Anomaly Perception paper (PDF row exists but not on disk)
  → 422 "no local PDF to parse," not a crash; confirm the button is entirely **absent** for Signal Detection
  Theory (no PDF attachment at all)
- clear the saved URL (Save with an empty field) while a bulk job might still be "done" from a prior run →
  confirm `!url` correctly disables **Parse structure for library** again
- resize to `375x812`, hard refresh — no horizontal overflow on either the Settings card or the Detail-pane row
- **re-parse idempotency (final-review fix, backlog #30):** if a real GROBID instance answered in Step 5, click
  **Parse document structure…** on the SAME paper a second time (only possible when a real GROBID server is
  reachable — skip this bullet and note it as untestable-this-environment otherwise, don't fabricate a result).
  Confirm the second run's own "Parsed N sections; mapped M chunks" message reports **the same order of
  magnitude** as the first run's result, not roughly double it — a re-parse must REPLACE the paper's prior
  `paper_sections` rows and chunk mappings, never append alongside them. If you have DB access to the running
  instance, directly confirm `SELECT COUNT(*) FROM paper_sections WHERE paper_id = ?` after the second parse
  equals the first parse's own `sections_found` count, not double it (this is the exact regression
  `tests/test_grobid_pipeline.py::test_parse_paper_structure_reparse_is_idempotent_not_additive` covers at the
  unit level — this step is the live end-to-end analogue).

## Steps

1. Open Settings. Confirm the **GROBID document structure** card renders under Local maintenance: a URL input
   (placeholder `http://127.0.0.1:8070`) + **Save**, with **Test connection** and **Parse structure for
   library** both effectively unusable/disabled while unconfigured (`GET /grobid/status` → `configured:false`).
2. Save a **loopback** URL (`http://127.0.0.1:8070`). Confirm `GET /grobid/status` now reports
   `configured:true` with that URL, and **Test connection** becomes available. Click it: confirm an honest
   result either way (`ok:true` "GROBID is reachable" if something really answers at that port in this
   environment, or `ok:false` with a specific unreachable-host detail otherwise) — never a fabricated success.
3. Save a **non-loopback** URL (`https://example.com:8070`). With egress still unset, open a paper's Details
   pane and click **Parse document structure…**. Confirm the request is refused with **403** and the exact
   detail text above, and the request listener shows **no** request ever reached `example.com`. Repeat against
   **Parse structure for library** in Settings — same 403, same no-egress-leak assertion.
4. Clear the URL (Save empty). Confirm `configured:false` again, **Parse structure for library** disabled, and
   clicking **Parse document structure…** on a paper surfaces the inline 409 "Configure a GROBID server URL…"
   message rather than a silent failure or crash.
5. Save the loopback URL back. Open the **Renderable Seed Paper**'s Details pane; confirm **Parse document
   structure…** is present (alongside whichever of Reprocess-PDF-text/OCR applies for its chunk state). Click
   it: a job starts, appears in the global **Status** popover labeled **"Local processing + self-hosted
   GROBID"**, and clicking that Status entry navigates to this paper's Methods → Details. On completion, confirm
   either a graceful **error** message (GROBID unreachable — the expected default here) or, if GROBID actually
   answered, a "Parsed N sections; mapped M chunks" message with `M <= chunk_count`. No crash either way.
6. In Settings, click **Parse structure for library**. Confirm the `ProgressBar` (`managedBy="backend-job"`)
   renders and only ONE Status entry exists for it (no client-side duplicate). On completion, confirm the
   summary line ("N papers parsed · M skipped · S sections found · C chunks mapped") renders with honest counts
   — `papers` should match the seed's live paper count, and papers with no local PDF (Signal Detection Theory)
   must land in `papers_skipped`.
7. Adversarial: run through the checklist above (fabricated job ids → 404, the no-PDF/no-attachment cases,
   double-submits, mobile viewport).

## Pass criteria

- Both Settings and per-paper GROBID controls are reachable, respond correctly at each configuration state
  (unconfigured / loopback / non-loopback + egress off), and never fabricate a mapped-section result.
- 0 console/page errors.
- The non-loopback egress gate holds with zero leaked requests to the configured host; the loopback path needs
  no consent; `test-connection` correctly has no gate at all.
- Both parse jobs are Status-findable with the correct compute-kind label and nav target; no duplicate Status
  rows.
- 409/403/404/422 fire in exactly the documented cases; mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_91_grobid_document_structure.md` + `screenshots/` (see `_TEMPLATE.md`).
