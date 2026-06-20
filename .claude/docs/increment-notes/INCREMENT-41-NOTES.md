# Increment 41 Notes — Gemini axis synonym suggester (egress-gated, human-curated)

## What
Optional AI assist to broaden a niche axis's recall: Gemini proposes related terms/synonyms, the user
**curates them in a modal**, and the chosen terms fold into the axis description (re-score to apply).
AI proposes, the human decides; everything stays transparent (the terms are visible/editable text in
the description). Local-first preserved — this is the only new off-machine path and it is opt-in.

## Backend
- `integrations/gemini/axis_terms.py` (new): `AxisTermSuggester` Protocol + `GeminiAxisTermSuggester`
  (mirrors `GeminiSummaryGenerator`). `suggest(label, description)` raises `DataEgressDisabledError`
  **before** importing/calling `google.genai` when egress is off; else one `generate_content` call for a
  JSON array of related terms. `_parse_terms` defensively cleans untrusted output: dedupe
  (case-insensitive), drop empties / over-long (>60) / label-word echoes, cap to 12. Exported from
  `integrations/gemini/__init__.py`.
- `app/backend/api/app.py`: `create_app(..., axis_term_suggester=None)` + `api.state.axis_term_suggester`
  (mirrors `summary_generator`).
- `app/backend/api/routers/axes.py`: **`POST /axes/suggest-terms`** (sync — one fast LLM call, not a
  library-wide pipeline; stateless). `_axis_term_suggester(app)` (injected or
  `GeminiAxisTermSuggester(GeminiConfig.from_environment())`). Egress off → **503** + guidance; other
  Gemini failure → **502** (never 500). `SuggestTermsRequest/Response` models. Route-surface test updated.

## Frontend (`app/frontend/js/15_axes.jsx` + `styles.css`; rebuilt `callosum-app.html`)
A "suggest terms" action on each axis opens a new **modal**: posts the axis label+description, shows the
returned terms as toggle chips (default selected) + an "add your own" input, and a live preview of the
resulting description (the axis description with a single `Related: …` block — re-applying **replaces**
it, doesn't stack). **Apply** = `PATCH /axes/{id} {description}` → axis goes stale (if it was scored) →
re-score. Egress-off (503) shows the enable-egress guidance, not a crash. First modal/overlay in the app.

## Verification
- **pytest: 143** (140 + 3 new): suggester returns curated terms; empty label → 422; **egress-off → 503**
  with no network touched (hermetic); `_parse_terms` dedupe/cap/echo-drop/malformed→[]. Existing tests
  unaffected.
- **Live browser E2E** (`.local/axes_terms_e2e/`, fake suggester injected): create axis → "suggest terms"
  → modal shows 3 chips → Apply → description folded to "…\n\nRelated: rsfmri, functional connectivity,
  default mode network" → **0 console errors**.
- Security audit: PASS (`.claude/security-audits/2026-06-19_axis-term-suggester.md`). No file under
  `app/`/`integrations/` exceeds 600 (axes.py 404, axis_terms.py 76).

## Usage
Set `CALLOSUM_ALLOW_DATA_EGRESS=1` + `GOOGLE_API_KEY`, restart, then on an axis click "suggest terms" →
curate → Apply → Re-score. Without egress, the modal explains how to enable it.

## Roadmap (next, per the user)
1. Resizable + collapsible side panels (frontend-only).
2. Axis-management tree: sort + multi-select + bulk delete/merge (merge needs a defined backend op).
3. Suggest optimal axes (big): unsupervised discovery + coverage-with-diversity (MMR) so suggested axes
   cover the library without redundant near-duplicates.
