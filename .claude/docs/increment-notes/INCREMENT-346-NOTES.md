# Increment 346 — LibreOffice partial refresh controls (P1 item #13)

## Context
The next safe LibreOffice P1 slice after the citations panel (inc 344) and bibliography editing (inc 345).
Roadmap item #13 calls for large-manuscript refresh/performance controls. The adapter already had a
transactional full-document refresh and a document-level automatic-bibliography toggle, making independent
citation-only and bibliography-only commands the smallest useful extension of proven machinery.

## Implemented
- `refresh()` now accepts explicit citation and bibliography mutation controls while always rendering the full
  ordered citation set. Partial document writes therefore cannot change citeproc context: numeric order,
  author-date disambiguation, uncited bibliography items, and bibliography exclusions see the same input as a
  full refresh.
- `refresh_citations()` updates every live citation mark but leaves the managed bibliography byte-for-byte
  untouched.
- `refresh_bibliography()` rebuilds only the managed bibliography and leaves every live citation mark untouched.
  Because this is a deliberate user command, it works even when automatic bibliography rebuilding is paused.
- The Writer **Callosum** menu exposes both commands immediately after **Refresh / renumber + bibliography**.
  Matching macro entry points (`CallosumRefreshCitations`, `CallosumRefreshBibliography`) remain available for
  by-hand macro installs and custom keyboard bindings.
- Extension version bumped 0.3.0 → 0.4.0 and the `.oxt` rebuilt.
- README and served help updated. This also fixed pre-existing inc-345 documentation drift: **Citations in this
  document…** was still described as read-only despite its include-uncited/exclude-cited controls.

## Scope boundary
This starts, but does not complete, P1 item #13. Manual-refresh mode / pause formatting, selected-citation and
current-section refresh, dirty-state/progress/cancellation, and incremental rendering remain open. This
increment introduces no background process, document-schema change, endpoint, dependency, or egress.

## Verification
- `uv run pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_oxt.py -q` — **52 passed**.
- `python adapters/libreoffice/run_roundtrip.py` — actual **`SELFTEST OK`** from real headless LibreOffice and a
  real seeded callosum server. The new spike deliberately wrote stale citation text and stale bibliography text,
  disabled automatic bibliography rebuilding, then proved bibliography-only repaired only the bibliography and
  citation-only repaired only the citation.
- `uv run pytest -n 4 -q` — **1414 passed, 1 skipped** in 594.20s.
- `uv run ruff check .` / `uv run ruff format --check .` — clean (**478 files formatted**).
- `python tools/check_line_budget.py` — clean (**351 application-source files** within cap).

## Gates
- **Principles / A-A:** non-triggering. This deterministically reformats the user's own citations in their chosen
  CSL style; it adds no literature claim, ranking, judgment, or signal.
- **Security:** non-triggering. Same loopback render endpoint and existing document mutation path; no new input,
  output, capability, host, persistence schema, or egress.
- **QA:** no app API/frontend surface changed, so the computed browser/API surface map is unchanged. UNO mutation
  is covered by the repository's required real-Writer harness instead.
- **Experience pass (deadline writer with a large manuscript, run locally because agent delegation was not
  permitted in this session):** the writer reaches the existing Callosum menu after moving citations and sees
  the full refresh plus two plainly named, adjacent narrower actions. The intended next step is direct, with no
  mode to remember and no destructive choice. No fix-now friction found. The actual menu clicks remain a human
  Writer check because headless UNO proves dispatch/package wiring and mutation behavior, not menu visibility.

## Manual verification debt
Cliff should confirm the two menu items are visible and invoke each once in real Writer after installing 0.4.0.
Do not treat the headless harness as a manual menu-click claim. The inc-344/345 citations-panel buttons remain
the same outstanding manual click-through.

## Next
Continue a separate bounded P1 slice, or move to backlog #36's batch **Draft all un-filled rows** and
retrieval-narrowed extraction. Do not imply the rest of item #13 shipped here.
