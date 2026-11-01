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

## Receipts
