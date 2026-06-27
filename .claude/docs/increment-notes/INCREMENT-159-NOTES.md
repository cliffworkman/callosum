# Increment 159 — formatted "Cite as…" in the Cite pane (#30 follow-on)

The deadline-writer persona's ask from the inc-156 experience pass: the in-app **Cite** pane could only extract
**BibTeX** (for a reference manager), but a writer hand-citing in prose wants a **formatted human citation**
(APA/MLA/IEEE/…). This adds it, reusing the inc-106 citeproc engine. **Frontend-only** — no backend change (the
`/citations/render` + `/citations/styles` endpoints already exist; both local, no egress).

## Implemented (`app/frontend/js/37_cite.jsx` + `styles.css`)

- A pane-level **style picker** in the results header (`/citations/styles`, default `apa`) — one selector for all
  suggestion cards.
- A per-card **`FormattedCiteButton`** ("Cite") that renders the paper in the selected style via
  `POST /citations/render {paper_ids:[id], style}` (the inc-106 engine) and copies the `reference_text` to the
  clipboard (✓ feedback) — the same render the Details "Cite as…" and the word-processor adapters use.
- The existing BibTeX copy stays as a secondary action (relabeled **BibTeX**); the card foot is now
  [Open source region] · [Cite] · [BibTeX] · stance confidence.
- CSS: `.cite-results-head` (note + picker on one row) + `.cite-style` (the labeled select), tokens only.

## Notes

- **No new claim/signal** — formatting is mechanical (citeproc); Principles non-triggering. **No backend/endpoint/
  egress/migration**, reuses tested endpoints → no audit gate; surface unchanged (route_42 claims `37_cite.jsx`):
  **110/110 API + 577/577 FE, 0 uncovered**.
- The render is **local** (bundled CSL + the Node citeproc sidecar; no egress).

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc159_cite_format.py`): open THEORY → Cite, paste a sentence → the
results show the **style picker**; clicking a card's **Cite** fires a `POST /citations/render` (200) — the
formatted-cite path runs end-to-end UI→engine — with 0 console/page/genai. (The in-process render returns e.g.
"Lovelace, A. (n.d.). Facial Anomaly Perception."; the clipboard write is the shipped Details/BibTeX pattern —
headed Chromium blocks `clipboard.writeText` without OS focus, so the driver asserts the render call, not the
clipboard.)

## Pytest

**578** unchanged (frontend-only; `test_frontend_assembly` confirms `callosum-app.html` is in sync). `ruff` clean.

## Next

Back to the bigger **#30** continuation — **SP2: beyond-library discovery** (OpenAlex `related_works` / co-citation
+ Semantic-Scholar recommendations, each candidate with an explainable reason; trips the audit + Principles gates,
so its own plan-mode increment) + Stage-4 section-scoping; the Word (Office.js) + Google Docs adapters remain the
broader word-processor track.
