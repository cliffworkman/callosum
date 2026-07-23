# Increment 349 — LibreOffice manual citation refresh mode (P1 item #13)

## Context

Increment 346 introduced explicit citation-only and bibliography-only refreshes. The next bounded part of the
roadmap's large-manuscript controls is manual citation refresh: users need to pause automatic citation formatting
without conflating that state with the existing independent automatic-bibliography preference.

## Implemented

- Added the document-local `CallosumCiteAuto` user property, default-on for every existing and new document. The
  **Toggle automatic citation formatting** Writer-menu action and `CallosumToggleCiteAuto` macro switch it.
- Ordinary insert, edit, style, delete, merge, and split flows now pass through `_auto_refresh`. Citation
  formatting and bibliography rebuilding are evaluated independently:
  - both on: the previous full automatic refresh;
  - citation on / bibliography off: citation-only mutation;
  - citation off / bibliography on: bibliography-only mutation;
  - both off: no citeproc request or document render write.
- Pausing never discards citation structure. A new citation remains a full ReferenceMark containing its CSL
  payload and visibly shows `{citation}` until the user runs **Refresh / renumber + bibliography** or **Refresh
  citations only**. Turning automatic formatting back on affects future changes; the confirmation directs the
  user to run one explicit refresh for existing pending changes.
- Explicit refresh commands deliberately bypass the citation-auto preference. The existing bibliography-auto
  preference still governs a normal full refresh; **Refresh bibliography only** remains its explicit override.
- Bibliography-panel include/exclude edits now call bibliography-only refresh, and **Insert bibliography here**
  explicitly updates only the bibliography. Neither deliberate bibliography operation can unexpectedly rewrite
  citations while formatting is paused.
- Extension version bumped 0.4.0 → 0.5.0 and `adapters/libreoffice/dist/callosum.oxt` rebuilt.
- Root/adapter README, served help, backlog, and project state updated.

## Scope boundary

This continues but does not complete P1 item #13. Selected-citation/current-section refresh, a persistent
dirty-state indicator, progress/cancellation, and incremental rendering remain open. There is no background
worker, endpoint, document-payload schema change, dependency, or new egress.

## Verification

- `uv run pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_oxt.py -q` — **58 passed**.
- `python adapters/libreoffice/run_roundtrip.py` — real headless LibreOffice + real seeded callosum server printed
  **`SELFTEST OK`**. The new spike proved the preference persists, a paused citation remains a structured
  placeholder, bibliography-only automatic updates remain independent, both-paused insertion leaves both
  surfaces untouched, and explicit refresh resolves pending fields.
- `uv run pytest -n 4 -q` — **1424 passed, 1 skipped** in 540.54s.
- `uv run ruff check .` / `uv run ruff format --check .` — clean (**478 files**).
- `python tools/check_line_budget.py` — clean (**351 application-source files** within cap).
- `python tools/qa/build_surface_map.py check` — **260/260 API surfaces covered**; 21 unchanged frontend checklist
  entries, no new app browser surface.

## Gates

- **Principles / A-A:** non-triggering. The feature controls deterministic formatting of the user's own
  structured citations and creates no literature claim, signal, ranking, or judgment.
- **Security:** triggered by the multi-file user feature. Audit
  `2026-07-23_libreoffice-manual-refresh.md` is **PASS**: fixed document-local state, no new host/endpoint/file
  path/dependency/secret, and both-paused mode suppresses rather than adds requests.
- **QA:** the computed app API/frontend surface is unchanged; the new Writer action is covered by the OXT
  action-registry test and required real-UNO harness.
- **Experience pass (deadline writer revising a large manuscript, code/help-grounded because delegation was not
  available):** the control is adjacent to the explicit refresh choices and its confirmation explains both the
  recovery action and separate bibliography state. New inserts visibly show `{citation}`. The remaining friction
  is that edits/style changes can be stale without a persistent dirty indicator; that roadmap requirement remains
  explicitly queued rather than silently treated as complete.

## Manual verification debt

Cliff should install 0.5.0 and click the new toggle off/on once in real Writer, then insert and edit a citation
while paused and invoke **Refresh citations only**. Headless UNO proves package dispatch and mutation behavior,
not actual menu visibility or message-box feel. The inc-344/345 citations-panel controls and inc-346 partial
refresh commands retain their existing manual click-through debt.

## Next

The visible dirty-state indicator is the most direct usability complement to manual mode. Selected-citation and
current-section refresh are also bounded follow-ons; progress/cancellation and true incremental rendering require
a larger render-architecture pass.
