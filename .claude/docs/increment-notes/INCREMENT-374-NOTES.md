# Increment 374 - Per-document Writer bibliography heading

## Context

P1 bibliography editing item #11 already supported uncited inclusions, cited-work exclusions, explicit
bibliography-only refresh, and paused automatic rebuilding. The heading remained a global `References` constant,
so venue-specific labels required a manual edit that the next refresh overwrote.

## Implemented

- **Bibliography heading…** is packaged beside the existing Writer bibliography commands.
- The value is a removable document user property: printable, single-line, trimmed, and capped at 120 characters.
  Blank input removes the property and restores `References`.
- Every managed bibliography render/currentness comparison uses the effective document heading. The heading is
  inserted as plain text inside the existing start/end bookmark pair.
- The command explicitly refreshes only the bibliography, even when automatic bibliography rebuilding is paused,
  without changing that mode. Reapplying the saved heading also repairs a stale/manually edited managed block.
  A render or Writer failure restores the previous property.
- The extension version is `0.19.0`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic document formatting and creates no claim,
  signal, recommendation, ranking, or egress channel.
- **Security:** `2026-07-24_writer-bibliography-heading.md` - **PASS**. Bounded plain-text input, no path/markup
  interpretation, established transactional Writer mutation, and no dependency or endpoint.
- **QA:** route 34 covers paused-mode application, preserved citations/entries/trailing prose, save/reopen,
  blank reset, and invalid-input no-mutation.
- **Experience:** a deadline-writer walkthrough found the path direct and specifically useful with automatic
  rebuilding paused. It identified two non-blocking follow-ups: expose the toggle's current state and consider an
  explicit **Restore References** affordance. Both are recorded in the backlog.

## Manual verification

1. In Writer, insert a citation and pause automatic bibliography rebuilding.
2. Choose **Callosum -> Bibliography heading…**, enter `Works Cited`, and confirm the bounded heading changes
   immediately while citations, bibliography entries, trailing prose, and paused mode remain unchanged.
3. Save and reopen the ODT; confirm `Works Cited` remains.
4. Reopen the command, clear the field, and confirm `References` returns without enabling automatic rebuilding.

## Verification

- LibreOffice adapter/OXT: **121 passed**; adapter/OXT/install focused run: **125 passed**.
- Help: **14 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: first launch stopped before self-test when the isolated UNO port
  did not open; exact clean retry completed **SELFTEST OK** against installed OXT `0.19.0`.
- Full project suite: **1566 passed, 1 skipped**.

## Remaining item #11 scope

Categorized bibliographies, chapter/section bibliographies (optionally alongside a full-document bibliography),
and citation/entry/title/DOI hyperlink controls remain.
