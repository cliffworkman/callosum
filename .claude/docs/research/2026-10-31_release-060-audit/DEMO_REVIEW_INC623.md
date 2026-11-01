# Demo experience review, inc 623

Self-review by the implementing session, with rendered Chromium evidence. No independent reviewer has seen this.

**Historical base:** `562bfce`, inc 576, reviewed 2026-09-04. **Reviewed through:** the inc-623 corrections commit named in
`demo/experience-coverage-v1.json` (`review.reviewed_rev`). Span: 158 commits, 30 routers (+2961/-123), 49 frontend files
(+2934/-337). `tools/demo/*.py` had no change in the span; `demo/` changed only in the ledger and in a deterministic WIP
fixture reorder (`dcb06546`). The website fingerprint domain is not part of this review (inc 624).

## Historical receipts, preserved
The refresh replaces the review block, so its earlier content is kept here.
- **Review:** reviewed_at 2026-09-04, reviewed_rev `562bfce`, reviewed_increment 576, source_fingerprint
  `a3d51bd64e6c47ebb5ae5901b0da8404b3e041324cb05ea76c88bc0e824c5c24`. Note: "Reviewed inc 576 exact-checksum PDF reconnection
  and cause-specific unavailable states. Recovery depends on local filesystem failures, so the backend-free demo remains
  intentionally unchanged."
- **Decline:** declined_at 2026-10-31, declined_rev `e7c30c5a`, declined_increment 615. An administrative extension through
  inc 615 that deferred review of the 607-610 surfaces. It reviewed nothing. Incs 616-622 then failed the gate, as recorded in
  each increment's notes.

## What the gate covers, and what it does not
`tools/qa/check_demo_experience_coverage.py` checks two things: every `www/` capability claim has a ledger status, and the
review is current for `app/backend/api/routers/*.py` and `tools/demo/*.py`. It does not check that the demo renders, that a
surface is truthful, or any frontend file. Findings D1-D4 below were all invisible to it: the gate had been failing only on
staleness, and a blanket refresh would have left every one of them in place. The 121 capability statuses were re-read
against this review, and none needed to change. `cap-reader` was already `saved-inspectable`; correction C1 is what makes
that accurate.

## Findings: misleading or broken (class D), all corrected
| # | Finding | Evidence | Since | Correction |
|---|---|---|---|---|
| D1 | **In-reader Find said "No matches" for words visibly on the page, and text could not be selected.** The demo bundles pdf.js 4, which removed `renderTextLayer`. The viewer calls that name on the global, inside a try/catch that treats failure as harmless, so all 38 pages had an empty `.textLayer`. A false negative stated as a result. | 38 layers, 0 spans. Direct `TextLayer` on the same page: 44 spans | No-text-layer since the demo adopted pdf.js 4; the false "No matches" since inc 590 | C1 |
| D2 | **Settings showed a raw `HTTP 404 on /embedding-profiles` and an empty "Library modernization" heading.** The brief for this increment described a brief notice there. No such notice existed: what a visitor saw was this error plus the generic banner. | `settings-modernization.png` | Incs 608-620 | C3 |
| D3 | **Every first load raised an alert** saying a surface was unavailable, before the visitor did anything, from background reads the runtime did not answer. | Banner on landing, `/library/import-queue` and `/papers/{id}/merge-origin` 404 | Merge-origin predates 576; import queue from #61 | C2 |
| D4 | **Delete on a paper card said "Editing paper details…".** The button became always visible in inc 585. | `DELETE /papers/42` message | Inc 585 | C2 |

Also found and corrected, class C rather than D: finding a referenced paper (inc 595) fell through to the generic message.

## Corrections
- **C1, `00_bootstrap.jsx`:** the demo branch of `loadPdfJs` puts a small `renderTextLayer` adapter over pdf.js 4's `TextLayer`
  on the global. The live branch is untouched.
- **C2, `demo-runtime.js`:** answers `/library/import-queue` with `{items: []}` and `merge-origin` with `null`, both true of this
  snapshot, and adds specific messages for Delete and `/references/resolve`. Modernization and profile paths remain deliberately
  unanswered, and a test pins that.
- **C3, `35j_modernization.jsx`:** demo mode renders one short notice instead of the panels, and reads nothing. Live behaviour goes
  through the same component as before, renamed `LiveLibraryModelsSection`.
- **C4, scientific honesty:** one sentence each in the saved-synthesis note, the Help view and `demo-about.html`: saved results came
  from an earlier version, not from the current models.
- **Harness:** the local-destination test now names the build command when `dist-demo` is missing. README and QA route 01 corrected.
  The route still said three papers and eight claims.

Not done, by instruction: no fake modernization backend, no regenerated fixture, no new demo feature, no change to `www/`.

## Modernization (incs 608-622): disposition C throughout
The accurate statement is that the demo has none of this, and it now says so. Rendered: no control, no read, no raw error.

| Capability | Live app | Demo |
|---|---|---|
| Retrieval profile choice; automatic Arctic preference | Settings | Absent; notice |
| Verification model choice; automatic DeBERTa preference | Settings | Absent; notice. DeBERTa's release gates are unarmed and unchanged |
| Library modernization in Status | Derived row | Absent; snapshot has no such job, Status shows only the saved Ask receipt |
| Download and verification state; classification and indexing | Background | None happens. No download, no index |
| Pause, Resume, Cancel, Try again | Settings | Absent. The notice names Pause, Resume and Try again; Cancel belongs to an index run |
| First-run modernization notice | What's-new banner | Not shown: the snapshot's version `0.1.0-demo` is not semantic, so the picker selects nothing. Verified rendered |
| Help "Library modernization" | Current corpus | Absent from the bundled corpus; see S4 |

## Scientific claims
- **S1, model identity.** No visible surface names Qwen, Arctic, DeBERTa or a current retrieval or verifier model. `Snapshot` strings
  name `gemini-2.5-flash-lite` and MiniLM-L6-v2 as fixture provenance, correctly for when it was captured. No fixture was changed.
- **S2, provenance line.** The saved summary has `model_provenance: null`, so the line is absent. It does not claim "not recorded"
  either, which is how the app treats an imported synthesis. C4 now tells the reader why no model appears.
- **S3, verification and contradiction.** Saved result: one verified, four flagged, shown apart. No saved citation is `contradicted`,
  so inc 619's cautious wording has nothing to render, and `status_note` is null. The bundled Help's "source disagrees" remains the
  baseline wording. Thresholds, labels and rules untouched.
- **S4, Help.** The bundled corpus has 66 sections; the current one has 69. Missing: Browser Capture, How Ask reads your question,
  Library modernization, and the rename of "Saved for later" to "Saved". I found no bundled statement that the current app makes
  false for the automatic path. It is dated, not wrong, and the Help view now says so. Regenerating it would need a snapshot rebuild
  and belongs with Help consistency in inc 624.
- **S5, bibliography and source roles.** Saved evidence predates incs 583, 607 and 611 (reference exclusion and source-role v2). The
  demo describes neither and claims neither. Its five saved claims quote running text. The source-role work is not represented, class C.

## Router dispositions (`git diff 562bfce..HEAD`)
A exercised, B saved or simulated and identified, C unavailable with an explanation, E not applicable for the stated reason.

| Router | Actual change | Class | Demo behaviour |
|---|---|---|---|
| `acquisition` | `POST /papers/by-doi`, `reason_code` | C | Add with DOI explains itself at the menu, opens no form |
| `agent` | Reuses the shared DOI add and admission | E | MCP surface; `/agent` writes already blocked; no visible change |
| `axes` | `GET /axes/{id}/ask-scope` | C | Axis Ask renders nothing in demo. Axis cards exercised (A) |
| `beyond_library_saved`, `gaps`, `overlooked`, `citation_equity`, `my_publications`, `my_publication_gaps` | `include_trashed=True` on identity lookups | E | Live-query identity only. Saved answers are fixed and the snapshot has no Trash |
| `capture` (new) | Browser Capture endpoints | C | No panel, no reads. `03a` returns early in demo. Help note names it |
| `citations` | Empty render instead of 422 | E | Unreachable: every saved citation has a live paper |
| `critical_review`, `critical_review_snapshot` (new) | Persisted critique, modal | B / C | Saved Critique inspected through `/saved`. The modal's entry points cannot be reached in demo: the finder cannot resolve, and no such Status receipt is saved |
| `discovery` | Search over more sources (inc 599) | B | Saved provider search labelled as saved. Shows the sources saved with it, fewer than live |
| `embedding_index`, `embedding_profiles`, `modernization` (new) | Profiles, indexing, modernization, Try again | C | C3 |
| `health` (new file) | Instance role, library identity | E | Snapshot health has neither, so no badge renders |
| `import_queue` (new) | Review queue | B | C2: empty, true of this snapshot; panel hidden at zero |
| `library`, `ocr`, `registration_acquisition`, `transparency` | Pass embedding runtime to admission | E | All of these writes are already blocked |
| `reference_lookup` (new) | `POST /references/resolve` | C | C2: reader's "find paper" explains itself. Exercised |
| `status` | Modernization row, nav changes | B | Saved receipt rendered, no modernization row |
| `summaries` | Query shape, axis scope, reference exclusion, overview | C | Composer absent in read-only demo, so nothing posts |
| `summaries_provenance`, `summaries_response` | Provenance, `status_note`, responsiveness, facets | B | Optional and null in the snapshot: renders without them. S2, S3 |
| `wanted` | Triage fields | B | Saved list opens, "Not checked yet", no raw error |
| `zotero_citations` | Trashed identity, indexing | E | Writer-adapter path; not part of a browser demo |

## Frontend dispositions
- **A, exercised after correction:** `00_bootstrap`, `30_viewer`, `30g_pdf_selection`, `30i_pdf_find`, `30c_frame`, `10_pdf_layer`, `10b_libmenus`, `10d_papercard`, `03_library`, `15_axes`, `15b_axis_card`, `25_detail`, `25a_detail_actions`, `18_help`, `35_settings`, `35j_modernization`, `40_app`, `40c_library_add_modals`, `40d_modal_hosts`, `36_gaps`, `36b_overlooked`, `36c_beyond_library_saved`, `26_wanted`, `30d_discover`, `30g_feed_suggest`, `04b_workspaces`, `04c_status`, `08h_methods_transparency`, `08x_methods_critical`.
- **B:** `20_synthesis`, `20b_summary_groups`, `20c_synthesis_results`, `19c_facet_coverage`, `20e_model_provenance`.
- **C:** `35h_browser_capture`, `35i_retrieval_profiles`, `04f_modernization_logic`, `10l_import_queue`, `10l_import_queue_logic`, `03a_capture_updates`, `15c_axis_ask`, `20d_scoped_ask`, `30j_reader_ask`, `30h_reference_finder`, `28e_add_doi`, `08x2_critical_modal`.
- **E:** `00_lib` (provider seam), `00b_external_links` (desktop shell), `03b_library_identity` (no identity in snapshot), `04e_whatsnew` (no banner, verified).

## Remaining limitations, acknowledged
1. Six Settings reads remain unanswered (`/grobid/status`, `/grobid/docker/status`, three `/methods/*/database`, `/sync/blocked-senders`).
   All predate inc 576. Opening Settings shows the accurate generic banner for seven seconds, and those sections show controls that
   explain themselves on click. Left alone as out of this span.
2. A visitor reads "Not downloaded" for the mirror databases in Settings. True of a snapshot with no database, and also predates 576.
3. Help is dated (S4).
4. Settings is not offered on the phone layout, same as the live app, so the notice is checked at desktop width only.
5. The PDF text layer was verified for containment, size, selection and Find on one paper, in headless Chromium on Windows. Alignment
   against the canvas was inspected on screenshots, not measured glyph by glyph.
6. Deployment on real static hosting was not exercised: a local static server under `/callosum-demo/` stood in for it.

Tests and browser receipts: `.claude/docs/increment-notes/INCREMENT-623-NOTES.md`.
