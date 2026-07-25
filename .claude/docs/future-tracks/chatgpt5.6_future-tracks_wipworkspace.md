You are working in the Callosum repository, a local-first, open-science-focused reference manager for scholarly research.

Your task is to design and implement an MVP Work in Progress system, abbreviated WIP, that extends Callosum from managing research inputs to managing research products under active development.

The feature must preserve Callosum's existing interaction model wherever possible.

The central product idea is:

* Library contains research sources.
* WIP contains research products being created.
* Both are browsable entity collections.
* Both use the same navigation grammar.
* They remain distinct entity types with distinct metadata, actions, detail schemas, and open-tab experiences.

Do not implement manuscripts as a subtype of library reference merely because both appear in a card browser.

Instead, generalize or reuse the existing browser infrastructure so Library references and WIP manuscripts can share interaction patterns without sharing inappropriate data models.

The primary design principle is:

The interaction model of Library should subsume WIP, but the reference data model should not subsume the manuscript data model.

## 1. Required working method

Before editing code:

1. Inspect the repository structure.
2. Read the current architecture documentation, backlog, future-track documents, frontend conventions, backend conventions, migration system, test patterns, and filesystem code.
3. Identify how the current application implements:

   * Top-level navigation
   * Library cards
   * Card and list views
   * Item selection
   * Multi-selection
   * Search
   * Filtering
   * Sorting
   * Details panes
   * Context menus
   * Open document tabs
   * PDF tabs
   * Tab persistence
   * Library references
   * Local files
   * Watched folders
   * Filesystem events
   * Tool runs
   * Findings or warnings
   * Activity history
4. Produce a concise implementation plan grounded in the actual repository.
5. Then implement the feature.

Do not stop after producing the plan.

Continue through implementation, migrations, tests, and documentation unless a genuine repository-level blocker prevents completion.

Avoid broad unrelated refactors.

## 2. Top-level information architecture

Add WIP as a second top-level browsing mode immediately after Library.

The relevant navigation should conceptually become:

```text
Library | WIP
```

Do not place WIP under Work, Cite, or another tool panel.

WIP is an application mode, not a single tool.

Switching between Library and WIP should preserve the overall application geometry and interaction model.

The user should retain familiar behavior for:

* Browsing cards or rows
* Selecting entities
* Opening entities
* Searching
* Filtering
* Sorting
* Using a details pane
* Using context menus
* Opening tabs
* Closing, pinning, reordering, and restoring tabs
* Keyboard navigation where already supported

Library and WIP should retain independent view state where practical.

For example:

```text
Library
  Search: facial anomaly
  Filter: has PDF
  Sort: year descending

WIP
  Filter: drafting
  Sort: last modified
```

Switching modes should not unnecessarily reset search, filters, sort order, scroll position, or selection state.

## 3. Shared browser shell

Identify the existing Library browser shell and generalize it only as much as necessary to support multiple browsable entity types.

A useful conceptual contract is:

```text
BrowsableEntity
  Card representation
  Details representation
  Search fields
  Sort fields
  Filter fields
  Context actions
  Open-tab representation
```

References and manuscripts should both participate in this interaction contract.

Do not force manuscript-specific fields into reference components through scattered conditional logic if a clean entity-type adapter, schema, registry, or renderer abstraction is more appropriate.

Prefer a structure conceptually similar to:

```text
BrowserShell
  mode="library"
  entityType="reference"
```

and:

```text
BrowserShell
  mode="wip"
  entityType="manuscript"
```

Adapt this to the actual repository architecture.

Avoid duplicating the entire Library browser implementation for WIP.

Also avoid over-generalizing the whole frontend into a large abstract framework if a smaller shared layer is sufficient.

## 4. WIP visual mode

WIP should feel like a distinct operating mode while preserving Library muscle memory.

Preserve:

* Overall application frame
* Card dimensions
* List geometry
* Typography hierarchy
* Search placement
* Details-pane location
* Selection behavior
* Tab behavior
* Core keyboard interactions

Differentiate:

* Mode accent treatment
* Card surface or border treatment
* Icons
* Metadata hierarchy
* Empty states
* Details-pane header
* Context actions
* Manuscript tab header
* Progress and warning indicators

The visual difference should be visible at a glance without changing the fundamental layout.

Avoid both failure modes:

1. WIP looks so different that existing Library muscle memory no longer transfers.
2. WIP looks so similar that users cannot tell whether they are manipulating a published source or an unpublished manuscript.

Use the application's existing design system.

Do not create a parallel visual language.

## 5. Manuscript Workspace entity

A WIP card represents a persistent Manuscript Workspace.

A Manuscript Workspace is not merely a folder path.

It should minimally support:

* Stable internal ID
* Display title
* Automatically derived title
* Optional user title override
* Root directory path
* Discovery source
* Discovery mode
* Workspace state
* Manuscript type
* Current stage
* Optional target journal
* Optional deadline
* Optional notes
* Created timestamp
* Updated timestamp
* Last filesystem activity timestamp

Use a stable UUID or equivalent persistent identifier.

Do not use the filesystem path as the primary identity.

A folder may be renamed, moved, temporarily unavailable, or remounted. The Manuscript Workspace should persist.

Workspace state should support at least:

* Active
* Paused
* Archived
* Missing

Renaming the manuscript inside Callosum must not rename the local folder by default.

## 6. WIP discovery and watched folders

Allow users to add one or more WIP watch roots.

Each watch root must independently support one of two discovery modes.

### Mode A: Selected folder is one manuscript

Example:

```text
~/Research/Price of a Scar/
```

The selected folder becomes one Manuscript Workspace.

### Mode B: Immediate subfolders are manuscripts

Example:

```text
~/Research/WIPs/
  Price of a Scar/
  Aesthetics and Truthiness/
  Facial Anomaly Meta-Analysis/
```

Each immediate child directory becomes one Manuscript Workspace.

Do not recursively interpret every nested folder as a separate manuscript by default.

Each watch root should support:

* Local path
* Discovery mode
* Enabled or paused state
* Optional excluded child folders
* Created timestamp
* Updated timestamp
* Last scan timestamp
* Last scan result or error state

Users should be able to configure multiple roots with different discovery modes.

Discovery must be idempotent.

Repeated scans must not create duplicate workspaces.

Do not automatically delete a Manuscript Workspace when its folder disappears.

Mark it missing and preserve its metadata.

If the folder later reappears at the same normalized path, reconnect it.

## 7. WIP landing view

The WIP mode should populate the same general card or list surface used by Library.

A manuscript card should display manuscript-relevant state, not bibliographic metadata.

At minimum, show:

* Display title
* Current stage
* Last modified or last filesystem activity
* Section-progress summary
* Open-task count
* Tool-check status summary
* Missing-file or missing-folder warning where applicable

Useful optional fields include:

* Manuscript type
* Primary file
* Target journal
* Deadline
* Unresolved finding count
* Stale tool-run count
* Linked reference count

A card might conceptually summarize:

```text
Price of a Scar

Drafting
Results: Needs revision
Discussion: Drafting

3 open tasks
1 stale check
Modified 18 minutes ago
```

Do not show misleading completion percentages unless they are derived only from explicit user-managed section statuses and clearly labeled.

Do not use AI to infer manuscript completion in this MVP.

## 8. WIP search, sorting, and filters

Reuse the existing Library search, sort, and filter interaction patterns.

Add manuscript-specific search fields and facets where appropriate.

Support at least:

* Title search
* Stage
* Manuscript type
* Target journal
* Deadline
* Modified date
* Has open tasks
* Has unresolved findings
* Has stale checks
* Missing folder
* Missing primary file
* Active, paused, archived, or missing state

Useful sort options include:

* Title
* Last modified
* Stage
* Deadline
* Created date
* Open-task count
* Unresolved finding count

Do not display irrelevant Library-specific filters in WIP.

Use mode-specific filter schemas or registries rather than hiding large numbers of reference controls through ad hoc CSS.

## 9. Selection and details pane

Selecting a manuscript in WIP should populate the existing details-pane region just as selecting a reference does in Library.

The details pane should share infrastructure but use a manuscript-specific schema.

Do not implement manuscript details by rendering all reference fields and making irrelevant cells invisible.

Instead, use an entity-specific details schema or component registry.

Conceptually:

```text
DetailsPane
  entityType="reference"
  schema=referenceDetailsSchema
```

```text
DetailsPane
  entityType="manuscript"
  schema=manuscriptDetailsSchema
```

The manuscript details pane should contain compact, directly editable information such as:

* Overview
* Current stage
* Manuscript type
* Target journal
* Deadline
* Primary file
* Section progress
* Open tasks
* References
* Tool checks
* Recent activity
* Tags or notes if shared systems already exist

Shared components such as tags, notes, files, or related entities may be reused where semantically appropriate.

The details pane is a summary and editing surface.

It is not the full Manuscript Workspace.

## 10. Opening a manuscript

Opening a manuscript from WIP should behave like opening a PDF from Library.

Use the existing global tab system.

Opening a reference may create a PDF or document tab.

Opening a manuscript must create a manuscript-workspace tab.

Conceptually:

```text
Tab
  type="pdf"
  entityId="reference-123"
```

```text
Tab
  type="manuscript-workspace"
  entityId="manuscript-456"
```

The manuscript tab should support the same tab-level behaviors already available where appropriate:

* Open
* Close
* Pin
* Reorder
* Restore
* Switch by keyboard
* Persist open state if the application already restores tabs

Do not embed manuscript workspace state into a PDF viewer abstraction if the tab manager can instead host multiple tab content types.

## 11. Manuscript Workspace tab

The opened manuscript tab should display the accumulated information, tracked state, and provenance associated with the manuscript.

It should answer:

What is the state of this manuscript right now, and what should the user work on next?

Provide coherent views or panels for:

* Overview
* Structure
* Tasks
* Files
* References
* Checks
* Activity

These may be implemented as subtabs, sections, a dashboard, or a hybrid based on the current frontend architecture.

A strong default layout would foreground:

* Current stage
* Primary file state
* Section progress
* Open tasks
* Stale or unresolved checks
* Recent activity

Do not attempt to build a full manuscript text editor in this MVP.

The manuscript workspace coordinates the research process around the manuscript. It does not need to replace Word, LibreOffice, Markdown editors, or LaTeX editors.

## 12. Manuscript stages

Provide a default stage vocabulary:

* Idea
* Planning
* Data collection
* Analysis
* Drafting
* Internal review
* Preprint
* Submitted
* Revise and resubmit
* Accepted
* Published
* Paused
* Abandoned

Use stable machine-readable values and human-readable labels.

Design storage so custom stages can be supported later.

Full custom-stage management is not required unless it fits the existing settings architecture cleanly.

Changing stage should create an activity event.

## 13. Manuscript files

A workspace may contain several manuscript-related files and directories.

Support file roles including:

* Primary manuscript
* Supplement
* Cover letter
* Response to reviewers
* Reporting checklist
* Figure
* Table
* Analysis output
* Other

The user must be able to designate one file as the primary manuscript.

Do not assume that the newest DOCX is canonical.

Callosum may suggest likely candidates, but the user must confirm or override the choice.

Track at minimum:

* Manuscript ID
* File ID
* Path
* File role
* Primary-file flag
* Existence state
* File size
* Modified timestamp
* Whole-file hash
* Extracted-text hash where available
* Last scanned timestamp
* Extraction status
* Extraction error where applicable

Only one active primary manuscript file may exist per manuscript.

Reuse existing text extraction and file handling.

Do not add weak one-off parsers merely to claim support for more formats.

Support the formats already handled reliably by the repository.

Keep the model extensible to DOCX, Markdown, LaTeX, plain text, and other formats where current infrastructure permits.

## 14. Section tracking

Provide section-level workflow tracking.

Default empirical-manuscript sections should include:

* Title page
* Abstract
* Introduction
* Method
* Results
* Discussion
* References
* Tables
* Figures
* Supplement
* Open practices statement
* Author contributions
* Data availability statement

Each section should support:

* Stable ID
* Name
* Display order
* Status
* Optional notes
* Optional content-detected state
* Created timestamp
* Updated timestamp

Default statuses:

* Not started
* Outlined
* Drafting
* Complete
* Needs revision
* Under review
* Approved
* Not applicable

Users must be able to:

* Add a custom section
* Rename a section
* Reorder sections
* Change status
* Mark a section not applicable
* Delete custom sections safely

Do not automatically mark a section complete because matching text or a heading exists.

If heading detection is feasible through existing extraction, represent:

```text
Content detected
```

as separate from:

```text
Status: Complete
```

Changing a section status should create an activity event.

## 15. Manuscript templates

Provide at least one default template for a standard empirical article.

Structure the data model so future templates can support:

* Registered reports
* Systematic reviews
* Meta-analyses
* Methods papers
* Commentaries
* Grant proposals
* Dissertation chapters

Apply a template when creating a Manuscript Workspace, while allowing later customization.

A complete template editor is outside the MVP.

## 16. Tasks

Add manuscript-scoped tasks.

A task may optionally be linked to:

* The manuscript generally
* A section
* A file
* A reference
* A tool finding

Task fields should include:

* Stable ID
* Manuscript ID
* Title
* Optional description
* Status
* Optional due date
* Optional section ID
* Optional file ID
* Optional reference ID
* Optional finding ID
* Created timestamp
* Updated timestamp
* Completed timestamp

Default statuses:

* Open
* In progress
* Blocked
* Complete
* Deferred
* Cancelled

Support task creation, editing, completion, reopening, and deletion where safe.

Task creation, status changes, completion, and reopening should create activity events.

Do not implement task dependencies, collaborators, recurring tasks, or notifications in this MVP.

## 17. Manuscript-reference relationships

A Manuscript Workspace should link to existing Callosum Library references without duplicating the underlying reference record.

Support relationship states including:

* Cited
* Possibly cited
* Background reading
* To cite
* Rejected for use
* Needs verification

A relationship should support:

* Manuscript ID
* Reference ID
* Relationship state
* Optional notes
* Created timestamp
* Updated timestamp

Provide basic UI for viewing, adding, removing, and changing these relationships.

This is the main bridge between Library and WIP.

## 18. Cross-mode navigation

Library and WIP should be distinct modes but part of one research ecosystem.

From a Manuscript Workspace, the user should be able to open a linked Library reference.

That reference should open through the normal Library PDF or document-tab workflow in the same global tab system.

Where practical, a Library reference should also expose reverse manuscript relationships such as:

```text
Used in 3 WIPs
  Price of a Scar
  Facial Anomaly Meta-Analysis
  Grant Renewal
```

For the MVP, reverse links may appear in the Library details pane rather than directly on every card if card-level display would overcrowd the interface.

The underlying relationship must be bidirectionally queryable even if the first UI exposes it only from WIP.

Do not duplicate reference metadata inside manuscript records.

## 19. Context actions

Reuse the existing context-menu framework with entity-specific actions.

Reference actions may remain unchanged.

Manuscript actions should include, where appropriate:

* Open workspace
* Open primary file
* Reveal folder
* Change stage
* Add task
* Run check
* Create checkpoint
* Pause tracking
* Archive manuscript
* Edit title
* Rescan files

Do not show reference-specific actions on manuscript cards unless they genuinely apply.

Do not implement controls that appear active but are not connected.

## 20. Snapshots and content identity

Implement lightweight manuscript snapshots.

A snapshot should represent manuscript content at a meaningful moment such as:

* Tool execution
* Manual checkpoint
* Stage transition
* Submission
* Resubmission
* Primary-file replacement

A snapshot should minimally support:

* Snapshot ID
* Manuscript ID
* Manuscript file ID
* Whole-file hash
* Extracted-text hash
* Optional section hashes
* Extracted text or reference to extracted text
* Snapshot reason
* Created timestamp
* Associated tool-run ID where applicable

Use deterministic hashes.

Do not automatically duplicate complete unpublished manuscript files unless the repository already has an explicit full-file versioning convention.

Avoid duplicate snapshots for identical content unless a separate event has meaningful provenance value.

## 21. Tool-run provenance

Extend or reuse the existing Callosum tool-run infrastructure so a run can be associated with an exact manuscript version.

A tool run should be able to record:

* Manuscript ID
* Manuscript file ID
* Snapshot ID
* Whole-file hash
* Relevant extracted-content hash
* Tool identifier
* Tool version
* Callosum version where available
* Execution timestamp
* Parameters
* Run status
* Result summary
* Structured result data or result location

Do not build a manuscript-only parallel execution system if a general tool-run model already exists.

Extend the shared model or create a clean association table.

The integrity rule is:

Every analytical claim about a manuscript must point to the exact content that licensed it.

Do not display only:

```text
Statcheck completed
```

Display meaning equivalent to:

```text
Statcheck ran against manuscript snapshot X at time Y.
```

## 22. Tool-run validity and staleness

The UI must distinguish:

* Current
* Current with unresolved findings
* Potentially stale
* Stale

Suggested semantics:

### Current

The content relevant to the tool has not changed, and there are no unresolved findings.

### Current with unresolved findings

The relevant content has not changed, but findings remain open, acknowledged, or deferred.

### Potentially stale

The file changed, but Callosum cannot determine whether the tool-relevant content changed.

### Stale

The relevant content changed, the primary file was replaced, or the run no longer matches current manuscript content.

Prefer scoped invalidation when technically justified.

For example, if statcheck examines Results and only Acknowledgments changed, the run may remain current if Callosum can reliably isolate and hash Results content.

If section extraction is uncertain, fall back to conservative whole-content invalidation.

Do not claim section-level certainty that the extraction layer cannot support.

## 23. Findings

Reuse or extend any shared finding, warning, or review-item system already present.

A manuscript-linked finding should support:

* Finding ID
* Tool-run ID
* Manuscript ID
* Manuscript file ID
* Optional section ID
* Optional reference ID
* Finding type
* Severity
* Summary
* Details
* Text anchor or surrounding context
* Status
* Created timestamp
* Updated timestamp
* Resolution timestamp
* Resolution notes

Finding statuses:

* Open
* Acknowledged
* Resolved
* Dismissed
* False positive
* Deferred
* Superseded

Keep finding disposition distinct from tool-run validity.

A stale run may contain resolved findings.

A current run may contain unresolved findings.

## 24. Activity timeline

Provide an append-only manuscript activity timeline.

Activity types should include at least:

* Manuscript discovered
* Manuscript renamed
* Stage changed
* Primary file selected
* File added
* File missing
* File restored
* Section status changed
* Task created
* Task completed
* Task reopened
* Reference linked
* Reference relationship changed
* Tool run started
* Tool run completed
* Tool run failed
* Tool run marked potentially stale
* Tool run marked stale
* Finding status changed
* Manual checkpoint created

Each event should support:

* Manuscript ID
* Event type
* Timestamp
* Human-readable summary
* Structured metadata where useful
* Related entity type
* Related entity ID

Activity events are an audit layer.

Do not use them as the only source of truth for current state.

## 25. Backend API

Follow existing API and service conventions.

The implementation will likely require operations for:

* Listing WIP watch roots
* Creating a watch root
* Updating a watch root
* Pausing or resuming a watch root
* Removing a watch root without deleting discovered workspaces
* Scanning a watch root
* Listing manuscripts
* Reading a manuscript
* Updating manuscript metadata
* Pausing or archiving a manuscript
* Listing manuscript files
* Assigning file roles
* Selecting a primary file
* Listing and editing sections
* Listing and editing tasks
* Listing and editing manuscript-reference relationships
* Creating a checkpoint
* Listing tool runs
* Listing and updating findings
* Listing activity events
* Querying reverse manuscript relationships from a Library reference

Use transactions for changes spanning multiple records.

Validate filesystem paths safely.

Do not allow arbitrary frontend-supplied paths to bypass existing local-file security boundaries.

## 26. Database and migrations

Use the repository's existing migration system.

Potential entities include:

* manuscript_watch_roots
* manuscripts
* manuscript_files
* manuscript_templates
* manuscript_sections
* manuscript_tasks
* manuscript_references
* manuscript_snapshots
* manuscript_tool_run_links
* manuscript_activity_events

Only create manuscript-specific findings if no general findings model can be reused.

Do not blindly create all entities as standalone tables if safe shared models already exist.

Add appropriate indexes and constraints for:

* Stable manuscript IDs
* Watch-root discovery identity
* Idempotent discovery
* Normalized paths
* Manuscript-file uniqueness
* One active primary file per manuscript
* Manuscript-reference uniqueness
* Snapshot hashes
* Tool-run associations
* Activity lookup by manuscript and time

Account for:

* Windows paths
* Linux paths
* macOS paths
* Mounted volumes
* Case sensitivity
* Case insensitivity
* Path separators
* Symlinks
* Junctions

Follow existing path-normalization conventions.

## 27. Filesystem behavior and failure modes

Handle explicitly:

* Watch root unavailable
* Manuscript folder renamed
* Manuscript folder moved
* Manuscript folder deleted
* File renamed
* Primary file deleted
* Primary file replaced
* Duplicate watch roots
* Nested watch roots
* Excluded child folders
* Two manuscripts with the same display title
* Multiple candidate manuscript files
* File changing during scan
* Unsupported format
* Extraction failure
* Permission error
* Symlink loop
* Junction loop
* Removable drive disconnection
* Network drive disconnection

Do not silently delete metadata when local files disappear.

Use missing states.

Avoid recursive symlink or junction loops.

Use existing watcher debouncing or implement a conservative equivalent so repeated filesystem events do not create duplicate scans or activity events.

## 28. Empty and error states

Provide clear WIP states for:

* No watch roots configured
* Watch root configured but no manuscripts found
* Manuscript discovered but no primary file selected
* Manuscript has no linked references
* Manuscript has no tool runs
* Missing folder
* Missing primary file
* Unsupported primary-file format
* Extraction failure
* Tool-run failure
* Stale checks
* Archived workspace

Messages should explain the actual state without overstating what Callosum knows.

## 29. Privacy and local-first behavior

Preserve Callosum's local-first model.

Unpublished manuscript text must not be sent to remote services without the existing explicit consent mechanism.

The WIP feature must remain useful without AI services.

Do not introduce cloud synchronization.

Do not introduce remote telemetry for unpublished manuscript content.

Make storage and snapshot behavior inspectable.

## 30. MVP exclusions

Do not implement these unless they already exist and need only trivial integration:

* Full manuscript editing
* Rich DOCX editing
* LaTeX editing
* Real-time collaboration
* Coauthor accounts
* Cloud synchronization
* Git-style branching
* Full document version control
* Automatic journal submission
* Submission portal automation
* Journal requirement scraping
* AI-generated manuscript completion
* AI-written manuscript sections
* Semantic document diffing
* Task dependencies
* Custom workflow-builder UI
* Automatic folder renaming
* Full-file snapshot duplication
* Coauthor assignment
* Notifications
* Recurring tasks

The purpose of the MVP is to build a trustworthy coordination layer around manuscripts, not to replace every external research tool.

## 31. Tests

Add tests using the current repository framework.

At minimum test:

### Navigation and shared browser behavior

* WIP appears immediately after Library
* Switching modes preserves independent view state where implemented
* WIP uses shared card or list infrastructure
* Manuscript cards render manuscript metadata
* Selecting a manuscript populates the manuscript details schema
* Opening a manuscript creates a manuscript-workspace tab
* Opening a linked reference uses the normal Library document-tab flow
* Tab close, restore, and persistence behavior remains intact

### Discovery

* Folder-as-manuscript discovery
* Immediate-subfolder discovery
* Idempotent rescanning
* Excluded-folder behavior
* Paused roots
* Duplicate titles with distinct IDs
* Missing roots
* Nested-root handling

### Identity

* Display-title rename does not rename folder
* Missing folder preserves manuscript
* Reconnection when path returns
* Path changes do not corrupt stable IDs

### Files

* File discovery
* Primary-file assignment
* Only one active primary file
* Missing primary file
* File hash updates
* Extraction failure behavior
* Primary-file replacement

### Sections and tasks

* Default template application
* Section status changes
* Custom section CRUD
* Section reordering
* Task CRUD
* Task completion
* Task reopening
* Activity events

### References

* Linking an existing Library reference
* Preventing duplicate manuscript-reference links
* Changing relationship state
* Reverse manuscript lookup from Library reference
* Opening linked references

### Snapshots and provenance

* Snapshot creation
* Snapshot deduplication for unchanged content
* Tool run linked to exact snapshot
* Current status for unchanged content
* Current with unresolved findings
* Potentially stale status
* Stale status after relevant changes
* Primary-file replacement invalidation

### Findings

* Finding status transitions
* Finding status independent of tool-run validity
* Activity creation for dispositions

### Error states

* Missing folder
* Missing primary file
* Unsupported format
* Permission failure
* Extraction failure
* Tool-run failure

Run the full existing test suite.

Do not weaken unrelated tests.

## 32. Documentation

Add or update documentation covering:

* Library and WIP as parallel modes
* Shared browser architecture
* Manuscript Workspace concept
* Watch-root discovery modes
* Manuscript identity
* File identity and primary-file selection
* Section and task tracking
* Library-WIP relationships
* Cross-mode navigation
* Snapshots
* Tool-run provenance
* Staleness semantics
* Findings lifecycle
* Activity history
* Local-first privacy behavior
* Known limitations
* MVP exclusions
* Future extension points

Document any architectural abstractions introduced to generalize the Library browser.

## 33. Implementation quality requirements

* Follow existing naming, typing, validation, and error-handling conventions.
* Reuse the Library browser's interaction model.
* Do not reuse the reference data model for manuscripts.
* Prefer entity-specific schemas over scattered visibility conditions.
* Prefer shared infrastructure over duplicated screens.
* Avoid excessive abstraction.
* Preserve local-first operation.
* Keep unpublished text private by default.
* Use deterministic hashes.
* Make stale, missing, unsupported, and uncertain states visible.
* Do not silently perform destructive filesystem actions.
* Do not overstate what Callosum verified.
* Keep the feature functional without AI.
* Maintain backward compatibility.
* Avoid new dependencies without a concrete need.
* Do not add placeholder controls.
* Keep cross-mode relationships queryable in both directions.
* Preserve existing Library workflows and performance.

## 34. Acceptance criteria

The MVP is complete when a user can:

1. Open Callosum and see WIP immediately after Library.
2. Switch between Library and WIP without learning a new navigation model.
3. Add one or more WIP watch roots.
4. Configure each root as either one manuscript or a container whose immediate child folders are manuscripts.
5. Scan roots and see Manuscript Workspace cards in WIP.
6. Search, sort, filter, and select manuscripts using familiar Library interactions.
7. See manuscript-specific information in the details pane.
8. Open a manuscript into a manuscript-workspace tab using the existing tab system.
9. Rename the workspace inside Callosum without renaming the folder.
10. Select a primary manuscript file.
11. Set the current stage.
12. Track default and custom sections.
13. Create and complete manuscript or section tasks.
14. Link existing Library references to the manuscript.
15. Open linked references through the normal Library tab workflow.
16. Query which manuscripts use a Library reference.
17. Associate an existing Callosum tool run with an exact manuscript snapshot.
18. See whether the run is current, current with unresolved findings, potentially stale, or stale.
19. Review and disposition findings.
20. Review manuscript activity chronologically.
21. Temporarily lose filesystem access without losing the workspace.
22. Restart Callosum and retain WIP state, tabs where supported, metadata, and provenance.
23. Pass all new and existing tests.

## 35. Final implementation report

When finished, return:

1. Architecture summary
2. How the Library browser was reused or generalized
3. How manuscript entities remain separate from references
4. Files added or changed
5. Database migrations
6. API routes or service operations
7. Navigation and frontend components
8. Details-pane schema changes
9. Tab-manager changes
10. Cross-mode relationship implementation
11. Snapshot and provenance implementation
12. Tests added
13. Validation commands
14. Test results
15. Known limitations
16. Repository-driven deviations from this prompt
17. Recommended next increment

Do not implement the recommended next increment unless it is required for this MVP.

Where the current repository architecture conflicts with a specific implementation detail in this prompt, preserve these core requirements:

* WIP is a top-level mode parallel to Library.
* WIP reuses Library interaction patterns.
* Manuscripts remain distinct first-class entities.
* Manuscripts open in workspace tabs through the shared tab system.
* Library and WIP are linked bidirectionally.
* Tool claims remain tied to exact manuscript content.

Adapt lower-level implementation details to the repository and explain consequential deviations in the final report.
