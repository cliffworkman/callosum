# Manual Browser Capture preview — implementation review

Scope: the local `feat/browser-capture-preview-0516` branch, based on DOI fix f3ccab44.
This is a primary-agent review, not an independent audit or a penetration-test claim.

## Boundaries checked

- Only a fixed Tauri action enum accepts local setup requests. No path, URL, executable,
  arbitrary origin, extension ID or byte payload comes from the frontend. The capability
  is main-window-only and Rust also checks its exact current loopback backend origin.
  No new FastAPI setup/registration/file-opening route exists. An XSS in the trusted app
  origin is still within the app's existing trust boundary; this feature does not solve it.
- The preview public identity is separate from development and store identities. The normal
  native host authenticates its exact origin before reading a request, requires local opt-in,
  and disallows development backend eligibility even when the dev environment flag is set.
  Existing pairing checks, loopback discovery and bounded session TTL remain intact.
- Preview sessions carry an opt-in generation internally. Every later authorization reads
  the desktop-owned state; disable invalidates old tokens, and re-enable uses a new generation.
  A verification receipt must also match the generation used for the actual session exchange.
  Work admitted before opt-out may complete. Pairing secrets/tokens are not written to evidence.
- A public key stabilizes unpacked identity, not code authenticity. Another locally approved
  unpacked extension could copy a public key. Package verification verifies app-provided bytes;
  the UI must not describe this as browser attestation. No private key was persisted or packaged.
- Embedded files are exactly allowlisted, individually hashed, versioned and reproducible.
  Existing files must match the previous receipt before update or cleanup. Symlinks and Windows
  reparse points are rejected. No recursive product cleanup, executable payload or arbitrary
  launcher path is accepted. Unexpected/modified content is retained for user inspection.
  Interrupted staging is fail-closed and requires inspection rather than broad deletion.
- macOS uses existing per-user packaged-host registration. Windows uses the NSIS-owned shared
  manifest path and exact Chrome/Edge registry keys so installer ownership cleanup still works.
  Disabling preview retains the host registration for other supported identities; its preview
  origin is unusable while the host/backend opt-in checks reject it.
- Verify performs a fresh normal-host/session handshake plus a 60-second desktop challenge.
  Options receives no capture token, writes no local file and sends no capture. Preparation,
  folder opening and registration cannot produce a successful verification receipt.

## Release review

The production-ID ratchet now lives in the tag workflow with full git history. Manual preview
is an explicit channel, not an invented store ID or a way to reset a previous store release.
Known-broken pristine Intel runtime IDs block public release. Passing the negative guard is
not portability proof: corrected immutable artifacts, signatures and clean-cache hardware
acceptance remain mandatory. Runtime publication and all public release actions need Cliff's
separate approval.

## Evidence still required

Real Intel macOS Chrome manual loading, handshake/capture, restart and opt-out remain separate
from unit tests and simulated rendered Settings. Windows native tests do not establish a
Windows browser installation. Edge, ARM hardware and older macOS are not inferred from Intel
Sequoia/OCLP testing. Record the final matrix in the acceptance report before release review.

Lineage: Cliff supplied the opt-in product/security constraints; earlier contributors supplied
the capture/pairing architecture; Lucien critiqued the DOI workflow; Cody implemented and
reviewed this preview boundary. No independent review is implied by those attributions.
