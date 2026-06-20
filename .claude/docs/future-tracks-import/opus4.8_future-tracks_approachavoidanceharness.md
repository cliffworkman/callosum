# Integrate APPROACH-AVOIDANCE.md into the Principles harness

**Task type:** CLAUDE.md / harness edit (meta — no application code). Not a future-track; action this directly.

## Goal
Wire the newly-authored **`.claude/APPROACH-AVOIDANCE.md`** (the values foundation beneath
`PRINCIPLES.md`) into the existing **Principles alignment gate** — as a **deeper, conditionally-consulted
layer, NOT a redundant second gate.** Verify the file exists at that path first; if it doesn't, report and
stop.

## Read first — the relationship (do not skip)
`APPROACH-AVOIDANCE.md` sits *beneath* `PRINCIPLES.md`, it does not duplicate it:
- **PRINCIPLES.md** = the operational rules + four worked aligned-vs-misaligned examples → *how* to build.
- **APPROACH-AVOIDANCE.md** = the values that explain and **generate** those rules → *why*. It has an
  **approach/avoidance** structure (including standalone hard boundaries with no approach face), and a
  **four-way drift typology** (confirmed / extended / emergent / divergent) for evaluating planned work.

Read it in full before editing. Its value in the harness is **generative**: when PRINCIPLES has no worked
example that matches a *novel* case, you derive the check from the relevant value.

## What to do (edit CLAUDE.md — rule #6 applies)
Make surgical additions; **point to A-A.md, do not copy its content into CLAUDE.md.**

1. **Reference docs table + directory layout** — add `.claude/APPROACH-AVOIDANCE.md` beside `PRINCIPLES.md`,
   described as: *"the values foundation beneath the charter — consulted when PRINCIPLES has no
   directly-applicable rule/example, for value-level concerns, and to drift-check future-tracks."*

2. **Extend the "Principles alignment gate" section** with a short **"Values layer (APPROACH-AVOIDANCE.md)"**
   note wiring it in as the deeper, conditional layer:
   - **Derive-from-value:** when no PRINCIPLES rule or worked example directly fits the case (a novel
     feature — most often a future-track), consult A-A and **derive the check from the relevant value.**
   - **Veto-level boundaries:** treat A-A's **standalone hard boundaries** (Part II — no paywall
     circumvention, no accusation of individuals, no becoming a gated/proprietary tool) as **veto-level**,
     alongside the Core design invariants.
   - **Broadened scope:** A-A catches value-level changes the principle triggers can miss — changes to
     access / licensing / distribution (equity), the acquisition boundary, anything that could introduce
     accusation, cost-vs-verification/consent trade-offs, or the **adoption of an emergent value** (a
     commitment not yet in the built artifact).
   - **Future-tracks drift check:** for planned/future-track work specifically, run A-A's four-way typology
     (confirmed / extended / emergent / divergent); **flag emergent values** ("adopt deliberately, don't
     drift into it") and **divergent tensions**, with the same deliverable as the principle gate — *propose
     the aligned alternative, don't just object.*
   - **Same philosophy:** still a **reflective pause, not a block**; and "a feature that cannot honor the
     values is a **finding about the feature, not a reason to relax them**" (extend the existing line to
     values).

3. **Economy (the point — do not make this a redundant gate):** A-A is consulted **only when the case is
   novel, value-level, or a future-track.** It is **not** a second mandatory full read on every gated edit.
   `PRINCIPLES.md` + the Core invariants remain the **first, primary** pass; A-A is the deeper layer reached
   for when that pass doesn't resolve or doesn't trigger on the change. State this explicitly so a future
   session doesn't turn it into a parallel tax.

4. **Rule #9** (or a new rule #10) — add one line: the Principles alignment gate now includes the **values
   layer (A-A.md)** for novel / value-level / future-track changes, deriving the check from the value when no
   principle directly applies.

5. **Session kickoff #8** — a brief cross-reference that the gate includes A-A for novel / future-track work.

## Constraints
- **Layered, not redundant.** The whole point is to add depth for the cases PRINCIPLES doesn't cover, without
  adding token cost to the cases it does. Do not make A-A a parallel mandatory gate.
- Keep the additions short and surgical; CLAUDE.md points to A-A, never recapitulates it.
- Meta edit only — no migration, no endpoint, no audit gate. Update CLAUDE.md in the same session (rule #6).

## Output
The CLAUDE.md edits (gate section + rule + reference table + directory layout + kickoff), and a one-paragraph
confirmation of how the values layer is wired in — deeper/conditional, veto-level hard boundaries, the
future-track drift check — and an explicit statement that it does **not** function as a redundant second gate.
