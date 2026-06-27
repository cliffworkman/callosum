# Increment backlog — DONE (shipped / closed items)

The completed half of the backlog, split out of [`INCREMENT-BACKLOG.md`](INCREMENT-BACKLOG.md) on 2026-06-20 so
the open queue stays scannable. This is the one-line *"what landed, which increment"* map; the per-increment
design diary (`increment-notes/INCREMENT-NN-NOTES.md`) and `changes.md` hold the detail. Items here are closed —
new work goes in the open backlog.

---

## Cross-cutting
- [x] **DESIGN.md design dictionary** (2026-06-19) — Pass 1 tokens + element recipes, Pass 2 inconsistencies +
  canonical rules; **CLAUDE.md rule #8** (read it before any CSS change) + reference-table + decision rows.
  *(The Pass-2 consolidation worklist remainder is still open — see the open backlog.)*

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
  retrieval** (inc 66). *(Deferred: permanent delete doesn't remove the on-disk PDF — open.)*
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
