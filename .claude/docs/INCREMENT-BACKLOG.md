# Increment backlog — OPEN (restructured 2026-08-09, at inc 466)

> **What this file is.** The running list of what's genuinely left to build. Full shipped detail lives in
> `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md` (the per-increment diary) and `INCREMENT-BACKLOG-DONE.md`
> (the closure index); this file's job is to say **what's still open**, not to re-narrate what already shipped.
>
> **Closure discipline (2026-08-09).** When an item here closes: **delete its entry from this file** — don't
> leave a growing "✅ CLOSED [paragraph]" bullet in place. Instead **append one compressed `- [x]` line to
> `INCREMENT-BACKLOG-DONE.md`**, keyed by the item's own stable `#N` where it has one, pointing at the relevant
> `INCREMENT-NN-NOTES.md` for full narrative. This file had drifted from that discipline (a duplicate in-file
> "Shipped — breadcrumbs only" section, plus several individually-growing closed entries) — the 2026-08-09 pass
> reconciled all of it into `INCREMENT-BACKLOG-DONE.md` and trimmed this file back to open items only. See
> CLAUDE.md's Increment workflow section for the enforced rule going forward.
>
> **Numbering is stable across edits.** Item numbers are cross-referenced from `CLAUDE.md`, session handoffs, and
> increment notes ("backlog #20", "backlog #5"), so a number is never reassigned. Gaps in the numbering are
> shipped/closed items now living in `INCREMENT-BACKLOG-DONE.md` — `grep "#12" INCREMENT-BACKLOG-DONE.md` finds
> them.
>
> **Guiding principle (Cliff's):** *reference manager first.* The verified-synthesis crown jewel only matters if
> Callosum is a credible day-one replacement for Mendeley/Zotero — so table-stakes reference-manager UX stays
> high priority; differentiators come after.
>
> **Scope note:** the bigger **longer-horizon tracks** have detailed build-prompt docs under **`future-tracks/`**
> (its `README.md` is the index) — that's the canonical design source; the entries below are the queue summary.

---

## 1. Near-term (small, self-contained, no design decision needed)

- **#28 remaining slice:** more Feed sources are a one-line `register()` each as they come up; a true background
  polling daemon is **deliberately not built** (pull-first design choice, not a gap).
- **#62 Duplicate-scan modal starts a brand-new backend job every time it mounts — a direct invariant-#5
  violation, spams the Status popover.** Found live 2026-08-28 (Cliff): open the Duplicates modal, close it,
  reopen it via a Status-popover click on that same scan's row → a second scan starts; repeating this piles up
  a new "Duplicate scan" row in Status every time, instead of resuming/reflecting the one already running or
  already finished. **Root cause, confirmed by reading the code (not guessed):** `DuplicatesModal`
  (`app/frontend/js/19_duplicates.jsx`, `useEffect(() => { runScan(); }, [runScan])`, ~line 82) unconditionally
  calls `runScan()` on every mount, and `runScan()` always does a fresh `apiPost("/papers/duplicates", {})` —
  there is no check for "is a scan already in flight" and no persistence of the current/last `job_id` across
  unmount (entirely component-local state, discarded on close). The backend has no guard either:
  `POST /papers/duplicates` (`app/backend/api/routers/duplicates.py:82-87`, `scan_duplicates_start`)
  unconditionally calls `request.app.state.dedup_jobs.create()` on every call, with no check of
  `dedup_jobs.list_all()` for an existing pending/running job first. `dedup_jobs`' own Status nav
  (`status.py:107`, `{"workspace": "library", "modal": "duplicates"}`) is exactly what reopens this same modal
  from a Status click, completing the amplifying loop Cliff described. **Fix shape (mirrors a guard already
  shipped elsewhere this same week, inc 507's `POST /grobid/docker/install`):** the backend endpoint should
  check for an existing pending/running `dedup_jobs` entry and return it (or 409) instead of always creating a
  new one; the frontend's `runScan()`/mount effect should check for (and resume polling) an already-in-flight
  job — via the Status endpoint, or a small "is one running" pre-check — before starting a fresh scan, and
  should not blindly restart on every remount. **Flagged by Cliff as fix-asap** (a direct, currently-shipping
  violation of invariant #5's "duplicate rows are impossible" guarantee) — pick up before other near-term work.
- **#63 Clicking an "Axis suggest" row in the Status popover fails to reopen the Suggest-Axes modal.** Found
  live 2026-08-28 (Cliff). **Root cause, confirmed by reading the code:** `axis_suggest_jobs`' Status nav
  destination (`app/backend/api/routers/status.py:106`, `{"pane": "theory", "section": "axes", "tab": "axes"}`)
  correctly opens the Axes pane/tab, but carries no `"modal"` key — and even if it did, there's nothing to
  consume it: every other Status-navigable modal (`duplicates`, `merge`, `critical-set`, `wanted`,
  `text-health`, `gaps`, `overlooked`, `scan`, `import`, `zotero-import`, `bundle-import`, `feedback`) is lifted
  to top-level state in `app/frontend/js/40_app.jsx`'s `onStatusNavigate` (~lines 210-240, one `if (nav.modal
  === "...") setXOpen(true)` branch per modal), but `SuggestAxesModal`'s own open/close state (`suggesting` in
  `app/frontend/js/15_axes.jsx:27`, `setSuggesting`) is purely local to `AxesPanel` and was never lifted or
  wired into that dispatch table — so a Status click can navigate to the right pane but has no way to actually
  reopen this specific modal. **Fix shape (mirrors the other 12 entries in `onStatusNavigate` exactly):** add
  `"modal": "suggest-axes"` (or similar) to `axis_suggest_jobs`' nav dict, lift `suggesting` to `40_app.jsx`
  top-level state (or thread an equivalent "open" signal down into `AxesPanel` via `ctx`/props), and add the
  matching `if (nav.modal === "suggest-axes") setSuggestAxesOpen(true)` branch.
---

## 2. Needs a design decision from Cliff (not destructive/security — just your call)

*(none currently — #58 resolved 2026-08-28: Cliff's call was "don't bundle, but make the existing opt-in
Docker setup dramatically more accessible," shipped inc 507; see `INCREMENT-BACKLOG-DONE.md`.)*

---

## 3. Gated — destructive / security / outward-facing sign-off, or an explicit maintainer decision

- **#52 Activate the hosted feedback relay and private Slack destination.** [non-code] [infra] [outward-facing]
  The in-app workflow and deployable relay shipped in inc 439; publication remains intentionally disabled until
  Cliff has a focused operations window. Create/select the private Slack channel and Slack app, enable an incoming
  webhook for that fixed destination, store `CALLOSUM_FEEDBACK_SLACK_WEBHOOK_URL` only in the hosted secret manager,
  deploy one HTTPS relay process behind a trusted reverse proxy, and configure clients with only the public
  `CALLOSUM_FEEDBACK_RELAY_URL`. Before enabling broadly: suppress bodies and authorization headers in proxy/APM
  capture for `/feedback/reports`; keep the relay's one-process limiter or add a shared ingress limiter before
  scaling; verify `/health` exposes only the configured boolean; submit a synthetic previewed report from Callosum;
  exercise missing-webhook, timeout, rate-limit, and disable paths; and confirm the message lands only in the
  intended private channel. Record the relay host/owner, monitoring and rotation procedure, then rotate by replacing
  the hosted secret, testing, and revoking the old webhook. Never put the webhook in a client `.env`, frontend/Tauri
  config, installer, log, issue, or feedback report. Full runbook: `feedback_relay/README.md`.
- **#42 Rotate the Gemini API keys** (and the CORE key pasted in chat during inc 75). [non-code — your manual
  action] `.gitignore` keeps all key material out of GitHub (verified via `git check-ignore`), so this is **not
  blocking** — but rotation is the only way to neutralize copies that exist in Dropbox version history / chat
  history outside git. Deferred by you.
- **#15 Sync — remaining threads.** [gated, non-code] Setup/enable/run UI, conflict review, server hardening,
  and the full SP4 sharing arc (identity → share → receive → revoke/block, staged like the original sync
  feature) all shipped — see `INCREMENT-BACKLOG-DONE.md`. **Still open, not code:** the live deploy of
  `sync_server/` on Postgres + wiring the Authentik audience [your infra]; a per-user storage quota + a real
  migration tool.
- **#49 Auto-updater — Cliff's own remaining rollout steps.** [non-code] The updater itself is live (inc 409) —
  see `INCREMENT-BACKLOG-DONE.md`. **Still open, not code:** (1) set the two `TAURI_SIGNING_PRIVATE_KEY`/
  `_PASSWORD` GitHub secrets yourself (`gh secret set`, from your own machine — the public key is already
  embedded in `tauri.conf.json`); (2) run the recommended throwaway `v0.3.0-rc1`→`rc2` rehearsal cycle (a real
  signed release, a scratch library — never your real 209-paper one) to prove the full check→download→ready→
  install→relaunch loop end to end before trusting it with real testers.

---

## 4. Longer-horizon future tracks — remaining slices only

*(Full design docs live in `future-tracks/`; most of these tracks are mostly-to-fully shipped — only the
genuinely-open remainder is listed here. Each still needs its own design + your graduation call, and must pass
the Principles + A-A gates before build.)*

- **#24 Bayesian auditor — ANOVA/regression BF.** Not a build queue item: **declined as a documented finding**
  (a candidate failed the J=2 → two-sample-t reduction check; no in-env anchor exists). **Rechecked 2026-08-10,
  confirmed still blocked, finding sharpened, not just re-asserted:** pingouin (this project's own dev-only
  verification anchor for the t-test/correlation BFs) still has no ANOVA/regression function — confirmed by
  reading its current `bayesian.py` source directly, not assumed stale. No validated Python port of Rouder et
  al. (2012) exists anywhere findable; the one real implementation of that method (a MATLAB toolbox built
  explicitly from the 2012 paper) requires the *full raw dataset + a model formula*, not summary statistics —
  meaning this isn't just "unverified," it's **structurally unreconstructable** from what a paper reports
  inline (F, df, N), unlike the t-test/correlation cases that already shipped. Revisit only if a trusted
  anchor (R BayesFactor / a validated Rouder-2012 quadrature) turns up **and** a way exists to extract
  sufficient design/cell-size info from papers — a second, separate gap this recheck surfaced.
- **#33/#34 Citation & bibliography engine + plugins — the LibreOffice adapter's next phase.** The full P0/P1/P2
  build-out (incs 106-464) is shipped (`INCREMENT-BACKLOG-DONE.md`). **Word and Google Docs parity also
  already shipped their own SP1-3 arcs (incs 164-166, 169-171) — corrected 2026-08-18, see `.claude/CLAUDE.md`'s
  "Cross-editor adapters" paragraph; this entry previously and incorrectly said this work "hadn't started."**
  **Still genuinely open:**
  - Traveling-library portability (named a P1 future track, never scheduled).
  - **#43** a true Google Workspace Marketplace one-click install (its own project — GCP project, OAuth
    verification, a public privacy policy, Google app review; likely overkill for a local-first single-user
    tool — build only if it becomes worth the ongoing maintenance cost).
  - **Word/Docs P1 parity, in progress (scoping resumed 2026-08-18).** Both adapters store an `items` array
    per citation cluster but only ever populate one (grouped citations/locators not yet wired up — the exact
    LibreOffice-roadmap-doc gap, now confirmed present on both cross-editor adapters too); neither has
    section-scoped bibliographies yet. Google Docs Refresh renumbers in insertion order, not true document
    order (Word's own Refresh already scans true document order, confirmed — this is Docs-specific).
  - **Word-on-the-web shipped inc 482 (SP4)** — the same task pane now runs through the existing cloudflared
    relay Google Docs already uses (a real `AccessControlMiddleware` exemption-list bug was found and fixed
    in the same increment; see `INCREMENT-482-NOTES.md` + `security-audits/2026-08-18_word-online-relay.md`).
    **Both desktop AND Word-on-the-web live-verified 2026-08-28 (inc 508)** — search-insert, Suggest,
    Refresh/bibliography, and Flatten all confirmed working in real Word (desktop) and real Word on the web
    (via the tunnel) for the first time; found + fixed three real bugs along the way (a `tools/run_https.py`
    `sys.path` bug, a wrong Trust-Center sideload instruction in the README, and a `taskpane.js` styles-dropdown
    race where `loadStyles()` ran before the tunneled user had saved their access token and never retried — see
    `INCREMENT-508-NOTES.md`).
  - **Word/Docs parity toward LibreOffice — phased roadmap (scoped 2026-08-28).** LibreOffice's adapter shipped
    every P0/P1/P2 item in `.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md`
    (the shared, generically-written "word processor plugins" roadmap doc — the right reference for Word's own
    build-out too, not LibreOffice-specific). Word/Docs only has the thin SP1-4 slice (search-insert, suggest,
    refresh/renumber, style switch, flatten, web relay). Sequencing for the remaining gap, confirmed against
    real Office.js API capabilities (WordApi 1.3-1.5: `Range.parentContentControlOrNullObject`,
    `Range.insertBookmark`/`.hyperlink`, `Word.Footnote`/`Endnote`, `Word.Field.code`) — **Office.js has no
    UNO-`enterUndoContext`/`leaveUndoContext` equivalent**, so any "verified one-step Undo/Redo" LibreOffice
    promises can only be approximated (build-before-mutate + explicit manual revert-on-failure), never
    guaranteed as one native Ctrl+Z entry — flag this honestly wherever it matters, don't silently promise
    LibreOffice-level safety:
    - **P0 items 1-5 (grouped citations, locators/prefix/suffix, edit/delete) shipped inc 509** — a real
      composer mirroring `adapters/libreoffice/composer.py`'s assembly model; the shared backend
      (`render_document`/`citeproc_runner.js`) needed zero changes, it already supported this. See
      `INCREMENT-509-NOTES.md`.
    - **P0 remainder — Document diagnostics shipped inc 512.** A read-only "Document diagnostics…" command
      (malformed/unresolvable citations, orphaned or retraction-flagged cited works, bibliography health),
      walking `context.document.contentControls` instead of UNO ReferenceMarks; "unsupported schema version"/
      "duplicate mark identity" have no Word equivalent (disclosed, not silently dropped). Fixed a real bug
      found while scoping it: Word's composer trusted the stored `csl_json.id` instead of stamping a reliable
      `"callosum-<paperId>"` id the way LibreOffice's `_build_records` already does — see
      `INCREMENT-512-NOTES.md`. **Inc 513 fixed a second real bug found live**: orphan detection wasn't
      trash-aware (sourced from `check-selected`'s `not_found`, whose internal lookup has no `deleted_at`
      filter) — now uses a trash-aware per-id `/papers/export` existence check instead — see
      `INCREMENT-513-NOTES.md`. **Still not started:** a bibliography-bounds safety review (Word's content-
      control-bounded bibliography may already be safer than the roadmap's LibreOffice-bookmark critique —
      verify, don't assume); safer Flatten (count summary, optional link-retention).
    - **P1 (not started):** note-style (footnote/endnote) citation placement (needs Word's own `noteIndex`
      computation from scratch — no existing infra, unlike LibreOffice's `_note_containers`); a persistent
      "Citations in this document" panel; bibliography categories/chapter-section blocks; accessibility pass
      (likely cheaper than LibreOffice's, since the task pane is plain HTML/CSS, not native AWT dialogs). A
      dedicated style-browser UI is low-value — Word's style dropdown already reflects anything installed via
      Settings' shared catalog.
    - **P2/leapfrog (not started):** evidence-aware Suggest-Citation details (stance breakdown, weak-evidence
      warning, Open in PDF — mirrors inc 460); citation-coverage/integrity-preflight audits
      (`POST /methods/retraction/check-selected` is already adapter-agnostic, zero backend work — mirrors inc
      459/463); Citavi-style Insert Evidence (mirrors inc 461, reuses `POST /citations/classify-stance`
      unchanged); open-science statement insertion (mirrors inc 462, `/statements/pending` is already fully
      generalized, zero backend work — Word needs its own small canned-phrase table, the web frontend's
      `38b_statements.jsx` has the reference list); Zotero-field conversion (Zotero's Word integration is
      documented as using real Word field codes, `ADDIN ZOTERO_ITEM CSL_CITATION {json}` — same convention
      inc 464 already verified for LibreOffice, `Word.Field.code` since WordApi 1.5 — a promising,
      research-first-required follow-up mirroring inc 464's own discipline, not to be guessed at). Mendeley
      Cite / EndNote CWY field conversion stay declined for Word for the identical reason already documented
      for LibreOffice (no complete vendor payload contract) — see
      `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.
  - AppSource / broader public distribution readiness (design with it in mind; do not build the actual
    submission/review process until there's a real reason to).
- **#35 My Publications — Layer 4.** Deterministic Layer 4 is complete (`INCREMENT-BACKLOG-DONE.md`). **Still
  open:** optional LLM narration over the already-grounded data remains deferred — no need to build it unless
  narration becomes useful.
- **#36 Meta-analysis — the assisted-extraction funnel's next escalations.** The consumer-side reporting
  auditor, effect-size converter, extraction workspace, batch drafting, and retrieval narrowing are all shipped
  (`INCREMENT-BACKLOG-DONE.md`). **Far future, its own workspace:** screening/PRISMA, double-coding/IRR
  (human-only — the track's no-independent-coder veto holds), RoB instruments, figure extraction (point at
  WebPlotDigitizer, don't build it).
- **#37 Equity & integrity signals — remaining, narrowed 2026-08-17.** The overlooked-work lens, positive
  self-correction, the real field self-citation baseline (= #25), and analytic-flexibility surfacing are shipped
  (`INCREMENT-BACKLOG-DONE.md`). Of the two forensic candidates it also named, stylometric inconsistency is
  declined (§6). **Still open, blocked on external data, not a design question:** an evidence-grade
  replication badge and a null-engagement badge — neither Crossref's relation vocabulary nor PubMed's publication
  types encode either fact today; an LLM-inferred version would only ever be candidate-class, which can't back
  the deterministic badge the design promised. Revisit only if a real metadata source appears (same disposition
  as #24).
- **#38 Research-impact analytics.** [future track — gated] Opt-in, local-first, commons-structured measurement
  of whether Callosum changes how people research. **Project A (local usage analytics) shipped** —
  `INCREMENT-BACKLOG-DONE.md`. **Project B (cross-user impact signal) remains far-future, gated** — needs N>1
  users, an accounts/hosting decision, and the design doc's own research-grade consent flow (Stage 3 on-device
  aggregation + Stage 4 opt-in contribution, neither built). Must still pass Principles + the A-A values layer
  (default-deny, compute-locally/transmit-summaries-only, public field registry, commons reciprocity) at that
  graduation.
- **#40 Publishers tool — deferred signals.** SP1a/SP1b + SciELO/TOP Factor/AJOL/NLM MEDLINE/thumb auditability
  all shipped (`INCREMENT-BACKLOG-DONE.md`). **Still open:** self-archiving/green-route (needs a
  Jisc-registered API key only the maintainer can obtain); Redalyc (TLS hostname mismatch + maintainer-only
  registration, live re-checked)/Latindex (confirmed closed); COPE (Cloudflare-bot-blocked)/OASPA (no structured
  members endpoint) membership; user exclusion/filtering (deliberately deferred — the design doc flags it as
  ethically fraught, "the disfavored extreme — it reintroduces the 'these are bad' valence").
- **#41 User-authored modules (plugins) — a real design doc now exists (scoping pass 2026-08-19).**
  The admin-gated `plugins_enabled` foundation toggle shipped (inc 483, `INCREMENT-483-NOTES.md`) —
  deliberately inert, controls nothing yet. See
  `.claude/docs/specs/2026-08-19-admin-gated-plugins-design.md` for the full scoping: a curated
  plugin "store" (not an open marketplace), a panel-modules-vs-source-providers decomposition
  (**source providers are explicitly sequenced AFTER panel modules**, not started), and a concrete
  direction for the principle-enforcement crux (constrain a module to typed fact/candidate output,
  let callosum's own already-trusted components do the rendering). **Still fully open, not
  started:** the plugin data model, a loader, sandboxing (browser-side for panel modules; the
  egress-centric trust problem is unresolved for source providers), and the review/store pipeline.
  The stale future-track file (`future-tracks/opus4.8_future-tracks_plugins.md`) now points at the
  design doc as the live reference; the two real existing internal registries
  (`registerPaneTab`/`build_default_feed_registry`) carry marker comments naming them as candidate
  extension points, deferred pending the design doc's open questions.
- **#57 Whole-library migration (Zotero/Mendeley/EndNote).** A user's *entire* existing
  reference-manager library moving into callosum, distinct from the #33/#34 "Traveling-library
  portability" line above (that one is about a single document's own in-document citations, not a
  whole library).
  - **Phase 1 shipped, inc 484:** the already-built native Zotero importer
    (`app/backend/importers/zotero.py`) — `POST /library/zotero/import`, a Library "+ Add" entry,
    and an onboarding-wizard option.
  - **Phase 2 partial, inc 486:** EndNote's documented RefMan (RIS) transfer path is covered by the
    existing generic importer; current Clarivate RIS aliases are parser-tested and Help gives the
    shortest export/import route. **Still open:** verify end to end against a real EndNote-created
    export—the checked-in contract fixture is explicitly only a synthetic stand-in.
  - **Phase 3 feasibility spike complete, inc 487:** Zotero's documented **Mendeley Reference
    Manager (online import)** is the practical fuller-library bridge; Callosum guides the user to
    run it once, then uses the shipped native Zotero importer. Online-sync/auth, personal-library,
    custom-field, and Mendeley Cite document boundaries are explicit; no protected-store reader.
  - **Phase 4 shipped, inc 485:** Zotero PDF highlight/underline positions are bounded, validated,
    and mapped into callosum's own PDF-space bbox/page coordinates for their owning attachment;
    ambiguous/unsupported geometry retains raw provenance and is not drawn. Inc 489 hardening pins an already-
    exact row to its proven attachment across a later Zotero relink and covers sibling PDFs/rotated pages.
  - **Phase 5 research gate complete, inc 488; implementation remains open/gated:** first-party sources confirm
    Mendeley Cite content controls and EndNote `ADDIN EN.CITE` Word fields/Traveling Library, but do not publish
    either complete, versioned payload contract. No converter was built from conflicting third-party reverse
    engineering. Reopen only with a vendor schema/supported API or an explicitly approved, multi-version fixture
    corpus plus fail-closed preservation safeguards.

---

## 5. Open proposals (undecided, not gated on anything — just not prioritized)

*(none currently — the scratch/ephemeral axis proposal was resolved 2026-08-09; see §6.)*

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
- **A scratch / ephemeral axis** — declined 2026-08-09 (confirmed with Cliff, first item of the post-P2 backlog
  sequence): the doc that proposed it already flagged doubt ("may already be covered"), and checking against the
  current codebase confirmed it — axis deletion is already 1 click + 1 confirm (`15_axes.jsx`'s `remove()`,
  `window.confirm`), and full-text search (A3, FTS5, `fulltext_repo.py`) already covers "quick lookup without
  committing to an axis." The one thing genuinely uncovered — auto-expiry, so a throwaway axis vanishes without
  the user remembering to delete it — was declined on its own terms: silently discarding user data has no
  precedent anywhere else in this codebase (papers go to Trash, never straight deletion, for exactly this
  reason), so auto-expiry would cut against an established value rather than fill a real gap.
- **Duplicate-publication / salami-slicing detection** (backlog #54's cross-paper branch) — declined 2026-08-09
  after research, not guessed: the research-integrity literature is explicit that there is **no algorithmic
  detection method** for redundant/overlapping publication across separate papers — it requires expert peer
  judgment about whether findings should have been one paper, not something a deterministic check can answer.
  Any automated attempt would mean guessing at an author's intent with no reliable evidence chain — the
  APPROACH-AVOIDANCE no-accusation boundary, not a data-consistency question. The narrower, genuinely
  buildable half of #54 — `scrutiny`'s actual within-paper repeated-value counting functions, which the
  design doc's "duplication analysis" mention actually pointed at — shipped as inc 469's honestly-framed
  repeated-values checker instead; see `INCREMENT-BACKLOG-DONE.md`.
- **Stylometric inconsistency** (backlog #37's forensic candidate #5,
  `future-tracks/opus4.8_future-tracks_equityintegritysignals.md`) — declined 2026-08-10, confirmed with Cliff.
  The source doc itself flagged this as an open question for the user ("the noisiest and most
  accusation-adjacent item in the entire residual — it points at *people*, not statistics... there is a real
  case that recording it at all risks a later blunt implementation"); even the doc's own hard-gated "neutral
  span-pointing signal, never an authorship claim" version keeps the accusation-adjacent shape front and
  center. Same disposition as the declined salami-slicing branch of #54 — the A-A no-accusation veto, not a
  data-consistency question.
