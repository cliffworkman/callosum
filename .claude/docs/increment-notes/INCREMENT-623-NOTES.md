# Increment 623 — Dedicated demo experience and coverage review

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `2de7f927`.
Local only: not pushed, not merged, no version bump. Feature freeze holds: corrections only, all demo-scoped.

Review, matrix and historical receipts: `.claude/docs/research/2026-10-31_release-060-audit/DEMO_REVIEW_INC623.md`.
Evidence (gitignored, local): `C:\Users\cliff\callosum-worktrees\integrate-607-608\.local\validation-623\`.

## Implemented
- `00_bootstrap.jsx`: demo-only `renderTextLayer` adapter over pdf.js 4's `TextLayer`, on the global the viewer reads.
- `demo-runtime.js`: truthful answers for `/library/import-queue` and `merge-origin`; specific Delete and `/references/resolve` messages.
- `35j_modernization.jsx`: demo notice instead of the modernization and model panels; no reads.
- `20_synthesis.jsx`, `18_help.jsx`, `build_demo.py` about page: saved results and Help are from an earlier version.
- `test_website_how_it_works.py`: the assertion names the build command. Nothing weakened.
- README and QA route 01 corrected. Two new regression tests.
- `experience-coverage-v1.json`: renewed by `--refresh`, after the review.

## Key technical detail
- **Line 225 of `30_viewer.jsx` reads the global `pdfjsLib`, not the local of the same name in the earlier effect.** That is why an
  adapter on the loader's return value changed nothing, and why the failure was silent: the bare name resolves to the global, the call
  throws, and the catch treats a text-layer failure as harmless. The live app's UMD 3.11 global has `renderTextLayer`.
- **Build order.** `build_demo` validates the gate, so it cannot build while the review is stale, and the review needs a build. The
  pre-refresh runs patched `staleness_errors` inside the local harness process only; nothing shipped does. The final receipts below
  use the unpatched build.
- **Playwright's `wait_for_function` is refused by the demo's CSP** (no `unsafe-eval`). That is correct behaviour; the tests poll.

## Scientific behaviour
Unchanged. No threshold, label, model identity, retrieval or verification code was edited and no fixture was regenerated.

## Manual verification script
1. `python tools/demo/build_demo.py --output .local/demo-preview/callosum-demo --base-path /callosum-demo/`
2. `python -m http.server 8081 --directory .local/demo-preview`, open `http://127.0.0.1:8081/callosum-demo/`.
3. No alert on first load. Double-click a paper, Ctrl+F for a word on the page: it finds it. Drag across text: it selects.
4. Settings: a short notice, no controls, no HTTP error. Help: the earlier-version note. Synthesize → Ask: the same statement.

## Security
No trigger on the audit gate: no endpoint, fetch, ingestion path or dependency. Independent review remains outstanding.

- **Git Bash rewrites `--base-path /callosum-demo/`** into `/C:/Program Files/Git/callosum-demo/`, and the build accepts it. One of my
  manual builds came out that way. It did not affect any receipt below (the harness and tests call `build_demo()` directly), and the
  PowerShell build is correct. The README now says so. I did not change `_base_path`.

## Receipts
All on review commit `1c8b203a` plus the ledger renewal, with `CALLOSUM_DB_URL` overridden to a new disposable file under
`.local\validation-623\` and checked by `preflight_db.py`. No model loaded and no backend ran for the browser checks.

### The three historical failures
| Test | Cause | Outcome |
|---|---|---|
| `test_demo_experience_coverage.py::test_every_public_capability_claim_has_an_explicit_demo_disposition` | Gate stale at 576 | **Resolved** by the review |
| `test_demo_snapshot.py::test_static_build_is_self_contained_and_base_path_safe` | `build_demo` validates the gate, same cause | **Resolved** by the review |
| `test_website_how_it_works.py::test_primary_local_destinations_exist[demo/-target2]` | `dist-demo` absent. It is gitignored and CI builds it first, but CI's build was failing on the same gate | **Resolved** by a supported build. Not a website content defect |

Run together with their parametrized siblings: **5 passed**. The test still fails without a build, by design, now naming the command.

### Checks
| Check | Result |
|---|---|
| Demo gate, `check_demo_experience_coverage.py` | Pass. 120 capabilities: 55 saved-inspectable, 26 saved-partial, 6 missing-snapshot, 5 browser-local, 13 external, 14 live-only, 1 inapplicable; 12 homepage links |
| `test_demo_experience_coverage`, `test_demo_snapshot`, `test_website_how_it_works`, `test_frontend_assembly` | 122 passed, 1 skipped. The skip needs the curated source database, which is not present (environment) |
| `CALLOSUM_RUN_E2E=1 tests/e2e/test_demo_static.py` | 2 passed |
| Rendered acceptance, `browser_acceptance.py --label final`, unpatched build, Chromium headless, 1440px and 375px | **58 passed, 0 failed**, 0 console errors, 0 page errors, 1226 in-memory provider calls, 12 distinct HTTP paths, all under `/callosum-demo/` |
| Builds | `dist-demo/` and a PowerShell subpath build: `<base href="/callosum-demo/">`. Root build: `<base href="/">`. No CDN or loopback marker |
| QA surface map, tach, line budget, what's-new, bandit, scoped ruff, pre-commit hooks | Pass |
| **Website gate, `check_website_coverage.py`** | **Fails, as expected.** Inc 624's job. Not refreshed or declined |

Provider reads still answered with a non-2xx status in the run: the six pre-576 Settings reads, plus the deliberate 405s for Delete and
`/references/resolve`.

Screenshots and `result.json`: `.local\validation-623\final\`. Earlier preview runs used the in-process staleness bypass and are labelled
`preview-*`.

### Outcome by origin
- **Historical failures resolved:** the three above.
- **Historical failures remaining:** none of these three. The website gate remains, and has its own review.
- **New regressions:** none observed in what ran.
- **Environment:** one skip (curated source database).

**Final-code full suite: not run in this increment, still owed.** It was not attempted here because the host stopped the last two
attempts. The newest complete receipt remains `70273c01` (3791 passed, 12 skipped, 3 failed), which predates incs 621-623.

### Protected state
Research master unchanged (665096192 bytes, 2026-09-22 18:10). Desktop DB unchanged by stat only (613908480 bytes, 2026-10-29 17:16:50).
Main checkout's dirty state unchanged. JUNO not touched. No model downloaded, no library indexed, nothing re-adjudicated.

## Not run
Real static hosting, other browsers, a packaged build, Settings on a phone (not offered there, same as live).
