<!-- qa-coverage
api: GET /wip/watch-roots, POST /wip/watch-roots, PATCH /wip/watch-roots/{root_id}, DELETE /wip/watch-roots/{root_id}, POST /wip/watch-roots/{root_id}/scan, POST /wip/rescan, GET /wip/scan/{job_id}, GET /wip/manuscripts, GET /wip/manuscripts/{manuscript_id}, PATCH /wip/manuscripts/{manuscript_id}, GET /wip/manuscripts/{manuscript_id}/files, PATCH /wip/manuscripts/{manuscript_id}/files/{file_id}, POST /wip/manuscripts/{manuscript_id}/files/{file_id}/open, POST /wip/manuscripts/{manuscript_id}/files/{file_id}/reveal, GET /wip/manuscripts/{manuscript_id}/activity, GET /wip/manuscripts/{manuscript_id}/snapshots, POST /wip/manuscripts/{manuscript_id}/snapshots, GET /wip/manuscripts/{manuscript_id}/sections, POST /wip/manuscripts/{manuscript_id}/sections, PATCH /wip/manuscripts/{manuscript_id}/sections/{section_id}, DELETE /wip/manuscripts/{manuscript_id}/sections/{section_id}, PUT /wip/manuscripts/{manuscript_id}/sections/order, GET /wip/manuscripts/{manuscript_id}/tasks, POST /wip/manuscripts/{manuscript_id}/tasks, PATCH /wip/manuscripts/{manuscript_id}/tasks/{task_id}, DELETE /wip/manuscripts/{manuscript_id}/tasks/{task_id}, GET /wip/manuscripts/{manuscript_id}/references, POST /wip/manuscripts/{manuscript_id}/references, DELETE /wip/manuscripts/{manuscript_id}/references/{paper_id}, GET /wip/papers/{paper_id}
api: GET /watch-roots, POST /watch-roots, PATCH /watch-roots/{root_id}, DELETE /watch-roots/{root_id}, POST /watch-roots/{root_id}/scan, POST /rescan, GET /scan/{job_id}, GET /manuscripts, GET /manuscripts/{manuscript_id}, PATCH /manuscripts/{manuscript_id}, GET /manuscripts/{manuscript_id}/files, PATCH /manuscripts/{manuscript_id}/files/{file_id}, POST /manuscripts/{manuscript_id}/files/{file_id}/open, POST /manuscripts/{manuscript_id}/files/{file_id}/reveal, GET /manuscripts/{manuscript_id}/activity, GET /manuscripts/{manuscript_id}/snapshots, POST /manuscripts/{manuscript_id}/snapshots, GET /manuscripts/{manuscript_id}/sections, POST /manuscripts/{manuscript_id}/sections, PATCH /manuscripts/{manuscript_id}/sections/{section_id}, DELETE /manuscripts/{manuscript_id}/sections/{section_id}, PUT /manuscripts/{manuscript_id}/sections/order, GET /manuscripts/{manuscript_id}/tasks, POST /manuscripts/{manuscript_id}/tasks, PATCH /manuscripts/{manuscript_id}/tasks/{task_id}, DELETE /manuscripts/{manuscript_id}/tasks/{task_id}, GET /manuscripts/{manuscript_id}/references, POST /manuscripts/{manuscript_id}/references, DELETE /manuscripts/{manuscript_id}/references/{paper_id}
fe: 04b_workspaces.jsx, 05_panes.jsx, 10f_wip.jsx, 30c_frame.jsx, 40_app.jsx
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
8. Link/change/open/unlink a Library paper without copying or deleting its canonical record.
9. Visit every Synthesize/Discover/Work subtab. Confirm the WIP cue, click-through, and absence of a paper cue.
10. Remove/restore a folder and confirm stable UUID, metadata, workflow, links, and checkpoints reconnect.

## Pass criteria

No console/page errors, stale paper context, duplicate identity, destructive scans, remote WIP exposure, layout
overlap, or ambiguous paper-vs-manuscript visual state.
