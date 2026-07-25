# Increment 376 - Writer bibliography DOI/URL links

## Context

Increment 375 added document-local navigation from citations to bibliography entries. P1 bibliography item #11
also called for optional external links on identifiers already printed by the bibliography style. Writer still
rendered those DOI/URL strings as plain text.

## Implemented

- The local citeproc sidecar enables its dormant DOI/URL wrapper extension. `/citations/render-document` adds
  aligned `bibliography_links` spans while retaining `bibliography_text`, `bibliography_html`, and
  `bibliography_entry_ids` unchanged.
- Link metadata is capped and mapped to the normalized plain bibliography text. Only bounded, non-overlapping
  HTTP(S) URLs with a hostname and no embedded credentials are accepted.
- **Toggle bibliography DOI/URL links** is an opt-in Writer-document setting. Writer inserts the exact citeproc
  text first, then formats only validated declared ranges inside the bounded managed bibliography.
- The setting survives refresh, save/reopen, bibliography moves, and citation placement conversion. Disabling
  rebuilds the same text without managed external links and leaves hyperlinks outside the bibliography alone.
- The extension version is `0.21.0`.

## Gates

- **Principles / governance:** non-triggering. This exposes source destinations already selected and printed by
  the active CSL style; it creates no scholarly claim, signal, recommendation, ranking, or network request.
- **Security:** `2026-07-24_writer-bibliography-external-links.md` - **PASS**.
- **QA:** route 34 covers exact-text preservation, unsafe/plain fallback, toggle, reopen, bibliography movement,
  placement conversion, and unrelated hyperlink preservation.
- **Experience:** a deadline-author walkthrough found the menu path direct but an unchanged bibliography
  ambiguous when the active style prints no DOI/URL. The confirmation now reports the applied link count and
  explains a zero-result style; checked ON/OFF state and title-level links are recorded as follow-ups.

## Manual verification

1. In Writer, select a style that prints DOI/URL text and create a bibliography.
2. Choose **Callosum -> Toggle bibliography DOI/URL links** and use Writer's standard follow-link action on the
   printed identifier. Confirm no new text appeared.
3. Save/reopen, refresh, move the bibliography, and convert citation placement; confirm the link persists.
4. Toggle off and confirm the bibliography text is unchanged and a separate manual hyperlink remains linked.

## Verification

- Focused citation/LibreOffice/OXT/install/help tests: **206 passed**.
- Installed Writer focused spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1573 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.

## Remaining item #11 scope

Categorized bibliographies, chapter/section bibliographies (optionally alongside a full-document bibliography),
bibliography-title links, and per-source navigation for grouped citations remain.
