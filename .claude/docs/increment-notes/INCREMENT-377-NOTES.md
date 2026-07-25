# Increment 377 - Writer categorized bibliographies

## Context

P1 bibliography item #11 could already control membership, heading, placement, rebuilding, and links, but every
visible entry still lived in one undivided list. The next competitor-parity slice is a safe document-wide
categorized bibliography before the structurally larger chapter/section bibliography work.

## Implemented

- The Writer file stores a bounded JSON map from numeric Callosum paper ids to validated category labels.
- **Citations in this document…** exposes **Set category…** for the selected cited or uncited work. Blank input
  removes an assignment; invalid input mutates nothing.
- Once any visible entry has a category, category headings sort alphabetically, citeproc's style-defined order
  stays stable within each group, and unassigned entries remain visible under **Other references**.
- Removing the final visible assignment restores the exact ordinary bibliography layout. Category headings stay
  inside the established managed bookmark pair.
- Existing bibliography entry targets and DOI/URL link offsets follow grouped entries. Assignments survive
  refresh and save/reopen; uncited/excluded membership remains independent.
- The extension version is `0.22.0`.

## Gates

- **Principles / governance:** non-triggering. Categories are explicit user-authored organization, not inferred
  scholarly claims, rankings, or recommendations.
- **Security:** `2026-07-25_writer-categorized-bibliographies.md` - **PASS**.
- **QA:** route 34 covers assignment/removal, ordering, uncategorized fallback, membership, links, refresh,
  movement, conversion, reopen, Undo, corrupt metadata, and bounds.
- **Experience:** a deadline-author walkthrough completed a three-category task from the document-citations
  panel. Its inclusive count now says **document work(s)** rather than incorrectly calling uncited further
  reading cited; custom ordering and batch assignment remain follow-ups.

## Manual verification

1. In Writer, create three bibliography entries and open **Callosum -> Citations in this document…**.
2. Select a work, choose **Set category…**, and enter `Methods`; assign another to `Theory`.
3. Confirm category headings and **Other references** appear without changing citation text or entry formatting.
4. Save/reopen and refresh; confirm categories and links remain coherent.
5. Submit a blank category for each assigned work and confirm the ordinary bibliography layout returns.

## Verification

- Focused LibreOffice/OXT/install tests: **138 passed**.
- Focused citation/LibreOffice/OXT/install/help suite: **210 passed**.
- Installed Writer focused spike: **SELFTEST OK**.
- Installed Writer full matrix: **SELFTEST OK**.
- Full project suite: **1577 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.

## Remaining item #11 scope

Chapter/section bibliographies (optionally alongside a full-document bibliography), custom category ordering and
batch assignment, bibliography-title links, and per-source navigation for grouped citations remain.
