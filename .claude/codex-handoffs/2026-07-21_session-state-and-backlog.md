# Codex handoff — session state + backlog for the coming week

## Context
Cliff presents callosum at a meeting **one week from today (2026-07-21) — around 2026-07-28**. This session did
two things: (1) drove the LibreOffice adapter's P0 correctness/safety rework (backlog #33/#34) from Phase 0
through Phase 10, then continued into the composer (Phase 5a/5b/5c) — **closing the entire rework**, and (2) ran
a strategic release-readiness review at Cliff's prompt ("what am I missing before the presentation, and beyond
it"). That review's findings are folded in below. This file exists because the session ran long enough to need
a handoff — it's written for whoever picks up next (Codex or a fresh Claude Code session) with **zero assumed
prior context**. (Superseded four earlier revisions of itself: three as the LibreOffice rework kept going past
its first "Phase 5 not started" snapshot, and a fourth after backlog #30 turned out to already be mostly built —
this is the final, accurate version.)

**Repo state: everything below is committed and pushed to `origin/main`** (HEAD `ccad974`). **Increment 332**,
**1345 pytest passing, 1 skipped**. `pytest -n auto -q` and `ruff format/check` are clean; the pre-commit
line-budget hook is clean.

## What shipped this session (don't redo)
- **Backlog #30's LibreOffice wiring + doc-drift cleanup (inc 332)** — see the "#30 correction" entry further
  down for the full story; short version: the feature was already built, only the LibreOffice adapter's Suggest
  macro needed wiring to it, plus several stale docs needed fixing.
- **The entire LibreOffice adapter P0 rework is done — backlog #33/#34, phases 0–10 plus 5a/5b/5c** (all under
  `adapters/libreoffice/`): versioned mark schema, transactional refresh with rollback, backend citeproc
  passthrough (locator/prefix/suffix/suppress-author/author-only), `mark_at_cursor`, delete/merge/split/
  open-in-callosum, a **bounded bibliography** (closes the original verified data-loss bug — a bookmark PAIR,
  never `text.getEnd()`), safe flatten ("Prepare submission copy"), read-only document diagnostics, and the
  real-UNO test harness **committed + cross-platform + running in CI** (`adapters/libreoffice/run_roundtrip.py`,
  `.github/workflows/libreoffice-adapter.yml`, path-scoped + non-blocking — **verified live on three separate
  pushes**, all passing on the first attempt: e.g.
  https://github.com/cliffworkman/callosum/actions/runs/29864362756).
- **The composer** (`adapters/libreoffice/composer.py`, new file) replaces the old one-shot search+single-select
  "Add citation…" flow entirely: **live search-as-you-type** (this codebase's first UNO event listener beyond
  the `.oxt` dispatcher — a real-UNO spike confirmed a programmatic `setText()` reliably fires
  `XTextListener.textChanged` and a synchronous local search-refresh has no reentrancy problem, ~26–37ms, so no
  debounce timer was needed), a **multi-item assembly** with manual reordering (Move ↑/↓), per-item
  **Options…** (locator — the exact 19-value CSL vocabulary — prefix, suffix, suppress-author, author-only,
  with suppress-author/author-only kept mutually exclusive in the UI), a **real rendered preview** (always a
  genuine round-trip through `POST /citations/render-document`, never simulated), and **Edit Citation**
  (reopens the same composer pre-populated from an existing citation via `mark_at_cursor`, saving back to the
  SAME citation identity — never mints a new rnd). New backend `insert_citation_items`/`edit_citation_items` in
  `callosum_cite.py` power Insert and Edit respectively, sharing a `_build_records` helper.
- **Deliberately NOT built**: a "restore style-defined sort" action. CSL/citeproc-js has no per-request override
  for a style's own `<citation><sort>` — it's baked into the style itself. Building one would be a no-op for 4
  of the 7 bundled styles (apa/ieee/nature/harvard-cite-them-right) and purely cosmetic for the rest — a control
  implying capability the tool doesn't have, which would itself be a transparency regression. The composer's
  preview (always real) already shows honestly whether manual reordering had any effect.
- **Pre-presentation README/asset fixes**: committed a previously-uncommitted, finished marketing site
  (`www/index.html`, `www/showcase.html`, 51 screenshots) and wired one shot + a link into the root `README.md`,
  replacing its long-stale screenshot TODO; fixed a factually-wrong claim in the README's Security note that
  cross-device sync "does not exist yet" (it's shipped and live in production since inc 312).
- **Backlog #45 queued, not yet done**: swap the Settings "Ada Lovelace" example name (`app/frontend/js/
  35a_mypubs.jsx` lines ~76/81, "e.g. Ada Lovelace" / "e.g. A. Lovelace") for **"Karen Spärck Jones"** / "K.
  Spärck Jones" — Cliff's request, a real non-ASCII test case (the "ä") and a credit-the-lineage nod (her TF-IDF
  work underlies the retrieval/term-weighting this project leans on). Cheap — do this one first if picking
  something small to warm up on.

## What's NOT done — the one open thread
**A real human has never driven the composer (Insert or Edit mode) in real Writer.** This has been flagged
across three increments in a row, not assumed away: real keyboard-typing responsiveness (vs. the spike's
programmatic `setText()`), the Add/Remove/Options/Move ↑↓/Insert-or-Update button flow, and the Options
sub-dialog's Clear button all need a manual pass before the composer is genuinely "done" from an end-user's
perspective. This is the same category of gap every dialog in this adapter has always had — there's no
browser-automation equivalent for LibreOffice dialogs, so this can only be closed by a human actually opening
Writer and using it. **This is the natural first thing to do with the LibreOffice adapter next**, before
building anything further on top of it.

Beyond that: the P0 batch that drove the last dozen-plus increments is genuinely complete. Whatever comes next
for the LibreOffice adapter (Word/Google Docs parity, footnote-style citations, Track-Changes handling — all
named as future items in the README's own "Limitations" section) is open territory, not a known backlog item.

## Pre-presentation checklist (the readiness review's near-term findings)
**Already done this session:** the `www/` commit + README screenshot/stale-claim fixes (see above).

**Still open, and these need Cliff personally, not an agent:**
- **Relocate the demo DB out of the Dropbox-synced folder, or pause sync during the demo.** The machine's own
  `CALLOSUM_DB_URL` still points inside `...\Dropbox\...\callosum\.local\validation-summarize\validation.sqlite`
  — exactly the setup the README warns against (a live `database is locked` risk mid-presentation).
- **Rehearse the demo end-to-end at least once**, ideally with a screen-recorded fallback in case a live model
  call/network hiccup strikes during the real thing.
- **Audit the demo library** (109 real PDFs, Cliff's own research) for anything inappropriate to have visible
  on screen live.
- **If demoing the LibreOffice adapter, do the manual verification pass first** (see above) — don't demo the
  composer live without having tried it yourself at least once.
- Optional, non-blocking: Gemini API key rotation (backlog #42) — `.gitignore` already keeps keys out of git,
  so this is cosmetic-clean-bill-of-health, not a real exposure. Cliff's own call, standing item.

## Backlog — what's open, "within reason" (full detail: `.claude/docs/INCREMENT-BACKLOG.md`)
**Needs a design decision from Cliff — do not just build these:** tag provenance formalization (#9), tags↔
findings/retraction filterability (#19), cross-method auditor deferrals (#23), CRediT builder UX follow-ups
incl. role presets (#26, wants a principles discussion first), the README "voice pass" itself (explicitly
Cliff's, not an agent's, per his own prior note — the factual fixes above are separate from this stylistic
pass), where the `.local/` SQLite-inside-Dropbox should live long-term.

**Gated — destructive/security/outward-facing, needs Cliff's sign-off per item:** permanent-delete not removing
the on-disk PDF (#14), the sync server's live-deploy hardening remainder (#15 — per-user rate limiting,
retention, backup runbook; NOT the same as the local UI work, which is done), harness-hardening repo-furniture
work (#20 — `SECURITY.md`/`CITATION.cff`/`.env.example`/`uv.lock`/`.pre-commit-config.yaml` still don't exist),
packaging/distribution exploration (#21, Tauri desktop shell — exploratory only).

**#30 correction (2026-07-22) — this WAS wrong, don't repeat it:** an earlier revision of this file called #30
"the highest-value unbuilt thing." That was propagated, unverified, from a stale `INCREMENT-BACKLOG.md` entry —
**it was already shipped** (inc 271/272, 2026-07-14/15), just never folded back into that file's bookkeeping
because it landed as one large uncredited Codex commit with no increment notes of its own. `app/backend/
citations/beyond_library.py` already does OpenAlex graph expansion + public-metadata search with an
explainable reason per candidate, wired into `POST /citations/suggest` and the web Cite pane, security-audited
PASS. This session (2026-07-22) closed the one real gap that WAS there — the LibreOffice adapter's Suggest
macro never called the beyond-library path at all — and fixed the doc drift (`INCREMENT-BACKLOG.md`,
`integrations/README.md` which was ALSO stale — it listed the already-real `openalex`/`semantic_scholar`
adapters as "planned, not implemented" — and `.claude/qa-routes/route_42_cite.md`, whose steps never actually
exercised the beyond-library checkbox despite the file already being "covered" by the mechanical gate). Also
removed a genuinely dead, confusing duplicate stub dir, `integrations/semantic-scholar/` (hyphen) — the real
implementation is `integrations/semantic_scholar/` (underscore). **Lesson for next time:** verify a backlog
"unbuilt" claim against the actual code before treating it as true, exactly the same "verify, don't assume"
lesson this session already learned twice with `fetch_csl` and the stale selftest timeout.

**What's genuinely still open for Track C:** Semantic Scholar's *recommendations* endpoint (the client exists,
used only for citation-context work — adding recommendations is a new external fetch, audit-gated); a
persistent, dismissible cache surface in the `gaps.py` style (what's shipped is live/per-sentence/ephemeral —
structurally different from the backlog's original "persistent... cache... dismiss" framing, and was never
built); Stage-4 section-scoping (needs GROBID + the plugin).

**Good candidates for small, self-contained work** (matches the "aesthetic/targeted polish" role Cliff described
this session): backlog #45 (Spärck Jones, above); #27 (more statcheck test forms, low-effort whenever); general
DESIGN.md-consistency passes across any panel that's drifted (read `.claude/DESIGN.md` first, rule #8 — reuse
existing tokens/recipes, never invent a new one silently).

**Declined — do not re-propose** (recorded in backlog §6): folders/collections hierarchy, PDF translation,
cloud multi-agent "write my review," a unidimensional star rating, and others — check §6 before suggesting
anything that sounds similar.

## Reminders (this session's own hard-won conventions — don't relitigate)
- **Real UNO mutation logic is never faked in pytest** — only pure/decidable logic gets pytest coverage;
  everything touching a real `doc` object is verified via `python adapters/libreoffice/run_roundtrip.py`
  (committed + cross-platform; see CLAUDE.md's Verification protocol item 4). One real gap this closed: a
  dialog-construction module (`composer.py`) can still load fine under plain pytest as long as it only imports
  `unohelper`/UNO *lazily inside functions* — don't assume "it's a dialog file" means "zero pytest coverage
  possible" without checking; see `tests/test_libreoffice_composer.py` for what that coverage looks like.
- **Read `.claude/CLAUDE.md` in full before any non-trivial change** — the 600-line cap (machine-enforced,
  `tools/check_line_budget.py`), the Principles gate (rule #9) for anything claim/signal/judgment, DESIGN.md
  (rule #8) before any CSS, QA-POLICY.md (rule #10) before any new endpoint/control, and the security-audit gate
  for new endpoints/integrations/file-write paths/auth.
- **Verify, don't assume** — this session caught two real bugs this way: `fetch_csl` assumed a 200+empty-list
  on a missing paper when the endpoint actually 422s (caught by a real-UNO spike, not a pytest mock); and a
  stale 180s selftest timeout that no longer had headroom once Phase 8/9 added more work. Keep exercising real
  paths, not just mocked ones, for anything touching an external call or a UNO object.
- **A control that implies a capability the tool doesn't actually have is a transparency regression, not a
  scope cut** — the reasoning behind declining "restore style-defined sort" above. Worth applying the same
  test to any other UI affordance that might not do what it visually promises.
- **Commit/push at the end of a work session by default** (no need to ask) — this repo's own standing
  convention, already exercised in this handoff (HEAD is pushed to `origin/main`).
