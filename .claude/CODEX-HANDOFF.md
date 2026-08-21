# Codex handoff — 2026-08-21: backlog #57, ref-manager migration (Phases 2-5)

You (Codex) are picking up callosum **unsupervised** this weekend — Cliff is at his weekly usage
limit for Claude Code until it resets Sunday, and won't be actively reviewing as you go. A
different AI (Claude) will review everything you produce once Cliff is back. That changes how you
should operate: **prefer stopping and documenting a genuine blocker over guessing past it.** A
clearly-flagged "I got this far, here's why I stopped" is far more useful to Sunday's reviewer than
a guess that ships wrong and has to be unwound.

**Read `.claude/CLAUDE.md` in full first.** Every rule below assumes you have. It is long on
purpose — this project has real invariants (an honesty contract around citation evidence, an
egress-off-by-default posture, a 600-line file cap) that are cheap to honor from the start and
expensive to unwind later.

**Base state (2026-08-21):** `main` at increment 484, 2331 root-suite pytest tests passing. Backlog
#57 Phase 1 (the native Zotero library importer) is shipped — read `INCREMENT-484-NOTES.md` and
`.claude/security-audits/2026-08-20_zotero-library-import.md` for exactly what that established,
since Phases 2-5 build on its patterns (the async-job route shape, the `find_existing_paper_by_
identity`/`create_paper` dedup primitives, the onboarding-wizard extension point).

---

## Before you touch anything user-facing: aesthetic coherence is not optional polish

Cliff's own words, directly: Codex "always messes up on aesthetics, deviating in places its
additions to callosum from its carefully curated appearance and structure." This is the single
thing this handoff most wants you to get right.

1. **Read `.claude/DESIGN.md` in full before writing a single line of CSS or JSX markup.** It is
   the design dictionary: a tokens table (`--bg`/`--panel`/`--ink`/`--accent`, the semantic color
   pairs `--verified`/`--flag`/`--danger`/`--wip`, the radius scale, three type roles), per-element
   recipes, and fixed color semantics — indigo means provenance/verification, green means verified,
   amber means unresolved/uncertain, red means destructive, and **no other meaning ever borrows
   these colors.** New UI conforms to an existing recipe and references a token. It does not invent
   a new color, a new radius, or a new spacing value because the existing ones didn't quite fit —
   if nothing fits, that itself is worth flagging in your session summary rather than working
   around silently.
2. **Never re-type a raw hex a token already names.** If you catch yourself writing `#4b3f72` or
   similar, stop — there is almost certainly a `var(--...)` for it already.
3. **Reuse existing component shapes.** This codebase has an established, load-bearing pattern for
   almost everything you'll need: async-job modals with a resume-on-remount `localStorage` poll
   loop (`app/frontend/js/27_scan.jsx`'s `ScanModalBody`, and Phase 1's own
   `27b_zotero_import.jsx`), the `axis-modal`/`axis-modal-overlay`/`axis-form-actions` chrome family,
   the Library "+ Add" menu (`10b_libmenus.jsx`'s `AddMenu`), and the onboarding wizard's
   choice-then-body pattern (`04e_onboarding.jsx`). Read the closest existing analog before writing
   a new component, and match its shape — don't design a new pattern for something this project
   already has three working examples of.
4. **Before calling any user-facing change "done," run the end-user experience pass**
   (`.claude/EXPERIENCE-PASS.md`, CLAUDE.md rule #11). It asks two questions beyond "does it work":
   (1) **reception** — is the new thing discoverable, is the next step obvious, does a user land on
   it without hunting; (2) **intended use** — what does a real user reach for next, does what you
   built support that or dead-end them. You won't have a live Claude session to dispatch the
   persona-agent mechanism the doc describes — instead, literally write out (in your own session
   summary) a one-paragraph walkthrough as a concrete user: someone mid-migration from Mendeley/
   EndNote/Zotero, trying to get their library into callosum with as few clicks as possible (that's
   the actual persona this whole backlog item exists to serve — Cliff's own words: "ensure such
   prospective users are able to essentially move their library into callosum with as few clicks
   and as little individual effort as possible"). If that walkthrough reveals friction, fix it or
   flag it — don't ship past a dead end because the code technically works.
5. **Match the codebase's actual voice in every doc you write** — increment notes, `CLAUDE.md`
   bullets, code comments. Read 2-3 neighboring entries before writing a new one (the most recent
   few `INCREMENT-NNN-NOTES.md` files and the newest few Stack-section bullets in `CLAUDE.md` are
   the fastest way to calibrate). This project's documentation is dense, specific, and
   self-referential — not generic AI-written prose. A reviewer can tell the difference immediately,
   and it's one of the fastest ways trust erodes.

---

## The task: backlog #57, Phases 2-5, as far as you can get by Sunday

Full current text of the backlog entry (`.claude/docs/INCREMENT-BACKLOG.md`):

> **#57 Whole-library migration (Zotero/Mendeley/EndNote).** A user's *entire* existing
> reference-manager library moving into callosum, distinct from the #33/#34 "Traveling-library
> portability" line above (that one is about a single document's own in-document citations, not a
> whole library).
> - **Phase 1 shipped, inc 484:** the already-built native Zotero importer
>   (`app/backend/importers/zotero.py`) — `POST /library/zotero/import`, a Library "+ Add" entry,
>   and an onboarding-wizard option.
> - Phase 2: EndNote via the existing generic BibTeX/RIS/CSL-JSON importer, verified against a
>   real EndNote export sample (not just a hand-built fixture).
> - Phase 3: feasibility spike for a Mendeley-via-Zotero-bridge import path (Mendeley's modern
>   export reportedly encrypts citation data, blocking a direct clean export; Zotero's own
>   import-from-Mendeley may be the practical bridge).
> - Phase 4: Zotero annotation-position fidelity — map Zotero-reader-JSON highlight positions into
>   callosum's own PDF-space bbox/page coordinates (closes the disclosed gap in
>   `integrations/zotero/README.md`).
> - Phase 5: word-processor in-document citation migration for Word, extending inc 464's
>   LibreOffice Zotero-conversion pattern — gated on primary-source research into Mendeley Cite's/
>   EndNote's actual field-code formats (neither is verified anywhere in this repo today; mirrors
>   inc 464's own research-first precedent, not reverse-engineering a sample file).

**Work them in this order — each is a genuinely separate, independently-committable slice. Stop
after any phase and move to the next; don't let a stuck phase block the ones after it.**

### Phase 4 first (recommended starting point — most bounded, least research risk)

Zotero annotation-position fidelity. The gap is precisely documented in
`integrations/zotero/README.md`: imported annotations carry `position_json`/
`coordinate_system="zotero-reader-json"` (raw, untranslated Zotero Reader coordinates) but never
populate `page`/`bboxes_json` — the columns callosum's own PDF viewer overlay actually reads
(`app/frontend/js/30_viewer.jsx`, `10_pdf_layer.jsx`). Zotero's own annotation-position JSON shape
is publicly documented (its own API/plugin docs describe the `position` object's `pageIndex` +
`rects` array in PDF-page-space) — this is a coordinate-transform problem, not a reverse-engineering
one. Read `app/backend/pdf_processing/extraction.py`'s `COORDINATE_SYSTEM` constant and the
existing bbox/page storage shape on `annotations` (`app/backend/persistence/schema.py`) before
designing the translation. **Honor invariant #2 (the coordinate honesty contract) exactly**: a
successfully-translated position is `exact`; anything you can't confidently translate must stay
`null`/region-level, never guessed into a false `exact`. Wire this into `app/backend/importers/
zotero.py`'s `_upsert_annotations` (additive — don't change the function's existing contract for
callers that don't need this). New endpoint/UI surface here is unlikely to be needed (this is a
backend data-fidelity fix, surfaced automatically once the frontend's existing overlay renderer
gets real bbox data) — but if you do add any UI, Phase 4 doesn't skip the aesthetic-coherence
section above.

### Phase 2 next — EndNote via the generic importer

**A real constraint, not a guess:** no genuine EndNote export sample exists anywhere in this repo
(confirmed by a fresh search this session — `integrations/` has no `endnote/` sibling to `zotero`/
`mendeley`, and nothing under `tests/fixtures/`). `.claude/docs/research/
opus4.8_deepresearch_refmanagercomparison.md` has real competitive research on EndNote's export
formats (it favorably notes clean "EndNote-XML, RIS, BibTeX export" unlike Mendeley's broken story)
but is market research, not a sample file. The existing generic importer
(`app/backend/metadata/citation_import.py`, `POST /library/import`) already parses BibTeX/RIS/
CSL-JSON — read it in full, including its documented v1 limitations (brace-delimited BibTeX entries
only, no `@string`/`#`-concat expansion) before assuming it needs new code at all.

Since you have no live human to hand a real EndNote export to this weekend, do the best-effort,
honest version of this phase:
1. Research EndNote's actual RIS/BibTeX export conventions from EndNote's own current
   documentation (not memory/assumption) — does it use any RIS tags or BibTeX entry shapes the
   existing parser's documented limitations would mishandle? (e.g., EndNote is known to sometimes
   emit `@ARTICLE(...)`-parenthesis-form BibTeX rather than brace-form — verify this against real
   EndNote docs, don't assume.)
2. If you find a genuine, well-sourced gap, fix it narrowly (minimal diff, rule #7) and add a
   test fixture that reproduces the *real* documented EndNote quirk, with a comment citing where
   you confirmed it (a doc URL, a spec reference) — not a fixture that only proves your own fix
   passes your own assumption.
3. **Be explicit in your session summary that this phase's fixture-based testing is a stand-in for
   real-file verification, not a substitute for it.** The backlog item's own text says "verified
   against a real EndNote export sample" — you cannot close that literal requirement without one.
   Leave the backlog line open/partial rather than marking it done on synthetic-fixture testing
   alone; that's Cliff's own call to make with a real export file in hand.
4. If EndNote's onboarding-wizard/import-modal copy (`04e_onboarding.jsx`'s
   `OnboardingImportChoice`, already says "exported from Zotero, Mendeley, or EndNote") needs no
   change, don't touch it — it already covers this path.

### Phase 3 — Mendeley-via-Zotero-bridge feasibility spike

This is explicitly a **spike**, not a build task — its job is to produce an honest answer, not
code you necessarily keep. `integrations/mendeley/README.md`'s existing text already concludes
direct Mendeley-database reads aren't viable (modern Mendeley encrypts citation data) and
speculates Zotero's own "import from Mendeley" feature might be a workable bridge. **Confirm or
refute that speculation with real research** (Zotero's own documentation/source on whether/how it
imports a Mendeley library, and what format the result takes) before writing any code. Three
honest outcomes are all acceptable, in order of preference:
1. **The bridge is real and documented** → design (don't necessarily fully build, if time is
   short) a path: guide the user to run Zotero's own Mendeley import once, then point callosum's
   already-shipped Zotero importer (Phase 1) at the resulting Zotero library. This might need zero
   new backend code — possibly just onboarding-copy/documentation work pointing users at the right
   sequence.
2. **The bridge is real but has real gaps** (partial metadata, no PDFs, etc.) → document exactly
   what transfers and what doesn't, update `integrations/mendeley/README.md` with the confirmed
   findings, and leave a clear "here's what a Mendeley user should expect" note for the onboarding
   copy — don't build a false-confidence import flow.
3. **The bridge doesn't hold up** → this is a legitimate, valuable finding. This project has
   precedent for declining a feature as a documented finding rather than forcing a bad
   implementation (e.g. backlog #24's salami-slicing detection, declined outright after research).
   Write up why, update `integrations/mendeley/README.md`, and move on — don't force code to exist
   just because time was spent on it.

### Phase 5 — likely out of scope for a solo weekend; treat as research-only if you get here

This phase depends on primary-source research into Mendeley Cite's and EndNote's actual
document-embedded citation field formats — **neither is verified anywhere in this repo**, and this
project has an explicit, hard-won precedent (inc 464's Zotero-citation-conversion work) of
verifying a citation format against the *tool's own source/documentation* before writing a parser
for it, specifically because guessing at an undocumented format is how silent data corruption
happens in a feature that touches a user's live manuscript. If you reach this phase with time
left, **do the research and write up findings — do not attempt to build a parser for either format
without first confirming its real shape against a primary source** (Mendeley Cite's actual Word
Content-Control/XML-part structure; EndNote's actual `{ADDIN EN.CITE ...}` field-code schema). A
solid research writeup here (even with zero code) is more valuable than a guessed-at parser that
could corrupt a real Word document.

---

## Hard rules for this session

1. **Work in an isolated branch, never on `main` directly.** Create a dedicated branch —
   `git checkout -b codex/backlog-57-phases-2-5` (or, if you prefer the isolation this project's
   own Claude Code sessions use, a separate worktree: `git worktree add
   .claude/worktrees/codex-backlog-57 -b codex/backlog-57-phases-2-5`). **Do not push or merge to
   `origin/main`.** Cliff will review and merge (or ask for revisions) once he's back Sunday —
   leaving your work as an unmerged, reviewable branch is the whole point of this handoff.
2. **Commit incrementally, with real messages**, one logical change per commit — this project's
   own convention (check `git log --oneline -20` for tone/format before your first commit).
3. **Verification protocol** (CLAUDE.md's own, don't skip steps): while developing, run only the
   targeted test file(s) for what you're touching (`pytest tests/test_<area>.py -q`) — the full
   suite is slow (~25-45 min on this machine, and this machine has a **known, real** pattern of
   killing pytest workers under memory pressure with no actual test failure — if a run gets
   silently killed with no FAILED output, that's an environment issue, retry with fewer workers or
   serially, never report it as a code regression). Before considering any phase "done," run the
   full suite once (`pytest -n auto -q`, or `-n 4`/serial if you hit the memory issue) and report
   the **actual observed pass count** — never state a test count you didn't personally just see in
   real output.
4. **The four alignment gates, all binding, all in `.claude/`:**
   - **Rule #8 / `DESIGN.md`** — covered at length above; the one this handoff most wants you to
     honor.
   - **Rule #9 / `PRINCIPLES.md`** — before adding or removing anything that produces a
     claim/signal/judgment about the literature, or changes provenance/egress posture, name the
     principle it touches and the worked example it resembles. This backlog item is mostly
     plumbing (moving records between systems), so it may not trigger this gate at all for most of
     Phases 2-4 — but Phase 3's Mendeley bridge and Phase 5's citation-format work both touch
     provenance (`imported_source` tagging) and are worth a quick read of `PRINCIPLES.md`'s
     relevant commitments before building.
   - **Rule #10 / `QA-POLICY.md`** — any new API endpoint, changed request/response contract, new
     interactive control, or new async job needs a QA route added in `.claude/qa-routes/` in the
     same increment (the next free number is **94** as of this writing — verify against
     `ls .claude/qa-routes/` before naming a new one, since more may land before you start). Phase
     1's own `route_93_zotero_library_import.md` is the closest template.
   - **Rule #11 / `EXPERIENCE-PASS.md`** — covered above.
5. **Security-audit gate** (CLAUDE.md's own list — a new API endpoint, a new external fetch, a new
   file-ingestion path, or 300+ added LOC all trigger it): open a
   `.claude/security-audits/YYYY-MM-DD_<feature>.md` stub at task start, fill it as you go
   (input validation, egress, secret handling, resource caps, negative-path checks actually run
   and recorded), end with **PASS** or an honestly-flagged open risk. Phase 1's
   `2026-08-20_zotero-library-import.md` is the direct template.
6. **600-line file cap** (rule #1) — `python tools/check_line_budget.py --list` after touching any
   `app/`/`integrations/` file; split into a sibling file before crossing 600, following this
   project's own established split pattern (a new `<name>_<concern>.py`/`.jsx` file, re-exported
   where needed — check any recent `INCREMENT-NNN-NOTES.md` for a worked example).
7. **`ruff format .` + `ruff check .` + `python -m tach check`** before any commit you consider
   part of a finished slice — CI runs all three; a red CI on Sunday costs more time than running
   these now.
8. **Never over-claim.** This is the single most important rule in this whole document, because
   nobody will be watching in real time to catch it. Report exactly what you ran and what it
   showed — a real command's real output, not a paraphrase of what you expect it would show. If
   something is untested, partially done, or genuinely uncertain, say so plainly in your session
   summary. A phase marked "done" that isn't will cost far more of Cliff's and Claude's time on
   Sunday untangling it than an honestly-reported partial phase would.
9. **Update `.claude/CLAUDE.md` in the same session as any change that affects architecture,
   conventions, or the design invariants** (rule #6) — this file is the project's living memory;
   drift here is exactly how institutional knowledge rots. Write increment notes
   (`.claude/docs/increment-notes/INCREMENT-485-NOTES.md` — the next free number as of this
   writing, verify it's still free — through however many increments you complete) in the
   established Implemented/Key technical detail/Manual verification script/Pytest shape, and a
   dated entry in `.claude/changes.md` for each.
10. **Trim `.claude/docs/INCREMENT-BACKLOG.md`'s `#57` entry as phases genuinely close** (per this
    project's own backlog-closure discipline — mark a phase's bullet done in place, or move fully
    closed detail to `INCREMENT-BACKLOG-DONE.md` only once the WHOLE #57 item closes, not
    per-phase). Don't mark Phase 2 "done" if the real-EndNote-sample verification is still
    outstanding — see Phase 2's own guidance above.

---

## When you stop (end of session, or Sunday, whichever comes first)

Append a **"Codex Session Summary"** section to the bottom of this same file
(`.claude/CODEX-HANDOFF.md`) — mirroring this project's own prior convention — covering:
- What actually shipped (phase-by-phase, with commit hashes on your working branch).
- The **real** final pytest count from an actual run you watched complete (not a target, not an
  estimate).
- Both `ruff format --check`/`ruff check` results and the `tach check` result.
- Anything partial, unverified, or where you made a judgment call the backlog text didn't
  resolve — flag it explicitly, don't bury it in a commit message.
- Which security audits and QA routes you opened, and their current status.
- Your honest recommendation for what Claude/Cliff should look at first on Sunday.

Then stop — don't push to `origin/main`, don't merge, leave the branch exactly as it is. Claude
will review it fresh against this handoff once Cliff's limit resets Sunday.

---

## Codex Session Summary

**Branch:** `codex/backlog-57-phases-2-5` — not pushed or merged. Cliff's three untracked Discover screenshots
under `.claude/` were left untouched.

### What shipped

- **Phase 4 — shipped, `45299b6`:** preserves exact Zotero highlight/underline rectangles only when bounded,
  unrotated PDF geometry can be proven; fixes attachment-child annotation ownership, scopes overlays to the PDF
  actually loaded, and retains raw provenance without drawing for every unsupported/ambiguous case. Re-import can
  upgrade legacy raw-only rows when the owning PDF becomes available.
- **Phase 2 — partial, `d7c38da`:** documents EndNote's current RefMan (RIS) export handoff and expands the RIS
  parser/test contract for Clarivate's `CPAPER`, `A4`, alternate title/journal/year tags. This remains **open**
  until a genuine, redacted EndNote-created export is exercised end to end; the checked-in fixture is explicitly
  synthetic.
- **Phase 3 — feasibility spike complete, `ff6502b`:** surfaces Zotero's documented Mendeley Reference Manager
  online-import bridge in onboarding, + Add, the Zotero modal, Help, integration docs, and QA guidance. Callosum
  receives no Mendeley credential and does not read/decrypt Mendeley's protected store.
- **Phase 5 — research gate complete, implementation open, `f57eac1`:** first-party sources confirm Mendeley Cite
  content controls and EndNote `ADDIN EN.CITE` fields/Traveling Library, but do not publish either complete,
  versioned payload contract. No converter was built from conflicting third-party reverse engineering. The
  research note defines evidence and preservation requirements for reopening implementation.

### Final observed verification

- `pytest -n auto -q` → **2338 passed, 3 skipped in 1315.42s (0:21:55)**.
- `ruff format --check .` → **784 files already formatted**.
- `ruff check .` → **All checks passed**.
- `python -m tach check` → **All modules validated**.
- `python tools/check_line_budget.py --list` → **all 553 application-source files ≤ 600**.
- `python tools/qa/build_surface_map.py check` → **428/428 API and 1767/1767 frontend surfaces covered**.
- `python tools/qa/check_website_coverage.py` → **70 QA routes (1 excluded), 6 external surfaces, 20 current
  figures** after reviewed receipt refresh.
- `python tools/qa/check_demo_experience_coverage.py` passed with all **121** surfaces categorized.

### Audits, QA, and honest boundaries

- Security audit `.claude/security-audits/2026-08-21_zotero-annotation-position-fidelity.md` is **PASS**.
  Phases 2, 3, and 5 added no endpoint, external fetch, new ingestion route, secret surface, or 300+ LOC feature
  requiring another audit.
- QA route 93 was extended for Zotero annotation fidelity and the Mendeley bridge; route 27 was corrected and
  extended for the EndNote citation-file path. Phase 5 is documentation-only and added no interactive surface.
- No real EndNote-created export was available, so Phase 2 is not complete. The manual verification script is in
  `INCREMENT-486-NOTES.md`.
- No vendor-published Mendeley Cite or EndNote payload schema/supported conversion API was found, so Phase 5
  converter implementation remains gated. Do not infer a stable schema from community samples.
- Phase 3's documented bridge was not driven through live Mendeley/Zotero accounts in this session; its manual
  credential/library verification matrix is in `INCREMENT-487-NOTES.md`.
- Phase 4 deliberately does not claim exact overlays for rotated pages or invalid/out-of-page rectangles; those
  rows preserve raw Zotero provenance and remain undrawn.

### Sunday review recommendation

Review `45299b6` first: the coordinate transform, attachment ownership/scoping, fail-closed cases, and security
audit carry the greatest correctness risk. Next inspect the EndNote/Mendeley guidance for wording and product fit.
Finally confirm the Phase 5 no-parser decision against the primary-source research note. If time allows, the most
valuable missing external evidence is one redacted genuine EndNote RIS export; it can close Phase 2 without

---

# Session 2 — 2026-08-21 (continued): hardening + cross-phase coherence pass

Cliff has 24+ hours of runway left before his weekly Claude Code limit resets Sunday and doesn't
want callosum idling. This session's own summary above was independently spot-checked by Claude
(file existence, backlog text, diff shape, a targeted 101-test independent re-run, a raw-hex-color
grep against `.claude/DESIGN.md`) — it holds up. **Good work.** This second session is not "do
Phases 6+" — there isn't new backlog #57 scope waiting. It's a deliberate step back: harden and
cross-check what already shipped, the same way a final whole-branch review catches things no
single task's own review could see.

**Still on `codex/backlog-57-phases-2-5`. Still don't push or merge to `origin/main`.**

## Do NOT do these — read this before anything else

1. **Do not build a Word-citation converter for Phase 5.** Your own research correctly found
   neither Mendeley Cite nor EndNote publishes a complete, versioned payload contract — that's a
   real, hard-won finding, not a gap to route around. Building a parser from third-party reverse
   engineering risks silently corrupting a real user's live manuscript. This stays gated exactly as
   you left it unless a genuine vendor schema surfaces.
2. **Do not fabricate or construct a substitute "real" EndNote export for Phase 2.** If you can
   find a genuinely public, official EndNote-published sample export (e.g., in EndNote's own
   documentation, a Clarivate support article, or a citable academic methods resource that
   publishes a real export snippet) — as opposed to a synthetic fixture you build to model a
   documented tag — use it and note the source. If you can't find one, Phase 2 stays exactly as
   partial as you already, correctly, left it. Don't let a second session's momentum turn an honest
   "open" into a false "closed."

## What to actually do

### 1. A full end-user experience pass across the now-5-option import surface (highest priority)

The onboarding wizard's import step (`04e_onboarding.jsx`'s `OnboardingImportChoice`) and the
Library "+ Add" menu (`10b_libmenus.jsx`'s `AddMenu`) both grew across Phases 1-3: what was
originally two options (generic file import, bundle import) is now up to five surfaces touching
Zotero/Mendeley/EndNote guidance in one place. Growing a menu one phase at a time is exactly how
clutter and inconsistent hierarchy creep in even when every individual addition was done carefully
— read `.claude/EXPERIENCE-PASS.md` again, then **write out, in full, a persona-grounded
walkthrough** (its own mechanism, adapted since you have no live Claude session to dispatch a
sub-agent for it): be a concrete user — pick one of Mendeley, EndNote, or Zotero — landing on the
onboarding wizard's import step for the first time, or opening the Library "+ Add" menu later.
Actually read the current copy and button hierarchy in both files as that user would encounter it,
not from memory of writing it. Report, honestly:
- Is the right option obvious for *your* chosen persona's actual tool, or does it require reading
  every option to figure out which applies?
- Does the button hierarchy (primary vs. ghost styling) still make sense now that there are more
  options, or does everything visually compete for attention?
- Is any copy now redundant or contradictory across the five options (e.g., does the Mendeley
  guidance say something that conflicts with what the generic-import option's copy already implied
  about Mendeley)?
- If you find real friction, fix it (tightening copy, reordering, adjusting which option is
  visually primary) — small, surgical UI/copy edits, not a redesign. If a fix is genuinely out of
  scope for a copy/ordering tweak, document the friction precisely instead of glossing over it.

### 2. A fresh, cross-phase DESIGN.md coherence re-read

Re-read `.claude/DESIGN.md` in full, then re-read every frontend file this whole arc touched
(`04e_onboarding.jsx`, `10b_libmenus.jsx`, `27b_zotero_import.jsx`, `30_viewer.jsx`) as one
connected pass, not per-commit. Look specifically for: any inconsistency in how the five import
options are visually presented relative to each other (spacing, button style, note/hint styling)
that a phase-by-phase view wouldn't surface; any place a new string of explanatory copy reads
differently in tone from its neighbors; any token or recipe used slightly differently across the
four files. Fix what's cheap and surgical; note anything larger.

### 3. Widen Phase 4's test coverage (the piece your own summary flagged as highest-risk)

You already flagged the coordinate transform as the first thing Sunday's reviewer should look at.
Reduce that risk now: add test cases for combinations your existing suite may not cover — multiple
attachments on one paper with annotations on different attachments, a rotated page combined with an
otherwise-valid rectangle (should still fail closed to raw provenance per your own PASS audit's own
stated invariant), and an attachment whose owning PDF is swapped/relinked after import (does a
previously-`exact` annotation ever get silently mis-attributed, or does it correctly stay pinned to
its original attachment id). If a test reveals a real bug, fix it and say so plainly — that is
exactly the kind of thing worth surfacing now rather than Sunday.

### 4. A consistency pass across the new documentation

Read `INCREMENT-485-NOTES.md` through `INCREMENT-488-NOTES.md` and the four new `CLAUDE.md` Stack-
section bullets as one continuous narrative (not four independent entries). Check: do they
cross-reference each other correctly (e.g., does Phase 5's note about Mendeley Cite/EndNote formats
correctly point back to Phase 3's Mendeley-bridge work rather than duplicating context)? Does any
one of them contradict what another says about the current onboarding flow now that item #1 above
may have changed it? Fix drift; this is cheap now and expensive to catch piecemeal later.

### 5. If time remains after 1-4: re-run the full suite once more and re-verify all gates

`pytest -n auto -q` (or `-n 4`/serial if the environment's known memory-pressure flakiness recurs —
never report a silently-killed run as a real failure), `ruff format --check .`, `ruff check .`,
`python -m tach check`, `python tools/check_line_budget.py --list`,
`python tools/qa/build_surface_map.py check`. Report the real final numbers.

## When you stop again

Append a **"Codex Session 2 Summary"** section (same file, same shape as session 1's): what you
found in the experience-pass walkthrough (including anything you decided NOT to change and why),
what you fixed in the DESIGN.md coherence check, what new test cases you added for Phase 4 and
whether any revealed a real bug, what doc-consistency fixes you made, and the final real
pytest/ruff/tach numbers. Same rule as before: **never report a number you didn't personally just
watch a real command produce.** Still don't push or merge — leave the branch for Claude's review
Sunday.
expanding the architecture.
