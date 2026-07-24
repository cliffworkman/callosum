# Increment 365 — Shared citation-style manager

## Context

The citation engine and Writer adapter already supported seven bundled CSL styles, but users had to recognize raw
style ids and had no shared place to search, preview, favorite, revisit, or choose an application default. P1 item
#9 called for one style-management model shared by Callosum and the word-processor adapters.

## Implemented

- `style_manager.py` parses descriptive metadata from the actual bundled CSL XML: canonical/short title, summary,
  citation format, discipline fields, dependent-parent relationship, and default locale.
- `GET /citations/styles` now returns that catalog plus locales, application default, favorites, and bounded
  recents. Search matches every token across names, ids, acronyms, summaries, citation format, and fields and is
  capped at 120 characters.
- `POST /citations/styles/preview` renders two explicitly fictional records through the real citeproc engine,
  including first/subsequent note positions and a bibliography.
- `PUT /citations/styles/preferences` stores the application default/locale, favorites, and up to eight recent
  styles in the existing local settings file.
- Settings gained a full-width **Citation styles** card with Installed/Favorites/Recent views, search, descriptive
  style details, locale, favorite/default actions, and real preview. `#citation-styles` opens Settings and scrolls
  directly to the manager.
- The in-app Cite pane initializes from the application default.
- LibreOffice **Citation style…** now searches and presents the shared descriptive catalog, previews the choice,
  applies it, or opens the full manager. New Writer documents inherit the application default on first use;
  existing documents retain their embedded style/locale. Successful document choices enter Recent without
  replacing the application default.
- Extension version bumped 0.14.0 → 0.15.0.
- A stale native assertion from increment 364 was corrected to expect the current **Convert citation placement**
  command wording.

## Boundaries

This increment manages the styles already bundled with Callosum. Installing custom/additional CSL files, a visual
or source editor, and CSL import/export remain later P1 #9 work. Application defaults intentionally do not restyle
existing documents.

## Verification

- Focused API/frontend/LibreOffice suites: **193 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** against the installed 0.15.0 OXT, including
  catalog search, fixed-example preview, blank-document default inheritance without premature embedding, Recent
  recording, and the complete legacy Writer fixture.
- Playwright at `375x812` and `1440x900`: deep link, search, favorites, recents, IEEE preview/default, responsive
  layout, no horizontal overflow, and zero console/page errors.
- Full project suite: **1508 passed, 1 skipped**.

## Gates

- **Principles / governance:** non-triggering. This is deterministic local document formatting and preferences; it
  creates no claim, signal, ranking, recommendation, judgment, or egress.
- **Security:** `2026-07-24_citation-style-manager.md` is **PASS**.
- **QA:** routes 34 and 35 now cover catalog metadata/search, preview isolation, preference persistence, default
  semantics, validation, deep linking, and mobile layout.

## Experience pass

A deadline writer can search “psychology” or “MLA,” inspect a real formatted example, choose a locale, and apply
the style without learning a CSL id. Favorites and Recent make return trips quick. The interface explicitly says
that the application default is for new documents and preserves existing manuscript formatting. At the narrow
center-pane width seen in the live app, the locale/default action now wraps without squeezing its label. The
project no-delegation instruction prevented a persona subagent, so this walkthrough was performed locally against
the deadline-citer workflow.

## Manual verification debt

Install 0.15.0 and run **Callosum → Citation style…** in Writer: search, select, preview, and apply a style, then
use **Open full style manager**. Confirm the assembled native dialog labels and keyboard order; the modal
`dialog.execute()` path cannot be clicked by the headless UNO fixture.

## Next

Continue P1 #9 with local custom CSL installation and provenance/validation before considering either a visual
editor or source editor.
