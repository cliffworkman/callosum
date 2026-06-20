# Security Audit — Citation export (BibTeX / RIS / CSL-JSON) (increment 70)

**Date:** 2026-06-20
**Trigger:** New API endpoint `POST /papers/export` + a net-new feature (formatter module + repo helper +
frontend). No new schema/migration.

## What changed
A way to get citations **out** of the library: `POST /papers/export {paper_ids, format}` renders the selected
LIVE papers' stored `csl_json` as **BibTeX / RIS / CSL-JSON** and returns it as a downloadable file. The
frontend offers a bulk file download (library bulk bar) and a per-paper clipboard copy (Details pane).

## Threat review
- **Read-only, local, no egress.** The endpoint reads the user's own stored metadata and formats it in
  memory — it makes **no external call** and **writes no file on the server** (the response body is text;
  the browser saves the download client-side). Nothing leaves the machine.
- **SQL injection (rule #3):** `get_papers_for_export` is a bound-param `select(papers).where(id.in_(ids),
  deleted_at IS NULL)` — no string interpolation. `paper_ids` is a Pydantic `list[int]`.
- **Input validation (rule #4):** `format` is a Pydantic `Literal["bibtex","ris","csl-json"]` — any other
  value is a 422 before the handler runs (and `render_citations` also raises `ValueError` on an unknown
  format as defense-in-depth). `paper_ids` requires `min_length 1`; the handler 422s if no **existing live**
  papers resolve (trashed/deleted/nonexistent ids contribute nothing). Live papers only — never exports
  trashed records.
- **Output-format injection:** the formatters **escape** their output so a paper's own text can't break the
  structure — BibTeX escapes `& % $ # _ { }` and the entry key is sanitised to `[A-Za-z0-9]`; RIS is a flat
  tag format (newlines in abstracts are flattened); CSL-JSON is `json.dumps` (inherently escaped). Worst case
  a malformed field yields a slightly-off citation, never code execution or a broken document boundary.
- **File-path safety:** the `Content-Disposition` filename is a **constant** (`callosum-citations.<ext>`,
  ext from a fixed map) — no request data in the path/filename.
- **Resource:** bounded by the selected id count; each paper renders a handful of lines/fields. No fan-out,
  no recursion.
- **API surface:** one new POST route, added to the route-surface invariant allowlist (`tests/test_health.py`).
  `/papers/export` (2-segment, POST) does not collide with any existing route (no `POST /papers/{paper_id}`).
  CORS unchanged (GET-only for cross-origin; this is a same-origin POST from the app). **Clipboard:**
  `navigator.clipboard` requires a secure context — satisfied on `127.0.0.1`.
- **Migration / deps:** none (pure DML read + stdlib formatting; reuses `abstract_plain_text`).

## Negative-path checks (results)
- `format` not in the allowlist → **422** (`test_export_citations_each_format_and_validation`,
  `test_render_citations_dispatch_and_bad_format`). **PASS.**
- `paper_ids` empty → **422**; all-nonexistent → **422**; all-trashed → **422** (same test). **PASS.**
- A trashed paper in a mixed selection is **excluded** from the output (same test). **PASS.**
- BibTeX special chars (`&`) escaped; title case-preserved (`{{…}}`); deduped keys; JATS stripped from the
  abstract (`test_bibtex_*`). **PASS.**
- **Live E2E** (`.local/citation_export_e2e/`): bulk `.bib` download contains both entries; per-paper BibTeX
  copied to the clipboard; **0 console errors**. **PASS.**

Full suite: **244 passed** (+8). No new dependency; no migration; no egress.

**Security Audit: PASS.**
