# Increment 518 — fix CI, red since 2026-08-27 (three distinct, unrelated issues)

## Implemented

Cliff asked to resolve the failing CI before switching to Codex. Checked `gh run list` first rather than
assuming today's Word work caused it: **CI has been failing since `feat: consolidate Feed...` (2026-08-27
17:53:40), well before any Word-parity work started** — the last green `CI` run was the v0.4.1 version bump on
2026-08-24. Confirmed via `gh run view --log-failed` this is **three separate, unrelated root causes**, not one:

**1. Stale Bandit baseline (`lint-and-test` job).** `.bandit-baseline.json` was last regenerated 2026-08-02
(the file's own `generated_at`), despite being touched-but-not-regenerated more recently. `tools/run_bandit.py`
is a ratcheted gate — it only fails on findings *not* already in the committed baseline. Ran a fresh scan and
diffed it against the old baseline by `(test_id, filename, line_number)` rather than trusting the raw "84 vs
73" count: **most of the apparent "new" findings were just line-number drift** on already-reviewed findings in
`providers.py`/`app_settings.py`/`library_bundle.py`/`word.py` from unrelated edits over the past 3+ weeks. The
only genuinely new findings were `app/backend/grobid_lifecycle.py`'s Docker subprocess calls (inc 507, B404/
B603/B607 — subprocess usage, partial-path execution) — already reviewed and documented as safe in
`.claude/security-audits/2026-08-28_grobid-docker-lifecycle.md` ("every subprocess argv element a fixed
constant... no injection surface"), matching the same accepted pattern `word.py`'s own `os.startfile`/
subprocess calls already have in the baseline. Regenerated the baseline from a fresh scan (same command
`run_bandit.py` itself runs, `-c pyproject.toml -r app/backend integrations sync_server feedback_relay`);
`run_bandit.py` now exits 0 locally.

**2. Two stale e2e literal-text assertions (`e2e-smoke` job).** The inc-505 Title-Case sweep (this same overall
session, before this visible portion started) updated `tests/test_frontend_assembly.py`/
`test_funding_discovery.py`'s literal-text assertions but **missed `tests/e2e/`** — a different test category
(Playwright, not covered by whatever search found the other stale strings). Two buttons' rendered text changed
from the sweep but the e2e tests still expected the old casing with `exact=True`, so `Locator.wait_for`/
`.click()` timed out (30s/90s) rather than failing fast:
- `"Reset read/star practice"` → `"Reset Read/Star Practice"` (`app/frontend/js/30e_feed.jsx:285`)
- `"Audit LMM reporting"` → `"Audit LMM Reporting"` (`app/frontend/js/10k_wip_checks.jsx:54`)

Ran the **full** `tests/e2e` suite locally after fixing both (not just the two that failed in CI) to check for
any other lurking mismatch — 13/13 passed, confirming these were the only two.

**3. Orphaned QA-route mapping + a real fingerprint-drift acknowledgment (`Website/showcase coverage drift
check`).** `www/showcase-coverage.json` still mapped `route_87_followed_authors` → `#cap-followed-authors`, but
the Feed-consolidation commit (`ec6fc0f`, this same session) retired the standalone Followed-Authors tab and
its QA route file — the mapping pointed at a route that no longer exists. Removed the stale mapping; folded the
capability mention into the existing `#cap-feed` chip ("Feed subscriptions" → "Feed subscriptions (incl.
followed authors)") rather than silently dropping the information, since the capability itself still exists,
just consolidated. Separately, the check's broader source-fingerprint (covering `app/frontend/**`,
`adapters/word/**`, etc.) had drifted since the 2026-08-24 review — **listed every commit touching fingerprinted
paths since then via `git log c7e242c..HEAD -- <paths>`** (14 commits, all from this same session: Feed
consolidation, GROBID Docker lifecycle, and the full incs 508-517 Word/Docs parity arc) rather than guessing at
scope. Checked `#cap-word`'s actual current copy against today's substantial Word feature additions — no update
needed, the copy was already deliberately hedged ("Word and Google Docs are represented at their actual
supported integration level, without implying identical capabilities") and never claimed feature parity to
begin with. Confirmed GROBID makes no showcase claims at all (matches its own existing QA-exclusion reasoning).
Refreshed with an honest, scoped review note — explicitly did **not** claim a full visual/screenshot
re-capture, since no screenshot-affecting UI changed this session.

### Files

- `.bandit-baseline.json` — regenerated from a fresh scan.
- `tests/e2e/test_demo_static.py`, `tests/e2e/test_smoke.py` — two literal button-text strings corrected.
- `www/showcase-coverage.json`, `www/showcase.html` — orphaned route mapping removed, chip label updated,
  review receipt refreshed.

## Manual verification script

All verified directly this session, not deferred: `uv run python tools/run_bandit.py` (exit 0),
`CALLOSUM_RUN_E2E=1 uv run pytest tests/e2e -q` (13 passed), `uv run python tools/qa/check_website_coverage.py`
(exit 0, "69 QA routes... 20 current figures"), `uv run python tools/check_line_budget.py` (OK), `uv run python
-m tach check` (OK), `uv run python tools/demo/build_demo.py` (succeeded), `uv run pip-audit -r requirements.txt
--strict` (clean), and the **full offline suite**: `uv run pytest -n auto -q` → **2563 passed, 3 skipped**
(matches `CLAUDE.md`'s already-stated count exactly — confirms this fix didn't regress anything).

## Pytest / tests

Full suite: 2563 passed, 3 skipped (unchanged count — no test logic added/removed, only two literal strings
corrected and one baseline/coverage data file regenerated). e2e: 13/13 passed.
