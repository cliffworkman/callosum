# Increment 151 — Validation-lock disclaimer + help-assistant toggle in Settings (BYOK deferred items)

Two of the deferred #39 follow-ons, both small Settings → AI features additions.

## Implemented

**A. Validation-lock disclaimer (the "quality, not correctness" note).** A standing footer note in Settings → AI
features: *"Whichever provider you choose, every summary sentence is still **verified locally** against your PDFs —
your model choice affects draft quality + coverage, never which citations are accepted."* This makes the
already-structural guarantee visible: citation verification (`summarization/verification.py`, re-run on every result
since inc 61) is local + provider-agnostic, so swapping to a weaker/cheaper model can change draft quality but can
**never** bypass verification. Frontend-only (`35_settings.jsx` + one CSS class `.settings-ai-note`, tokens only) +
a help-corpus line.

**B. Help-assistant toggle in Settings.** The AI help assistant already runs per-provider via the inc-149
`complete()` seam — the remaining gap was that its enablement was **env-only** (`CALLOSUM_HELP_ASSISTANT_ENABLED`).
Now it's a Settings toggle (mirroring the egress toggle), with the stored value overlaying the env default:
- `app_settings.set_help_assistant_enabled(bool)`; `GeminiConfig.from_environment()` overlays the stored flag.
- `routers/settings.py`: `SettingsStatus` gains `help_assistant_enabled` + `help_source` ("ui"/"env"); `PUT
  /settings` accepts `help_assistant_enabled`.
- `35_settings.jsx`: an **AI help assistant** switch (shown for any provider) with a sub explaining it's its OWN
  gate (sends only the question + public help docs, never library text) — independent of egress.

## Notes

- The help assistant stays a **separate** consent from the library egress gate (it never sends library text) — the
  toggle just moves that consent from an env var to the UI. **No new audit gate**: the only schema change is a
  non-secret bool toggle identical to the already-audited (inc 146) egress flag; no secret handling, no new
  external fetch, no migration. The validation disclaimer is frontend text.
- **Principles gate: aligned, non-triggering** — the disclaimer *reinforces* the core thesis (verification is the
  deterministic substrate's job, not the model's; inspectability over authority). It adds no claim/signal.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc151_aisettings.py`): Settings → AI features shows the **AI help
assistant** toggle (default off) + the `.settings-ai-note` disclaimer ("verified locally…"); toggling the switch
flips its state; 0 console/page/genai.

## Pytest

**552** (+2 `test_settings.py`: help-assistant PUT toggle + the `from_environment` stored-help overlay). `ruff`
clean; build + assembly green; QA surface **109/109 API + 561/561 FE, 0 uncovered** (the new toggle rides
`route_35`); help corpus help-assistant section updated (`HELP-DOCS-SYNCED` → 151). No migration.

## Next

inc 152 — OS-keychain key storage (optional `keyring` + file fallback; the last deferred #39 item; audited).
