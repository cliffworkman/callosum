# Increment 436 — global AI and long-operation Status contract

## Outcome

Status is now the global place to find work in progress. Every application `JobStore`, every synchronous AI request,
and every mounted shared `ProgressBar` appears there; rows identify their compute boundary and navigate back to the
relevant workspace, pane/tab, modal, and paper or summary when known. The popover is also available beside the mobile
Workspace selector.

## Architecture

- `JOB_NAV_DEFAULTS` gives every backend job family a server-owned destination. Job producers may add only typed
  entity ids; the Status serializer drops URLs, free text, and destination overrides. A structural test fails when a
  new application `JobStore` lacks a destination.
- `JobStore.create(nav=...)` establishes entity context before work starts and preserves it through
  running/progress/done/error transitions.
- The client registry wraps the normal request seam for synchronous provider and installed-local AI routes. Its
  explicit inventory includes Help, provider testing, funding/preregistration triage, tags, semantic citation and
  discovery retrieval, critique proposals, PDF reprocessing, re-verification, and assisted extraction.
- `ProgressBar` self-registers by default through `StatusScope`. `managedBy="backend-job"` or
  `managedBy="tracked-request"` assigns an existing owner and prevents duplicate rows.
- Determinate operations retain real completion and approximate linear ETA. Indeterminate operations explicitly say
  completion and ETA are not measurable; elapsed time is never converted into a fake percentage.

## Principles and experience pass

This touches Principles **8 (inspectability)** and **10 (local-first/provider-swappable)** and most resembles the
grounding concern in Example 1: an AI operation's provenance and route back to its inspectable output must stay visible.
The easier misaligned path was to cover only obvious cloud-LLM buttons, or manufacture reassuring percentages for
opaque work; the aligned path covers provider and installed-local computation while withholding unknown measurement.

The **Multi-tasker** and **Migrator** paths were exercised through the browser: start work, leave its surface, inspect
global state, return through the row, finish, then repeat at phone width. The original gap—AI calls without backend jobs
and progress bars without global registration—is closed. One low-severity limitation remains: simultaneous jobs of the
same family share a generic label when no human-readable entity title is available, although each still routes to its
own typed entity. No existing backlog file is present; retain this as a follow-up here rather than inventing a new one.

## Privacy and security

This adds no model call, egress, dependency, persistence, or external host. The client registry stores operation
labels, status, bounded destination, progress, and compute-kind only—not request bodies or responses. Backend Status
continues to exclude `Job.result`; navigation is now narrower than before because only positive integer entity ids
survive beside server-owned destination tokens.

## Tests

Backend tests pin destination coverage, navigation preservation, compute-kind labels, and hostile navigation-field
discarding. Frontend structural tests pin automatic progress registration, AI route inventory, workspace/pane scope,
mobile access, ownership deduplication, and destination dispatch. An opt-in Chromium test holds a real synchronous AI
request open, leaves its surface, verifies Status visibility/locality/indeterminate honesty, clicks back to the UI,
and observes the finished receipt with no console error or mobile overflow.

Validation completed with **87** focused Status/JobStore/frontend tests, the full Chromium smoke at **9 passed**, and
the complete offline suite at **1786 passed, 1 skipped**. Ruff format/check, the rebuilt frontend artifact, the
600-line budget, and strict QA surface coverage (**352/352 API; 1545/1545 frontend**) are clean.

## Rollback

Revert Increment 436 and rebuild `callosum-app.html`. No migration or stored data is involved. The pre-436 Status
popover will return to backend jobs only, with navigation limited to the previously special-cased families.
