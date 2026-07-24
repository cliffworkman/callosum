The main gap is that Callosum currently has a rendering engine, but not yet a complete citation-authoring model.

Four immediate architectural observations
Grouped citations are already partially anticipated. The stored payload uses an items array, and the rendering request supports multiple items per citation. But insert_citation() always creates {"items": [record]}, and the UI only permits one selection. This means multiple citations should not require a total redesign, but it will require a real citation-instance schema rather than merely appending more CSL records.
The current style UI discards information the backend already exposes. The plugin can request the available style IDs, but the user interface asks the user to type an exact ID and locale into two modal text boxes.
The bibliography implementation is presently a data-loss hazard. On refresh, Callosum selects everything from the bibliography bookmark to the end of the document and deletes it before rebuilding the bibliography. Any legitimate text placed after the bibliography can therefore be destroyed. The README consequently tells users to keep everything above it, but the software should enforce a bounded managed range rather than rely on that convention.
Flattening is irreversible and immediately executed. The current command performs the operation first and only then reports what happened. Zotero explicitly warns users that unlinking is irreversible, while EndNote's equivalent creates a separate plain-text copy instead of modifying the working document in place.
Priority 0: correctness, safety, and expected citation mechanics

These should precede further AI functionality.

1. Replace the Add Citation flow with a unified citation composer

The current two-stage flow asks for a query, waits for submission, and then opens a separate result list. The replacement should provide:

Live results while typing, with a short debounce
Search across author, title, year, DOI, venue, keywords, abstract, and citekey
Full keyboard navigation
Recently cited items
Items already cited in the document
Optional collection, tag, and project filters
A persistent citation assembly area using removable "pills" or rows
Repeated searching so several sources can be added before insertion
A preview of the final rendered citation
An explicit Insert button

Zotero's citation dialog searches live as the user types, prioritizes already-cited items, supports multiple items, and exposes keyboard-first operation. Paperpile and Mendeley use similar multi-item composer models.

The deterministic library-search composer and Callosum's semantic "Suggest citation" function should remain separate modes. Mixing them would make ordinary citation insertion unpredictable.

2. Add true grouped citations

Users need to create and edit forms such as:

(Smith, 2020; Workman et al., 2021)
[2,4-6]
Several references within one footnote
Several references with different locators and prefixes

Required operations include:

Add and remove items
Reorder items manually
Restore style-defined sorting
Preview rendered ordering
Merge an adjacent citation into the current group
Split a grouped citation

Zotero, Mendeley, RefWorks, Paperpile, and EndNote all treat grouped citations as baseline functionality. EndNote permits up to 250 references in one citation, although Callosum does not need such an extreme initial target.

3. Introduce citation-instance metadata

Each item inside a citation needs metadata separate from the library record:

item_id
locator_type
locator_value
prefix
suffix
suppress_author
author_only or narrative
suppress_date
manual_sort_position
custom_override

Do not write locators or prefixes into the underlying paper's CSL metadata. They describe this occurrence of the citation, not the work itself.

This schema should also be versioned so future adapters can migrate old documents. The current approach embeds complete CSL records inside the ReferenceMark name. Before grouped citations are enabled, test the practical size and reliability limits of that strategy because several full CSL records may create extremely large mark names.

4. Add Edit Citation and Delete Citation

Selecting or placing the cursor inside an existing Callosum citation should open the same composer used for insertion, populated with the citation's current items and options.

Users must be able to:

Add or remove references
Change locators
Change prefixes and suffixes
Suppress author or date
Reorder grouped items
Delete the entire citation safely
Open the cited record in Callosum
Revert manual overrides

The present action registry has no edit or delete operation. Zotero, Mendeley, RefWorks, and EndNote all expose editing from the existing citation.

5. Support locators, prefixes, suffixes, and narrative citations

At minimum:

Page
Page range
Chapter
Section
Paragraph
Figure
Table
Volume
Issue
Line
Verse
Timestamp or time range
Generic "other"

Also support:

Prefix, such as see, cf., or explanatory prose
Suffix
Suppress author
Suppress date
Narrative form, such as Workman et al. (2021)
Per-item options inside grouped citations

These are routine features across Zotero, Mendeley, Paperpile, RefWorks, and EndNote.

6. Redesign bibliography storage and placement

Replace the "bookmark to document end" implementation with a bounded managed bibliography object.

The user should be able to:

Insert the bibliography at the cursor
Move it without corrupting it
Delete and reinsert it
Toggle automatic bibliography generation
Change or suppress the heading
Use a bibliography without requiring it to remain at the document end
Detect and repair a missing or damaged bibliography field
Preserve all document content outside the managed range

The initial implementation should treat the bibliography as one explicitly bounded live field or section, not an unbounded tail of the document.

7. Make flattening safe

The command should become something like "Prepare submission copy" and provide:

An explicit irreversible-action warning
Citation count and bibliography count
Save-as-copy by default
Optional filename suggestion such as manuscript-static.odt
A checkbox to retain hyperlinks
A checkbox to remove Callosum document metadata
A post-operation integrity check
Undo when technically possible

Directly flattening the only working copy should require a second deliberate choice.

8. Add transactions, rollback, and document repair

Refresh currently updates citation marks sequentially and then rebuilds the bibliography. A failure halfway through could leave a partially transformed document.

Each document-level operation should:

Validate all stored citation payloads.
Build the complete render result before modifying the document.
Create a recoverable snapshot or undo group.
Apply all changes.
Verify that the expected marks still exist.
Roll back or preserve the original if verification fails.

Add a "Document diagnostics" or "Repair Callosum citations" command that reports:

Malformed fields
Duplicate citation IDs
Orphaned records
Missing bibliography
Bibliography outside its expected range
Unsupported schema versions
Fields damaged by copy/paste or Track Changes
Citations whose library records have changed or disappeared

Citavi includes a repair operation that reconstructs its document fields, while Zotero and RefWorks document specific field corruption and Track Changes risks.

Priority 1: full competitor parity
9. Build a real style manager

The plugin should not require users to know CSL IDs.

**Started in increment 365 (2026-07-24):** the shared local catalog now searches bundled styles by descriptive
metadata, distinguishes dependent/independent styles, previews representative fictional references through real
citeproc, and persists favorites, recents, locale, and application default. Settings provides the full manager;
LibreOffice uses the same catalog and lets users open it. Blank documents inherit the application default while
existing documents retain their embedded style/locale. That increment left repository installation, local/URL
import, validation/update handling, visual/source editing, duplication, and custom export open.

**Local import shipped in increment 366 (2026-07-24):** Settings installs a bounded local `.csl` only after
structural checks and real citeproc validation. Exact duplicates and changed canonical updates are distinguished;
bundled styles cannot be replaced. Personal and dependent styles become first-class in the shared catalog,
preferences, previews, rendering APIs, and Writer. Still open: removal/export/portability, repository search,
explicit URL import, full-schema/update provenance, duplication, and visual/source editing.

**Removal/export/portability shipped in increment 367 (2026-07-24):** personal styles download as valid `.csl`
files carrying a constrained Callosum id marker, so an export reinstalled on another device retains the exact
document-facing style id. New unmarked imports use deterministic canonical-id hashes. Removal is explicit, warns
that existing documents require reinstallation, refuses bundled/application-default styles and installed
parents, and cleans local Favorites/Recent state. Still open: repository search, explicit URL import, full-schema/
update provenance, duplication, and visual/source editing.

**Repository and URL import shipped in increment 368 (2026-07-24):** Settings searches the public CSL/Zotero
catalog on explicit submit, matching journal/style title, acronym, citation format, and discipline locally after
one bounded fixed-host catalog fetch. A result installs through the existing personal-style validator; dependent
styles fetch and preflight their bounded canonical parent chain before any write. **Import URL** is a separate
explicit HTTPS-only action with private/local DNS and connected-peer rejection, guarded redirects, byte/depth
bounds, and the same duplicate/update confirmation. Still open: full upstream-schema/update provenance,
duplication, and visual/source editing.

**Schema/provenance/update/duplication shipped in increment 369 (2026-07-24):** all imports validate locally
against the official CSL 1.0.2 RELAX NG schema and Schematron macro rules before citeproc. Personal styles retain
their local-file, repository, URL, or copy source plus install/update/check timestamps in a fail-soft local
sidecar. Remote update checks run only on explicit request, include installed custom parents, and apply the exact
preflighted chain after confirmation. **Duplicate** gives bundled, independent, or dependent styles a new
standalone personal identity and preserves source lineage. Still open: visual/source editing.

**Source editing shipped in increment 370 (2026-07-24):** independent personal styles open in a two-pane source
editor with a rendered fixed-fictional-example draft preview. Bundled and dependent styles use **Duplicate to
edit**, producing an independent copy before the editor opens. Save preserves the installed and canonical ids,
repeats official schema, macro, and citeproc validation, records the local edit, writes atomically, and rejects a
stale exact revision rather than overwriting it. This completes Priority 1 item #9.

Required functionality:

Search styles by journal, publisher, discipline, acronym, or style name
Favorites and recent styles
Installed styles
Style preview using representative references
Language and locale selector
Search and install from the CSL repository
Import a local .csl file
Import by URL
Validate imported CSL
Explain validation failures
Detect duplicates and style updates
Open the selected style in a visual or source editor
Duplicate a style before editing
Export custom styles
Distinguish dependent and independent CSL styles
Document-level versus application-default style settings

Mendeley supports searching, installing, and importing custom styles by URL. Paperpile and SmartCite support thousands of searchable styles and custom CSL uploads. RefWorks exposes favorites, recent styles, personal styles, institutional styles, and CSL styles.

The visual style editor belongs primarily in the Callosum application, not inside the LibreOffice modal system. The plugin should launch or communicate with it.

10. Support note styles properly — COMPLETE (incs 362–364, 371–373)

Callosum now supports:

Footnote citations
Endnote citations where supported
Style-controlled note placement
Multiple sources in one note
Prefix and suffix prose in notes
Ibid and subsequent-note behavior through citeproc
Switching an existing document between note and in-text styles
Detection of citations inserted in the wrong context
Tracked-change-aware placement conversion that preserves unrelated redlines and refuses managed-range conflicts

Zotero, RefWorks, Paperpile, EndNote, Citavi, and SmartCite all support at least some note-based workflows.

11. Add bibliography editing controls

Users should be able to:

Include uncited works
Exclude particular cited works, such as personal communications
Change the bibliography heading
Divide bibliographies into categories
Create chapter or section bibliographies
Create a full-document bibliography alongside chapter bibliographies
Hyperlink citations to bibliography entries
Optionally hyperlink titles or DOIs
Update or freeze only the bibliography

Zotero permits inclusion of uncited items and exclusion of cited items. EndNote supports categorized bibliographies. Citavi and SmartCite support chapter or section bibliographies.

12. Add a persistent "Citations in this document" panel

This should list:

Every unique cited work
Number of occurrences
Locations in the manuscript
Citation groups containing the work
Missing or orphaned records
Retraction or correction status
Metadata conflicts
First and most recent citation
Click-to-navigate behavior
Search within document citations

RefWorks now provides a "My Citations" view that lists cited references, occurrence counts, and navigation to individual citations.

13. Add refresh and performance controls

For large manuscripts:

Automatic refresh on insertion
Manual refresh mode
Pause formatting
Pause bibliography updates separately
Refresh selected citation
Refresh current section
Refresh citations only
Refresh bibliography only
Visible dirty-state indicator
Progress and cancellation
Incremental rendering where possible

RefWorks exposes separate formatting and bibliography toggles specifically to reduce processing costs. SmartCite similarly recommends disabling automatic bibliography updates for large documents.

14. Improve portability and collaboration

Callosum's embedded CSL records give it a useful starting point. Expand that into:

A document-level traveling citation library
Clear distinction between linked, locally copied, and orphaned references
Relink an orphaned item to a Callosum library record
Import document references into the user's library
Preserve collaborators' citations even when their libraries differ
Record which metadata version produced the rendered citation
Resolve conflicts between embedded metadata and current library metadata
Optional "use document version" versus "update from library"
Cross-platform schema shared by LibreOffice, Word, and Google Docs

Zotero exposes orphaned citations, Paperpile keeps document-specific copies for collaboration, SmartCite indexes references embedded by collaborators, and EndNote embeds a "Traveling Library" in Word documents.

15. Add journal-abbreviation controls

Support:

Journal abbreviation metadata
MEDLINE or discipline-specific abbreviation lists
Prefer library abbreviation versus generated abbreviation
Preview and validation
Unknown-abbreviation warnings

Zotero exposes a document preference for MEDLINE journal abbreviations.

16. Accessibility and keyboard operation

The citation composer should be completely usable without a mouse:

Configurable keyboard shortcuts
Correct tab order
Screen-reader labels
Focus trapping in modal dialogs
Arrow-key result navigation
Enter to add, Enter again to insert
Shortcut to edit the citation at the cursor
Escape to cancel without mutation
High-contrast and scaling support

Zotero has extensive keyboard support, while RefWorks has repeatedly expanded keyboard and screen-reader accessibility in its citation tools.

Priority 2: Callosum-specific leapfrog features

This is where Callosum should stop imitating competitors.

17. Expand Suggest Citation into an evidence-aware composer

Current suggestions already provide stance, match score, and a quotation preview.

Extend that with:

Select several suggested sources at once
Expand the full matched passage
Open the passage in the PDF
Display page number and section
Compare supporting, contrasting, and merely mentioning evidence
Filter by study type, publication year, tag, or collection
Explain why a source was retrieved
Warn when the evidence only weakly supports the sentence
Insert the appropriate page locator automatically, but only after user confirmation
Record the evidence passage associated with the citation for later auditing

The critical design principle should remain: no source is inserted merely because a model ranked it highly.

18. Manuscript-level citation coverage analysis

Add an optional scan that identifies:

Empirical claims without citations
Citations attached to several logically distinct claims
Citations whose evidence appears unrelated to the nearby sentence
Overreliance on one source, author, lab, journal, or theoretical camp
Excessive self-citation
Long stretches of uncited factual prose
Review articles cited where primary evidence may be preferable
Sources cited secondhand
Claims supported only by retracted or corrected papers

This should be an audit surface, not an automatic correction system.

19. Citation integrity preflight

Before submission, inspect every cited work for:

DOI resolution
Metadata completeness
Duplicate references
Retractions, expressions of concern, and corrections
Preprint versus version-of-record relationships
Missing page or article numbers
Impossible years, volumes, or issues
Broken URLs
Inconsistent author names
Uncited bibliography entries
Cited items missing from the bibliography
Manual citation edits that will be overwritten
Citation style validation failures

This would align the plugin with Callosum's broader open-science and reference-verification purpose rather than treating citations as decorative formatting.

20. Citavi-like insertion of quotations and knowledge items

Citavi's major differentiator is that it can insert saved quotations, thoughts, core statements, category structures, and their citations directly into Word.

Callosum could do this better by allowing users to insert:

A highlighted PDF passage
The passage plus citation
A paraphrase note plus citation
A structured evidence card
A saved methodological detail
A claim and its supporting or contrasting evidence
A quotation with an automatically populated locator
A quotation with traceability back to the PDF annotation

This is a natural extension of Callosum's evidence-snippet architecture.

21. Open-science statement insertion

CRediT insertion already proves the basic pattern. Extend it to:

Data availability statements
Code availability statements
Preregistration statements
Materials availability
Funding disclosures
Conflict-of-interest statements
Ethics approval statements
Author contribution statements
Reporting-guideline declarations
AI-use disclosures

These should be generated from structured Callosum records, previewed, and explicitly inserted as static manuscript text.

22. Cross-manager document conversion

Eventually support detection and conversion of:

Zotero fields
Mendeley fields
EndNote fields
Microsoft Word native citations
Plain-text citations with recoverable identifiers
Existing bibliographies imported into Callosum

EndNote already converts Word and legacy Reference Manager citations, and RefWorks can import references from Word and PDF bibliographies.

This is valuable, but it should follow native citation reliability.

Features I would deliberately defer

These competitors offer them, but they should not displace the core roadmap:

A full visual CSL editor inside LibreOffice
Figure and table management like EndNote
Plagiarism or generic AI-text detection
Journal recommendation from inside the plugin
Automatic insertion of sources without confirmation
Conversion from every historical reference-manager format
Real-time semantic suggestions running continuously as the user types prose

The first serious milestone should be:

Bounded and safe bibliography fields
Safe flatten-to-copy workflow
Unified live-search citation composer
Grouped citations
Edit and delete existing citations
Locators, prefixes, suffixes, and narrative citations
Searchable style manager with CSL import
Footnote and endnote styles
Document diagnostics and repair
Tests covering copy/paste, undo, Track Changes, document reopening, corrupted marks, and large manuscripts

Once those exist, Callosum would have Zotero-level basic authoring mechanics while retaining functionality its major competitors largely lack: evidence-backed semantic citation suggestion, stance classification, citation integrity checking, and open-science statement generation.
