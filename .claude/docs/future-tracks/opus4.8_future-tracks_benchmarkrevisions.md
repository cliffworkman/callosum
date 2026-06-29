# Future-tracks inbox — Competitive-benchmark revisions (Phase 2)

**Provenance.** These revisions come from a competitive-benchmarking pass: Callosum (inc 104) characterized on the
same 30 dimensions against seven reference managers (Zotero, Mendeley, Paperpile, RefWorks, ReadCube Papers,
Citavi, EndNote) + Elicit, and against Zotero's ~15-plugin AI ecosystem. Full analysis, the gap ledger, and the
rationale for every disposition below live in **`callosum-integrated-comparison.md`** (kept with the project
docs). The organizing finding — *museum before crown jewel*: a user who cannot read a PDF and cite in Word never
reaches the auditing suite, so the table-stakes and the already-specced citation engine come first; the
differentiator tracks come after.

Each item was decided with the user; the **Decisions already made** lines are settled — do not re-litigate them,
they encode the hard part. Every AI-touching item is answerable to `PRINCIPLES.md` + `APPROACH-AVOIDANCE.md` and,
where it proposes or judges, the **Auditability-standard** gate already open in the backlog.

---

## How to process this file

1. **Fold each item into `INCREMENT-BACKLOG.md`** under the section named in its **Fold-into** line, preserving
   the existing bullet format (`- [ ] **Name** (`…detaildoc.md`): description with **bold constraints**.`).
2. **Create `future-tracks/` detail docs** (house format: Disposition · Architecture · Scope discipline · Gates ·
   Tests/acceptance · Output) for the three larger items flagged **needs a detail doc**: Curated Axis mode, the
   MCP server, and the library-level citation-context classifier. The smaller items are backlog bullets only.
3. **Honor the gates:** the 600-line-per-file rule; a security audit on each new surface (full-text search input,
   the MCP server, any write path); the Principles + A-A gate on every AI-assist item; `contradicted`-status and
   citation-context work must stay **signal, not verdict** (PRINCIPLES #2/#3, the THEORY contract).
4. **Sequencing:** Section A is build-now and slots alongside the citation-engine spine (the single highest
   priority, already specced). Section B is deferred behind critical functionality (word-processor integration is
   in flight). Sections C/D are records, not build orders.
5. Report the fold-in to the user, as usual. Do **not** touch the parked counsel-gated acquisition lane.

---

## A. Build now — table-stakes + axis refinements + two correctness fixes

### A1. Saved searches (persisted boolean/metadata filters)
*Fold-into: Theme 4 — App-wide (open). Priority: build-now, low cost.*
- **What:** let a user name and persist a combination of the **existing** library filters (the `item_type` /
  axis / tag / needs-review / statcheck-signal params + sort + the search scope), and recall it from the library
  header.
- **Decisions already made:** this is **distinct from axes** — it persists *metadata/boolean predicate state*
  (e.g. "author = X AND year > Y AND tag = Z"), which a semantic axis does not reproduce. It is filter
  persistence, not a new organizing primitive.
- **Acceptance:** a saved filter restores the exact predicate set and result list; saved filters are
  user-owned/editable; no new query semantics required (reuse the inc-89 search + existing facet params).

### A2. Library-wide per-paper citation counts
*Fold-into: My Publications follow-ups (extends the planned My-Pubs **Layer 3**). Priority: build-now, low cost.*
- **What:** surface a per-paper citation count on **all** library cards (and/or the Details pane), not only on
  the user's own publications. My-Pubs Layer 3 already plans per-paper OpenAlex counts for own-pubs; generalize
  that to the whole library via the OpenAlex/Crossref calls already in use.
- **Decisions already made:** it is a **displayed metadata field with a visible source**, never folded into a
  composite or used to silently rank (**PRINCIPLES #7 — no opaque scores**). Show the number + provenance; let
  the user sort by it explicitly if at all, never implicitly.
- **Acceptance:** counts render with their source and a fetch/cache path consistent with My-Pubs; missing/uncertain
  counts are shown honestly, not zero-filled.

### A3. Basic full-text PDF search box
*Fold-into: Theme 4 — App-wide (open). Priority: build-now, medium cost.*
- **What:** a literal/lexical full-text search box over already-extracted PDF text (the `chunks` text), e.g. a
  SQLite **FTS5** index, surfaced as a search field with hit highlighting.
- **Decisions already made:** this is **complementary to, not a replacement for, the internal semantic
  retrieval** (which stays surfaced through synthesis/axes). The axis-creation flow remains Callosum's *semantic*
  query surface; this box is the *exact-string* lookup users expect ("find 'ultimatum game' verbatim"). Keep both;
  do not conflate.
- **Acceptance:** exact-phrase and term search over extracted text returns paper + page hits; **input is validated**
  (security audit fires on the new query surface); performance acceptable on a personal library.

### A4. Plain-Markdown annotation export
*Fold-into: Theme 3 — Synthesis & Details (open). Priority: build-now, low cost.*
- **What:** export a paper's (or a selection's) highlights + notes to a `.md` file.
- **Decisions already made:** scoped to **plain Markdown** for now — directly on-brand for the leaveable/open
  ethos. Obsidian/Notion *bidirectional sync* is explicitly **not** in scope here (see C, deferred ecosystem
  integrations).
- **Acceptance:** annotations serialize with their page/quote context to readable Markdown; round-trips out of the
  app cleanly.

### A5. Color tags / ratings / flags
*Fold-into: Tags & keywords. Priority: build-now, low cost.*
- **What:** add a color attribute to tags and a simple rating/flag on papers, complementing the existing tag +
  star primitives.
- **Decisions already made:** organizational polish only; **tags remain provenance-stamped** (the inc-71/73
  mechanism is preserved) and become **pure labels** under the axis-primitive division below (A7) — not containers.
- **Acceptance:** color/rating render in list + Details; ratings are a user field, never an AI-assigned score.

### A6. Drag-and-drop deposit into axes
*Fold-into: a new bullet under the axes work / Theme 4. Priority: build-now, low–medium cost.*
- **What:** drag a paper (from the library list) onto an axis in the rail to add it.
- **Decisions already made:** the manual-add membership path **already exists** (the `+ add` / `✓ in axis` flow);
  this is a faster input method for it. For a **Keyword Axis** a drop is a *manual override* (pin regardless of
  score — rides the existing manual-assignment-survives-re-score guarantee); for a **Curated Axis** (A7) it is
  *add-and-position*.
- **Acceptance:** drop adds membership and persists; a keyword-axis drop is recorded as a manual override.

### A7. Curated Axis mode  **(needs a detail doc)**
*Fold-into: a new bullet under the axes work, with a `future-tracks/` detail doc. Priority: build-now, medium cost.*
- **What:** an axis populated **by hand** rather than by keyword scoring — the bounded home for the genuinely
  arbitrary, non-semantic working set (e.g. "the 12 papers for Aim 2, in citation order").
- **Decisions already made (all settled):**
  - **The umbrella term stays "Axis."** The curated variant is **never called a "folder"** (which would undersell
    it). Distinguish it by a **subtle aesthetic cue**, not a loud type label. If a word is needed internally:
    *Curated Axis* vs *Keyword Axis*.
  - A curated axis **hides/disables the keyword + scoring UI** and orders members **manually** (drag-to-reorder);
    a keyword axis orders by fit.
  - **Switching is bidirectional**, protected by the existing *manual-assignments-survive-re-scoring* guarantee
    (`axis_scoring.restore_manual_assignments`), so a flip **never ejects hand-picked members**:
    - **Keyword → Curated ("freeze"):** snapshot current members, drop live scoring, unlock manual ordering. This
      is the natural end of the thresholding workflow (scores are load-bearing only until the user is satisfied).
    - **Curated → Keyword:** allowed, with a **one-line warning** that it requires search terms and replaces the
      manual order with fit order (members preserved; ordering lost). Not blocked, not silent.
  - **Flat for now.** Nesting is deferred — and when it lands it must be **recursive *semantic* sub-axes** (the
    auto-axis method applied within a parent card; the planned My-Pubs subheading grouping is the prototype),
    **not** arbitrary manual folder-trees (those stay declined). See C.
  - **Tags demote to pure labels** (filter + provenance) so curated axes own manual working-set grouping and
    there is no tag/folder overlap. (This is the coherence condition; apply it app-wide.)
- **Acceptance:** a curated axis is creatable, hand-populated, manually ordered, and drag-droppable; freeze and
  the warned reverse both work with no membership loss; synthesis over a curated axis works unchanged (scope is
  by-selection — see A8); the keyword/curated distinction is a subtle visual cue, never a "folder" label.

### A8. Synthesis scope label at summarize
*Fold-into: Theme 3 — Synthesis & Details (open). Priority: build-now, low cost. Pairs with A9-bug.*
- **What:** at summarize time, show a one-line scope statement, e.g. "summarizing N papers; uncertain excluded."
- **Decisions already made:** synthesis already scopes **by the selected set** (membership-origin-agnostic), so a
  curated axis needs nothing special. A keyword axis carries cutoff ambiguity (assigned-only vs assigned + uncertain
  above the slider); the label makes "what fed this summary" explicit and reproducible — on-theme for verify-
  everything. Depends on the display fix below so *shown = summarized*.
- **Acceptance:** every summary states its scope count and whether uncertain members were included.

### A9. **[Fix]** Activate the dormant `contradicted` verification status
*Fold-into: Theme 3 — Synthesis & Details (open), as a correctness fix. Priority: build-now, normal — a completeness
gap in the existing verification spine, **not** a new feature.*
- **The bug:** the schema **already defines** `CITATION_MAPPING_STATUSES = ("verified", "weak", "contradicted",
  "unverified")` (`persistence/schema.py`), and the NLI CrossEncoder produces entailment / **contradiction** /
  neutral — but `summarization/verification.py` only extracts the *entailment* probability (`_entailment_confidence`
  picks the entailment index and discards contradiction), `_status()` only ever returns `verified / weak /
  unverified`, and the frontend renders only `verified / flagged`. So Callosum can flag a claim as
  *not-sufficiently-supported* but **cannot surface that a source actively *disagrees*** — the single most
  consequential class of citation error a verify-everything tool exists to catch.
- **Decisions already made:** scope it **narrowly** — read the contradiction probability, return `contradicted`
  from `_status()` when it dominates, and render it as a **distinct, visible state** (the source disagrees), with
  its quote/page like any other evidence. It is **signal, not verdict** (PRINCIPLES #2/#3) — "these passages
  contradict this claim, your call," never "this claim is false." A broader "make flagged/contrasted states
  prominent / hard-to-scroll-past" UX pass is a **reasonable follow-on**, recorded but not required for this fix.
- **Acceptance:** a sentence whose cited source contradicts it resolves to `contradicted` and renders distinctly
  with evidence; the entailment/contradiction extraction is covered by tests; no claim is pronounced true/false.

### A10. **[Fix]** Carry "hide uncertain" through to the library-pane axis-contents display
*Fold-into: My Publications follow-ups / axes. Priority: build-now, low — straight bug fix.*
- **The bug:** when "hide uncertain" is toggled (Settings or the per-axis button), the **count badge** switches
  from certain+uncertain to certain-only, but the **library-pane axis-contents display does not carry that logic
  through** — so the badge and the shown list disagree (the 27-shown-vs-badge-6 discrepancy).
- **Acceptance:** with "hide uncertain" on, the library-pane axis contents show certain-only, matching the badge;
  *shown = summarized* (so A8's scope label is honest).

---

## B. Deferred — fold into the longer-horizon tracks; queued behind critical functionality

### B1. Read-first / write-gated MCP server  **(needs a detail doc)**
*Fold-into: Longer-horizon future tracks (new entry + detail doc). Priority: deferred but queued — the one
genuinely-new architectural item; not cross-manager-prevalent, but the defensive moat.*
- **What:** expose Callosum's own MCP server so external agents (Claude/ChatGPT/Cursor/Gemini) use the library
  *through Callosum* rather than bypassing it. Without one, hosted/plugin bridges treat the reference manager as a
  dumb store and capture the provenance decisions; with an unsafe one, Callosum inherits Zotero's "full access to
  your computer" problem.
- **Decisions already made:** **read-first** (search, metadata, full-text, **grounded passage retrieval with page
  anchors** exposed freely); **all writes gated** through explicit confirmation + session undo (mirror
  llm-for-zotero's confirmation-cards-+-undo and cookjohn's toggleable writes); **every AI-originated write
  provenance/lineage-stamped** so "what did the agent change, on what evidence" stays auditable. Security audit +
  egress gate apply. Keeps Callosum the authority over bibliographic state and provenance.

### B2. Collaboration / shared libraries
*Fold-into: Settings & accounts (ties to "Account creation / login"). Priority: deferred — **not declined**.*
- **What:** opt-in shared libraries.
- **Decisions already made:** rides the **account + web surface already on the backlog** (auth + the plugin
  store), built later as an **opt-in** layer under the same **E2E/consent discipline** as any sync. It is a scope
  + architecture-weight question, not a values one — so deferred behind critical functionality, not declined.

### B3. OCR for scanned PDFs
*Fold-into: Library management & import. Priority: deferred — after word-processor integration.*
- **What:** Tesseract-based OCR fallback for image-only / garbage-OCR PDFs (also helps merge's preprint-vs-scanned
  case).
- **Decisions already made:** real packaging cost (Tesseract bundling implies desktop-distribution work), so it
  **rides the desktop-shell / packaging track**, after the word-processor work.

### B4. Library-level scite-style citation-context classifier  **(needs a detail doc)**
*Fold-into: Longer-horizon future tracks (new entry + detail doc). Priority: deferred — after Track C + A9.*
- **What:** classify whether a **citing** paper *supports / contrasts / mentions* a claim, across the citation
  graph — the scite analogue, done locally/openly and **grounded in retrieved passages**.
- **Decisions already made:** **distinct from** the gap-finder (which is citation-graph *discovery*) and from
  Track C (which evaluates *the user's own draft sentence*, not citing papers). Sequenced **after** Track C and
  after A9 (activating the contradiction stance), which capture much of the value first. Must follow the THEORY
  contract + the Auditability-standard gate (signal not verdict; stance from inspectable classification with
  verbatim quotes + confidence).

### B5. Mobile / tablet reading
*Fold-into: Packaging & distribution (post-V1). Priority: deferred — directional.*
- **What:** on-the-go reading.
- **Decisions already made:** the new **read mode** (inc 101) is the foundation; a **read-only mobile companion**
  is the plausible later step. Not a near-term build.

---

## C. Reserved / declined — record the decision; do not build, do not re-propose

- **Folders / collections hierarchy — RESOLVED as superseded by axes; not a gap.** A collection answers "which
  papers belong under this label"; an **axis answers it automatically** (define once, library self-populates,
  scored + overridable). Folder use-cases decompose onto existing primitives: *semantically coherent set* → axis;
  *arbitrary flat set* → tag; *"read this week"* → the needs-review/status filter. The **Curated Axis** (A7) is the
  manual-container path. Record so this is not re-raised as a missing feature.
- **Nesting — design decision recorded (deferred).** When nesting is built it must be **recursive *semantic*
  sub-axes** (auto-axis applied within a parent card; My-Pubs subheading grouping is the prototype). **Arbitrary
  manual folder-trees stay declined** — they are the hierarchy-creep the axis model deliberately avoids; the
  recursive-semantic form is the better answer to the "900 papers, hard to navigate" case. Infrastructure rides in
  free on the My-Pubs sub-grouping work.
- **Optional E2E-encrypted sync — reserved as a far-future seam only; not actively planned.** No clear sync target
  at present. If pursued later, must be **opt-in** and preserve the local-first default.
- **PDF translation — declined, out of scope.** Thin across the seven incumbents (a Zotero-ecosystem pattern), low
  on the cross-manager-prevalence signal.
- **Also consciously declined** (already implied by PRINCIPLES/A-A; recorded for completeness): cloud multi-agent
  "write my literature review"; website-bibliography publishing (WordPress/Drupal/Kerko); mind-mapping / Alfred /
  Todoist integrations; any embedded proprietary closed model; figure/table "data-from-charts" as a *casual*
  feature (only ever inside the human-verified MA workbench, provenance-gated).

---

## D. Open proposal — raised, not yet adopted (decide later)

- **Scratch / ephemeral axis.** Because carving an intersection is so cheap (a 3-way "fMRI disfigurement
  ultimatum" axis yields a plausible collection in moments), users will spawn throwaway axes that clutter the
  rail. A *scratch* axis that does not persist (or auto-expires) could be the natural complement to cheap
  generative axes. **Not adopted** — may be covered already by "just delete the throwaway axis" + the A3
  full-text box. Fold into **Open proposals**, decide later.

---

## E. Gates that apply across the above (summary)

- **600-line-per-file rule** on every touched module (split as inc 91 did for `papers.py`/`repository.py`).
- **Security audit** fires on: the full-text search input (A3), the MCP server + every write path (B1), and any
  account/web surface (B2).
- **Principles + A-A gate** on every AI-assist item; **Auditability-standard** gate (already open) on the
  citation-context classifier (B4) and any new evaluative AI surface.
- **Signal, not verdict** is load-bearing for A9 (`contradicted`) and B4 (citation-context): show the passages and
  their stance with evidence and confidence; never pronounce a claim true/false or a paper good/bad.
- **No opaque scores** (A2 citation counts): displayed metadata with visible source, never a silent composite.
