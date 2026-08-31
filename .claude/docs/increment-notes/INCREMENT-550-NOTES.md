# Increment 550 — fix CI: reconcile the demo e2e smoke test with the 5-paper corpus

## Implemented

`gh run list` showed the GitHub Actions `CI` workflow's `e2e-smoke` job failing on the last two
pushes to `main` (inc 548's demo-corpus growth, and inc 549's showcase hotspot work, which just
inherited the failure). Root cause: `tests/e2e/test_demo_static.py` — a real-Playwright browser
smoke test over the built, backend-free static demo, opt-in via `CALLOSUM_RUN_E2E=1` — hardcoded
dozens of exact counts/strings against the demo's **old 3-paper corpus and old all-verified
synthesis**, and was never updated when:
- **inc 543** changed the saved Synthesize · Ask demo synthesis to a realistic verified+flagged
  mix (previously all-verified) — `.summary-sentence.flagged` went 0→4, `.overview-line` went 2→1.
- **inc 548** grew the curated demo corpus 3→5 papers to clear the `MIN_DOMAIN_PAPERS = 4` gate
  for the `cap-domains` capability.

Fixed by building a **read-only diagnostic harness** (mirrors the real test's exact click-path but
prints actual values instead of asserting) and running it against a real, locally-built copy of
the current static demo through real headless Chromium. Every replacement value in the test file
is a directly observed, live-captured fact — including re-verifying two spots where a naive
unguarded read raced ahead of the real UI (a debounced search filter, and an ambiguous
`.pane-tab.active` selector that briefly grabbed the wrong pane) with properly sequenced
re-checks. The full old→new table lives in
`.claude/backups/plans/2026-08-31_fix-ci-demo-e2e-staleness.md` if ever needed again; the summary
is: 12 straightforward count/text updates, a full rewrite of the
per-paper statcheck/Checklists loop from `range(3)` with two binary branches to `range(5)` with
per-paper branching (the two new papers don't fit the old shape — one has no processed PDF at
all, the other has a processed PDF but nothing statcheck-eligible), and a 5-row
`expected_meta_reference` tuple (was 3 rows; one row is byte-identical to before, confirming it's
genuinely unaffected).

**A second, related bug was found and fixed along the way** (not just test staleness):
`app/frontend/js/31_mypubs_dashboard.jsx`'s My-Publications "domains" note still hardcoded *"This
two-paper demo uses one explicitly saved, hand-curated presentation so it does not fabricate a
clustering result…"* — text written when the demo had 2 confirmed publications and one
hand-authored fallback domain. Per inc 548's own notes, the demo now genuinely has 4 confirmed
publications and 2 real, backend-computed domains (`/my-publications/domains` job output, no
fabrication) — so the note was factually wrong about the very thing inc 548 fixed. Replaced with
an accurate description of the current real state. Confirmed via grep this string appears nowhere
else in the repo, and the one test assertion that touches it (`to_contain_text("starts at four
confirmed publications")`) only checks a substring that's kept verbatim either way.

## Key technical detail

Rebuilding `callosum-app.html` (required — a separate `tests/test_frontend_assembly.py::
test_built_artifact_is_in_sync` compares the tracked file byte-for-byte against a fresh
`build_frontend_document()` call) hit a genuine **local-machine-only** blocker: `subprocess.run()`
calling `node`/esbuild with the full ~900KB concatenated JSX payload hung indefinitely through
Python on this machine specifically — reproduced consistently across `capture_output=True`,
plain file-redirected stdin/stdout, bytes mode, and multiple clean process retries, while the
*identical* `node esbuild ...` invocation succeeded in ~13s when run directly as a backgrounded
shell command monitored within one shell session. Small esbuild inputs (a few bytes) worked fine
either way; only the full-size real payload hung, and only through Python's subprocess. Root
cause not fully isolated (did not reproduce with `--collect-only`-only pytest either, suggesting
something environmental/session-specific rather than an esbuild or payload-size issue in
isolation) — flagged as a local dev-environment quirk, not a code defect (CI's own Ubuntu runner
builds this exact source fine, confirmed by every prior green `lint-and-test` run).

Worked around by reconstructing `callosum-app.html` via the same logic
`build_frontend_document()` uses (`template.replace("{{STYLES}}", styles).replace("{{SCRIPT}}",
script)`), computing each input independently and verifying each in isolation before combining:
`assemble_jsx()`'s output confirmed **byte-identical** to a manual sorted-glob concatenation;
`script` obtained by running the *exact* `_ESBUILD_ARGS` (`--loader=jsx --jsx=transform
--jsx-factory=React.createElement --jsx-fragment=React.Fragment --format=iife --target=esnext`)
directly via the shell (0 errors); final assembly confirmed via `git diff --stat` showing exactly
the one intended content edit and nothing else, plus the same sanity assertions
`test_assembles_and_placeholders_consumed` makes (placeholders consumed, no Babel remnants, real
`React.createElement(` output, real `#root` mount point).

## Manual verification script

1. `CALLOSUM_RUN_E2E=1 pytest tests/e2e/test_demo_static.py -q` once the local esbuild-via-Python
   hang clears (or from a fresh machine/session) — should pass end-to-end.
2. `python tools/qa/build_surface_map.py check` / existing QA routes — unaffected, no surface
   changed, only demo-fixture verification text.
3. Push to `main`, then `gh run list --branch main` — confirm the `CI` workflow (`lint-and-test` +
   `e2e-smoke`) goes green on the new commit.

## Pytest

`ruff format` + `ruff check tests/e2e/test_demo_static.py` — clean. `python -m py_compile
tests/e2e/test_demo_static.py` — compiles. Full local pytest run blocked by the environment issue
above; CI (a clean environment, confirmed unaffected on every prior push) is the authoritative
gate for this change, per the plan's own verification step.
