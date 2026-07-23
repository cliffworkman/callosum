# Security audit — WIP local filesystem workspace

**Status:** PASS for increments 351–355
**Date:** 2026-07-23
**Scope:** WIP watch roots, manuscript/file discovery, local file open/reveal, manuscript extraction, and all
`/wip/*` API routes.

## Threats

- A remote/tunnel caller reads unpublished manuscript metadata or content.
- A frontend-supplied path escapes a registered manuscript root.
- A symlink/junction causes recursive traversal outside the intended workspace or creates a loop.
- A scan is unbounded and exhausts CPU/memory/SQLite capacity.
- A missing/moved file silently deletes user metadata.
- A manuscript is accidentally added to cross-device sync or an external provider request.
- A deterministic check result is detached from the exact manuscript text it examined or presented as a verdict.
- An OS-open endpoint launches a path supplied directly by the caller.

## Required controls

- [x] Every `/wip/*` route is local-only, including GET; read-only companion mode is denied.
- [x] Root creation validates an existing directory and stores a normalized comparison key.
- [x] Explicit relinking validates an existing non-symlink directory, refuses manuscript/root collisions, preserves
      stable manuscript/file identity, and records both the previous and replacement paths in local activity.
- [x] Discovery never follows symlink/junction directories and has entry/depth bounds.
- [x] Client paths are accepted only when registering/relinking a root; later open/read operations resolve trusted
      rows and re-check containment.
- [x] Missing files/folders become explicit states; no scan deletes workspace metadata.
- [x] WIP tables are absent from `sync.changeset.SYNCABLE`.
- [x] No WIP code calls an LLM or external provider.
- [x] WIP search/facet/count projections query only local metadata and content hashes; they neither read full
      manuscript text nor create a new egress path.
- [x] File hashing is local and bounded to 256 MiB per file; scans are capped at 5,000 files and depth 20.
- [x] Primary-file extraction accepts only an explicit supported-format allowlist, is capped at 256 MiB (plain text
      at 32 MiB), persists no full manuscript text/file bytes, and bounds checkpoint context to 6 × 500 characters.
- [x] Snapshot create/list routes inherit the same local-only dependency; checkpoints deduplicate in SQLite and
      never enter sync or an external request.
- [x] Check run/list and finding-review routes inherit the same local-only dependency. Statcheck executes only over
      locally extracted blocks, persists no full manuscript text, and makes no external or LLM request.
- [x] Every WIP tool run binds to a file, exact snapshot, extracted-text hash, tool version, Callosum version,
      explicit coverage, and timestamp. Finding coordinates remain null unless an honest anchor exists.
- [x] OS open/reveal is loopback-only and uses only a trusted DB-resolved path.

## Findings

No blocking findings. The local-only dependency rejects read-only mode, proxy/forwarding headers, non-loopback
Host values, and non-loopback clients. Discovery skips symlink directories/files and VCS/dependency trees. Open and
reveal accept only database IDs, reconstruct a root-relative path through `trusted_child`, and require a current
regular file before invoking the OS. Tests cover remote/forwarded/read-only denial, stable missing/restored identity,
hashing, primary-file uniqueness, and injected open/reveal targets.
Checkpoint tests additionally cover exact extracted identity, deduplication, changed-file status, unsupported
formats, and forwarded-request denial.
Tool-run tests cover exact snapshot binding, candidate evidence/context, disposition review, current-to-potentially-
stale-to-stale invalidation, explicit no-finding coverage language, and remote denial for every check endpoint.
Relink tests cover stable UUID/workflow/file identity, missing-to-active restoration, target collision refusal, and
remote denial. Reverse paper-to-WIP navigation reads only existing local relationship rows.
