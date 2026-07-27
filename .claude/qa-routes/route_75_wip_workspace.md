<!-- qa-coverage
api: GET /wip/watch-roots, POST /wip/watch-roots, PATCH /wip/watch-roots/{root_id}, DELETE /wip/watch-roots/{root_id}, POST /wip/watch-roots/{root_id}/scan, POST /wip/rescan, GET /wip/scan/{job_id}, GET /wip/browse-dirs, GET /wip/manuscripts, GET /wip/manuscripts/{manuscript_id}, PATCH /wip/manuscripts/{manuscript_id}, DELETE /wip/manuscripts/{manuscript_id}, POST /wip/manuscripts/{manuscript_id}/relink, GET /wip/manuscripts/{manuscript_id}/files, PATCH /wip/manuscripts/{manuscript_id}/files/{file_id}, POST /wip/manuscripts/{manuscript_id}/files/{file_id}/open, POST /wip/manuscripts/{manuscript_id}/files/{file_id}/reveal, GET /wip/manuscripts/{manuscript_id}/activity, GET /wip/manuscripts/{manuscript_id}/snapshots, POST /wip/manuscripts/{manuscript_id}/snapshots, GET /wip/manuscripts/{manuscript_id}/checks, POST /wip/manuscripts/{manuscript_id}/checks/statcheck, GET /wip/manuscripts/{manuscript_id}/funding-runs, GET /wip/manuscripts/{manuscript_id}/journal-runs, PATCH /wip/findings/{finding_id}, GET /wip/manuscripts/{manuscript_id}/sections, POST /wip/manuscripts/{manuscript_id}/sections, PATCH /wip/manuscripts/{manuscript_id}/sections/{section_id}, DELETE /wip/manuscripts/{manuscript_id}/sections/{section_id}, PUT /wip/manuscripts/{manuscript_id}/sections/order, GET /wip/manuscripts/{manuscript_id}/tasks, POST /wip/manuscripts/{manuscript_id}/tasks, PATCH /wip/manuscripts/{manuscript_id}/tasks/{task_id}, DELETE /wip/manuscripts/{manuscript_id}/tasks/{task_id}, GET /wip/manuscripts/{manuscript_id}/references, POST /wip/manuscripts/{manuscript_id}/references, DELETE /wip/manuscripts/{manuscript_id}/references/{paper_id}, GET /wip/papers/{paper_id}, POST /funding-discovery/run (manuscript_id), POST /methods/publishers/run (manuscript_id)
api: GET /watch-roots, POST /watch-roots, PATCH /watch-roots/{root_id}, DELETE /watch-roots/{root_id}, POST /watch-roots/{root_id}/scan, POST /rescan, GET /scan/{job_id}, GET /browse-dirs, GET /manuscripts, GET /manuscripts/{manuscript_id}, PATCH /manuscripts/{manuscript_id}, DELETE /manuscripts/{manuscript_id}, POST /manuscripts/{manuscript_id}/relink, GET /manuscripts/{manuscript_id}/files, PATCH /manuscripts/{manuscript_id}/files/{file_id}, POST /manuscripts/{manuscript_id}/files/{file_id}/open, POST /manuscripts/{manuscript_id}/files/{file_id}/reveal, GET /manuscripts/{manuscript_id}/activity, GET /manuscripts/{manuscript_id}/snapshots, POST /manuscripts/{manuscript_id}/snapshots, GET /manuscripts/{manuscript_id}/checks, POST /manuscripts/{manuscript_id}/checks/statcheck, PATCH /findings/{finding_id}, GET /manuscripts/{manuscript_id}/sections, POST /manuscripts/{manuscript_id}/sections, PATCH /manuscripts/{manuscript_id}/sections/{section_id}, DELETE /manuscripts/{manuscript_id}/sections/{section_id}, PUT /manuscripts/{manuscript_id}/sections/order, GET /manuscripts/{manuscript_id}/tasks, POST /manuscripts/{manuscript_id}/tasks, PATCH /manuscripts/{manuscript_id}/tasks/{task_id}, DELETE /manuscripts/{manuscript_id}/tasks/{task_id}, GET /manuscripts/{manuscript_id}/references, POST /manuscripts/{manuscript_id}/references, DELETE /manuscripts/{manuscript_id}/references/{paper_id}
fe: 04b_workspaces.jsx, 05_panes.jsx, 06_methods_statcheck.jsx, 08e_methods_publishers.jsx, 08k_funding_discovery.jsx, 10f_wip.jsx, 10g_wip_relink.jsx, 10h_wip_filters.jsx, 10i_wip_context.jsx, 10j_wip_folder_browser.jsx, 10k_wip_checks.jsx, 25_detail.jsx, 30c_frame.jsx, 40_app.jsx
-->

# ROUTE 75 - WIP manuscript workspace

**Tier:** 1 local-stateful
**Goal:** Prove WIP is the permanent second collection inside Library, remains a distinct unpublished entity, and
replaces paper context throughout Callosum without destroying either collection's state.

## Environment

Use a disposable local database and two roots: one folder-as-manuscript and one immediate-children root. Include
manuscript candidates, a nested figure, one excluded child, and one temporarily missing folder. Register console
and page-error listeners before navigation.

## Standing assertions

- Console/page errors and document horizontal overflow are zero at 1440x900 and 375x812, light and dark.
- Tabs begin **Library · WIP**. Manuscript tabs always show a visible `WIP` badge and teal context treatment.
- Library and WIP preserve independent state.
- While WIP is active, Synthesize/Discover/Work show the manuscript cue and no stale paper cue or paper ID.
- WIP is absent in read-only mode and forwarded/non-loopback `/wip/*` requests return 403.
- Scans do not follow symlinks and never delete metadata for missing folders/files.

## Steps

1. Add each root mode and rescan. Confirm the correct immediate manuscripts, exclusions, and idempotent repeat.
2. Search/filter/sort/select in WIP, switch to Library and back, and confirm both collection states survive.
3. Edit Details; double-click and confirm Overview, Structure, Tasks, Files, References, Checks, and Activity.
4. Change section status; add/reorder/delete a custom section; confirm a default section cannot be deleted.
5. Add/complete/reopen/delete a task and confirm meaningful Activity events.
6. Assign roles and change the primary file; confirm exactly one. Open/reveal the exact registered file.
7. Create a manual checkpoint twice and confirm unchanged content deduplicates. Change the file, rescan, and confirm
   the prior checkpoint becomes potentially stale until re-extraction, then stale when extracted text differs.
8. Run Statcheck against a draft containing one deliberately inconsistent inline APA result. Confirm the run names
   its tool version, exact checkpoint, coverage boundary, quoted result, context, reported p, and recomputed p.
9. Open the source file from a finding, then change its disposition and confirm the run remains inspectable. A
   zero-finding run must state its coverage and must never call the manuscript clean.
10. Link/change/open/unlink a Library paper without copying or deleting its canonical record.
11. Visit every Synthesize/Discover/Work subtab. Confirm the WIP cue, click-through, and absence of a paper cue.
12. Move a manuscript folder, relink it explicitly, and confirm stable UUID, file IDs, metadata, workflow, links,
    checkpoints, and runs reconnect. A path already owned by another manuscript must be refused, never guessed.
13. From a linked paper's Library Details, open its **Used in WIPs** relationship and confirm the complete
    manuscript workspace opens while the Library selection remains recoverable.
14. Exercise title/type/journal search, stage/state/deadline/modified facets, open-task/unresolved-finding/stale-check/
    missing-primary toggles, and task/finding count sorts. Confirm card counts and empty-state clearing remain exact.
15. Open the manuscript context menu by right-click and Shift+F10; exercise stage, pause/resume, archive/restore,
    rescan, and open. Open multiple WIP tabs, drag-reorder them, close one, and confirm paper tabs are unaffected.
16. Open "+ Add location" → "Browse…": confirm the folder-browser modal opens on the home directory, descending
    into a subfolder updates the path readout and list, "Up one level" returns to the parent (disabled at a
    filesystem root), and "Select this folder" populates the path input and closes the modal without submitting.
    Repeat from an existing manuscript's "Relink folder" → "Browse…" and confirm it starts near the manuscript's
    current (possibly-missing) location. Confirm Cancel at any point leaves the underlying input untouched, and
    that a permission-denied or empty folder shows an inline message rather than a dead end or crash.
17. Click the "N watched locations" summary to expand the watch-root list; confirm each row shows its path and
    discovery mode. Delete a watch-root via its 🗑 button (confirm the `window.confirm` guard fires and cancelling
    leaves it untouched); confirm the manuscript(s) it discovered survive the deletion and remain visible/selectable.
    Right-click a manuscript card → "Remove manuscript"; confirm the `window.confirm` guard names the manuscript
    and warns the action is permanent; confirm cancelling leaves it untouched, while confirming removes the card
    immediately and it does not reappear after a Rescan (proving it doesn't merely hide — it's gone from the DB).
18. **Inc 402: the Methods panel's "Statistics" section, wired to WIP.** With a WIP manuscript open, expand
    Methods → **Statistics** (not Details) and confirm it shows the same Deterministic-checks/Content-checkpoints
    UI as the manuscript's own **Checks** tab (not "Select a paper…" — `ctx.selectedPaper` stays null for a
    manuscript by design; this section now branches on `ctx.researchContext.kind` instead). Run statcheck (or, for
    a manuscript with no primary file, confirm the honest "Select a primary manuscript file…" 422 message appears
    inline rather than a crash). Confirm a run/disposition change made from *either* the Methods-panel Statistics
    section or the manuscript's own Checks tab is reflected in the other without a manual page reload (the shared
    `wip.refresh` counter). Switch to a Library paper and confirm its own Statistics section (whole-library batch +
    per-paper cached result) is pixel-identical to before — this section's non-manuscript branch is untouched.
19. **Inc 403: Discover > Funding wired to WIP manuscripts.** With a WIP manuscript open, go to Discover >
    Funding — confirm it defaults to "Describe research" mode (never "Selected paper", since `ctx.selectedPaper`
    stays null for a manuscript) with the description pre-filled from the manuscript's title/notes and a "Pre-
    filled from `<title>`" note; the field freely editable. Run a search (`POST /funding-discovery/run` with
    `manuscript_id`) and confirm it completes normally. Confirm the manuscript's own Checks tab shows a new
    "Funding searches" entry with the correct title/counts/date **without a manual reload** (the shared
    `wip.refresh` cross-sync from inc 402, reused here). Confirm `GET /wip/manuscripts/{id}/funding-runs` is
    correctly scoped — a second manuscript's list stays empty; a Library-paper-mode Funding run is unaffected and
    does not appear in any manuscript's list.
20. **Inc 404: Discover > Journals wired to WIP manuscripts.** With a WIP manuscript open, go to Discover >
    Journals — confirm it defaults to "Paste an abstract" mode with the abstract pre-filled from the
    manuscript's title/notes and a "Pre-filled from `<title>`" note; enter a subject and run "Find journals"
    (`POST /methods/publishers/run` with `manuscript_id`). Confirm the manuscript's own Checks tab shows a new
    "Journal searches" entry (topic/weighting/counts/date) **without a manual reload**. Confirm
    `GET /wip/manuscripts/{id}/journal-runs` is correctly scoped (a second manuscript's list stays empty) and
    that a Library-paper-mode Journals run never writes a receipt for any manuscript.

## Pass criteria

No console/page errors, stale paper context, duplicate identity, destructive scans, remote WIP exposure, layout
overlap, or ambiguous paper-vs-manuscript visual state.
