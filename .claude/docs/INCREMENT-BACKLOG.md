# Increment backlog — OPEN (complexity-ordered for autonomous operation, 2026-06-21)

> **Reconciled against inc 109–152 on 2026-06-27, and again through inc 202 on 2026-06-29.** A lot that was listed
> open/partial actually shipped (inc 109–116 frontend/UX; 117–119 My-Pubs overhaul; 121 THEORY/METHODS accordion;
> 126–137 GRIM/p-curve/findings/gap-finder; 146–152 the BYOK arc; **156–159 Track C SP1; 161 merge; 162–171 the
> Word/Google-Docs adapters; 175–181 reading-pane + credit + README; and the whole accounts+sync arc 194–202**).
> Those were **relocated to `INCREMENT-BACKLOG-DONE.md`** (breadcrumbs at the bottom) and the partial items below
> tightened to their *true remainder*. **Number gaps (#1, #2, #10, #39 …) = shipped + relocated** — numbers are kept
> stable for the cross-references. **#15 is now "mostly shipped" (accounts/sync), not "not built."**
>
> **The cut point** (the `⛔ NEEDS CLIFF` line) separates what Claude Code may build unattended from what needs your
> judgment. Slide it; items are numbered so "move #N above the cut" is unambiguous.

> **How this file is organized now.** Every open item is in **one list, ordered by how ready it is for
> Claude Code to execute *unattended*** — simplest/safest at the top, most complex / most-needs-me at the
> bottom. That ordering mostly tracks raw build effort, but it also reflects whether an item needs a
> **decision** from me, touches something **destructive** or **security-sensitive**, is **gated** on an open
> question, or is **blocked** on a prerequisite that doesn't exist yet — because those are what actually
> decide whether CC can safely touch it.
>
> **The cut point** is the line **`⛔ NEEDS CLIFF — requires my judgment; do NOT build autonomously`**.
> Everything above it, CC builds top-down; everything below it is mine. I placed it where I'd draw the line —
> **slide it up or down** (items are numbered, so "move it after #7" is unambiguous). The kickoff prompt keys
> off this exact line, so moving the line resizes CC's scope automatically. The first several items below the
> cut (#5–#9) are the natural "slide-down-to-include" candidates: medium build, not dangerous.
>
> **Labels.** Every below-cut item is tagged with *why* it needs me: **[decision]**, **[security]**,
> **[destructive]**, **[gated]**, **[blocked]**, **[outward-facing]**, **[infra]**, **[future track]**,
> **[non-code]**.
>
> **Nothing lost.** All open-item detail is preserved. Shipped items are kept as one-line breadcrumbs at the
> very bottom — their full detail remains in `INCREMENT-BACKLOG-DONE.md`.

> **Guiding principle (mine):** *reference manager first.* The verified-synthesis crown jewel only matters if
> Callosum is a credible day-one replacement for Mendeley/Zotero — otherwise it's a costly single-use tool
> opened *alongside* them, not *instead of* them. "The crown jewel only sells tickets if it's in a beautiful
> museum." So this whole backlog is **high priority** — it's the museum.

> **Scope note:** the bigger **longer-horizon tracks** live as detailed build-prompt docs under
> **`future-tracks/`** (its `README.md` is the index). `future-tracks/` is the canonical source — the entries
> below are the queue summary, not the design.

_Italic notes are light implementation pointers, not designs._

> ## ⭐ NEXT MAJOR UPGRADE — ✅ SHIPPED inc 121 (relocated to DONE)
> The THEORY/METHODS accordion-on-a-module-registry shell shipped inc 121 (DESIGN.md §5 = the placement rubric +
> registry pattern); the findings/flag/review subsystem it set up then shipped across inc 130–134 (see #31). The
> remaining METHODS-module pool is #32. **No designated "next major upgrade" right now** — pick from the open list.

---

## ▶ AUTONOMOUS — Claude Code builds these, top-down (simplest first)

> **★ DONE (Cliff, 2026-06-26):** the **build-and-test slate** (inc 142–145) **and the full BYOK arc** are shipped —
> **#10** (inc 146 Gemini key in Settings), inc 147 Test-key, inc 148 synthesis "AI is off" nudge, and **#39**
> (inc 149 engine + inc 150 Settings UI: Gemini/OpenAI/Anthropic/**local** via one httpx seam; a loopback local
> provider runs with **zero egress**) — **and all the deferred follow-ons** (inc 151 validation disclaimer +
> help-assistant Settings toggle; inc 152 OS-keychain storage, optional `keyring` + file fallback). **The whole
> BYOK arc is done.** The open backlog below is the next pick.
>
> **Reading-pane follow-ups (Close-reader pass, inc 144 — shipped highlights/notes export):** ✅ **remembered
> scroll position per paper — inc 175**; ✅ **Notes-panel extraction (`30b_notes.jsx`, relieves the cap) + noted-only
> filter + note/text search — inc 176**; ✅ **next/prev-mark toolbar navigation — inc 177**; ✅ **mark-nav `[`/`]`
> hotkeys — inc 179.** Remaining (diminishing + **split-gated**: `30_viewer.jsx` is now 599/600 MAXED → extract
> another low-coupling unit first): keyboard zoom (Ctrl +/− — **conflicts with browser zoom**); a "fit
> page"/fit-height option (touches the fit-mode logic — render-risk); free-form note colors/labels; a
> scrollbar/minimap marker. (See `INCREMENT-144/175/176/177/179-NOTES.md`.)

**Beta feedback — Bella (Slack, 2026-06-30): reading-workflow markers.** Three small, related per-paper-state
features (Cliff queued them; duplicate-detection + the Unsorted tab she also asked for already exist — inc 56/64 +
inc 80). Likely **one increment**: a tiny migration adding per-paper state + a library facet/sort + a card control.
- **reading queue** — ✅ **SHIPPED inc 219** (the **Queue** tab — 3rd tab of the left-pane AXES section): a dedicated
  `reading_queue` table; drag-a-card / Details-button to add, drag-to-reorder, ✓-read / ×-remove.
- **read / unread marker + priority markers** — ✅ **SHIPPED inc 220 (markers + sort) + inc 221 (filter facet)**:
  `papers.read_at` + `papers.priority`; a manual read toggle + a high/normal/low priority picker on each card
  [`16b_readmark.jsx`]; **"By priority"** + **"Unread first"** sorts; and the **header Read/Priority filter facet**
  (inc 221, after the `40_app.jsx`→`useLibrary` split that freed the headroom). User labels, never an AI score (the
  inc-207 declined-ratings logic). **This completes Bella's reading-workflow thread** (queue 219 + markers 220 +
  facet 221).
  *(Experience-pass finding #4 — ✅ **SHIPPED inc 223**: "By priority" now tiebreaks within each tier on recency
  [`papers.id DESC`], so the large unset tier isn't one oldest-first block.)*
*(Eileen's multi-pass metadata enrichment — the other half of that thread — shipped inc 217/218.)*

**SQLite read-then-write upgrade-deadlock — app-wide concurrency hardening** *(surfaced by the inc-219 headed
verification; **inc 219 shipped the partial fix: `PRAGMA journal_mode=WAL` + `busy_timeout=5000` in `make_engine`**,
which resolves the common write-vs-read contention).* **Still open:** a SELECT-then-write endpoint (`add_to_queue`,
`add_tag`, `add_to_axis`, … — most write routes) can *still* rarely fail with `sqlite3.OperationalError: database is
locked` when a write collides with a concurrent fetch in the **same instant** — SQLite returns SQLITE_BUSY *immediately*
for a snapshot-upgrade (busy_timeout can't break it). A human essentially never hits it (it needs two near-simultaneous
writes/a write+fetch); only a machine-gun headed driver provokes it. **The textbook cure (`BEGIN IMMEDIATE` for all
transactions) is UNSAFE here**: `_run_scan_job` (+ embed/import/enrich workers) wrap the entire multi-minute job in **one**
`engine.begin()` transaction, so forcing every transaction to grab the write lock up front would block all other requests
for the whole job. So this needs its **own focused increment** — e.g. a transaction-level retry-on-busy scoped to the
short request-path write endpoints, or splitting the long jobs into incremental commits first (then BEGIN IMMEDIATE
becomes safe). Low user-impact; do it as part of a pre-public concurrency pass.

**Superuser *capabilities* — what the flag gates** — **[decision — deferred by the maintainer]** the **flag shipped
inc 195**: a `CALLOSUM_SUPERUSER_ORCIDS` env allowlist → `app_settings.is_superuser_orcid` → an `is_superuser` flag
derived from the **verified ORCID claim** on the signed-in account, surfaced in `GET /settings`'s `account` block + a
"· superuser" indicator in Account settings (the maintainer's ORCID `0000-0002-2206-0325` is set in the gitignored
`.env`). **Still open:** *what being a superuser actually gates* — no capability is wired yet ("build out what that
means later"). A design decision when a concrete superuser-only capability is wanted.

**statcheck: connect "this paper is flagged" → "the specific result that doesn't recompute"** *(experience-pass
finding, inc 140; persona: the **deadline citer**.)* The per-paper drill-down (METHODS → **Statistics check** →
per-test rows with reported-vs-recomputed *p* + page) exists and is good, but the path to it was hidden.
**~~(a)~~ ~~(c)~~ ~~(d)~~ SHIPPED (inc 141 + 154):** the "⚠ N flagged" chip opens the **Statistics check** section,
re-targets the top flagged paper, **auto-runs** the per-paper check (a+c, inc 141), and **scrolls+flashes the first
inconsistent row** so the citer lands on the specific result that doesn't recompute (d, inc 154). **Remaining
([design] — needs Cliff):** **(b)** a "Check statistics" entry on the paper itself (card chip / Details button) —
inc-122 deliberately moved statcheck *out* of Details, so weigh re-cluttering; **(e)** the "⚠ flagged" (signal) vs
"📋 to review" (work-state) duality — clarify/collapse for the "what's wrong with these numbers" use case (inc-133
made them coexist on purpose).

*(#1 brand-assets investigation — ✅ resolved/non-issue: no `.webp` assets exist, and `inline_brand_assets.py` reads
`.claude/media/` correctly [inc 109 moved the source]; the "silent no-op" was a stale pre-inc-109 sandbox note.
#2 PDF page-view options [fit-width / two-up] — ✅ SHIPPED inc 110. Both relocated to DONE.)*

**3. Protect imported/system tags from silent clobber** — **inc 143 (Librarian pass) shipped the core:** deleting
an imported `keyword:*` tag is now **durable** (a per-paper `suppressed_paper_tags` set, migration 0020 — re-resolve /
backfill no longer silently re-adds a removed keyword; re-adding it clears the suppression). **inc 174** shipped the
**confirm before 🔎 re-resolve overwrites hand-edited metadata** (a `window.confirm` guard when
`imported_source == "user-edited"`). **Remaining ([decision] — needs Cliff):** a tag's **source as an always-on
label/icon** — *conflicts with the inc-100 decision* ("differentiate sources aesthetically, no Details labels"), so
it's not autonomous; a "what re-resolve changed" **diff toast**; a **lock-this-tag** affordance. *(See **#9** for the
full tag-provenance context.)*

**4. Progress indication for long operations** — **[mostly shipped]** indeterminate bar (79) → DETERMINATE "X / N"
progress for scan + import (142) + a "Review unsorted →" door + the **scan done-summary now lists which files
couldn't be read + why** (155) + the **import** path's **skipped-record reporting** (173 — the BibTeX/CSL/RIS
parsers now report entries dropped at parse for no-title-and-no-DOI, plus record-cap overflow; the summary shows
"N skipped (no title or DOI)", and `failed`/`skipped` are now distinct). A rough **ETA** ("~Ns left") — ✅
**SHIPPED inc 225** (`Job.started_at` + `eta_seconds()` → all the job status payloads + ProgressBar/libmenus).
**Remaining:** a per-item **title** in the import/embed/enrich progress label (scan already has the filename, inc
214); a **cancel** button — **deferred** (correct cooperative cancellation needs the four `_run_*_job`
single-`engine.begin()` blocks split into per-item transactions = the same infra as the SQLite read-then-write
concurrency pass above).

**5. G deferred items** (`INCREMENT-49-NOTES.md`) — **[design]** **Shipped:** the "More" add-arbitrary-field menu
(inc 96 — an `AddFieldRow` reusing the validated `csl` patch) + **editable Translator(s)** (inc 111). **Remaining:**
**multiple URLs** (self-contained, small frontend) + **per-attachment PDF serving** (Files opens the *primary* PDF
today — true per-file routing is coupled to the duplicate-merge multi-PDF records, **#17**, and wants a design pass).

⛔ NEEDS CLIFF — requires my judgment; do NOT build autonomously

*(The cut point. Slide it. Items below run from "almost promotable" to "biggest / most gated." #5–#9 are the
natural slide-down candidates.)*

**6. `.btn-*` divergent-button migration / DESIGN.md §3 Pass-2 worklist** — **[decision]** migrate the divergent
ghost/icon buttons to the canonical `.btn-*` classes (value-shifting → a per-button JSX className change),
reconcile `.axis-link.axis-danger` amber→red, and finish the **radius scale**'s messy middle (4/5/6/8/9px — the
tokens + clean pill/modal migration landed inc 53). Best folded into the next CSS-heavy increment; new CSS already
follows the canonical rules. **⚠ Lowest build effort below the line — but it conflicts with inc-86's "keep as
documented exceptions" ruling, which CC caught and escalated in the sandbox instead of executing. Rule on that
(stale item, or are you reversing inc-86?) and it's a trivial promote above the cut.**

**7. Multi-paper summary follow-ups** — **[mostly shipped]** focus-query discoverability (inc 145) + the
**coverage readout** ("Drew from M of N selected papers · top K chunks · K contributed no cited passage") + the
**answerability** note (no claim cleared verification) + the `top_k` display (inc 153) all shipped → relocated to
DONE. **Remaining only:** coverage *beyond* the 24/50-chunk cap (a real multi-pass / map-reduce synthesis change —
its own design + a live eyeball; not autonomous-cheap).

**8. Credit-the-lineage backfill** (`…_credithelpbackfill.md`) — **[your call: attributions]** **inc 180 shipped the
statcheck slice** (in-context credit block + one-click "＋ add to library" for Nuijten et al. 2016, matching
GRIM/p-curve; + consolidated the credit-block CSS into a shared `.method-credit`). **inc 181 shipped Lane B** (a
Runtime & build dependencies section in `THIRD-PARTY-NOTICES.md` crediting every Python+JS dep with its license).
**#8 effectively complete** — the retraction / gap-finder surfaces are data-source-driven (credited at the NOTICE
level, not the add-a-paper pattern), so the Lane-A "add the source paper" doesn't apply there. The retroactive
credit-help backfill: Lane A scholarly-method lineage (statcheck → Nuijten & Epskamp / Nuijten et al. 2016; etc.)
+ Lane B software-dependency NOTICE (AGPL-3.0) + help-doc sync. A near-term **maintenance pass**, not a
longer-horizon track — but it spans the codebase and the attributions are a judgment call. *(Credit-the-lineage is
now a values-layer principle — `.claude/CREDIT-THE-LINEAGE.md`, captured 2026-06-21 — applied forward to every
method-implementing tool: in-context credit + one-click library-add of the source.)*

**9. Tag provenance / source — remaining design-level sub-tasks** — **[design]** `tags.import_source` seeds this
(`zotero`/`user`/`keyword:crossref`). **Shipped:** style-by-source (inc 100 — `source` exposed on
`PaperTagRef`/`TagRef`/`TagSummary`; imported keyword tags render muted + a source tooltip vs the accent-colored
tags you typed, in Details and the sidebar Tags panel) and the source filter (inc 105 — an **All / Yours /
Keywords** toggle in the sidebar Tags panel, shown only when both kinds exist). **Still open (the design-level
parts):** formalize the full vocabulary (`system:{retraction|transparency|…}`) and **group** tags by source in the
UI. *(The clobber-guard sub-task is promoted above the cut as #3.)* NB a per-**link** provenance may be needed for
per-paper facts (a global tag's `import_source` can't say "THIS paper is retracted") — those likely belong to the
findings subsystem, projected as read-only system-tags.

*(#10 Gemini API key field in Settings — ✅ SHIPPED inc 146; folded into the BYOK arc #39. Relocated to DONE.)*

**11. README front-door expansion** (`future-tracks/opus4.8_future-tracks_readmescopeaudit.md`) — **[outward-facing
— your voice]** expand the README into a contributor front door: known-limitations, a **safety note** (127.0.0.1,
no auth/rate-limiting), **cross-platform** setup + venv/uv, dev-vs-user setup + the frontend build step, first-run
model-download note, `.env.example` + **both** egress gates, pointers to CONTRIBUTING/SECURITY/CITATION, the
auto-migrate note, an honest "built with AI assistance" note, a UI screenshot. (Status + license badges added
2026-06-20.) **inc 178 shipped an accurate draft** (current feature list + the `npm install`/`build_frontend` step +
the privacy/security/limitations/AI-assistance sections + credit/license pointers). **Remaining (the maintainer's):
the voice pass + a UI screenshot** (a `<!-- TODO(maintainer) -->` placeholder marks the spot). Also still pending:
`SECURITY.md` / `CITATION.cff` / `.env.example` (backlog #20) so the README can link them.

**12. Critical-review supplement (multi-paper)** — **[gated]** a stronger, more opinionated generation mode (own
endpoint/mode, egress gate, security audit) that critically reviews the selected paper(s). **Must meet the
Auditability standard (#13)** before it ships — it judges/critiques rather than grounds.

**13. Resolve "how auditable is auditable enough?"** — **[decision — gates #12 + future Tracks B/C]** explicitly,
before any AI-assist authoring/evaluation feature ships. The features that propose citations, judge a user's claim,
or critically review papers are stronger, more opinionated AI actions than a grounded summary; the inspectability
bar must be **defined deliberately, not assumed**. **Reference model:** the existing local citation-verification
layer (embedding + NLI stance + verbatim quote, shown with confidence — invariant #1/#4). New AI-assist surfaces
meet it or state explicitly where/why they fall short — and the verification step must be **low-friction** (users
skip verification under time pressure). *Not a build — a decision from you that unblocks the items it gates.*

**14. Permanent delete doesn't remove the on-disk PDF** (managed/linked) — **[destructive]** deferred from inc 65
(deleting user files is riskier). See `INCREMENT-65-NOTES.md`.

**15. Optional account + login + cross-device sync** — **[mostly SHIPPED — accounts arc, incs 194–202]** the whole
arc landed since the last reconcile: **SP1** "Sign in with ORCID" (inc 194 — OIDC + PKCE, identity-only, default-off,
populates My-Pubs); the **superuser flag** (inc 195, capabilities still deferred — see the top item); **SP2**
email/Google login (inc 196 — platform-config via Authentik, method-agnostic); and **SP3 opt-in, E2E-encrypted
cross-device sync** (incs 197–202) — the crypto + change-tracking foundation (197), the `sync_uid` engine over
top-level + FK + link collections (198–200), natural-key tag convergence (201), and the **reference sync-server +
HttpSyncTransport + opt-in `/sync/*`** (202; `sync_server/`, FastAPI+Postgres, OIDC resource server, opaque-blob
E2E). All audited; local-first stays the default. **Remaining:** **SP3c** — the Settings → Sync UI (set up / enable /
run, passphrase prompt) + the **conflict-review screen** (read `sync_conflicts`, pick a side); the maintainer's
**live deploy** (stand up `sync_server/` on Postgres + wire the Authentik audience); pre-public **server hardening**
(per-user rate-limiting, retention, backup runbook, a migration tool); and **SP4 sharing** (= B2 collaboration). The
superuser-*capabilities* decision is the separate top-of-list item.

**16. Undo / soft-delete buffer (beyond Trash)** — **[proposal — pairs with #17]** merge (below) is destructive in
an app with no git (only zip snapshots); a stronger undo buffer is worth a slot before/with merge. (Basic Trash +
Restore shipped inc 54/65.)

**17. Library merge (manual; free-form, deliberately NOT gated behind dedup)** — **[destructive — parked]** manually
merge two/several library entries into one (combine metadata, pick a canonical record, re-point
PDF/chunks/embeddings/**annotations**/synthesis-citations/axis-assignments). Destructive + far-reaching → its own
carefully-audited increment. **Why free-form, not gated behind dedup:** Zotero/Mendeley both offer manual merge, and
*automatic* duplicate detection routinely fails to surface true duplicates (e.g. a published article + its preprint
where the preprint is a scanned PDF with garbage OCR). Gating merge behind detection traps the user into keeping an
unwanted duplicate or deleting something they want. Manual merge must always be available. *(You want more time on
the exact UX — parked at the end. Pairs with the undo/soft-delete net, #16.)*

**18. Author/expert keywords as FIRST-ORDER tags — remaining sources** — **[blocked]** Zotero tags (inc 71) +
Crossref `subject` (inc 73) already import as tags. Remaining: **OpenAlex `concepts`** + **PubMed MeSH** (richer
index keywords) — they arrive only when those integrations land (OpenAlex client exists for OA-location only today;
PubMed via the connected MCP). On a Feed/Search **save** (librarypaneltab track), attach the source's keywords as
tags. Blocked on those integrations + the Feed/Search track (**#28**).

**19. Tags ↔ findings / system-facts (the retraction-surfacing connection)** — **[blocked + design]**
`opus4.8_future-tracks_theorymethods.md`'s **findings subsystem** emits a retraction FACT (Crossref Retraction
Watch) as a persistent **"retracted" mark** + descriptive transparency tags (open-data/code/prereg). These should be
**filterable the way tags are** — "locate every RETRACTED paper" — reusing the inc-71 tag-filter (`?tag_id=`/banner)
OR a unified facet filter. **Build directive when those tracks land:** do NOT reinvent a separate filter/chip
surface — extend tags/tag-filter; keep system-facts visually distinct + non-editable. **→ Worth a short design chat
before the findings track (#31) starts.**

**20. Harness hardening** (`future-tracks/opus4.8_future-tracks_harnesshardening.md`) — **[infra]** adopt **uv**
(`uv.lock`); **pre-commit** (ruff, whitespace, a 600-line size-budget script); CI gates **one at a time**
(`alembic check` + a temp-DB migration test, **pip-audit** + **Dependabot**); **stage** expensive/judgment checks as
dormant drafts in a new **`.claude/staged-harnesses/`** + `REGISTRY.md` with activation triggers (Pyright strict,
tach, coverage, Hypothesis, embedding/vector-drift, bandit); **branch protection** after CI is green; repo
furniture: **SECURITY.md, `.env.example`, CITATION.cff, CHANGELOG, SPDX `AGPL-3.0-or-later`**. Standing rule:
**ratchet — one new blocking gate at a time**; subtraction is the tie-breaker. Changes the dev workflow CC itself
runs under — your sign-off, one gate at a time.

**21. Packaging & distribution (post-V1)** — **[exploratory]** a **Tauri desktop shell** (`app/desktop-shell/`
placeholder); an **OS keychain** for `GOOGLE_API_KEY` (+ future secrets) for a non-technical desktop user; **desktop
distribution + GROBID service ops** (when Track C lands; `ops/` notes). Exploratory.

---

### Longer-horizon future tracks (detailed prompts in `future-tracks/`)

The grand plan: Callosum as a complete, **inspectable** ecosystem for engaging the literature responsibly. Each
track is a *signal/suggestion/retrieval that stays non-authoritative* and must pass the **Principles alignment
gate** before any build. Sequenced *toward*, not queued — the core UX above comes first. See `future-tracks/
README.md` for the index. *(Roughly ordered below from most self-contained to most foundational/most gated — all
well below the cut; each needs its own design + my graduation call.)*

**22. Free-legal full-text acquisition** (Track D) — **[future track — mostly shipped]** the OA lane + 7-source
cascade + wanted list shipped inc 74–76 (relocated to DONE). **Remaining only:** institutional / author-contact
resolvers + the honest "not found" UX polish. **Explicitly excludes paywall circumvention.**

**23. LMM-reporting auditor** (`…_lmmreportingauditor.md`, METHODS, consumer-side) — **[future track]** flags what a
reader should look for in a mixed-model paper (random-effects structure, df method, convergence, REML/ML, ICC, R²,
missing-data sensitivity); **reads reported text only — never runs a model or touches raw data**. A self-contained
sibling of statcheck under the findings subsystem.

**24. Bayesian-statistics auditor** (`…_bayesianauditing.md`, METHODS) — **[future track]** Tier-1 recompute default
Bayes factors for canonical designs (t/F/r + N) + Tier-2 completeness audit; signal-not-verdict, deliberately does
**not** teach "BF>3 = significance". Sibling of statcheck under the findings subsystem.

**25. Citation-equity audit** (`…_citationequitytool.md`, METHODS) — **[future track]** identity-**agnostic**
structural/topical reference-list audit (self-citation, concentration, Global-South under-citation, topical gaps) +
add-only "overlooked work" remediation; descriptive, never a verdict. Gender/identity module **deferred + separately
gated** (A-A no-accusation).

**26. CRediT contributions builder** (`…_creditcontributionsbuilder.md`) — **[future track]** authors × 14-roles
grid (NISO CRediT) → a contributorship statement injected via the Word link (depends on #33/#34); **builder, not
verifier**; credits **tenzing** + library-adds its paper (credit-the-lineage).

**27. Open-science signals — statcheck follow-ons** — **[mostly shipped]** statcheck v1 + library lens + header
chip (inc 95/97/100); the sibling producers **p-curve** (inc 126) + **GRIM/GRIMMER** (inc 127/129); and the
**unified findings-subsystem "N to review" facet** (inc 133) — all shipped + relocated to DONE. **Remaining only:**
more statcheck **test forms** (test-stat `<`/`>` comparisons, results in tables) — a regex-extension increment.

**28. Literature discovery — Feed/Search tabs** (`…_librarypaneltabadditions.md`) — **[SHIPPED inc 182–192 —
relocated to DONE]** the **Search** tab (Crossref + PubMed providers over a `SourceProvider` registry + the
axis-relevance **highlight**, augment-never-filter; metadata-only save) and the **Feed** tab (bioRxiv/medRxiv +
PubMed-keyword + journal-by-ISSN sources, manual or opt-in staleness-gated auto-refresh, with abstracts) both
shipped. **Remaining only:** more Feed sources are a `register()` each (no UI edit); a true background polling daemon
is **deliberately not built** (pull-first). *(This unblocked #18's keyword sourcing on save — still gated on
OpenAlex-concepts/PubMed-MeSH landing.)*

**29. Literature gap-finder** (`…_gapfinder.md`) — **[v1+v2 SHIPPED inc 135/137 — relocated to DONE]** the
**backward gap** (works cited by ≥N of your papers; Gaps button + Add/Dismiss; inc 135) and **v2** — the **forward
gap** (works that cite ≥N of your papers), **axis-scoped** ranking, and the persistent `gap_candidates` cache
(migration 0019) — all shipped (inc 137). Counts are your-library citing (never a quality rank); coverage stated;
candidates not verdicts; audits PASS. **Remaining only:** **followed-authors** as a gap source (needs a
followed-authors concept that doesn't exist yet → effectively blocked on that) + external-search discovery beyond
the library (overlaps the discovery track #28).

**30. Highlight-to-suggest / highlight-to-evaluate** (Track C) — **[SP1a SHIPPED, inc 156]** for a draft sentence —
suggest papers to cite + evaluate support/contrast/mention via the NLI spine. Never auto-insert/auto-judge.
**Highest-value novel capability.**
- **SP1a (inc 156) — DONE:** the local **in-library** suggest+evaluate engine + `POST /citations/suggest` contract
  + an in-app **Cite** pane (paste a sentence → ranked cards with stance pill + verbatim quote + match + Open
  source region + Copy BibTeX). Fully local, no egress. See `INCREMENT-156-NOTES.md`.
- **SP1b (inc 157) — DONE:** the **LibreOffice "Suggest citations" UNO macro** (`adapters/libreoffice/callosum_cite.py`
  `CallosumSuggestCitations`) on the SP1a contract — select a sentence → suggest (pick-list: stance + quote +
  match) → **Insert** the chosen cite via the inc-108 flow. Client-side only; verified by the headless UNO
  round-trip (SELFTEST OK). See `INCREMENT-157-NOTES.md`.
- **Formatted "Cite as…" (inc 159) — DONE:** the in-app Cite pane gained a style picker + a per-card formatted
  **Cite** button (inc-106 render engine), beside the BibTeX copy — the persona's deadline-writer ask.
- **NEXT (big):** **SP2 / Stage-3 — beyond-library discovery** (below).
- **SP2 / Stage-3 — beyond-library suggest:** OpenAlex `related_works` / co-citation + Semantic-Scholar
  recommendations, each candidate carrying an **explainable reason** ("shares N refs", "co-cited with X"); this is
  where the bias-amplification mitigation lives (surface the reason; never rank by citation count). Trips the audit
  + Principles gates (new external fetch / discovery signal).
- **Stage-4 — section-scoping:** constrain candidates to a manuscript section's working bibliography (needs GROBID
  section awareness + the plugin). Last.
- **UX backlog (from the inc-156 experience pass):** an accordion entry signpost for the Cite section; (the
  `match 1.00`-looks-fake reaction is a seed-data artifact — real cosine varies).

**31. THEORY/METHODS panes + findings subsystem** (`…_theorymethods.md`) — **[mostly SHIPPED — relocated to DONE]**
the accordion shell (inc 121), the FACT-vs-candidate findings model (inc 130), the **first producer = retraction**
(inc 131 Crossref/OpenAlex + inc 132 the Retraction Watch DB mirror), the statcheck **candidate** findings + the
unified **"N to review"** facet (inc 133), and the retraction **on-import auto-check + RW staleness nudge** (inc 134)
all shipped. **on-import retraction-check extended to the remaining DOI-bearing routes — ✅ SHIPPED inc 224**
(OA-acquire job + per-paper re-resolve + fill-metadata; scan + citation-import were wired inc 134). The **Zotero
import hook is moot** — `import_zotero_library` has no API route (harness/tests only), so there's no caller to
hook. **Remaining only:** an automatic **cadence** refresh of the RW DB (manual + the staleness nudge is v1); a
later consolidation folding the statcheck signal chip into the unified facet (coexist is the deliberate v1).
(p-curve/GRIM are collection/per-value → they don't emit per-paper candidates, by design.) **Cross-cut:** system
FACTs (`RETRACTED`) filterable via the inc-71 tag mechanism (see #19).

**32. THEORY/METHODS module pool** (`…_theorymethodsextension.md`) — **[future track]** additional principle-aligned
panel-module candidates; depends on the findings subsystem + module registry (#31).

**33. Citation & bibliography engine** (`…_citationbibliographyengine.md`) — **[future track]** the reference-manager
**spine**. **Phase 1 shipped inc 106** — **citeproc-js** rendered backend-side via a Node sidecar
(`app/backend/citations/`) over bundled CSL styles, surfaced **in-app** (Details "Cite as …" + a bulk
formatted-bibliography download); formatted styles (APA/MLA/Chicago/IEEE/Nature/Harvard); credit in
`THIRD-PARTY-NOTICES.md`; no egress. **Phase 2 shipped inc 107** — the **position-aware document-render** layer
(`POST /citations/render-document`, `render_document` / `rebuildProcessorState`): renders a document's **ordered
citation clusters** with numeric renumbering + author-date disambiguation; self-contained (renders from passed
CSL-JSON, no library lookup); the contract every adapter calls. **The first adapter — LibreOffice (UNO) — shipped
inc 108** (`adapters/libreoffice/`): the target-agnostic field abstraction
(`{itemKeys, cslJsonPayload, renderedText, orderIndex}`) realized as ReferenceMarks carrying CSL-JSON (Zotero
`CSL_CITATION` pattern), full-document-order scan, and a flatten mode — the full live-field loop, headless-tested in
a real LibreOffice. **All three adapters now SHIPPED** (relocated to DONE): **LibreOffice .oxt v2** (inc 162 — a
one-click installable extension with the Callosum menu/toolbar + search-to-cite + Suggest); the **Word add-in**
(Office.js, SP1–3, inc 164–166 — live Content-Control fields + Refresh/renumber + Suggest + style-switch + Flatten,
served over local HTTPS same-origin); and the **Google Docs add-on** (Apps Script, inc 168–171 + setup automation
193 — NamedRange + DocumentProperties over a cloudflared bridge with bearer-auth + cite-only ingress). **Deferred
only:** grouped cites / locators / prefixes, note-style footnote management, fetch-on-demand long-tail styles
(consent-gated), Vancouver + more bundled styles, rich-clipboard (italics) copy, a shared subprocess timeout, and a
true Marketplace one-click Docs install (#43).

**34. Word + LibreOffice + Google Docs citation plugins** (Track B) — **[SHIPPED inc 106–108, 162–171 — relocated to
DONE]** cite-while-you-write over CSL-JSON + citeproc, the track-level framing of #33. The CSL engine (106) +
position-aware document render (107) + **all three adapters** shipped: **LibreOffice** (108 macro → 162 one-click
.oxt), **Word** (Office.js SP1–3, 164–166), **Google Docs** (Apps Script + bridge, 168–171, + setup automation 193).
**Never auto-inserts.** Deferred follow-ons under #33.

**35. My Publications — Part 2: impact dashboard** (`…_mypublications.md`) — **[mostly SHIPPED — relocated to DONE]**
Part 1 auto-axis (inc 78); Layer 1 dashboard tab (inc 81); Layer 2 Research domains (inc 83); **the full SP1–SP3
overhaul (inc 117–119)** — dashboard restructure + browsable publication cards, group-by-domain, and **Layer 3
citing articles + per-paper citation counts** (inc 119). **Remaining only:** **Layer 4** grounded prospection
(citation gaps, emerging citing-topics, candidate collaborators — LLM narration over graph data only). The
author-resolution infra also powered the gap-finder (#29).

**36. Meta-analysis extraction workbench** (`…_metaanalysisextractionworkbench.md`, its **own** REVIEW/SYNTHESIS
workspace) — **[future track]** protocol → embedding-screened queue → LLM-drafted **provenance-anchored,
human-verified** extraction → double-coding/IRR → deterministic effect-size conversion → export
(metafor/JASP/RevMan) + audit trail. **Extracts/structures, never pools/models/adjudicates**; LLM is never an
independent coder.

**37. Equity & integrity signals** (`…_equityintegritysignals.md`, HACKADEMIA-derived) — **[future track — most
needs the values layer]** inspectable, **non-accusatory** prestige/credit/attention lenses (overlooked-work /
inverse Matthew, citation credit-concentration, positive self-correction) + 2 principle-fraught forensic candidates
recorded with the **no-index / no-accusation** reframing. Citation-graph-shaped → OpenAlex adapter + findings
subsystem; project as **system-facts tags**. Gated by the Principles gate **and** the A-A **no-accusation** veto —
the track that most needs the values layer.

**38. Research-impact analytics** (`…_researchimpactanalytics.md`) — **[future track — gated]** opt-in, local-first,
**commons**-structured measurement of whether Callosum changes how people research, at **human-subjects-research**
consent discipline. **A.** local usage analytics (zero-egress; instrumentation seam + personal dashboard are the
only near-term, buildable-now parts) vs **B.** cross-user impact signal (far-future, gated). Must pass the
Principles gate **and** the A-A values layer (default-deny; compute-locally / transmit-summaries-only; public field
registry; commons reciprocity; valence rule = *less* time-in-app is the win). Graduation is my explicit call.

*(#39 BYOK / multi-provider LLM — ✅ SHIPPED inc 146–152 (engine + Settings UI + Test-key + nudge + disclaimer +
help-toggle + OS-keychain). Relocated to DONE. Truly deferred: real cloud/Ollama/OS-vault round-trips = your manual
spot-checks.)*

**40. PUBLISHERS — where-to-submit METHODS tool** (`…_publishersmethodstool.md` + its child gate
`…_publisherschoicegate.md`) — **[future track — DO NOT BUILD YET]** at submission time, surface **verifiable,
fully-sourced facts** per candidate journal (OA color, APC + waiver, green route, license, RR/data policy, TOP
factor, open impact, multi-route legitimacy **incl. regional indexes**) under a **user-set open-science weighting** —
the author weighs them; **never a verdict**. Veto: **no composite score, no "predatory" label** (A-A no-accusation),
abstract + preferences **local, never transmitted**, **equity** first-class. The **first-use choice gate** (no
pre-selected default; the weighting one forced choice among peers) is the near-term enhancement. **More controversial
than most** — build only this principled shape; gate through Principles + A-A at graduation. **Do not build yet.**

**41. User-authored modules** (`…_plugins.md`) — **[future track — record only]** **deferred record only** — capture
the extension-point idea + open questions; do NOT build a plugin system until a dedicated design pass.

> **Shared infra these unlock (kept as README-only `integrations/` stubs on purpose):** **OpenAlex** (my-pubs →
> gap-finder → discovery → acquisition; the acquisition slice is built), **Unpaywall** (Track D — superseded by
> OpenAlex in inc 74), **Semantic Scholar** (Track C, discovery), **GROBID** (Track C section-scoping).
> (**mendeley** is NOT track infra — it's *Import coverage*, shipped inc 93.)

---

**42. Rotate the Gemini API keys** (and the CORE key pasted in chat during inc 75) — **[non-code — my manual
action]** they live in **Dropbox version history** / chat history; `.gitignore` keeps all key material out of GitHub
(proven via `git check-ignore`), so this is **not blocking** — but rotation (revoke + reissue, then update `.env`)
is the only way to neutralize copies that exist *outside* git. Deferred by me.

---

**43. Google Workspace Marketplace publishing — true one-click Google Docs add-on install** (`adapters/googledocs/`)
— **[future track — outward-facing; deferred, likely overkill]** the one piece of the Google Docs install that inc
193's quick-tunnel + one-file bundle (`tools/build_gdocs_addon.py` → `callosum-gdocs.gs`) **couldn't** remove: a real
**"Install from the Marketplace"** button, replacing the paste-a-script / authorize-each-doc flow with a published
listing. Requires its own project: a **GCP project**, an **OAuth consent screen + Google verification** (the add-on
already declares its scopes in `appsscript.json`), a **privacy policy** (public URL), and Google's **app review**
(slow turnaround). Big + outward-facing + ongoing-maintenance, and **likely overkill for a local-first single-user
tool** — the add-on still talks only to the user's own cloudflared bridge, so a Marketplace listing buys
*convenience*, not capability. Build only if a true one-click install becomes worth the publishing + review +
maintenance cost. *(inc 193 already shipped the lighter alternative: a Cloudflare Quick Tunnel + a single-paste
`callosum-gdocs.gs` bundle, so the non-Marketplace install is now ~4 steps — see `INCREMENT-193-NOTES.md`.)*

---

## Competitive-benchmark revisions (folded 2026-06-29 from the inbox — full detail + the decided rationale in `future-tracks/opus4.8_future-tracks_benchmarkrevisions.md`)

A competitive-benchmarking pass (Callosum vs Zotero/Mendeley/Paperpile/RefWorks/ReadCube/Citavi/EndNote + Elicit +
the Zotero AI-plugin ecosystem) produced decided dispositions. *Museum before crown jewel:* table-stakes + the
citation-engine spine come first; differentiators after. The **Decisions already made** lines in the source doc are
settled — don't re-litigate. Item codes (A1…D) match that doc.

**A — build-now (autonomous-ish close-outs; ABOVE the cut). The bug/gap fixes here are the priority close-outs:**
- ✅ **A9 — DONE (inc 203): the dormant `contradicted` verification status is live.** The NLI softmax's contradiction
  prob (previously discarded) now yields `contradicted` when it dominates support (≥0.55 & > support); rendered as a
  distinct red "⚠ source disagrees" pill with its quote/page. Signal-not-verdict.
- ✅ **A10 — DONE (inc 204): the axis count-badge filter carries the card's hide-uncertain state.** Clicking the badge
  while 👁 hide is on filters the Library to the same assigned (≥ cutoff) + manual set the card shows (banner: "…·
  assigned only"). *Shown = summarized*; default-off → inc-63 behavior unchanged.
- **[Cliff, queued, non-urgent] Remove the redundant THEORY → Discover accordion placeholder.** The inc-163
  "Coming soon" stub registered THEORY → **Discover** (tabs Beyond library/Feed/Search) in `09_placeholders.jsx`, but
  the real Discover/Search (inc 184) + Feed (inc 188) shipped as **center-pane tabs in the library frame**
  (`30c_frame.jsx`) — the placeholder is now stale/duplicative. Drop the Discover `<ComingSoon>` registration (per the
  inc-163 convention: remove each stub in the increment its real feature lands); the library frame is the right home.
- **A8 — synthesis scope label at summarize** ("summarizing N papers; uncertain excluded"). *Largely shipped by the
  inc-153 coverage readout* — verify + add the uncertain-inclusion statement if missing.
- ✅ **A1 — DONE (inc 208): saved searches.** A named bundle of the existing facets (q/search_field/item_type/axis/
  tag/needs-review/signal/sort), stored in a `saved_searches` table (JSON params, `extra="forbid"`) + recalled from a
  **Saved ▾** header menu (apply / save current / delete). Distinct from an axis (replays GET /papers filters, no new
  query semantics, no score).
- **A5 — color tags ONLY** (a color attribute on tags). **Ratings/flags are declined** (Cliff, 2026-06-29): a
  unidimensional star/rating reduces a paper to one number, erasing the multi-dimensionality that tags capture —
  "I'd give bad science 5 stars for teachability." This coheres with the charter (#7 no opaque composite,
  inspectability over authority): tags are the flexible, orthogonal, inspectable way to judge a paper; a star is a
  reduction. So A5 = **color tags only** — a color attribute on tags (a small fixed, theme-aware palette stored as a
  palette *key*, not arbitrary hex), an uncolored tag keeps its inc-100 provenance style; tags stay provenance-stamped
  + are pure labels (the A7 division). No rating field, ever.
- ✅ **A6 — DONE (inc 206): drag a library card onto a (non-My-Pubs) axis card to add it.** A manual override via
  `POST /axes/{id}/papers`; the axis card shows a dashed-accent drop-invite; My-Pubs (authorship-resolved) is not a
  drop target. Frontend-only (rides the existing endpoint).
- ✅ **A2 — DONE (inc 210): library-wide per-paper citation counts.** A **"Citations ↻"** header control →
  `POST /papers/citation-counts/refresh` (async, OpenAlex `cited_by_count` by DOI → the new `paper_citation_counts`
  table, migration 0027) → a verbatim **"N cited-by"** chip on every card + an explicit opt-in **Most cited** sort.
  Attributed ("per OpenAlex · as of <date>"); never a composite, never a silent rank; no-record → honest "—" (#2/#6/#7).
  Metadata egress (DOI→OpenAlex), NOT the Gemini gate; audit `2026-06-29_citation-counts.md` PASS.
- ✅ **A3 — DONE (inc 209): full-text PDF search.** A SQLite **FTS5** index (`chunks_fts`, external-content + sync
  triggers, migration 0026) over the extracted `chunks.text`, surfaced as a **"Full text (PDFs)"** search scope →
  per-occurrence snippet hits (bolded matches + page + Open-at-page, region precision). `GET /papers/fulltext`;
  sanitized + bound + fail-closed (audit PASS). The exact-string complement to axes/synthesis; no claim/rank/score.
  *(A4 — plain-Markdown annotation export — already shipped inc 144.)*
- ✅ **A7 — DONE (SP1 inc 211 + SP2 inc 212): Curated Axis mode.** An axis populated **by hand** (`kind="curated"`
  + a `cluster_node_papers.position` column, migration 0028): hidden scoring UI, a 📌 cue, **drag-to-reorder** (the ⠿
  grip), drop-to-add, and the bidirectional **freeze** (❄, keyword→curated — snapshot shown members, drop uncertain) /
  warned **convert** (↩, curated→keyword — members kept, order lost). `PUT /axes/{id}/order`; membership stays in
  `cluster_node_papers` so synthesis/A6/merge work unchanged. Design spec `…/specs/2026-06-30-curated-axis-design.md`.
  **Settled (all honored):** umbrella stays "Axis" (never "folder"); manual-survives-switch; flat (no nesting); tags
  already pure labels. **This closes the entire A1–A10 benchmark list.**

**B — deferred (BELOW the cut; queued behind critical functionality):**
- **B1 — read-first / write-gated MCP server** *(spec `…/specs/2026-06-30-mcp-server-design.md`; design home: §B1)* —
  expose Callosum's own MCP server so external agents use the library *through* Callosum (keeping it the provenance
  authority) rather than bypassing it. **SP1 — read-first — DONE (inc 213):** `mcp_server/` (a separate stdio
  deployable mirroring `sync_server/`) with 5 read tools (search / get_paper / full-text / **grounded find_passages
  with quote+page** / format_citation), each one HTTP call to the running app; read-only by construction; no app
  change; audit `2026-06-30_mcp-server.md` PASS. **SP2 — gated writes — TODO** (its own spec + a heavy A4/A-A pass):
  `add_tag` / `add_to_axis` / `save_reference` / `annotate`, each provenance-stamped (`imported_source="ai-agent"`),
  reversible (session undo / soft-delete), and gated (writes-enabled opt-in + per-write confirmation) + an agent
  audit log. The one genuinely-new architectural item; the defensive moat.
- **B2 — collaboration / shared libraries** — opt-in shared libraries on the **now-built account + sync** layer
  (incs 194–202), under the same E2E/consent discipline. **Not declined** — a scope/architecture-weight question.
  *(This is essentially SP4 of the accounts arc.)*
- **B3 — OCR for scanned PDFs** (Tesseract fallback; also helps merge's preprint-vs-scanned case) — rides the
  desktop-shell/packaging track (#21) for the bundling cost.
- **B4 — library-level citation-context classifier (scite analogue)** *(needs a detail doc; design home: §B4)* —
  classify whether a *citing* paper supports/contrasts/mentions a claim across the citation graph, locally + grounded
  in retrieved passages. **Distinct from** the gap-finder (#29, discovery) and Track C (#30, the user's own draft).
  Sequenced **after Track C + A9**. THEORY contract + Auditability gate (#13): signal not verdict, verbatim quotes +
  confidence.
- **B5 — mobile / tablet reading** — a read-only mobile companion built on inc-101 read mode; directional, post-V1.

**C — reserved / declined (recorded; do NOT build or re-propose):** folders/collections hierarchy (**superseded by
axes** — coherent set → axis, arbitrary flat set → tag, "read this week" → needs-review filter; the A7 Curated Axis is
the manual-container path); arbitrary manual **nesting** (declined — when nesting lands it's recursive *semantic*
sub-axes, the My-Pubs subheading prototype); **PDF translation** (out of scope); cloud multi-agent "write my review",
website-bibliography publishing, mind-mapping/Alfred/Todoist, embedded closed models, casual data-from-charts. **(NB:
the source doc's "optional E2E sync — reserved, not planned" line is now SUPERSEDED — opt-in E2E sync shipped incs
197–202; see #15.)**

**D — open proposal (decide later):** a **scratch / ephemeral axis** (non-persisting / auto-expiring) to absorb cheap
throwaway intersection-axes — may already be covered by "just delete the throwaway axis" + the A3 full-text box.
*(Fold into Open proposals; pairs with #16.)*

---

## Shipped — breadcrumbs only (full detail in `INCREMENT-BACKLOG-DONE.md`)

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
- Open-science signals — statcheck v1 + library lens + header chip (95/97/100); **p-curve (126) + GRIM/GRIMMER (127/129) + unified "N to review" facet (133)** *(only "more test forms" remains — see #27)*
- Citation engine Phase 1/2 + LibreOffice adapter — inc 106/107/108 *(Word + Google Docs adapters remain — see #33/#34)*
- **Frontend/UX pass — inc 109–116:** brand-asset source move (109); **PDF page-view options** fit-width/two-up (110, was #2); editable Translators (111, part of #5); multi-paper focus query (112, see #7); button canonicalization (113–115, see #6); synthesis ✕-close + AXES ambient outlines (116). *(Journaled in `RECOVERY-LOG.md`.)*
- **My Publications overhaul SP1–SP3 — inc 117–119:** dashboard restructure + browsable publication cards; group-by-domain; **citing articles + per-paper citation counts** *(only Layer 4 prospection remains — see #35)*
- **QA mechanism** — surface-coverage gate + Codex-exec supervisor + watched inbox (rule #10) — inc 120
- **THEORY/METHODS accordion** on a self-registering module registry (the "next major upgrade") — inc 121; statcheck relocated into a METHODS section — inc 122
- **Synthesis overview fix** — front-matter-aware no-query selection (123) + evidence-traceable Overview (124) + strengthened classifier (125)
- **Findings subsystem** — FACT-vs-candidate store + Review pane (130); retraction producer Crossref/OpenAlex (131) + Retraction Watch DB (132); statcheck candidates + unified facet (133); on-import auto-check + RW staleness nudge (134) *(see #31 for remainder)*
- **Literature gap-finder** — backward gap (135) + watched-folder focus-rescan (136) + **v2** forward/axis-scoped/cached (137) *(only followed-authors remains — see #29)*
- **Auto-select top library paper on load** (138); **accordion tabs-within-a-section** — Tags→AXES tab, METHODS reorder (139)
- **End-user experience pass (rule #11 + EXPERIENCE-PASS.md)** + persona-agent mechanism (140); the build-and-test slate — statcheck path (141), determinate progress (142), durable keyword deletion (143), export highlights (144), discoverable focus query (145)
- **BYOK arc — inc 146–152 (#10 + #39):** Gemini key in Settings (146); Test-key (147); synthesis "AI is off" nudge (148); multi-provider engine Gemini/OpenAI/Anthropic/local (149) + Settings provider UI (150); validation disclaimer + help-assistant toggle (151); OS-keychain storage (152)
- **Track C SP1 (#30) — inc 156–159:** highlight-to-suggest/evaluate engine + `/citations/suggest` + Cite pane (156); LibreOffice Suggest macro (157); formatted "Cite as…" in the Cite pane (159) *(SP2 beyond-library still open)*
- **Contact email / metadata-access in Settings** (158); **library folder watched-by-default** (160); **non-destructive paper merge** (161, part of #17)
- **Word-processor adapters (#33/#34) — inc 162–171, 193:** LibreOffice one-click .oxt v2 (162); Word add-in Office.js SP1–3 (164–166); "Coming soon" placeholders (163); Google Docs SP0 remote-access auth (168) + cloudflared bridge (169) + Apps Script add-on SP2/SP3 (170–171) + setup automation (193)
- **Reading-pane run (#4-adjacent) — inc 175–179:** remembered scroll (175); Notes-panel split + filter/search (176); next/prev-mark nav (177) + hotkeys (179)
- **README front-door draft (#11)** (178); **credit-the-lineage — statcheck slice + shared `.method-credit`** (180, #8) + **dependency NOTICE pass** (181, #8 Lane B)
- **Literature discovery (#28) — inc 182–192:** Search tab (Crossref + PubMed + axis-relevance highlight, 183–186) + Feed tab (bioRxiv/medRxiv + PubMed-keyword + journal-ISSN, 187–192)
- **Accounts arc (#15) — inc 194–202:** Sign in with ORCID SP1 (194) + superuser flag & runbook (195) + email/Google SP2 (196); **opt-in E2E sync SP3** — crypto/changeset (197), `sync_uid` engine + FK + link + natural-key (198–201), reference sync-server + transport + opt-in `/sync/*` (202)
