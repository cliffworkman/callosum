# Increment 606 â€” 0.5.16 release preparation

## Implemented

PR #103 became ready and merged at `1bdde98411a912a7bc854a6e30d96805434eab78`.
Parents: `4bce1a77c8ffa774789a62d97c22f22ea75ee307`, then accepted
`80025d1a9ddc889530a2cddb2a5b0bbfe94f77a0`. The merge tree equals the accepted tree:
`d9d2176e6ed6213beb5290c9119e6b76c24f1bda`.

Use `tools/bump_version.py 0.5.16` for the five desktop-shell version files;
`pyproject.toml` is unchanged. Add the informational manual-preview What's New entry,
rebuild `callosum-app.html`, and update README, desktop first-launch/support documentation,
served Browser Capture help and the release instructions. No functional control changed.
Correct documentation drift without rewriting old increment/acceptance receipts.

## Key contract and release boundary

The existing annotated-tag workflow remains the only release mechanism. Windows/macOS updater
signatures are separate from OS signing: Windows remains unsigned, macOS ad-hoc/non-notarized.
All four corrected immutable runtime IDs, dedicated preview identity, pairing boundaries and
public-release guard stay unchanged. No production browser IDs or store availability are claimed.

Physical evidence: Intel Sequoia/Chrome (OCLP iMac) and Windows 11 x64/Chrome; subsequent
Windows indexing/provenance fixes passed isolated real-runtime replay, not a second browser run.
Apple Silicon has automated build/startup/integration evidence only and is not a release blocker
per Cliff. Edge and older macOS are unvalidated; Linux Browser Capture is unsupported (#109).

## Experience and manual verification script

A returning reader sees what changed and the exact Settings â†’ Integrations route, with manual
preview/store limitations visible before installation. The existing enable/prepare/verify flow is
unchanged. No feature-wide experience pass or new physical acceptance is claimed for copy edits.
In a disposable UI session, present desktop version 0.5.16 with no dismissed-banner record:
1. Check the Browser Capture Early Access headline is visible and readable.
2. Check it directs readers to Settings â†’ Integrations and discloses unavailable store installation.
3. Read the Browser Capture help section for the support boundaries above.
4. Dismiss the banner and verify it disappears. Never exercise capture against an accepted QA DB.

## Validation

Local release-prep validation: **94 targeted tests passed** (What's New gate and frontend assembly).
All-file pre-commit passed (Ruff format/check, Bandit, Tach, line budget and syntax/whitespace gates).
What's New, preview-package verification, public-release guard and explicit demo/showcase
coverage gates passed. All six version references across five files are 0.5.16; Python package
metadata and managed-runtime inputs are unchanged. Frontend regenerated successfully.
The actual banner component/registry/styles rendered at 1365px and 800px with a simulated
health response: screenshots visually inspected, text readable without overflow, dismissal
persisted the correct version, no page errors. This was isolated UI evidence, not hardware QA.
Fresh remote CI, CodeQL, UNO and Windows/macOS Intel+ARM64/Linux packaging must pass on the
release-prep commit; record exact head, artifact hashes/signatures and limitations in the external
pre-tag report. No tag or release is authorized by those checks alone.

Demo and website coverage retain the existing explicit deferral through increment 606 using the
normal --decline mechanism; no new demo/showcase review is claimed.

## Lineage and preservation

Cliff supplied physical acceptance, authorized the merge/preparation and retained final release
approval. Lucien supplied the release-gate scope; Cody implemented and verified this preparation.
Original PASS/PARTIAL/FAIL evidence, confirmation provenance, frozen worktrees and untracked
files remain unchanged. A pre-merge receipt verified 150 evidence hashes and ten worktree states.
