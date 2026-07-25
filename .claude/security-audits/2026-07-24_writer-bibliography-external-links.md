# Security audit - Writer bibliography DOI/URL links

**Date:** 2026-07-24
**Increment:** 376
**Result:** PASS

## Scope

- Additive bibliography link-span metadata from the local citeproc sidecar and render contract.
- Opt-in document-local Writer preference and bounded bibliography hyperlink formatting.
- Menu/OXT packaging, pure tests, installed-Writer proof, and documentation.

## Findings

- **No automatic egress or fetch.** citeproc derives links from the existing local CSL record, and Callosum
  neither resolves nor requests any destination. A network visit happens only if the user explicitly invokes
  Writer's standard follow-link action.
- **Schemes and authority fail closed.** Only `http` and `https` URLs with a hostname are accepted. Embedded
  usernames/passwords, whitespace/control characters, malformed authorities, non-web schemes, and values over
  2048 characters remain plain text.
- **Metadata is bounded and aligned.** At most 20 non-overlapping spans are accepted per entry; negative,
  zero-length, overlapping, out-of-range, or misaligned-entry metadata is discarded. Missing metadata degrades
  to the unchanged plain bibliography.
- **Markup is not injected.** The existing `bibliography_html` sanitizer still strips anchors and allows only
  its established presentation tags. The new response exposes integer text offsets plus validated URL strings;
  Writer first inserts the exact plain entry and formats only the selected existing range.
- **Document mutation stays bounded.** Hyperlinks are applied relative to the managed bibliography start
  bookmark and never select beyond its rendered entries. Rebuilding with the setting off removes only formatting
  inside that bounded block; citation links, manual prose links, and trailing content are untouched.
- **State changes roll back.** If render or Writer formatting fails, the existing UndoManager transaction
  restores the bibliography and the document preference returns to its prior value.
- **No secret, file, dependency, or subprocess expansion.** URLs never become file paths or subprocess
  arguments; no token or credential is read; citeproc-js is the existing locked dependency and its dormant
  wrapper extension is enabled only on the local engine instance.
- **Backward compatibility is additive.** `bibliography_text`, sanitized `bibliography_html`, and
  `bibliography_entry_ids` are unchanged. Older adapters ignore `bibliography_links`.

## Verification

- Unsafe/credentialed/out-of-range span tests and aligned DOI-link render tests pass.
- Focused citation/LibreOffice/OXT/install/help suite: **206 passed**.
- Installed Writer focused spike and full matrix: **SELFTEST OK**, including toggle, save/reopen, movement,
  placement conversion, exact text, and unrelated manual-link preservation.
- Full project suite: **1573 passed, 1 skipped**.
- Ruff check/format, line budget, QA surface map, OXT packaging, and diff hygiene: **PASS**.
