# Increment 157 — Highlight-to-suggest, SP1b (the LibreOffice "Suggest citations" macro)

The second sub-project of #30: surface the inc-156 `POST /citations/suggest` contract **inside LibreOffice**,
where the writer is already inserting citations (the inc-108 cite-while-you-write adapter). Select (highlight) a
sentence → a new macro fetches library suggestions (stance + quote + match) → pick one → it's inserted as a live
citation via the existing inc-108 Insert→ReferenceMark flow. This is the inc-107→108 pattern: SP1a was the
contract, SP1b is the adapter that consumes it.

**Client-side only:** all in `adapters/libreoffice/callosum_cite.py` (the macro ships into the user's
LibreOffice). Talks only to 127.0.0.1, reuses the SP1a endpoint + the inc-108 insert. **No server change, no new
endpoint, no new egress, no migration, no new dependency** (stdlib `urllib`).

## Implemented (`adapters/libreoffice/callosum_cite.py`)

- **Pure helpers (UNO-free, pytest-able):**
  - `build_suggest_rows(suggestions)` — one pick-list row per suggestion: `[stance] Author Year · match N.NN —
    "quote…"` (stance label or "no stance"; author/year → title fallback; quote truncated to `SUGGEST_QUOTE_MAX`).
    The quote is the *reason* (the honesty surface). Parallel to `suggestions` (row index → paper_id).
  - `fetch_suggestions(base, text, top_k=5)` — `_post_json(.../citations/suggest, {text, top_k, evaluate:True})`,
    defensive on shape (→ `[]`). Uses `SUGGEST_TIMEOUT = 90s` (the first call loads the embed + NLI models
    server-side; render/export don't, so they keep the 20s default).
- **UNO layer:**
  - `current_query_text(doc)` — the **selection** if non-empty (highlight-to-suggest), else the **paragraph**
    around the caret (`gotoStartOfParagraph`/`gotoEndOfParagraph`).
  - `_insertion_cursor_at_end(doc)` — a collapsed cursor at the **end** of the selection (so the cite lands after
    the highlighted sentence; `view.getEnd()`).
  - `_suggest_listbox(doc, rows)` — a modal dialog (mirrors `_input_box`) with a `UnoControlListBoxModel` + a
    caveat label + Insert/Cancel; returns the selected index (`getSelectedItemPos`) or `None`.
  - `suggest_and_insert(doc, base)` — the orchestration: extract text → fetch → (msgbox if empty) → pick-list →
    `insert_citation(doc, suggestions[idx]["paper_id"], base, cursor=...)`.
- **Entry point** `CallosumSuggestCitations` (try/except → msgbox) added to `g_exportedScripts`.

## Key technical detail

- **Stance + suggestions are the backend's (inc 156)** — the macro only presents the evidence + inserts. The
  honesty contract is carried into the UNO UI: rows show stance + quote (the reason), the user **picks** (nothing
  auto-inserts), and inserting reuses citeproc (no formatting in the adapter).
- **`SUGGEST_TIMEOUT = 90s`** (vs the 20s render/export default): the first `/citations/suggest` call loads the
  embedding + NLI models server-side. A server-down case still fails fast (connection refused ≠ a 90s hang). The
  round-trip's first run hit the 20s wall before this — the fix.
- **UNO/Windows gotcha:** LibreOffice's bundled Python prints to a cp1252 stdout — a `→` in a `print()` raised
  `UnicodeEncodeError` and failed the selftest *after* the assertions passed. Keep selftest log/strings ASCII.

## Principles / security

- **Principles:** non-triggering beyond honoring the inc-156 posture (no new claim/signal; presentation + insert).
- **Audit:** an **addendum** to `.claude/security-audits/2026-06-21_libreoffice-adapter.md` (same local-only,
  plain-text, defensive, no-egress, no-new-dependency posture). The one new data flow — the **document text**
  (highlighted sentence / paragraph) POSTed to the **local** server — is the feature's purpose and stays on
  127.0.0.1 (no egress), analogous to the inc-108 macro sending CSL-JSON. **PASS.**
- **No QA route** (rule #10): a LibreOffice macro is outside the web-app surface map; `/citations/suggest` is
  already covered by `route_42_cite.md`. Surface map unchanged. **No help-corpus change** (the macro is not an
  in-app surface; the `adapters/libreoffice/README.md` is its doc).

## Manual verification

**Headless round-trip (`python .local/lo_roundtrip/run_roundtrip.py`) → SELFTEST OK.** The harness was extended:
`seed_db` now adds a chunk per paper + **embeds** them (real `all-MiniLM` + `SQLiteVecVectorStore`) so
`/citations/suggest` returns results; `selftest_uno.py` adds a section that calls `cc.fetch_suggestions(base,
"attention mechanism transformer architecture")` → asserts ≥1 suggestion incl. a seeded paper (got
`[(1, 'support'), (2, 'support')]` — both papers, **stance from the real NLI**), formats the rows, and inserts
the top one (`check` → 1 mark). This proves the suggest→insert chain end-to-end through **real LibreOffice** + a
real server with an embedded library. (Selftest subprocess timeout bumped 120→180s for the added ML work.)

**The interactive list-box dialog is the user's manual eyeball** (rule #11 experience pass) — it blocks on
`execute()`, so it can't be driven headlessly: copy the macro into `%APPDATA%\LibreOffice\4\user\Scripts\python\`,
start the server, select a sentence, run **Tools → Macros → CallosumSuggestCitations**, confirm the pick-list
shows stance + quote + match and the chosen cite inserts after the sentence. (Op note: a prior round-trip left a
zombie TCP listener on :8099 + a stale soffice; the harness now uses :8100/:2003 — re-point the ports if they're
held.)

## Pytest

**572** (+4 `test_libreoffice_adapter.py`: `build_suggest_rows` format + match-fallbacks; `fetch_suggestions`
posts-and-returns + defensive-on-bad-shape). `ruff format`/`check` clean. No `app/`/`integrations/` change → no
build_frontend, no surface-map change, no migration.

## Next

A formatted "Cite as… (style)" copy in the in-app Cite pane (the deadline-writer persona's ask; via the inc-106
render engine). Then SP2 — **beyond-library** discovery (OpenAlex `related_works` / co-citation + Semantic-Scholar
recommendations, each candidate carrying an explainable reason; trips the audit + Principles gates) + Stage-4
section-scoping. The Word (Office.js) + Google Docs adapters remain the broader word-processor track.
