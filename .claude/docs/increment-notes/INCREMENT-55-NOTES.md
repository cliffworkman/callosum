# Increment 55 Notes (fix) — strip JATS from the editable abstract + suggest-axes terms

Two user-reported leaks, one root cause: Crossref abstracts are stored as **raw JATS XML** in
`papers.abstract` (inc-33: store raw, derive a cleaned display copy), and two consumers read it raw:
1. the inc-49 editable abstract **textarea** (bound to raw `p.abstract`) → showed literal `<jats:p>` tags;
2. the suggest-optimal-axes local **c-TF-IDF** (`axis_suggestion._paper_tokens`) → tag names like "jats"
   became top terms / labels.

## Implemented
- **`app/backend/metadata/abstract_display.py`:** new **`abstract_plain_text(raw)`** — same lenient
  `HTMLParser` approach as `clean_abstract_for_display` but emits **plain text**: drops all tags (keeps
  their text), decodes entities, drops a redundant leading "Abstract" title, joins paragraphs with blank
  lines. Reuses `_local_name` (namespaced `jats:p` → `p`) + the entity-encoded pre-pass
  (`&lt;jats:…` → unescape first). Pure; never raises (falls back to the stripped raw).
- **`routers/papers.py`:** `PaperDetailResponse.abstract_text` (a tag-free sibling of `abstract` raw +
  `abstract_display` HTML), set from `abstract_plain_text` in `_paper_detail`.
- **`axis_suggestion.py`:** `_paper_tokens` tokenizes `title + abstract_plain_text(abstract)` — JATS tag
  names can no longer enter the c-TF-IDF terms/labels.
- **`25_detail.jsx`:** the Abstract textarea binds `value={p.abstract_text ?? p.abstract}` — shows clean
  prose; saving still writes the user's plain text to the `abstract` column (replacing JATS for that paper).

## Key technical detail
Display-only cleaning (consistent with inc-33's store-raw ethos): the stored `papers.abstract` is
untouched; the textarea shows the derived `abstract_text` and only overwrites the column if the user edits
+ saves. The abstract's JATS noise still lives in the *embedding text* (`paper_embedding_text`) →
clustering/scoring vectors; cleaning that is **deferred** (it's coupled to `PAPER_TEXT_VERSION` and would
force a full re-embed + break axis scoring until then) — out of scope for a display/terms fix.

## Verification
- **pytest: 190** (+7): `abstract_plain_text` unit tests (strips JATS, entity-encoded, plain passthrough,
  paragraph joins, None/blank, pure); the API JATS test now also asserts `abstract_text` is tag-free; a
  suggest test asserts no term/label contains "jats"/"italic" for JATS-wrapped abstracts.
- **Live E2E** (`.local/jats_fix_e2e/`): open a JATS-abstract paper's Detail → the abstract textarea shows
  clean, tag-free text; **0 console errors**.
- No audit gate (no new endpoint/egress/ingestion/migration). All `app/` files < 600.

## Deferred (noted)
Cleaning the abstract inside `paper_embedding_text` (embedding-level JATS) — needs a `PAPER_TEXT_VERSION`
bump + a full re-embed; tracked for a future embedding-hygiene pass.
