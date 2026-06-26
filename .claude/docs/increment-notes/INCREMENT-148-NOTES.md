# Increment 148 — Synthesis pane egress-off nudge (frontend-only)

## Implemented

When AI is off, the Synthesis pane now shows a clear **"AI summaries are off"** nudge with a one-click
**Enable in Settings →** door, instead of a dead-end raw `DataEgressDisabledError` string.

- **`app/frontend/js/40_app.jsx`** — `paneCtx` gains `onOpenSettings: () => setSettingsOpen(true)` + a
  `settingsNonce` state bumped on the Settings modal's `onClose`, so panes re-read egress state when Settings closes.
- **`app/frontend/js/20_synthesis.jsx`** (`SynthesisPane`, + its `registerPaneSection` render threads
  `onOpenSettings`/`settingsNonce`):
  - **Proactive:** `api("/settings")` on mount + on `settingsNonce` change → `egressOff = !data_egress_enabled`;
    when off (and not currently showing the reactive error), a `.synth-nudge` banner renders above the controls.
  - **Reactive:** the `.errbox` path now renders the same nudge when `state.error` contains
    `DataEgressDisabledError` (instead of the developer-y exception text).
- **`app/frontend/styles.css`** — one `.synth-nudge` recipe (amber `--flag` status banner + a `.btn-link` action),
  mirroring `.synth-scope-note`; tokens only (rule #8).

## Key technical detail

Informational, not a block — local features stay usable; the nudge just gives the off-state a destination. It reuses
the inc-146 `GET /settings` (no new endpoint) and the inc-121 accordion's `paneCtx` injection. **No Principles
trigger** (a UX affordance over an existing state; the egress posture is unchanged). The `settingsNonce` re-read
means enabling AI in Settings clears the nudge on modal close without a reload.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc148_nudge.py`): egress OFF → open THEORY → Synthesis → the nudge
renders ("AI summaries are off…"); **Enable in Settings →** opens the Settings modal. 0 console/page/genai.

## Pytest

**536** unchanged (frontend-only; the wiring is headed-verified). `ruff` clean; build + assembly green. No new
endpoint → route-surface + QA surface unchanged (`GET /settings` already covered). help corpus synthesis section
updated (the egress-off line now describes the nudge; `HELP-DOCS-SYNCED` → 148). No migration.

## Next

inc 149–150 — multi-provider LLM (#39): OpenAI + Anthropic + a loopback **local** provider via httpx (no new deps);
the local provider is the flagship — summaries with **zero egress**. Carries a Principles-gate pass (local ≠ egress)
+ a security audit.
