# Word/Docs parity arc — handoff to Codex (2026-08-28)

Written by Claude at the end of a long session (incs 508-517, +inc 518 fixing CI after this was first written).
Cliff's Claude usage is maxed out for ~48 hours (until Sunday); he asked for this arc handed off to Codex to
keep moving in the meantime. **Cliff will not be available to answer questions during this window.** Make
conservative, well-documented judgment calls rather than blocking on him — see "Working solo" below.

**CI is green as of inc 518** (`.claude/docs/increment-notes/INCREMENT-518-NOTES.md`) — it had been red since
2026-08-27 (three unrelated causes: a stale Bandit baseline, two stale e2e literal-text assertions from the
inc-505 Title-Case sweep, an orphaned QA-route mapping from the Feed-consolidation tab retirement), all fixed
and verified locally (full suite 2563 passed/3 skipped, e2e 13/13, Bandit/tach/line-budget/pip-audit/website-
coverage all clean) before this handoff was finalized. **If CI goes red again after you push, don't assume
it's the same three issues re-occurring** — read the actual failure log fresh (`gh run view --log-failed`),
the same way inc 518 did, rather than pattern-matching to what's already been fixed.

## READ FIRST — do not re-derive this

1. **`.claude/CLAUDE.md` in full**, if you haven't already this session. It is the project's base of
   operations — the design invariants (esp. #1-6), the Principles alignment gate (rule #9), the QA policy
   (rule #10), the latency contract (rule #12), and the Verification protocol are all binding, not optional
   context. This handoff does not restate them.
2. **`.claude/docs/increment-notes/INCREMENT-{509,510,511,512,513,514,515,516,517}-NOTES.md`**, in order —
   the real design diary for everything already built this arc. Read the actual notes, not just the one-line
   summaries in `INCREMENT-BACKLOG.md` — several contain load-bearing technical detail (exact API behavior
   confirmed via research, real bugs found and fixed, honest scope boundaries) you need before extending
   the code.
3. **`.claude/docs/INCREMENT-BACKLOG.md`'s `#33/#34` entry** — the live tracker for this arc's remaining scope.
   Keep it current as you close items, using the exact same pattern the existing entries already use (see
   "How to report progress" below) — don't leave it stale.
4. **`.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md`** — the shared,
   generically-written roadmap doc LibreOffice's own P0/P1/P2 build-out followed. It is the reference for what
   "parity" means, item by item. Every item Word has closed cites its number from this doc; every item still
   open is listed by number too.

## Non-negotiable verification requirements

This project has a real, documented problem with AI-generated work claiming success it hasn't earned — see
CLAUDE.md's own "Verification protocol" section, which exists because of exactly this failure mode. This
handoff adds no new rules, it just makes sure you've internalized the existing ones before working without
Cliff's oversight:

- **Never write "tests pass," "verified," or "PASS" without having actually run the command in this turn and
  reporting its real output.** If you did not run `node --test adapters/word/taskpane_core.test.js`, do not
  claim a test count. If you touch any `.py` file, run `ruff format <file>` and `ruff check <file>` on exactly
  what you touched (never `ruff format .` / `ruff check .` unscoped — see the note below on concurrent
  sessions) and the relevant `pytest tests/test_<area>.py -q` subset, and report the real pass/fail counts.
- **No agent — not you, not the session that built incs 508-517 — can drive real Microsoft Word.** There is no
  headless Word, no browser-automatable surface for the desktop add-in. Every increment this arc has shipped
  Office.js code with `node --test` covering only the pure-logic layer (`taskpane_core.js`), and has
  **explicitly written "not yet live-verified" in the increment notes** rather than claiming the in-Word
  behavior was confirmed. Do the same. Write the manual verification script Cliff should run when he's back;
  do not claim you ran it.
- **Write an `INCREMENT-NNN-NOTES.md` for every real increment**, continuing the numbering from 518, in the
  exact shape the existing ones use (Implemented / Key technical detail / Manual verification script /
  Pytest-or-node-test). Update `.claude/changes.md` and `.claude/CLAUDE.md`'s Word paragraph + the increment
  counter (two places: `**Increment N**` near the top, and `numbered increments (currently at N)` further
  down) the same way every prior increment in this arc did — grep those two exact strings if you need to find
  them again fast.
- **Small increments, one at a time, each committed and pushed separately.** This entire arc (incs 508-517)
  never bundled unrelated changes into one commit. Don't start that habit now.
- **A concurrent session may be touching this repo.** Check `git status` before acting. Never run
  `ruff format .` / `ruff check .` unscoped (per this project's own established convention — see the memory
  note "Scope repo-wide commands in concurrent sessions" if you have access to it, or just: scope every lint/
  format command to the exact files you touched).

## What's already done (incs 508-517) — summary only, read the real notes for detail

- **508**: first live verification of the Word add-in (desktop + Word-on-the-web), two real bugs fixed
  (`run_https.py` sys.path, wrong sideload docs, a styles-dropdown token race).
- **509**: the grouped-citation composer — multi-work citations, per-item locator/label/prefix/suffix/
  suppress-author/author-only, Edit/Delete citation at cursor. Mirrors `adapters/libreoffice/composer.py`.
  Zero backend changes were needed (the shared `render_document`/`citeproc_runner.js` engine already
  supported all of this — confirmed by reading, not assumed).
- **510-511**: a real Remote Access bug found live-testing 509 (desktop 401ing because Remote Access was on
  for the tunnel), fixed properly (not just worked around) by exempting `tools/run_https.py`'s own process
  from the gate via the existing `CALLOSUM_DISABLE_REMOTE_ACCESS` hatch — **zero changes to
  `access_control.py`'s actual logic**. Read 511's notes in full before touching anything security-adjacent;
  it documents a rejected unsafe alternative (trusting loopback origin) and why.
- **512-513**: Document diagnostics (malformed/unresolvable citations, orphaned/retraction-flagged cited
  works, bibliography health) — and a real id-reliability bug found while building it (Word's composer was
  trusting the stored, unreliable `csl_json.id` instead of stamping `"callosum-<paperId>"` the way
  LibreOffice's `_build_records` already does), then a second real bug found *live-testing* diagnostics
  (orphan detection wasn't trash-aware). **Read 513's notes carefully** — the trash-awareness lesson
  (`get_paper()` has no `deleted_at` filter; `get_papers_for_export()` does) is exactly the kind of thing
  that's easy to get subtly wrong again if you build a new feature that needs to check "does this paper still
  exist" without reading 513 first.
- **514**: `tools/run_dev.py` — a combined launcher so the HTTP dev server and Word's HTTPS server can't
  silently drift to different databases/code versions again (this was a real, repeatedly-hit bug this
  session). Use this for your own local testing: `python tools/run_dev.py` (needs `CALLOSUM_DB_URL` set first).
- **515**: closed P0 — verified (not assumed) Word's bibliography is already structurally safe against the
  data-loss hazard LibreOffice's bookmark-based approach had; safer Flatten (count summary, honest "no saveAs"
  disclosure, opt-in metadata cleanup, post-operation integrity re-scan).
- **516**: the "Citations in this document" panel — every unique cited work, occurrence count, orphan/
  retraction badges, click-to-navigate, client-side search. Also **extracted a shared `checkPaperExistence(ids)`
  helper** in `taskpane.js` — Document diagnostics and this panel both call it now. **Reuse this helper for
  anything else you build that needs to check paper existence/retraction status** rather than re-inlining the
  logic a third time.
- **517**: accessibility pass — icon-button `aria-label`s, Enter-to-add-top-result, Escape-to-cancel.

Current state: `node --test adapters/word/taskpane_core.test.js` → **33/33 passing**. Confirm this yourself
before starting (`cd` to the repo root, run it) — don't trust this document's number as current by the time
you read it if any time has passed or other work has landed.

## What's left, in priority order

### P1 remainder

**1. Note-style (footnote/endnote) citation placement — the biggest lift, confirmed by prior research, not
guessed.** Word has zero existing infrastructure for this (unlike LibreOffice, which has
`_note_containers`/`_citation_context`/`_insert_note_mark` in `callosum_cite.py`). Before writing any code:

- **Confirm the current Word JS API surface yourself** — do not trust anything below as gospel, it's a
  same-session-2026-08-28 research summary, not a spec citation: WordApi 1.5 added footnote/endnote support
  (`Body.footnotes`/`Body.endnotes` collections, a `Word.NoteItem` type, content-control-scoped footnote/
  endnote collections too). Read Microsoft's current Word JS API reference for `Word.Body`, `Word.NoteItem`,
  `Word.Range.insertFootnote`/`insertEndnote` (or whatever the actual current method names are) before
  designing anything.
- **The shared backend already supports what you'd need**, confirmed by reading `app/backend/citations/
  render.py`/`citeproc_runner.js`: `render_document` accepts a `noteIndex` per citation cluster (a real
  one-based note number, "0 sentinel for in-text; one-based Writer footnote number for note fields" per the
  existing doc comment) — this is what drives citeproc's ibid/subsequent-note disambiguation. **This means,
  same as every prior increment in this arc, the backend needs zero changes** — the entire feature is
  Word-side: computing the real note index for each citation (which note is it in, is it the first or a later
  citation in that same note, what's that note's own 1-based position among all notes), and inserting the
  citation content control either into an existing note (if the cursor is already inside one) or creating a
  new one.
- **LibreOffice's `_note_containers`/`_citation_context`/`_insert_note_mark` (in `adapters/libreoffice/
  callosum_cite.py`, read them in full before designing the Word equivalent) show the *shape* of the problem
  to solve** (detect note-vs-inline context, compute the real note index, insert-into-existing vs. create-new)
  — but they're UNO-specific implementations. Don't port the code; port the *approach*, verified against
  Word's real API.
- **A document-level footnote-vs-endnote preference** (mirrors LibreOffice's `PREF_NOTE_PLACEMENT`, stored via
  a document user-property) should use `Office.context.document.settings` — the exact mechanism this arc's
  style-persistence (`callosumStyle`) already uses. Don't invent a new storage mechanism.
- **A real, disclosed constraint from this arc's own research (inc 510/511's notes)**: Office.js has no
  equivalent of UNO's `enterUndoContext`/`leaveUndoContext` — you cannot guarantee note-placement changes land
  as one native Undo step the way LibreOffice's inc-364 conversion work could. If you build placement
  *conversion* (inline↔footnote↔endnote, LibreOffice's inc 364), disclose this honestly in the increment notes
  and the UI copy, exactly as inc 515's Flatten work did for the equivalent "Callosum can't save a copy for
  you" gap — do not silently claim Undo safety you can't actually provide.
- **Scope conservatively.** If full placement *conversion* (inc 364's equivalent) turns out to be too large
  for one increment, ship note-style *insertion* (a document already set to footnote-style gets its Callosum
  citations placed in footnotes correctly) first, as its own increment, and file conversion as a following one
  — matching this arc's own established pattern of shipping the smallest sound slice.

**2. Bibliography categories / chapter-section blocks.** LibreOffice's equivalent took incs 377-384 (8
increments) to build in full. Do not attempt the whole thing in one increment. Read the roadmap doc's item
#11 for the full target shape, and LibreOffice's own incremental build-out notes (`INCREMENT-377-NOTES.md`
through `INCREMENT-384-NOTES.md`) for how it was actually sequenced there — mirror that sequencing logic
(smallest useful slice first), don't try to match its exact feature list in Word if Word's data model makes
some piece meaningfully harder (disclose why, the same way this arc has repeatedly done for other gaps).

### P2 / leapfrog (after P1, or interleave if a P2 item is clearly smaller than continuing P1)

All of these mirror an already-shipped LibreOffice increment, reusing an already-adapter-agnostic backend
endpoint (confirmed — check each endpoint's own router file for `# adapter-agnostic` framing or equivalent
comments before assuming, don't just trust this list):

- **Evidence-aware Suggest-Citation details** (mirrors inc 460): full quote, stance breakdown, weak-evidence
  warning, editable locator, Open in PDF. The backend `/citations/suggest` response already carries what's
  needed (confirmed for the LibreOffice/web builds — verify the exact response shape is unchanged before
  assuming).
- **Citation-coverage / integrity-preflight audits** (mirrors incs 459/463): note that Document diagnostics
  (inc 512-513) already covers the retraction-check half of this. What's NOT yet covered: uncited-paragraph-
  stretch detection (inc 463's `_uncited_paragraph_stretches`, a purely structural/local scan — no NLI, no
  network). Read inc 463's own notes for the real polarity bug it found and fixed there before assuming a
  naive paragraph-range comparison is correct.
- **Citavi-style Insert Evidence** (mirrors inc 461): search a paper → pick a saved highlight → configure →
  insert (quote-only / quote+cite / paraphrase+cite / structured card). Reuses `POST /citations/classify-stance`
  unchanged (confirmed adapter-agnostic — `app/backend/api/routers/citation_stance.py`).
- **Open-science statement insertion** (mirrors inc 462): reuses `/statements/pending` (`GET`/`POST`,
  `app/backend/api/routers/statements.py`) unchanged — already fully generalized, not LibreOffice-specific.
  Canned starting phrases live client-side in `app/frontend/js/38b_statements.jsx`'s `STATEMENT_TYPES` — Word
  needs its own small copy of that phrase table (not a backend change).
- **Zotero-field conversion** (mirrors inc 464): Zotero's Word integration is documented (per this arc's own
  competitive-review research) as using real Word field codes, `ADDIN ZOTERO_ITEM CSL_CITATION {json}` — the
  same convention inc 464 verified for LibreOffice against Zotero's own open-source integration code. **Do
  not guess at this** — verify against Zotero's actual open-source Word integration source (mirrors inc 464's
  own research-first discipline) before writing a parser. `Word.Field`/`.code` (WordApi 1.5+) is the
  read mechanism to investigate. Mendeley Cite / EndNote CWY conversion stay **declined** for the same
  documented reason as LibreOffice (no complete vendor payload contract) — see
  `.claude/docs/research/2026-08-21_word_citation_migration_formats.md`. Don't reopen that.

### Explicitly out of scope for this handoff

- **Word support in the packaged Tauri desktop app** — a separate, harder problem (no per-machine cert-trust
  mechanism available to an installed app; the desktop app's random-port-per-launch design conflicts with a
  static sideloaded manifest URL). Backlogged under the same `#33/#34` entry, clearly separated. Do not start
  this unless explicitly asked — it's a different shape of problem from everything else in this arc.
- **A dedicated in-task-pane style browser/search/install UI** — deliberately not being built. Word's style
  dropdown already reflects anything installed via Settings' shared catalog; this was evaluated and declined
  as low-value polish, not an oversight.

## Known technical constraints discovered this arc (don't rediscover the hard way)

- **Backend engine is already ahead of both adapters' UIs.** Before adding a backend endpoint or field for a
  new Word feature, check whether `render_document`/`citeproc_runner.js` (or whatever endpoint you're about
  to extend) already supports it — confirmed repeatedly this arc (grouped citations, locators, note-index) to
  be already-built and simply unused. Grep first, build second.
- **Never trust `csl_json.id` for "which library paper is this."** Use the `"callosum-<paperId>"` stamping
  convention (`stampCallosumId`/`extractPaperId` in `taskpane_core.js`) for anything new that needs a reliable
  paper id from a citation.
- **Never trust `/methods/retraction/check-selected`'s `not_found` for "does this paper still exist"** — it's
  not trash-aware. Use the shared `checkPaperExistence(ids)` helper in `taskpane.js`.
- **Office.js has no `saveAs`** and **no `enterUndoContext`-equivalent**. Both confirmed via research this
  arc. Don't design a feature that silently assumes either exists.
- **An unresolved, previously-flagged architectural gap, found while writing this handoff (not addressed this
  arc — flag it to Cliff, don't just quietly carry it forward):** a prior session (2026-08-18, before inc 508)
  approved a citation-storage redesign for Word specifically *because* grouped citations were coming —
  `ContentControl.tag` should hold only a short stable id, with the actual CSL-JSON payload moved to a Custom
  XML Part keyed by that id, instead of base64-encoding the full CSL-JSON directly into the tag (the same
  scaling risk the LibreOffice roadmap doc flags for ReferenceMark names). **That redesign was never applied.**
  `encodeCitationTag()` in `taskpane_core.js` (confirmed by reading it just now) still does
  `CITATION_PREFIX + " " + b64encode(JSON.stringify({items}))` — the original, simpler-but-unbounded pattern —
  and inc 509 built the full grouped-citation composer on top of it unchanged. No hard Word `ContentControl.tag`
  length limit was found via research (searched; Microsoft doesn't document one plainly), so this may not be
  an active bug today, but a citation grouping many works (each with a full CSL-JSON record: title, all
  authors, abstract if present, DOI, etc.) produces a correspondingly large base64 tag, and every note-style/
  bibliography-category feature you're about to build will add more citations using the same pattern. **Ask
  Cliff whether he wants the Custom-XML-Part refactor done before continuing, or whether it's fine to keep
  building on the current pattern for now** — don't silently pick one, this was already a real design decision
  someone made and then didn't follow through on; a second silent decision compounds the drift.
- **The correlated-objects pattern** (`.track()`/`.untrack()` + `Word.run(object, callback)`) is how Edit
  Citation holds a `ContentControl` reference across separate `Word.run` calls — reuse this pattern (see
  `editCitationAtCursor`/`insertOrUpdateCitation` in `taskpane.js`) for anything else that needs to act on a
  specific control across more than one user interaction, rather than re-scanning by position (which
  `navigateToCitation`, inc 516, deliberately does instead, for a case where re-scanning is actually the safer
  choice — read that increment's own reasoning for when to pick which approach).
- **`adapters/word/taskpane.js` is 773 lines** as of inc 517 (`adapters/` is exempt from the project's 600-line
  cap on `app/`/`integrations/` files, but if this keeps growing, consider a split before it gets unwieldy —
  mirror the existing split precedents elsewhere in the codebase, e.g. `10b_libmenus.jsx`, if/when you do).

## Working solo (Cliff unavailable ~48h)

- **Prefer the smaller, safer option whenever there's a real choice**, and document which you picked and why
  in the increment notes — exactly the pattern this arc's own plan-mode passes established (e.g., inc 511
  choosing a combined-launcher script over a deeper single-process merge). Don't guess at what Cliff would
  want on something consequential; pick the conservative path and leave a clear trail for him to redirect
  later if he wants the bigger version.
- **Do not touch**: `access_control.py` or anything else security-relevant beyond what's already described
  above, git history rewrites, force-push, `--no-verify`, or anything the project's own CLAUDE.md flags as
  needing explicit sign-off (the security audit gate, rule #9's Principles gate for claim/signal features —
  Document diagnostics and the citations panel already went through this reasoning; a genuinely new
  claim-producing feature should too, and if you're not confident doing that reasoning yourself, say so in the
  increment notes rather than skipping it).
- **If you hit something that genuinely needs Cliff's input** (a real product-direction fork, not just an
  implementation detail), stop, write up the question clearly in the backlog entry or a new dated doc in
  `.claude/docs/`, and move to the next item rather than blocking everything on it.
