# Increment 174 — confirm before 🔎 re-resolve overwrites hand-edited metadata (backlog #3)

A librarian-pass finding from backlog **#3**: 🔎 re-resolve passes `force=True` (inc 49), which **silently
overwrites** a paper's metadata from Crossref — including papers the user has hand-edited (`imported_source ==
"user-edited"`, the inc-49 stamp that otherwise protects them from *batch* enrich). One misclick = lost edits.

## Implemented
- **`app/frontend/js/25_detail.jsx`** — `DoiRow.resolve()` now guards: if `paper.imported_source === "user-edited"`,
  a `window.confirm` ("This paper has hand-edited metadata. Re-resolving from Crossref will overwrite your edits.
  Continue?") must be accepted before it commits the DOI + re-resolves. Matches the established `window.confirm`
  convention (used for every consequential action — delete, trash, import-all, etc.). Non-user-edited papers are
  unaffected (no prompt).

## Gates
- Frontend-only; no backend/endpoint/migration/egress; reuses the existing `imported_source` already on the detail
  response + the `re-resolve` endpoint → no audit/Principles trigger. 25_detail.jsx 579 → **584** (under the 600 cap).
- **QA (rule #10):** no new surface (a confirm on an existing control) → 121/121 API + 608/608 FE, 0 uncovered.
- Frontend rebuilt; `test_frontend_assembly` 5/5; pytest **619** unchanged (frontend-only).

## Verification
By the convention (10 other `window.confirm` guards) + build/assembly/surface gates. The dialog's in-browser
appearance is a light manual check (matches the proven pattern). The remaining #3 items —
**always-on tag-source label** (reverses the inc-100 "differentiate aesthetically, no labels" decision → needs
Cliff) and a **diff toast** / **lock-this-tag** (design) — are left for a decision.
