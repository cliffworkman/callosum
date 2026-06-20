## What & why

<!-- One or two sentences: what this changes and the motivation. -->

## Checklist

- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `pytest` is green (added/updated tests for new behavior)
- [ ] If the frontend changed: re-ran `python tools/build_frontend.py` + the opt-in e2e smoke
- [ ] No file under `app/` or `integrations/` exceeds 600 lines
- [ ] No secrets committed (`.env` / API keys stay local)
- [ ] If it produces a claim/signal about the literature or touches egress/provenance: ran the
      **Principles alignment gate** (and proposed the aligned alternative where at odds) — see `.claude/PRINCIPLES.md`
- [ ] Security-sensitive change? Noted the audit (see the audit gate in `.claude/CLAUDE.md`)

## Notes for reviewers

<!-- Anything non-obvious: trade-offs, follow-ups, screenshots for UI changes. -->
