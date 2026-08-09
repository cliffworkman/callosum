# Security Audit — Zotero citation conversion (inc 464, backlog #33/#34 P2 item #22)

**Date:** 2026-08-09
**Feature:** A new "Convert Zotero citations…" LibreOffice command that decodes Zotero-authored ReferenceMarks
(format verified against Zotero's own open-source `zotero-libreoffice-integration`) found in an open Writer
document and replaces them with live callosum citations — matching an existing library paper first, else
auto-adding a metadata-only paper straight from the citation's own embedded CSL-JSON.
**Triggers:** audit-gate #1 (new endpoint `POST /citations/zotero/resolve`), #3 (a new file-ingestion-*adjacent*
path — the untrusted content here is a Writer document's ReferenceMark *names*, not an uploaded file, but it's
the same trust boundary: content originating outside this app), #5 (net-new feature spanning 4+ files:
`app/backend/api/routers/zotero_citations.py`, `app/backend/importers/zotero.py`,
`adapters/libreoffice/callosum_cite.py`, `app/backend/api/app.py`).

## Scope

Read-only scan first (`zotero_conversion_scan`), an explicit confirm dialog naming exactly what will happen
(including everything left unconverted and why), then: one `POST /citations/zotero/resolve` call resolving every
distinct cited work to a `paper_id` (local DB match or create), followed by a per-mark remove-and-reinsert loop
using the existing `insert_citation_items` engine, and a bibliography-block swap using the existing `refresh()`
engine. **No LLM, no provider egress, no external metadata fetch** — every match/create is a local SQLite
read/write over data the citation itself already carries.

## Threat review

| Vector | Assessment |
|---|---|
| **Data egress** | **None.** `resolve_zotero_citations` touches only `request.app.state.engine` (local SQLite) — no `httpx`/`urllib`/provider SDK anywhere in `zotero_citations.py` or `normalize_zotero_csl_item`. Not the Gemini gate (invariant #3); not an external metadata lookup (unlike, e.g., citation-equity's OpenAlex calls). **To assert:** a grep of `app/backend/api/routers/zotero_citations.py` for `httpx\|requests\|urllib\|generativelanguage\|google-genai\|anthropic\|openai` returns no matches. |
| **Input validation** | The request body is untrusted twice over: it originates from a Writer document's ReferenceMark *name* (rule #4 — content pulled from an opened document, which could come from anywhere), decoded client-side by `_decode_zotero_mark_name` before ever reaching the network. That decoder is defensive exactly like `decode_mark_name`: non-string input, a missing/wrong prefix, a truncated random suffix, invalid JSON, or a missing/empty `citationItems` list all return `None` — **never raises**, confirmed by `test_decode_zotero_mark_name_parses_real_shape_rejects_foreign_and_malformed` including a non-string (`123`) argument. Server-side, `ZoteroResolveRequest.items` is Pydantic-validated (`item_data: dict[str, Any]`, `uris: list[str]`) and bounded `Field(min_length=1, max_length=MAX_ZOTERO_DISTINCT_WORKS=300)` — empty or over-cap input → **422** before any DB write. `normalize_zotero_csl_item` is itself defensive: a missing/malformed `issued`, `author`, `DOI`, `type`, `container-title`, or `language` field degrades to `None`/a safe default rather than raising (`test_normalize_zotero_csl_item_tolerates_missing_fields`, `test_normalize_zotero_csl_item_ignores_malformed_issued_and_non_matching_uri`). |
| **Output encoding** | The resolved `paper_id`/`created` flags are plain integers/booleans (Pydantic response model) — no HTML/script surface. In the adapter, the embedded `itemData` title/author/etc. only ever become a *new paper's stored metadata* (rendered later through the existing, already-audited citeproc pipeline — the same rendering path every library paper's title already goes through) — never interpolated into a shell command, file path, or raw SQL string. |
| **Injection (SQL)** | None — `find_existing_paper_by_identity`/`create_paper` are the same existing, already-audited SQLAlchemy Core bound-parameter helpers the Zotero *library* importer uses (rule #3); no new SQL construction in this increment. |
| **File-path safety** | Not engaged — no file is read or written by this endpoint (rule #4's file-path clause). The adapter's own `_zotero_bibliography_section` uses `doc.getTextSections()` (a live UNO document object query), not a filesystem path. |
| **SSRF** | None — no server-side fetch of a caller-supplied URL. The `uris` field is parsed *locally in the adapter* (never sent to any URL-fetching code; the backend only echoes it back into `csl_json` for storage) via a fixed regex (`ZOTERO_ITEM_URI_RE`) matched against known-shape `zotero.org/...` strings — a non-matching URI is silently ignored, never dereferenced. |
| **AuthZ / exposure** | `/citations/zotero/resolve` sits behind the existing `AccessControlMiddleware` bearer gate when Remote access is on (default-off → localhost only). It is **not** on the cloudflared cite-only ingress allowlist (`adapters/googledocs/cloudflared-config.yml`'s `path: ^/(papers\|papers/export\|citations/render-document\|citations/suggest\|citations/styles)$` — an exact-match regex, confirmed by grep to exclude `/citations/zotero/resolve`), so it is unreachable via the Google-Docs tunnel — correct: this is a desktop-authoring/LibreOffice-only surface, not a mobile-read or cross-editor path. On a `CALLOSUM_READ_ONLY=1` instance the mutating `POST` returns 403 (method gate) since it can create library rows. |
| **Resource exhaustion** | Bounded twice: `MAX_ZOTERO_DISTINCT_WORKS=300` caps the resolve request (server-enforced via Pydantic); `MAX_ZOTERO_CONVERT_MARKS=500` caps the adapter's per-occurrence replace loop client-side (each replacement triggers its own document re-render via `insert_citation_items`'s existing `_auto_refresh`, so this bound keeps worst-case refresh count sane on a very large document — truncation is disclosed in the confirm dialog, never silent). |
| **Supply chain** | **No new dependency.** `re`/`json` (stdlib) in both the backend normalizer and the adapter decoder; FastAPI/Pydantic and the adapter's existing `urllib`-based `_post_json` are already present. |

## Negative-path checks (concrete results — 2026-08-09)

- [x] `POST /citations/zotero/resolve` with **empty `items`** → **422** (`test_resolve_rejects_empty_and_over_cap_input`).
- [x] `POST /citations/zotero/resolve` with **`MAX_ZOTERO_DISTINCT_WORKS + 1` items** → **422** (same test).
- [x] `_decode_zotero_mark_name` on **non-string input**, **malformed JSON**, **the empty-`citationItems` foreign literal** (`"ZOTERO_ITEM CSL_CITATION {}"`, the exact string this codebase's own `test_decode_rejects_foreign_and_malformed` uses for "another tool's mark"), and **a Callosum-prefixed name** all return `None` (`test_decode_zotero_mark_name_parses_real_shape_rejects_foreign_and_malformed`).
- [x] `normalize_zotero_csl_item` on **`{}`** (every field missing) produces a safe, non-raising canonical dict (`test_normalize_zotero_csl_item_tolerates_missing_fields`).
- [x] `normalize_zotero_csl_item` on a **malformed `issued` shape** (a string instead of the `date-parts` list) and a **non-Zotero URI** both degrade to `None` rather than raising or misparsing (`test_normalize_zotero_csl_item_ignores_malformed_issued_and_non_matching_uri`).
- [x] A resolve item referencing a **paper id no longer resolvable / no match anywhere** → a new metadata-only paper is created, never a 500 (`test_resolve_creates_metadata_only_paper_when_no_match`).
- [x] The adapter's `convert_zotero_citations_interactive` **never calls the backend when the user declines the confirm dialog** (`test_convert_zotero_citations_interactive_cancel_on_declined_confirm`) and **never mutates a mark it couldn't resolve** (`test_convert_zotero_citations_interactive_skips_unresolved_item_without_inserting`).
- [x] **Zero egress surface.** A grep of `app/backend/api/routers/zotero_citations.py` and `app/backend/importers/zotero.py` for `httpx|requests|urllib|google|openai|anthropic|generativelanguage` returns no matches.
- [x] `pytest tests/test_zotero_citations.py tests/test_libreoffice_adapter.py tests/test_zotero_importer.py -q` → **196 passed** (2026-08-09).
- [x] Real-UNO (`adapters/libreoffice/run_roundtrip.py`, `spike_zotero_citation_conversion`): a hand-built malformed Zotero mark and a Bookmark-mode anchor coexist with two valid marks in the same real document — the scan/conversion completes without crashing, correctly isolating and reporting the malformed/unsupported ones rather than aborting the whole run.

## Principles posture (rule #9)

This is a **faithful format migration**, not a claim/signal/judgment about the literature — the closest worked
precedent is the existing Zotero *library* importer (`import_zotero_library`), whose exact trust posture is
reused verbatim: `imported_source="zotero"`, `processing_tier="metadata-only"` for anything auto-added from
self-asserted Zotero metadata, no verification claim attached. The fact-vs-candidate line stays intact: a
matched paper's existing record is never overwritten by the (potentially staler) embedded citation data — only
its `paper_id` is reused. Coverage stays honest (#6): note-style and Bookmark-mode Zotero citations are counted
and named in both the confirm dialog and the final summary as **left unconverted**, never silently dropped or
guessed at — the misaligned easy path here would have been reverse-engineering the undocumented Bookmark-mode
storage format from inference rather than declaring it an unverified boundary, which Cliff's own explicit
"research first" direction for this increment was designed to prevent.

## Verdict

Every negative path fails closed (422 at the Pydantic boundary; `None` from every decode/normalize function on
malformed input, never a raise) and is covered by an executed test. The endpoint has no network code path at all
(statically confirmed by grep) and is unreachable via the cite-only tunnel allowlist (confirmed against the real
`cloudflared-config.yml` regex). Bound parameters throughout (rule #3, unchanged from the existing
`find_existing_paper_by_identity`/`create_paper` helpers); no new file-write path; no SSRF; no new dependency;
both size bounds (300 distinct works server-side, 500 marks client-side) are enforced and their truncation is
disclosed to the user rather than silent.

**Security Audit: PASS.**
