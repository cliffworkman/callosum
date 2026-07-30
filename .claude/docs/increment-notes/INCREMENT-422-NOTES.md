# Increment 422 — desktop app icon: replace the invisible-on-light-backgrounds mark

## Implemented

Cliff: "the white only icon is invisible on many backgrounds -- this new version fixes the problem," pointing
at a new `.claude/media/logo_app.png` he'd dropped in. Confirmed the root cause by inspecting actual pixel
data rather than trusting a visual glance (an earlier look at both source PNGs in this same session had
mis-rendered their transparent backgrounds as solid black, which would have led to the wrong conclusion about
what changed): the inc-396 icon source (`.claude/media/logo_dm.png`) is a transparent PNG whose only content
is a **very light gray (220,220,220) line stroke** — exactly the "invisible on a light background" failure
mode described. The new `logo_app.png` (400×400 RGBA, also transparent-background) fills the brain/neuron
mark **solid black** with a white/light outline — visible against light backgrounds via the black fill *and*
against dark backgrounds via the white outline, not just one or the other.

Regenerated the full icon set exactly per the inc-396 precedent: `npx tauri icon
"<repo>/.claude/media/logo_app.png"` run from `app/desktop-shell` regenerated every file under
`src-tauri/icons/` (`32x32.png` through `icon.ico`/`icon.icns`, the Windows `Square*.png`/`StoreLogo.png`
tiles). The tool's own auto-generated `android/`/`ios/` subdirectories were deleted again (rule #5 — still a
desktop-only project, no mobile target ever added since inc 396 either).

## Key technical detail

No source-canvas "squaring" step was needed this time (unlike inc 396, where the original `logo_dm.png` was
348×303 and had to be composited onto a padded 1024×1024 square canvas first) — `logo_app.png` was already a
square 400×400 RGBA canvas, so it was passed to `npx tauri icon` directly. Visually spot-checked the
regenerated `icon.png` (full detail holds up, transparent corners preserved — confirmed via `PIL`
pixel-sampling that the source's corners are genuinely `(0,0,0,0)`, not opaque black) and `32x32.png` (detail
necessarily simplifies at that size, as expected for any icon, but the shape still reads clearly).

## Housekeeping

- Not a security-audit trigger (a static asset swap, no code/logic change).
- No pytest impact (desktop-shell-only, no Python/frontend touch).
- Folded into the still-untagged v0.3.5 (bundles inc 421's ACL fix + this icon fix) rather than a separate
  release — same precedent as v0.3.4's backlog-note commit riding along without its own version bump.

## Manual verification (owed until the next real install)

Once v0.3.5 installs: confirm the taskbar/window icon reads clearly against both a light and a dark Windows
taskbar theme (the specific failure mode reported) — this is the whole point of the change, and only really
confirmable by looking at the real installed app, not just the generated PNG files.
