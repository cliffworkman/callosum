# UX Scope

The current UI is a three-pane local reference workbench served from the FastAPI app. It is implemented in `app/frontend/` React chunks and assembled into the single served frontend.

## Main Surfaces

- Library: searchable/sortable paper list with checkbox multi-select, axis filter banner, tag filter banner, selected-paper actions, bulk summarize, bulk export, bulk Trash, live/Trash toggle, restore, permanent delete, empty Trash, and duplicate-scan entry point.
- PDF viewer: pdf.js document rendering, text selection, user highlights, highlight notes/colors, annotation management panel, citation overlays, synthesis-saved highlights, page jumps, zoom, and coordinate-honest exact/region/null behavior.
- Details pane: always-editable bibliographic fields, DOI re-resolve, identifiers, "More" DOI-populated fields, attachment list, tags, local tag suggestions, and provenance footer.
- Axes panel: create/edit/merge/delete axes, term curation, score/re-score with per-axis cutoff, manual add/remove via library focus mode, hide/show uncertain papers, sort/filter, and suggest-optimal-axes.
- Synthesis pane: always-on top-right pane with query box, saved synthesis history, generated sentences split into verified and flagged sections, citation cards, quotes, page links, confidence scores, and "Save as highlight" when allowed.
- Duplicates modal: local scan results, confidence/reason display, trash resolution, dismiss as not duplicate, dismissed-pair management, and undismiss.
- Settings modal: dark-mode preference.
- Help modal: navigable help corpus plus optional AI help assistant.

## Evidence UX Commitments

- Every synthesis citation shows source title, page, quote, status, retrieval confidence, quote confidence, support confidence, and coordinate precision.
- Sentence display uses `verified` when all citations verify; otherwise it is `flagged`.
- Citation statuses come from storage as `verified`, `weak`, `contradicted`, or `unverified`; the UI styles non-verified citation states as flagged evidence requiring review.
- Exact coordinates may draw rectangles and may be saved as durable synthesis highlights.
- Region coordinates open the source and display an approximate-location warning.
- Null/absent coordinates open the source page if possible and draw nothing.
- Confidence is shown as signal, not proof. The quote and PDF location remain the user-facing evidence.

## Current Interaction Boundaries

- Gemini-backed summary generation is unavailable until the user explicitly enables library data egress and provides an API key.
- The AI help assistant has its own toggle and uses the help corpus, not library text.
- Duplicate detection flags possible duplicates but never auto-merges.
- Manual axis assignment is a durable override and survives re-score.
- Imported/user/system-like provenance must stay visible enough that the user can tell what came from them, Zotero, Crossref, synthesis, or local inference.
