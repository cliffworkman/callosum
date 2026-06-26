# Increment 147 — "Test this key" (egress-gated key validation)

## Implemented

A **Test key** button in Settings → AI features confirms a pasted Gemini key works before the user relies on it.

- **`app/backend/api/routers/settings.py`** — `POST /settings/test-key` → `KeyTestResult{ok, detail}`. Logic:
  egress OFF → `{ok:false, detail:"Turn on “Allow AI features” first…"}` and **no outbound call**; no key →
  `{ok:false, detail:"No API key is set…"}`; else `_ping_gemini(model, key)`. Always HTTP 200 (a result, not an
  error). `_ping_gemini` makes a minimal **non-library** call (`generate_content(contents="Reply with the single
  word OK.")`) — the key is never logged and any error is **redacted** (`str(exc).replace(key, "***")`) +
  length-capped before reaching `detail`.
- **`app/frontend/js/35_settings.jsx`** (`AiSettings`) — a Test key button + a ✓/✗ result line (`apiPost(
  "/settings/test-key", {})`), shown when a key is available. One CSS block `.settings-keytest` (+ `.ok` green
  `--verified` / `.err` amber `--flag-ink`), tokens only (rule #8).

## Key technical detail

**Gated on egress ON.** The test is a real call to Google, so it only fires when "Allow AI features" is on — when
the toggle is off, Callosum makes **zero** outbound AI calls (the toggle's promise stays ironclad; the strongest
reading of invariant #3). No second egress path is introduced. The key-test sends a fixed throwaway prompt, never
library text. **Principles gate: non-triggering** (it produces no claim/signal about the literature; it strengthens,
not weakens, the egress posture).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc147_testkey.py`): a key saved + egress OFF → click **Test key** →
the result reads "Turn on “Allow AI features” first…", **0 genai requests**, and the key never appears in the DOM.
0 console/page errors. (The egress-ON happy path is unit-tested with a monkeypatched pinger — a headed run never
fires a real Gemini call.)

## Audit

`.claude/security-audits/2026-06-26_test-key.md` **PASS** — non-library payload, egress-gated, key never
logged/returned (redacted errors), no new dependency, single bounded call per click.

## Pytest

**536** (+4 `test_settings.py`: egress-off → no ping, egress-on + no key, egress-on + key → ping result,
`_ping_gemini` redaction). Route-surface extended (`POST /settings/test-key`). `ruff` clean; build + assembly green;
QA surface **109/109 API + 549/549 FE, 0 uncovered** (`route_35_settings.md` extended). No migration.

## Next

inc 148 — the synthesis-pane egress-off nudge; then inc 149–150 multi-provider LLM (#39).
