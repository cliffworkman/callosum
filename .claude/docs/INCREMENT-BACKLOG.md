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
- **#59 Title-Case retrospective.** DESIGN.md now has a rule that button/toggle/dropdown labels use Title Case
  (2026-08-27, prompted by "Auto-Refresh"/"Mark All Read" in Feed) — that same fix was only applied to the
  controls concretely touched in that change. A full app-wide pass is still needed: audit every button, toggle,
  and dropdown label for Title Case compliance and fix stragglers.
- **#60 Control-height retrospective.** DESIGN.md now has a canonical `--control-h` token (2026-08-27, prompted
  by visibly mismatched heights across the input/select/buttons in Feed's and Search's own `.searchbar` rows) —
  applied there only (the shared `.searchbar` container, covering Feed/Search/Library-header/WIP-filters). A
  full app-wide pass is still needed: audit every other button/input/select for height consistency and apply
  `--control-h` (or a documented, deliberate exception) wherever it's missing.
- **#61 `OpenAlexAuthorClient` caches a failed fetch as a permanent "no result."** Found live (2026-08-27) while
  verifying Feed's Author-follow flow: a transient `httpx`/Brotli decompression error on one real OpenAlex
  response got written to `external_api_cache` with `status_code=NULL`, and `_fetch()`'s cache-read branch
  (`integrations/openalex/author.py`) treats ANY cached row — success or error — as authoritative, so that
  author's name/ORCID can never resolve again without a manual cache-row delete. Needs a fix that only caches
  genuine 2xx responses (or a bounded TTL/retry on error rows), not a workaround at the call site. Separately
  noticed but unconfirmed: `_fetch_by_orcid`'s URL literally uses backslashes
  (`f"{OPENALEX_ROOT}\authors\orcid:{orcid.strip()}"`) instead of forward slashes — worth checking whether this
  is a live bug or an escaping/display artifact when this item is picked up.

---

## 2. Needs a design decision from Cliff (not destructive/security — just your call)

- **#58 Bundle GROBID with callosum, not just self-hosted opt-in.** GROBID (`integrations/grobid/`,
  inc 479) currently ships as a **deliberately never-bundled**, separately-run, opt-in Docker
  service the user points callosum at from Settings — see CLAUDE.md's Section-scoped
  Suggest-Citation + GROBID paragraph. **Real evidence this may need to change (2026-08-25,
  found live by Cliff):** without GROBID, synthesis retrieval that isn't scoped to a specific
  section (e.g. run against "all sections" rather than "Discussion") pulls in repeated per-page
  running-header/footer text — the paper's own short-title line that PDF layout repeats on every
  page — as if it were real body content. For a synthesis asking "what is the anomalous-is-bad
  bias?" run unscoped, every retrieved evidence chunk was a near-duplicate fragment of the header
  line itself ("Workman et al. The 'anomalous-is-bad' stereotype"), verified/cited as if
  substantive, while the identical query scoped to Discussion returned clean, real evidence. The
  heuristic (non-GROBID) section/chunk pipeline's own tagging doesn't reliably exclude running
  headers from retrieval once no section filter narrows the search; GROBID's real section-
  boundary bboxes (mapped onto callosum's own PyMuPDF chunk coordinates by content overlap, not
  fuzzy text matching) may resolve this since it identifies structural document regions instead
  of guessing per-block. **Status: Cliff is re-running GROBID parsing across the full library now
  to confirm whether this actually fixes the header-pollution problem — not yet confirmed, don't
  treat as settled.** **If confirmed, this reframes GROBID from "optional accuracy boost" to "the
  fix for a real retrieval-quality bug"** — which pressures the original "never bundled" choice,
  since asking every user to separately run Docker + configure a URL to get *correct* (not merely
  improved) retrieval is a much higher bar than asking for an optional quality upgrade. **Design
  tradeoffs to weigh, not yet resolved:** GROBID is a JVM service with GB-scale CRF/embedding
  model files (unlike the already-bundled portable CPython the desktop shell ships today) — a
  full bundle would meaningfully grow the Windows/macOS/Linux installer size; alternatives include
  a download-on-first-use runtime (fetched and cached locally rather than baked into the
  installer) or keeping it external but making setup the strongly-recommended default path (a
  guided one-command flow surfaced during onboarding) rather than a buried Settings field.
  **The narrower, cheaper fix shipped 2026-08-26, independent of the bundling decision:** the
  *heuristic* (non-GROBID) retrieval path now excludes repeated running-header/footer text
  directly — `app/backend/summarization/chunk_filtering.py::exclude_repeated_boilerplate_chunks`
  drops any chunk whose text is short (≤25 words) and recurs verbatim across ≥3 of the *same
  paper's* own pages, wired into `pipeline.py::_source_chunks_for_scope` ahead of both the
  query-ranked and no-query retrieval branches, with a per-paper safety valve (never silences a
  paper down to zero candidate chunks). This is complementary to the existing content-pattern
  `is_front_matter_chunk` (which already catches journal-citation-style running headers via DOI/
  volume/superscript patterns, per its own test fixtures) — a plain title-case running header has
  none of those fingerprints and needed the repetition-based signal instead. Tests:
  `tests/test_chunk_filtering.py`, `tests/test_summaries.py`. **This may fully resolve the original
  reported bug on its own, for every user, regardless of whether GROBID is ever bundled** — the
  live re-test (rerun the original unscoped "anomalous-is-bad bias" synthesis) still needs doing to
  confirm real Discussion-section evidence now surfaces instead of header fragments.
  **Operational snag hit while confirming (2026-08-25/26), also fixed 2026-08-26:** the first
  attempt to bulk-parse the full ~216-paper library failed 100% with GROBID returning HTTP 503 —
  its own log shows `Could not get an engine from the pool within configured time`, i.e. GROBID's
  internal fixed-size processing-engine pool was exhausted by callosum's bulk-parse job sending
  requests faster/more concurrently than GROBID could drain them, not a crash (the container stayed
  up, CPU-pegged, actively working). Fixed with two changes: `integrations/grobid/client.py::
  parse_fulltext` now retries specifically on 503 (linear backoff, bounded at 3 attempts — every
  other non-200 status still fails immediately as likely-permanent), and the bulk job's
  `GROBID_PARSE_WORKERS` (`app/backend/api/routers/grobid.py`) dropped from 4 to 2 concurrent
  requests. Tests: `tests/test_grobid_client.py`. **A second live retry surfaced a distinct failure**
  (`Error -3 while decompressing data: incorrect header check`, from httpx's own streaming decoder) —
  root-caused as GROBID returning a truncated/corrupted gzip response under the same heavy concurrent
  load; fixed by sending `Accept-Encoding: identity` so GROBID never compresses the response at all
  (a TEI-XML response is already bounded by the existing size cap, so the larger uncompressed
  transfer is an acceptable trade). **Confirmed live:** a subsequent full-library bulk parse
  succeeded. Four follow-on UI requests shipped the same day: GROBID Settings moved directly under
  Library access (was empty whitespace); "Test connection" merged onto the Save row as "Test"; a
  "Parse unparsed only" button alongside "Parse all papers" (`only_unparsed`, backed by
  `paper_ids_with_sections()`); and a per-paper bulk-selection "parse structure (GROBID)" button
  mirroring the existing reprocess-text action. Bulk parsing also now excludes metadata-only papers
  (no local PDF) from the candidate count entirely, since GROBID structurally cannot parse one.
  Tests: `tests/test_grobid_endpoints.py`, `tests/test_grobid_pipeline.py`. **Still open:** if
  bundling GROBID is pursued later, its own concurrency-pool sizing still deserves first-class
  design attention rather than relying on these mitigations alone.

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
    **Not yet live-verified** — the maintainer doesn't have desktop Word installed yet; neither the existing
    desktop SP1-3 flow nor the new SP4 relay flow has ever been exercised in real Word. **Immediate next
    step, not yet done:** once Word is installed, run both — the desktop regression check first, then the
    Word-on-the-web relay setup (`adapters/word/README.md`'s "Word on the web" section) — before deciding the
    next concrete increment (grouped citations/locators is the natural next P1 item once verification lands).
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
