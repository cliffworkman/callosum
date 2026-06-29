<!-- qa-coverage
api: GET /papers/fulltext
fe: 10c_fulltext.jsx
-->

# ROUTE 22 - Full-text PDF search

**Tier:** 1 local-stateful
**Goal:** Exercise verbatim full-text search over the extracted PDF chunk text (inc 209, A3) — the **"Full text"**
search scope → `GET /papers/fulltext` (FTS5 over `chunks.text`) → per-occurrence snippet hits that open the PDF at the
matching page. The exact-string complement to the semantic axes/synthesis — NOT a meaning search.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment); the seed includes papers with extracted chunk text. **Egress
UNSET.** Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** With egress unset, any request to a `generativelanguage`/Gemini/genai host is **Critical** (full-text
  search is entirely local — no model, no network).
- **Coordinate honesty.** A hit opens the PDF at **region** precision — scroll to the page, **no fabricated exact
  rect**. A full-text hit that draws an exact highlight (it has no token bbox) is **Critical**.
- **Verbatim, not semantic.** Results are literal matches over chunk text (FTS5), distinct from axes/synthesis. No
  claim/rank/score is computed or displayed (bm25 is an internal ordering only). A "relevance score" shown as a verdict
  is a bug.
- **Malformed input never 500s.** A query with FTS5 operator syntax (`"`, `*`, `NEAR(`, `^`, `a AND (b`) must return
  **200 + an empty/normal result**, never a 500 (the query is sanitized + bound; `_safe_match` quotes every token).

## Adversarial checklist

- paste ~50KB into the search box; submit whitespace-only
- `GET /papers/fulltext?q=` with `"`, `*`, `NEAR(`, `^`, empty, `a AND b OR (c` → 200, no 500
- `limit` out of range (0, 9999) → clamped / 422 per the Query bounds
- rapid scope toggling (All ↔ Full text) mid-type — no stale list / no orphan spinner
- resize to `375x812`, hard refresh - no horizontal overflow

## Steps

1. In the Library search bar, switch the scope dropdown to **Full text (PDFs)**. The placeholder becomes "search
   inside your PDFs…". Type a phrase known to appear in a seeded PDF's text.
2. The library list is replaced by the full-text results: a "searches inside your PDFs — exact wording, not meaning"
   hint, an "N matches in M papers" line, and per-occurrence cards. Each card shows the paper title + author·year, a
   snippet with the matched terms **bolded**, the page (`p. N`), and an **Open at page** button. (`GET /papers/fulltext?q=`)
3. Click **Open at page** on a hit → the PDF opens in a tab scrolled to that page (region precision — page scroll,
   no exact rectangle drawn).
4. Search a phrase that doesn't occur → "No matches in your PDFs." (empty state, not an error).
5. Type a malformed FTS5 query (e.g. a lone `"`); confirm a graceful empty result (HTTP 200), no console/page error,
   no 500. Directly: `GET /papers/fulltext?q="` → `200` `[]`.
6. Switch the scope back to **All fields** (or clear the query) → the normal paper list returns.

## Pass criteria

- Full-text scope → hit list → open-at-page completes through the UI.
- Hits are verbatim matches with snippet + page; opening is region precision (no fabricated exact rect).
- Malformed/empty queries return 200 (never 500); 0 console/page errors; 0 genai-host requests.
- No relevance score is presented as a verdict.
- Mobile viewport has no horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_22_fulltext.md` + `screenshots/` (see `_TEMPLATE.md`).
