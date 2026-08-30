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
      `INCREMENT-513-NOTES.md`. **P0 fully closed, inc 515**: the bibliography-bounds safety review confirmed
      Word's Content-Control-bounded bibliography is structurally safe already (no code change needed — Word
      gets the safety property LibreOffice needed incs 374-384 to earn, for free from its data model); Flatten
      now shows a pre-confirm citation/bibliography count, an honest "Callosum can't save a copy for you"
      reminder (Office.js has no `saveAs`, confirmed), an opt-in style-setting cleanup, and a post-operation
      integrity re-scan — see `INCREMENT-515-NOTES.md`.
    - **P1 — "Citations in this document" panel shipped inc 516.** Every unique cited work, occurrence count,
      orphan/retraction badges (reusing the shared `checkPaperExistence()` helper factored out of Document
      diagnostics in the same increment), click-to-navigate, client-side search. Scoped narrower than the
      roadmap's wishlist: "metadata conflicts" and "most recent citation" skipped (disclosed, not silently
      dropped — see `INCREMENT-516-NOTES.md`). **Accessibility pass shipped inc 517** — icon-button
       `aria-label`s, Enter-to-add-top-result in search, Escape-to-cancel an in-progress assembly; tab order/
       keyboard reachability were already correct (confirmed by direct read, plain HTML with no `tabindex`
       overrides) — see `INCREMENT-517-NOTES.md`.
      **Inc 519 closes the storage prerequisite the 2026-08-18 design decision approved but inc 509 did not
      carry through:** new Word citations keep CSL-JSON in a versioned document Custom XML Part and put only its
      opaque ID in the Content Control tag. Legacy base64 tags migrate on Refresh/Edit; duplicate references are
      de-aliased; delete/Flatten clean their parts; missing/malformed parts fail closed. This prevents grouped
      citations from making `.tag` grow with full scholarly metadata before native note placement deepens the
      format. Pure logic is Node-tested; the Office.js lifecycle is explicitly not yet live-verified. See
      `INCREMENT-519-NOTES.md`.
      **Inc 520 ships native note-style placement:** the style catalog's existing `citation_format=note` reveals
      a per-document Footnotes/Endnotes preference; Insert creates a native Word note or adds to an existing
      matching note; Refresh scans all native note bodies and passes Word's real one-based position as
      `noteIndex` (ordinary notes leave gaps; multiple clusters in one note share an index). Mixed inline/note,
      footnote/endnote, or preference/existing-type placement fails closed and diagnostics explains it. The same
      all-story scan now covers panel navigation, Delete, and Flatten. Pure rules are tested; Office.js note
      lifecycle is explicitly not yet live-verified. See `INCREMENT-520-NOTES.md`.
      **Inc 521 starts bibliography item #11 with safe document-local categories:** each resolvable cited work in
      the existing document panel can receive one bounded label; the managed bibliography groups named categories
      alphabetically, preserves citeproc order within them, and leaves unassigned/mixed entries under **Other
      references**. Storage is bounded and fail-closed on missing entry identity; failed refresh restores the
      prior setting. Pure logic is tested; Office.js settings/UI/layout are not yet live-verified. **Inc 522 adds
      bounded batch assignment:** explicit checkboxes, Select visible/Clear, mixed-selection safety, one atomic map
      update, and one Refresh/rollback for the whole selection. Pure logic is tested; live Word interaction remains
      deferred. **Inc 523 adds explicit category precedence:** active named groups can move up/down in a staged
      editor, reset removes the setting, current unranked groups fall back alphabetically, Other remains last, and
      Save performs one Refresh with exact-property rollback. Pure logic is tested; live Word interaction remains
      deferred. **Inc 524 adds heading-scoped bibliography blocks:** strict hidden-heading/generated-block Content
      Control pairs share a random bounded identity; semantic membership is the nearest heading subtree; the full
      citeproc result is projected without changing prompts/rendering; multiple/full blocks coexist; Refresh,
      diagnostics, removal, categories, and Flatten understand the pair. It requires WordApi 1.6 and deliberately
      refuses note styles until native note anchors can be mapped to headings without guessing. Pure logic is
      tested; live Word interaction remains deferred. See `INCREMENT-521-NOTES.md` through
      `INCREMENT-524-NOTES.md`. **Inc 525 adds opt-in bibliography title/DOI links:** the backend's existing
      validated per-entry spans now survive category/order and section projection, with Unicode code-point
      conversion and exact paragraph-local single-match checks before WordApi 1.3 applies any hyperlink. One
      bounded document setting governs full and section blocks; disable restores the same plain generated text
      without touching ordinary manuscript links. Unsafe, malformed, misaligned, overlapping, or ambiguous
      metadata remains plain. No backend/citeproc/text change. Pure logic is tested; live Word interaction remains
      deferred. See `INCREMENT-525-NOTES.md`.
      **HANDED OFF TO CODEX 2026-08-28** (Cliff's Claude usage maxed out ~48h) — see
      `.claude/docs/2026-08-28_codex-word-parity-handoff.md` for the exact remaining scope, verification
      requirements, and known traps. A dedicated style-browser UI is
      low-value — Word's style dropdown already reflects anything
      installed via Settings' shared catalog.
    - **P2/leapfrog (started inc 526):** **evidence-aware Suggest-Citation details closed inc 526** — the full
      matched passage, complete support/mention/contrast signal, plain-language retrieval reason, shared-threshold
      weak-evidence warning, editable auto page locator, and region-precision **Open in PDF** now sit behind each
      Word suggestion's **Details…** action. An inserted suggestion adds one bounded evidence snippet/page/chunk
      record to the existing Custom XML payload; Edit preserves it and the document panel exposes **View
      evidence…**. The response, models, prompt, ranking, user-choice boundary, and fully local/no-egress posture
      are unchanged. Pure/static logic is tested; live Word interaction remains deferred. See
      `INCREMENT-526-NOTES.md`. **Open-science statement insertion closed inc 527:** Word now mirrors the seven
      existing author-asserted disclosure kinds and canned starting phrases, reads/stages/clears through unchanged
      `/statements/pending`, and inserts the exact bounded author-reviewed draft as ordinary text at the cursor.
      No Content Control, AI/provider call, inferred fact, backend contract, or document mutation occurs during
      staging. Pure/static logic is tested; live Word interaction remains deferred. See `INCREMENT-527-NOTES.md`.
      **Citation coverage closed inc 528:** Word now performs the same local structural scan for 3+ consecutive
      substantive paragraphs without a Callosum citation anchor, counting inline and native-note anchors at the
      main-text paragraph while excluding headings, short transitions, tables, and managed bibliography blocks.
      This is explicitly a neutral review prompt, not a support/citation verdict. The originally grouped
      "integrity-preflight" half required no new control: **Document diagnostics…** already performs the fresh,
      trash-aware existence + `POST /methods/retraction/check-selected` retraction check (incs 512-513), so inc
      528 did not duplicate it. See `INCREMENT-528-NOTES.md`. **Zotero field conversion closed inc 530:** after
      verifying Zotero's current first-party Word integration source and WordApi 1.5 field contracts, Word now
      scans exact `ADDIN ZOTERO_ITEM CSL_CITATION {json}` fields, previews and snapshot-checks a bounded conversion,
      resolves embedded records through the unchanged local inc-464 endpoint, preserves grouped per-item overrides,
      and replaces only verified inline fields through the existing Custom-XML/Refresh lifecycle. Note-style,
      Bookmark-mode, malformed, oversized, and ambiguous material remains untouched; bibliography replacement is
      conditional. Office.js mutation remains awaiting the consolidated live Word check. Mendeley
      Cite / EndNote CWY field conversion stay declined for Word for the identical reason already documented
      for LibreOffice (no complete vendor payload contract) — see
      `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`.
  - AppSource / broader public distribution readiness (design with it in mind; do not build the actual
    submission/review process until there's a real reason to).
  - **LibreOffice/Word/Docs support in the packaged desktop (Tauri) app — completed 2026-08-29 (a
    separate Claude-driven track, NOT part of the Codex Word/Docs-parity handoff above — different files, no
    overlap: `app/desktop-shell/*`, `app/backend/api/routers/libreoffice.py`, Settings UI, confirmed via `git
    diff` against Codex's own commits before starting).** Full plan:
    `.claude/backups/plans/2026-08-29_tauri-word-libreoffice-googledocs-support.md`. **Phase 1 shipped inc 531**:
    the packaged app now prefers its last-successful port across ordinary restarts (`backend.rs`'s
    `read_preferred_port`/`pick_port`, falling back to a fresh random pick on conflict — same access-control
    boundary as before, CORS/`AccessControlMiddleware`, not port obscurity); Settings shows the live server
    address with a Copy button; and a one-click "Point LibreOffice at This Instance" button
    (`POST /integrations/libreoffice/set-server-url`, loopback-only, rejects a Remote-Access-tunnel Host) writes
    the adapter's own `~/.callosum/libreoffice.json` sidecar directly — closing the LibreOffice-in-the-packaged-
    app gap completely. **Phase 2 shipped inc 532:** an explicit packaged-Settings action creates a localhost-
    only end-entity certificate, restricts its private key, installs/verifies per-user OS trust, and enables a
    Tauri-supervised fixed `127.0.0.1:8443` HTTPS Uvicorn companion against the same DB/library/version as the
    main app. Trust mutations are loopback + Settings-header gated; the companion gets Remote access disabled
    only in its own environment; disable removes trust/material; browser/source workflows retain the separate
    dev-certificate launcher. Windows uses PowerShell `Import-Certificate` (not `certutil`); macOS targets the
    login keychain but awaits live hardware QA. See `INCREMENT-532-NOTES.md` and
    `.claude/security-audits/2026-08-29_tauri-word-https.md`. **Phase 3 shipped inc 533:** packaged Settings can
    explicitly start/stop a Tauri-owned Cloudflare Quick Tunnel and copy its temporary URL. The connector targets
    a separate Uvicorn child whose bearer gate fails closed whenever Remote access is off, so cloudflared's
    loopback forwarding can never inherit the ordinary local-trust path. Tauri isolates cloudflared from any
    existing user config, waits for strict URL issuance, owns both process trees, and removes both on stop/exit.
    Quick Tunnel's bearer-only/no-ingress-allowlist tradeoff remains visible; source and named-tunnel workflows
    remain available. See `INCREMENT-533-NOTES.md` and
    `.claude/security-audits/2026-08-29_tauri-quick-tunnel.md`.
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
    corpus plus fail-closed preservation safeguards. **Re-verified 2026-08-29 (fresh research, not re-guessed):
    still correctly gated** — no vendor schema, no open-source reference implementation, and no reverse-
    engineering write-up exists for Mendeley Cite's Word content-control payload; a well-resourced competitor
    (Paperpile) independently confirms the same gap as of Feb 2025. **This is NOT the same thing as Phase 2/3
    below being good enough** — see Phase 6.
  - **Phase 6 (started 2026-08-29): real Mendeley + EndNote whole-library import (metadata + PDFs + folders),
    handed to Codex.** Phase 2 (EndNote RIS) and Phase 3 (Mendeley-via-Zotero) turned out to have real gaps a
    live user hit: RIS import is metadata-only (no PDFs, no folders — confirmed by reading
    `app/backend/metadata/citation_import.py` directly), and the Zotero bridge requires installing an entire
    separate application just to leave Mendeley. Research doc:
    `.claude/docs/research/2026-08-29_mendeley_endnote_native_import.md`. Handoff:
    `.claude/docs/2026-08-29_codex-mendeley-endnote-import-handoff.md`. Summary: Mendeley gets a real OAuth2
    importer against the official `dev.mendeley.com` REST API (no Zotero needed — **blocked on the maintainer
    registering an OAuth app there first**); EndNote gets a `.enlx` Compressed Library importer (metadata + PDFs
    + groups in one file). **Increment 535 resolved the reader-strategy question empirically:** no maintained
    pure-language row reader was found, while a disposable MariaDB 10.11 engine successfully upgraded and read
    EndNote's public X7 MyISAM `refs` table from a copy. **Increment 541 resolved the managed-engine design:**
    Windows and Debian live tests proved that one-shot `mariadbd --bootstrap` can rebuild/read a private copy,
    write bounded `--secure-file-priv` output, and exit under `--skip-networking`, eliminating a persistent
    service/listener/account. A pruned experimental Windows runtime was 29 files/20.24 MB. The next approved seam
    was completed in **increment 542**: a developer-only executor now performs bounded archive preflight,
    digest-verified copy-only extraction, deterministic allowlisted runtime identity, fixed SQL/direct argv,
    bounded output/timeout cleanup, and path-free aggregate receipts. A fresh official-Windows live run returned
    the public fixture's 59 rows/54 columns and left no process. **Increment 544 closes the launcher-only Linux
    identity gap:** a deterministic 28-file launcher/message/charset bundle extracted from the pinned official
    image ran directly on Debian 12 outside Docker, reproduced the same schema receipt, resolved all 18 OS-owned
    dependencies, and remained identity-stable after relocation. It is not imported by production. Shipping
    **Increment 545 completes the engineering license/provenance review:** MariaDB is GPL-2.0-only and remains a
    separate optional process; official Linux binary/source hashes and signatures plus a deterministic 31.8 MB
    stripped candidate are proven. Distribution is still blocked on qualified legal approval of the aggregate
    boundary and implementation of the specified source/notices/signatures/transformation kit. **Increment 546
    closes the runtime-specific Linux ABI/package-policy gate:** the exact candidate passed seven Ubuntu/Debian
    releases as root and uid 1000; support is conservatively limited to Ubuntu 22.04/24.04/26.04 and Debian 12/13
    inside Callosum's amd64 `.deb`, with five declared OS libraries and no vendored system copies. Shipping remains
    gated on an actual packaged-app install matrix after legal approval, macOS build/sign/notarization, a real
    attached-PDF fixture, and a separate modern SQLite-era fixture; Docker is not an end-user prerequisite.
    Fixtures remain gitignored at `.claude/backups/endnote-fixtures/`. **Increment 537 added the safe, dormant
    Mendeley transport scaffold:**
    version-pinned/bounded documents, folders, memberships, files, signed-download redirect, and OAuth exchange
    primitives with hermetic tests. It also found the official authorization-code flow still requires a
    confidential secret, documents no PKCE, and pins one redirect URI—a real packaged-desktop blocker beyond
    merely obtaining credentials. No callback/token persistence/UI is published until registration capabilities
    and safe secret/redirect ownership are proven live. **Increment 538 added the dormant snapshot import core:**
    complete synthetic v1 document/folder/membership snapshots validate before writes, map through the existing
    CSL paper contract, deduplicate via canonical identity plus stable `mendeley-document` provenance, and
    atomically populate the existing imported-collection hierarchy. Identity disagreement, orphan/cyclic folders,
    and unknown memberships fail closed. No route, token use, live request, PDF handling, or UI exists; the newly
    supplied gitignored secret does not by itself solve client-ID/redirect/desktop-confidentiality. **The shared
    imported-folder/group → axis seam shipped in
    increment 536:**
    Zotero now preserves `parentCollectionID`, previews top-level folders in its existing import dialog, and only
    on explicit action snapshots descendant-inclusive membership into idempotent ordinary axes. Curated is the
    default; the unchecked keyword option keeps exact folder papers as manual anchors and reuses local scoring.
    The generic provenance/API seam already accepts future `mendeley` and `endnote` collection rows. See
    §6 below — this does **not** contradict the "folders/collections declined" entry; that decision was about
    manual folder-creation inside callosum, not imported structure from another tool.

---

## 5. Open proposals (undecided, not gated on anything — just not prioritized)

*(none currently — the scratch/ephemeral axis proposal was resolved 2026-08-09; see §6.)*

---

## 6. Declined / will-not-build (recorded so it's not re-proposed)

- **Folders/collections hierarchy** — superseded by axes (a coherent set → axis; an arbitrary flat set → tag;
  "read this week" → the needs-review filter; the Curated Axis is the manual-container path). **Scope note
  (2026-08-29):** this was a decision about *manual* folder-creation inside callosum's own UI — it does not
  apply to *imported* folder/collection structure arriving from another tool (Zotero/EndNote/Mendeley), which
  is a different question with its own scoped feature under #57 Phase 6 (map imported structure onto axes).
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
