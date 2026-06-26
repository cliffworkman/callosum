<!-- qa-coverage
api: /settings, /settings/test-key
fe: 35_settings.jsx
-->

# ROUTE 35 - Settings

**Tier:** 1 local-stateful
**Goal:** Exhaust settings controls and persistence boundaries without touching external services.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **BYOK key secrecy (inc 146).** `GET /settings` must return STATUS ONLY — the response body containing the literal API-key value is **Critical**. The "Allow AI features" egress toggle must default to OFF on a clean instance; defaulting ON without an explicit toggle is **Critical** (invariant #3).
- **Coordinate honesty.** `exact` -> bbox rect; `region` -> scroll + note; `null` -> page-open, no rect. An approximate/absent location shown as an exact highlight is **Critical**.
- **Signal not verdict.** No hidden composite score; no "bad papers" accusation. Filters + visible counts only.

## Adversarial checklist

- paste ~50KB into every editable field; submit empty / whitespace-only
- double-click submit; rapid-click; navigate away mid-async-job
- malformed input where an identifier is expected
- deep-link / direct state for a non-existent id
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. Open settings. Confirm all controls render: theme, AI features (key + egress toggle), default axis cutoff, hide uncertain, watched-folder auto-rescan, and help assistant section.
2. Toggle theme on/off. Confirm app chrome changes and PDF page rendering remains light/readable.
3. Move the default-axis-cutoff slider through min/mid/max. Confirm labels/count previews stay signal-only.
4. Toggle hide-uncertain and watched-folder auto-rescan. Reload and confirm intended persistence or documented session-only behavior.
5. Open and close help-assistant settings. With egress unset, no genai request is allowed.
6. **AI features (BYOK).** Confirm the section renders: a (password-masked) Gemini API key input + Save, and an "Allow AI features" toggle that is **OFF** on the clean instance. Paste a fake key, Save; reload and confirm a "key saved" status with **no key value shown anywhere** (inspect `GET /settings` — body must not contain the pasted string). Toggle egress on then off; confirm no genai request fires (egress unset; this only writes the local store). Clear the key; confirm it reverts to "Not set".
7. **Test key (egress-gated).** With a key saved and **egress OFF**, click **Test key** → the result reports "Turn on Allow AI features…" and **no genai/`generativelanguage` request fires** (the egress toggle's promise: off ⟹ no outbound call). `POST /settings/test-key` returns `{ok:false}`; the response/DOM never contains the key value.
8. Resize to mobile while settings is open; confirm controls remain reachable and labels do not overflow.

## Pass criteria

- Every settings control is reachable, responsive, and has clear state.
- 0 console/page errors and 0 genai-host requests.
- Settings do not create hidden composite scores or accusation language.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_35_settings.md` + `screenshots/` (see `_TEMPLATE.md`).

