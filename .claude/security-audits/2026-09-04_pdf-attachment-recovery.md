# Security Audit: Exact-Checksum PDF Attachment Recovery

Date: 2026-09-04
Increment: 576
Scope: existing local folder scan, PDF-serving diagnostics, and recovery UI

## Trigger and boundary

This change spans more than three files and changes the existing file-ingestion reconciliation path, triggering the
security audit gate. It adds no endpoint, external integration, dependency, authentication logic, filesystem delete,
or provider call. `POST /library/scan` remains the sole write boundary and still accepts only an existing local
directory. The new behavior updates an existing attachment row when—and only when—a scanned PDF's SHA-256 is exactly
equal to that row's stored checksum.

## Input and path safety

- The scan endpoint retains its existing `Path(...).is_dir()` validation and its non-recursive `*.pdf` scope.
- The existing 80 MiB per-file cap is checked before hashing or parsing.
- Attachment ids and stored checksums used for recovery come from the database, never from client input.
- Recovery does not compare filenames, titles, authors, DOI metadata, or fuzzy similarity. An exact content digest is
  the only reconnection authority.
- The resulting path is the resolved path of a file actually enumerated inside the selected folder. This is the same
  path trust boundary already used when a scan creates a linked attachment.
- Platform path normalization uses `normcase` plus a best-effort absolute resolution. Missing/disconnected paths fail
  closed as unavailable rather than aborting the entire scan.

## Mutation and integrity

Recovery changes only `storage_mode`, `availability`, `original_path`, `resolved_path`, and `file_size`. It preserves:

- attachment and paper ids;
- stored checksum;
- extracted chunks and their source checksum;
- embeddings;
- highlights, notes, and attachment-scoped annotations;
- import/OA provenance and document role.

A recovered file at its original recorded location keeps its existing storage mode; a copy found elsewhere becomes a
linked attachment because Callosum does not own or copy that file. All matching unavailable attachment rows may point
to the same exact bytes; this is safe because their checksums are identical and their distinct provenance remains.

Removed-file detection is now limited to scan-sourced paths whose immediate parent is the folder currently being
scanned. This fixes the prior cross-folder mutation where scanning one valid watched folder could mark attachments in
another valid watched folder missing.

## Diagnostics and privacy

PDF 404 responses retain their old human-readable body for compatibility and add only:

- stable error code;
- local attachment id;
- storage mode;
- recorded availability;
- Callosum version when known.

No response header or copied diagnostic contains a paper title, PDF name, original/resolved path, username, document
text, API key, token, environment value, or provider credential. The attachment id is already scoped to a paper route
and reveals less than the existing successful response, which already returns it. The folder-scan error-detail path
behavior is pre-existing and remains limited to the local, authenticated application surface.

## Egress and resource behavior

Reconnection adds no paper to `scanned["added"]`, so the later enrichment/embedding phase does not run for it and no
Crossref or AI request occurs. Hashing cost is unchanged: the scanner already hashed each in-cap PDF for deduplication.
The checksum index now retains all matching rows rather than one arbitrary row; this is bounded by attachment count and
avoids losing an inaccessible duplicate behind an accessible match.

## Negative-path verification

- Different content: remains a new-file ingestion; it cannot relink an attachment by filename.
- Missing managed root: 404 `PDF_LIBRARY_FOLDER_MISSING`, with no path in headers/body.
- URL-only record: 404 `PDF_REMOTE_ONLY`.
- Missing linked file: 404 `PDF_ATTACHMENT_FILE_MISSING`.
- Foreign/nonexistent attachment id: remains paper-scoped and returns `PDF_ATTACHMENT_NOT_FOUND`.
- Non-PDF attachment: remains rejected and returns `PDF_ATTACHMENT_NOT_PDF`.
- Exact file moved and renamed: reconnects the same attachment id; paper count and chunk ids remain unchanged.
- Multiple watched folders: scanning one leaves the other's attachments available.

These cases are pinned in `tests/test_library_scan.py`, `tests/test_papers.py`, and
`tests/test_frontend_assembly.py`. The final verification receipt is recorded in the increment notes.

## Residual risk

As before, a user-controlled local file can change after it is hashed (local TOCTOU); subsequent scientific paths
continue to carry the stored source checksum and existing staleness mechanisms. This change neither broadens the
filesystem surface nor claims that a later-mutated file still matches. A future file-watcher could reduce that window,
but is not necessary for safe recovery of an exact snapshot.

**Security Audit: PASS**
