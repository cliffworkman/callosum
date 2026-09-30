# Preview restart acceptance: Finder metadata

Cliff's real Intel Chrome acceptance of `ac8b4cba` established a successful two-sided
native-host handshake, one genuine PDF capture, Import Queue appearing within about
one second without refresh, DOI lookup/confirmation, and automatic Library appearance.
Observation preserved the provisional evidence before confirmation and the final intact
PDF, correct DOI, explicit user-confirmation provenance, 122 chunks and 122 embeddings.

After a graceful QA app restart, Cliff reported that Verify connection was disabled.
The paper and extension files had survived unchanged, but this did not establish that
the restarted integration remained usable. A read-only inventory found a regular
6,148-byte `.DS_Store` in the extension root, with the Finder metadata header. All eight
extension files still matched both the embedded package and the installation receipt.
The metadata SHA-256 was
`3b60bd7a16f58abcd75b12ce6643e3023abe42fda66c3ba57b81545640a1b967`.
Its original bytes and the failure receipt were preserved outside the extension directory.

The exact-inventory verifier rejected the extra file. Settings used `prepared: false`
to disable Verify/Open folder but did not render the returned `package_error`. This
made a normal Finder side effect look like a silent, disabled integration. The evidence
establishes the file's presence, not which Finder interaction created it or its exact time.

## Narrow correction

Installed-folder verification permits `.DS_Store` only in the root or existing `icons`
directory, only as a regular non-link file between 8 bytes and 1 MiB with the Finder
header. Those bytes are never executed, parsed beyond the header, packaged, or included
in the extension receipt. They are ignored for extension-content verification, and
removed only by the existing explicit Prepare/update or disable cleanup operation.
Cleanup remains limited to fixed names; no recursive removal is introduced.

All eight extension files remain hash-checked. Unknown files/directories, links,
reparse points, malformed/oversized metadata and modified extension bytes still fail
closed and remain untouched. Build-time package inventory stays exact: this allowance
is only for Finder metadata written into the installed directory. Identity, host origin,
pairing, runtime and production release gates are unchanged.

Settings now shows the returned package verification error when it disables controls.
Regression coverage exercises metadata retention during verification, explicit update
and cleanup, unrelated files alongside valid metadata, malformed/oversized metadata,
Unix metadata symlinks, and the rendered disabled-control/error state with simulated IPC.
Native Intel packaged reacceptance is required; Windows unit tests and mocked Settings
are not a substitute for that hardware result.

The original QA bundle and evidence are retained; no live bundle edits or ad hoc deletion
of the observed metadata are used to claim acceptance. A replacement build must carry
its own exact source commit and artifact checksum. Publication remains unauthorized.

## Contribution lineage

- 2026-09-30 | Evidence | Cliff Workman: performed real Chrome capture/DOI acceptance
  and reported the disabled Verify control after restart.
- 2026-09-30 | Investigation and implementation | Cody (Codex): traced the extra Finder
  metadata through strict inventory verification and the missing UI error, then prepared
  the narrowly scoped metadata handling and regression coverage.
