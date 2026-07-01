# Increment 240 — Touch-native highlighting on mobile (the last B5 nicety)

The inc-239 mobile reader left one further-deferred piece: creating highlights *by touch* (the reader itself was
done). This builds it. Maintainer forks (AskUserQuestion): a **contextual pill** (reuse the existing picker near the
selection) + a **swatch row** (pick color as you create).

## The gap — mouseup doesn't fire on touch

Desktop highlighting: select text → `onPagesMouseUp` (bound to `.pdf-scroll`'s `onMouseUp`) reads
`window.getSelection()`, maps the client rects → bboxes, and shows the floating `.hl-picker` pill near the selection;
tapping a swatch calls `createHighlight(color)` → `POST /papers/{id}/annotations`; the "＋ note" action creates + opens
the editor. On a phone you *can* long-press-select text (that's a native gesture), but **`mouseup` never fires on
touch** — so the pill never appears. Everything downstream (bbox-mapping, the create endpoint, the note editor,
recolor) already works.

## The fix — a mobile selectionchange trigger (reuse everything)

One new hook, `useTouchSelectionPicker`, in `js/30f_pdf_gestures.jsx`:

```js
function useTouchSelectionPicker({ active, onSelection }) {
  useEffect(() => {
    if (!active) return;
    let timer = null;
    const onChange = () => { if (timer) clearTimeout(timer); timer = setTimeout(onSelection, 350); };
    document.addEventListener("selectionchange", onChange);
    return () => { document.removeEventListener("selectionchange", onChange); if (timer) clearTimeout(timer); };
  }, [active, onSelection]);
}
```

`PdfViewer` calls it: `useTouchSelectionPicker({ active: !!mobile && state.status === "ready", onSelection: onPagesMouseUp })`.

- **`selectionchange` is the touch analogue of `mouseup`** — it fires as the selection settles. Debounced 350ms so it
  waits until the user stops dragging the handles.
- **`onSelection` is the exact same `onPagesMouseUp`** the desktop mouseup path uses — it reads the current selection,
  builds the picker (or clears it if the selection collapsed). So the create/color/note flow is reused verbatim; there
  is no new create path.
- `onPagesMouseUp` is a stable `useCallback` (deps `[]`), so the once-attached listener never re-attaches.
- **Mobile-gated** (`active = mobile && ready`) — desktop keeps mouseup only, no double-fire.

Only CSS added: `.app.mobile` finger-sizes the picker — `.hl-swatch` 18→28px, roomier padding, a bigger `.hl-note-add`.

## Fits the inc-239 touch model

The inc-239 pinch listener only `preventDefault`s **two**-finger moves (single-finger, which drives selection, is
untouched), and `touch-action: pan-x pan-y` on `.pdf-scroll` governs pan/zoom — not text selection. So long-press
selection works alongside pan + pinch.

## Verification

**Frontend-only** — no Python touched → `HF_HUB_OFFLINE=1 python -m pytest -q` = **884 passed, 1 skipped** (unchanged;
`test_frontend_assembly` 5/5). `ruff` + `format` clean (no Python changed). **QA surface 173/173 API + 761/761 FE, 0
uncovered** — the picker + the new hook ride `route_32_viewer_annotations.md` (30f is already claimed there; no new API
surface, the create endpoint is unchanged). No audit/Principles trigger: a highlight is user-authored data (no
claim/signal), and coordinate honesty #2 is unchanged (the identical bbox-mapping).

**Headed-verified at 390×844, 0 console/page errors** (`.local/visual/drive_inc240_touchhighlight.py`): open the PDF →
create a text selection over a text-layer span via the DOM Selection API (which fires the **same** `selectionchange` a
long-press produces) → the `.hl-picker` appears with **5 color swatches + a ＋note action + 28px finger-sized swatches**
→ tap a swatch → **1 `POST /annotations` + the highlight renders** (`.pdf-user-highlight-group`) + the picker closes.

Note: real long-press → native selection isn't scriptable in Playwright, so the driver drives the identical
`selectionchange` → create path programmatically. The long-press *gesture* that produces the selection is the browser's
own and unchanged; what this increment adds — turning that selection into a picker — is exactly what the driver
exercises.

## B5 complete

This is the last B5 nicety. B5 (mobile reading) is fully complete with nothing deferred: SP1 responsive + read-only
tunnel (237) · SP2 read-only companion UI (238) · SP3 mobile reader (239) · touch highlighting (240). B1–B5 all done.
