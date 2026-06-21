# PUBLISHERS — first-use choice gate (force all publisher defaults; no pre-selection)

**Disposition for CC:** Capture into the PUBLISHERS future-track
(`opus4.8_future-tracks_publishers-methods-tool.md`); this specifies the gate behavior for that tool. Do not build
ahead of the parent tool. The gate is scoped to **PUBLISHERS only** — not a global Callosum behavior.

## What the gate does
Before PUBLISHERS produces any output for a user the first time, it requires the user to **actively set every
settable publisher-related default**. Nothing is pre-selected — no option pre-checked, no slider resting at a
value, no "recommended" pre-fill. The tool yields no recommendations until the user has made each choice. After
the defaults are set once, PUBLISHERS runs inline; **the gate does not re-fire on subsequent uses** (settings stay
editable anytime in the settings modal).

## Why this shape (rationale = guard-rails; do not optimize these away)
- **No default — on, off, or otherwise — until the user sets one.** Any pre-selected default, even a "sensible"
  one, imposes a value the user didn't choose. With nothing pre-selected, neither on nor off is privileged; the
  user authors each choice. This dissolves the no-neutral-default problem on the answer rather than relocating it
  to a pre-fill.
- **Force *all* the consequential publisher defaults, not just the open-science weighting.** If the open-science
  weighting were the lone forced choice, the spotlight would re-singularize it — it would read as a purity test.
  Making every consequential publisher default an equal forced choice removes the singling-out: the open-science
  weighting becomes one decision among peers, framed no differently.
  *(Implementation note: the de-singularization goal is met as long as the weighting sits among other genuine
  choices; purely cosmetic display prefs needn't be forced — forcing those is friction without payoff. Calibrate
  the forced set to the consequential settings, and don't pad it with invented decisions just to give the
  weighting company.)*
- **Deliberate, one-time friction.** Callosum is opinionated and effortful by design (verify-everything,
  inspect-the-evidence); it does not cater to the just-give-me-results user, and that is a feature. The friction
  is **one-time (first use)**, not a recurring tax — the gate fires once, then the tool runs inline.
- **A stance is unavoidable; minimize it, don't fake escaping it.** Choosing on imposes; choosing off imposes;
  blank-until-set is itself a perspective — and Callosum is *itself* a perspective on how science could work, so
  the project is not obligated to be stance-free. The aim is to **reduce the presence** of the stance to the
  minimum achievable, not to counterfeit neutrality. Forcing the choice is the most defensible residual: "you
  must decide," not "we decided for you."

## The settings in scope
The open-science weighting (the thumb) plus the other consequential PUBLISHERS settings — e.g., match strictness,
which profile dimensions to prioritize in the ranking, default sort. (Final set = whatever PUBLISHERS exposes as
consequential.) Each presented neutrally, none pre-selected, with a plain one-line explanation of what it does.

## Workflow (the Word round-trip)
The tool pulls the abstract from the linked word processor, so the choices must exist before the first run for
the first output to reflect them. If the user invokes PUBLISHERS in-text (from Word) before completing setup,
**switch focus back to Callosum** and require the choices before running the analysis; thereafter it runs inline
from Word.

## Privacy (non-negotiable)
The publisher settings — the open-science weighting especially — are **stored locally and never transmitted**
(local store, behind the egress gate, inspectable). Device-local, or E2E-encrypted if ever synced, so Callosum HQ
can never read them. State the local-only guarantee **where the user sets the choices**, since that is where any
purity-test fear would arise.

## Output legibility (carries the ongoing legibility the quiet setup doesn't)
The results view always shows the chosen weighting's state inline — "open-science weighting: [the user's setting]
— N journals elevated for [goods]; adjust" — so a hasty or forgotten choice is visible and adjustable exactly
where it bites. The gate ensures a genuine first choice; the output thumb keeps it legible thereafter.

## Veto-level (do not let these erode)
- No pre-selected default on any forced choice (a "recommended" pre-fill defeats the purpose).
- The open-science weighting is never the *lone* forced choice (that re-singularizes it).
- Publisher settings are never transmitted.
- The gate is PUBLISHERS-scoped, not global.

## Tests / acceptance criteria
- PUBLISHERS produces **no output** until every forced publisher default is set; **no option is pre-selected** at
  first use.
- The open-science weighting appears as **one forced choice among others**, never alone.
- The gate fires **once** (first use); subsequent uses run inline; settings remain editable in the modal.
- Invoking from Word before setup **returns focus to Callosum** and requires the choices first.
- Publisher settings are **never transmitted** (test asserts no egress).
- The results view **always shows the chosen weighting's state** inline.

## OUTPUT
A first-use choice gate for PUBLISHERS that forces the user to actively set every consequential publisher default
with no pre-selection, presents the open-science weighting as one neutral choice among peers (never alone), stores
all settings locally and never transmits them, fires once with thereafter-inline operation, and surfaces the
chosen weighting's state at output — implementing the minimize-the-stance posture without pretending to escape it.
