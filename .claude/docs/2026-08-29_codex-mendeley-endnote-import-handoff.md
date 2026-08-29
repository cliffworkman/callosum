# Real Mendeley + EndNote whole-library import — handoff to Codex (2026-08-29)

Written by Claude after Cliff (the maintainer) flagged that the currently-shipped Mendeley/EndNote import paths
(backlog #57 Phases 2/3) don't actually meet his and his colleague's real needs. Cliff's Claude usage resets
tomorrow morning; he asked for this to be handed off to Codex to keep moving overnight. **Read the research doc
first — it is not optional context**: `.claude/docs/research/2026-08-29_mendeley_endnote_native_import.md`.
This handoff assumes you've read it and does not re-derive its findings.

## READ FIRST — do not re-derive this

1. **`.claude/CLAUDE.md` in full**, if you haven't already this session. Same binding invariants as every prior
   handoff (design invariants #1-6, the Principles gate rule #9, QA policy rule #10, latency contract rule #12,
   Verification protocol). This handoff does not restate them.
2. **`.claude/docs/research/2026-08-29_mendeley_endnote_native_import.md`** — the actual research: why the
   shipped Phase 2/3 paths are insufficient, why the Mendeley OAuth-API path and EndNote `.enlx` path are better,
   the real (not hypothetical) MyISAM-vs-SQLite discrepancy found by directly inspecting real fixture files, and
   the explicit open research question about safely reading MyISAM tables that this handoff does NOT resolve
   for you.
3. **`.claude/docs/research/2026-08-21_mendeley_via_zotero_bridge.md`** and
   **`.claude/docs/research/2026-08-21_endnote_generic_import.md`** — the existing, still-valid research behind
   the currently-shipped Phase 2/3 paths. You are not replacing them (the Zotero bridge and RIS import stay as
   fallback options in the UI — see "Product decision" below), you are adding a better primary path alongside.
4. **`.claude/docs/research/2026-08-21_word_citation_migration_formats.md`** — the SEPARATE, correctly-still-
   gated question (converting live Mendeley Cite / EndNote CWY citation fields *already embedded in a Word
   manuscript*). **Do not touch this.** It was re-verified fresh on 2026-08-29 (same conclusion: still gated, no
   new evidence). This handoff is exclusively about whole-*library* import — references, PDFs, folders — not
   in-*document* citation conversion. If you find yourself writing anything that touches
   `adapters/word/*`/`adapters/libreoffice/*` citation-field parsing for this task, you have the wrong scope.
5. **`.claude/docs/INCREMENT-BACKLOG.md`'s `#57` entry** — Phase 6 is the live tracker for this work. Keep it
   current as you go, the same pattern every other entry in this file already uses.

## Non-negotiable verification requirements (same as every other handoff this project has given you)

- **Never claim "tests pass," "verified," or "PASS" without having actually run the command and reporting real
  output.** Run `ruff format`/`ruff check` scoped to exactly the files you touched (never unscoped — a
  concurrent session may be touching this repo; check `git status` before acting).
- **Write an `INCREMENT-NNN-NOTES.md` for every real increment**, continuing the current numbering (check
  `.claude/docs/increment-notes/` for the current max — **do not trust any number written in this doc as still
  current**, re-check live, the same discipline the Word/Docs handoff already asked of you). Update
  `.claude/changes.md` and `.claude/CLAUDE.md`'s relevant paragraph + the increment counter (two places).
- **Small increments, one at a time, each committed and pushed separately.**
- **Open a `.claude/security-audits/` stub at task start for each of Phase A (Mendeley OAuth) and Phase B
  (EndNote import)** — both trigger the audit gate for multiple independent reasons (new API endpoint, new
  external integration, new file-ingestion path — see the research doc's own security-posture section for what
  each audit needs to cover).
- **This is real personal data.** Cliff's own real (if old) EndNote library is now sitting at
  `.claude/backups/endnote-fixtures/` (gitignored — confirmed via `git check-ignore -v`, do not ever remove that
  gitignore coverage or commit these files). Treat it with the same care as any other user's real library data —
  read-only, never mutated, never logged verbatim beyond what's needed for a fail-closed error message.

## What's already done (relevant context, not this task's scope)

- Phase 1 (native Zotero importer, inc 484), Phase 4 (Zotero annotation position fidelity, inc 485), Phase 5
  (Word/LibreOffice citation-field conversion research gate, inc 488, re-verified 2026-08-29 — stays gated) are
  all complete and out of scope here.
- Phase 2 (EndNote RIS, inc 486) and Phase 3 (Mendeley-via-Zotero, inc 487) are shipped and **stay in the
  product as fallback/simpler options** — see "Product decision" below. You are adding better *primary* paths
  alongside them, not removing them.
- The Word/Docs parity arc (incs 508-532) is a **separate, concurrent Claude-driven-then-Codex-driven track** —
  unrelated files, no scope overlap with this task. Don't let it distract you; this is genuinely different work.

## Scope, in three phases

### Phase A — Mendeley native OAuth importer

**Blocked on Cliff, cannot be finished without him.** callosum needs its own registered OAuth application at
dev.mendeley.com (a `client_id`/`client_secret` pair) — this is a one-time manual registration step only Cliff
can do (the same category of task as the existing Google Docs OAuth client setup). **What you CAN do now,
without those credentials:**
- Design and scaffold the OAuth 2.0 Authorization Code flow (mirror the existing ORCID OIDC pattern in
  `app/backend/api/auth/` for the general shape: redirect, callback, token storage — but this is a *different*
  vendor/protocol, verify Mendeley's actual current OAuth endpoints/scopes from `dev.mendeley.com`'s live docs
  yourself rather than trusting this document's paraphrase).
- Build the `/documents` (paginated, `folder_id` filter), `/folders` (hierarchical via `parent_id`),
  `/folders/{id}/documents`, `/files` + `/files/{id}` (redirect-to-signed-URL PDF download) client calls against
  Mendeley's real, current API reference — read it yourself, don't assume the research doc's summary is
  complete or unchanged by the time you implement.
- Reference `github.com/Mendeley/mendeley-python-sdk` (official, if dormant) for the exact call shape, but write
  your own client code — don't vendor or copy that project's code wholesale without checking its license terms
  and whether its dependencies are acceptable for this project.
- Store the resulting OAuth token the same way BYOK provider keys already are (`app_settings.py`, write-only
  over the wire, keychain-or-file) — this is a credential, treat it like one.
- **Stop short of the actual live OAuth handshake and document exactly what's blocked and why** in the
  increment notes, so Cliff can register the app and unblock you (or a future session) with minimal
  re-explanation. Do not fabricate a working end-to-end test without real credentials.
- Design the import logic itself (walk `/folders` → `/documents` per folder → `/files` per document) to run
  every incoming work through `find_existing_paper_by_identity` (the same function
  `app/backend/importers/zotero.py` and `app/backend/api/routers/zotero_citations.py`'s
  `resolve_zotero_citations` already share) before creating a new paper row — this directly addresses Cliff's
  "jillion duplicates" complaint and is reuse, not new design.

### Phase B — EndNote native `.enlx` importer

**Blocked on you resolving a real open research question first — do not start coding until you have.** The
research doc explicitly does not resolve *how* to safely read the MyISAM `.frm`/`.MYD`/`.MYI` table files both
of Cliff's real fixtures actually use (not SQLite, contrary to what the open-source community reverse-engineering
documents for modern EndNote — a real, verified-by-direct-inspection discrepancy, not a guess). **Your first job
here is a dedicated research spike**, mirroring this project's own "research first, verify against real sources,
never guess" discipline (the same discipline behind, e.g., inc 464/530's Zotero-field-conversion work): is there
a safe way to read MyISAM tables without depending on a persistent MySQL/MariaDB server — a trustworthy
pure-language reader, an ephemeral/embeddable engine you spin up and tear down solely for this import, or
something else? Or is this genuinely not safely buildable without such a dependency, in which case say so
plainly and scope Phase B down accordingly (e.g., to whichever EndNote versions turn out to use the
SQLite-based format instead — untested, no fixture available for that variant) rather than shipping something
you can't stand behind. **Do not hand-roll a binary MyISAM parser from scratch without first checking whether a
trustworthy existing implementation already exists** — the same "verify against real code, don't guess"
principle that made the Zotero-field-conversion feature safe applies here.

Once you have a real strategy:
- Real fixtures are at `.claude/backups/endnote-fixtures/` (gitignored, confirmed): `EndNotex1/My EndNote
  Library.enl` + its companion `.Data` folder (a real personal EndNote X1 library, MyISAM-based, `PDF/`
  subfolder present but empty in this copy — no real attachment to test against), and
  `EndNotex7.7/Sample_Library_X7.enlx` (EndNote's own vendor-shipped sample, also MyISAM-based, also no real
  PDF attachments inside it) plus `EndNotex7.7/My EndNote Library.xml` (a real personal EndNote-XML export, no
  groups/attachments — useful only for confirming the "EndNote XML carries no group/attachment data" finding).
  **Neither fixture has a real attached PDF to test the attachment-extraction half against** — ask Cliff or his
  EndNote-using colleague for one if you need real attachment coverage, or disclose this test gap honestly
  rather than claim it's covered.
- Parse the `.enlx` ZIP → extract the MyISAM tables (`refs`, `misc`, `groups` if present, `pdf_index`) → map to
  paper fields, exactly mirroring the `citation_import.py` module's existing `csl_record_to_paper_fields`
  contract where the fields overlap, so downstream code doesn't need a second paper-field-mapping path.
- Extract attachment PDFs from the `.Data/PDF/` (or wherever the real fixture data shows them) folder and run
  them through the same PDF ingestion pipeline the Zotero importer already uses (`app/backend/pdf_processing/
  ingest.py` — read how the Zotero importer calls it, reuse the same call, don't reinvent it).
- **Fail closed on schema mismatch.** Verify the expected tables/columns exist before trusting them; a library
  from an EndNote version whose schema doesn't match should produce a clear "unsupported EndNote library
  version" error, never a silent partial/wrong import.
- **Bound everything.** ZIP entry count/size, table row counts, attachment counts — this is untrusted external
  file content (rule #4).
- Same identity-matching + PDF-attach-to-existing-vs-new-paper discipline as Phase A above.
- Map the EndNote group/group-set hierarchy (if extractable) the same way Phase C describes below.

### Phase C — imported folders/groups → axes (no external blocker, buildable and testable now)

This has no prerequisite and can be built/verified before Phase A/B are unblocked, and gives immediate value
even if only Zotero's existing collections get wired up first:

- **Retroactively surface the already-imported, currently-inert Zotero `collections`/`collection_papers`
  tables** (`app/backend/importers/zotero.py`'s `_upsert_collections` already writes this data on every Zotero
  import — confirmed via grep that nothing currently reads it). This alone is real, immediate value for anyone
  who's already run the Zotero importer.
- Design one shared "import as axis" step usable by all three sources (Zotero's `collections`, EndNote's
  group-set hierarchy once Phase B extracts it, Mendeley's `/folders` once Phase A is live): default to
  creating a manual **Curated Axis** per top-level folder/group (the existing user-defined-container concept —
  read `15_axes.jsx`'s existing Curated Axis code before designing this, reuse its data model rather than
  inventing a parallel one), with an explicit opt-in checkbox to instead create a normal auto-scored axis from
  the same paper set (per Cliff's own explicit request — "maybe even giving users the option to import them as
  non-manual axes").
- This is additive — it must not change the existing axis system's own semantics, scoring, or UI for
  manually-created axes in any way.

## Product decision (already made, don't re-litigate)

Cliff's own words: "we need a one-click (or very few at least) solution that allows people to take their extant
libraries, migrate them seamlessly and fully into their extant libraries, and to keep working with as few
roadblocks as possible." The existing Phase 2 (RIS)/Phase 3 (Zotero bridge) paths stay in the product as
simpler/fallback options (RIS for a bare-metadata-only need; the Zotero bridge for anyone who already has Zotero
or wants the most battle-tested community-verified path) — but the NEW Phase A/B paths should become the
**recommended, default-surfaced** options in onboarding, the Library "+ Add" menu, and Help, the same way the
native Zotero importer is already the recommended Zotero path over generic BibTeX/RIS.

## Principles / APPROACH-AVOIDANCE gate — already run, reuse this reasoning

Neither new path produces a claim/signal/judgment about the literature (format migration, same posture as the
Zotero-field-conversion feature's own audit language: "a faithful format migration, not a claim about the
literature"). Neither touches the no-protected-store-reaching boundary: EndNote's `.enlx` is a file the user
explicitly exported and handed to callosum (copy-then-read, the same posture the Zotero importer already uses —
not live decryption of a running application's database, and specifically NOT the encrypted-Mendeley-Desktop-DB
workaround that boundary already forbids); Mendeley's OAuth path uses the vendor's own sanctioned consent
screen, the structural opposite of reaching into a protected store without permission. Confirm this reasoning
still holds for whatever you actually build — don't just cite it if the implementation drifts from what's
described here.

## Working solo (Cliff largely unavailable until his session resets)

- **Prefer the smaller, safer option whenever there's a real choice**, and document which you picked and why —
  the same pattern the Word/Docs arc's own plan-mode passes established.
- **Do not touch**: `access_control.py`, `adapters/word/*`/`adapters/libreoffice/*` citation-field logic (wrong
  scope, see above), git history rewrites, force-push, `--no-verify`.
- **If you hit something that genuinely needs Cliff's input** beyond the two named blockers above (the OAuth
  app registration, the MyISAM-reading strategy decision if it turns out genuinely unresolvable safely), stop,
  write up the question clearly in the backlog entry or a new dated doc, and move to the next unblocked phase
  rather than stalling everything on it. Phase C has no blocker — if Phase A/B both hit a wall, there's still
  real, shippable work available there.
