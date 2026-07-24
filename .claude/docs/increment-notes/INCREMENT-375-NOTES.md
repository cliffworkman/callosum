# Increment 375 - Writer citation-to-bibliography links

## Context

P1 bibliography editing item #11 could control membership, rebuilding, placement, and the heading, but an
in-text citation could not navigate to its rendered bibliography entry. citeproc already returned the required
ordered entry identities internally; Callosum discarded them.

## Implemented

- `/citations/render-document` adds an aligned `bibliography_entry_ids` field while retaining the existing
  `bibliography_text` and `bibliography_html` contract unchanged.
- Writer creates stable `CALLOSUM_BIB_ENTRY_<paper-id>` bookmarks inside the bounded managed bibliography.
- **Toggle citation-to-bibliography links** is an opt-in document setting. A citation links only when it contains
  exactly one work with a rendered entry. Grouped and excluded citations remain plain.
- Toggle state, targets, and links survive refresh, citation placement conversion, save, and reopen. Disabling
  removes only Callosum's internal links; unrelated external links are preserved.
- Link changes participate in the existing UndoManager transaction and its rollback oracle now checks both
  visible citation text and the managed URL.
- The extension version is `0.20.0`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic, local document navigation and creates no
  scholarly claim, signal, recommendation, ranking, or egress channel.
- **Security:** `2026-07-24_writer-bibliography-links.md` - **PASS**.
- **QA:** route 34 covers single/grouped/excluded behavior, external-link preservation, toggle, reopen, refresh,
  and placement conversion.
- **Experience:** the deadline-writer path is useful and direct. Help now names Writer's follow-link action and
  external-link preservation; the OFF confirmation does the same. Visible toggle state and a future grouped-
  citation source chooser are recorded as non-blocking backlog follow-ups.

## Manual verification

1. In Writer, create two single-work citations and one grouped citation, then choose **Callosum -> Toggle
   citation-to-bibliography links**.
2. Use Writer's follow-link action on each single-work citation and confirm it reaches that work's bibliography
   entry. Confirm the grouped citation remains plain.
3. Save/reopen and refresh; confirm links and targets persist. Toggle off and confirm a separate external
   hyperlink is unchanged.

## Verification

- Focused citation/LibreOffice/OXT/install/help tests: **197 passed**.
- Installed Writer focused spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1568 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.

## Remaining item #11 scope

Categorized bibliographies, chapter/section bibliographies (optionally alongside a full-document bibliography),
title/DOI links, and per-source navigation for grouped citations remain.
