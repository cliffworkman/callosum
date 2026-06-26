# Increment 128 — split 40_app.jsx (relieve the 600-line cap)

A behavior-preserving refactor clearing the standing rule-#1 risk: `40_app.jsx` had crept to **590/600** (flagged
since inc 126/127). No user-facing change.

## Implemented

- **New chunk `app/frontend/js/04_layout.jsx`** (107 lines) holds, extracted verbatim from `40_app.jsx`:
  - the module-scope **layout helpers** — `_loadLayout` / `_saveLayout` / `_clampW` / `_beginDrag`, the
    `LEFT_*` / `RIGHT_*` width constants, and the **`Divider`** component;
  - a new **`useUiPrefs()` custom hook** = the app's persisted UI state (theme; the axis hide-uncertain +
    cutoff defaults; auto-scan-watched; side-panel widths/open + their localStorage effects; the
    THEORY/METHODS accordion-open state; transient Reading mode), lifted out of `App` unchanged.
- **`40_app.jsx`** (**590 → 514**): the helper block is gone (now in 04), and `App` replaces ~50 lines of
  pref/layout `useState`/`useEffect`/`useCallback` with one `const { … } = useUiPrefs();` destructure
  (`settingsOpen`/`helpOpen` stay in `App` — they're modal toggles, not persisted prefs).

## Key technical detail

- **Chunk load order:** `04_layout.jsx` loads early (after `00_lib`), so its module-scope consts/hook are defined
  before any consumer runs. `30_viewer.jsx` already used `_loadLayout`/`_saveLayout` (which previously hoisted from
  the *last* chunk, 40) — moving them earlier only makes them defined-before-use. The IIFE keeps one shared scope,
  so behavior is identical.
- **`useUiPrefs` is the persisted-UI-state cluster** — a cohesive, self-contained hook (no dependency on the
  library/focus clusters), so the extraction is mechanical and low-risk. Verified behavior-preserving below.

## Manual verification

- Build OK; `tests/test_frontend_assembly.py` green (the new chunk auto-globbed); full pytest **471 passed, 1
  skipped** (frontend-only — unchanged); `ruff` clean; QA surface check 0 uncovered.
- **Headed smoke** `.local/visual/drive_inc128_layout.py`: the app renders (all 6 accordion sections); **dark-mode
  toggles** (data-theme flips); **left panel collapse works AND persists across reload** (the `useUiPrefs`
  localStorage effects); **Reading mode + Esc** work; **0 console/page errors**.

## Pytest

471 passed, 1 skipped (no test changes — behavior-preserving). `ruff` clean; surface check 0 uncovered (91 / 484).
