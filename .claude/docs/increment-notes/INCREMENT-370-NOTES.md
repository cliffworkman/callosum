# Increment 370 - Revision-safe CSL source editor

## Implemented

- Independent personal styles expose **Edit source** in Settings. Bundled and dependent styles expose
  **Duplicate to edit**, which creates and opens a standalone personal copy.
- The two-pane editor keeps the complete CSL XML visible beside a draft citation and bibliography preview rendered
  from the same fixed fictional records as the style manager.
- **Validate & preview** runs full candidate validation and citeproc without writing. **Save** repeats those checks,
  preserves the local and canonical style ids, writes atomically, and records a local-edit timestamp.
- Each editor load returns a SHA-256 revision. Save requires that exact revision and returns 409 if the source
  changed. It checks before validation and immediately before replacement, preventing a stale editor or a change
  that lands during validation from silently overwriting newer work.

## Boundaries

This is deliberately a complete source editor, not a partial visual-CSL builder that would imply support for only
some of CSL. Only independent personal styles are editable. The source and preview remain local; no library,
PDF, manuscript, credential, LLM, or external network data enters the flow. Existing documents continue to refer
to the same stable style identity after an edit.

## Gates

- **Principles:** principle 8 is strengthened because the exact formatting program and its rendered consequence
  are visible together. Principle 10 applies because validation and preview are deterministic and local. The
  aligned path is reviewable source -> local preview -> explicit save; the declined shortcut is silently changing
  a bundled/dependent style or overwriting a newer revision.
- **Design/experience:** the existing manager remains the entry point. A deadline citer can duplicate an unfamiliar
  journal style, see the copy become selected, validate a draft, and save without leaving Settings. Desktop uses
  a source/preview split; mobile stacks both surfaces without hiding controls.
- **Security:** `2026-07-24_csl-source-editor.md` - **PASS**.
- **QA:** routes 34 and 35 cover API identity/concurrency and the complete Settings interaction.

## Verification

- Editor source/race/boundary tests: **2 passed**.
- Frontend assembly and served help: **63 passed**.
- Playwright desktop: bundled **Duplicate to edit** opened the copy directly; a 69 KB APA source received a
  666px editor pane, rendered an unsaved bracketed citation, saved under the same ids, and showed its edit date.
- Playwright mobile (`375x812`): one-column source/preview stack, dirty-close cancel/discard, persistent saved
  source, zero page/modal overflow, and zero current-page console errors. This pass found and fixed the shared
  modal's 540px cascade overriding the intended desktop work-surface width.
- QA surface map: **309/309 API**; all new frontend controls claimed (the 21 reported gaps remain the pre-existing
  tag/My Publications checklist entries). Ruff, frontend build, line budget, `git diff --check`, and offline lock
  verification are clean.
- Real LibreOffice Writer exercised the shared style catalog and render-document calls through phase 6, then hit
  the same existing harness timeout ceiling recorded in increment 369 while entering merge/split; the timeout
  disposed the UNO bridge, and the informational CI job will retry once.
- Full project suite: **1550 passed, 1 skipped** in 13:31.

## Result

P1 roadmap item #9, the real citation-style manager, is complete.
