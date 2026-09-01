# Increment 553 Notes — Versioned Local AI Onboarding Refresh

## Outcome

The existing first-run wizard already embedded the complete shared `AiSettings`, so managed Local AI setup was
technically present. Its old cloud-era introduction was misleading, however, and users who had completed onboarding
before Increment 547 never saw it again.

This increment versions onboarding at contract version 2. A fresh install still receives the complete wizard. A
desktop install with the legacy `onboarding_completed:true` state and no current version receives one two-screen
refresh—AI features, then Done. **Not now**, Finish, and successful traversal all persist version 2, so this is a
single notice rather than a recurring nag. Read-only companions and non-desktop browser sessions do not receive the
migration refresh.

The obsolete Library **New layout** banner is replaced with a newly keyed **New: Local AI** announcement. Its
**Set up Local AI** action always reopens the same AI-only onboarding flow, even after the one-time refresh was
dismissed, so users retain a direct recovery path in addition to Settings → AI features.

## Invariants

- The wizard and Library action reuse the real `AiSettings`; no second Local AI implementation exists.
- Local AI remains explicit user choice. Cloud egress stays off by default and there is no fallback/provider change.
- The completion flag and bounded onboarding version are written together through the existing local settings API.
- Existing identity, library, import, and axis onboarding behavior is unchanged for fresh installs.
- The old announcement dismissal key is not reused; returning users actually receive the new Local AI notice.

## Verification

- Settings, health, and frontend-assembly suite: **127 passed, 2 expected integration failures** (the retired-banner
  assertion and stale generated artifact); after updating that assertion and rebuilding, the exact affected slice:
  **7 passed**.
- `callosum-app.html` rebuilt successfully from the modular frontend.
- Ruff format/check, ratcheted Bandit, Tach, the 600-line budget (**576 files**), and `git diff --check`: pass.
- Experience pass: a returning researcher who dismisses an unfamiliar automatic refresh still has a concise,
  persistent Library-level route back to setup; neither entry point changes providers or makes an egress decision.
- Live packaged-Tauri clicks remain for the manual route-73/77 pass; no model download or inference was required to
  validate the version/presentation seam itself.
