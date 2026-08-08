# Increment 461 — Citavi-style "Insert evidence" for the LibreOffice adapter (backlog #33/#34, P2 item #20)

## Implemented

Third item in the confirmed P2-leapfrog roadmap (#19 → #17 → **#20** → #21 → #18 → #22; see memory
`callosum-p2-leapfrog-roadmap`, updated this increment). Two scope decisions confirmed with Cliff before the
formal plan: (1) include a basic claim-vs-evidence stance check this round (not deferred), and (2) the picker
searches **any** paper in the library, not just already-cited ones.

### New backend endpoint: `POST /citations/classify-stance`

New sibling router `app/backend/api/routers/citation_stance.py` (`citations.py` was already at 595/600 lines —
no room; mirrors the established `methods_retraction.py`/`paper_enrich.py` sibling-router pattern). Reuses the
exact cached `_suggest_stance_scorer(request)` `NLIStanceScorer` singleton `/citations/suggest` already warms —
no new model, no new egress class. This is the first pairwise `(sentence, passage)` stance endpoint in the
codebase; every other call site (`/citations/suggest`, `beyond_library.py`, `critical_review.py`,
`citation_context.py`, `reference_integrity.py`) bundles classification with retrieval.

```python
class ClassifyStanceRequest(BaseModel):
    sentence: str = Field(min_length=1, max_length=MAX_TEXT_LEN)  # reuses citations.py's existing 4000-char cap
    passage: str = Field(min_length=1, max_length=MAX_TEXT_LEN)

@router.post("/citations/classify-stance", response_model=StanceResponse | None)
def classify_stance_endpoint(payload: ClassifyStanceRequest, request: Request) -> StanceResponse | None:
    scorer = _suggest_stance_scorer(request)
    stance = scorer.classify_stance(sentence=payload.sentence, passage=payload.passage)
    if stance is None:
        return None
    return StanceResponse(label=stance.label, confidence=stance.confidence, probs=stance.probs)
```

### New sibling module: `adapters/libreoffice/evidence_insert.py`

Mirrors the `composer.py`/`citations_panel.py` "dialog construction is a distinct concern" pattern —
`callosum_cite.py` is 6000+ lines (a pre-existing size; `adapters/` is outside the 600-line rule #1 scope, so
no line-budget concern, but the module-separation discipline still applies). A three-dialog flow:

1. **`_paper_search_dialog`** — live search-as-you-type single-select paper picker. Reuses the SAME
   empirically-proven-safe `XTextListener` wiring `composer.py::run_composer_dialog` already uses for its
   search box, applied to a single pick instead of a multi-item assembly.
2. **`_annotation_list_dialog`** — lists the chosen paper's saved highlights (`cc.list_paper_annotations`, a
   new small HTTP wrapper in `callosum_cite.py` calling `GET /papers/{id}/annotations` — an existing endpoint
   the adapter had never called before this increment). Single-select.
3. **`_annotation_configure_dialog`** — the Details/configure step: full quote + note (read-only), an editable
   **Claim** field with an explicit **Check stance** button (deliberately NOT live-per-keystroke — NLI
   inference is a real model call, matching Suggest-citation/citation-integrity-preflight's own explicit-action
   convention), a **format** dropdown (4 choices below), and an editable page locator pre-filled from the
   annotation's own `page` field. Returns `(format, locator)` on Insert, else None — mirrors
   `composer.py::_edit_item_options`'s "returns on OK, discard on Cancel" contract exactly.

**Four insertion formats** (`FORMAT_QUOTE_ONLY` / `FORMAT_QUOTE_CITE` / `FORMAT_PARAPHRASE_CITE` / `FORMAT_CARD`):
quote-only and quote+citation both use the verbatim quote; paraphrase+citation uses the saved note (falling
back to the quote if no note was ever saved — never silently inserting nothing); the structured card joins
quote + note. **"Quote only" inserts plain text with NO citation mark at all** — a deliberate, disclosed
capability for drafting a working note before deciding whether/how to cite, not an accident.

### The two-step insertion core (`insert_evidence`)

The first place this adapter inserts free-form body text AND a citation mark together as one user action —
`insert_statement` inserts text with no citation, `insert_citation_items` inserts a citation with no free text;
this chains both, reusing each unmodified:

```python
def insert_evidence(doc, base, paper_id, annotation, fmt, locator):
    cursor = cc._insertion_cursor(doc)
    body = format_body_text(annotation, fmt)
    if body:
        doc.getText().insertString(cursor, body + "\n", False)
    if fmt == FORMAT_QUOTE_ONLY:
        return None
    entry = {"paper_id": paper_id, **_evidence_annotation_fields(annotation)}
    if locator:
        entry["locator"] = locator
        entry["label"] = "page"
    return cc.insert_citation_items(doc, [entry], base, cursor=cursor)
```

UNO's `insertString(cursor, text, False)` collapses the passed cursor to right after the inserted text, so
reusing that SAME cursor object for `insert_citation_items` places the citation mark immediately after its
body — no manual repositioning needed.

### Evidence-audit traceability (extends inc 460's mechanism, not a new one)

New optional key on `_ITEM_DEFAULTS`: `evidence_annotation_id` (default `None`) — the annotation analog of
inc 460's `evidence_chunk_id` (a saved highlight has no `chunk_id`). Additive/backward-compatible, confirmed no
`SCHEMA_VERSION` bump needed (`_normalize_item`'s `setdefault` loop already covers a new default key, the exact
inc-460 precedent). Implemented as a NEW function `_evidence_annotation_fields` in `evidence_insert.py` rather
than branching inside `callosum_cite.py`'s existing `_evidence_fields` — a smaller, lower-risk diff achieving
the identical end state (the same set of `evidence_*` keys populated), since `_evidence_from_item`'s read side
(the "Citations in this document" → View evidence… display) is already generic over whichever fields are
present and needed no changes either way.

### `.oxt` packaging

New menu node ("Insert evidence…", `adapters/libreoffice/oxt/Addons.xcu`); `evidence_insert.py` added to
`tools/build_libreoffice_oxt.py`'s `ENTRIES` (the regression guard `test_every_local_sibling_import_is_packaged`
caught this omission immediately on the first test run — exactly the class of bug it exists to catch). A new
macro export `CallosumInsertEvidence`/`g_exportedScripts` entry too, following the majority precedent (33 of 35
existing `_ACTIONS` entries have a matching Tools → Macros export).

## Key technical detail

**`evidence_insert.py`'s own `import callosum_cite as cc` is a DIFFERENT module object than
`adapters.libreoffice.callosum_cite`** (the way pytest imports it via the package path). The sys.path-injection
+ bare `import callosum_cite` idiom every sibling module (`composer.py`, `citations_panel.py`, this one) uses to
run standalone under LibreOffice's own bundled Python means `evidence_insert.cc is not
(adapters.libreoffice.callosum_cite)` — confirmed empirically. Tests that monkeypatch something
`evidence_insert.py` calls internally (`_insertion_cursor`, `insert_citation_items`, `_post_json`,
`_component_ctx`, `list_paper_annotations`) must patch it on `ei.cc.*` (the module's OWN reference), not the
test file's separately-imported `cc` — patching the wrong one silently no-ops (or, worse, lets a real
`urllib` call through to a nonexistent host). Caught by three tests actually hitting real DNS-resolution
`URLError`s on first run, not by inspection.

## Housekeeping / gates

- **Security audit**: two addenda — `.claude/security-audits/2026-06-27_citation-suggest.md` (the new
  `/citations/classify-stance` endpoint: no new model/egress class, bounded input, graceful `None`
  degradation) and `.claude/security-audits/2026-06-21_libreoffice-adapter.md` (the adapter-side flow: a new
  call to an already-audited endpoint, the first two-step insertion chaining only already-audited primitives,
  and the disclosed "quote only, no citation" capability).
- **QA route**: `.claude/qa-routes/route_42_cite.md` gains `POST /citations/classify-stance` in its `api:`
  frontmatter, a route_39-style note that the real end-to-end proof is `run_roundtrip.py`
  (`spike_insert_evidence`), and a direct-API step + pass-criteria line so it's still exercised live in this
  suite.
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #20 marked **✅ CLOSED inc 461**; the roadmap-order note updated
  ("#19, #17, and #20 are now closed; #21 is next").
- Memory `callosum-p2-leapfrog-roadmap` updated: items #17/#20 marked closed with their one-line gists, #21
  named as next up.
- `.claude/CLAUDE.md`: counter bumped to 461; pytest count updated to the actual measured total.

## Manual verification script

1. Open a real Writer document. Run **Insert evidence…**.
2. Search for a paper with saved PDF highlights (e.g. "attention") → pick it.
3. Pick a saved highlight from the list → confirm the full quote + note render.
4. Type a claim, click **Check stance** → confirm the 3-way support/contrast/mention breakdown renders (or an
   honest "unavailable" message if the local NLI model isn't loaded).
5. Try each of the 4 formats in turn (Cancel between, or Undo after each Insert):
   - Quote only → confirm a quoted paragraph lands with NO citation mark.
   - Quote + citation → confirm the quote AND a citation land, in that order.
   - Paraphrase + citation → confirm the saved note's text lands (not the quote) + a citation.
   - Structured card → confirm quote + note + citation all land together.
6. Confirm the editable locator pre-fills from the highlight's page and is honored in the inserted citation.
7. Open "Citations in this document" → View evidence… on an Insert-evidence-sourced citation → confirm it
   shows the recorded page + snippet, same as a Suggest-citation-sourced one.

## Verification

- `pytest tests/test_citation_stance.py tests/test_libreoffice_adapter.py tests/test_libreoffice_composer.py
  tests/test_libreoffice_oxt.py tests/test_citations_suggest.py -q` → **198 passed** (5 new backend endpoint
  tests + 21 new adapter tests [pure helpers + the two-step insertion sequence + `run_insert_evidence`
  orchestration, all UNO-free via monkeypatching] + 2 existing tests updated for the new `_ITEM_DEFAULTS`/`.oxt`
  packaging shape).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: unaffected (`adapters/` is outside the line-budget tool's scope;
  `citation_stance.py` is a small new leaf file, well under the cap).
- `python tools/qa/build_surface_map.py check`: `API surfaces: 384 | covered: 384 | uncovered: 0` (up from 383;
  the new endpoint is claimed by `route_42_cite.md`'s frontmatter, not just incidentally passing).
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — the new `spike_insert_evidence` proves the real
  two-step body-text-then-citation sequence lands correctly for 3 of the 4 formats (quote+citation, quote-only
  inserting zero marks, structured card), and that the new `evidence_annotation_id` field round-trips
  losslessly through a real save/reopen.
- Full `pytest -n auto -q`: [see final commit message / CI status for the actual green count — local
  full-suite runs on this machine have documented intermittent xdist worker-crash flakiness near the end
  unrelated to code; CI's clean-environment run is the fallback per established session practice].

## Rollback

Revert `app/backend/api/routers/citation_stance.py` (new file, delete), the citation_stance import/mount in
`app/backend/api/app.py`, `adapters/libreoffice/evidence_insert.py` (new file, delete),
`adapters/libreoffice/callosum_cite.py`, `adapters/libreoffice/oxt/Addons.xcu`,
`adapters/libreoffice/selftest_uno.py`, and `tools/build_libreoffice_oxt.py` to their pre-461 state. All changes
are additive/backward-compatible (a new endpoint, a new sibling module, one new default key); no schema/
migration involved.
