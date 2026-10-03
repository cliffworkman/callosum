# Browser Capture manual preview for 0.5.16 — design before implementation

Branch: feat/browser-capture-preview-0516, based on accepted local DOI commit
f3ccab44e020f480deb0ed23c776002d349cf3c7. PR #103 remains draft at c7a7c10b;
runtime correction 25abf37a stays separate. Frozen worktrees/evidence are not edited.

## User flow

Settings → Integrations → Browser Capture explicitly offers an early-access, manual
Developer mode installation. Enable early access grants local opt-in, Prepare extension
verifies and stages the bundled files, Open extension folder reveals that one directory.
Chrome and Edge instructions require the user's Load unpacked approval. Neither staging,
folder opening nor native registration means installed/connected.

Verify connection starts a short-lived challenge. The user opens the extension's Options
page and presses Verify connection there. The browser launches the normal packaged native
host, which checks the exact preview caller ID, opt-in generation, packaged UI backend,
pairing and session exchange before writing a challenge-matched receipt. Settings reports
only that fresh verified exchange, not permanent connectivity. Errors/timeout are explicit.
The toolbar retains its existing single-click capture behavior; verification never captures.

## Identity and authority

A dedicated RSA public key is generated once; only its public DER and derived Chromium ID
are committed. No private key is written or shipped. It is distinct from development and
future store IDs. The normal org.callosum.connector manifest authorizes that exact preview
ID alongside genuine store IDs. No wildcard, arbitrary ID input, dev launcher or
CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD dependency is allowed for preview callers.

An installed unpacked extension is user-approved local code. A public key pins an ID; it
does not certify source authenticity against another local user-approved extension with
the same public key. Package hashes establish the app-provided files, not browser attestation.

The privileged surface is a fixed-action Tauri command bound to main and the current
packaged UI origin, never a FastAPI file-writer/launcher/registration endpoint. It accepts
no paths, URLs, extension IDs or arbitrary content. Remote/browser-only Settings explains
that preparation requires the desktop app. Pairing remains local; only short-lived capture
tokens reach the extension. Preview tokens carry the current opt-in generation internally;
each backend authorization checks it against local desktop-owned state. Disable invalidates
preview tokens immediately, including after re-enable, without revoking store/dev sessions.
Already admitted work may finish; disabling is not deletion of captured papers.

## Files and updates

The package is embedded in the shell from an allowlisted, deterministic builder, with
per-file SHA-256s and version. Prepare writes only a fixed app-data subdirectory outside
the app bundle. Stable `browser-capture-preview/extension` survives updates. Existing
managed contents must match their receipt before replacement/cleanup; unexpected files,
links/reparse points or modified bytes fail closed and are not executed or removed.
An app update does not silently rewrite browser code. Prepare explicitly updates it;
the browser may require Reload on its Extensions page, followed by fresh verification.
Disable revokes first, then removes only a verified managed package; modified files are
retained with an actionable cleanup explanation. Browser removal remains the user's action.

## Release policy and ordering

Preview is an explicit manual-preview channel, not a production store identity and not a
false `released` claim. The store-release guard retains D1: once store release is true,
both genuine store identities are required and later tags cannot remove them or revert
the store-release state. A preview build cannot satisfy a store-release gate.
Production IDs and store-install links remain empty/unavailable in this change.

Integration order: PR #103 base → accepted DOI fix → reviewed preview commits. Separately,
approve and publish all four immutable corrected runtime artifacts from 25abf37a; verify
their signed manifests/hashes; only then incorporate the new runtime references. Require
CI/CodeQL and Windows/macOS x64/macOS arm64/Linux build checks on the resulting exact head,
then pristine-cache Intel launch/capture acceptance before any 0.5.16 tag. Existing repaired
runtime QA is behavior evidence only. No new macOS support floor is inferred from a Sequoia
OCLP iMac; Apple Silicon, older macOS and Edge claims need their own evidence. Linux capture
remains unsupported. Version bump/tag/publication are separate approval gates.

When genuine store IDs/URLs exist, a separately approved update exposes store installation.
Users install the store edition, verify it, then disable/remove preview to avoid duplicate
toolbar actions. Preview's ID is not silently converted into a store identity. Existing
Library records and provenance survive that migration.

## Validation and lineage

Tests must distinguish deterministic identity/package/path/IPC/session tests, simulated
frontend flows, CI packaging, and real packaged desktop/Chrome evidence. Real tests include
fresh profile, handshake, genuine PDF click, restart/update, opt-out, wrong-ID and absent-host
negatives. Human capture/confirmation clicks remain Cliff's; state is snapshotted/restored.

Principles: evidence for connection claims (1/6/8), observed versus verified state (3),
explicit human opt-in (5/9), local scoped authority (10). The misleading shortcut would
label a prepared folder or registered host “installed”; the design requires a real handshake.

Cliff Workman: preview product direction, security/release constraints, real human acceptance.
Earlier Claude/ChatGPT contributors: underlying browser-capture architecture, preserved in
PR #103. Lucien: prior DOI-review critique. Codex (Cody): this preview design and implementation.

References: https://developer.chrome.com/docs/extensions/reference/manifest/key and
https://v2.tauri.app/security/capabilities/ (checked 2026-09-27).
