# Increment backlog — OPEN (audited & reorganized 2026-07-19, at inc 308)

> **What this file is.** The running list of what's genuinely left to build. Full shipped detail lives in
> `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` (the per-increment diary) and `INCREMENT-BACKLOG-DONE.md`;
> this file's job is to say **what's still open**, not to re-narrate what already shipped.
>
> **Numbering is stable across edits.** Item numbers are cross-referenced from `CLAUDE.md`, session handoffs, and
> increment notes ("backlog #20", "backlog #5"), so a number is never reassigned. When an item ships, it moves to
> the **Shipped — breadcrumbs** section at the bottom *keeping its number* in parentheses, so `grep "#12"` still
> finds it. Gaps in the numbering (#1, #2, #6, #10, #39, …) are shipped items relocated this way.
>
> **The autonomous-vs-Cliff cut line is retired (2026-07-19).** The old split ("CC builds top-down, everything
> below `⛔ NEEDS CLIFF` is mine") no longer organizes this file. It's replaced by grouping items by **what they
> actually are** (near-term polish / needs your decision / gated on something destructive-security-outward-facing /
> longer-horizon track), with the same **why-it-needs-you labels** as before (**[decision]**, **[security]**,
> **[destructive]**, **[gated]**, **[blocked]**, **[outward-facing]**, **[infra]**, **[future track]**,
> **[non-code]**) attached inline. Nothing about *what* needs a human call changed — only the bookkeeping construct
> that used to sort by it.
>
> **This pass (2026-07-19) audited every open item against the increment-notes through inc 308** (not just this
> file's own claims) and found real drift — three items marked open/gated were actually already shipped:
> **#12** (critical-review, both single-paper *and* multi-paper — inc 266 + inc 271), **B1 SP2** (gated MCP agent
> writes — inc 216, called out as "the one genuinely-new architectural item" while already built), and the
> **workspaces-nav "what moved" hint** (inc 285). Also fixed: the **#5** multi-URL field had already shipped
> (inc 214) leaving only per-attachment PDF serving open; the **SQLite `database is locked` saga** (a ~60-line
> history in the prior version of this file) is fully closed (inc 272–281) and is now one breadcrumb line; and the
> entire **Competitive-benchmark A1–A10 + B1–B5 list is now closed** (only D, an open proposal, remains). Verified
> directly: no `SECURITY.md`/`CITATION.cff`/`.env.example`/`uv.lock`/`.pre-commit-config.yaml` exist yet, so **#20**
> stays genuinely open as described.
>
> **Follow-up correction (2026-07-22):** **#30** was ALSO stale, missed by the 07-19 audit — its SP2/Stage-3
> "beyond-library suggest" had shipped inc 271/272, landed as one large uncredited Codex commit with no
> increment notes of its own, so it never got folded back into this file's status line. This is the same class
> of drift the 07-19 pass found elsewhere (a shipped feature miscategorized as open) — a reminder that a
> commit lacking its own `INCREMENT-NN-NOTES.md` is a real risk factor for this file going stale, not just an
> aesthetic gap.
>
> **Guiding principle (Cliff's):** *reference manager first.* The verified-synthesis crown jewel only matters if
> Callosum is a credible day-one replacement for Mendeley/Zotero — so table-stakes reference-manager UX stays
> high priority; differentiators come after.
>
> **Scope note:** the bigger **longer-horizon tracks** have detailed build-prompt docs under **`future-tracks/`**
> (its `README.md` is the index) — that's the canonical design source; the entries below are the queue summary.

---

## 1. Near-term (small, self-contained, no design decision needed)

- ✅ **QA 2026-07-19 batch — CLOSED inc 309.** All 7 findings now fixed + browser-verified (inc 308 fixed 3;
  inc 308's Playwright follow-up + inc 309 closed the rest). **[Medium] the metadata-only-paper PDF 404** was a
  **real gap, not a fixture artifact** — fixed by threading the library card's known `attachment_count` through
  to `PdfViewer`, which now skips the doomed fetch entirely (zero console error, zero network request) rather
  than relying on a 404 to fall back gracefully. **[Low ×4] mobile CSS spacing** — all 4 fixed (Feed filter
  buttons now content-sized + wrap as a group; the whatsnew notice gets a shorter mobile copy, 82px→48px; Settings
  provider badges wrap onto their own line instead of colliding with Use; Work's provenance line gets 14px inset
  instead of touching the screen edge). **[housekeeping]** `route_00_smoke_readonly.md` steps 4–5 rewritten to the
  actual current pane structure (confirmed live: left = Axes+Review, right = Details+GRIM+Statistics
  check+Bayesian+Mixed-model+Transparency), and its "404 is expected" pass criteria fixed to match the new
  behavior. See `INCREMENT-309-NOTES.md`.
- ✅ **httpx→httpx2 TestClient migration — CLOSED inc 309.** Turned out to need **zero source changes** — starlette
  1.x's `testclient.py` auto-prefers `httpx2` when installed, falling back to `httpx` + a deprecation warning only
  when it's absent. Added `httpx2>=2,<3` to `requirements-dev.txt` + `pyproject.toml`'s `test` extra (dev/test-only,
  same author/org as the existing `httpx`/`starlette`; audited PASS). Along the way found this dev environment's
  installed fastapi/starlette had never actually been bumped to inc 305's pinned versions — synced via
  `pip install -r requirements-dev.txt`, which is what let the warning reproduce at all.
- ✅ **Per-attachment PDF serving — CLOSED inc 316 (#5 complete).** `GET /papers/{paper_id}/pdf?attachment_id=`
  opens a specific attachment (the merge-survivor multi-PDF case); the Details "Files" list wires each button to
  its own attachment; a citation now opens the exact (PDF) attachment its evidence came from rather than always
  the primary — a real coordinate-honesty gap found and fixed in the same pass (a non-PDF supplementary-text
  attachment's citations still degrade to the primary, gated via `_is_pdf_attachment`, never surfaced as a
  broken 404). See `INCREMENT-316-NOTES.md`. **Remaining, filed as a follow-up, not urgent:** the same
  attachment-awareness for methods-evidence targets (statcheck/GRIM/Bayes/LMM/meta-analysis/transparency/
  reference-integrity) and `37_cite.jsx`'s citation object — same latent risk class, safe-by-omission today.
- ✅ **QA runs 20260702/03 remaining re-triage — CLOSED inc 317.** Every Critical/High/Medium/Low from routes
  24/27/30/32 re-verified live against a fresh fixture, not assumed. Route 30's Critical (PATCH/tag/cite 500s) +
  its downstream Highs/Mediums — **confirmed fixed** (the SQLite write-lock arc, incs 272–281). The 3
  console-error-budget Mediums (routes 24/27/30) — **not bugs**: Chromium's own network-layer logging for
  intentionally-triggered 4xx/5xx during adversarial checks, not an app `console.error()` (the fetch wrapper only
  ever calls `console.warn`). Route 27's "Import doesn't accept PDF" — **by design**, documented in the help
  corpus. Route 27's "outside-path scan accepted" — **already a known, accepted local-app tradeoff** (CLAUDE.md's
  security baseline). Route 32's "no exact-precision citation reachable" — **a QA-fixture limitation**, not an
  app bug (the seed doesn't pre-bake a verified citation; not deterministically seedable without faking the whole
  synthesis pipeline). **Two real, still-open bugs found + fixed:** `DuplicatesModal`'s un-dismiss didn't
  refresh the candidate list in-place (only a full modal close/reopen recovered it — narrower than the original
  "stays absent even after a fresh scan" framing); `ScanModal` lost mid-scan progress visibility across a modal
  close/reopen (no data loss — the job always completed server-side — just lost UI feedback). See
  `INCREMENT-317-NOTES.md`. **Left as a documented, non-urgent loose end:** the console-error-budget QA-POLICY
  assertion could be refined to exclude expected-adversarial 4xx/5xx noise, so future QA runs stop re-manufacturing
  the same 3 non-bugs.
- ✅ **#31 cadence auto-refresh — CLOSED inc 318.** An opt-in, staleness-gated automatic refresh of the
  Retraction Watch mirror, following the client-driven pull pattern already established for Feed's own
  auto-refresh (no backend scheduler exists, and none was introduced). Default off (Settings → Local
  Maintenance checkbox); when on, fires the full re-check batch (`POST /methods/retraction/run` — mirror
  refresh + re-check every paper) on launch/focus once the mirror is >30 days old or never downloaded, gated by
  a 1-hour attempt throttle found necessary during live verification (without it, a mirror that can never
  become fresh — e.g. no contact email set — would re-run the batch on every window focus indefinitely). See
  `INCREMENT-318-NOTES.md`. **Remaining #31 sub-item, still a deliberate v1 non-goal:** folding the statcheck
  signal chip into the unified findings facet (coexist on purpose — revisit only if it starts reading as
  redundant).
- **#28 remaining slice:** more Feed sources are a one-line `register()` each as they come up; a true background
  polling daemon is **deliberately not built** (pull-first design choice, not a gap).
- ✅ **#45 My Publications example name — CLOSED 2026-07-22.** Swapped "e.g. Ada Lovelace"/"e.g. A. Lovelace" for
  "e.g. Karen Spärck Jones"/"e.g. K. Spärck Jones" in the name/alt-names placeholders (`35a_mypubs.jsx`).

---

## 2. Needs a design decision from Cliff (not destructive/security — just your call)

- **statcheck signal/work-state duality** (from #14 of the original close-out list): the "⚠ flagged" (signal) vs
  "📋 to review" (work-state) coexistence is intentional (inc 133) but still reads as two overlapping systems to
  a new user. Clarify or collapse — low urgency, a UX nuance not a bug.
- ✅ **#11 README front-door — CLOSED 2026-07-22.** The screenshot landed with the `www/` commit; the voice
  pass was drafted to a scratch file for Cliff to react to (his explicit preference in the moment), reviewed,
  and applied as-is.
- ✅ **The `.local/` SQLite-inside-Dropbox note — CLOSED 2026-07-22.** The working library DB (209 papers,
  378MB) relocated to `C:\Users\cliff\callosum-data\library.sqlite`; `CALLOSUM_DB_URL` + `run-callosum.ps1`
  updated; the old copy left in place, untouched, as a backup.

---

## 3. Gated — destructive / security / outward-facing sign-off, or an explicit maintainer decision

- ✅ **#14 Permanent delete removes managed on-disk attachments — CLOSED inc 340 (2026-07-22).** Delete forever
  and Empty Trash now remove only root-contained `managed` files; linked, URL, out-of-root, shared, and unsafe
  paths survive. Reversible staging coordinates filesystem cleanup with DB/vector rollback; audit PASS.
- ✅ **#15 Sync UI (SP3c) — CLOSED (your remaining pieces below).** The accounts/sync arc (incs 194–202: SP1 ORCID
  sign-in, SP2 email/Google, SP3 the full E2E crypto+engine+server) + its SP3c UI, split into 2 increments and
  shipped 2026-07-19/20: **Increment A (inc 310)** — `GET /sync/conflicts` + `POST /sync/conflicts/{id}/resolve`
  (the backend gap a UI needed). **Increment B (inc 311)** — the actual **Settings → Sync UI**: setup (passphrase
  + one-time recovery code), a sequential enable gate, run + honest error handling (fixed two real bugs it
  surfaced: `/sync/run`'s wrong-passphrase 401 was firing the unrelated remote-access lockout overlay, now 422;
  an unhandled SQLite lock collision was a raw 500, now a clean 503), and the conflict-review panel. Browser-
  verified end-to-end with Playwright. See `INCREMENT-310/311-NOTES.md`.
  **Server hardening (per-user rate-limiting, retention, a backup runbook) — CLOSED inc 341 (2026-07-22).**
  `sync_server/rate_limit.py` (a standalone per-`sub` sliding-window limiter, 429 + `Retry-After`), `store.py::
  prune_tombstones` (a 90-day tombstone grace period, run via `python -m sync_server.prune_tombstones` on your
  own cron — not an in-process scheduler), and `sync_server/OPERATIONS.md` (backup/restore + the retention
  trade-off, stated plainly). Audit addendum PASS. **Still yours, not code:** the **live deploy** of
  `sync_server/` on Postgres + wiring the Authentik audience [non-code, your infra]; a per-user storage **quota**
  and a real **migration tool** (both explicitly out of this pass's scope — see `sync_server/README.md`'s "Not
  yet"); and **SP4 sharing** (= B2 collaboration, live-shared-library layer) [gated, its own design] — the only
  genuinely open threads left in #15.
- **Superuser *capabilities* — what the flag gates.** [decision] The flag shipped inc 195 (a verified-ORCID
  allowlist → an `is_superuser` indicator) but **no capability is wired to it yet** — a design decision for when a
  concrete superuser-only capability is wanted.
- **#42 Rotate the Gemini API keys** (and the CORE key pasted in chat during inc 75). [non-code — your manual
  action] `.gitignore` keeps all key material out of GitHub (verified via `git check-ignore`), so this is **not
  blocking** — but rotation is the only way to neutralize copies that exist in Dropbox version history / chat
  history outside git. Deferred by you.
- **#20 Harness hardening.** [infra] Cliff greenlit the full scope 2026-07-22 (static files + pre-commit/uv +
  branch protection, one at a time with sign-off per the standing rule below). **Closed 2026-07-22:** repo
  furniture — `SECURITY.md` (honest threat-model note + a placeholder for a private contact, since none exists
  yet), `CITATION.cff` (no ORCID — flagged as a maintainer TODO rather than invented), `.env.example` (every
  `CALLOSUM_*`/provider-key env var grepped from the actual codebase, organized by concern). **Not done, not
  asked for this pass:** `CHANGELOG.md` and SPDX file headers — narrower scope than what was actually
  requested; add them separately if wanted. **Also closed 2026-07-22 (inc 342):** uv adoption (`pyproject.toml`
  normalized + `[dependency-groups].dev` + committed `uv.lock`; CI installs via `uv sync --locked`); migrated
  the hand-rolled `tools/git-hooks/pre-commit` to the standard **pre-commit framework**
  (`.pre-commit-config.yaml`: ruff + whitespace/EOF/large-file hygiene + the size-budget script); 3 CI gates
  added **one at a time**, each confirmed green before the next (`alembic upgrade head` + `alembic check`
  against a temp DB; `pip-audit` blocking on `requirements.txt` + report-only on `requirements-dev.txt`;
  Dependabot enabled for `uv`/`npm`/`github-actions`); the `.claude/staged-harnesses/REGISTRY.md` for 7 dormant
  judgment-call checks (Pyright, tach, coverage gate, Hypothesis, embedding-drift, performance monitoring,
  bandit), each with an explicit activation trigger. **Branch protection also closed 2026-07-22:** Cliff chose
  the status-checks-only option (of three presented); added `required_status_checks` (`lint-and-test` +
  `e2e-smoke`) to the pre-existing "Callosum Rules" ruleset via the GitHub API — his admin bypass keeps his own
  direct-push workflow unchanged; a PR-required rule stays deferred until a second contributor is active. **#20
  is now fully closed.**
- **#21 Packaging & distribution (post-V1).** [exploratory] A Tauri desktop shell (`app/desktop-shell/`
  placeholder); an OS keychain for `GOOGLE_API_KEY` (+ future secrets) for a non-technical desktop user; desktop
  distribution + GROBID service ops (when Track C Stage-4 section-scoping lands — SP2/Stage-3 shipped inc
  271/272 and doesn't need GROBID). **Explored 2026-07-23 (inc 343), still open:** research doc +
  hands-on spike (`.claude/docs/future-tracks/desktop-packaging-tauri.md`) — the OS-keychain half is already
  mostly done (inc 152); a bare Tauri shell **confirmed working** against the real, already-running backend.
  The actual remaining engineering is bundling the Python backend + its ML stack (torch alone: 1.19 GB) into a
  Tauri sidecar — recommends evaluating an ONNX Runtime embedding-backend swap first, on its own merits, before
  any packaging build starts.

---

## 4. Longer-horizon future tracks — remaining slices only

*(Full design docs live in `future-tracks/`; most of these tracks are mostly-to-fully shipped — only the
genuinely-open remainder is listed here. Each still needs its own design + your graduation call, and must pass
the Principles + A-A gates before build.)*

- **#24 Bayesian auditor — ANOVA/regression BF.** Not a build queue item: **declined as a documented finding**
  (a candidate failed the J=2 → two-sample-t reduction check; no in-env anchor exists). Revisit only if a
  trusted anchor (R BayesFactor / a validated Rouder-2012 quadrature) turns up.
- **#25 Citation concentration — a real *field* self-citation baseline.** Needs per-field-paper reference
  fetches — a cost/design call. *(Overlaps #37's citation-credit-concentration remediation.)*
- ✅ **#27 statcheck — more test forms — PARTIALLY CLOSED 2026-07-22.** Test-stat `<`/`>` comparisons (e.g.
  `F(1,44) < 1, p > .05`) now handled — a p-value-interval consistency check reusing the existing "does a valid
  value exist" philosophy, never a false flag on an ambiguous case. **Still open:** results reported in tables
  — a structurally different problem (table-aware extraction), not a regex extension.
- **#29 Gap-finder — followed-authors as a source.** Blocked on a "followed authors" concept that doesn't exist
  yet; also external-search discovery beyond the library (overlaps #30/Track C).
- ✅ **#30 Highlight-to-suggest/evaluate (Track C), SP1 + SP2/Stage-3 — CLOSED, corrected 2026-07-22.** This
  entry was **stale** (this doc drifted per rule #6): SP2/Stage-3 "beyond-library suggest" was NOT unbuilt — it
  shipped inc 271/272 (2026-07-14/15, landed as one large uncredited Codex commit that never got its own
  increment notes, which is exactly why it fell out of this file's bookkeeping). `app/backend/citations/
  beyond_library.py` already does OpenAlex `referenced_works`/`related_works`/citing-works graph expansion
  anchored on the top in-library matches, plus Crossref/PubMed/OpenAlex keyword search — every candidate
  carries `reason`/`relationship_kind`/`relationship_label`, never a bare/citation-count score. Wired into
  `POST /citations/suggest` (`include_beyond_library`) and the web Cite pane (`37_cite.jsx`'s `BeyondSuggestionCard`
  + "Also search beyond my library" checkbox); security-audited PASS
  (`.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`). **Newly closed 2026-07-22:** the
  LibreOffice adapter's "Suggest citations" macro never called this path at all (in-library-only) — it now has
  the same opt-in checkbox + a save-then-cite flow for a picked beyond-library candidate (reusing
  `/discovery/save`, the same write path the web "Add to library" button uses).
  **Still genuinely open:** Semantic Scholar's *recommendations* endpoint (the client exists for citation-context
  work, but nothing calls its recommendations API — a new external fetch, trips the audit gate); a persistent,
  dismissible cache surface in the `gaps.py` style (what's shipped is a live, per-sentence, ephemeral flow — the
  backlog's original "persistent... cache... dismiss" framing describes a structurally different design that
  was never built); **Stage-4 section-scoping** (needs GROBID + the plugin). None of these is "the highest-value
  unbuilt thing" anymore — that framing was the stale part.
- **#33/#34 Citation & bibliography engine + plugins — the LibreOffice adapter's next phase.**
  Superseded by the much richer competitor-informed roadmap now at
  `.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md` (+ its
  `…competitivereview.md` companion), folded in 2026-07-21. **This entry was stale (caught 2026-07-23) — the
  P0 correctness/safety batch it described as "active now" was already fully shipped, incs 320–328:** the
  bounded managed-bibliography-range fix (a real bookmark PAIR replacing the old bookmark-to-document-end scan
  — `_write_bibliography` in `adapters/libreoffice/callosum_cite.py`), the safe "Prepare submission copy"
  flatten (irreversible-action warning, save-as-copy default, post-op integrity check via
  `verify_flatten_integrity`), transactional refresh + a document-diagnostics/repair command
  (`_transactional_apply` / `diagnose_document`), and the unified live-search citation composer with
  per-occurrence versioned metadata (`composer.py`, Phases 5a/5b/5c, incs 329–331) are all live in the code
  today — confirmed by reading the actual implementation, not just the increment notes. **The composer's
  manual-verification debt is now closed (2026-07-23):** Cliff hand-tested Phases 5a/5b/5c live in Writer —
  "a great start!" **P1 parity started (inc 344, 2026-07-23):** item #12, the "Citations in this document"
  panel, shipped — a modal (not yet live-refreshing; see `citations_panel.py`'s own docstring for why) list of
  every unique cited work with occurrence count, missing/orphaned + retraction status, live filter, and
  click-to-navigate. **Item #11, bibliography editing, shipped next (inc 345, 2026-07-23):** "Add uncited
  work(s)…" (a "further reading" entry with no in-text citation, via citeproc-js's own `updateUncitedItems`)
  and "Toggle bibliography exclude" (a cited work omitted from the bibliography, e.g. a personal communication,
  via `makeBibliography`'s field-filter `exclude` — both real citeproc-js mechanisms, newly wired through
  `POST /citations/render-document`), both now live in the same panel (which moved from read-only to
  read-write). Found + fixed a real, previously-latent bug along the way:
  `_write_bibliography`'s bookmark cleanup wasn't reliable across repeated rebuilds — see
  `INCREMENT-345-NOTES.md`. **P1 item #13 started (inc 346, 2026-07-23):** the menu now has independent
  **Refresh citations only** and **Refresh bibliography only** commands for large manuscripts. Both preserve
  full-document citeproc context but mutate only the requested surface; the explicit bibliography command also
  works while automatic bibliography rebuilding is paused. Real UNO proved the isolation in both directions.
  Still open within #13: manual-refresh mode / pause-formatting state, selected-citation and current-section
  refresh, dirty-state/progress/cancellation, and incremental rendering. **Needs Cliff's own manual click-through
  soon** (flagged explicitly for #12/#11's panel buttons and #13's two new menu commands — not left to drift like
  the composer's verification did). Remaining P1 (real CSL style manager, note/footnote styles, more bibliography
  editing controls — categories/chapter bibliographies/hyperlinked entries, remaining refresh/performance
  controls, portability, journal abbreviations, keyboard/accessibility) **and P2
  leapfrog** (evidence-aware Suggest-Citation, manuscript-level citation-coverage audit,
  pre-submission citation-integrity preflight, Citavi-style evidence-card insertion, open-science statement
  insertion, cross-manager conversion) — see the roadmap doc for the full prioritized list + a test plan.
  **#43** (a true Google Workspace Marketplace one-click install) is its own project (GCP project, OAuth
  verification, a public privacy policy, Google app review) — likely overkill for a local-first single-user
  tool; build only if a one-click install becomes worth the ongoing maintenance cost.
- **#35 My Publications — Layer 4.** Grounded prospection: citation gaps, emerging citing-topics, candidate
  collaborators (LLM narration over graph data only). Not started.
- **#36 Meta-analysis — the assisted-extraction funnel's next escalations.** The consumer-side reporting auditor,
  the effect-size converter, the extraction workspace (grid + select-in-PDF capture), the dataset loop + exports,
  and the AI-proposes/human-filters funnel are all shipped (SP1/SP2a/SP2b, incs 249–259). **Batch "Draft all
  un-filled rows" shipped inc 347 (2026-07-23):** sequentially proposes across eligible paper-linked rows, skips
  rows with existing candidates, shows determinate progress, continues past named row failures, and never
  bulk-accepts — every candidate keeps the same per-cell verify gate. **Retrieval-narrowed text shipped inc 348
  (2026-07-23):** for papers over the 12-chunk budget, the empty structured field labels are embedded locally and
  vector search is restricted to that linked paper's chunks; only the top 12 page-tagged passages cross the
  consent-gated provider boundary (still capped at 50k chars), with the old bounded document-order assembly as a
  failure fallback. **Far future, its own workspace:** screening/PRISMA, double-coding/IRR
  (human-only — the track's no-independent-coder veto holds), RoB instruments, figure extraction (point at
  WebPlotDigitizer, don't build it).
- **#37 Equity & integrity signals — remaining.** The overlooked-work lens shipped (inc 279) and its
  header-density UX follow-up is resolved (Wanted/Gaps/Overlooked + Feed consolidated into Discover → Search,
  inc 286). Still open: a real field self-citation baseline (= #25); **positive self-correction** (not started);
  the **2 principle-fraught forensic candidates** (recorded with the no-index/no-accusation reframing, most
  needs the values layer — A-A no-accusation veto applies directly).
- **#38 Research-impact analytics.** [future track — gated] Opt-in, local-first, commons-structured measurement
  of whether Callosum changes how people research. **A.** local usage analytics (zero-egress; buildable-now) vs
  **B.** cross-user impact signal (far-future, gated). Must pass Principles + the A-A values layer (default-deny,
  compute-locally/transmit-summaries-only, public field registry, commons reciprocity). Graduation is your call.
- **#40 Publishers tool — deferred signals.** SP1a/SP1b (the engine + panel + weighting + first-use choice gate)
  shipped. Remaining: green-route/TOP-factor/regional-index (AJOL/SciELO/Redalyc/Latindex) legitimacy signals;
  user exclusion/filtering; thumb auditability; the real field self-citation baseline (= #25 again).
- **#41 User-authored modules (plugins).** [future track — record only] Deferred record of the idea + open
  questions. Do not build a plugin system until a dedicated design pass.
- **#44 Lakens-catalog integration — increments 2–5.** Increment 1/1b (the transparency-signals auditor + its
  persistence/review-queue) shipped (incs 250/251). Remaining: **Increment 2** — `DocumentTextProvider` adapters
  for JATS/XML, DOCX, HTML (unlocks better table/stat extraction + registration comparison). **Increment 3**
  (fraught, gated) — **RegCheck**, a registration↔paper delta table, human-verified, behind the auditability
  gate — an emergent value needing the "how auditable is auditable enough" question answered first. **Increments
  4–5** overlap existing tracks (CRediT = #26; more statcheck forms = #27; a collection-level z-curve).

---

## 5. Open proposals (undecided, not gated on anything — just not prioritized)

- **A scratch / ephemeral axis** (non-persisting / auto-expiring), to absorb cheap throwaway intersection-axes.
  May already be covered by "just delete the throwaway axis" + the full-text search box (the A3 FTS feature).

---

## 6. Declined / will-not-build (recorded so it's not re-proposed)

- **Folders/collections hierarchy** — superseded by axes (a coherent set → axis; an arbitrary flat set → tag;
  "read this week" → the needs-review filter; the Curated Axis is the manual-container path).
- **Arbitrary manual nesting** — declined; when nesting lands it's recursive *semantic* sub-axes (the My-Pubs
  subheading prototype), not folder-style nesting.
- **PDF translation** — out of scope.
- **Cloud multi-agent "write my review"**, website-bibliography publishing, mind-mapping/Alfred/Todoist
  integrations, embedded closed models, casual data-from-charts extraction — all declined.
- **The `.btn-*` divergent-button migration** — declined 2026-07-06 (maintainer decision pass): the divergent
  ghost/icon buttons stay documented exceptions per inc-86; new CSS already follows the canonical `.btn-*` rules.
- **A unidimensional star/paper rating** — declined 2026-07-06: reduces a paper to one number, erasing the
  multi-dimensionality tags capture. Color tags only (#A5/#207), never a rating field.
- **A tag's source as an always-on label/icon** — declined 2026-07-06: kept aesthetic-only (muted styling +
  tooltip + the All/Yours/Keywords filter already convey provenance).

---

## Competitive-benchmark revisions — CLOSED (2026-07-19 audit)

The full A1–A10 (bug/gap close-outs) and B1–B5 (collaboration, OCR, citation-context, library-bundle sharing,
mobile reading, including **B1 SP2 gated MCP writes — confirmed shipped inc 216**, previously miscategorized as
open) competitive-benchmark lists are now **completely closed**. Full detail in
`future-tracks/opus4.8_future-tracks_benchmarkrevisions.md` + the relevant increment notes. Nothing left here
except the recorded declines (folded into §6 above) and the one open proposal (§5, item D — the scratch axis,
which "pairs with #16").

---

## Shipped — breadcrumbs only (full detail in increment-notes/ + `INCREMENT-BACKLOG-DONE.md`)

*(Breadcrumbs through inc 202 were already condensed in a prior pass; this section extends them through inc 308.)*

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
  (127/129) + unified "N to review" facet (133) *(only "more test forms" remains — see #27)*
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
  cached (137) *(only followed-authors remains — see #29)*
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
  **#8 is complete.**
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
