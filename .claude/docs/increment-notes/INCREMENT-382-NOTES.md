# Increment 382 - Writer bibliography title links

## Context

Increment 376 made DOI/URL text already printed by a CSL style clickable. Styles that intentionally omitted the
identifier still produced no useful external link, even when the source record had a DOI or URL and its title was
visible in the bibliography. This was the final open bibliography-title-link slice of P1 item #11.

## Implemented

- `/citations/render-document` keeps citeproc's validated visible DOI/URL anchors as the primary
  `bibliography_links` metadata. Only when an entry has no such span does it consider a title fallback.
- A fallback requires one citeproc entry id, the corresponding request item, a bounded safe DOI or URL, and one
  uniquely matched normalized title in the exact rendered entry. DOI is preferred and canonicalized to an HTTPS
  `doi.org` URL; the existing HTTP(S)-only URL validator remains the fallback.
- Exact matches are preferred. ASCII-only case differences support styles that change title case without
  changing characters; ambiguous, shortened/transformed, oversized, multi-source, or unsafe cases stay plain.
- The response's bibliography text, sanitized HTML, entry-id alignment, and field name are unchanged. Writer's
  existing bounded span path therefore applies the links to full, categorized, and section bibliographies and
  retains them through refresh, movement, placement conversion, and save/reopen.
- The existing document preference remains compatible. Its menu/help wording is now **Toggle bibliography
  title/DOI links**, and the extension version is `0.27.0`.

## Gates

- **Principles / governance:** non-triggering. This is deterministic source navigation and produces no claim,
  signal, recommendation, ranking, or egress.
- **Security:** `2026-07-25_writer-bibliography-title-links.md` - **PASS**.
- **QA:** route 34 step 17 covers visible-identifier precedence, Nature-style title fallback, exact-text
  preservation, persistence/conversion, unrelated hyperlink preservation, and fail-plain negative paths.
- **Experience:** a code/help-grounded deadline-author walkthrough found the renamed command discoverable and the
  count/zero-result confirmation sufficient. It adds no text and needs no extra choice. A persona subagent was not
  used because delegation was disabled; the existing checked-state follow-up remains.

## Manual verification

1. In Writer, insert two cited works with DOI metadata and build an APA bibliography.
2. Choose **Callosum -> Toggle bibliography title/DOI links**. Confirm the already-rendered DOI text becomes
   clickable and no text changes.
3. Switch to Nature with complete journal metadata so the style omits DOI text. Confirm each rendered title now
   links to its source DOI, while the DOI itself does not appear.
4. Save/reopen, refresh, move or categorize the bibliography, insert a section bibliography, and convert citation
   placement. Confirm the links remain coherent.
5. Toggle off. Confirm managed bibliography links disappear, text is unchanged, and a manual hyperlink in prose
   remains linked.

## Verification

- Focused backend/LibreOffice/OXT/install/help tests: **213 passed**.
- Installed Writer focused bibliography-link spike: **SELFTEST OK** (exit 0; 123.1 seconds).
- Installed Writer full matrix: **SELFTEST OK** (exit 0; 495.4 seconds).
- Full project suite: **1584 passed, 1 skipped** (692.97 seconds).
- Ruff check/format: **pass**.
- Line budget: **pass** (386 app-source files).
- QA surface map: **pass** (309/309 gated API; 1370/1391 frontend with 21 existing report-only findings).
- OXT packaging: **pass** (72,992 bytes).
- Diff hygiene: **pass**.

## Remaining item #11 scope

Per-source navigation for grouped citations and long-manuscript section-bibliography list/jump/remove-all polish
remain.
