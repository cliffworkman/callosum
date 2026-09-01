<!-- qa-coverage
api: GET /health, GET /settings, PUT /settings
fe: 04e_onboarding.jsx, 04c_status.jsx, 35b_providers.jsx, 35a_mypubs.jsx, 27_scan.jsx, 28_import.jsx, 28b_bundle.jsx, 14_axes_edit.jsx, 17_axes_suggest.jsx
-->

# ROUTE 77 — First-run onboarding wizard

**Tier:** 1 local-stateful
**Goal:** Exhaust the first-run wizard (inc 416) and the versioned Local AI refresh (inc 553). A fresh install
sequences five existing settings screens; a pre-v2 completed desktop install sees only the shared AI-provider step
and completion screen once. The sharpest checks: identity is never overwritten, Local AI setup is real rather than
duplicated UI, cloud egress remains off by default, and every skip/not-now exit is reachable and durable.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Egress unset. To force first-run onboarding, ensure
`~/.callosum/app-settings.json` (or `CALLOSUM_SETTINGS_PATH`) has neither `onboarding_completed` nor
`onboarding_version` (a fresh settings file satisfies this). To test a returning desktop user, seed
`{"onboarding_completed": true}` with no version; packaged Tauri must surface the one-time Local AI refresh.
To test the "existing tester" identity path, first `PUT /settings` a My
Publications profile via `PUT /my-publications/profile {"display_name": "Ada Lovelace", "name_variants":
["A. Lovelace"], "orcid": "0000-0002-1825-0097"}` before loading the app.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.**
- **Provider/egress gate.** The AI step includes the real managed **Local AI** card and **Set up Local AI** action.
  With egress unset, the cloud-provider toggle must render OFF/unchecked on load, with no
  pre-checked box and no "Continue (recommended)"-style pressure toward turning it on. Any request to a
  `generativelanguage`/Gemini/genai host with egress off is **Critical**.
- **Never overwrites existing identity data.** With a profile seeded per the Environment note, the identity
  step must show the real name/variants/ORCID — never blank fields — regardless of how quickly you click
  through. This is **Critical** if violated (real user data loss).
- **"Skip setup" is always visible and always works** during first-run setup. **Not now** is the refresh exit.
  Either must result in `GET /health` reporting `onboarding_completed:true` and `onboarding_version` equal to
  `onboarding_current_version`; reload must not re-nag.
- **No dead ends.** Every step's Next/Back/Skip/choice buttons are completable; the import/axis steps'
  "Skip this step →" is always present alongside the two real tool choices.
- **Setup cannot be mistaken for an inert button.** While managed Local AI setup is active, the AI step names its
  current phase, shows real byte progress/ETA where measurable, and disables **Next**. The explicit **Continue in
  background** exit remains available and must not cancel the Tauri-owned setup.

## Adversarial checklist

- rapid-click "Next →" through all five steps without touching anything — must reach the "You're all set" screen
  with no error
- on the identity step, click "Refresh my papers" (or press Enter in the variant field) as fast as possible
  after the wizard opens (before the profile GET could plausibly have resolved) — with a seeded profile, confirm
  the saved result still matches the original data, not blanks
- click "Skip setup" on the very first step (identity) — confirm the wizard closes immediately and does not
  reappear on reload
- with legacy completed state and no version, confirm the desktop refresh starts on **AI features**, contains only
  AI + Done, and **Not now** prevents recurrence; the Library notice must still reopen the same AI-first refresh
- on the import step, pick "Import EndNote RIS / citations file…", then click Back — confirm the choice screen reappears
  cleanly (no stuck state)
- resize to `375x812` — the wizard card fits without horizontal overflow, and its internal step body scrolls if
  tall content (e.g. a populated watched-folder list) exceeds the card height

## Steps

1. Baseline screenshot: load the app fresh (no `onboarding_completed` key) → the wizard appears, blocking, with
   the identity step showing empty fields (no prior profile).
2. Step through identity: enter a name, click Next.
3. Step through AI providers: confirm **Local AI** offers **Set up Local AI** with no API key and cloud egress is off.
   Start setup and confirm **Next** immediately disables while the setup card advances through named phases. During
   downloads confirm the real MiB counter moves and the ETA is explicitly approximate; during hashing/startup it must
   not invent a percentage. Confirm the new feedback scrolls into the wizard's visible body. Use **Continue in
   background**, open Status, and click **Setting up Local AI** to return to the same live AI step. Let setup reach
   **Local AI: Ready**, then click Next. Repeat once with an injected failure and confirm retry/repair guidance rather
   than a cloud API-key instruction.
4. Step through library folder: confirm it shows the default watched library folder; click "Add + scan" with a
   folder path, confirm progress appears (and, separately, appears in the Status popover); click Next (or use
   the step's own "×"/"Close", confirming both reach the same next step).
5. Step through import: choose "Import EndNote RIS / citations file…", pick a small BibTeX file, confirm the import summary,
   click Next.
6. Step through axis: choose "Create one manually…", name an axis, confirm it saves, reaches the final screen.
7. Confirm the "You're all set" screen, click Finish. Confirm the wizard is gone and `GET /health` now reports
   `onboarding_completed:true` and current `onboarding_version`. Reload — the wizard must NOT reappear.
8. **Existing-tester path**: reset `onboarding_completed` to unset, seed a My Publications profile directly via
   the API (see Environment), reload — confirm the identity step shows the real seeded name/variants/ORCID, not
   blanks, then click through or Skip.
9. **Returning-user refresh:** seed only `onboarding_completed:true`, launch packaged desktop, and confirm the
   two-screen **What's new in Callosum — AI features** refresh appears once. Confirm **Not now**, Next/Finish, and
   real Local AI setup each persist the current version and do not recur on reload.
10. Dismiss/finish the refresh, then click **Set up Local AI** in the Library announcement. Confirm it reopens
    directly at the same AI step even though onboarding is current; no identity/library/import/axis step appears.
11. Adversarial: rapid-click-through, Enter-key race on identity, mobile viewport check (see checklist above).

## Pass criteria

- The full wizard appears once on a fresh install; the AI-only refresh appears once on a legacy completed desktop.
- The identity step never shows or saves blanks over an existing profile.
- The AI step exposes the real Local AI setup and keeps cloud egress off by default.
- An active Local AI setup cannot be advanced past accidentally, survives explicit background dismissal, and remains
  observable/reopenable through Status without a duplicate setup process.
- The Library announcement can always reopen the AI-only refresh after a skip/dismiss.
- "Skip setup" works from every step and always marks onboarding as done.
- Each of the five steps' embedded tool actually performs its real action (scan/import/axis-create), visible
  in the Status popover where applicable.
- 0 console/page errors; **0 genai-host requests** with egress off; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_77_onboarding_wizard.md` + `screenshots/` (see `_TEMPLATE.md`).
