# Security audit — full-text PDF search (inc 209, A3)

**Trigger:** a new API endpoint + a new query surface (`GET /papers/fulltext` runs a SQLite **FTS5 MATCH** over the
extracted PDF chunk text). Audit-gate rule #1 (new endpoint) + the rule-#10 "new query surface — validate input".

**Change under review:** migration `0026_chunks_fts` (an external-content FTS5 index `chunks_fts` over `chunks.text`
+ a sync trigger trio); `persistence/fulltext_repo.py` (`_safe_match` + `search_chunks_fulltext`);
`routers/fulltext.py` (`GET /papers/fulltext`); a frontend "Full text" search scope + `10c_fulltext.jsx`.

## Threat review

- **Input validation / query-language injection (the core risk).** The raw user query is **never** placed into SQL
  text. It is (a) **sanitized** by `_safe_match`: split on whitespace, drop tokens with no alphanumeric char, wrap each
  remaining token as a double-quoted FTS5 phrase (embedded `"` → `""`), AND-ed by juxtaposition. Quoting neutralizes
  **every** FTS5 operator (`*` `:` `-` `^` `(` `)` `NEAR` `AND` `OR` `"`) so the query can be neither an FTS5 *syntax
  error* nor an injection of the FTS5 query language; and (b) passed as a **bound parameter** (`:q`) to a parameterized
  `sqlalchemy.text` statement (rule #3 — no interpolation; table/column names are constants). A no-usable-token query
  returns `[]` without touching the DB. **Defense in depth:** the execute is wrapped in `try/except OperationalError →
  []`, so even a hypothetical sanitizer gap can never surface a 500.
- **Output encoding / XSS.** The snippet returned by FTS5 `snippet()` wraps matched terms in two private-use markers
  (U+E000/U+E001). The frontend (`10c_fulltext.jsx::renderFtSnippet`) **splits on the markers and rebuilds React
  nodes** (plain text segments + `<b>`); **no `dangerouslySetInnerHTML`** — React escapes the (user-PDF-derived) text.
  No HTML/script in chunk text can execute.
- **SSRF / external calls / egress.** None. The feature is entirely local (a SQLite query); no network, no model, no
  external fetch. The headed run confirmed **0 genai-host requests**. This is NOT the Gemini egress gate's concern.
- **Secret handling.** None involved.
- **Resource caps.** `limit` is bounded by FastAPI `Query(ge=1, le=FULLTEXT_MAX_RESULTS=50)` and re-clamped in the
  repo (`max(1, min(limit, 50))`); FTS5 `MATCH ... LIMIT` is index-backed (no full scan). Per-occurrence hits are
  capped at 50.
- **File-path safety.** None (no path is built from input).
- **Trashed-paper leakage.** The query JOINs `papers ... AND p.deleted_at IS NULL`, so soft-deleted papers' chunks are
  excluded (the retrieval/pipeline convention) — verified by `test_fulltext_search_and_trashed_exclusion`.
- **Index sync / data integrity.** `chunks_fts` is external-content (no text duplication) kept in sync by triggers on
  `chunks`. The **AFTER DELETE** trigger is the critical one: chunk deletion happens via FK CASCADE on `purge_paper`
  (inc 65), which bypasses the Python layer — the trigger fires on the CASCADE, so a purged paper's text leaves the
  index. Verified by `test_fts_trigger_syncs_on_insert_and_cascade_delete`.
- **Supply chain.** **No new dependency** — FTS5 is built into the project's SQLite (the same connection that already
  loads sqlite-vec / runs `MATCH`); the migration is the source of truth (`metadata.create_all` can't express FTS5).

## Negative-path checks (run)

- Malformed FTS5 queries `"`, `*`, `NEAR(`, `^`, `a AND b OR (c`, empty, whitespace → **HTTP 200, `[]`**, never a 500
  (`test_fulltext_malformed_and_empty_never_500`; headed-confirmed for `"`).
- `limit` out of `[1,50]` → 422 (FastAPI Query bounds).
- Trashed paper → excluded from results (test above).
- Egress unset → 0 genai-host requests during the full-text flow (headed driver).

## Principles

Non-triggering: verbatim lexical lookup — it computes **no claim, rank, or score**; `bm25()` is an internal result
*ordering* only, never displayed as a verdict. The exact-string complement to the semantic axes/synthesis. Coordinate
honesty preserved (a hit opens at **region** precision — page scroll, no fabricated exact rect).

## Verdict

**Security Audit: PASS.** Input sanitized + bound + fail-closed; output escaped (no XSS); local-only (no egress/SSRF);
bounded; trashed-excluded; trigger-synced (incl. the CASCADE path); no new dependency.
