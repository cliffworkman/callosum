# Security audit — Word bibliography title/DOI links

**Date:** 2026-08-28
**Increment:** 525
**Scope:** document-local opt-in external hyperlinks inside Callosum-managed full and heading-scoped Word
bibliographies.

## Boundary and threat review

- **Input validation:** the shared citation renderer remains the source of aligned entry-local spans, but Word
  does not trust that metadata blindly. The adapter requires exact entry/link-list alignment, at most 20 spans
  per entry, integer non-overlapping positive code-point ranges inside the exact entry, and a bounded URL of at
  most 2,048 characters. Python Unicode-code-point positions are converted explicitly rather than interpreted as
  JavaScript UTF-16 offsets.
- **URL / SSRF / egress:** only `http:` and `https:` destinations with a hostname and without embedded username
  or password are accepted. Whitespace, control characters, `javascript:`, `file:`, `data:`, `mailto:`, malformed,
  or credentialed URLs remain plain. Callosum does not fetch or preflight the destination. Enabling the option
  writes a normal Word hyperlink; egress occurs only if the author deliberately follows it through Word. The
  task pane's same-origin API behavior and Remote-access tunnel allowlist do not change.
- **Output encoding / injection:** visible bibliography text continues to come from the existing plain-text
  citeproc contract and is inserted with `insertText`, never HTML. WordApi `Range.hyperlink` receives only the
  validated destination after the generated paragraph text and anchor each resolve exactly once. Missing,
  shifted, duplicated, or ambiguous matches are skipped instead of guessed.
- **Secrets and private content:** the persisted setting is only the string `"1"`; it contains no URL, title,
  paper metadata, credential, token, or path. No new logs, receipts, requests, provider calls, or secret reads
  exist. The Word-on-the-web bearer token remains confined to the existing fetch wrapper and never enters a
  hyperlink or document setting.
- **Resource bounds:** renderer request bounds are unchanged. Word processes at most 20 candidate links per
  bibliography entry and existing bibliography/section-block caps still apply. Link work occurs only during an
  explicit refresh/setting change, never through polling or background observation.
- **File/path safety and supply chain:** no file read/write path, dependency, executable, download, or package
  change is introduced.
- **Failure / rollback:** malformed additive link metadata degrades to plain text. A setting-change refresh
  failure restores the exact prior document setting. Replacing the bounded managed Content Controls removes only
  their links; hyperlinks outside those controls are never enumerated or mutated.

## Negative checks

The Node pure suite covers non-HTTP(S), credentialed, whitespace-bearing, malformed, out-of-range, overlapping,
misaligned, excessive, and astral-Unicode-offset inputs. Static wiring checks require paragraph-local search,
exactly one result, setting rollback, and metadata cleanup. The existing Python Word asset test asserts the task
pane contains no AI/provider/library host; the citation renderer tests already cover unsafe title/DOI/URL span
fallback. Exact commands/results are recorded in `INCREMENT-525-NOTES.md`.

Real Word hyperlink navigation cannot be driven by the available automation. Desktop Word and Word-on-the-web
manual checks remain explicitly owed in the consolidated arc verification checklist.

## Result

**Security Audit: PASS**
