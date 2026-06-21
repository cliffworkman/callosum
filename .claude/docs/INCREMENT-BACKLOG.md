# Increment backlog — nearer-term core-UX increments

Durable, ordered to-do list for upcoming increments (captured 2026-06-19, post-increment 43; revised
after a design discussion). Each item gets its **own plan-mode design** when picked up — several are
deliberately underspecified here; this is the queue, not the design.

> **Guiding principle (the user's framing):** *reference manager first.* The verified-synthesis crown
> jewel only matters if Callosum is a credible day-one replacement for Mendeley/Zotero — otherwise it's a
> costly single-use tool opened *alongside* them, not *instead of* them. "The crown jewel only sells
> tickets if it's in a beautiful museum." So this whole backlog is **high priority** — it's the museum.

> Scope note: the bigger **longer-horizon tracks** now live as detailed build-prompt docs under
> **[`future-tracks/`](future-tracks/)** (see its `README.md` index) — statcheck/open-science signals, the
> Word/LibreOffice citation plugin, highlight-to-suggest/evaluate, free full-text acquisition, the
> THEORY/METHODS panes + findings subsystem, the Literature-discovery Feed/Search tabs, the gap-finder, My
> Publications, and the (deferred) user-authored modules. (The older `backlog-future-tracks.md` capture was
> archived to `.claude/deprecated/` in Phase 6.) **`future-tracks/` is the canonical source — reference it, don't recapitulate.**
> The items below are the near-term core UX.

**Suggested sequence (agreed dependencies):** **A** (axis edit-modal / title-term decoupling) ships
**before suggest-optimal-axes** (which must target the finalized axis model). **G** (metadata + DOI
correction) ships **before E** (dedup) — clean identifiers make dedup tractable. **Library merge is last**
(free-form, deliberately *not* gated behind dedup — see the item). Otherwise reprioritize freely.

_Italic notes are light implementation pointers, not designs._

---

## Tags & keywords (added 2026-06-20, post inc-71/72) — a theme the original backlog + the external future-tracks docs predate

Tagging (**inc 71** manual + **inc 72** local c-TF-IDF suggest) opened a surface that the rest of this backlog
and the `opus4.8_future-tracks_*.md` docs were written *before*. Capture the connections now so they don't
become a blindspot when those tracks land.

- [ ] **Author/expert keywords as FIRST-ORDER tags** (the inc-72 c-TF-IDF suggester is the *second-order*
  gap-filler). Authors/indexers already did the concept work of naming a paper's primary dimensions — privilege
  it; let the suggester propose only what they *missed* (it already excludes existing tags). Sources, roughly by
  value:
  - **Zotero tags** — already imported (inc 71 `_upsert_tags`, `import_source="zotero"`). ✅ surfaced.
  - **Crossref `subject`** — present in the raw Crossref message (cached in `external_api_cache`) but **dropped**
    by `integrations/crossref/adapter.py::_crossref_message_to_csl` today. Coarse (journal-level categories) but
    free — extend the adapter to capture it → import as tags (`import_source="keyword:crossref"`).
  - **OpenAlex `concepts`** + **PubMed MeSH** — richer index keywords; arrive when those integrations land
    (OpenAlex/semantic-scholar are planned adapters; PubMed via the connected MCP). On a Feed/Search **save**
    (librarypaneltab track), attach the source's keywords as tags.
- [ ] **Tag provenance / source** (the cross-cut that makes the above coherent). `tags.import_source` already
  seeds this (`zotero`/`user`); formalize a small vocabulary — `user`, `keyword:{crossref|openalex|pubmed}`,
  `system:{retraction|transparency|…}` — so the UI can group/style by source ("author keywords" vs "your tags"
  vs "system facts"), protect imported/system tags from silent clobber (mirror the inc-49 user-edit guard), and
  offer "show only author keywords." NB a per-**link** provenance may be needed for per-paper facts (a global
  tag's `import_source` can't say "THIS paper is retracted") — those likely belong to the findings subsystem,
  projected as read-only system-tags.
- [ ] **Tags ↔ findings / system-facts (the retraction-surfacing connection the user flagged).**
  `opus4.8_future-tracks_theorymethods.md` describes a **findings subsystem**: a retraction producer (Crossref
  Retraction Watch) emits FACT findings rendered as a persistent **"retracted" mark** (the doc literally calls
  it a tag), and transparency producers emit **descriptive tags** (open-data/open-code/prereg). These should be
  **filterable the way tags are** — "locate every RETRACTED paper across the library" — by reusing the inc-71
  tag-filter (`?tag_id=`/banner) affordance OR a unified facet filter spanning user-tags + system-facts.
  **Build directive when those tracks land:** do NOT reinvent a separate filter/chip surface — extend
  tags/tag-filter; keep system-facts visually distinct + non-editable (a fact isn't a user label). Hooked from
  the future-tracks docs (see their "Tags hook" notes). **→ Worth a short design chat with the user before the
  findings track starts.**

---

## Cross-cutting — `DESIGN.md` design dictionary — ✅ DONE (first pass, 2026-06-19); consolidation worklist remains

- [x] Created **`.claude/DESIGN.md`** (Pass 1 tokens + recipes; Pass 2 inconsistencies + canonical rules)
  and added **`CLAUDE.md` rule #8** (read DESIGN.md before any CSS change) + reference-table + decision rows.
- [ ] **Remaining: apply the Pass-2 consolidation worklist** (DESIGN.md §3) — opportunistically or on
  request: a `--danger` red token (split destructive colors), `--accent-overlay`/`--hover`/`--accent-line`/
  `--flag-line` tokens, canonical `.btn-*` classes, a radius scale. Best folded into the **dark-mode
  theming** increment (same "scattered hex → tokens" work). New CSS already follows the canonical rules.
- **Two-pass population (per the user):**
  - **Pass 1 — document as-is:** agents read `styles.css` (and the inline-styled JSX) and catalogue the
    *actual* design facts per element class — shape, radius, background/text colors (the real hex or the
    `var(--token)` they reference), spacing, typography, states (hover/disabled/active). Descriptive, not
    prescriptive. e.g. "Dropdowns: rounded rect, `--panel` bg, `--ink` text, 1px `--line-2` border…".
  - **Pass 2 — find + reduce heterogeneity:** evaluate the dictionary for things that *should* be uniform
    but aren't (e.g. one kind of form control with several different stylings), and decide — thoughtfully —
    where to consolidate vs. where contextual difference is legitimate. Produce the canonical rules + a
    short list of proposed consolidations (the user will likely iterate after a first pass).
- **My timing recommendation:** do this **before the next CSS-heavy increment** — specifically it should
  **precede / merge with the dark-mode theming work** (backlog H), because Pass 2's "consolidate scattered
  hex into shared tokens" *is* the CSS-variable refactor dark mode needs anyway. The sidebar/logo/filter
  item below is also CSS-heavy and would benefit from DESIGN.md existing first. Net: DESIGN.md is a strong
  candidate for the **very next** increment (it's read-only Pass 1 + a low-risk consolidation Pass 2).
- _Likely a workflow/multi-agent job (parallel readers over the CSS → a synthesized dictionary → a
  consistency critic). No app-behavior change in Pass 1._

---

## Cross-cutting — Auditability standard (gating constraint for AI-assist features) — [ ] open question

- [ ] **Resolve "how auditable is auditable enough?" — explicitly, before any AI-assist authoring/evaluation
  feature ships.** The features that propose citations, judge a user's claim, or critically review papers
  (the future-tracks **Track B/C** + the **multi-paper-summary critical-review supplement** below — items 2–4
  of the 2026-06-20 capture) are stronger, more opinionated AI actions than a grounded summary. The bar for
  how inspectable/verifiable each must be should be **defined deliberately, not assumed**.
- **Reference model:** the existing **local citation-verification layer** (embedding similarity + NLI stance
  + verbatim quote, shown with confidence — invariant #1/#4) is the current standard for what "auditable"
  means. New AI-assist surfaces should be measured against it and either meet it or state, explicitly, where
  and why they fall short — built with awareness that **users skip verification under time pressure**, so the
  verification step must be **low-friction** (see Track C's captured design intent).
- _Not a feature — a gating note attached to items 2–4. Each of those features must answer this before its
  own plan-mode design is approved._

---

## Theme 1 — Axes UX (builds directly on inc 38–43) — do first

### A. Axis **edit modal** + title-vs-term decoupling — ✅ DONE (increment 44)
- [x] Unified **Edit Axis modal** (`14_axes_edit.jsx`) for create/edit/term-search; inline forms + the
  inc-41 terms modal removed; per-axis `.axis-desc` preview removed (terms live only in the modal).
- [x] **Title is now cosmetic; the description (its `Related:` terms, primary first) is the embedded
  query** (`_axis_text` description-only + label fallback; no migration).
- [x] Create flow = quick inline name → prefilled modal (name → title + first selected term).
- [x] Suggested terms **deselected by default**; **selected sort to the top**.
- _See `INCREMENT-44-NOTES.md`. (Tier-tag cleanup — the ASSIGNED tag — is item B, not done here.)_

### A′. **Click an axis-listed article → open its PDF** — ✅ DONE (increment 44)
- [x] An axis paper's click opens its PDF tab via `openPdf` (threaded App → Sidebar → AxesPanel) and
  selects it. Axes panel is now a clickable, AI-powered library overview. _(Future pair: "filter library
  to this axis".)_

### B. Tier tags + **uncertain → assigned** confirmation — ✅ DONE (increment 50)
- [x] **Removed the "ASSIGNED" tag** (`AxisTierBadge` renders nothing for assigned → just the confidence;
  amber = uncertain; dashed = manual). Legibility over a redundant label.
- [x] Kept **×**; added a **✓ confirm** on uncertain rows → a manual override (`confidence IS NULL`) that
  **survives re-score** (the two `axis_scoring.py` upsert fixes).

### C. **"Add articles" library focus-mode** — ✅ DONE (increment 50)
- [x] The axis **＋** opens a **focus mode on the Library panel**: a **reminder card above the search bar**
  names the axis; each library row grows a **+add / ✓ in axis / ✓ staged / − staged** button.
- [x] **Staged → committed on Save** (the user's choice); Cancel discards; already-in-axis rows show a
  member signifier + can be removed. **Replaced** the inc-38 `AddPaperPicker` (now retired).
- _See `INCREMENT-50-NOTES.md`. Built together with B (shared manual-assignment surface)._

### B′. Eyeball toggle to hide/show UNCERTAIN papers — ✅ DONE (increment 51)
- [x] An **👁** at the right of the re-score row (shown only when the axis has ≥1 uncertain paper) toggles
  an **assigned/manual-only** view; a "N uncertain hidden — show" hint restores them. Pure display filter;
  per-axis local state. See `INCREMENT-51-NOTES.md`.

### B″. Sidebar density: connection-in-logo + axis filter + tighter header — ✅ DONE (inc 47 + 48)
- [x] **Connection status via the logo** (inc 47): 4-state CSS `background-image`; green dot in the
  cell-body when connected; `● connected` text line gone.
- [x] **Removed** the "local reference workbench" subtitle + the "local-verifier-v1" text (inc 47/48).
- [x] **Axis filter** (`Filter axes…`, matches title or terms) preceding the sort dropdown (inc 48).
- [x] **"+ new" → green "+"** (`--verified`); `Filter… · sort ▾ · +` on one no-wrap row (inc 48).
- _See `INCREMENT-47-NOTES.md` + `INCREMENT-48-NOTES.md`._

### Suggest-optimal axes — ✅ DONE (increment 52)
- [x] **✨ Suggest** clusters the library (`AgglomerativeAbstractClusterer`, now in use) with a
  **coverage-with-diversity** objective (novelty filter vs existing axes + MMR-lite among suggestions);
  **local c-TF-IDF labels** with optional **egress-gated Gemini polish** (falls back to local; never 503).
  Async `POST /axes/suggest` + `GET /axes/suggest/{job_id}`; the user curates + creates via `POST /axes`.
  New `app/backend/clustering/axis_suggestion.py` + `integrations/gemini/axis_cluster_labeler.py` +
  `17_axes_suggest.jsx`. See `INCREMENT-52-NOTES.md`.

---

## Theme 2 — Library management

### D. Library **multi-select + bulk delete** — ✅ DONE (increment 54)
- [x] Checkbox multi-select + bulk-delete bar (mirrors inc-43) → **soft-delete** (`papers.deleted_at`) with
  a **Trash ⇄ Library** toggle + per-row **Restore** (the "undo/soft-delete (trash)" open proposal,
  delivered here). Soft because hard-delete orphans embeddings/vectors + crashes retrieval.
- [x] Permanent delete / **empty-trash** — ✅ DONE (increment 65). `VectorStore.delete` + `repository.purge_paper`/
  `purge_all_trashed` (trashed-only; delete embeddings + vectors before the paper row → no orphan crash);
  `DELETE /papers/{id}/permanent` + `POST /papers/trash/empty`; frontend **Delete forever** / **Empty Trash**.
  See `INCREMENT-65-NOTES.md`.
- [x] Exclude trashed (soft-deleted, not-yet-purged) papers from new synthesis **retrieval** — ✅ DONE
  (increment 66). The real path was `pipeline._source_chunks_for_scope` (query scope = `select(chunks)` with
  no paper filter), now filtered to live papers; also hardened `retrieval._candidate_embedding_ids`. See
  `INCREMENT-66-NOTES.md`.
- [ ] **Deferred:** permanent delete does not remove the on-disk **PDF file** (managed/linked) — out of scope
  in inc 65 (deleting user files is riskier). See `INCREMENT-65-NOTES.md`.

### E. **Duplicate detection with scoring** — ✅ DONE (increment 56)
- [x] A **"Duplicates"** scan surfaces likely-duplicate groups with a confidence + reason, **layered**
  (shared PMID/arXiv → canonical title+author+year → embedding ≥0.92), merged via **union-find**. Entirely
  local; **flag-only** — the review modal resolves a group by trashing the redundant copy (soft-delete),
  never auto-merges. New `app/backend/clustering/duplicate_detection.py` + `19_duplicates.jsx`. See
  `INCREMENT-56-NOTES.md`.
- [x] Persistent **"not a duplicate"** dismiss — ✅ DONE (increment 64). `dismissed_duplicate_pairs` table
  (migration 0006) + `POST /papers/duplicates/dismiss`; `find_duplicate_groups` drops dismissed pairs before
  the union-find so the group never re-flags. Non-destructive, local. Forced the dedup endpoints out of
  `papers.py` into `routers/duplicates.py` (600-line cap). See `INCREMENT-64-NOTES.md`.
- [x] **Un-dismiss / "manage dismissals"** UI — ✅ DONE (increment 67). The Duplicates modal's **Previously
  dismissed** section lists dismissed pairs + un-dismisses them (`GET /papers/duplicates/dismissed` +
  `POST /papers/duplicates/undismiss`). Dedup-dismiss data access split to `persistence/dedup_repo.py`
  (600-line cap). See `INCREMENT-67-NOTES.md`.
- [ ] **Deferred:** the actual **merge** (see "Deferred — library merge"). (Un-dismiss is per-pair; whole-group
  dismiss is retained for dismissing a whole flagged group at once.)

### Import coverage — additional sources (the "reference manager first" frontier) — [ ] open
*(Captured 2026-06-20 reconciling the `integrations/mendeley/` README, which is correctly **not** tied to any
future track — it's import coverage, not track infra.)*
- [ ] **Beyond Zotero import.** Today only Zotero imports (`importers/zotero.py`). Reference-manager-first
  parity means accepting libraries that originate elsewhere, mapped to the same `csl_json` canonical record:
  - **Mendeley** — a constrained import path via Zotero's Mendeley bridge or exported BibTeX/RIS/CSL-JSON
    (**not** direct encrypted-local-DB reads). Surfaces the `integrations/mendeley/` stub.
  - **BibTeX / RIS / CSL-JSON import** — the complement to the inc-70 citation *export*; reuse the CSL-JSON
    model so any reference manager's export can seed the library.
- _Validate untrusted import files at the boundary (rule #4); audit-gate the new ingestion path._

---

## Theme 3 — Synthesis & Details pane

### F. Always-on Synthesis + **contextual Details pane** — ✅ DONE (increment 57)
- [x] The right pane is a **vertical split** (no tabs): **Synthesis always on top**; the editable **Details**
  appear in a lower section **only when a paper is selected**, with a **draggable divider** (height persisted)
  reusing the inc-42 resizer. See `INCREMENT-57-NOTES.md`.

### G. **Editable Details pane** + DOI correction & re-search — ✅ DONE (increment 49)
- [x] Mendeley-style **always-editable** Details pane (`app/frontend/js/25_detail.jsx`): inline fields,
  "Add …" placeholders, **auto-save on blur**, Literature Type dropdown, collapsible Identifiers, a "More"
  section that auto-surfaces extra DOI-populated fields, a Files list, honest provenance footer.
- [x] `PATCH /papers/{id}` (`build_paper_update` — safe partial csl_json merge; **no migration**; DOI clash
  → 409) marks `imported_source="user-edited"` (kept out of the batch-enrich allowlist → no silent clobber).
- [x] **DOI field + 🔎 `POST /papers/{id}/re-resolve`** (force past the user-edited guard; only the DOI
  leaves; Crossref miss → graceful). Audit: `.claude/security-audits/2026-06-19_paper-edit-doi.md`.
- **Deferred (noted in `INCREMENT-49-NOTES.md`):** per-attachment PDF serving (Files opens the *primary*
  PDF today — true per-file routing lands **with F/E's duplicate-merge**, which creates multi-PDF records);
  multiple URLs; Translator(s); a "More" **add-arbitrary-field** menu (today it only surfaces what a DOI gave).

### Multi-paper summary from a library selection — ✅ selection→summarize DONE (inc 62); critical-review DEFERRED
- [x] **Selection → summarize (inc 62):** the library bulk bar's **summarize** button runs a verified,
  citation-grounded synthesis of the checkbox-selected papers in the always-on Synthesis pane (with an "N
  selected papers" note), reusing the `/summarize` papers scope + local verification + the inc-61 cache.
  Includes a backend **round-robin chunk-coverage fix** so a multi-paper summary spans all selected papers
  (`pipeline.py::_round_robin_by_paper`). See `INCREMENT-62-NOTES.md`.
- [ ] **Critical-review supplement (DEFERRED):** a stronger, more opinionated generation mode (its own
  endpoint/mode, egress gate, security audit) that critically reviews the selected paper(s). **Must meet the
  Auditability standard** (cross-cutting, above) before it ships — it judges/critiques rather than grounds.
- [ ] **Optional follow-ups:** a focus **query** for a multi-paper summary (query-ranked coverage); coverage
  beyond the 24-paper cap.

---

## Theme 4 — App-wide

### H. **Settings UI** + light/dark mode — ✅ DONE (increment 46)
- [x] **Settings modal** (`35_settings.jsx`, gear icon in the sidebar) — the prefs surface; persists to
  localStorage.
- [x] **Light/dark mode toggle** — warm-dark theme via `:root[data-theme="dark"]` CSS-variable overrides +
  a no-flash bootstrap; theme-matched logo (`logo_dm.png`); the rendered PDF page stays light. See
  `INCREMENT-46-NOTES.md` + `DESIGN.md` §1b.
- [x] **Favicon dark-swap** — ✅ DONE (inc 53): two `media="(prefers-color-scheme:…)"` favicon links
  (light/dark), no JS; follows the OS scheme.
- [~] **Remaining/queued:** more settings (e.g. the axis cutoff default → here); the DESIGN.md §3 `.btn-*`
  class DRY — **PARTIAL (inc 68)**: canonical `.btn-*` classes added + the cleanly-identical buttons
  consolidated by selector-grouping (CSS-only, no visual change); *remaining* = migrate the divergent
  ghost/icon buttons by changing their JSX className to `.btn-*` (value-shifting) + reconcile
  `.axis-link.axis-danger` amber→red. The **full** radius consolidation (4/5/6/8/9px) — the radius *tokens* +
  clean pill/modal migration landed inc 53; the messy middle remains.

### In-app HELP viewer + AI help assistant — ✅ DONE (inc 53 → corpus-driven modal inc 59 → assistant inc 60)
- [x] A **?** button opens `HelpModal` (`18_help.jsx`). **inc 59:** fetches `GET /help/corpus` and renders
  **extensive** end-user docs (`app/backend/help/help_content.md`) as a navigable two-column modal (TOC +
  scroll-to-flash). **inc 60:** an **AI help assistant** (`POST /help/ask`) — ask a question, get an answer
  + reference chips that deep-link sections via `flashHelpSection`; **separate** `CALLOSUM_HELP_ASSISTANT_ENABLED`
  gate (independent of the library egress flag), inc-58 seam pattern, NO RAG. Help feature complete.

### Hardening — Subresource Integrity on CDN scripts — ✅ DONE (increment 53)
- [x] `integrity="sha384-…" crossorigin="anonymous"` on the React / ReactDOM / Babel-standalone
  `<script>` tags in `index.html` (pdf.js loads dynamically — left as-is). Verified by the live E2E
  (the app renders under the hashes).

### Packaging & distribution (post-V1) — [ ] open
*(Captured 2026-06-20 reconciling the `app/desktop-shell/` + `ops/` READMEs, whose "planned" notes were
invisible to this backlog.)*
- [ ] **Desktop shell (Tauri)** — wrap the local FastAPI + browser UI as a native desktop app
  (`app/desktop-shell/`, currently a placeholder). Post-V1; the app runs as a local server + browser today.
- [ ] **OS keychain for secrets** — store `GOOGLE_API_KEY` (and any future secret) in the OS keychain rather
  than an env var / `.env`, for a non-technical desktop user. Pairs with the desktop shell.
- [ ] **Desktop distribution + GROBID service ops** — installers/packaging + (when Track C lands) running a
  local GROBID service (`ops/` notes). Exploratory; tracked here so those READMEs aren't invisible to the plan.

---

## Captured from `callosum_TDL.txt` (2026-06-20) — near-term UX the original backlog predates

The user's raw to-do list, folded in (deduped against shipped increments). Each gets its own plan-mode design.

**Library management & import**
- [ ] **Scan / refresh / watch library folders** (the user's top-priority marker) — detect new/changed/removed
  files in a watched folder and reconcile the library. Pairs with *Import coverage* (Theme 2).
- [ ] **"UNSORTED" cluster** — a toggle gathering papers whose DOI/metadata resolution failed (the Mendeley
  "Unsorted/Needs-review" analogue) so they are easy to find + fix.
- [ ] **Filter library by type** (article / book / preprint …) — extends the inc-69 sort + inc-63/71 axis/tag
  filters (sort-by-date already shipped in inc 69).
- [ ] **Drop chunked-row content from library article cards** — cards currently show chunk text; tidy them to
  bibliographic info only.
- [ ] **Double-click-to-open vs. text-selection** — stop a library card's double-click-to-open from hijacking
  text selection inside the card (UX bug).

**PDF viewer**
- [ ] **Page-view options** — fit-to-width, two-up / side-by-side, etc.
- [ ] **Reading mode** — a distraction-minimized layout that maximizes the active PDF and hides chrome.

**Settings & accounts**
- [ ] **Gemini API key field in Settings** — let the user set `GOOGLE_API_KEY` from the Settings UI (the
  **BYO-key** model for public/GitHub users who supply their own key). *Security:* store it safely (OS keychain
  — see *Packaging & distribution* — or at minimum never log/commit it); composes with the egress gate.
- [ ] **Account creation / login + publishing name** — a settings-level identity (the publishing name feeds
  **My Publications**). **Big + security-sensitive** — auth is absent by design today (see the pre-deployment
  requirements in CLAUDE.md); needs its own design + audit. Likely post-V1 / tied to any hosted mode.
- [ ] **Hide uncertain axis papers BY DEFAULT** — make the inc-51 per-axis 👁 toggle default to *hidden* (a
  Settings default), surfacing uncertain only on demand.

**App-wide UX**
- [ ] **Progress indication for long operations** — a standard: any time-taking op (summary/score/suggest/dedup
  jobs, import, embedding) must tell the user it's happening, with a progress bar.
- [ ] **Re-score line-wrapping fix** — the re-score control line wraps badly in expanded axis cards (UI bug).

**Investigations (not features)**
- [ ] Confirm where the in-app images (the `.webp`s) are actually stored/served.
- _Retraction tracking + "make it plain to users" → already the **findings subsystem** (future-tracks) + the
  equity track's **self-correction** signal; not re-listed here._

---

## Deferred — needs more thought (do last)

### Library **merge** (free-form; deliberately **NOT** gated behind dedup)
- [ ] Manually merge two/several library entries into one (combine metadata, pick a canonical record,
  re-point PDF/chunks/embeddings/**annotations**/synthesis-citations/axis-assignments). Destructive +
  far-reaching → its own carefully-audited increment.
- **Why free-form, not gated behind dedup (E):** Zotero/Mendeley both offer manual merge, and their
  *automatic* duplicate detection routinely fails to surface true duplicates. Gating merge behind detection
  traps the user — e.g. a published article + its preprint where the preprint is a scanned PDF with
  garbage OCR: detection may not link them, leaving the user forced to either keep the unwanted duplicate
  or **delete something they want to keep**. Manual merge must always be available. _(User wants more time
  to think on the exact UX — hence parked at the end. Pairs with an **undo/soft-delete** safety net given
  how destructive it is.)_

---

## Open proposals (raised, not yet adopted — decide later)
- **Undo / soft-delete (trash).** Several destructive ops are landing (bulk delete, eventually merge) in an
  app with no undo and no git (only zip snapshots). A trash or undo buffer is worth a slot before/with the
  destructive features — especially the merge above.
- **Filter the library by axis.** — ✅ DONE (increment 63). Clicking an axis's **count badge** narrows the
  Library to that axis's papers (server-side `?axis_id=` filter) with a clearable banner; pairs with the
  inc-62 multi-paper summarize (filter → select all → summarize). See `INCREMENT-63-NOTES.md`. _(Deferred:
  cross-page select-all, filter by tier, persisting the filter.)_

---

## Longer-horizon future tracks (detailed prompts in [`future-tracks/`](future-tracks/))

The grand plan: Callosum as a complete, **inspectable** ecosystem for engaging the literature responsibly.
Each track is a *signal/suggestion/retrieval that stays non-authoritative* and must pass the **Principles
alignment gate** (`.claude/PRINCIPLES.md`) before any build. These are sequenced *toward*, not queued — the
core UX above comes first. See `future-tracks/README.md` for the index; do not recapitulate their detail here.

- [ ] **Open-science signals — statcheck** (`future-tracks/opus4.8_future-tracks.md` Track A): recompute APA
  NHST p-values from extracted text; a separately-displayed, inspectable per-paper signal (never folded into
  a hidden score). Folds into the METHODS findings subsystem. Runs on existing PDF text.
- [ ] **Word + LibreOffice citation plugin** (Track B): cite-while-you-write over the canonical CSL-JSON + a
  CSL processor (`citeproc-py`/`citeproc-js`); a backend CSL-format endpoint, then an Office.js add-in, then a
  LibreOffice UNO extension. Post-V1 authoring surface; **never auto-inserts** a citation.
- [ ] **Highlight-to-suggest / highlight-to-evaluate** (Track C): for a draft sentence — suggest the papers to
  cite (in-library = retrieval in reverse, fully local; beyond-library via OpenAlex/Semantic-Scholar with
  explainable reasons) and evaluate the claim's support/contrast/mention via the existing NLI/verification
  spine. Suggestions carry reasons; never auto-insert/auto-judge. Highest-value novel capability.
- [ ] **Free-legal full-text acquisition** (Track D): an ordered resolver chain (OpenAlex→Unpaywall→PMC/Europe
  PMC→preprints→CORE→institutional→author-contact→honest "not found"); validates + stores the PDF as a managed
  attachment that upgrades the paper's tier. **Explicitly excludes paywall circumvention.**
- [ ] **THEORY/METHODS panes + findings subsystem** (`…_theorymethods.md`): a module-registry accordion + a
  **FACT-vs-candidate** findings model (retraction via Crossref Retraction Watch, statcheck, transparency
  producers) with distinct visual/epistemic treatment. **Cross-cut:** system FACTs (e.g. `RETRACTED`) should be
  filterable via the inc-71 tag mechanism — see the "Tags hook" notes + the Tags & keywords section above.
- [ ] **THEORY/METHODS module pool** (`…_theorymethodsextension.md`): additional principle-aligned panel-module
  candidates, each a self-contained prompt; depends on the findings subsystem + module registry.
- [ ] **Literature discovery — Feed/Search tabs** (`…_librarypaneltabadditions.md`): FEED + SEARCH center tabs
  over a `SourceProvider` layer (PubMed/Crossref/bioRxiv), Fraser-method triage, axis-relevance **highlight
  (augment, never filter)**; save→auto-axis. On save, attach the source's keywords as tags (Tags & keywords).
- [ ] **Literature gap-finder** (`…_gapfinder.md`): surface relevant-but-absent papers via citation methods
  (backward/forward gap, followed authors) with transparent provenance, ranked by axis relevance, add-or-dismiss.
  Depends on the OpenAlex adapter.
- [ ] **My Publications** (`…_mypublications.md`): an auto, pinned axis of the researcher's own papers; **LLM-free**
  OpenAlex/ORCID author resolution with confirm-and-learn. Shared author-resolution infra for the gap-finder.
- [ ] **User-authored modules** (`…_plugins.md`): **deferred record only** — capture the extension-point idea +
  open questions; do NOT build a plugin system until a dedicated design pass.
- [ ] **Equity & integrity signals** (`…_equityintegritysignals.md`, HACKADEMIA-derived; folded in 2026-06-20
  from the future-tracks-import inbox): inspectable, **non-accusatory** prestige/credit/attention lenses —
  overlooked-work (inverse Matthew effect), citation credit-concentration (self-cite / reciprocal clusters),
  positive self-correction — plus 2 principle-fraught forensic candidates (analytic-flexibility, stylometric)
  recorded with the **no-index / no-accusation** reframing baked in. All citation-graph-shaped → depend on the
  **OpenAlex adapter** + the **findings subsystem**, and project as **system-facts tags** (extend the
  `system:{…}` provenance vocabulary in *Tags & keywords*). Gated by the Principles gate **and** the
  `APPROACH-AVOIDANCE.md` **no-accusation** veto boundary before any build — this is the track that most needs
  the values layer.
- [ ] **Research-impact analytics** (`…_researchimpactanalytics.md`, folded in 2026-06-20 from the inbox):
  opt-in, local-first, **commons**-structured measurement of whether Callosum changes how people research, held
  to **human-subjects-research** consent discipline (not telemetry; no IRB → self-imposed). Two separate
  projects: **A. local usage analytics** (zero-egress; user is the first beneficiary — the **instrumentation
  seam + personal dashboard are the only near-term, buildable-now parts**) and **B. cross-user impact signal**
  (far-future, gated on an accounts/hosting decision + N>1 + an in-product consent regime). Touches the **egress
  posture + equity/data-sovereignty** → must pass the Principles gate **and** the A-A values layer (default-deny
  opt-in; compute-locally / transmit-summaries-only; pseudonymous-named-honestly; a **public field registry** as
  a data-minimization fitness function; commons reciprocity; valence rule = *less* time-in-app is the win).
  Graduation past the two zero-egress stages is the user's explicit call.
- [ ] **PUBLISHERS — where-to-submit METHODS tool** (`…_publishersmethodstool.md` + its child gate
  `…_publisherschoicegate.md`, folded in 2026-06-20 from the inbox): at submission time, surface **verifiable,
  fully-sourced facts** about each candidate journal (OA color, APC + waiver, green route, license, RR/data
  policy, TOP factor, open impact, multi-route legitimacy **incl. regional indexes**) under a **visible,
  user-set open-science weighting** — the author weighs them; the tool **never computes a verdict**. Veto-level:
  **no composite score, no "predatory" label/classifier** (the A-A **no-accusation** boundary), the abstract +
  preferences matched/stored **locally and never transmitted** (no closed-publisher JournalFinder), **equity**
  (regional-index parity; gate-the-boost-not-the-listing) first-class. The **first-use choice gate** (no
  pre-selected default; the weighting as one forced choice among peers) is the near-term enhancement. **More
  controversial than most tracks** — build only this principled shape; depends on the Word link + local
  embeddings; gate through the Principles gate **and the A-A values layer** at graduation. **Do not build yet.**

**Shared infra these unlock (kept as README-only `integrations/` stubs on purpose):** the **OpenAlex** adapter
(my-publications → gap-finder → discovery → acquisition — build first as shared infra), **Unpaywall** (Track D),
**Semantic Scholar** (Track C, discovery), **GROBID** (Track C section-scoping). (**mendeley** is the exception
— NOT track infra; it's **import coverage**, tracked under *Import coverage* in Theme 2 above.)

---

## Dev-infra & repo hardening (post-git) — added 2026-06-20 (from the inbox)

Two roadmap docs filed under `future-tracks/` (detail there — reference, don't recapitulate). This is the
near-term work now that the repo is live.

- [ ] **Harness hardening** (`future-tracks/opus4.8_future-tracks_harnesshardening.md`) — adopt **uv**
  (`uv.lock`); **pre-commit** (ruff, whitespace, a 600-line size-budget script); add CI gates **one at a time**
  (`alembic check` + a temp-DB migration test, **pip-audit** + **Dependabot**); **stage** expensive/judgment
  checks as dormant drafts in a new **`.claude/staged-harnesses/`** + `REGISTRY.md` with activation triggers
  (Pyright strict, tach boundary contracts, coverage gate, Hypothesis, embedding/vector-drift harness, bandit);
  **branch protection** after CI is green; reclassify the principles gate as **governance, not a fitness
  function**; remaining repo furniture: **SECURITY.md, `.env.example`, CITATION.cff, CHANGELOG, SPDX
  `AGPL-3.0-or-later` in `pyproject.toml`**. Standing rule: **ratchet — one new blocking gate at a time**;
  subtraction is the tie-breaker.
- [ ] **README front-door expansion** (`future-tracks/opus4.8_future-tracks_readmescopeaudit.md`) — the README
  is accurate but scoped as an app description; expand it into a contributor front door: known-limitations /
  rough-edges, a **safety note** (127.0.0.1, no auth/rate-limiting, don't expose), **cross-platform** (bash)
  setup + venv/uv, dev-vs-user setup + the frontend build step, first-run model-download note, secrets /
  `.env.example` + **both** egress gates (incl. `CALLOSUM_HELP_ASSISTANT_ENABLED`), pointers to
  CONTRIBUTING/SECURITY/CITATION, the auto-migrate note, an honest "built with AI assistance" note, and a UI
  screenshot. (Status + license **badges added 2026-06-20**.)

---

## Security follow-up (do whenever; NOT blocking) — added 2026-06-20

- [ ] **Rotate the 4 Gemini API keys.** They remain in **Dropbox version history** (and were embedded in 16 local
  backup zips inside the old `.claude/GEMINI_API.txt` until the 2026-06-20 scrub removed them). `.gitignore` keeps
  all key material out of GitHub — proven via `git check-ignore` — so this is **not blocking**; but rotation
  (revoke + reissue in Google AI Studio, then update `.env`) is the only way to neutralize the copies that exist
  *outside* git. Deferred by the user — do whenever convenient.
