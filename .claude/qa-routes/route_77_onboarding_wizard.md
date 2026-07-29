<!-- qa-coverage
api: GET /health, GET /settings, PUT /settings
fe: 04e_onboarding.jsx, 35a_mypubs.jsx, 27_scan.jsx, 28_import.jsx, 28b_bundle.jsx, 14_axes_edit.jsx, 17_axes_suggest.jsx
-->

# ROUTE 77 — First-run onboarding wizard

**Tier:** 1 local-stateful
**Goal:** Exhaust the new first-run wizard (inc 416) — a full-screen overlay shown once per machine, sequencing
five existing settings screens. The sharpest checks: it never overwrites an existing My Publications profile
with blanks, it never defaults the AI/egress toggle on, and "Skip setup" is always a real, reachable exit.

## Environment

Clean seeded instance (`_TEMPLATE.md` → Environment). Egress unset. To force the wizard to appear, ensure
`~/.callosum/app-settings.json` (or `CALLOSUM_SETTINGS_PATH`) has no `onboarding_completed` key (a fresh
settings file already satisfies this). To test the "existing tester" path, first `PUT /settings` a My
Publications profile via `PUT /my-publications/profile {"display_name": "Ada Lovelace", "name_variants":
["A. Lovelace"], "orcid": "0000-0002-1825-0097"}` before loading the app.

## Standing assertions

- **Console-error budget = 0.** Any console `error` ≥ Medium; any `pageerror` ≥ High.
- **No uncompletable control.**
- **Egress gate.** With egress unset, the AI/BYOK step's toggle must render OFF/unchecked on load, with no
  pre-checked box and no "Continue (recommended)"-style pressure toward turning it on. Any request to a
  `generativelanguage`/Gemini/genai host with egress off is **Critical**.
- **Never overwrites existing identity data.** With a profile seeded per the Environment note, the identity
  step must show the real name/variants/ORCID — never blank fields — regardless of how quickly you click
  through. This is **Critical** if violated (real user data loss).
- **"Skip setup" is always visible and always works**, at every one of the five steps, and always results in
  `GET /health`'s `onboarding_completed` reporting `true` afterward (confirmed via the network tab or a
  follow-up `GET /health`).
- **No dead ends.** Every step's Next/Back/Skip/choice buttons are completable; the import/axis steps'
  "Skip this step →" is always present alongside the two real tool choices.

## Adversarial checklist

- rapid-click "Next →" through all five steps without touching anything — must reach the "You're all set" screen
  with no error
- on the identity step, click "Refresh my papers" (or press Enter in the variant field) as fast as possible
  after the wizard opens (before the profile GET could plausibly have resolved) — with a seeded profile, confirm
  the saved result still matches the original data, not blanks
- click "Skip setup" on the very first step (identity) — confirm the wizard closes immediately and does not
  reappear on reload
- on the import step, pick "Import citations file…", then click Back — confirm the choice screen reappears
  cleanly (no stuck state)
- resize to `375x812` — the wizard card fits without horizontal overflow, and its internal step body scrolls if
  tall content (e.g. a populated watched-folder list) exceeds the card height

## Steps

1. Baseline screenshot: load the app fresh (no `onboarding_completed` key) → the wizard appears, blocking, with
   the identity step showing empty fields (no prior profile).
2. Step through identity: enter a name, click Next.
3. Step through AI/BYOK: confirm the egress toggle is off; leave it off; click Next.
4. Step through library folder: confirm it shows the default watched library folder; click "Add + scan" with a
   folder path, confirm progress appears (and, separately, appears in the Status popover); click Next (or use
   the step's own "×"/"Close", confirming both reach the same next step).
5. Step through import: choose "Import citations file…", pick a small BibTeX file, confirm the import summary,
   click Next.
6. Step through axis: choose "Create one manually…", name an axis, confirm it saves, reaches the final screen.
7. Confirm the "You're all set" screen, click Finish. Confirm the wizard is gone and `GET /health` now reports
   `onboarding_completed: true`. Reload the app — the wizard must NOT reappear.
8. **Existing-tester path**: reset `onboarding_completed` to unset, seed a My Publications profile directly via
   the API (see Environment), reload — confirm the identity step shows the real seeded name/variants/ORCID, not
   blanks, then click through or Skip.
9. Adversarial: rapid-click-through, Enter-key race on identity, mobile viewport check (see checklist above).

## Pass criteria

- The wizard appears once on a fresh install and never again after Finish/Skip.
- The identity step never shows or saves blanks over an existing profile.
- The AI/BYOK step's egress toggle is off by default, never pre-checked.
- "Skip setup" works from every step and always marks onboarding as done.
- Each of the five steps' embedded tool actually performs its real action (scan/import/axis-create), visible
  in the Status popover where applicable.
- 0 console/page errors; **0 genai-host requests** with egress off; mobile viewport has no overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_77_onboarding_wizard.md` + `screenshots/` (see `_TEMPLATE.md`).
