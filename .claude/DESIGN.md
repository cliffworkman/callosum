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

### Pills / badges (mono, uppercase, soft-bg + matching ink)
Recipe: `--mono`, ~10px, `text-transform:uppercase`, `letter-spacing:.04em`, padded `2px 7px`, pill
radius. Semantic color **pairs**: verified → `--verified-soft`/`--verified`; flag/uncertain/region →
`--flag-soft`/`--flag`; neutral → `--line`/`--ink-2`; accent/manual → `--accent-soft`/`--accent`.
(`.tier*`, `.axis-tier*`, `.sent-badge/.cite-status/.coord`, `.needs-doi`, `.chip`.)
**Narrow exception (inc 203, A9): red `--danger` is permitted on ONE *status* pill — `.cite-status.contradicted`**
(`--danger-line`/`--danger`), for a cited source that *actively disagrees* with the claim — the strongest negative
verifier signal, deliberately distinct from amber "uncertain/weak". This is the **only** status that uses red; it is
**non-interactive** (a pill, not a button), so it doesn't conflate with the §4 destructive-action red. Don't extend
red to any other status.

### Chips (interactive, rounded-pill, toggle)
`--term-chip`: dashed `--line-2` border + `--panel` bg when off; solid `--accent` border + `--accent-soft`
bg + `--accent` text when **on**. Radius 999px.

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

## 5. Pane architecture — THEORY / METHODS (inc 121)

The two side panes are **accordions** on a **module registry** (`app/frontend/js/05_panes.jsx`:
`registerPaneSection({id, label, paneId, order, render})` + `<PaneAccordion paneId ctx openId onOpen/>`). The
center `LibraryFrame` (library/PDF/dashboard tabs) is separate and untouched.

**Placement rubric — place a tool by the user's COGNITIVE TASK, not its implementation.** "AI-powered" is
orthogonal to the distinction.
- **THEORY (left pane)** — *knowing the literature*: **AXES** (your conceptual lenses, with a **Tags** tab — your
  labels — alongside it, inc 139: like-with-like, see "Tabs within a section" below) and **SYNTHESIS** (what the
  corpus says). `paneId: "theory"`.
- **METHODS (right pane)** — *evaluating how a paper was studied*, **ordered by cognitive task** (inc 139):
  **DETAILS** (`order: 10`) → **DATA CONSISTENCY (GRIM)** (inc 127, `order: 20` — it examines the *raw data*, so it
  precedes the analysis check) → **STATISTICS CHECK** (inc 122, `order: 30` — statcheck's per-paper check *and*
  library-wide batch, moved out of Settings + the Details pane into `06_methods_statcheck.jsx`, reusing the
  `.settings-*` / `.detail-statcheck` / `.statcheck-*` recipes — no new tokens) → **REVIEW** (inc 130 — the findings
  subsystem, `08_methods_findings.jsx`, `order: 40`); other checks later. `paneId: "methods"`.
- **Soft labels (for now):** the visible chrome shows only the section headers (AXES / SYNTHESIS //
  DETAILS / DATA CONSISTENCY / STATISTICS CHECK / REVIEW), **no "THEORY"/"METHODS" umbrella header** — the vocabulary
  is adopted once the METHODS modules earn it. The `paneId` is the internal architecture + the eventual rename.

**The registry pattern.** Sections are **data**, not hard-coded markup: a new section is one `registerPaneSection`
call in its own chunk (chunk load order 05<10<15<20<25 ⇒ the registry exists before the calls run), `order`
controls display position, **zero edits to `PaneAccordion`**. Design for addable (and someday user-supplied)
modules. **Mount-but-hide:** every section body stays mounted, inactive ones `display:none` (`.acc-section:not(.open)`),
so in-progress work (a running synthesis) survives a section switch. One section open per pane; the open section
persists (`callosum.theoryOpen` / `callosum.methodsOpen`). **Note the esbuild gotcha:** a registered-but-unreferenced
component is dead-code-eliminated from the build until something uses it — wire the consumer in the same change.

**Tabs within a section (inc 139) — the IA rule.** **Accordion sections are broad tool *categories*; within a
section, TABS present like-with-like submenus** so the accordion stays shallow instead of sprouting a sibling
section for every variant. AXES = `[Axes | Tags]` (your conceptual lenses + your labels — same cognitive task,
different lens). The rule going forward: **like groups with like** — e.g. future statistics checks become **tabs
inside STATISTICS CHECK**, not new sections; and **order sections by cognitive task**, not implementation
(DATA CONSISTENCY before STATISTICS CHECK). Mechanics (`05_panes.jsx`): `registerPaneTab({id,label,paneId,order},
{id,label,order,render})` adds a tab to a find-or-created host section; `registerPaneSection({…,render})` is sugar
for a one-tab section (no strip shown). The tab strip **reuses the `.tags-srcfilter` segmented-chip recipe**
(`.pane-tabs`, no new tokens); tabs **mount-but-hide** like sections (`.pane-tab:not(.active){display:none}`) so an
open axis / running action survives a tab switch; the active tab persists (`callosum.panetab.<sectionId>`).

**"Coming soon" placeholders (inc 163) — honest roadmap stubs.** Planned-but-unbuilt sections/tabs may be
scaffolded ahead of time (a visible roadmap), but only **honestly**: a stub must (1) name a **genuine,
backlog-tracked** capability — not vaporware; (2) be placed by the **cognitive-task rubric** above (THEORY new
sections after Cite; METHODS evaluation modules after REVIEW at `order: 50+`; *more stat checks become TABS in
STATISTICS CHECK*, not new sections — `09_placeholders.jsx` appends a "More checks" tab to the `statcheck` section
via `registerPaneTab` find-or-create, no edit to `06_methods_statcheck.jsx`); (3) **bake in the principle framing
it will ship with** (signal-not-verdict, never accusation) so the roadmap itself coheres; and (4) be **inert** —
no controls, no data ("silence is not a certificate": a placeholder *signals* incomplete work, it never fakes a
result). Recipe: the `<ComingSoon title body builds/>` component (`09_placeholders.jsx`) + the `.coming-soon*`
CSS (an `--accent-soft` badge + muted body; tokens only). Remove a stub in the same increment its real feature lands.

**AI-usage principle.** The AI's job is to make verification cheap, **never to substitute for it.** For any AI
feature ask *"where did the judgment go?"* — it must land on a checkable computation or on the human, never hide in
an opaque selection/score. **The findings output contract (inc 130, METHODS "Review"):** a **FACT** renders as a
neutral persistent **mark** (`.fact-mark`, e.g. "◆ retracted"), a **CANDIDATE** as a reviewable **card**
(`.finding-card` → Confirmed / Accepted[needs reason] / Noted); the library badge (`.finding-badge`, "N to review")
describes the user's **WORK STATE**, never paper quality, and shows nothing at zero. Speculative candidates get a
`.speculative` dashed card; every candidate routes to its page at **region** precision (no fabricated exact rect).
This is the FACT-vs-CANDIDATE backbone the later producers plug into. **inc 133** activates the candidate half: a
producer (statcheck) emits CANDIDATE findings, and a unified **"📋 N to review"** library chip
(`.trash-toggle.findings-chip`, indigo `--accent` = the work-state/provenance accent, deliberately **not** the
red/amber reserved for fact/status) + a `?finding=needs-review` filter surface every paper with an unreviewed
candidate. The chip is a *work-state queue* count (papers you haven't reviewed), never a quality rank — distinct
from the red retraction chip (a fact) and the amber statcheck chip (a signal). **inc 131 (retraction)** is the
first producer: its FACT renders a specialized FactMark (`.fact-mark.retraction` — `--flag` amber for correction/concern,
`--danger` red for `.retraction-severe` = retracted) carrying a **notice** link + the flagging sources; a per-paper
`.retraction-status` line states "checked — none found" / "unchecked — no DOI" (silence ≠ clean); the
`.trash-toggle.retraction-chip` (red `--danger`) is the library "N retracted" *filter* count, never a verdict.

**Accessibility.** Differentiate sections/states by **icon + label, not color alone**; prefer a highlight/glow over
a blink; gate motion behind `prefers-reduced-motion`. Accordion headers carry `aria-expanded`.
