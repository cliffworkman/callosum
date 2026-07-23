# Security audit — WIP local filesystem workspace

**Status:** PASS for increments 351–352  
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
- An OS-open endpoint launches a path supplied directly by the caller.

## Required controls

- [x] Every `/wip/*` route is local-only, including GET; read-only companion mode is denied.
- [x] Root creation validates an existing directory and stores a normalized comparison key.
- [x] Discovery never follows symlink/junction directories and has entry/depth bounds.
- [x] Client paths are accepted only when registering/relinking a root; later open/read operations resolve trusted
      rows and re-check containment.
- [x] Missing files/folders become explicit states; no scan deletes workspace metadata.
- [x] WIP tables are absent from `sync.changeset.SYNCABLE`.
- [x] No WIP code calls an LLM or external provider.
- [x] File hashing is local and bounded to 256 MiB per file; scans are capped at 5,000 files and depth 20.
- [x] OS open/reveal is loopback-only and uses only a trusted DB-resolved path.

## Findings

No blocking findings. The local-only dependency rejects read-only mode, proxy/forwarding headers, non-loopback
Host values, and non-loopback clients. Discovery skips symlink directories/files and VCS/dependency trees. Open and
reveal accept only database IDs, reconstruct a root-relative path through `trusted_child`, and require a current
regular file before invoking the OS. Tests cover remote/forwarded/read-only denial, stable missing/restored identity,
hashing, primary-file uniqueness, and injected open/reveal targets.
