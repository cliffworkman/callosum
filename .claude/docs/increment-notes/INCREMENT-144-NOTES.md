# Increment 144 — Export / copy a paper's highlights + notes (Close reader dogfood)

## Experience pass (rule #11)

**Persona:** the **Close reader** (reading one paper deeply — marking passages, noting a few, returning across
sessions). A dispatched persona agent drove the read → highlight → note → navigate → return-and-re-find flow.
**Found:** the reading experience is genuinely good — page comfort (zoom / Fit-width / Two-up / Reading mode),
select→swatch or select→✎-note in one gesture, a Notes panel that lists every mark and jumps+flashes to it, and
marks that **persist + re-find** reliably across sessions. **The one real gap:** there is **no way to get my marks
*out*** — Callosum keeps them safe and jumpable but trapped in the panel; no "copy all notes", no per-paper
annotation digest, no markdown export. "The marked-up artifact is the reader's payoff." Verdict: *comfortable to
read + mark, but a serious reader keeps a foot in their PDF app because they can't carry their marks forward.*
(5th persona run → 5th real, specific gap.)

## Implemented

A **Copy** + **Export .md** affordance in the PDF viewer's Notes panel head (shown when there is ≥1 highlight).
Both assemble a Markdown **digest** of the paper's highlights + notes — built entirely from the already-loaded
`annotations` (`{page, anchor_text, note}`), page-ordered like the panel:

```
# <paper title>

_N highlights_

**p.3** — <highlighted text>
> <note>
```

- **`30_viewer.jsx`:** a pure `buildAnnotationDigest(title, annotations)` helper + `copyDigest`
  (`navigator.clipboard`, the inc-70 secure-context pattern; toast on success) + `exportDigest` (blob → `<a
  download>` `*-notes.md`, the inc-70 download pattern). Two `.btn-link` buttons in `.pdf-annot-head`.
- **Frontend-only** — no backend endpoint, no new data (the annotation list already carries the quote + note +
  page); a backend export endpoint (reusable by future adapters) is a possible follow-up, deferred.

## Key technical detail

The digest is page-ordered (the panel's order) and omits the blockquote line for a note-less highlight, so the
output stays clean. The clipboard + blob-download are the same proven wiring as the inc-70 citation copy/export
(works on the 127.0.0.1 secure context). No coordinate-honesty concern (the digest is text, not a page overlay).

## Manual verification

- **Logic:** `buildAnnotationDigest` verified deterministically via `node` (title, count, per-highlight quote +
  page, note-as-blockquote, empty-note-skips-blockquote).
- **Headed, no egress** (`.local/visual/drive_inc144_marks.py`): seeds a paper + a real 2-page PDF + 2 highlights
  (one noted), opens the viewer, opens the Notes panel → **Copy** + **Export .md** appear; clicking **Copy** puts
  the exact digest on the clipboard (read back + asserted). 0 console/page/genai.

## Triage of the remaining close-reader findings (filed to backlog)

Shipped: export/copy my marks (the biggest gap). **Remaining (close-reader pass):** keyboard zoom (Ctrl +/−) +
next/prev-mark hotkeys; a "noted-only" filter + a search box over note text in the panel; a "fit page" / fit-height
option + **remembered scroll position** per paper (re-open lands where you left off); free-form note color/labels;
a scrollbar/minimap marker for where highlights sit in a long PDF.

## Pytest

**524** unchanged (frontend-only; the pure digest logic is node-verified, the flow headed-verified). `ruff` clean;
build + assembly green; surface **106/106 API + 536/536 FE, 0 uncovered** (the 2 new buttons covered by
`route_32_viewer_annotations.md`). No new endpoint/migration/egress.

## Next (the slate)

- **Skeptical synthesizer ↔ multi-paper focus query (#7)** — the last of the slate (inc 145; needs egress to test live).
- **Then BYOK** (user-prioritized after the slate).
