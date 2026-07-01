// PDF reader gestures + navigation split from 30_viewer.jsx (inc 239, rule #1 — the pinch-zoom effect took it over
// the 600-line cap). `usePinchZoom` (a hook) + `MinimapTrack` (a leaf component) hoist in the shared IIFE, so
// PdfViewer (in 30_viewer, textually before) references them regardless of chunk load order.

// B5 (inc 239): pinch-to-zoom on touch. During the gesture we apply a cheap CSS transform to the pages container
// (no per-move re-render), then on release commit the final scale via onCommit (a crisp re-render through the
// inc-34 single-scale pipeline). A native listener with {passive:false} preventDefaults the 2-finger move so the
// browser doesn't also scroll/zoom mid-pinch (the scroller carries touch-action:pan-x pan-y on mobile). Active-only.
function usePinchZoom({ scrollRef, pagesRef, scaleRef, active, onCommit }) {
  useEffect(() => {
    const el = scrollRef.current;
    if (!active || !el) return;
    const dist = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
    let p = null;   // { startDist, startScale, target }
    const onStart = (e) => {
      if (e.touches.length === 2) p = { startDist: dist(e.touches), startScale: scaleRef.current, target: null };
    };
    const onMove = (e) => {
      if (!p || e.touches.length !== 2 || !pagesRef.current) return;
      e.preventDefault();
      const ratio = dist(e.touches) / p.startDist;
      const t = Math.min(3, Math.max(0.4, Math.round(p.startScale * ratio * 100) / 100));
      p.target = t;
      pagesRef.current.style.transformOrigin = "center top";
      pagesRef.current.style.transform = `scale(${t / p.startScale})`;
    };
    const onEnd = () => {
      const pp = p; p = null;
      if (pagesRef.current) pagesRef.current.style.transform = "";
      if (pp && pp.target != null && Math.abs(pp.target - pp.startScale) > 0.005) onCommit(pp.target);
    };
    el.addEventListener("touchstart", onStart, { passive: true });
    el.addEventListener("touchmove", onMove, { passive: false });
    el.addEventListener("touchend", onEnd, { passive: true });
    el.addEventListener("touchcancel", onEnd, { passive: true });
    return () => {
      el.removeEventListener("touchstart", onStart);
      el.removeEventListener("touchmove", onMove);
      el.removeEventListener("touchend", onEnd);
      el.removeEventListener("touchcancel", onEnd);
    };
  }, [active, onCommit]);
}

// inc 215: a thin scrollbar-side minimap — one tick per highlight at its page's vertical fraction; click to jump.
// Positioned by PAGE (numPages), not pixel offset, so it never touches the fragile render-core geometry (inc 34/35);
// the equal-page-height approximation is fine for a navigation aid. Shown when the Notes panel is closed (the panel
// already lists + jumps). Tinted by the highlight's own color.
function MinimapTrack({ annotations, numPages, onJump }) {
  if (!numPages) return null;
  return (
    <div className="pdf-minimap" title="Highlights — click a mark to jump to it">
      {annotations.map((a) => {
        const pct = Math.max(0, Math.min(100, ((a.page - 1 + 0.5) / numPages) * 100));
        const label = a.note ? `p.${a.page} — ${a.note}` : `Highlight on p.${a.page}`;
        return (
          <button key={a.id} className="pdf-minimap-tick" title={label}
                  style={{ top: pct + "%", background: a.color || "var(--flag)" }}
                  onClick={() => onJump(a)} />
        );
      })}
    </div>
  );
}
