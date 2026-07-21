# Codex handoff — session state at Increment 328 + backlog for the coming week

## Context
Cliff presents callosum at a meeting **one week from today (2026-07-21) — around 2026-07-28**. This session did
two things: (1) drove the LibreOffice adapter's P0 correctness/safety rework (backlog #33/#34) from Phase 0
through Phase 10, and (2) ran a strategic release-readiness review at Cliff's prompt ("what am I missing before
the presentation, and beyond it"). That review's findings are folded in below. This file exists because the
session hit its context limit — it's written for whoever picks up next (Codex or a fresh Claude Code session)
with **zero assumed prior context**.

**Repo state: everything below is committed and pushed to `origin/main`** (HEAD `6e397a4`). Increment 328,
**1333 pytest passing, 1 skipped**. `pytest -n auto -q` and `ruff format/check` are clean; the pre-commit
line-budget hook is clean.

## What shipped this session (don't redo)
- **LibreOffice adapter P0 rework, Phases 0–4 and 6–10, all done** (`adapters/libreoffice/`): versioned mark
  schema, transactional refresh with rollback, backend citeproc passthrough (locator/prefix/suffix/suppress-
  author/author-only), `mark_at_cursor`, delete/merge/split/open-in-callosum, a **bounded bibliography**
  (closes the original verified data-loss bug — a bookmark PAIR, never `text.getEnd()`), safe flatten
  ("Prepare submission copy"), read-only document diagnostics, and — as of Phase 10 — the real-UNO test
  harness is now **committed + cross-platform + running in CI** (`adapters/libreoffice/run_roundtrip.py`,
  `.github/workflows/libreoffice-adapter.yml`, path-scoped + non-blocking). Full detail:
  `.claude/docs/increment-notes/INCREMENT-320-NOTES.md` through `INCREMENT-328-NOTES.md`.
- **Pre-presentation README/asset fixes**: committed a previously-uncommitted, finished marketing site
  (`www/index.html`, `www/showcase.html`, 51 screenshots) and wired one shot + a link into the root `README.md`,
  replacing its long-stale screenshot TODO; fixed a factually-wrong claim in the README's Security note that
  cross-device sync "does not exist yet" (it's shipped and live in production since inc 312).
- **Backlog #45 queued, not yet done**: swap the Settings "Ada Lovelace" example name (`app/frontend/js/
  35a_mypubs.jsx` lines ~76/81, "e.g. Ada Lovelace" / "e.g. A. Lovelace") for **"Karen Spärck Jones"** / "K.
  Spärck Jones" — Cliff's request, a real non-ASCII test case (the "ä") and a credit-the-lineage nod (her TF-IDF
  work underlies the retrieval/term-weighting this project leans on). Cheap — do this one first if picking
  something small to warm up on.

## What's NOT done — the two biggest open threads
1. **Phase 5 (the composer UI)** — the largest remaining piece of the LibreOffice P0 rework, **deliberately
   deferred by Cliff** (he asked to hold it until after a context compaction, which has now happened). Locators,
   prefixes/suffixes, suppress-author/date, and building a true multi-item grouped citation from scratch are
   NOT reachable from any UI yet — only single default-shaped citations can be inserted today (merge/split let
   you combine/separate *after* the fact, per Phase 6, but there's no composer). Backend/schema support for all
   of this already landed in Phases 1–3 (`app/backend/api/routers/citations.py`'s `CitationItem` model,
   `citeproc_runner.js`'s `buildCitationItem`) — this is purely the UI layer + the adapter-side dialog. **Read
   `.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md`** (item 5 in that
   roadmap) before starting; also re-read this session's now-superseded increment notes for the confirmed
   citeproc constraints recorded there (`suppress-date` has no citeproc-js equivalent — ships as an inert
   no-op; 4 of 7 bundled CSL styles define their own `<citation><sort>` that silently overrides manual item
   order within a grouped citation, so any composer "preview" MUST be a real round-trip through
   `POST /citations/render-document`, never a client-side simulation).
2. **The CI workflow's Linux path is unverified on a real runner.** `.github/workflows/libreoffice-adapter.yml`
   was written carefully (Ubuntu's `libreoffice`/`python3-uno` apt packages, the system-python UNO bridge
   location, `pgrep`/`kill` process management) but there was no way to execute a GitHub-hosted runner from
   this session's environment. **The first time this workflow actually fires on a real PR/push touching
   `adapters/libreoffice/**`, check its Actions run** — it may need tweaks (Xvfb if some UNO call turns out to
   need a display; longer `wait_http`/`wait_port` timeouts if a cold runner is slower than local dev; the exact
   `python3-uno` package name if Ubuntu's runner image differs from expectations).

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
- **Scope the LibreOffice-adapter portion of the demo to what's actually stable**: insert/refresh/style (Phases
  0–2, transactional + bounded) — avoid merge/split or implying full composer maturity (Phase 5 doesn't exist).
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

**The highest-value unbuilt thing, per the backlog's own audit note:** **#30, Track C SP2/Stage-3** —
"beyond-library suggest" (surfacing relevant papers the user doesn't yet have, not just ranking what's already
in the library). Worth a fresh look if there's room for a substantial new feature this week.

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
  (now committed + cross-platform; see CLAUDE.md's Verification protocol item 4).
- **Read `.claude/CLAUDE.md` in full before any non-trivial change** — the 600-line cap (machine-enforced,
  `tools/check_line_budget.py`), the Principles gate (rule #9) for anything claim/signal/judgment, DESIGN.md
  (rule #8) before any CSS, QA-POLICY.md (rule #10) before any new endpoint/control, and the security-audit gate
  for new endpoints/integrations/file-write paths/auth.
- **Verify, don't assume** — this session caught a real bug (`fetch_csl` assumed a 200+empty-list on a missing
  paper; the endpoint actually 422s) purely because a real-UNO spike exercised a case no pytest mock did.
  Keep exercising real paths, not just mocked ones, for anything touching an external call or a UNO object.
- **Commit/push at the end of a work session by default** (no need to ask) — this repo's own standing
  convention, already exercised in this handoff (HEAD is pushed to `origin/main`).
