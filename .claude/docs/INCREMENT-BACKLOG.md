# Increment backlog — OPEN (nearer-term core-UX increments)

Durable, ordered to-do list — **open items only.** Shipped/closed items were split out to
[`INCREMENT-BACKLOG-DONE.md`](INCREMENT-BACKLOG-DONE.md) on 2026-06-20 so this queue stays scannable. Each item
gets its **own plan-mode design** when picked up — several are deliberately underspecified here; this is the
queue, not the design.

> **Guiding principle (the user's framing):** *reference manager first.* The verified-synthesis crown jewel
> only matters if Callosum is a credible day-one replacement for Mendeley/Zotero — otherwise it's a costly
> single-use tool opened *alongside* them, not *instead of* them. "The crown jewel only sells tickets if it's in
> a beautiful museum." So this whole backlog is **high priority** — it's the museum.

> Scope note: the bigger **longer-horizon tracks** live as detailed build-prompt docs under
> **[`future-tracks/`](future-tracks/)** (see its `README.md` index). **`future-tracks/` is the canonical
> source — reference it, don't recapitulate.** The items below are the near-term core UX.

_Italic notes are light implementation pointers, not designs._

---

## Tags & keywords (added 2026-06-20, post inc-71/73)

- [ ] **Author/expert keywords as FIRST-ORDER tags — remaining sources.** Zotero tags (inc 71) + Crossref
  `subject` (inc 73) already import as tags. Remaining: **OpenAlex `concepts`** + **PubMed MeSH** (richer index
  keywords; arrive when those integrations land — OpenAlex client exists for OA-location only today; PubMed via
  the connected MCP). On a Feed/Search **save** (librarypaneltab track), attach the source's keywords as tags.
- [ ] **Tag provenance / source.** `tags.import_source` already seeds this (`zotero`/`user`/`keyword:crossref`);
  formalize a small vocabulary — `user`, `keyword:{crossref|openalex|pubmed}`, `system:{retraction|transparency|…}`
  — so the UI can group/style by source ("author keywords" vs "your tags" vs "system facts"), protect
  imported/system tags from silent clobber (mirror the inc-49 user-edit guard), and offer "show only author
  keywords." NB a per-**link** provenance may be needed for per-paper facts (a global tag's `import_source` can't
  say "THIS paper is retracted") — those likely belong to the findings subsystem, projected as read-only
  system-tags.
- [ ] **Tags ↔ findings / system-facts (the retraction-surfacing connection).**
  `opus4.8_future-tracks_theorymethods.md`'s **findings subsystem** emits a retraction FACT (Crossref Retraction
  Watch) as a persistent **"retracted" mark** + descriptive transparency tags (open-data/code/prereg). These
  should be **filterable the way tags are** — "locate every RETRACTED paper" — reusing the inc-71 tag-filter
  (`?tag_id=`/banner) OR a unified facet filter. **Build directive when those tracks land:** do NOT reinvent a
  separate filter/chip surface — extend tags/tag-filter; keep system-facts visually distinct + non-editable.
  **→ Worth a short design chat before the findings track starts.**

---

## Cross-cutting — `DESIGN.md` Pass-2 consolidation (open remainder)

- [ ] **Apply the Pass-2 consolidation worklist** (DESIGN.md §3) — opportunistically or on request: migrate the
  **divergent ghost/icon buttons** to the canonical `.btn-*` classes (value-shifting → a per-button JSX className
  change), reconcile `.axis-link.axis-danger` amber→red, and finish the **radius scale**'s messy middle
  (4/5/6/8/9px — the tokens + clean pill/modal migration landed inc 53). Best folded into the next CSS-heavy
  increment. (New CSS already follows the canonical rules.)

---

## Cross-cutting — Auditability standard (gating constraint for AI-assist features) — open question

- [ ] **Resolve "how auditable is auditable enough?" — explicitly, before any AI-assist authoring/evaluation
  feature ships.** The features that propose citations, judge a user's claim, or critically review papers
  (future-tracks **Track B/C** + the **multi-paper critical-review supplement** below) are stronger, more
  opinionated AI actions than a grounded summary; the inspectability bar must be **defined deliberately, not
  assumed**. **Reference model:** the existing local citation-verification layer (embedding + NLI stance +
  verbatim quote, shown with confidence — invariant #1/#4). New AI-assist surfaces meet it or state explicitly
  where/why they fall short — and the verification step must be **low-friction** (users skip verification under
  time pressure). _A gating note on the items below, not a feature itself._

---

## Theme 2 — Library management (open)

- [ ] **Permanent delete doesn't remove the on-disk PDF** (managed/linked) — deferred from inc 65 (deleting
  user files is riskier). See `INCREMENT-65-NOTES.md`.
- [ ] **Import coverage — beyond Zotero.** Today only Zotero imports (`importers/zotero.py`).
  Reference-manager-first parity = accept libraries originating elsewhere, mapped to the same `csl_json` record:
  **Mendeley** (via Zotero's bridge or exported BibTeX/RIS/CSL-JSON — **not** direct encrypted-local-DB reads;
  surfaces the `integrations/mendeley/` stub); **BibTeX / RIS / CSL-JSON import** (the complement to inc-70
  export; reuse the CSL-JSON model). _Validate untrusted import files at the boundary (rule #4); audit-gate the
  new ingestion path._

---

## Theme 3 — Synthesis & Details (open)

- [ ] **G deferred items** (`INCREMENT-49-NOTES.md`): per-attachment PDF serving (Files opens the *primary* PDF
  today — true per-file routing lands with the duplicate-merge multi-PDF records); multiple URLs; Translator(s);
  a "More" **add-arbitrary-field** menu (today it only surfaces what a DOI gave).
- [ ] **Critical-review supplement (multi-paper).** A stronger, more opinionated generation mode (own
  endpoint/mode, egress gate, security audit) that critically reviews the selected paper(s). **Must meet the
  Auditability standard** (above) before it ships — it judges/critiques rather than grounds.
- [ ] **Multi-paper summary follow-ups:** a focus **query** (query-ranked coverage); coverage beyond the
  24-paper cap.

---

## Theme 4 — App-wide (open)

- [ ] **More settings** — e.g. the axis cutoff default → Settings. (Hide-uncertain-by-default shipped inc 77.)
- [ ] **`.btn-*` divergent-button migration** — see the DESIGN.md Pass-2 remainder above.
- [ ] **Packaging & distribution (post-V1)** — a **Tauri desktop shell** (`app/desktop-shell/` placeholder); an
  **OS keychain** for `GOOGLE_API_KEY` (+ future secrets) for a non-technical desktop user; **desktop
  distribution + GROBID service ops** (when Track C lands; `ops/` notes). Exploratory.

---

## Captured from `callosum_TDL.txt` (near-term UX)

**Library management & import**
- [ ] **Scan / refresh / watch library folders** (user's top-priority marker) — detect new/changed/removed
  files in a watched folder and reconcile the library. Pairs with *Import coverage*.
- [ ] **"UNSORTED" cluster** — a toggle gathering papers whose DOI/metadata resolution failed (the Mendeley
  "Unsorted/Needs-review" analogue) so they are easy to find + fix.
- [ ] **Filter library by type** (article / book / preprint …) — extends the inc-69 sort + inc-63/71 axis/tag
  filters (same allowlist-param pattern).

**PDF viewer**
- [ ] **Page-view options** — fit-to-width, two-up / side-by-side, etc.
- [ ] **Reading mode** — a distraction-minimized layout that maximizes the active PDF and hides chrome.

**Settings & accounts**
- [ ] **Gemini API key field in Settings** — set `GOOGLE_API_KEY` from the UI (the **BYO-key** model for
  GitHub users). _Security:_ OS keychain (see Packaging) or at minimum never log/commit it; composes with the
  egress gate.
- [ ] **Account creation / login + publishing name** — a settings-level identity (the publishing name feeds
  **My Publications**). **Big + security-sensitive** — auth is absent by design today; needs its own design +
  audit. Likely post-V1 / tied to any hosted mode.

**App-wide UX**
- [ ] **Progress indication for long operations** — a standard: any time-taking op (summary/score/suggest/dedup/
  acquire/wanted jobs, import, embedding) tells the user it's happening, with a progress bar.
- [ ] **Re-score line-wrapping fix** — the re-score control line wraps badly in expanded axis cards (UI bug).

**Investigations (not features)**
- [ ] Confirm where the in-app images (the `.webp`s) are actually stored/served.

---

## Deferred — needs more thought (do last)

### Library **merge** (free-form; deliberately **NOT** gated behind dedup)
- [ ] Manually merge two/several library entries into one (combine metadata, pick a canonical record, re-point
  PDF/chunks/embeddings/**annotations**/synthesis-citations/axis-assignments). Destructive + far-reaching → its
  own carefully-audited increment.
- **Why free-form, not gated behind dedup (E):** Zotero/Mendeley both offer manual merge, and *automatic*
  duplicate detection routinely fails to surface true duplicates (e.g. a published article + its preprint where
  the preprint is a scanned PDF with garbage OCR). Gating merge behind detection traps the user into keeping an
  unwanted duplicate or deleting something they want. Manual merge must always be available. _(User wants more
  time on the exact UX — parked at the end. Pairs with an **undo/soft-delete** safety net.)_

---

## Open proposals (raised, not yet adopted — decide later)
- **Undo / soft-delete buffer (beyond Trash).** Merge (above) is destructive in an app with no git (only zip
  snapshots); a stronger undo buffer is worth a slot before/with merge. (Basic Trash + Restore shipped inc 54/65.)

---

## Longer-horizon future tracks (detailed prompts in [`future-tracks/`](future-tracks/))

The grand plan: Callosum as a complete, **inspectable** ecosystem for engaging the literature responsibly. Each
track is a *signal/suggestion/retrieval that stays non-authoritative* and must pass the **Principles alignment
gate** before any build. Sequenced *toward*, not queued — the core UX above comes first. See
`future-tracks/README.md` for the index; do not recapitulate the detail here.

- [ ] **Open-science signals — statcheck** (`opus4.8_future-tracks.md` Track A): recompute APA NHST p-values
  from extracted text; a separately-displayed, inspectable per-paper signal (never a hidden score). Local; runs
  on existing PDF text.
- [ ] **Word + LibreOffice citation plugin** (Track B): cite-while-you-write over the CSL-JSON + a CSL processor;
  a backend CSL-format endpoint, then an Office.js add-in, then a LibreOffice UNO extension. **Never auto-inserts.**
- [ ] **Highlight-to-suggest / highlight-to-evaluate** (Track C): for a draft sentence — suggest papers to cite
  (in-library = retrieval in reverse, local; beyond-library via OpenAlex/Semantic-Scholar with explainable
  reasons) + evaluate support/contrast/mention via the NLI spine. Never auto-insert/auto-judge. Highest-value
  novel capability.
- [ ] **Free-legal full-text acquisition** (Track D): **largely shipped as inc 74–76** (the OA lane + cascade +
  wanted list). Remaining track-D ideas: institutional / author-contact resolvers, the honest "not found" UX
  polish. **Explicitly excludes paywall circumvention.**
- [ ] **THEORY/METHODS panes + findings subsystem** (`…_theorymethods.md`): a module-registry accordion + a
  **FACT-vs-candidate** findings model (retraction via Crossref Retraction Watch, statcheck, transparency
  producers), distinct visual/epistemic treatment. **Cross-cut:** system FACTs (`RETRACTED`) filterable via the
  inc-71 tag mechanism (see Tags & keywords).
- [ ] **THEORY/METHODS module pool** (`…_theorymethodsextension.md`): additional principle-aligned panel-module
  candidates; depends on the findings subsystem + module registry.
- [ ] **Literature discovery — Feed/Search tabs** (`…_librarypaneltabadditions.md`): FEED + SEARCH center tabs
  over a `SourceProvider` layer (PubMed/Crossref/bioRxiv), Fraser-method triage, axis-relevance **highlight
  (augment, never filter)**; save→auto-axis (attach source keywords as tags).
- [ ] **Literature gap-finder** (`…_gapfinder.md`): surface relevant-but-absent papers via citation methods
  (backward/forward gap, followed authors) with transparent provenance, ranked by axis relevance, add-or-dismiss.
  Depends on the OpenAlex adapter.
- [ ] **My Publications — Part 2: impact dashboard tab** (`…_mypublications.md`): **Part 1 shipped inc 78**
  (the auto-axis); **Layer 1 shipped inc 81** (the 📊 dashboard tab — headline OpenAlex metrics + the
  indexed-vs-library gap + a publications-by-year SVG chart + an editable AI research summary; cache-only read,
  the summary egress-gated). Remaining: **Layer 2** domain decomposition (cluster the user's own corpus into
  sub-axes via `abstract_clustering.py`, citations per domain, re-filter the Layer-1 plot/tiles); **Layer 3**
  enriched paper cards (per-paper OpenAlex citation count + citing-works modal, field/year percentile,
  citations-by-year sparkline, self-vs-external split); **Layer 4** grounded prospection (citation gaps,
  emerging citing-topics, candidate collaborators — LLM narration over graph data only). The author-resolution
  infra (`integrations/openalex/author.py`) now also unlocks the **gap-finder** / discovery track (a separate
  parked future-track the user floated: find papers beyond the library / external search).
- [ ] **User-authored modules** (`…_plugins.md`): **deferred record only** — capture the extension-point idea +
  open questions; do NOT build a plugin system until a dedicated design pass.
- [ ] **Equity & integrity signals** (`…_equityintegritysignals.md`, HACKADEMIA-derived): inspectable,
  **non-accusatory** prestige/credit/attention lenses (overlooked-work / inverse Matthew, citation
  credit-concentration, positive self-correction) + 2 principle-fraught forensic candidates recorded with the
  **no-index / no-accusation** reframing. Citation-graph-shaped → OpenAlex adapter + findings subsystem; project
  as **system-facts tags**. Gated by the Principles gate **and** the A-A **no-accusation** veto — the track that
  most needs the values layer.
- [ ] **Research-impact analytics** (`…_researchimpactanalytics.md`): opt-in, local-first, **commons**-structured
  measurement of whether Callosum changes how people research, at **human-subjects-research** consent discipline.
  **A.** local usage analytics (zero-egress; instrumentation seam + personal dashboard are the only near-term,
  buildable-now parts) vs **B.** cross-user impact signal (far-future, gated). Must pass the Principles gate **and**
  the A-A values layer (default-deny; compute-locally / transmit-summaries-only; public field registry; commons
  reciprocity; valence rule = *less* time-in-app is the win). Graduation is the user's explicit call.
- [ ] **PUBLISHERS — where-to-submit METHODS tool** (`…_publishersmethodstool.md` + its child gate
  `…_publisherschoicegate.md`): at submission time, surface **verifiable, fully-sourced facts** per candidate
  journal (OA color, APC + waiver, green route, license, RR/data policy, TOP factor, open impact, multi-route
  legitimacy **incl. regional indexes**) under a **user-set open-science weighting** — the author weighs them;
  **never a verdict**. Veto: **no composite score, no "predatory" label** (A-A no-accusation), abstract +
  preferences **local, never transmitted**, **equity** first-class. The **first-use choice gate** (no
  pre-selected default; the weighting one forced choice among peers) is the near-term enhancement. **More
  controversial than most** — build only this principled shape; gate through Principles + A-A at graduation.
  **Do not build yet.**

**Shared infra these unlock (kept as README-only `integrations/` stubs on purpose):** **OpenAlex** (my-pubs →
gap-finder → discovery → acquisition; the acquisition slice is built), **Unpaywall** (Track D — superseded by
OpenAlex in inc 74), **Semantic Scholar** (Track C, discovery), **GROBID** (Track C section-scoping).
(**mendeley** is NOT track infra — it's *Import coverage*, above.)

---

## Dev-infra & repo hardening (post-git) — added 2026-06-20

Two roadmap docs under `future-tracks/` (detail there — reference, don't recapitulate). Near-term now the repo
is live.

- [ ] **Harness hardening** (`future-tracks/opus4.8_future-tracks_harnesshardening.md`) — adopt **uv**
  (`uv.lock`); **pre-commit** (ruff, whitespace, a 600-line size-budget script); CI gates **one at a time**
  (`alembic check` + a temp-DB migration test, **pip-audit** + **Dependabot**); **stage** expensive/judgment
  checks as dormant drafts in a new **`.claude/staged-harnesses/`** + `REGISTRY.md` with activation triggers
  (Pyright strict, tach, coverage, Hypothesis, embedding/vector-drift, bandit); **branch protection** after CI is
  green; repo furniture: **SECURITY.md, `.env.example`, CITATION.cff, CHANGELOG, SPDX `AGPL-3.0-or-later`**.
  Standing rule: **ratchet — one new blocking gate at a time**; subtraction is the tie-breaker.
- [ ] **README front-door expansion** (`future-tracks/opus4.8_future-tracks_readmescopeaudit.md`) — expand the
  README into a contributor front door: known-limitations, a **safety note** (127.0.0.1, no auth/rate-limiting),
  **cross-platform** setup + venv/uv, dev-vs-user setup + the frontend build step, first-run model-download note,
  `.env.example` + **both** egress gates, pointers to CONTRIBUTING/SECURITY/CITATION, the auto-migrate note, an
  honest "built with AI assistance" note, a UI screenshot. (Status + license badges added 2026-06-20.)

---

## Security follow-up (do whenever; NOT blocking) — added 2026-06-20

- [ ] **Rotate the Gemini API keys** (and the CORE key pasted in chat during inc 75). They live in **Dropbox
  version history** / chat history; `.gitignore` keeps all key material out of GitHub (proven via
  `git check-ignore`), so this is **not blocking** — but rotation (revoke + reissue, then update `.env`) is the
  only way to neutralize copies that exist *outside* git. Deferred by the user.
