# DESIGN.md — callosum design dictionary

The canonical reference for how callosum's UI looks. **Any change to `app/frontend/styles.css` (or inline
`style={{…}}` in `app/frontend/js/*.jsx`) MUST start with a read-through of this file** (CLAUDE.md rule).
The goal is to prevent design-by-committee drift as new controls land in an existing codebase: a new
button/input/badge conforms to a recipe here rather than inventing its own styling.

**Design intent (from `styles.css`):** *a quiet, dense reading instrument, not a landing page. Ink-on-paper
neutrals; one structural accent (deep indigo) reserved for provenance/verification — the thing that makes
Callosum Callosum. Type does the work: a humanist sans for chrome, a readable serif for paper titles.*

Two-pass document (per the user): **Pass 1** describes the CSS *as it is today*; **Pass 2** flags
inconsistencies and proposes canonical rules + consolidations. Pass-2 consolidations are a **worklist** —
apply them opportunistically or on request; new CSS should already follow the canonical rules. This is a
first attempt — expect iteration.

---

## 1. Tokens (the foundation — `:root` in `styles.css`)

**Use a token; never re-type a raw hex that a token already names.**

| Token | Value | Meaning / use |
|---|---|---|
| `--bg` | `#fbfaf7` | warm paper white — app background, inset inputs |
| `--panel` | `#ffffff` | raised surfaces (cards, modals, list) |
| `--panel-2` | `#f4f2ec` | sidebar / detail / inset surfaces |
| `--ink` | `#1c1b19` | primary text |
| `--ink-2` | `#55514a` | secondary text |
| `--ink-3` | `#8a8479` | tertiary / metadata / placeholders |
| `--line` | `#e6e2d8` | hairline rules / dividers |
| `--line-2` | `#d8d3c6` | control borders (inputs, buttons) |
| `--accent` | `#2f2a6b` | **deep indigo — provenance/verification + primary actions ONLY** |
| `--accent-soft` | `#ecebf5` | accent backgrounds (active chips, soft panels) |
| `--verified` / `--verified-soft` | `#2f6b45` / `#e6f0e9` | grounded/verified (green) |
| `--flag` / `--flag-soft` | `#9a5b2e` / `#f4ebe2` | **unresolved / region / uncertain (amber-brown)** — a *status*, not "delete" |
| `--sel` | `#eef1fb` | selected row background |
| `--hover` | `#ece9e0` | row / card hover (inc 46) |
| `--accent-line` | `#dad8ee` | border partner for `--accent-soft` |
| `--flag-line` / `--flag-ink` | `#e6cdb4` / `#6e4421` | border + text partners for `--flag-soft` |
| `--danger` / `--danger-line` | `#b3261e` / `#e3b1ac` | **destructive actions** (delete) — distinct from `--flag` (status) |
| `--accent-overlay` | `#5c55b0` | on-page indigo (PDF highlight/synthesis) — **constant across themes** (white page) |
| `--on-fill` | `#ffffff` | text on a filled semantic color (primary button, status badge) — **flips in dark** |
| `--radius` | `7px` | default corner radius |
| `--radius-sm` / `--radius-lg` / `--radius-pill` | `5px` / `12px` / `999px` | radius scale (inc 53): small controls / modals / pills (DESIGN.md §3 #6) |
| `--mono` / `--sans` / `--serif` | (stacks) | mono = metadata/numbers; sans = chrome; serif = paper titles, summary sentences, quotes |

Type roles: **serif** (`--serif`) = paper/summary/quote titles (reads like a bibliography); **sans** =
all chrome/controls; **mono** = confidences, counts, IDs, status, timestamps.

---

## 1b. Dark theme (inc 46)

**Mechanism:** `:root` holds the light tokens; **`:root[data-theme="dark"]`** overrides their *values*
for a warm-dark palette. Nothing else changes — every chrome color flows through a token, so the override
cascades. `data-theme` is set on `<html>` by a **no-flash bootstrap** `<script>` in `index.html`'s `<head>`
(reads `localStorage["callosum.theme"]`, else `prefers-color-scheme`); the Settings modal toggle writes the
same attribute + storage.

**Rules that make dark mode work — follow them for any new CSS:**
- **Every chrome color is a token.** Never inline a raw hex for chrome; if dark needs a different value,
  it must be a token overridden in the dark block.
- **The rendered PDF page stays light in BOTH themes.** `.pdf-page*` `#fff`, the on-page highlight rgba
  (`.pdf-highlight`, `.textLayer ::selection`), and `--accent-overlay` are intentionally *not* themed —
  they sit on the white document. Only app *chrome* (toolbar, scroll backdrop, annotation panel) themes.
- **Text on filled semantic colors uses `--on-fill`,** not `#fff` — because the fills (`--accent`,
  `--verified`, `--flag`, `--danger`) become *light* pastels in dark, so the text must flip to dark.
- **Theme-matched / status assets swap via CSS, not JS, with the base64 in CSS vars (NOT the Babel
  script).** The brand logo is a `<div className="brand-logo">` whose `background-image` is a `--logo-*`
  token picked by `[data-theme]` × a `.connected` class — **4 states** (light/dark × off/on; the "on"
  variant adds the green **connection** dot, so the logo encodes connection status; see inc 47). Four
  logos in the Babel script would blow its 500KB deopt cap, so they live in CSS `:root` vars filled by
  `inline_brand_assets.py`. Keep inlined PNGs **small** (~57KB; recompress oversized exports losslessly).

The dark palette values live in `styles.css` `:root[data-theme="dark"]` (warm-dark; user-tunable).

## 2. Element recipes (Pass 1 — canonical "this is how X looks")

### Surfaces
- **Panel/card:** `--panel` bg, `1px var(--line)` border, `var(--radius)`. Inset/sidebar surfaces use
  `--panel-2`. Modals: `--panel`, `1px var(--line-2)`, radius 12px, shadow `0 14px 48px rgba(0,0,0,.32)`,
  over a `rgba(20,16,12,.42)` overlay.
- **Settings groups (`.settings-card`):** the canonical panel/card recipe above, arranged as one full-width
  stack. Related subsections share an unframed two- or three-column `.settings-sections-grid` inside the card
  (never cards inside cards) and collapse to one column on mobile. The provider roster is the inset-card exception:
  four always-open built-ins in an equal-size 2×2 desktop grid; custom providers continue in two-column,
  natural-height rows below; mobile uses one column with natural heights. Peer AI permission controls use one
  unframed three-column `.settings-ai-controls` row and stack on mobile; each description spans through its toggle
  column. The two Axes defaults likewise share a full-width two-column row, with each feature name using the standard
  eyebrow treatment and each description below its heading/control row. Library access and Local maintenance form
  the next row; Discover: Journals spans both columns
  and divides its two preferences between them. Watched-folder launch/focus scanning is standard behavior, not a
  user-facing preference. Repeated identity values such as published-name variants reuse
  the established removable `.tag-chip` recipe. Credit-the-lineage actions, including the OpenURL source in Library
  access, use `MethodCreditButton` so DOI presence, import progress, completion state, and read-only behavior agree.
  Metadata access belongs in the account column below identity/publication metadata, not in Library behavior.
  Provider copy spans the card content width and names the endpoint for built-in and custom providers; the active
  provider's model and connection-test controls share a row. Integration columns put their primary full-width action
  immediately below the eyebrow, followed by explanatory copy with inline secondary download links.
- **Focus ring (inputs):** `outline: 2px solid var(--accent-soft); border-color: var(--accent);` — applied
  consistently on `.axis-input`, `.searchbar input`, `.synth-input`. **This is the canonical focus state.**

### Text inputs
Border `1px var(--line-2)`, `var(--radius)`, `--sans`, color `--ink`, + the focus ring above. Background is
`--panel` for inputs on inset surfaces, `--bg` for inputs on white. Textareas add `resize: vertical` +
`min-height`.

**Inline-editable variant (`.detail-edit`, inc 49 — the Details pane):** an always-editable field that
*reads as text* until interacted with — `border: 1px solid transparent` + transparent bg by default;
**hover** → `border-color: var(--line-2)`; **focus** → the canonical ring (`outline 2px var(--accent-soft);
border-color var(--accent)`) + `background: var(--panel)`. Empty shows the grey `--ink-3` italic
placeholder ("Add …"). Same recipe at title scale via `.detail-title-input` (serif 18px). Use this when a
whole pane is directly editable (no view/edit toggle) so static metadata and its editor look identical.

### Buttons — canonical `.btn-*` classes (inc 68)
There are now **canonical button classes** in `styles.css` (one definition per variant); the historical
ad-hoc class names are **grouped into** those rules so the recipe isn't re-typed. **New buttons use
`.btn` + a variant** (`.btn-primary` / `.btn-ghost` / `.btn-link` / `.btn-icon`) + optional `.danger`.
- **`.btn-primary` (filled):** `var(--accent)` bg + border, `--on-fill` text, `var(--radius)`, weight 600.
  (grouped: `.axis-btn`, `.synth-actions button` [keeps a larger-padding delta]. **`.hl-editor-actions`
  Delete/Cancel/Save migrated to `.btn-ghost`/`.btn-primary`/`.danger` — inc 113.**)
- **`.btn-ghost` (outline/secondary):** `var(--bg)` bg, `1px var(--line-2)` border, `--ink-2` text,
  `var(--radius)`; hover → `border-color/color: var(--accent)`. (grouped: `.pginate button`. `.btn-ghost.danger`
  = a red destructive ghost. **Kept as intentional compact variants (inc 86, §3 #5):** `.axis-sort` (tiny inline
  `<select>`), `.pdf-zoom button` (fixed 24×24 squares), `.source-jump` (indigo = provenance/citation jump),
  `.history-delete` (compact; delete-hover now red) — distinct by design, so NOT folded; radii `--radius-sm`.)
- **`.btn-link`:** no border/bg, `--accent` text, hover underline; disabled → `--ink-3`. (grouped:
  `.axis-link`.) `.btn-link.danger` **and** `.axis-link.axis-danger` are both red `--danger` (inc 113 — DESIGN §4;
  axis-delete was amber, now red).
- **`.btn-icon`:** `1px transparent` border, transparent bg, `--ink-3`, `--radius-sm`; hover → `--accent`
  + faint `--line-2` border + `--panel` bg. (grouped: `.axis-icon-btn`; its `.axis-icon-danger` delete-hover is
  now red `--danger`, inc 113. **`.axis-icon-btn` carries an AMBIENT outline at rest** (`border-color: currentColor`
  — the icon's own color, so the outline is always visible; hover then swaps the *color* to accent rather than
  revealing the outline — inc 116, mirroring the inc-104 gear/help treatment). **Kept as intentional variants
  (inc 86):** `.axis-x`, `.frame-tab-close` — borderless symbol-× *remove-from-view* closes; their **amber** hover
  is deliberate (remove ≠ destroy, inc 113).)
- **Add/create buttons are GREEN (`--verified`)** — a deliberate affordance so an "add" action reads as distinct
  from neutral/primary controls (e.g. `.axis-new` "+", ruled inc 113). Green therefore has **two** roles:
  *verified/grounded* (status) and *add-action* (affordance). New add buttons use green. *(Open: the library
  "+ Add ▾" menu is not yet green — see §3 worklist #1.)*
- **`.danger` modifier:** red `--danger` text (+ `--danger-line` border for icon hover). The canonical
  destructive color (DESIGN §4); use it on new destructive buttons.
- **Disabled (all):** `opacity:.45` (ghost uses `.4`) + `--line-2` bg/border + `--ink-3` text; `cursor:default`.
- **`.method-credit` lineage buttons:** use the shared `MethodCreditButton` helper and the existing `.btn-link`
  recipe. Label is **"＋ add missing to library"** while any DOI-backed credited source is absent, and
  **"✓ added to library"** once all DOI-backed sources are present. Multi-source credits import only missing items.

### Pills / badges (mono, uppercase, soft-bg + matching ink)
Recipe: `--mono`, ~10px, `text-transform:uppercase`, `letter-spacing:.04em`, padded `2px 7px`, pill
radius. Semantic color **pairs**: verified → `--verified-soft`/`--verified`; flag/uncertain/region →
`--flag-soft`/`--flag`; neutral → `--line`/`--ink-2`; accent/manual → `--accent-soft`/`--accent`.
(`.tier*`, `.axis-tier*`, `.sent-badge/.cite-status/.coord`, `.needs-doi`, `.chip`.)
**Narrow exceptions:** red `--danger` is permitted only on the strongest negative **evidence-backed status** pills:
`.cite-status.contradicted` (inc 203, A9) for a cited source that *actively disagrees* with the claim, and
`.tier-retracted` (inc 292) for a registry-recorded retraction. Both use `--danger-line`/`--danger`, are
**non-interactive** status pills, and must remain evidence prompts — not author accusations, scores, or destructive
actions. Don't extend red to weaker statuses.

### Chips (interactive, rounded-pill, toggle)
`--term-chip`: dashed `--line-2` border + `--panel` bg when off; solid `--accent` border + `--accent-soft`
bg + `--accent` text when **on**. Radius 999px.

### Library-header chip grouping — signals vs review-queue (statcheck #e)
The library-header filter chips are grouped by **KIND** into two `.lib-chip-group` clusters divided by a thin
`--line` rule: **signals** (`.lib-chip-signals` — a check *detected* something concrete: statcheck `⚠ flagged` amber
`--flag`, retraction `⚠ retracted` red `--danger`) vs **your review queue** (`.lib-chip-queue` — go-look *work-state*,
indigo `--accent`: findings `📋 to review`, transparency `🔎 open data not detected`). The colors already carry the
signal-vs-work-state semantics (amber/red = signal, indigo = queue); the grouping makes the distinction read at a
glance so `flagged` isn't conflated with `to review`. **`open data not detected` stays in the *queue* group, never
*signals*** — it is deliberately a go-look, *not* a detection/verdict (the A-A no-accusation boundary: never a "hides
data" claim). New header chips join the group whose color they carry.

### Drop-target invite (drag-and-drop, inc 206)
A valid drag-over target shows a **dashed `--accent` border + `--accent-soft` fill** (`.axis.drag-over`) — dashed =
*transient/pending* (the drop hasn't happened), accent = the pane's primary color. Distinct from the solid-`--accent-line`
`.active` state. Reuse this recipe for any future drag-to-add affordance.

### Tag colors (inc 207, A5)
**Non-semantic** user labels (distinct from the indigo/green/amber/red status colors — these are organizational, the
user's choice). A fixed 8-key palette (`--tag-red … --tag-gray`), one **ink** token per key (light in `:root`,
lighter overrides in the dark block so it reads on the dark soft-bg). The colored chip recipe sets `--tag-c` via
`.tag-color-<key>` and mixes it with `--panel` for a theme-aware soft fill: `.tag-chip.tag-colored { background:
color-mix(in srgb, var(--tag-c) 16%, var(--panel)); … }`. A colored chip **overrides** the inc-100 provenance styling
(an uncolored tag keeps it). **No rating/score color** — ratings were deliberately declined (a star reduces a paper to
one dimension; tags stay orthogonal). Reuse `--tag-c` + `color-mix` for any future per-entity color.

### Full-text search results (inc 209, A3)
The full-text hit list **reuses the `.cite-card` / `.quote` / `.cite-title` / `.cite-meta` / `.cite-card-foot`
recipe** (inc 156) — a hit is just another evidence card. New only: `.ft-mark` = the matched term, rendered **bold in
`--accent`** (search = the provenance/primary color), and the quiet `.fulltext-hint` / `.fulltext-meta` / `.ft-page`
mono-meta lines. Reuse `.ft-mark` for any future search-match highlight.

### PDF highlight minimap (inc 215)
A thin `.pdf-minimap` gutter (`flex: 0 0 14px`, `--panel-2` bg, `--line` left border) beside the page scroller,
shown only when the Notes panel is closed. Each highlight is a `.pdf-minimap-tick` — absolutely positioned by
**page fraction** (`top: ((page-1+0.5)/numPages)%`), tinted by the highlight's own color (fallback `--flag`),
`var(--radius-sm)` corners, `--accent` hover outline. Tokens only; no raw hex. It's a navigation aid (page-level,
not pixel), so it never touches the inc-34/35 render-core geometry.

### Status / provenance accents
Connection LED, synthesis "running" pulse, the provenance box (`.prov`: `--accent-soft` bg + accent border
+ accent bold) — indigo = provenance. Verified green / flagged amber on summary sentences (left border 3px).

**Status-by-color, not by text (a deliberate pattern — keep UI dense, status in the affordance):** the
**axis count badge** (`.axis-count-badge`) encodes *scoring status* in its **background color** — muted
`--line-2` (not scored), `--verified` green (scored & fresh), `--flag` amber (`.is-stale`, edited →
re-score) — with the status in its `title` tooltip. There is **no separate status text line** (the old
`.axis-state` "scored / re-score / not scored yet" strings were removed). White text on the green/amber
states. Prefer this pattern (color + tooltip on an existing element) over a dedicated text line when space
is at a premium.

**Axis-kind cue (A7, inc 211) — a small icon, never a "folder" label.** A *curated* axis (hand-picked,
hand-ordered; `kind="curated"`) is distinguished by a **📌 prefix on the label** (the established cue
pattern — My-Pubs uses 📄), plus `.axis-count-badge.is-curated` = a **quiet `--accent-soft` tint** (a
deliberate hand-built set — distinct from the neutral unscored grey and the green-scored / amber-stale of a
keyword axis; it has no scoring state). Members reorder by **dragging the ⠿ grip** (`.axis-grip`; inc 212 — each
`.axis-member-drag` row is an HTML5 drag source + drop target; `.dragover` = an inset top `--accent` line). The
cue is deliberately *subtle* (per §A7); the curated axis is the umbrella "Axis", never a "folder".

### Hover (rows/cards)
List rows + cards darken to a warm neutral on hover (`.axis:hover`, `.cluster:hover`, `.frame-tab:hover`,
`.history-row:hover` → `#ece9e0`; `.paper:hover` → `#faf8f3` — *two different hovers, see Pass-2*).

### Feedback — long async ops get a progress bar (a standing rule)
**Any user-triggered async operation that can take more than ~1s shows the indeterminate `ProgressBar`** while
it is pending — never a frozen-looking idle control. The shared component is `<ProgressBar />` (an indeterminate
sliding `.progress-bar`/`.progress-bar-fill`); render it gated on the pane's `busy`/`running` flag. Already on:
summary generation (`.synth` busy), axis score / axis suggest / dedup scan / statcheck-all, library scan / import /
wanted re-check (the async-job modals). When you add a new async job (a `JobStore[R]` subsystem or any
poll-until-done call), wire its pending state to `ProgressBar` too. (Convention named inc 116 / TDL #45; the
component itself predates it.)

---

## B5 read-only companion (inc 237/238)

- **`.read-only-badge`** — a fixed top-right pill marking a read-only instance (`--flag-*` family, `--radius-pill`;
  `pointer-events: none`). Shown when the app detects `/health.read_only` (the mobile read-only tunnel). Tokens only.
- **`.detail-ro`** — a Details field rendered as **static text** (no input chrome) on a read-only companion; `.mono`
  variant for identifiers; the `.detail-title-input.detail-ro` variant for the title. Reuses `--ink`.
- **`.mobile-nav` / `.app.mobile`** (inc 237) — the phone-width single-column layout + bottom nav; `100dvh`, tokens.
- **Pattern:** a read-only companion **hides** write controls (via a `readOnly` flag threaded through the panels +
  a `DetailReadOnly` React context for the Details fields) and **never fires a write on load** — the on-launch rescan
  + the CiteRow render only run when read-write is confirmed. The enforcement is the server method gate, not the UI.
- **`.pdf-back-pill`** (inc 239) — a fixed "← Synthesis" pill floating above the bottom nav on the mobile reader after
  a citation jump; `--accent` fill + `--on-fill` + `--radius-pill`, `z-index: 55` (below the read-only badge's 60).
- **Mobile reader (inc 239):** on a phone the PDF **defaults to fit-width** (`pageView="width"`; Two-up hidden) and
  **pinch-to-zoom** drives the scale — `.pdf-scroll` gets `touch-action: pan-x pan-y` (mobile) so single-finger pan
  works but the browser's own pinch-zoom is off; the gesture applies a CSS `transform` to `.pdf-pages` then commits a
  crisp re-render on release. Desktop is untouched (the `mobile` branch never runs >760px).
- **Touch highlighting (inc 240):** the existing `.hl-picker` pill is finger-sized on a phone — `.app.mobile .hl-swatch`
  is 28px (vs 18px), with roomier padding + a bigger `.hl-note-add`. Triggered by a mobile-only `selectionchange` hook
  (the touch analogue of desktop's mouseup); no new UI, just the same picker reached by touch.

## 3. Consistency findings + proposed consolidations (Pass 2 — a worklist)

> **Status (inc 46):** the **color-token** consolidations below (#1 split destructive → `--danger`, #2
> overlay indigo → `--accent-overlay`, #3 border/ink partners → `--accent-line`/`--flag-line`/`--flag-ink`,
> #4 unified `--hover`) are **DONE** — those tokens now exist and the scattered hex was replaced (this was
> the dark-mode groundwork). **Remaining:** #5 the `.btn-*` class DRY and #6 the radius scale.

Ranked; "legit" = a context difference worth keeping.

1. **Destructive color split — RESOLVED (inc 113; the `--danger` token has existed since inc 46).** Genuinely
   **destructive** (data-deleting) actions now use red `--danger` (#b3261e) + `--danger-line`:
   `.axis-link.axis-danger` (delete axis), `.axis-icon-danger` (axis delete-icon), `.history-delete` (delete a
   saved synthesis), plus the highlight/summary deletes that were already red. **Deliberate distinction kept:**
   *remove-from-view* ×-closes — `.axis-x` (pull a paper off an axis) and `.frame-tab-close` (close a tab) —
   **stay amber `--flag`**: they dismiss, they don't destroy data. So `--flag` = status + remove-from-view, red
   = data-delete. (The `.axis-count-badge` is **no longer a fixed color** — it now
   encodes scoring status (green `--verified` / amber `--flag` / neutral `--line-2`; see §2), which retired
   the earlier "is the badge red or amber?" question; it uses `--flag` only for the *stale* state.)
2. **The indigo is three colors.** `--accent #2f2a6b` (chrome/provenance), an **overlay indigo
   `#5c55b0`/`rgba(92,85,176,…)`** (PDF highlight, text selection, synthesis outline, `.source-*` hovers),
   and `#b9b6dd` (manual-tier dashed border). The overlay indigo is arguably **legit** (a brighter indigo
   reads better as a translucent overlay on the page than the dark `--accent`), but it's a raw hex repeated
   ~6×. **Proposal:** add **`--accent-overlay: #5c55b0`** (document it as the on-page highlight indigo);
   make `#b9b6dd` a token or reference `--accent-soft`.
3. **Off-token border hexes that pair with soft backgrounds.** `#dad8ee` (the border for `--accent-soft`
   surfaces: `.axis.active`, `.axis-bulk-bar`, `.pane-tabs .active`, `.prov`) and `#e6cdb4` (border for
   `--flag-soft`: `.axis-err`, `.errbox`) and `#6e4421` (the ink for `--flag-soft` error text). **Proposal:**
   `--accent-line: #dad8ee`, `--flag-line: #e6cdb4`, `--flag-ink: #6e4421`. (Every soft bg should have a
   named line + ink partner.)
4. **Two hover backgrounds.** Rows/cards use `#ece9e0`, but `.paper:hover` uses `#faf8f3`. **Proposal:**
   one `--hover: #ece9e0` token; treat `.paper:hover` as either the same or a documented exception.
5. **~10 near-duplicate button blocks.** **PARTIAL (inc 68):** the canonical `.btn` / `.btn-primary` /
   `.btn-ghost` / `.btn-link` / `.btn-icon` + `.danger` classes now exist (see §2), and the cleanly-identical
   duplicates were consolidated by grouping their ad-hoc selectors into the canonical rules — **no re-typing,
   no visual change** (every grouped property was byte-identical): primary (`.axis-btn` + `.synth-actions
   button`), ghost (`.pginate button`), link (`.axis-link`), icon (`.axis-icon-btn`). **Remaining:** the
   size-/color-divergent ghost & icon buttons (`.axis-sort`, `.axis-new`, `.pdf-zoom button`, `.source-jump`,
   `.history-delete`, `.hl-editor-actions button`, `.axis-x`, `.frame-tab-close`). **RESOLVED (inc 86) —
   folding declined, deliberately.** On review these are **not near-duplicates**: each is an *intentional
   distinct variant* — a tiny inline `<select>` in a no-wrap controls row (`.axis-sort`), compact toolbar
   controls (`.pdf-zoom`), a green "+" (`.axis-new`, color `--verified`), borderless symbol-× closes with a
   flag hover (`.axis-x`, `.frame-tab-close`), small special-hover deletes/jumps (`.history-delete` flag,
   `.source-jump` accent-bg). Forcing them into the full-size `.btn-ghost`/`.btn-icon` recipe would **enlarge
   them + change their hovers** — a *value-shift*, contra the "consolidate, don't redesign" intent — and yields
   ~no DRY (they share almost nothing with the canonical base). So they are **kept as documented intentional
   exceptions**; the only safe unification applied was tokenizing their radii (see #6). New buttons still use
   `.btn-*`; these compact variants stay bespoke by design.
6. **Radius is semi-tokenized.** **PARTIAL (inc 53; inc 86):** the scale exists — `--radius-sm:5px`,
   `--radius:7px`, `--radius-lg:12px`, `--radius-pill:999px`; the clean pill/modal values migrated (inc 53),
   and **inc 86 tokenized every hardcoded `5px` → `var(--radius-sm)`** across `styles.css` (the dominant
   messy-middle value; zero visual change since `--radius-sm` *is* 5px). **Remaining:** the rarer `4/6/8/9px`
   radii are still hardcoded — consolidate opportunistically (each is a small value-shift, so not bundled).
7. **One-off backgrounds (mostly legit):** toast `#43210f`/`#ffe9dc`, flagged-sentence `#fffaf6`,
   `.axis-preview #f1efe7`, `.pdf-scroll #eceae3`, skeleton gradient. Keep as documented one-offs, but pull
   any that recur into tokens.
8. **`.credit-role-label` re-types the `.term-chip` off/on recipe (inc 261, CRediTer).** The CRediT builder's
   role chips need the same dashed-off / solid-`--accent`-on look as `.term-chip`, but with the right-hand corners
   **squared** so an optional degree `<select>` (`.credit-degree`) can fuse flush to the chip's right edge. It
   therefore duplicates the recipe (tokens only — no new hex) instead of reusing the class. **Legit, minor:** a
   real visual difference (fused pill vs. standalone pill). **Proposal (opportunistic):** if a third fused-control
   chip ever appears, extract a shared `.chip`/`.chip.on` base and let `.term-chip` + `.credit-role-label` add only
   their corner/border deltas. Not worth a refactor for two sites.
9. **Settings group cards — RESOLVED (2026-07-20).** The settings redesign needed a named grouping wrapper, but
   not a new surface language: `.settings-card` uses the canonical panel/card tokens exactly, while its subsection
   grids remain unframed. The pattern and its responsive/provider-grid rules are documented in §2 above.
10. **Missing content padding on 6 workspace tabs — RESOLVED (2026-07-20).** `.workspace-body` is deliberately
    unpadded (a full-bleed list tab like Discover Feed/Search wants edge-to-edge rows), so a content-style tab must
    supply its own — `.wb-pane` (Work → Meta-Analyze) and `.synth` (Synthesize → Ask) already did; Work → Cite/
    Meta-Reference/CRediT, Discover → Journals/Funding, and Synthesize → Critique didn't (`.cite-pane` had no base
    rule at all — only an incomplete mobile-only patch; `.cite-workspace`/`.statcheck-section` used by Critique had
    no rule at all; `.grim-section` used by CRediT had none either). Fixed with one new standalone class,
    `.ws-pad { padding: 16px 18px }` (the `.wb-pane`/`.synth` rhythm), added alongside each broken component's
    existing root class. Kept standalone rather than folded into `.grim-section`/`.statcheck-section` directly,
    because those two are *also* legitimately used inside already-padded contexts — a METHODS accordion `.acc-body`
    (GRIM/statcheck/Bayes/LMM/transparency/meta-analysis-reporting), and `EffectSizeSection`'s `.grim-section`
    nested inside Workbench's already-padded `.wb-pane` — where adding padding to the bare class would double it.

---

## 4. Rules for new CSS

1. **Read this file first.** (Enforced by the CLAUDE.md rule.)
2. **Reference tokens, never re-type a named hex.** Need a color that isn't a token? Add a token here in
   the same change and explain it — don't inline a raw hex.
3. **Reuse a recipe.** A new button/input/pill/card should match §2. If it genuinely needs to differ,
   say why (a documented context exception) rather than drifting silently.
4. **Semantics of color are fixed:** indigo `--accent` = provenance/verification + primary action; green
   `--verified` = affirmative — grounded/verified, **connection-OK (the logo dot), and the "go"/create
   affordance (the new-axis "+")**; amber `--flag` = unresolved/uncertain/region (a *status*); red
   `--danger` = destructive. Don't borrow one for another.
5. **Type roles are fixed:** serif for paper/summary/quote text; sans for chrome; mono for
   numbers/IDs/status.
6. When a change reveals a new inconsistency, **add it to §3** so the dictionary stays the source of truth.

---

## 5. Navigation architecture — workspaces + per-paper lenses

Callosum has **two navigation dimensions**. Place new tools by the user's **cognitive task**, not by implementation
detail, data source, or whether AI is involved.

1. **Center workspaces are modes of work**: what the user is doing now. The center menu switches between **My
   Publications / Library / Synthesize / Discover / Work / Extract**, plus **Help / Settings** utilities. A tool
   belongs in a workspace when the user enters a broad mode, compares many papers, searches beyond the selected PDF,
   writes, cites, extracts datasets, or needs center-width output.
2. **Side panes are selected-paper lenses**: what the user is inspecting about the current paper while the center
   mode stays available. A tool belongs in a side accordion when it is compact, paper-scoped, and useful as persistent
   context beside the reader.

Use this placement question first: **is this a mode the user enters, or a lens on the current paper?** If the tool
creates a workbench, produces broad output, or coordinates multiple papers, it is a workspace or workspace tab. If it
only labels, inspects, or verifies the selected paper, it can stay in a side accordion section or tab.

The current center workspace map is:

- **My Publications**: the user's publication dashboard.
- **Library**: the reading surface, library list, selected-paper tab, and open PDF tabs.
- **Synthesize**: Ask for verified corpus answers and Critique for a wide single-paper critical read.
- **Discover**: Feed, Search, Wanted, Gaps, Overlooked, Journals, and Funding.
- **Work**: Cite (Suggest, Meta Reference List, Citation Concentration, How it's cited) and CRediT statement.
- **Extract**: Workbench, Effect-Size, and Meta-Analysis.
- **Help / Settings**: utilities, right-aligned on desktop and grouped as Utilities on mobile.

The internal pane ids `theory` and `methods` remain implementation vocabulary for the left and right side panes. They
are **not** a reason to place new broad features in side accordions. The left side pane holds compact
literature-context lenses such as Axes, Tags, Reading queue, and Review/findings. The right side pane holds compact
paper-evaluation lenses such as Details, GRIM, Statistics check, transparency, and related methods checks. Single-paper
Critical Read lives in **Synthesize → Critique** because it is a wide scrutiny workflow, not a compact side lens.

**Workspace registry and menu-bar recipe.** The center menu bar is data-driven by
`app/frontend/js/04b_workspaces.jsx`: `registerWorkspace`, `registerWorkspaceTab`, `workspaces`,
`workspaceTabs`, `getWorkspace`, `<MenuBar/>`, and `<WorkspacePane/>`. A workspace can be shell-rendered by `40_app`
(Library, My Publications, Help, Settings) or populated by registered tabs (Synthesize, Discover, Work, Extract). Host
metadata is order-sorted and idempotent by id; read-only companions hide workspaces or tabs marked `hideInReadOnly`.
The menu bar lives
**inside** the center pane, not app-wide, so the three-pane layout stays separate and full height. Token recipe:
`.menubar` is a `flex:0 0 auto` bar at the top of `.workspace-frame`, with `--panel-2` background and `--line`
border; `.menubar-item.active` uses the established active accent semantics (`--accent-soft`, `--accent-line`,
`--accent`). Workspace sub-tabs reuse the existing `.tags-srcfilter` segmented strip via `.workspace-tabs`; bodies
use `.workspace-body pane-tab` so inactive tabs stay mounted but hidden (`.pane-tab:not(.active){display:none}`).
The active workspace persists at `callosum.workspace`, and each workspace tab persists at
`callosum.workspacetab.<workspaceId>`.

On phone-width screens (inc 302), that same center-pane menu bar renders as a compact **Workspace** `<select>`
instead of the desktop horizontal tab strip. It switches the same visible workspaces/utilities and stays separate
from the bottom `.mobile-nav`, which only chooses the visible region: Library / Panels / Details.

**Library PDF tab recipe (inc 290).** Inside the Library workspace, the tab strip order is fixed as: **Library**,
then the optional selected-paper tab, then open PDF tabs. The selected-paper tab is a transient "selected, not
opened" affordance: dashed `--accent` border + `--accent-soft` fill (same pending/drop-target semantics as §4), no
close button, not draggable, and clicking it calls the normal PDF-open path. Open PDF tabs are draggable among
themselves only; drag-over uses the same dashed `--accent` + `--accent-soft` invite. When the selected paper already
has an open PDF tab, the selected-paper tab is hidden.

**Discover selected-paper cue (inc 291).** Discover → Journals and Discover → Funding show the selected/open paper
context before the Discover sub-tabs by reusing the Library tab vocabulary: selected-but-not-open uses
`.frame-tab.frame-tab-selected`; selected-and-open uses `.frame-tab.active`. This cue is a bridge back to the reader
(open the selected PDF or return to its open reader tab), not a new Discover sub-tab style. Feed and Search do not
show the cue; Feed stays focused on followed-source triage, and Search stays focused on corpus search.

**Discover recent-query recall (inc 299).** Discover → Search and Discover → Journals keep small browser-local
recent lists in `localStorage`. Recall controls re-run the stored input with fresh provider results; they do not
replay cached rows. Search also has a **Clear ×** control for the active query/results. These controls reuse
`.lib-sort` and `.btn.btn-primary`, so they stay visually in the existing search/action row vocabulary.

**Accordion registry and lens recipe.** The side panes are accordions on the module registry in
`app/frontend/js/05_panes.jsx`: `registerPaneSection({id, label, paneId, order, render})`,
`registerPaneTab(host, tab)`, `paneSections`, `sectionTabs`, and
`<PaneAccordion paneId ctx openId onOpen/>`. Sections are **data**, not hard-coded markup: a new lens is one
registration call in its own chunk, `order` controls display position, and `PaneAccordion` does not need to change.
The visible chrome still shows section headers only — no large "THEORY" or "METHODS" umbrella label — while
`paneId: "theory"` and `paneId: "methods"` remain the internal architecture. One section is open per pane, and the
open sections persist as `callosum.theoryOpen` / `callosum.methodsOpen`.

**Side-pane ordering.** The left side pane is for compact selected-paper literature lenses: Axes and Tags are grouped
together because they are conceptual labeling lenses; Queue and Review/findings stay as paper-context surfaces. The
right side pane is for *evaluating how a paper was studied*, ordered by cognitive task: Details (`order: 10`) → Data
consistency / GRIM (`order: 20`, raw data check before analysis check) → Statistics check (`order: 30`, statcheck and
related tests) → Review (`order: 40`, findings) → other methods checks. Future statistical checks become tabs inside
**Statistics check**, not sibling sections. Future paper-evaluation modules follow the right-pane order; future
literature-understanding lenses follow the left-pane order. Larger corpus synthesis and writing/citation authoring
belong in center workspaces.

**Tabs within a section or workspace.** Tabs are for like-with-like variants inside one broad task. In side panes,
`registerPaneTab({id,label,paneId,order}, {id,label,order,render})` adds a tab to a find-or-created host section, and
`registerPaneSection({…, render})` is the one-tab shorthand. In workspaces, `registerWorkspaceTab` does the same for
workspace modes. Work → Cite has one nested tab registry (`registerCiteTab`) for citation-authoring variants where
Meta Reference List belongs after Suggest and before Citation Concentration. All tab systems reuse `.tags-srcfilter`
plus `.tags-srcfilter-btn`; side-pane tabs use `.pane-tabs`, workspace tabs use `.workspace-tabs`, and both
mount-but-hide bodies through `.pane-tab`. Side-pane active tabs persist as `callosum.panetab.<sectionId>`. Per-tab
`hideInReadOnly` is allowed; on a read-only companion
a section or workspace is hidden only when it is explicitly `hideInReadOnly` or every contained tab is hidden.
Section-definer and workspace-definer metadata is authoritative regardless of chunk-load order, so a tab-adding chunk
that loads first only seeds a placeholder. Note the esbuild gotcha: a registered-but-unreferenced component can be
dead-code-eliminated from the build until a consumer references it, so wire the consumer in the same change.

**Accordion pane layout (inc 248) — headers always visible.** The two accordion panes (`.pane-sidebar`,
`.pane-detail`) are `display:flex; flex-direction:column; overflow:hidden`; they do not scroll as whole panes. The
center `.pane-list` keeps normal scrolling. `.pane-accordion` is `flex:1; min-height:0`; a collapsed `.acc-section`
is `flex:0 0 auto`, and the open section is `flex:0 1 auto`: natural height when short, shrinkable when full. Then
`.acc-section.open .acc-body{overflow-y:auto}` scrolls only the body, so a long Details section never buries the
other headers. `.acc-body` uses `padding: 2px 14px 14px` to align with the header spacing; Details'
`.detail-edit-pane` keeps vertical-only inline padding to avoid doubling. All values are existing token/px recipes.

**"Coming soon" placeholders (inc 163) — honest roadmap stubs.** Planned-but-unbuilt sections, tabs, or workspace
tabs may be scaffolded only when the capability is genuinely backlog-tracked, placed by the mode-vs-lens rule above,
and framed with the principle language it will ship with. A placeholder must be inert: no controls, no data, no
fake result. "Silence is not a certificate" applies to the roadmap too. Recipe: `<ComingSoon title body builds/>`
from `09_placeholders.jsx` plus the `.coming-soon*` CSS (`--accent-soft` badge, muted body, tokens only). Remove a
stub in the same increment its real feature lands.

**AI-usage and findings contracts.** The AI's job is to make verification cheap, **never to substitute for it**. For
any AI feature ask: *where did the judgment go?* It must land on a checkable computation or on the human, never hide
in an opaque selection or score. The findings output contract (METHODS "Review") keeps **FACT** and **CANDIDATE**
separate: a fact renders as a neutral persistent mark (`.fact-mark`, e.g. retraction), while a candidate renders as
a reviewable card (`.finding-card` → Confirmed / Accepted [needs reason] / Noted). The library badge
(`.finding-badge`, "N to review") describes the user's **work state**, never paper quality, and shows nothing at
zero. Speculative candidates get a `.speculative` dashed card; every candidate routes to its page at **region**
precision unless an exact anchor is actually known. The unified "N to review" library chip uses indigo `--accent`
as the work-state/provenance accent, deliberately separate from red/amber fact/status colors. Retraction facts use
`.fact-mark.retraction` (`--flag` for correction/concern, `--danger` for retracted) with notice links and source
provenance; the per-paper retraction status says "checked — none found" or "unchecked — no DOI" rather than implying
cleanliness from silence.

**Accessibility.** Differentiate sections, tabs, and states by icon + label, not color alone; prefer highlight/glow
over blinking; gate motion behind `prefers-reduced-motion`. Accordion headers carry `aria-expanded`, and workspace
and tab strips use tablist/tab semantics.
