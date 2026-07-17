# Increment 282 — Credit-the-lineage backfill: the overlooked-work lens (#8)

Closes the one remaining Lane-A gap in backlog #8 (credit-the-lineage). The retroactive backfill was already
"effectively complete" (inc 180 gave statcheck/GRIM/p-curve the shared `.method-credit` affordance; 11 method panels
carry it: statcheck, GRIM, p-curve, citation-equity, citation-context, Bayes, mixed-model, meta-analysis,
transparency, effect-size, CRediT). The **overlooked-work lens** (#37, inc 279, built *after* the inc-180 pass)
operationalizes the **Matthew effect** (Merton 1968) but credited it only in prose — so it lacked the consistent
in-context credit + one-click library-add. This adds it.

## Implemented

- `app/frontend/js/36b_overlooked.jsx`: a `MERTON1968_CSL` source-paper constant + an `OverlookedCredit` component
  on the **shared `.method-credit` recipe** (same as `StatcheckCredit` — `<b>Method:</b> … — <citation>` + a
  "＋ add to library" button that `apiPost("/library/import", {content: JSON.stringify([CSL]), format: "csl-json"})`
  via the inc-93 import path + a `.method-credit-sub` note). Rendered at the bottom of the lens modal; the now-redundant
  "(Merton, 1968)" trimmed from the intro prose (the credit block carries the full citation).
- `THIRD-PARTY-NOTICES.md` already credits Merton (1968) (added with the lens in inc 279); this makes it **in-tool +
  one-click-addable**, satisfying the CREDIT-THE-LINEAGE acceptance criteria (in-tool lineage + offer the source paper).

## The audit (why nothing else)

The other credit-less method surfaces are **data-source-driven or compositional**, where Lane-A "add the source paper"
doesn't apply (they're credited at the NOTICES level, per the backlog rationale): publishers (DOAJ/OpenAlex data + the
SPECTER *model*, not a re-implemented method paper), reference-integrity (Crossref/Retraction-Watch data), funding +
gap-finder + retraction (data sources), critical-read (composes existing signals). With the lens covered, **every
method-implementing tool with an identifiable method-paper lineage now surfaces it in-tool + offers it to the library.**

## Manual verification script

Open **Overlooked** (menu bar → any workspace's discovery entry / the library header) → confirm the modal footer shows
"**Method:** the Matthew effect in science — Merton, R. K. (1968), Science 159(3810):56–63  ＋ add to library"; click
it → the paper imports into the library (idempotent) and the button reads "✓ added to library".

## Pytest

`tests/test_frontend_assembly.py::test_overlooked_lens_panel_present_and_honest` extended (asserts `OverlookedCredit` +
`.method-credit` + the Merton CSL + DOI present). Full suite unchanged at **1237 passed** (no new test, an existing
guard extended); assembly suite green.
