# Increment 72 Notes — Auto-suggest tags (local c-TF-IDF, no Gemini)

The per-paper analogue of inc-52's axis suggestion: a "✨ Suggest" button on the Details Tags row proposes
candidate tags mined from the paper's own text vs the library, which the user curates. **Purely local** (no
embeddings, no clustering, **no Gemini** — the user's explicit choice); candidates flow into the inc-71
tag-add path.

## Implemented
- **New `app/backend/clustering/tag_suggestion.py`** — `suggest_tags_for_paper(conn, paper_id, *,
  existing_tag_names, limit=8)`: ranks the paper's terms by **tf · idf** over the live library —
  `tf(term, paper) · (log((N+1)/(df+1)) + 1)` — dropping the paper's current tags, then returns the top-N.
  Reuses **`axis_suggestion._paper_tokens`** (shared content tokenizer: title + JATS-stripped abstract,
  stopwords/short/digits removed — keeps tags & axis terms from the same vocabulary). Trashed/missing paper
  or no usable text → `[]`. `MAX_LIBRARY_PAPERS = 5000` guards the IDF scan. No embeddings/clustering/egress.
- **`GET /papers/{id}/suggested-tags`** (`routers/tags.py`, sync, read-only) → `{suggestions: [str]}`; 404
  for an unknown paper; excludes the paper's existing tags (via `get_tags_for_paper`).
- **Frontend** (`25_detail.jsx` `TagsRow`): a **✨ Suggest** link → GET → candidate chips (reuse the dashed
  `.term-chip`, click to add); `add()` now takes an optional name so a candidate click reuses the inc-71 add
  path, drops the accepted candidate, and refreshes. A quiet "no new suggestions" when empty. `styles.css`
  `.tag-suggest-*`. Rebuilt `callosum-app.html`.

**No migration, no egress, no new dependency.** tag_suggestion.py 60 / tags.py 71 — all < 600.

## Verification
- **pytest 251** (+3, `tests/test_tag_suggestion.py`): distinctive term ranks first + existing tags excluded
  (case-insensitive) + trashed/missing → `[]`; **idf demotes a common term** below an equally-frequent rare
  one; endpoint returns candidates, drops a just-added tag, 404s on unknown. Route-surface invariant
  += `/papers/{paper_id}/suggested-tags`.
- **Live E2E** (`.local/tag_suggest_e2e/`): ✨ Suggest → candidates (most distinctive = "photosynthesis") →
  accepting one adds it as a tag + removes it from the suggestions. **0 console errors.**
- Audit `.claude/security-audits/2026-06-20_tag-suggest.md` — **PASS** (local, read-only, bound-param,
  plain-text output).

## Manual verification script
1. Click a paper with an abstract → Details → Tags row → **✨ Suggest**.
2. Candidate chips appear (the most distinctive terms of that paper). Click one → it becomes a tag and leaves
   the suggestions. Nothing is sent off-device.

## Deferred (noted)
- The optional egress-gated **Gemini** polish (deliberately omitted — local-only per the user). Could be
  added later behind the existing consent gate, mirroring `axis_suggestion.apply_labels`.
- Multi-word phrase candidates (today single tokens); a sidebar Tags browser (inc-71 deferral).
