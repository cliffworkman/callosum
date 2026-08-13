# Increment backlog — DONE (shipped / closed items)

The completed half of the backlog, split out of [`INCREMENT-BACKLOG.md`](INCREMENT-BACKLOG.md) on 2026-06-20 so
the open queue stays scannable. This is the one-line *"what landed, which increment"* map; the per-increment
design diary (`increment-notes/INCREMENT-NN-NOTES.md`) and `changes.md` hold the detail. Items here are closed —
new work goes in the open backlog.

> **Closure discipline (restated 2026-08-09 — see CLAUDE.md's Increment workflow section).** When an item in
> `INCREMENT-BACKLOG.md` closes: **delete its entry from the open file** (don't leave a growing "✅ CLOSED"
> paragraph in place — that's exactly the drift this split exists to prevent) and **append one compressed
> `- [x]` line here**, keyed by the item's own stable `#N` where it has one (numbers are never reassigned, so
> `grep "#N" INCREMENT-BACKLOG-DONE.md` finds it precisely). Point at the relevant `INCREMENT-NN-NOTES.md` for
> full narrative rather than re-telling the story here — this file is an index, not a second diary. **2026-08-09
> reconciliation pass:** this file had gone stale since 2026-07-22 while `INCREMENT-BACKLOG.md` grew its own
> redundant "Shipped — breadcrumbs only" section plus several individually-growing "✅ CLOSED" entries instead —
> all of that is merged in below (see the sections from "Near-term closures" onward), and the open file is
> trimmed back to genuinely-open items only.

---

## Cross-cutting
- [x] **DESIGN.md design dictionary** (2026-06-19) — Pass 1 tokens + element recipes, Pass 2 inconsistencies +
  canonical rules; **CLAUDE.md rule #8** (read it before any CSS change) + reference-table + decision rows.
  *(The Pass-2 consolidation worklist remainder is still open — see the open backlog.)*
- [x] **Mobile workspace switcher** (inc 302) — at phone width, the center workspace menu renders as a compact
  **Workspace** dropdown instead of the desktop horizontal tab strip; the bottom mobile nav remains the region
  switcher (**Library / Panels / Details**).
- [x] **Navigation placement rubric rewrite** (inc 303) — `DESIGN.md §5` is now the canonical mode-vs-lens rule:
  center workspaces are broad modes of work, side panes are selected-paper lenses, and THEORY/METHODS survive only as
  internal pane ids.
- [x] **Benchmark backlog reconciliation** (inc 303) — A8 was closed-as-covered in inc 205, and A5 color tags shipped
  in inc 207; both stale open bullets are now marked done in the open backlog with their rationale.

## Theme 1 — Axes UX (inc 44–52)
- [x] **A. Axis edit modal + title/term decoupling** (inc 44) — one Edit Axis modal; the **title is cosmetic**
  and the description's `Related:` terms are the embedded query; suggested terms deselected by default.
- [x] **A′. Click an axis-listed article → open its PDF** (inc 44).
- [x] **B. Tier-tag cleanup + uncertain→assigned ✓ confirm** (inc 50) — ASSIGNED tag removed; ✓ promotes an
  uncertain paper to a manual override (`confidence IS NULL`) that survives re-score.
- [x] **C. "Add articles" library focus-mode** (inc 50) — the axis ＋ opens a staged add/remove focus mode on
  the library, committed on Save (retired the inc-38 AddPaperPicker).
- [x] **B′. Eyeball toggle to hide/show UNCERTAIN papers** (inc 51). *(Make-it-the-default is still open.)*
- [x] **B″. Sidebar density** — connection-in-logo (inc 47); dropped the subtitle + verifier text (inc 47/48);
  axis filter + green "+" on one no-wrap row (inc 48).
- [x] **Suggest-optimal axes** (inc 52) — clusters the library with a coverage-with-diversity objective; local
  c-TF-IDF labels + optional egress-gated Gemini polish (falls back to local; never 503).
- [x] **Hide uncertain axis papers by default** (inc 77) — a **Settings → Axes** toggle that makes the inc-51
  per-axis 👁 hide-uncertain view the default (persisted; the per-axis 👁 still overrides).
- [x] **My Publications — Part 1: the auto-axis** (inc 78) — a pinned, **OpenAlex-resolved, LLM-free** axis of
  your own papers: a profile (name/variants/ORCID) → ORCID/DOI-confirmed members + name-only candidates you
  confirm/reject (persisted) + an import hook. New `integrations/openalex/author.py`, `profile_repo`,
  `clustering/my_publications.py`, `routers/my_publications.py`, migration 0009. *(Part 2 — the impact dashboard
  tab — is still open.)*

## Theme 2 — Library management (inc 54–67)
- [x] **D. Multi-select + bulk delete → soft-delete + Trash/Restore** (inc 54); **permanent delete /
  empty-trash** with vector cleanup → no orphan crash (inc 65); **exclude trashed papers from synthesis
  retrieval** (inc 66); **permanent delete removes exclusively owned managed attachment files while preserving
  linked/out-of-root/shared paths** (inc 340, security-audited).
- [x] **E. Duplicate detection** — layered (identifier→title→embedding) + union-find, flag-only, local (inc 56);
  **persistent "not a duplicate" dismiss** (inc 64); **un-dismiss / manage dismissals** (inc 67).
  *(Deferred: the actual library **merge** — open, do-last.)*

## Theme 3 — Synthesis & Details (inc 49, 57, 62)
- [x] **F. Always-on Synthesis + contextual Details split** (inc 57) — vertical split (no tabs), draggable
  divider, height persisted.
- [x] **G. Editable Details pane + DOI correction / re-resolve** (inc 49) — Mendeley-style always-editable
  fields, auto-save on blur, `PATCH /papers/{id}` (safe csl_json merge), 🔎 `re-resolve`; user-edits guarded
  from batch clobber. *(Deferred: per-attachment PDF serving, multi-URL, Translators, "More" add-field — open.)*
- [x] **Multi-paper summary from a library selection** (inc 62) — the bulk-bar **summarize** runs a verified
  synthesis of the checkbox-selected papers + a round-robin chunk-coverage fix. *(Critical-review supplement +
  follow-ups — open.)*

## Theme 4 — App-wide (inc 46, 53, 59–60, 68)
- [x] **H. Settings UI + light/dark mode** (inc 46) — Settings modal (gear), warm-dark theme via
  `data-theme` overrides + no-flash bootstrap, theme-matched logo, PDF page stays light; favicon dark-swap
  (inc 53). *(More settings + the `.btn-*` DRY remainder — open.)*
- [x] **In-app HELP** — a ? viewer (inc 53) → corpus-driven navigable modal `GET /help/corpus` (inc 59) →
  **AI help assistant** `POST /help/ask` with its own `CALLOSUM_HELP_ASSISTANT_ENABLED` gate (inc 60).
- [x] **Subresource Integrity** on the React/ReactDOM/Babel CDN scripts (inc 53).
- [x] **Canonical `.btn-*` classes** (inc 68, **partial** — selector-grouped, zero visual change; migrating the
  divergent ghost/icon buttons is open).

## Other shipped (outside the original themes)
- [x] **Sort the library** (inc 69) — a `sort` allowlist query param.
- [x] **Citation export** (inc 70) — BibTeX / RIS / CSL-JSON, bulk download + per-paper clipboard copy.
- [x] **Tags** (inc 71) — manual per-paper labels + filter-by-tag; **auto-suggest tags via local c-TF-IDF**
  (inc 72); **author/index keywords as first-order tags via Crossref `subject`** (inc 73, + a backfill tool).
  *(Tag provenance UI + OpenAlex concepts / PubMed MeSH sources + the tags↔findings cross-cut — open.)*
- [x] **Filter the library by axis** (inc 63) — clickable axis count badge → `?axis_id=` filter + banner.
- [x] **LLM token-spend cache** (inc 61) — content-addressed summary cache + usage logging.
- [x] **Provider-agnostic egress gate at the DI seam** (inc 58).
- [x] **Literature acquisition A/B/C** (inc 74–76) — the legally-clear OA lane (the `OaLocation` seam +
  OpenAlex, inc 74); the **7-source resolver cascade** (DOAJ/Europe PMC/Crossref-OA/CORE/arXiv/bioRxiv/OSF,
  inc 75); the **wanted list + auto-acquiring OA re-check + coverage** (inc 76). Spec:
  `future-tracks/opus4.8_future-tracks_acquisitionclean.md`. *(The legally-ambiguous lane stays parked.)*

## Open proposals — resolved
- [x] **Filter the library by axis** (inc 63). **Undo / soft-delete** delivered as Trash + Restore (inc 54/65).

## Release-readiness arc (Phases 1–8, 2026-06-20)
- [x] **Phase 1** Principles harness in CLAUDE.md · **Phase 2** backlog reflects the full vision · **Phase 3**
  architecture + README cleanup · **Phase 4** test-harness audit + extension · **Phase 5** modularize + dedup +
  dead-code + security + lint (ruff, generic `JobStore[R]`) · **Phase 5.5** README coverage reconciliation ·
  **Phase 6** `.claude/` consolidation · **Phase 7** **published to github.com/cliffworkman/callosum** (public,
  AGPL-3.0) · **Phase 8** the future-tracks watched-inbox session-kickoff rule. Chronology: `changes.md`.

## Frontend / UX pass (inc 109–116; journaled in `RECOVERY-LOG.md`)
- [x] **Brand-asset source move** (inc 109) — sources at `.claude/media/`; `inline_brand_assets.py` re-inlines from
  there. *(Closes the stale open-#1 "is it broken?" — it isn't.)*
- [x] **PDF page-view options** (inc 110, was open #2) — fit-to-width + two-up, persisted (`callosum.pageView`),
  on the existing viewer; the inc-34 scale/text-layer invariant preserved.
- [x] **Editable Translator(s)** (inc 111, part of open #5) — the Details pane edits CSL `translator` like authors.
- [x] **Multi-paper focus query** (inc 112; discoverability completed inc 145) — a query ranks the selection
  summary's coverage (see #7).
- [x] **Button canonicalization** (inc 113–115) — advanced DESIGN.md §3; the `.btn-*` DRY + radius-middle +
  the inc-86 "documented exceptions" decision remain open (#6).
- [x] **Synthesis ✕-close + AXES ambient outlines** (inc 116).

## My Publications overhaul (inc 117–119)
- [x] **SP1 dashboard restructure + browsable publication cards** (inc 117); **SP2 group-by-domain** (inc 118);
  **SP3 citing articles + per-paper OpenAlex citation counts** (inc 119, = Layer 3). *(Only Layer 4 grounded
  prospection remains — open #35.)*

## QA + UI-shell + experience gates (inc 120–122, 140)
- [x] **QA mechanism** (inc 120) — `tools/qa/build_surface_map.py` surface-coverage gate + the Codex-exec
  supervisor + the watched `qa-inbox`; **CLAUDE.md rule #10**.
- [x] **THEORY/METHODS accordion on a self-registering module registry** (inc 121, the designated "next major
  upgrade") — DESIGN.md §5; **inc 122** relocated statcheck into a METHODS section; **inc 139** added
  tabs-within-a-section (Tags → an AXES tab) + METHODS reorder; **inc 138** auto-selects the top library paper.
- [x] **End-user experience pass — rule #11 + `EXPERIENCE-PASS.md`** (inc 140) — the persona-grounded
  experience-agent mechanism (the 4th gate: serves-the-user).

## Methods / data-detective producers (inc 123–137)
- [x] **Synthesis overview fix** — front-matter-aware no-query selection (inc 123) + an evidence-traceable
  **Overview** above the verified claims (inc 124) + a strengthened front-matter classifier, live-validated (inc 125).
- [x] **p-curve** (inc 126), **GRIM/GRIMMER** (inc 127) + multi-item GRIMMER (inc 129) — collection/per-value
  data-detective checks; credited (`THIRD-PARTY-NOTICES.md`). *(Open #27 keeps only "more statcheck test forms".)*
- [x] **40_app.jsx split** to relieve the 600-line cap (inc 128).
- [x] **Findings subsystem** — FACT-vs-candidate `paper_findings` store + Review pane (inc 130); **retraction
  producer** Crossref/OpenAlex (inc 131) + the Retraction Watch DB mirror (inc 132); statcheck **candidates** +
  the unified **"N to review"** facet (inc 133); on-import auto-check + RW staleness nudge (inc 134). *(Open #31
  keeps only Zotero/single-PDF on-import + a cadence RW refresh.)*
- [x] **Literature gap-finder** — backward gap (inc 135) + watched-folder focus-rescan (inc 136) + **v2**
  forward/axis-scoped/cached gaps, migration 0019 (inc 137). *(Open #29 keeps only followed-authors.)*

## Build-and-test slate — persona experience passes (inc 141–145)
- [x] **statcheck flagged→detail path** (141); **determinate "X / N" import/scan progress** (142); **durable
  imported-keyword deletion** (143, `suppressed_paper_tags`, migration 0020); **export/copy highlights + notes**
  (144); **discoverable multi-paper focus query** (145). Each found + fixed a real gap via a persona agent.

## BYOK / multi-provider LLM arc (inc 146–152; open #10 + #39)
- [x] **Gemini API key + egress consent in Settings** (inc 146, was #10) — local `~/.callosum/app-settings.json`
  store overlays the env fallback; key write-only over the wire; egress default-off. Audit `2026-06-26_byok-api-key.md`.
- [x] **"Test this key"** egress-gated ping (inc 147); **synthesis "AI is off → Enable in Settings →" nudge** (inc 148).
- [x] **Multi-provider engine** (inc 149) — one `complete()` seam → Gemini/OpenAI/Anthropic/**local** (httpx, no new
  dep); a loopback **local provider runs with zero egress** (`requires_egress`); provider-aware egress gate. **Settings
  provider UI** (inc 150). Audit `2026-06-26_multi-provider-llm.md`.
- [x] **Validation-lock disclaimer + help-assistant Settings toggle** (inc 151); **OS-keychain key storage**
  (inc 152, optional `keyring` + file fallback). Audit `2026-06-27_keychain-storage.md`. *(Truly deferred: real
  cloud/Ollama/OS-vault round-trips = manual spot-checks.)*

## Infra / hygiene
- [x] **QA supervisor: isolate the disposable QA instance from the shared Remote-access setting** (was #46,
  shipped 2026-07-02) — `_qa_serve.qa_server()` points the throwaway instance at its own `CALLOSUM_SETTINGS_PATH` +
  forces `CALLOSUM_DISABLE_REMOTE_ACCESS=1`; `supervisor.py` scrubs `CALLOSUM_DB_URL` from the `codex exec` env
  (defense-in-depth). A user's Remote-access toggle can no longer leak into and 401 the disposable QA run. Not a
  security finding — QA-harness isolation.
- [x] **600-line-cap cleanup: split `routers/methods.py` + `persistence/schema.py`** (was #47, inc 262) — two `app/`
  files had drifted over the rule-#1 hard cap by inc 261. `methods.py` 619→450 (retraction cluster →
  `routers/methods_retraction.py`, the inc-226 sibling-router pattern) and `schema.py` 628→558 (summary table group →
  `persistence/schema_summaries.py` on the shared `schema_base` metadata, the inc-137 pattern). Behavior-preserving;
  1044 passed / 1 skipped unchanged.

## Decision-pass closures (maintainer, 2026-07-06)
- [x] **#6 `.btn-*` divergent-button migration — DECLINED.** Divergent ghost/icon buttons kept as **documented
  exceptions** per inc-86; new CSS already follows the canonical `.btn-*` rules. (The `.axis-danger` amber→red +
  radius-scale tidy fold into a future CSS-heavy increment opportunistically, not a migration sweep.)
- [x] **#13 AI-assist auditability standard — RATIFIED** → the 4-part inspectability bar (retrieved source span +
  local-NLI stance + verbatim quote + visible confidence, one low-friction click away; honest shortfall if it
  can't meet it). Durable home: `architectural-decisions-log.md` (+ `PRINCIPLES.md` THEORY cross-ref). Un-gates #12
  + Tracks B/C for planning. (Item stays in the open list as the stated standard, not relocated.)
- [x] **#3 tag source as an always-on label/icon — DECLINED.** Kept aesthetic-only per inc-100 (muted styling +
  tooltip + All/Yours/Keywords filter). The #3 diff-toast + lock-this-tag remainders are now autonomous-eligible.
- [x] **statcheck finding (b) "Check statistics" entry on the paper — DECLINED.** Rely on the inc-141 flagged-chip
  → per-paper-check path; a Details/card entry re-clutters what inc-122 deliberately cleaned. ((e) remains open.)

## Decision-pass closures (maintainer, 2026-07-22)
- [x] **#9 Tag provenance vocabulary formalization** (inc 334) — Cliff chose the bigger scope ("formalize the
  vocabulary too", not just UI grouping). `tags.import_source` now follows a documented `{namespace}:{origin}`
  contract (`tags_repo.py::TAG_SOURCE_NAMESPACES`): bare `user` (sentinel), `import:{system}`, `keyword:{system}`
  (already-conformant, unchanged), `agent:{system}`, and `system:{fact}` reserved for #19. The two pre-existing
  bare values (`zotero`, `ai-agent`) were renamed to `import:zotero` / `agent:mcp` via a new tag-scoped constant
  at each single call site (their *other*-table provenance columns — papers/attachments/collections/notes/
  annotations — are untouched, a separate vocabulary) + an idempotent data migration (0047) for existing rows.
  The sidebar Tags browser now groups by exact source with a header per group (new `js/10e_tagspanel.jsx`,
  extracted from `10_pdf_layer.jsx` when grouping pushed it over the 600-line cap). The per-**link** per-paper-fact
  half stays with #19, unchanged.
- [x] **#23 cross-method auditor consolidation** (incs 336-338, F1/F2/F4, all three checkers) — LMM, meta-analysis,
  and Bayesian each gained: a library-wide batch + header chip counting flagged papers, filterable via
  `GET /papers?signal=...` (F1, the full statcheck-style build Cliff chose over the cheaper per-paper badge);
  a review-queue candidate persisted as a side effect of the existing ad-hoc per-paper view, no batch run
  required first (F4, Cliff's chosen "persist on ad-hoc view" design); and the credit-block footer no longer
  renders before the paper is confirmed applicable (F2 — a genuine bug for LMM/meta/Bayesian; confirmed NOT
  applicable to statcheck, which has no `is_x`-style gate, so left untouched there). The Bayesian checker
  combines two independent signals (a BF-reproduction mismatch + a reporting-completeness checklist) into one
  `flagged` status — the one real design decision beyond mechanically repeating the LMM pattern; its
  `GET /papers/{id}/bayes` endpoint was also extracted from `methods.py` into its own `methods_bayes.py` router
  (mirroring the inc-262 `methods_retraction.py` precedent) to stay under the 600-line cap. Security audit:
  `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md` (PASS, all three).
- [x] **#19 Tags ↔ findings / system-facts (retraction-surfacing)** (inc 335) — the naming-only path #9 sketched:
  `apply_retraction()` (`app/backend/methods/retraction.py`, the one call site both the batch job and the
  on-import hook use) now links/unlinks a real tag (`RETRACTION_TAG_NAME = "system:retraction:retracted"`,
  `import_source = "system:retraction"`) in lockstep with the existing FACT/signal, scoped to `status ==
  "retracted"` only (matches `count_retraction_flagged`'s existing "flagged" definition — not correction/
  concern). The existing `signal=retraction-retracted` facet, header chip, and RETRACTED badge are UNCHANGED —
  this is an additive discovery path through the generic tag/tag-filter mechanism, not a replacement. New
  `tags_repo.get_tag`/`remove_tag_from_paper_by_name` + three router guards (`routers/tags.py`: reject
  color/lock/delete on any `system:`-namespaced tag, 409; reject a user creating a tag literally named
  `system:...`, 422) protect the fact from being edited or squatted. Frontend: `tagIsSystemFact`/`tagDisplayName`
  (`00_lib.jsx`) hide the color-dot/lock/remove affordances and show "Retracted" instead of the raw reserved
  tag name, in both `TagsRow` (`25b_tags.jsx`) and the sidebar `TagsPanel` (`10e_tagspanel.jsx`).
- [x] **#26 CRediT builder UX follow-ups** (inc 339, from the inc-261 experience pass): **(a)** role presets
  per author (First author / PI / Collaborator one-click bundles) — pure client-side toggle-all-or-fill-gaps
  convenience, byte-for-byte the same `roles` state a manual multi-click would produce, so the audited
  "build never infer" backend boundary is untouched (Cliff's call: "build presets anyway, skip the
  discussion" — a quick internal Principles check still ran at design time); **(b)** an opt-in "and" before
  the last by-role contributor name (`use_and`, default off, scoped to the by-role join only); **(c)** a
  discoverability jump-link from Discover → Journals ("Where to submit") to Work → CRediT (the backlog's
  "item ~5 in the accordion" framing was stale — both features had already moved to top-level workspace tabs
  in inc 280; the jump is cross-workspace, mirroring the existing `openReferenceWarnings` pattern).

## Near-term closures (migrated from open backlog §1, 2026-08-09)
- [x] **QA 2026-07-19 batch** (inc 308/309) — all 7 findings fixed + browser-verified: the metadata-only-paper
  PDF 404 (a real gap — `PdfViewer` now skips the doomed fetch via the library card's known `attachment_count`);
  4 mobile CSS spacing fixes (Feed filter buttons, whatsnew notice, Settings provider badges, Work's provenance
  line); `route_00_smoke_readonly.md` rewritten to the actual current pane structure.
- [x] **httpx→httpx2 TestClient migration** (inc 309) — needed zero source changes (starlette 1.x auto-prefers
  `httpx2` when installed); added the dev/test-only dep, synced the dev environment's stale fastapi/starlette.
- [x] **#5 Per-attachment PDF serving** (inc 316; methods follow-up inc 388; cite/viewer follow-up inc 392) —
  `GET /papers/{id}/pdf?attachment_id=` opens a specific attachment; Details' Files list, citation evidence, and
  every Methods panel (statcheck/Bayesian/mixed-model/meta-analysis/transparency) now open the exact PDF
  attachment their evidence came from, not always the primary. A real coordinate-honesty gap (non-PDF
  supplementary attachments) was found and fixed in the same pass.
- [x] **QA runs 20260702/03 remaining re-triage** (inc 317) — every Critical/High/Medium/Low from routes
  24/27/30/32 re-verified live, not assumed. Route 30's Critical (the SQLite write-lock arc) confirmed fixed;
  three Mediums confirmed non-bugs (Chromium's own adversarial-4xx/5xx network logging); two real bugs found +
  fixed (`DuplicatesModal` un-dismiss not refreshing in-place; `ScanModal` losing mid-scan progress on
  modal close/reopen).
- [x] **#31 cadence auto-refresh** (inc 318) — an opt-in, staleness-gated automatic Retraction Watch mirror
  refresh (client-driven, no backend scheduler), gated by a 1-hour attempt throttle found necessary live (a
  mirror that can never become fresh would otherwise re-run on every window focus).
- [x] **Inc 455's followed-author date-precision limit** (inc 458) — `AuthorWork` gained a validated
  `publication_date`; Feed's `_to_entry` prefers it over the bare-year fallback, additive/backward-compatible.
- [x] **#45 My Publications example name** (2026-07-22) — swapped "Ada Lovelace" for "Karen Spärck Jones" in the
  name/alt-names placeholders.
- [x] **#51 funding partial-provider test flake** (inc 440) — the test relied on live scholarly-provider
  results changing; now supplies deterministic local fixtures for the same selected-paper + partial-failure
  contract.
- [x] **#53 `import_citations` silently swallows per-record exceptions** (2026-08-09) — found live while
  verifying inc 466 (a real `sqlite3.OperationalError: database is locked` collision with a concurrent
  watched-folder rescan was indistinguishable from an ordinary malformed record). `citation_import.py` now logs
  the skipped record's title + exception via `_log = logging.getLogger("callosum.citation_import")`, matching
  the exact convention already used by 8 sibling batch-loop call sites. Covered by a new test using the
  `test_usage_logging.py` `_ListHandler`/`_capture()` pattern (not `caplog`, which doesn't reliably see
  `callosum.*` loggers in this project). No behavior change to the returned summary; no increment number
  (too small to rise to a full increment).
- [x] **Superuser capabilities — a reusable gate + Diagnostics, its first application** (inc 468) — the
  `is_superuser` flag (inc 195) gated nothing until now. Cliff's answer reframed this as a general
  access-control pattern (any feature not yet proven safe for general release gets the *option* to sit behind
  the gate — no exception to the standalone no-paywall-circumvention veto), not a one-off. Built
  `require_superuser` (`app/backend/api/dependencies.py`, enforced at the route-decorator level) + its first
  application, `GET /diagnostics` (library counts, remote-access/sync config state, app/DB identity — plain
  counts and booleans only, no content/secrets). Live-verified against the maintainer's real running platform,
  including a stronger-than-planned negative-case proof (a real signed-in non-superuser identity correctly
  sees nothing). Security audit PASS.
- [x] **statcheck signal/work-state duality** (2026-08-09) — research found collapsing the two systems would
  violate the facts-vs-candidates principle (a flagged paper's inconsistency is a persistent fact; "to review"
  is your work state; they're meant to diverge once you've reviewed a paper that stays flagged). The gap was
  narrower than "confusing duality": the help docs already explained the relationship correctly, but only from
  the review-queue side — "Checking statistics" (where a new user meets the ⚠ chip first) never linked forward.
  Closed with (1) a cross-reference sentence in "Checking statistics" linking to "Reviewing findings" (a real
  working in-app anchor link, `#help-reviewing-findings`, verified by clicking it), and (2) a small "Signals" /
  "To review" label above each library-header chip group (`.lib-chip-group-label`, mirroring the existing
  `.eyebrow` small-caps recipe) so the two-systems distinction reads at a glance, not just on hover. Both
  verified live via Playwright screenshots.
- [x] **#54 Repeated-values checker — the narrowed half, fully closed** (inc 469) — research found #54's
  original "duplicate-publication detection" framing (compares a paper against *other* papers/authors) was
  itself an unverified assumption. Reality splits in two: salami-slicing (redundant publication across
  separate papers) has no algorithmic detection method at all — declined outright, recorded in
  `INCREMENT-BACKLOG.md` §6; `scrutiny`'s actual `duplicate_count`/`duplicate_tally` functions (the real source
  of the design doc's "duplication analysis" mention) are a within-one-paper repeated-exact-value counter —
  buildable, GRIM/GRIMMER/DEBIT-shaped, but with no peer-reviewed method behind it. Shipped the latter,
  honestly: `count_repeated_values` (`app/backend/methods/duplicate_values.py`) + a new sibling router
  (`methods_duplicate_values.py`, kept entirely separate from `methods.py`, which had no headroom left) +
  paper-aware save. The result model carries no `consistent`/`flagged` field, and the frontend renders no
  `cite-status` pill — a deliberate presentation choice so the tool can't visually borrow the credibility of
  GRIM/GRIMMER/DEBIT sitting next to it. Text-only credit (no citable paper exists). Live-verified end-to-end
  via Playwright; security audit PASS. **#54 is now fully closed.**
- [x] **#55 Z-curve** (inc 470) — the source design doc's "auto-zcurve" proposed Gemini-assisted "focal
  statistic" extraction, flagged by the doc itself as "more dangerous... judgment-laden," the exact misaligned
  path PRINCIPLES.md Example 3 warns about. Research found the aligned path already existed: p-curve (inc 126)
  had already solved this identical problem by reusing statcheck's exhaustive deterministic extraction instead
  of an LLM-picked focal test, with an already-proven collection-level/no-accusation framing. Z-curve extends
  that pattern — no LLM, no egress. Cliff confirmed building the full Bartoš & Schimmack (2022) EDR/ERR
  mixture-model estimator, verified against the reference R package's own source (not memory). New Principles
  finding beyond p-curve: EDR/ERR are rate estimates, more verdict-shaped than p-curve's right-skew statistic —
  mitigated with a hard (non-dismissible) reliability warning below the reference implementation's own N=300
  threshold, CIs always shown beside the point estimate, and no per-paper/per-author breakdown anywhere. A real
  performance bug (an absolute log-likelihood convergence criterion that never converges for large N) was caught
  by a stress test before shipping, not after. Live-verified end-to-end against the real 217-paper library;
  security audit PASS.

## Design-decision closures (migrated from open backlog §2, 2026-08-09)
- [x] **#11 README front-door** (2026-07-22) — the screenshot landed with `www/`; the voice pass was drafted
  to a scratch file, reviewed, and applied as-is.
- [x] **The `.local/` SQLite-inside-Dropbox note** (2026-07-22) — the working library DB (209 papers, 378MB)
  relocated to `C:\Users\cliff\callosum-data\library.sqlite`; `CALLOSUM_DB_URL` + `run-callosum.ps1` updated;
  the old copy kept in place as a backup.

## Gated-item closures (migrated from open backlog §3, 2026-08-09)
- [x] **#14 Permanent delete removes managed on-disk attachments** (inc 340) — Delete forever / Empty Trash
  now remove only root-contained `managed` files; linked/URL/out-of-root/shared/unsafe paths survive. Reversible
  staging coordinates filesystem cleanup with DB/vector rollback. Audit PASS.
- [x] **#15 Sync UI (SP3c) + server hardening** (inc 310/311, 341) — Increment A: `GET /sync/conflicts` +
  resolve endpoint. Increment B: Settings → Sync UI (setup, enable gate, run + error handling, conflict-review
  panel), browser-verified. Server hardening: per-user rate-limiting (`sync_server/rate_limit.py`), a 90-day
  tombstone-pruning script, and an operations runbook. Audit addendum PASS. *(SP4 sharing + the live
  `sync_server` deploy + a per-user quota/migration tool remain open — see open backlog #15.)*
- [x] **#15 SP4a — sharing identity** (inc 475, round 3 item #4). A per-account X25519 keypair (private key
  sealed under the existing sync DEK, no new KEK), a server-side public-key directory reachable only by exact
  id (structurally no listing/search function — backlog #15's own divergence fence), and a fingerprint-
  verification UI (`SharingIdentityPanel`, Signal's "safety number" pattern). No record is shared in this
  stage — SP4b/c/d remain open, see open backlog #15. Audit `2026-08-10_sync-identity-sp4a.md` PASS.
- [x] **#15 SP4b — share** (inc 476, round 3 item #4). A "sealed" X25519 ECDH + HKDF-SHA256 + AES-256-GCM
  content-key wrap (`sync/sharing.py`, the `crypto_box_seal`/HPKE-base-mode shape) lets a sender end-to-end
  encrypt an ad-hoc picked set of Library papers (reusing the already-audited B2 `build_bundle()` unmodified,
  no PDFs) to one fingerprint-confirmed recipient via a new bulk-bar "share…" action. Sender-only — no
  receiving/importing capability yet; SP4c/d remain open, see open backlog #15. Audit
  `2026-08-12_sync-sharing-sp4b.md` PASS.
- [x] **#15 SP4c — receive** (inc 477, round 3 item #4). Closes the send→receive loop: a "Shared with me…"
  Library entry lists shares addressed to me (no passphrase), then decrypts one on explicit per-row action
  using my own SP4a identity's private key and merges it via `import_bundle()` (a new `source=` kwarg stamps
  `imported_source="share-import"`, never overwriting a merged paper's own prior provenance). A non-recipient
  can never fetch a share's content (server 403 + local re-check). A new `received_shares` table is the
  cross-user provenance log. Independent re-verification needed zero new code (B2 SP3's existing action already
  covers it). SP4d (revoke/roles) is the arc's final open stage, see open backlog #15. Audit
  `2026-08-12_sync-sharing-sp4c.md` PASS.
- [x] **#15 SP4d — revoke + blocked senders, closes the SP4 arc** (inc 478, round 3 item #4). A sender-only soft
  revoke (`revoked_at` on `sync_server`'s `shares` table, never a delete) lets a share be withdrawn before
  import — never after, since the server structurally has no read-receipt concept and can't know if a recipient
  already decrypted it (proven, not just disclosed, by `test_revoke_after_import_does_not_undo_the_import`). A
  local-only, never-egressed blocked-senders list (`app_settings.py`) filters `GET /sync/shares` and refuses
  import (403) as defense in depth, replacing the originally-sketched "roles" territory, which turned out to
  have no target in the shipped one-shot-snapshot share architecture. Closes backlog #15's SP4 sharing arc
  (identity → share → receive → revoke/block) in full; the live `sync_server` deploy + per-user quota/migration
  tool remain open, see open backlog #15. Audit `2026-08-13_sync-sharing-sp4d.md` PASS.
- [x] **#20 Harness hardening — fully closed** (2026-07-22, inc 342) — repo furniture (`SECURITY.md`,
  `CITATION.cff`, `.env.example`); uv adoption (`pyproject.toml` + committed `uv.lock`, CI via `uv sync
  --locked`); the hand-rolled pre-commit hook migrated to the standard pre-commit framework; 3 CI gates added
  one at a time (alembic check, pip-audit, Dependabot); `staged-harnesses/REGISTRY.md` for 7 dormant judgment-
  call checks; branch protection (status-checks-only, admin bypass preserved).
- [x] **#21 Packaging & distribution (post-V1) — superseded by #49** — the Tauri desktop shell (once a
  "placeholder"/research spike) is fully built and shipping on all three platforms with real CI-verified
  installers and public GitHub Releases. Remaining desktop-adjacent work continued under #49.
- [x] **#49 In-app auto-updater for the desktop shell — live** (2026-07-28, inc 409; two follow-up bugs fixed
  same arc) — Windows/macOS periodic check + silent background download + non-blocking restart toast; Linux
  gets an "Open release page" fallback; CI signs builds and publishes `latest.json`. *(Cliff's own remaining
  rollout steps — setting the GitHub signing secrets, running a throwaway rehearsal release — stay open, see
  open backlog #49.)*

## Future-track closures (migrated from open backlog §4, 2026-08-09)
- [x] **#25 Citation concentration — a real field self-citation baseline** (inc 456/457) — an empirical
  bootstrap-resampling calibration (6 real fields, stimulus-norming methodology) found population self-citation
  rates varying ~3x by field and computable coverage varying 18%-74%; N=40 chosen as a disclosed judgment call.
  Wired into the shipped signal via `_compute_self_citation_baseline` with a dual cap (target 40, hard-capped at
  100 raw checks). `audit_reference_list`/`_self_citation` gained backward-compatible params; the WIP call site
  and frontend needed zero changes. *(Overlapped #37's citation-credit-concentration remediation.)*
- [x] **#29 Gap-finder — followed authors as a source** (inc 454) — follow an OpenAlex author (by name/ORCID,
  or from an already-resolved id); Refresh fetches their works (cached, capped 50/author) and surfaces those
  absent from the library. A sibling module (its own two tables), not a third gap-finder direction. Deliberately
  not ranked by axis relevance in v1, disclosed in the UI.
- [x] **#30 Highlight-to-suggest/evaluate (Track C), SP1/SP2/Stage-3 + the persistent save-for-later queue**
  (inc 156-159, 271/272, 449, 465) — beyond-library suggestion via OpenAlex graph expansion + Crossref/PubMed/
  OpenAlex keyword search + Semantic Scholar recommendations, every candidate carrying a `reason`/
  `relationship_label`, never a bare score; wired into the web Cite pane and the LibreOffice adapter. Inc 465
  added an explicit "Save for later" button persisting a suggestion into a reviewable modal queue
  (`saved_beyond_library_suggestions`, keyed by `dedup_key`), mirroring how "Gaps" is itself built (a modal, not
  a tab). *(Stage-4 section-scoping, needing GROBID + the plugin, remains open — see open backlog #30.)*
- [x] **#33/#34 Citation & bibliography engine — LibreOffice adapter, full P0/P1/P2 build-out** (inc 106-108,
  162-171, 193, 320-464). The competitor-informed roadmap
  (`future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md` + its `…competitivereview.md`
  companion) is fully shipped: **P0** correctness/safety (incs 320-331 — bounded bibliography ranges, safe
  flatten, transactional refresh/diagnostics, the live-search citation composer); **P1** parity (incs 344-385 —
  the "Citations in this document" panel, bibliography editing/categories/ordering/chapter-section blocks,
  targeted refresh scopes, document-local dirty-state tracking, note-style/footnote/endnote placement +
  conversion + tracked-change safety, the citation-style manager + local CSL editing/import/export); and the
  **P2 leapfrog track** (incs 459-464, confirmed closed via memory `callosum-p2-leapfrog-roadmap`) — citation
  integrity preflight (#19), the evidence-aware Suggest-Citation composer (#17), Citavi-style "Insert evidence"
  (#20), open-science statement insertion (#21), citation coverage audit (#18), and Zotero-to-callosum
  conversion (#22). Full narrative for any specific increment: its own `increment-notes/INCREMENT-NNN-NOTES.md`
  (106-464 span this arc) — not re-narrated here.
  *(Still genuinely open — see open backlog #33/#34: traveling-library portability; #43 the Google Workspace
  Marketplace one-click install; the recorded Word/Google-Docs feature-parity future goal.)*
- [x] **#33/#34 keyboard/screen-reader accessibility pass** (inc 474, round 3 item #3). All 13 UNO
  dialog-construction sites gained a real Tab order, initial focus, LibreOffice-accessibility-bridge field
  names (via `a11y.py`'s `TabIndex`-adjacent `Tabstop=False` label pattern — VCL's real mechanism, found by
  probing the actual installed LibreOffice after a `LabelControl`-property first attempt crashed real-UNO),
  and Enter-to-add/remove in the composer (Zotero's own shortcut). New `spike_dialog_accessibility_wiring`
  proves it against real `AccessibleName`/`XKeyListener` behavior; real per-keystroke Tab traversal and
  screen-reader announcement still need the manual script in `INCREMENT-474-NOTES.md`.
- [x] **#35 My Publications — Layer 4, deterministic grounded prospection** (inc 386, 389, 390, 391) — grounded
  citation gaps (OpenAlex works citing shared reference anchors); domain-union scoping; grounded emerging citing
  topics (equal three-year windows, visible count differences); grounded citing-author connections (stable
  author ids appearing across ≥2 citing works and ≥2 own publications). All descriptive, never a forecast or
  importance score; every count opens to exact evidence. *(Optional LLM narration over the grounded data remains
  deferred — no need to build it unless it becomes useful.)*
- [x] **#36 Meta-analysis assisted-extraction funnel — batch draft + retrieval narrowing** (inc 347, 348; the
  core SP1/SP2a/SP2b funnel shipped inc 249-259) — "Draft all un-filled rows" sequentially proposes across
  eligible rows with determinate progress, never bulk-accepts (every candidate keeps its per-cell verify gate);
  for papers over the 12-chunk budget, empty field labels are embedded locally and vector search narrows to that
  paper's own chunks before the consent-gated provider call. *(Far future, its own workspace: screening/PRISMA,
  double-coding/IRR [human-only, no-independent-coder veto holds], RoB instruments, figure extraction [point at
  WebPlotDigitizer, don't build it] — see open backlog #36.)*
- [x] **#37 Equity & integrity signals — overlooked-work lens + positive self-correction + field self-citation**
  (inc 279, 286, 393; baseline = #25, inc 457) — the overlooked-work lens (Merton 1968) + its header-density UX
  follow-up (Discover consolidation); a defensible correction-record slice (Crossref/Retraction Watch correction
  FACT → a read-only system tag + green badge + evidence-linked Details row; no badge means only "not surfaced by
  these registries," never "no correction exists"). *(Still open — see open backlog #37: an evidence-grade
  replication source if one emerges; null-engagement; 2 principle-fraught forensic candidates needing the A-A
  values layer.)*
- [x] **#38 Research-impact analytics — Project A, local usage instrumentation** (inc 450) — a zero-egress
  event log + Settings → "Your usage" dashboard: counts (never payloads) of citation export / duplicate
  resolution / metadata re-resolve / locating a quote / reviewing a flagged reference; on by default (nothing
  egresses); always inspectable/exportable/deletable; no opaque "flourishing score." *(Project B, the cross-user
  impact signal, remains far-future/gated — needs N>1 users + an accounts/hosting decision — see open backlog
  #38.)*
- [x] **#40 Publishers tool — SciELO/TOP Factor/AJOL/NLM-MEDLINE/thumb auditability** (inc 448, 451, 452, 453) —
  a live SciELO regional-index lookup; a locally-mirrored TOP Factor transparency rubric (its `Total` shown only
  inside an expanded per-category basis block, never bare); a locally-mirrored AJOL CC-BY-4.0 snapshot
  (including AJOL's own JPPS rating, shown plainly); a live NLM MEDLINE-indexing lookup (self-paced against
  NCBI's rate limit, precisely named `indexed_in_medline` after a live overclaim check caught "MEDLINE" ≠
  "PubMed"); `fit_rank`/`weighted_rank` thumb auditability when weighting diverges from topical fit. Redalyc
  (TLS cert failure), Latindex (confirmed closed), COPE (bot-blocked), and OASPA (no structured members API)
  were all live re-checked, not assumed, and confirmed not buildable. *(Still open — see open backlog #40:
  self-archiving/green-route [needs a Jisc-registered key]; Redalyc/Latindex if they ever reopen; COPE/OASPA if
  an API appears; user exclusion/filtering, deferred on purpose as ethically fraught.)*
- [x] **#44 Lakens-catalog integration — RegCheck (Increments 1/1b/2/4/5) + DEBIT — fully closed** (inc
  250/251, 352, 387, 425-433, 467). The transparency-signals auditor + persistence (1/1b); `DocumentTextProvider`
  (2, PDF/JATS/XML/HTML/DOCX/ODT/plain/TeX); the conservative table-aware statcheck slice (5-partial, inc 387);
  document-scoped chunk/search/embedding consumers as the hard prerequisite so a registration attachment can't
  contaminate article synthesis or Methods reads (425); local registration-reference extraction + four honest
  transparency states (426); explicit OSF/DataCite candidate discovery (427); confirmed OSF/AsPredicted/local
  acquisition with immutable content-hash versions (428); canonical evidence-bearing commitment extraction
  (429); section/study-aware article retrieval (430); persisted evidence-bound comparison rows + human review +
  stale-basis detection (431); the side-by-side inspection UI + security audit (432); bounded pagination/
  transactional revalidation/fail-closed extraction/exact search receipts (433, the acceptance-audit
  close-out). This is the fraught, gated **RegCheck** track — see the individual increment notes for the full
  narrative. **Increment 4 overlapped CRediT #26** (closed). **Increment 5's DEBIT slice shipped inc 467**
  (item #4 of the confirmed post-P2 backlog sequence, memory `callosum-next5-backlog-roadmap`): the binary-data
  analog of GRIM/GRIMMER (Heathers & Brown 2019, an unpublished OSF working paper, no DOI), extending
  `app/backend/methods/grim.py` + the inc-401 paper-aware-save pattern exactly. Research before design found
  Increment 5's original phrasing ("DEBIT/duplication analysis and perhaps a z-curve") actually named three
  separate things — **duplicate-publication detection and z-curve were spun off as their own new backlog items,
  #54 and #55**, each needing its own Principles + APPROACH-AVOIDANCE pass (duplicate-detection risks the
  no-accusation boundary; z-curve needs LLM-assisted extraction). **#44 is now fully closed.**
- [x] **#48 WIP integration — Checklists / Critique / Meta-Reference — fully closed** (inc 441-447) —
  Checklists (Transparency/mixed-model/Bayesian/meta-analysis reporting audits, each via the same exact-
  snapshot receipt seam, `not-found` rows becoming reviewable `info` candidates only when their gate is on, never
  a negative finding from silence); Synthesize > Critique (a local-only exact-snapshot job comparing ≤12 bounded
  draft claims against matching-model Library embeddings, high-confidence contrast only, no defect finding or
  score); Work > Meta-Reference (`inspect_reference`/`audit_reference_list` reused unmodified against the
  manuscript's own cited Library papers, two new additive tables, an honest "not computed" self-citation
  degraded path). Citation-context stays permanently out of scope for WIP (an unpublished draft has no DOI in
  any citation graph).

## Competitive-benchmark revisions — CLOSED (2026-07-19 audit, migrated 2026-08-09)
- [x] The full A1-A10 (bug/gap close-outs) and B1-B5 (collaboration, OCR, citation-context, library-bundle
  sharing, mobile reading — including B1 SP2 gated MCP writes, inc 216) competitive-benchmark lists are
  completely closed. Full detail: `future-tracks/opus4.8_future-tracks_benchmarkrevisions.md` + the relevant
  increment notes.

## Shipped — breadcrumbs (inc 84 through inc 408+, migrated from `INCREMENT-BACKLOG.md` 2026-08-09)

*(This is the original condensed breadcrumb trail that used to live inside the open backlog file's own
"Shipped — breadcrumbs only" section — preserved verbatim below rather than re-summarized, since it was
already compressed prose. New closures go in the dated sections above, in this file's own `- [x]` style, not
appended here.)*

- ⭐ Star key publications + scope the AI summary to starred — inc 84
- Review queue for OpenAlex works missing from My Pubs + import missing own-papers — inc 85
- Un-dismiss for missing works — inc 92
- Import coverage beyond Zotero (BibTeX / RIS / CSL-JSON; also covers Mendeley/EndNote) — inc 93
- Scan / refresh library folders — inc 87; Watched folders — inc 98
- "UNSORTED" cluster (`needs_review`) — inc 80
- Filter library by type — inc 91
- PDF Reading mode (⛶ Read / ⤢ Exit / Esc) — inc 101
- Re-score line-wrapping fix — inc 86
- More settings → axis cutoff default in Settings — inc 105 *(ongoing: other prefs as they arise)*
- Open-science signals — statcheck v1 + library lens + header chip (95/97/100); p-curve (126) + GRIM/GRIMMER
  (127/129) + unified "N to review" facet (133); comparison-bound forms (inc 333) + conservative table-aware
  statcheck for PDF/JATS/XML/HTML/DOCX/ODT attachments (inc 387). **#27 closed.**
- Citation engine Phase 1/2 + LibreOffice adapter — inc 106/107/108 *(Word + Google Docs adapters — see below)*
- **Frontend/UX pass — inc 109–116:** brand-asset source move; PDF page-view options fit-width/two-up (was #2);
  editable Translators (part of #5); multi-paper focus query (see #7); button canonicalization; synthesis
  ✕-close + AXES ambient outlines. *(Journaled in `RECOVERY-LOG.md`.)*
- **My Publications overhaul SP1–SP3 — inc 117–119:** dashboard restructure + browsable publication cards;
  group-by-domain; citing articles + per-paper citation counts *(only Layer 4 prospection remains — see #35)*
- **QA mechanism** — surface-coverage gate + Codex-exec supervisor + watched inbox (rule #10) — inc 120
- **THEORY/METHODS accordion** on a self-registering module registry — inc 121; statcheck relocated into
  METHODS — inc 122
- **Synthesis overview fix** — front-matter-aware no-query selection (123) + evidence-traceable Overview (124) +
  strengthened classifier (125)
- **Findings subsystem** — FACT-vs-candidate store + Review pane (130); retraction producer Crossref/OpenAlex
  (131) + Retraction Watch DB (132); statcheck candidates + unified facet (133); on-import auto-check + RW
  staleness nudge (134); on-import extended to remaining DOI-bearing routes (224) *(remainder — see #31)*
- **Literature gap-finder** — backward gap (135) + watched-folder focus-rescan (136) + v2 forward/axis-scoped/
  cached (137) + followed-authors as a third source (454, #29 closed)
- **Auto-select top library paper on load** (138); accordion tabs-within-a-section (139)
- **End-user experience pass (rule #11 + EXPERIENCE-PASS.md)** + persona-agent mechanism (140); the
  build-and-test slate — statcheck path (141), determinate progress (142), durable keyword deletion (143),
  export highlights (144), discoverable focus query (145)
- **BYOK arc — inc 146–152 (#10 + #39):** Gemini key in Settings; Test-key; synthesis "AI is off" nudge;
  multi-provider engine Gemini/OpenAI/Anthropic/local + Settings provider UI; validation disclaimer +
  help-assistant toggle; OS-keychain storage
- **Synthesis coverage readout + top_k + answerability** (153, #7) *(coverage beyond the 24/50-chunk cap
  remains — a real multi-pass/map-reduce change, its own design)*
- **Track C SP1 + SP2 (#30) — inc 156–159, 271/272, and 2026-07-22:** highlight-to-suggest/evaluate engine +
  Cite pane; LibreOffice Suggest macro; formatted "Cite as…"; beyond-library suggest (OpenAlex graph expansion +
  public metadata search, explainable reasons, security-audited) wired into both the web Cite pane and (as of
  2026-07-22) the LibreOffice adapter's Suggest macro too *(Stage-4 section-scoping remains — see §4)*
- **Reading-workflow markers (Bella's ask) — inc 219–223:** reading queue (219); read/unread + priority markers
  + sort + filter facet (220/221); "By priority" unset-tier recency tiebreak (223). **Thread complete.**
- **Word-processor adapters (#33/#34) — inc 106–108, 162–171, 193:** LibreOffice macro → one-click .oxt v2; Word
  add-in Office.js SP1–3; Google Docs Apps Script add-on + cloudflared bridge + setup automation. *(Deferred
  polish — see §4.)*
- **Reading-pane run — inc 175–179:** remembered scroll; Notes-panel split + filter/search; next/prev-mark nav
  + hotkeys. **PDF highlight minimap** (215) and **precise-highlighting word-reconstruction** (270) also shipped.
  *(Only a "fit-height" 4th page-view mode remains, render-risk + needs a browser eyeball — low priority.)*
- **README front-door draft (#11)** (178, maintainer voice-pass remains — see §2); **credit-the-lineage** —
  statcheck slice + shared `.method-credit` (180) + dependency NOTICE pass (181) + the overlooked-work lens
  credit (282) + the shared "add missing to library" correctness pass across every method-credit surface (293).
  **Backfill audit closed inc 466** (item #3 of the post-P2 backlog sequence — the proposing future-tracks doc
  was stale; most of it was already built): added the two genuine gaps found — Retraction Watch credit (Settings
  → Local Maintenance, no canonical paper exists so text-only, matching the SciELO precedent) and a real
  `LakensCredit` block (Crone & Green 2025, DOI verified) replacing 7 panels' passing sub-text mentions with an
  actual clickable, library-addable citation — plus `pyjwt`/`keyring` NOTICES gaps and a stale header fix. **Also
  found and fixed a real, separate bug while live-verifying**: `MethodCreditButton` (used by ~12 panels) showed
  "✓ added to library" without ever polling `POST /library/import`'s async job to completion — a real click could
  show success while the import had actually failed (confirmed via a genuine write-lock collision with a
  concurrent watched-folder rescan). Now polls to the real outcome, matching `GapsModal`'s own pattern. **#8 is
  complete.**
- **Literature discovery (#28) — inc 182–192, 286, 295–297:** Search tab (Crossref + PubMed + axis-relevance
  highlight) + Feed tab (bioRxiv/medRxiv + PubMed-keyword + journal-ISSN); Wanted/Gaps/Overlooked + Feed
  consolidated into Discover → Search (286, resolves #37's header-density UX finding); follow-by-title +
  typeahead (295); selectable sources (296). *(Only "register more sources as they arise" remains.)*
- **Accounts arc (#15) — inc 194–202:** Sign in with ORCID (194); superuser flag & runbook (195); email/Google
  (196); opt-in E2E sync — crypto/changeset (197), `sync_uid` engine + FK + link + natural-key (198–201),
  reference sync-server + transport + opt-in `/sync/*` (202). *(SP3c UI + deploy + hardening + SP4 remain — §3.)*
- **A1–A10 close-out list — inc 203–212:** dormant `contradicted` status (203); axis count-badge carries
  hide-uncertain (204); THEORY→Discover placeholder removed (205); drag-to-axis (206); color tags (207); saved
  searches (208); full-text PDF search FTS5 (209); per-paper citation counts (210); Curated Axis SP1/SP2
  (211/212). **Closes the entire A1–A10 benchmark list.**
- **B1 read-first MCP server** (213) **+ B1 SP2 gated agent writes** (216, opt-in, provenance-stamped, audited,
  reversible — confirmed shipped, was miscategorized as open before this audit).
- **Metadata enrichment SP1/SP2** (217/218, Europe PMC + PubMed sources).
- **Bayesian auditor — full arc, inc 241–244** (JZS t-test BF, completeness checklist, correlation BF, Tier-3
  advisories). *(ANOVA/regression BF declined — see §4.)*
- **Publishers "where to submit" tool SP1a/SP1b** (245/246).
- **LMM-reporting auditor** (247, *cross-method deferrals — see §2*); **accordion panels polish + Cite tabs**
  (248); **meta-analysis reporting auditor** (249, consumer-side).
- **Transparency-signals auditor + persistence** (250/251, the Lakens-catalog increment 1/1b).
- **Meta-analysis workbench SP1/SP2a/SP2b + the assisted-extraction funnel** (252, 253, 255, 258, 259).
  *(Next escalations — see §4.)*
- **In-app remote-access-lockout recovery** (254); **unified multi-provider BYOK / custom LLM providers** (256);
  **autonomous close-out sweep** (257).
- **Citation-equity → Citation concentration** (227–230, 260, values rework — dropped the geography/gender
  signal on principle). **CRediTer contribution-statement builder v1** (261, *UX follow-ups — see §2*).
- **600-line-cap cleanup + the line-budget gate itself** (262, 264 — backlog #20 ratchet step 1; #47 closed).
- **OpenURL institutional link-resolver** (263); **reversible un-merge** (265, #16); **critical-review
  supplement, single-paper AND multi-paper** (266, 271 — backlog #12, confirmed shipped, was miscategorized as
  gated/unbuilt before this audit — meets the #13 auditability bar throughout).
- **The `database is locked` reliability arc — CLOSED end-to-end, inc 272–281.** WAL + busy_timeout (219);
  transaction-level short-write retry (272); long-job incremental commits across scan/ingest/enrich/methods/
  read-heavy jobs, Increments A–D (273–278); the overlooked-work lens (279, #37); the last residual
  snapshot-upgrade edge closed via a uniform `run_write` sweep over every short SELECT-then-write handler (281).
  *(A prior version of this file carried ~60 lines of this saga's history under "still open" framing; it is not
  open — `tests/test_short_write_sweep.py` machine-enforces the invariant.)*
- **Workspaces navigation — inc 280, 284–292, 296–303:** the two-level menu-bar nav (280); DESIGN §5 rewrite
  (284); the one-time "what moved" hint (285, confirmed shipped — was miscategorized as an open follow-up before
  this audit); discovery-surface consolidation (286); Synthesis+Work split (287); library header polish + Open
  Data signal (288); workspace scroll + My-Pubs polish (289); selected-paper tab + PDF reorder (290); Discover
  selected-paper cue (291); Discover Search/Journals recall (299); mobile workspace switcher (302); the
  navigation rubric rewrite + a backlog reconciliation pass (303).
- **PDF text-health "missing section labels" fix** (283); **library retractions refresh + RETRACTED badge**
  (292, *filterable-facet integration remains — see #19*); **Reading Queue stratified by priority** (294);
  **Synthesize Ask/Critique split** (298).
- **Fast pytest** — targeted runs + xdist parallelism + testmon change-based selection (300).
- **Six misc UX fixes** — Trash search, read-mode menu bar, Discover recall, duplicate card, invert sort,
  missing-PDF filter (301).
- **Per-item import/embed progress titles** (304, #4); **web-stack CVE migration** (305, FastAPI/Starlette —
  *the httpx→httpx2 TestClient follow-up remains, see §1*); **richer keyword tags** — OpenAlex topics + PubMed
  MeSH (306) **+ everywhere** — Feed/Search-save background-enrich + 🔎 re-resolve (307, #18 complete).
- **QA-pass fixes** (308) — read-only credit-403 gating, mobile Help layout, Discover Clear × — **all three
  browser-verified 2026-07-19** (a Playwright follow-up session; the Clear × fix needed a genuine second pass —
  see `INCREMENT-308-NOTES.md`).
- **WIP manuscript workspace MVP — incs 351–356.** The unprocessed source prompt was reconciled from the watched
  inbox on 2026-07-24 after confirming the implementation directly: WIP is a distinct top-level manuscript
  collection with watched-folder discovery, workflow/files/tasks/references/activity, exact content checkpoints,
  snapshot-bound deterministic checks/findings, reverse Library navigation, dedicated facets/context actions, and
  tab reorder parity. The canonical design source now lives in `future-tracks/`.
- ✅ **#50 "Status" menu — cross-feature async-job popover — CLOSED 2026-07-28 (incs 406-408).** Phase 1
  (inc 406): a click-toggle popover after Help/Settings aggregating every `JobStore` on `api.state` (~30
  features) via reflection, with real progress/ETA where a job reports it and an honest indeterminate
  spinner where it doesn't; per-row dismiss + clear-all-finished + a 1-hour auto-expiry backstop. Phase 2
  Wave 1 (inc 407): audited every "library refresh"-style job for real-progress coverage — citation-count
  refresh, metadata enrichment, library scan, library import, and bundle import already had it; the one
  gap (`retraction_jobs`) got a one-line `mark_progress` fix. Phase 2 Wave 2 (inc 408): Ask's per-candidate
  verification loop now reports real progress/ETA (retrieval + the LLM generation call stay indeterminate
  on purpose — a single opaque blocking request has no sub-progress signal, and a cache hit would make a
  naive ETA misleading), live-verified end-to-end with a real Gemini call against a disposable instance.
  **`dedup_jobs` remains the one deliberately-indeterminate job in the app** (no per-item loop exposed to
  the router without restructuring the duplicate-detection algorithm itself) — an honest gap, not an
  oversight; revisit only if that algorithm changes for other reasons.
