# Security Audit — LibreOffice (UNO) citation adapter (inc 108)

**Date:** 2026-06-21
**Feature:** The first word-processor adapter — a drop-in LibreOffice Writer Python macro that places live
citation fields (ReferenceMarks carrying CSL-JSON), reads the ordered set, and writes back the in-text + bibliography
that callosum's `POST /citations/render-document` (inc 107) renders. Client-side code that ships into the user's
LibreOffice; **no change to the callosum server.**
**Files:** `adapters/libreoffice/callosum_cite.py` (the macro), `adapters/libreoffice/README.md`,
`adapters/libreoffice/selftest_uno.py` (headless round-trip harness), `tests/test_libreoffice_adapter.py`.

## Trigger
The future-track spec flags the **per-target field-injection path into live documents** as a security surface; a
new external component also warrants a review. Note what this is **not**: no new server endpoint, no new server
dependency, no new server fetch/ingestion path, no auth change. The render endpoint it calls was audited inc 107.

## Threat review
- **Field injection into the document.** The adapter writes the server's rendered citation/bibliography text into
  Writer ranges with `XText.setString` / `insertString` — i.e. **plain text**, never an HTML/RTF/ODF paste path.
  There is no markup interpreter on the write side, so a malicious-looking rendered string cannot inject document
  structure, macros, or fields. The server output is *already* sanitized (`render._safe_html` / `_to_text`, inc
  106/107); the adapter takes the **`text`** field (plain), not HTML. Defence-in-depth: even unsanitized text
  would be inert as `setString` content.
- **Untrusted input / boundary (rule #4).** Two inputs: (a) the user-typed paper id — coerced with `int()` before
  it reaches `/papers/export` (a non-numeric id raises and is shown in a message box, never executed); (b) the
  ReferenceMark name payload — `decode_mark_name` is **defensive**: wrong prefix/arity, bad base64, bad JSON, or an
  empty item list all return `None` and the mark is skipped (a corrupt or foreign mark — e.g. a real Zotero mark —
  never crashes a refresh and is never sent to the server).
- **SSRF / external calls / egress.** The macro talks **only** to a fixed `http://127.0.0.1:8080` base over stdlib
  `urllib` (no third-party HTTP client). The CSL-JSON it sends is the **user's own document/library data**, to the
  user's own local server. No remote host, no cloud, **no egress** (this is the local LibreOffice target — exactly
  why it is the first adapter; Google Docs, the cloud target, is fenced as opt-in and built last). The two
  `urlopen` calls carry `# noqa: S310` with a justification (fixed local base, not attacker-controlled).
- **Resource / DoS.** Bounded by the document: each refresh sends N clusters where N = citations in the document;
  the server already caps clusters/items/total (inc 107). HTTP calls use a 20s timeout. No unbounded loops (the
  `_new_rnd` counter and the scan both iterate the finite mark set).
- **Secret handling.** None — no keys, no tokens; the macro reads only the local library.
- **File-path safety.** The macro writes nothing to disk and builds no filesystem path; the only paths are the
  user's chosen Scripts/python install location (manual) and the dev self-test's temp profile (not shipped).
- **Code-execution surface.** The macro decodes base64→JSON only (`json.loads`, not `eval`/`pickle`); a crafted
  mark name can at worst produce a `None` (skipped) or a CSL dict forwarded to citeproc, which treats it as data.
- **Fail-safe UX.** Every macro entry point wraps its work in try/except and surfaces failures in a Writer message
  box — a server-down / bad-id / network error never crashes Writer or corrupts the document.

## Negative-path checks (concrete)
- Foreign/malformed/empty marks → skipped, not fatal (`test_decode_rejects_foreign_and_malformed`).
- Non-numeric / unknown paper id → `int()`/`fetch_csl` raises → message box, no document change.
- Unknown style id → `set_style` validates against `GET /citations/styles` and raises before any write.
- Internal `_mark` handles are stripped from the request body (`test_build_render_request_shape`) — only CSL-JSON +
  citationID reach the server.
- **End-to-end**: the headless UNO self-test (`selftest_uno.py`) drives a real LibreOffice through insert → render →
  restyle → flatten against a live callosum and asserts the position-aware output — confirming the write path is the
  plain-text path described above.

## Principles gate (rule #9)
Clears. The adapter **places**, callosum **renders** — no formatting (and thus no claim) originates in the adapter;
it **never auto-inserts** (every action is user-invoked); it is fully **local** (no egress). Credit-the-lineage is
honored: the Zotero `CSL_CITATION` field convention is credited as a *pattern* in the README + `THIRD-PARTY-NOTICES.md`.

## Result
**Security Audit: PASS** — client-side, local-only, plain-text writes, defensive decode, no new server surface, no
egress, no secrets, no file-path-from-input.

---

## Addendum — inc 157: the "Suggest citations" macro (`CallosumSuggestCitations`)

**Date:** 2026-06-27. A new macro extends the adapter: read the current sentence (the selection, else the
paragraph at the caret), POST it to `POST /citations/suggest` (the inc-156 contract), show a pick-list of library
suggestions (stance + quote preview + match), and insert the chosen one via the existing audited `insert_citation`
flow. **Same posture as inc 108 — no new server surface** (the endpoint was audited inc 156), no new dependency
(stdlib `urllib`), no egress (127.0.0.1 only).

- **New data leaving the macro:** the **document text** (the highlighted sentence / current paragraph) is POSTed
  to the local server — analogous to the inc-108 macro sending CSL-JSON, and to the in-app Cite pane: it is the
  user's own draft, sent to the user's own 127.0.0.1 server, **no egress**. The suggest engine is fully local
  (local embeddings + local NLI; inc-156 audit `2026-06-26_citation-suggest.md`).
- **Untrusted input (boundary):** the response is consumed defensively — `fetch_suggestions` returns `[]` on a
  malformed/empty shape; `build_suggest_rows` tolerates missing stance/author/year/match and truncates the quote;
  the chosen `paper_id` flows into `int()` via the audited `fetch_csl`/`insert_citation` path. No markup is
  interpreted (the list rows are plain strings in a UNO ListBox; the inserted text is the plain-text render path).
- **Resource / timeout:** the suggest call uses a longer timeout (`SUGGEST_TIMEOUT = 90s`) because the first call
  loads the embed + NLI models server-side; a server-down case fails fast (connection refused, not a 90s hang).
- **Honesty / Principles:** the dialog shows each candidate's stance + quote (the reason) and the user **picks**
  — nothing auto-inserts; the suggestion/stance signal is the backend's (already gated), and inserting reuses
  citeproc (no formatting in the adapter). Non-triggering beyond honoring this.
- **Verification:** the pure logic (`build_suggest_rows`, `fetch_suggestions`) is pytest-covered; the
  suggest→insert chain is exercised by the extended headless round-trip (`selftest_uno.py` → **SELFTEST OK**,
  both seeded papers returned with a `support` stance from the real NLI, top one inserted). The interactive
  list-box dialog is the user's manual eyeball.

**Addendum result: PASS** — same local-only, plain-text, defensive, no-egress, no-new-dependency posture; the only
new data flow (document text → local server) is the feature's purpose and stays on 127.0.0.1.

---

## Addendum — P0 phases 1–6 (backlog #33/#34, 2026-07-21): schema, transactional refresh, cite-property
## passthrough, mark_at_cursor, delete/merge/split/open-in-callosum

**Trigger:** cumulative — phases 1–4 were each individually small enough not to trigger the gate on their own
merits (recorded as such in their increment notes); phase 6 (delete/merge/split/open-in-callosum + a new
frontend deep-link) crosses "a net-new feature spanning 3+ files / ~300+ LOC" on its own, so this addendum
covers the whole P0-so-far surface in one place rather than fragmenting across many tiny notes.

- **Phase 1 (versioned mark-payload schema):** purely additive + backward-compatible — a `"v"` key in the
  existing base64-JSON payload, defaulted for old marks, explicitly inert (never guessed at) for an unrecognized
  future version. No new external surface; still the same defensive `decode_mark_name` (any parse failure → the
  mark is skipped, never fatal) the original audit already covers.
- **Phase 2 (transactional refresh):** `_transactional_apply` wraps the existing, already-audited write-back
  loop in `doc.getUndoManager()` grouping. No new external surface, no new input boundary — a reliability
  mechanism over the same local UNO mutation the original audit reviewed. Verified against real UNO with a
  fault-injection spike (a mid-loop failure rolls the whole document back to its exact pre-refresh state).
- **Phase 3 (backend cite-property passthrough):** the one backend-adjacent change here — `CitationCluster.items`
  gained a typed `CitationItem` model (`app/backend/api/routers/citations.py`) with `locator`/`prefix`/`suffix`
  length-capped (200/300/300 chars — rule #4, free text from an eventual composer needs a boundary) and `label`
  validated against CSL's real, fixed locator vocabulary (a clean 422 on garbage, not a silent no-op reaching
  citeproc-js). This **tightens** validation on an existing endpoint; it does not loosen it, add a new endpoint,
  or add egress. `citeproc_runner.js`'s new `buildCitationItem` only ever reads recognized keys off items already
  passed through the existing (audited) request pipeline.
- **Phase 4 (`mark_at_cursor`):** a read-only positional lookup over the existing, already-decoded citation scan.
  No new external surface, no new input boundary.
- **Phase 6 (delete / merge / split / open-in-callosum) — the new surfaces this addendum actually needs to review:**
  - **Delete/merge/split** are local UNO document mutations only — no network, no file I/O, no new dependency.
    Threat review is about correctness (not leaking/destroying the wrong content), verified with real-UNO spikes:
    deleting a citation removes exactly that citation's mark + text and leaves surrounding body text byte-intact;
    merging combines exactly the two targeted citations' item sets; splitting reverses a merge losslessly. All
    three degrade honestly (a message box, no mutation) when the cursor isn't on a recognized citation.
  - **`open_in_callosum` (`webbrowser.open`) — a new "launch an external process" surface.** The URL is built
    from two parts only: the already-configured, user-owned local server `base` (no user input reaches this —
    it's the same `base` every other adapter call already uses) and a `paper_id` extracted from the citation's
    own CSL item id and validated with `.isdigit()` before use — a non-numeric/malformed id is refused with a
    message box, never reaches `webbrowser.open`. No shell is invoked (`webbrowser.open` dispatches to the OS's
    URL handler, e.g. `os.startfile`/`open`/`xdg-open` under the hood on the respective platforms) and no
    arbitrary scheme/host is reachable — this is the same class of surface as the already-audited
    `2026-06-27_libreoffice-install.md` (`os.startfile`/`open`/`xdg-open` against a fixed path), applied here to a
    fixed local HTTP(S) base instead of a fixed file path.
  - **The new frontend deep-link** (`app/frontend/js/40_app.jsx`'s `?open_paper=<id>` mount effect): the param is
    parsed with `parseInt` + `Number.isFinite` before use; an absent/invalid value is a silent no-op (no crash,
    no error surfaced). A valid id is passed to the existing `openPdf({id})` path — the exact same "open this
    paper" chokepoint every citation-jump/Files-list/axis-open action already uses; a non-existent id degrades
    exactly as it already does for any other caller of `openPdf` (pre-existing behavior, not a new failure mode).
    The param is stripped from the address bar via `history.replaceState` immediately after use, so it never
    persists across a refresh or gets bookmarked/shared with a stale value. No backend query is built from this
    value directly — any downstream fetch (the PDF itself) goes through the existing, already-parameterized
    `GET /papers/{id}` family.

## Negative-path checks (phase 6, concrete)
- Cursor not on any citation → delete/merge/split/open-in-callosum each show an honest message box; no mutation.
- Only one item in a citation → split refuses with a message box ("nothing to split"), no mutation.
- No adjacent citation in the requested merge direction → refuses with a message box, no mutation.
- A malformed/non-numeric extracted item id → `open_in_callosum` refuses with a message box; `webbrowser.open`
  is never called.
- `?open_paper=abc` (non-numeric) or absent → the frontend effect is a no-op; no console error
  (`test_open_paper_deep_link`, frontend assembly suite).

## Result
**Security Audit: PASS** — phases 1–4 are internal/reliability mechanisms over an already-audited surface with
no new external reach; phase 6's two new touchpoints (`webbrowser.open`, the frontend deep-link) both build a
URL/id from validated, non-injectable inputs and mirror already-audited patterns in this codebase. No new
egress, no new endpoint, no new dependency, no secrets, no file-path-from-input.

## Addendum — evidence-aware Suggest-Citation (inc 460, roadmap #17, backlog #33/#34)

Triggered by the security-audit gate's criterion #5 (net-new feature spanning 3+ files with meaningful LOC), not
by any new external-facing surface — this increment touches **zero backend Python** and adds no new endpoint.
The two pieces actually worth reviewing:

- **The `open_paper` deep link gains `page`/`precision` params** (from the new "Open in PDF" button in the
  Suggest-citation Details dialog, using the exact same `webbrowser.open` call already audited above — same
  fixed local `base`, same `paper_id` source). `page` is `parseInt`'d + `Number.isFinite`-checked before use
  (mirrors the existing `paperId` handling exactly); an invalid/absent value degrades to `target: undefined`
  (today's exact pre-460 behavior), never a crash. `precision` is passed through as an opaque string read only
  by `applyPdfCitationTarget`'s existing `"exact"`/`"region"` branch — an arbitrary/unrecognized value simply
  fails both branches and draws nothing (no exact-highlight fabrication, per invariant #2), never an injection
  surface (it's never used to build a selector, URL, or DOM string directly). Both new params are stripped from
  the address bar via `history.replaceState` immediately after use, same as `open_paper` already was.
- **The evidence-audit record** (`evidence_chunk_id`/`evidence_page_start`/`evidence_page_end`/`evidence_snippet`,
  new optional keys on a citation mark's stored item, `adapters/libreoffice/callosum_cite.py`) is local-only
  data already present in the `/citations/suggest` response the adapter already fetches — no new egress, no new
  fetch. It's persisted inside the SAME mark-name payload mechanism every other per-item override (locator/
  prefix/suffix) already uses, with no new storage/serialization primitive. `evidence_snippet` is hard-truncated
  to `EVIDENCE_SNIPPET_MAX` (150 chars, well under the server's own 400-char cap) specifically to bound
  mark-payload size for a grouped multi-source citation — verified empirically via the extended
  `spike_mark_size_and_reopen` (adds `evidence_n` grouped, evidence-bearing citations with full-length snippets
  and confirms lossless save/reopen round-trip). These fields ride along harmlessly in a later render-document
  request if the citation is refreshed (`CitationItem`'s `extra="allow"` + citeproc-js already ignores CSL
  fields it doesn't recognize — the same posture every other extra field in the stored CSL record already has;
  no privacy/egress implication either way since render-document is a same-origin localhost call, not external
  egress).
- **Multi-select insertion** (`_suggest_dialog`'s `MultiSelection = True`) changes no trust boundary — it's the
  same local UI control property, and insertion still only ever happens on an explicit Insert click (nothing
  auto-inserts); a mixed library/beyond-library selection is refused with a message box rather than silently
  mixing two different consent postures (library picks need no extra egress; a beyond-library pick still goes
  through the existing, already-audited `save_beyond_library_item`/`/discovery/save` write path unchanged).

**Negative-path checks:** `?open_paper=<id>&page=abc` (non-numeric page) → the deep link still opens the paper,
just with no page-jump target (matches the existing non-numeric-`open_paper` no-op posture); a multi-select pick
spanning both library and beyond-library kinds → refused with a message box, nothing inserted
(`test_suggest_and_insert_*`, `tests/test_libreoffice_adapter.py`); an evidence-bearing grouped citation
round-trips losslessly through a real save/reopen (`spike_mark_size_and_reopen`, extended).

**Security Audit (inc 460 addendum): PASS.** No new endpoint/egress/dependency; the deep-link extension mirrors
an already-audited pattern with the same input validation; the evidence record reuses an existing storage
mechanism with a disclosed, empirically-verified size bound.

## Addendum — Citavi-style "Insert evidence" (inc 461, roadmap #20, backlog #33/#34)

Triggered by gate criterion #5 (net-new feature spanning 3+ files). New sibling module
`adapters/libreoffice/evidence_insert.py` (the `composer.py`/`citations_panel.py` dialog-construction pattern)
adds a three-dialog flow: search a paper, pick one of its saved highlights, optionally check a typed claim's
stance against it, and insert it in one of four formats alongside a live citation. Two pieces worth reviewing:

- **A new adapter call site, not a new endpoint.** `cc.list_paper_annotations` calls the already-existing,
  already-audited `GET /papers/{paper_id}/annotations` — the adapter had simply never called it before. The
  response (verbatim quote, page, note, color) is read-only, local (127.0.0.1), and only ever displayed inside
  the modal dialogs the user themselves is driving; nothing is sent anywhere. The new stance check
  (`evidence_insert.check_stance`) calls the sibling `POST /citations/classify-stance` endpoint audited above,
  with the same bounded-text posture (an early `if not sentence or not passage: return None` before any call —
  no oversize/empty text ever reaches the network layer, and a genuinely oversized claim still degrades to the
  endpoint's own 422, shown to the user in the dialog rather than crashing it).
- **The first two-step insertion (free body text + a citation mark, one user action).** `insert_evidence`
  chains two already-audited primitives unchanged: `text.insertString(cursor, body + "\n", False)` (the
  `insert_statement` precedent — plain prose, no markup/formatting injection surface, since Writer's
  `insertString` treats the argument as literal text, never as rich content or a formula) followed by the
  existing `insert_citation_items` reusing the SAME cursor. No new UNO primitive, no new trust boundary. The new
  `evidence_annotation_id` key on `_ITEM_DEFAULTS` (the annotation analog of the inc-460 `evidence_chunk_id`)
  rides the same mark-name payload mechanism every other per-item field already uses — additive, no
  `SCHEMA_VERSION` bump needed (`_normalize_item`'s generic `setdefault` loop already covers a new default key,
  same as inc 460's four `evidence_*` fields). Verified to round-trip losslessly through a real save/reopen via
  the new `spike_insert_evidence` (mirrors `spike_mark_size_and_reopen`'s own proof for the chunk-sourced
  fields).
- **"Quote only" format inserts free text with no citation at all** — a deliberate, disclosed capability (an
  author drafting a working note from a saved highlight before deciding whether/how to cite it), not a new
  attribution-risk pattern: the SAME author who saved the highlight is the one choosing this format, at the
  same one-user-action, explicit-Insert-click boundary every other insertion in this file already uses. Nothing
  auto-inserts; every dialog step requires an explicit action (Next/Select/Insert), matching every other
  multi-step flow in this adapter (the composer's Add/Insert, Suggest-citation's pick-then-Insert).
- **The `.oxt` packaging regression guard already caught the real omission this session** —
  `test_every_local_sibling_import_is_packaged` failed the moment `evidence_insert.py` was added but not yet
  listed in `tools/build_libreoffice_oxt.py`'s `ENTRIES`, exactly the class of bug that guard was built to catch
  (a packaged install 404ing on `import evidence_insert` the first time "Insert evidence…" is clicked). Fixed
  before this addendum was written, not discovered later.

**Negative-path checks (recorded, `tests/test_libreoffice_adapter.py`):** a paper with no saved highlights →
an honest message box, nothing opened further (`test_run_insert_evidence_messages_when_no_annotations`); a
cancelled paper search / highlight pick / configure step at any of the three stages → `None`, no mutation
(`test_run_insert_evidence_stops_early_when_paper_not_picked`); "quote only" → zero citation marks inserted,
confirmed both by a monkeypatched unit test and the real-UNO spike; a stance-check network failure inside the
configure dialog is caught and shown inline (`except Exception` around `check_stance`, never crashes the
dialog).

**Security Audit (inc 461 addendum): PASS.** No new endpoint beyond the already-audited
`/citations/classify-stance`; no new egress class; the two-step insertion chains only already-audited
primitives; the new evidence field follows the existing additive, migration-free storage convention; the
packaging regression guard is green.
