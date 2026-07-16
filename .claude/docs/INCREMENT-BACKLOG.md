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
which resolves the common write-vs-read contention; **inc 277 added bounded retry for short cache/metadata/reference/funding writes**,
which covers the common transient `database is locked` failures without changing long-job lock behavior).*
**✅ SHORT-WRITE HALF CLOSED inc 272:** the inc-277 `_write` retry was at the wrong granularity (it retries a single
`conn.execute` on the *same still-open transaction*, which keeps its stale snapshot → can't clear a snapshot-upgrade
BUSY). Inc 272 added **transaction-level** retry: `run_write(engine, fn)` (`persistence/sqlite_retry.py` — fresh
connection per attempt → run → commit → retry the whole unit on a lock) wired into the hot short writes
(read/priority, tag color/add/lock/remove, reading-queue add/reorder/remove, axis create), **plus** a backstop
`SqliteWriteRetryMiddleware` that re-runs any *replay-safe* mutating request that raises an uncaught lock error before
sending a response (a denylist excludes job-spawn/external-fetch/secret-write families so a replay can't double-execute).
**◐ LONG-JOB half IN PROGRESS (inc 273 = Increment A):** `commit_each(engine, items, process)` (per-item commits via
`run_write`) + the **scan / watched-rescan** jobs converted — the `scan_library_folder` insert phase commits as its
own unit, then enrich+embed commits **per paper**, so those jobs release the write lock between papers (atomicity is
now per-item — intended; partial progress is usable + the scan is idempotent). Design/plan under `.claude/docs/specs|plans/2026-07-15-long-job-incremental-commits*`.
**✅ A2 DONE (inc 274):** `scan_library_folder` now takes `engine` and ingests each new file in its own `run_write`
transaction (replacing the per-file savepoint), releasing the lock between files during extraction — the **scan
half is now fully per-item** (extraction per file + enrich/embed per paper).
**✅ A3 DONE (inc 275):** the axis-score job pre-embeds candidate papers **one committed transaction per paper**
(`ensure_candidate_embeddings_committing` → `commit_each`), then scores in one short `run_write` txn (`score_axis`'s
`ensure_embeddings` a no-op since `embed_papers` is idempotent) — so **all the auto-running offenders (scan +
watched-rescan + axis-score) are now per-item.** **Remaining:** increments B–D — **B** ingest family (citation
import, bundle import, enrich-batch); **C** method batches (statcheck / retraction / transparency) + citation-counts;
**D** read-heavy (dedup, gap-finder, my-publications refresh/decompose). **Still open (the residual snapshot-upgrade edge):** a SELECT-then-write endpoint (`add_to_queue`,
`add_tag`, `add_to_axis`, … — most write routes) can *still* rarely fail with `sqlite3.OperationalError: database is
locked` when a write collides with a concurrent fetch in the **same instant** — SQLite returns SQLITE_BUSY *immediately*
for a snapshot-upgrade (busy_timeout can't break it). A human essentially never hits it (it needs two near-simultaneous
writes/a write+fetch); only a machine-gun headed driver provokes it. **The textbook cure (`BEGIN IMMEDIATE` for all
transactions) is UNSAFE here**: `_run_scan_job` (+ embed/import/enrich workers) wrap the entire multi-minute job in **one**
`engine.begin()` transaction, so forcing every transaction to grab the write lock up front would block all other requests
for the whole job. So this needs its **own focused increment** — e.g. a transaction-level retry-on-busy scoped to the
short request-path write endpoints, or splitting the long jobs into incremental commits first (then BEGIN IMMEDIATE
becomes safe). Low user-impact; do it as part of a pre-public concurrency pass. **▲ Elevated (QA run 20260702, tiers
1+2 before the credit wall):** the Codex-exec QA driver reproduced this **broadly**, not just as a rare edge — the
axes route (`route_15`: `POST /axes` create → 500, `POST /axes/{id}/score` → job `error` "database is locked while
inserting an axis embedding", then every subsequent axis write [edit/merge/delete/curated] 500 on the same locked
fixture) and the reading-markers route (`route_50`: `POST /papers/{id}/read` → 500). The endpoints themselves are
correct (the read-marker handler is a clean set+commit+return; the axis-score job is the long-held `engine.begin()`
write lock the note above describes). The QA harness's rapid concurrent API calls against the throwaway server (plus a
background embed/score job holding the write transaction) provoke it far more readily than a human. Confirms this is
the highest-value pre-public concurrency item — the fix is still the deferred transaction-splitting / retry-on-busy
increment (the naive `BEGIN IMMEDIATE` is still unsafe for the long jobs), NOT an in-session patch.
**◆ Refined (QA runs 20260702/03 triage, 2026-07-03):** the *dominant* amplifier turned out to be a **QA-harness
fixture-isolation bug**, not the app — `_qa_serve.py` never set `CALLOSUM_LIBRARY_DIR`, so the disposable instance's
launch rescan imported the user's real ~47-PDF library into the throwaway DB (`route_23`: 3 seeded → "50 shown"), and
that heavy background import (extract→embed→enrich, all writes) monopolized the single WAL write slot for the whole
run — starving the foreground UI writes (`route_15` axes, `route_30` `PATCH /papers`, `route_65` workbench cell) into
`database is locked` 500s. **Fixed in-session** (`_qa_serve.py` now points `CALLOSUM_LIBRARY_DIR` at an empty temp
dir; verified count stays 3→3 across a launch rescan) — this should remove most of the QA-amplified reproduction. The
**underlying rare human-concurrency item above stands unchanged** (a real user's write+fetch collision, or a genuine
background score/embed job vs. a foreground write) and is still the deferred transaction-splitting / retry-on-busy
increment. The 20260702/03 re-run (post-fix) will show how much, if anything, still 500s on a clean fixture.

✅ **CLOSED inc 296: QA seed gap: `_seed_library` now sets the `item_type` column.** The two shared seed papers pass
`item_type="article-journal"`, so `GET /papers/item-types` is non-empty and the Library **Type filter** can render in
the QA fixture. A regression test now covers the seed helper's `/papers/item-types` behavior.

**QA runs 20260702/03 — assorted UX findings (triaged 2026-07-03; the write-lock + input-cap + fixture Criticals
were handled separately — see the `database is locked` item above + changes.md).** The independent, real polish
items (the ones NOT downstream of the now-fixed fixture-isolation pollution):
- ✅ **CLOSED inc 282: rejected tag values now show inline validation feedback.** Failed tag add/remove/color
  operations render the existing API message in the Details tag row with `role="alert"`, `aria-invalid`, and
  `aria-describedby`; editing the add input clears the message. Covered by `route_20_tags` and frontend assembly tests.
- ✅ **CLOSED inc 283: statcheck rows show source context inline.** Per-test statcheck results carry bounded
  extracted-text context and render it with the shared evidence quote component, plus page/section provenance where
  available. Covered by `route_33_methods_statcheck`, statcheck tests, and frontend assembly tests.
- ✅ **CLOSED inc 297: library header action row wraps at mobile width.** The Library title/action row now has
  explicit shrink boundaries and word-wrapping action controls, so Add / saved-search / signal chips remain reachable
  in narrow panes without horizontal overflow. Covered by `route_23_citation_counts` and frontend assembly tests.
- The remaining Medium/Low from `route_24/27/30/32` are **held for re-triage against the post-fix re-run** — several
  read as downstream of the fixture pollution (broken/duplicate seed papers, the detail-pane 500 cascade), so they
  may not reproduce on a clean fixture; don't file ghosts.

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
([design]):** ~~(b) a "Check statistics" entry on the paper itself~~ — ✅ **DECLINED 2026-07-06** (rely on the
inc-141 "⚠ N flagged" chip→section path, which already routes the citer to the per-paper check; a Details/card
entry re-clutters what inc-122 deliberately cleaned); **(e)** the "⚠ flagged" (signal) vs "📋 to review"
(work-state) duality — clarify/collapse for the "what's wrong with these numbers" use case (inc-133 made them
coexist on purpose).

*(#1 brand-assets investigation — ✅ resolved/non-issue: no `.webp` assets exist, and `inline_brand_assets.py` reads
`.claude/media/` correctly [inc 109 moved the source]; the "silent no-op" was a stale pre-inc-109 sandbox note.
#2 PDF page-view options [fit-width / two-up] — ✅ SHIPPED inc 110. Both relocated to DONE.)*

**45. Watched-rescan write-lock hardening + content-hash dedup** — ✅ **CLOSED 2026-07-15 (already implemented; verified during a review pick-up):** both halves are in place and tested. **(a) single-flight guard** — `_start_scan_family_job` (`routers/library.py`) serializes the whole scan/rescan family via `app.state.library_scan_singleflight_lock` + `active_library_scan_job_id`: a concurrent `POST /library/scan` **or** `/library/watched/rescan` returns the *active* job (`_SCAN_ALREADY_RUNNING_DETAIL`) instead of starting a second self-contending writer (test `test_watched_folders.py` asserts "already running"). **(b) content-hash dedup** — `scan_library_folder` builds `existing_by_checksum` over **all** attachments (any source/provenance) and skips files whose `file_sha256` already exists (`matched_by: "checksum"`), so foreign-provenance rows aren't re-imported as duplicate scaffolds (test `test_library_scan.py` asserts `matched_by == "checksum"`). Cross-process (two servers on one SQLite file) is out of scope of the in-process lock but covered by the inc-219 WAL + `busy_timeout`; the deeper request-path SELECT-then-write retry remains its own deferred pre-public concurrency increment. The non-code Dropbox-`.local/` relocation note below still stands. _Original write-up follows for history:_
Original: surfaced 2026-07-02
diagnosing a live "library repopulated + metadata won't fetch" report. Root cause was a DB-selection footgun (a
shell without `CALLOSUM_DB_URL` fell back to the thin validation-harness DB), but it exposed two real latent bugs
in the inc-160 watched-rescan: **(a)** concurrent `POST /library/watched/rescan` background jobs writing to SQLite
self-contend → a cascade of `sqlite3.OperationalError: database is locked` on `INSERT INTO papers` /
`external_api_cache` (enrichment *fetches* fine — Crossref 200s — but the *persist* fails, so metadata never lands).
Fix: **serialize rescans** (a single-flight guard so only one runs at a time) and/or set SQLite `busy_timeout` +
WAL so writers wait instead of erroring. **(b)** the rescan dedups by library source-path, so a DB whose rows came
from a *different* provenance (the harness) gets **duplicate scaffold rows** re-imported every launch → the
"repopulated" appearance + `UNIQUE constraint failed: papers.doi` on enrich. Fix: **dedup by content hash** so
foreign-provenance rows are recognized. Neither threatens a properly-scanned library; both only bit when pointed at
the wrong DB — but the lock hardening (a) is a general robustness win (two servers on one SQLite file, big imports).
_Also flag (non-code): the `.local/` SQLite DBs live inside the synced Dropbox folder — worsens lock contention +
syncs a 280 MB binary constantly; relocating `.local/` out of Dropbox is the healthier fix (needs Cliff's call)._

**3. Protect imported/system tags from silent clobber** — **inc 143 (Librarian pass) shipped the core:** deleting
an imported `keyword:*` tag is now **durable** (a per-paper `suppressed_paper_tags` set, migration 0020 — re-resolve /
backfill no longer silently re-adds a removed keyword; re-adding it clears the suppression). **inc 174** shipped the
**confirm before 🔎 re-resolve overwrites hand-edited metadata** (a `window.confirm` guard when
`imported_source == "user-edited"`). **Remaining:** ~~a tag's source as an always-on label/icon~~ — ✅ **DECLINED
2026-07-06** (kept **aesthetic-only** per inc-100: muted styling + tooltip + the All/Yours/Keywords filter already
convey provenance). Additive UX bits are **no longer [decision]-blocked → autonomous-eligible** (small frontend):
✅ **CLOSED inc 298: re-resolve now reports displayed metadata/tag changes inline**; ✅ **CLOSED inc 299:
per-paper tag locks protect a tag link from accidental removal until unlocked.** *(See **#9** for the full
tag-provenance context.)*

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

*(**#6** `.btn-*` divergent-button migration — ✅ **DECLINED 2026-07-06** (maintainer decision pass): the divergent
ghost/icon buttons stay **documented exceptions** per inc-86; new CSS already follows the canonical `.btn-*` rules.
Relocated to DONE. The `.axis-danger` amber→red reconcile + the radius-scale tidy fold into the next CSS-heavy
increment opportunistically — not a migration sweep.)*

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

**12. Critical-review supplement (multi-paper)** — **[gated — on its own design; the #13 bar is now RATIFIED]** a
stronger, more opinionated generation mode (own endpoint/mode, egress gate, security audit) that critically reviews
the selected paper(s). **Must meet the now-ratified auditability standard (#13)** before it ships — it
judges/critiques rather than grounds.

**13. AI-assist auditability standard — ✅ RATIFIED 2026-07-06** (maintainer decision pass). The inspectability bar
any stronger AI-assist feature (critical-review #12; Tracks B/C highlight-suggest / evaluate) must meet before it
ships: **every AI judgment/suggestion carries (a) its retrieved source span(s), (b) an inspectable stance label
(local NLI), (c) a verbatim quote, and (d) a visible confidence — with the evidence one low-friction click away
(never a step the user skips); a feature that cannot meet the bar states explicitly where + why it falls short**
(silence ≠ certificate). Reuses the existing local citation-verification layer (invariants #1/#4). **Durable home:**
`.claude/architectural-decisions-log.md` (+ a `PRINCIPLES.md` THEORY cross-ref). **Effect:** un-gates #12 + Tracks
B/C to be *planned* against this bar — each still needs its own design + graduation call; ratifying the bar removes
only the "bar undefined" block.

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

**16. Undo / soft-delete buffer (beyond Trash)** — **[SHIPPED for merge, inc 265]** the specific "merge is
destructive + irreversible" gap is closed: the inc-161 merge is now **fully reversible** via **Un-merge** (a
`merge_operations` reversal snapshot + `paper_unmerge`; the survivor's Details shows "Merged from … — Un-merge").
See `INCREMENT-265-NOTES.md`. (A *general* undo buffer beyond merge — e.g. undo an edit/delete — remains a future
possibility, but the load-bearing case that motivated #16 is done.)

**17. Library merge (manual; free-form, deliberately NOT gated behind dedup)** — **[SHIPPED — merge inc 161,
reversibility inc 265]** manual N-way merge of library entries into one canonical record (field-by-field metadata
pick + re-point PDFs/chunks/embeddings/annotations/tags/axis-assignments + a "Merged from…" lineage note), launched
from a duplicate group OR the library bulk bar, **not** gated behind dedup (Zotero/Mendeley parity — auto-detection
misses true duplicates like a preprint-vs-published pair). `metadata/paper_merge.py` + `duplicates.py` +
`38_merge.jsx`; made reversible in inc 265 (#16). Any *further* merge UX polish (e.g. an inline post-merge Undo
toast) is a nicety, backlogged.

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

**23. LMM-reporting auditor** (`…_lmmreportingauditor.md`, METHODS, consumer-side) — **[SHIPPED inc 247 — all 7
checks + literacy explainers; deferrals below]** the METHODS "Mixed-model reporting" panel flags what a reader should
look for in a mixed-model paper (random-effects structure, df method, convergence, REML/ML, ICC, R², missing-data
sensitivity); **reads reported text only — never runs a model or touches raw data**. `methods/lmm.py` +
`GET /papers/{id}/lmm` + `08f_methods_lmm.jsx`; FLAG-not-ADJUDICATE (present/not-found/n-a, no score/verdict);
precondition-scoped (ICC + missing-data n/a when not applicable); grounded cited recommendations + add-to-library.
- **Deferred — CROSS-METHOD (experience passes, inc 247 LMM + inc 249 meta-analysis; consolidate as one item across
  the auto-detected-method METHODS auditors — LMM / meta-analysis / and by extension statcheck / bayes):**
  (F1) an **on-paper "report card" chip** — a "runs an LMM · report card →" / "reports a meta-analysis · report card →"
  library-card signal mirroring statcheck's inc-141 chip→section path, so a citer reaches the panel in the moment
  without knowing it exists (each auto-detects for free — `_LMM` / `_META` — so the same gate can drive a chip; the
  auditors' shared reception gap; a bigger, design-gated follow-up). (F4) let each audit **persist as a candidate** in
  the findings/review store (inc 130) so the judgment survives closing the pane + feeds the library-wide review queue
  (cross-method triage). (F2, inc 249) suppress the **methods-credit footer** on the explicit "not applicable to this
  paper" state (a `MetaSection`/`LmmSection`/statcheck/bayes footer renders even on a non-applicable paper, reading as
  if the audit found methods) — a small state-lift, uniform across the four siblings.
- **Deferred (SP2, no data source / bigger design):** LLM-assisted detection for fuzzier reporting (consent-gated);
  a per-check precision/recall pass on real mixed-model papers.

**24. Bayesian-statistics auditor** (`…_bayesianauditing.md`, METHODS) — **[FULLY DONE — SP1 inc 241 + SP2 inc 242 +
SP3 inc 243 + SP4 inc 244]** the **Tier-1 deterministic recompute** (SP1): default **JZS** t-test BF (Rouder et al.
2009) for inline `t(df) = …, BF10 = …` via `methods/bayes.py::jzs_bf10` (scipy quadrature; verified vs pingouin) + the
**Tier-2 completeness checklist** (SP2): presence/absence of the prior + convergence diagnostics + sensitivity
analysis (BARG/WAMBS/JASP) + a coherence flag on a breaching *reported* diagnostic (R-hat > 1.1 / ESS < 400 /
divergences) + the **correlation recompute** (SP3): default **correlation** BF (Ly et al. 2016) for inline `r(df) = …,
BF10 = …` via `corr_bf10` (exact ₂F₁ closed form; **verified exactly vs pingouin `bayesfactor_pearson`**) + **Tier-3
advisory prompts** (SP4, inc 244): conservatively-gated, clearly-demarcated (neutral, not amber; "requires expert
judgment") credible-vs-confidence + BF-direction prompts (`_advisory_notes`) — never flags/verdicts. All on `GET
/papers/{id}/bayes` + the METHODS panel `08d_methods_bayes.jsx`. Signal-not-verdict, no score, no accusation; the
checklist runs only on a Bayesian paper, convergence is n/a for closed-form BFs, "not found" = not-detected-in-text,
thresholds cited as conventions, advisories are exploratory prompts. Local, no LLM/egress/migration/dependency; audits
PASS; credited (Rouder + Ly + BayesFactor + BARG/WAMBS/JASP). Deliberately does **not** teach "BF>3 = significance".
**ANOVA / regression BFs — DEFERRED as a documented finding (inc 243 audit addendum 2):** the default ANOVA/regression
BF is **not faithfully recomputable from F+df+N alone** (design-dependent) and has **no in-env anchor**; a candidate
failed the J=2 → two-sample-t reduction check, so shipping it would fabricate false flags — declined per rule #2 + the
A-A veto until a trusted anchor (R BayesFactor / a validated Rouder-2012 quadrature) exists. Sibling of statcheck.

**25. Citation concentration** (`…_citationequitytool.md`, METHODS) — **[DONE — SP1 inc 227 + SP2 inc 228 +
values rework inc 229]** the **structural** reference-list audit (self-citation, Matthew concentration, venue +
institutional concentration) shown against a field-topic sample (SP1) + the topical **overlooked-work remediation**
(SP2 — **Find overlooked work** surfaces topically-relevant omitted papers ranked by a local SPECTER cosine,
add-only/no-quota/metadata-only). **Inc-229 values rework (maintainer + CC):** removed the **geography ("Global
South") signal** + all gender framing — *rejected on principle*, because sorting cited authors into a group to measure
bias reifies the category (visibility-by-category == erasure-by-category). Renamed **"Citation concentration."** It
now measures only the shape of WHAT is cited (deference to concentrated power/prestige), never WHO wrote it; enforced
by a static guard test. Descriptive, never a verdict; a ⚠ low-coverage flag (signal over <50% of refs). **Open
follow-up (deferred, not blocking):** a real *field* self-citation baseline (needs per-field-paper reference fetches —
a cost/design call).

**26. CRediT contributions builder** (`…_creditcontributionsbuilder.md`) — **[v1 shipped inc 261]** the
**CRediTer** authoring aid: an authors × 14-NISO-role grid → a contributorship statement in both by-author /
by-role layouts, in the **THEORY** authoring cluster. Deterministic/local/no-egress/no-LLM; **builder, not
verifier** (an AST-pinned no-inference boundary); credits **tenzing** + the CRediT/NISO taxonomy with a one-click
library-add (credit-the-lineage). Output = copy-to-clipboard (universal, the **primary** button) **+ native
LibreOffice injection** (the `/credit/pending` hand-off → **Callosum → Insert CRediT statement**). **Remaining
(deferred):** ORCID/affiliation fields + a machine-readable **JATS/XML** export; **Word** (fast-follow) + **Google
Docs** (blocked on widening the cloudflared cite-endpoint allowlist — security-gated) native injection; Beck &
Christensen contributorship-representation refinements (pending the user's reference).
**UX follow-ups (inc-261 experience pass — the "deadline author" persona, Dr. Maya Chen):** **(a)** *role presets*
per author (First-author / PI / Collaborator one-click starting bundles the user then edits) to collapse the
14-chip × N-author click grid in the narrow sidebar — the highest-value ask, deferred because presets that
pre-select roles want a deliberate build + a principles beat (they must read as an editable convenience the human
asserts, never callosum *inferring* who did what); **(b)** an **"and" before the last name** in by-role lines
(`… Chen and Lee.`) — deferred as debatable (NISO comma-only is also valid; make it an opt-in format flag if
adopted); **(c)** *discoverability* — CRediT statement is item ~5 in the THEORY accordion; consider a jump/link
from "Where to submit" ("Ready to submit? Build your CRediT statement →"). The four cheap findings (Copy made
primary + "Send to LibreOffice" relabel; a by-author layout hint; a persistent staged confirmation that clears on
edit; the credit block reframed "About this tool:" so it doesn't read as manuscript citations) were fixed in inc 261.

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

**36. Meta-analysis** (`…_metaanalysisextractionworkbench.md`) — **[consumer-side reporting auditor SHIPPED inc 249;
producer-side extraction workbench is the deferred remainder]**
- **SHIPPED (inc 249) — the consumer-side reporting auditor:** a METHODS "Meta-analysis reporting" panel (the
  statcheck/LMM sibling) that reads a *published* meta-analysis's extracted text and flags whether it *reports* 7 key
  choices (effect-size metric, model, heterogeneity I²/τ²/Q, publication bias, sensitivity/influence, study count
  k+participants, search & selection) — present/not-found/not-applicable, evidence + cited recommendation + explainer.
  `methods/metaanalysis.py` + `GET /papers/{id}/meta-analysis` + `08g_methods_metaanalysis.jsx`; FLAG-not-ADJUDICATE
  (no score/verdict; **never pools/models/re-computes** — structural + test-pinned); precondition-scoped (search = n/a
  for a within-study mini-meta); local/no-egress/no-LLM. Experience-pass deferrals folded into #23's cross-method
  chip/persist/credit-footer item.
- **DEFERRED → the producer-side extraction workbench** (its **own** REVIEW/SYNTHESIS workspace, a bigger future
  track): protocol → embedding-screened queue → LLM-drafted **provenance-anchored, human-verified** extraction →
  double-coding/IRR → deterministic effect-size conversion → export (metafor/JASP/RevMan) + audit trail.
  **Extracts/structures, never pools/models/adjudicates**; LLM is never an independent coder. Its own spec +
  workspace + heavy Principles/A-A pass (the maintainer chose "reporting auditor now, workbench next").
- **✅ SP1 — SHIPPED inc 252 (the deterministic effect-size converter):** the workbench's first buildable slice, sliced
  converter-first (AskUserQuestion). `methods/effectsize.py` (a `Conversion` dataclass + SMD→Hedges' g / SD-derivation /
  correlation→Fisher's z / binary 2×2→log OR/RR/RD [+ Haldane zero-cell] / cross-metric d↔r, log OR→d + a `convert`
  dispatch) + `POST /methods/effect-size` (sync, mirrors `/methods/grim`) + `08i_methods_effectsize.jsx`. Hand-enter one
  study's stats → a common metric + variance + a 95% CI, via **cited formulas**, with the **path shown**, the
  **formula source cited**, and every **derivation/continuity/approximation choice recorded** + a **copy value + variance**
  extract button. **The convert-never-synthesize boundary is structural + test-pinned** (`test_no_aggregation_code_path` —
  no pooling/heterogeneity/meta-regression/bias-inference def, no aggregation import; the endpoint takes one study). No
  score/opaque-number (#7); cross-metric flagged as an approximation. Verified against Borenstein-et-al.-(2009) formula
  anchors. Local/no-egress/no-LLM/no-migration/no-dependency. pytest +12; QA 183/183 API + 828/828 FE, 0 uncovered;
  audit PASS; headed-verified. **Filed follow-up:** a copy-full-row / accumulating-dataset affordance once SP2's dataset
  exists (SP1's copy button is a per-study bridge). **NEXT within #36 = SP2:** the extraction **workspace** (a
  REVIEW/SYNTHESIS surface + a user-defined included set + an extraction template + **LLM-drafted, provenance-anchored,
  human-verified** extraction [the egress + heavy-A-A slice] + a persisted dataset that feeds *this* converter + export
  to metafor/JASP/RevMan + an audit log); further deferred: screening/PRISMA, double-coding/IRR, RoB instruments, figure
  extraction (point at WebPlotDigitizer, don't build).
- **✅ SP2a — SHIPPED inc 253 (the grid) + inc 255 (select-in-PDF capture):** the stateful **Extract** workspace —
  `ma_projects`/`ma_rows`/`ma_cells` (migration 0033) + `workbench_repo` + `/workbench/*` router + `45_workbench.jsx`.
  Projects (a design + template) → rows (one effect, optionally paper-linked) → provenance-anchored cells (hand-typed
  **or** captured by selecting the number in the PDF → verbatim+editable, exact-bbox anchor) → per-row **Convert** hook.
- **✅ SP2b — SHIPPED inc 258 (the dataset loop + stat-package exports):** **Convert all** (the audited per-study
  converter over every row; honest "k of N converted"; incomplete rows named, never fabricated) + native exports —
  **metafor** (per-study yi/vi + moderators; `rma()`-ready) / **RevMan** (raw per-group data per design) / generic CSV /
  provenance JSON. `workbench_export.py`; number-aware `_csv_safe`. Convert-never-synthesize boundary preserved
  (no pooling, no summary row). **Experience-pass deferrals (inc 258, persona = deadline meta-analyst):**
  (1) **surface the converter's caveats/choices/CI on the converted cell** (an amber marker or tooltip) — Convert-all
  paints N green `metric = value` cells silent about continuity corrections (Haldane +0.5) + approximation flags that
  live only in the provenance JSON; **principle-relevant** (every claim carries its evidence / silence-is-not-a-
  certificate). (2) **field-level "why this row failed"** + distinguish blank-vs-invalid, and specifically catch the
  **comma-decimal** input trap (`float("12,5")` throws → a filled-looking cell silently won't convert). (3) optional
  page/quote columns in the *generic* CSV for supplement tables (keep metafor/RevMan clean); a **0-converted export
  guard**; promote **Convert all →** to a real button (DESIGN-gated).
- **✅ SP2b assisted-extraction funnel — SHIPPED inc 259 (AI proposes, the human filters):** an **egress-gated**
  assistant (**Draft from PDF**) that *proposes* values for a row's empty **structured** cells as **candidates**
  (`ma_proposals`, migration 0034; `ma_cells.origin`) — the LLM reads the paper's page-tagged text and returns
  `{value, quote, page}`; the app **anchors each locally** (`workbench_assist.anchor_proposal`/`locate_quote` →
  exact/region/unanchored, never the model's claim) and renders **amber candidates** with the verbatim quote + an
  honest anchor badge. Accept / edit-then-accept / reject **per cell**; nothing enters `ma_cells`/Convert/exports until
  accept (fact ≠ candidate isolation; `origin='assisted'` in provenance). Rides the existing `EgressGatedExtractionAssistant`
  (403 with AI off; loopback = no egress); `parse_proposals` is defensive; text capped 50k. `routers/workbench.py` +
  `integrations/gemini/extraction_assistant.py` + `46_workbench_propose.jsx`. Audit PASS; QA route 65 extended; full
  Principles/A-A pass (fact-vs-candidate, egress, the-human-is-the-filter). **Next escalations within the funnel:**
  (1) **batch "Draft all un-filled rows"** — one confirm, the SAME per-cell verify gate on every candidate (never a
  bulk auto-accept); (2) **retrieval-narrowed text** — embed the field labels → send only the top-k relevant chunks
  (cheaper + more accurate than the 50k head); (3) **double-coding / IRR** stays **human-only** (the track's
  no-independent-coder veto — the AI is a funnel, never a second rater). **Experience-pass deferrals (inc 259, persona
  = deadline meta-analyst; the cheap edit-flow fixes were folded into the increment):** (a) the candidate anchor badge
  says **"region"** (app vocabulary) — a first-timer may not parse it; consider a self-explanatory gloss without
  drifting the exact/region/null contract; (b) ✅ **FIXED (post-review, inc 259):** the **unanchored** "Open at anchor"
  now opens at `precision:null` (scroll only — no rect and no "region" note that would imply we located it), so it no
  longer presents the AI's guessed page as a found region; the page shown is still the model's claim (see post-review
  minor below); (c) candidates are **amber-only** with no text label — add a small "AI proposal" cue so
  fact-vs-candidate isn't color-alone (accessibility). **Post-review minors (final whole-branch review, backlogged):**
  (i) `workbench_assist._value_in_quote` uses a **substring** test (`"5" in "0.15"` → a spurious *exact* anchor) —
  tighten to a numeric/token match; (ii) an **unanchored** candidate still stores the model's **`claimed_page`**
  (unverified) — consider dropping it or marking it unverified in the badge (pairs with (a)/(c)). **Known UX
  limitation:** a **custom loopback** provider is conservatively treated as needing egress consent for the Draft
  button's enabled state (the `aiReady` gate keys on provider==local or egress+key), so a `127.0.0.1` custom endpoint
  won't enable Draft until AI features are on — safe-by-default, slightly over-conservative.

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
`…_publisherschoicegate.md`) — **[SP1 COMPLETE — SP1a inc 245 + SP1b inc 246; deferred signals remain]** at submission time, surface
**verifiable, fully-sourced facts** per candidate journal (OA color, APC + waiver, green route, license, RR/data
policy, TOP factor, open impact, multi-route legitimacy **incl. regional indexes**) under a **user-set open-science
weighting** — the author weighs them; **never a verdict**. Veto: **no composite score, no "predatory" label** (A-A
no-accusation), abstract + preferences **local, never transmitted**, **equity** first-class.
- **SP1a — the backend engine + endpoint (✅ SHIPPED inc 245):** two clients (`integrations/openalex/sources.py` +
  `integrations/doaj/journals.py`) + a pure `methods/publishers.py` + async `POST/GET /methods/publishers/run`. From
  an abstract → a topic-seeded candidate pool (abstract embedded **locally**, never transmitted) → uniform factual
  profiles ranked by fit + an optional open-science `weighting` (request param). Vetoes structural + test-pinned (no
  composite score, no "predatory", every candidate listed incl. closed, elevate-don't-denigrate). Audit + QA
  `route_60` PASS. Legitimacy SP1 subset = DOAJ inclusion + Seal; the rest deferred + named honestly.
- **SP1b — the panel + the weighting + the first-use choice gate (✅ SHIPPED inc 246):** `08e_methods_publishers.jsx`
  (paper-picker OR abstract+subject → the SP1a run → profile cards, each fact links to its source) + a visible
  **open-science weighting** control (always shows its state inline via the output thumb; adjust + re-run) + the
  **first-use no-pre-selected-default choice gate** (local `app_settings` `publisher_weighting` + `publisher_breadth`,
  never transmitted; the weighting AND the breadth are forced **together** so the weighting isn't the lone choice;
  PUBLISHERS-scoped; fires once). No SP1a endpoint change (the panel reads `/settings` + maps breadth→top_k).
  Headed-verified; help corpus "Where to submit"; audit addendum (prefs never transmitted).
- **Deferred within #40 (no data source yet):** green-route / TOP-factor / regional-index (AJOL/SciELO/Redalyc/
  Latindex) legitimacy signals; user exclusion/filtering; thumb auditability; a real field self-citation baseline.

**41. User-authored modules** (`…_plugins.md`) — **[future track — record only]** **deferred record only** — capture
the extension-point idea + open questions; do NOT build a plugin system until a dedicated design pass.

**44. Transparency & registration alignment — the Lakens-catalog integration** (`chatgpt5.5_future-tracks_integratinglakens.md`,
folded from the inbox 2026-07-02) — **[future track; increment 1 buildable-now, later increments gated]** a survey of
Daniël Lakens' automated-review tool catalog (the same one our statcheck/GRIM/Bayesian/meta credits cite) + a concrete
5-increment integration order. Its thesis is right: **callosum has a strong statistical-auditing spine; the biggest
missing category is transparency & registration alignment** — *does the paper make its open-science artifacts visible,
and how do they line up with the published report?* Gated by the Principles gate **and** the A-A **no-accusation veto**
(this track lives right on it). The concrete order:
- **✅ Increment 1 — SHIPPED inc 250:** `methods/transparency.py` + `GET /papers/{id}/transparency` +
  `08h_methods_transparency.jsx` — a consumer-side METHODS **"Transparency signals"** auditor (the exact statcheck/LMM/
  meta pattern) over existing chunks: 7 ODDPub/rtransparent/Nosek-derived detectors (data availability, code/software
  availability, conflict-of-interest, funding, protocol/trial registration, preregistration, "available upon request")
  → **present / not-found / not-applicable**, each with the matched sentence (region page-open), an explainer, and the
  in-context `basis`. NO gate (every paper gets the 7 checks). "not found" = "not detected in the extracted text — check
  the paper", never "concealed"/"absent" (silence≠certificate, test-pinned `test_no_accusatory_language`); signal-not-
  verdict; no composite "transparency score". Local, regex, no new dependency. Audit PASS; Principles+A-A aligned; QA
  route_63; headed-verified.
- **✅ Increment 1b — SHIPPED inc 251 (persist transparency):** `methods/transparency_findings.py` (present-only FACTs +
  per-disclosure status) + `signals_repo.store_transparency_status`/`count_transparency_review` + `POST/GET
  /methods/transparency/run` + `/summary` + the `repository.SIGNAL_FILTERS` generalization to `(type, source|None,
  status)` with **7 transparency review queues** + the `08h` **Check all papers** batch + a **🔎 N · open data not
  detected** Library-header chip (indigo work-queue). A batch persists each paper's *detected-present* disclosures as
  findings-FACTs (inc 130 — render as Review-pane marks) + every disclosure's check status (inc 97), powering the review
  queues. **The A-A no-accusation boundary is structural + test-pinned:** present-only FACTs (an absence is NEVER a
  fact); review-queue-not-verdict wording ("not detected — go look", never "hides data"); no score/rank; precondition-
  scoped filters (registration n/a excluded, upon-request is the present case). No migration; local/no-egress/no-LLM/no-
  dependency. pytest +8; QA 182/182 API + 814/814 FE, 0 uncovered; audit PASS; headed-verified. This delivered the
  inc-250 experience-pass **F4** (library surfacing + a review queue). **Still deferred within 1b:** the **#19
  tags→system-facts** thread (read-only `system:transparency:*` tags — the tag-provenance model is an open design
  problem); + the standing cross-method **F1** on-paper report-card chip (the panel batch trigger is still METHODS-
  buried) + **F2** credit-footer-on-n/a, both filed to #23. Credit-the-lineage in NOTICES: ODDPub (Riedel et al. 2020),
  rtransparent (Serghiou et al. 2021), Nosek et al. (2018).
- **Increment 2 (infra):** **DocumentTextProvider** adapters for JATS/XML, DOCX, HTML (PyMuPDF/Tesseract stay the
  primary PDF path) — unlocks better table/stat extraction + PMC transparency detection + registration comparison.
- **Increment 3 (fraught — gated):** **RegCheck** — a registration↔paper **delta table with source-paired quotes**
  labeled *reported match / possible divergence / not located / ambiguous*, **never "QRP"**, human-verified, behind the
  **auditability gate** (LLM-assisted). An **emergent value + a divergent tension** in A-A terms — needs the unresolved
  "how auditable is auditable enough?" question answered before build.
- **Increment 4 (overlaps existing):** CRediT builder/extractor → folds into the CRediT track (tenzing builder +
  ContriBOT extractor).
- **Increment 5 (overlaps existing):** extend consistency checks toward a **registry** (DEBIT, table-aware stat
  extraction, more statcheck forms — **#27**; opt-in collection-level **z-curve**, disclosure-table-first + human-verified
  focal-statistic extraction, beside p-curve).
- Overlaps flagged as cross-references, not new work: CRediT (the `creditcontributionsbuilder` track), meta-analysis
  extraction (**#36**), equity/integrity (**#37**), more statcheck forms (**#27**). Not-prioritized (per the doc):
  QuartoReview (manuscript editor, out of scope), coarse (causal-inference-specialized), open_peer_review (study-specific).

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
- ✅ **DONE inc 296: removed the redundant THEORY → Discover accordion placeholder.** `09_placeholders.jsx` retains
  only the explanatory note from inc 205; the real Discover/Search (inc 184) + Feed (inc 188) remain center-pane tabs
  in the library frame (`30c_frame.jsx`). A frontend-assembly regression asserts the stale THEORY registration does
  not return.
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
- **B2 — collaboration / shared libraries** — **[COMPLETE — SP1 inc 234 + SP2 inc 235 + SP3 inc 236]** the file-based,
  copyright-safe slice: a **portable library bundle** — export/import a versioned JSON file carrying metadata + tags +
  annotations + axis definitions **+ syntheses** but **NO PDFs** (`metadata/library_bundle.py`; `POST
  /library/bundle/export` + `POST/GET /library/bundle/import`). No server, no egress; merge additive/non-destructive by
  identity; the recipient re-acquires their own PDFs. **SP2** relays syntheses as the sender's assessment (region
  precision, a `summaries.imported_json` display blob, never re-verified / never in the verification tables, clearly
  flagged — invariants #1/#4). **SP3** adds **"Re-verify against my library"** (`POST /summaries/{id}/reverify`,
  `summarization/reverify.py`) — re-runs the local verifier over the recipient's chunks + converts the synthesis in
  place to native (no egress, no LLM). Specs `.claude/docs/specs/2026-07-01-library-bundle-{design,syntheses-sp2,
  reverify-sp3}.md`. **Beyond B2 (deferred, own design):** a *live* shared library on the account+sync layer (incs
  194–202) under the E2E/consent discipline — ≈ accounts SP4.
- **B3 — OCR for scanned PDFs** — **[DONE inc 231]** a manual per-paper **"OCR this paper"** action (shown only for
  a PDF with no text layer): local **Tesseract** produces a **searchable PDF** (image + embedded OCR text layer),
  attached as the new primary + extracted through the normal pipeline → the scanned paper becomes searchable +
  embeddable + citable with **exact** highlights + selectable text. No new pip dependency (system binary), no egress.
  *Follow-ups:* bundle Tesseract with the desktop shell (#21); a batch "OCR all scanned"; re-OCR of a partially-texted
  PDF (needs the deferred delete-chunks/vector-cleanup); non-English language packs.
- **B4 — citation-context classifier (scite analogue)** — **[DONE — SP1 inc 232 + SP2 inc 233]** a two-way panel:
  **How it's cited** (incoming — how others cite this paper) ⇄ **How it cites its sources** (outgoing). Both fetch the
  citing sentences from **Semantic Scholar** (which has already linked each in-text citation to its reference — no
  local parsing) + classify each stance **locally** with our NLI (support/contrast/mention). Counts, never a score;
  the sentence is always the evidence; a signal not a verdict; no accusation. Spec
  `.claude/docs/specs/2026-07-01-citation-context-design.md`. **Possible later:** Semantic Scholar intents as a
  supplementary tag; a library-wide most-contested/most-supported facet; report caching.
- **B5 — mobile / tablet reading** — **[COMPLETE — SP1 inc 237 + SP2 inc 238 + SP3 inc 239]** the desktop app is
  **responsive** (single-column + a bottom nav on a phone-width viewport, built on the inc-101 read mode) and reachable
  **read-only** over the cloudflared tunnel: a **`CALLOSUM_READ_ONLY=1` method gate** (403 on every write — the real
  boundary) + a **read-only ingress allowlist** (`adapters/mobile/`, defense in depth) + the bearer token; the app
  **reads clean read-only** — a "Read-only" badge, every write control hidden (Details render as static text; the
  METHODS analysis sections + Discover/Feed tabs drop), and no doomed writes on load (via a `read_only` flag on
  `/health`); and the **PDF reader is phone-native** — fit-width by default, **pinch-to-zoom** (`30f_pdf_gestures.jsx`),
  and a citation jump pulls the reader into view with a one-tap **"← Synthesis"** back pill; and (inc 240) you can
  **highlight by touch** — a long-press selection surfaces the same color-picker pill (via a mobile `selectionchange`
  hook, since `mouseup` doesn't fire on touch), finger-sized. Run a 2nd read-only callosum for the tunnel
  (`tools/run_tunnel.py --mobile`; `adapters/mobile/README.md`). **B1–B5 all done — nothing deferred.**

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
