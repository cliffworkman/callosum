# Increment 108 — LibreOffice (UNO) citation adapter, v1: the live-field loop

## Implemented
The first **word-processor adapter** — cite-while-you-write in LibreOffice Writer, riding the inc-107
`POST /citations/render-document` contract. The adapter is a thin **field-placer**: it never formats citations
(the backend citeproc engine does), it only places live fields, reads the full ordered set, and writes back the
rendered in-text + bibliography. New top-level **`adapters/`** tree (client code that ships into the user's
LibreOffice — not the FastAPI app, not a server-side `integrations/` client).

- **`adapters/libreoffice/callosum_cite.py`** — the drop-in UNO macro. Four entry points (Tools → Macros):
  - **CallosumInsertCitation** — paper id → `POST /papers/export {format:"csl-json"}` → stamp `id="callosum-<n>"`
    → insert a `CALLOSUM_CITATION` **ReferenceMark** (name = base64 CSL-JSON payload, Zotero `CSL_CITATION`
    pattern) → refresh.
  - **CallosumRefresh** — full-document scan of our ReferenceMarks **in document order** (`XTextRangeCompare`) →
    `POST /citations/render-document {style, locale}` → write each cluster's plain text back into its mark →
    rebuild the bibliography block.
  - **CallosumSetStyle** — validate against `GET /citations/styles`, persist `{style, locale}` as document
    user-properties, refresh.
  - **CallosumFlatten** — unlink live fields → static text (for submission). One-way.
  - UNO-free helpers (unit-tested): `encode/decode_mark_name`, `stamp_item_id`, `build_render_request`,
    `order_by_comparator`; stdlib `urllib` HTTP (no third-party dep — LibreOffice's bundled Python has no pip).
- **`adapters/libreoffice/README.md`** — install/use; credit note. **`adapters/libreoffice/selftest_uno.py`** — the
  headless round-trip harness (keeper). **`tests/test_libreoffice_adapter.py`** — 5 pytest pure-logic tests.
- **`THIRD-PARTY-NOTICES.md`** — credits the Zotero `CSL_CITATION` field **pattern** (credit-the-lineage).

## Key technical detail — four real UNO traps found via the headless self-test
The field model + endpoint were settled; the hard part was UNO's document-mutation semantics. The headless
self-test (driving a real LibreOffice) surfaced four bugs a static read would never catch:
1. **`loadComponentFromURL` crashes the bridge** unless loaded with `Hidden=True` (and `--invisible` makes it
   worse — dropped). 
2. **Stale bookmark anchor** — clearing the old bibliography deletes its bookmark, so re-reading that anchor
   hangs; reuse the live cursor instead.
3. **`setString` on a ReferenceMark anchor destroys the mark** (replacing a mark's whole range removes it) — so
   the write-back was silently deleting every mark. Fix: **recreate** the mark around the new text (snapshot name
   + range → drop → replace text → re-wrap a same-named mark; the `rnd`/payload, hence the citationID, is
   preserved).
4. **Holding `ReferenceMarks` collection items across a mutation invalidates the others** (a property read on a
   stale handle *hangs*). Fix: capture immutable **names** first, then **re-fetch each mark by name** right before
   editing it (applied to both the write-back and flatten). Also: removing a ReferenceMark deletes its wrapped
   text, so **flatten** captures the rendered text and re-inserts it as plain static text. Citations are placed
   non-adjacently (real documents have text between them; adjacent marks corrupt on recreate — a documented v1
   limitation).

## Manual verification script (the user's hands-on pass)
1. `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080` (with a populated library).
2. Copy `adapters/libreoffice/callosum_cite.py` into `%APPDATA%\LibreOffice\4\user\Scripts\python\`; restart LO.
3. New Writer doc → type a sentence → **Tools → Macros → … → callosum_cite → CallosumInsertCitation**, enter a
   paper id → the citation renders. Insert a second elsewhere → **CallosumRefresh** → numeric styles number by
   order. **CallosumSetStyle** `ieee` then `apa` → the whole doc re-renders + bibliography updates.
   **CallosumFlatten** → citations become static text.

## Headless self-test (automated, run this session)
`.local/lo_roundtrip/run_roundtrip.py` seeds a temp callosum (Vaswani 2017 + Devlin 2019), starts the server + a
headless soffice, runs `selftest_uno.py`, tears down. Result **SELFTEST OK**:
- document order `[callosum-1, callosum-2]`; IEEE in-text `[1]` / `[2]`; APA `(Vaswani & Shazeer, 2017)` /
  `(Devlin & Chang, 2019)`; flatten removes the marks and preserves the rendered text.

## Pytest
**424** passing (+5 `test_libreoffice_adapter.py`: mark-name round-trip, foreign/malformed-mark rejection, id
stamp, request builder, document-order sort; 1 skipped opt-in browser smoke unchanged). `ruff` clean. Audit
`.claude/security-audits/2026-06-21_libreoffice-adapter.md` **PASS**. No `app/` change → no migration, no
route-surface change, no frontend rebuild; **no egress** (local 127.0.0.1 only).

## Non-goals (deferred)
`.oxt` packaging + toolbar (v1 is the drop-in macro); a library-search picker (insert is by id); grouped cites /
locators / note-style footnotes; Track-Changes-corruption handling; adjacent-mark recreate. **Next adapters:**
Word (Office.js — needs the CORS/origin change) then Google Docs (cloud opt-in).
