# Build now — Credit backfill + help update

**Disposition for CC:** BUILD (maintenance pass). Apply the credit-the-lineage principle
(`opus4.8_principle_credit-the-lineage.md`) **retroactively** across the existing codebase, complete
software-dependency attribution, and update the help. Well-timed ahead of the GitHub/shared release, where missing
attribution becomes visible and where dependency-license attribution is an AGPL-3.0 obligation, not a courtesy.
Low-risk; runs through the Principles gate (clears — attribution-forward).

## Why
The credit-the-lineage principle sets the pattern *going forward*; this pass fixes what is *already missing*. A
project about credit shipping with uncredited foundations would be self-refuting — most acutely for statcheck,
already built on Nuijten & Epskamp's work with no in-context credit.

## Two distinct kinds of credit (do not conflate — different debts, different mechanisms)
- **Lane A — scholarly-method lineage:** tools that implement/operationalize identifiable scholarly work
  (statcheck; the forthcoming CRediT builder; the auditors). Mechanism: **in-context credit in the tool + offer
  the source paper(s) to the library** (the research-citation pattern).
- **Lane B — software-dependency credit:** open-source libraries the code depends on (FastAPI, SQLite,
  SQLAlchemy, Alembic, sentence-transformers, sqlite-vec, …). Mechanism: a **third-party NOTICE / acknowledgments
  file** honoring each dependency's license and AGPL-3.0 obligations — *not* "add the paper to your library."

Both may currently be incomplete. Handle each in its own lane and keep them from bleeding into each other.

## Lane A — scholarly-method credit backfill
- Audit existing tools/features for any that implement or build on identifiable scholarly work or an existing
  tool; where credit is **missing or buried**, add in-context credit + library-add per the principle's
  lineage-manifest mechanism.
- Seed (known): **statcheck → Nuijten & Epskamp (package); Nuijten, Hartgerink, van Assen, Epskamp & Wicherts
  (2016, *Behavior Research Methods*)** — credit in-tool + offer the paper to the library.
- Check the retrieval/embeddings stack: if a *named scholarly method* is used (e.g., SPECTER/SciNCL), credit it
  (Lane A); if it's a generic library (plain sentence-transformers, sqlite-vec), that's Lane B.
- Each backfilled tool gets a **lineage manifest** surfaced consistently (the principle's affordance).

## Lane B — software-dependency / license attribution
- Ensure a complete **third-party NOTICE / acknowledgments** file crediting all open-source dependencies and
  honoring their licenses, consistent with AGPL-3.0. Generate/verify from the dependency manifest
  (pyproject/requirements). Load-bearing for the public release.
- This is **license compliance + acknowledgment**, distinct from research citation — keep the two
  files/sections separate so neither implies the other.

## Help update
- Update the help/docs to (1) document the relevant/new functionality, and (2) **carry the credit attributions** —
  wherever the help describes a method-implementing feature, it credits the lineage (with the paper), mirroring
  the in-tool credit.
- **Standing requirement (cross-ref the principle):** every future tool updates the help to cover its
  functionality *and* its lineage credit — help-currency + credit are part of "done," not an afterthought.

## Gates
- **Principles gate:** clears — attribution-forward, honest.
- **Security audit:** none triggered (docs/attribution only), unless the library-add wiring for a backfilled
  paper routes through the acquisition path (existing, already-audited).

## Tests / acceptance criteria
- Every existing method-implementing tool surfaces its **lineage in-context** and offers its source paper to the
  library (statcheck verified first).
- A complete **third-party NOTICE** exists, honoring all dependency licenses + AGPL-3.0.
- Scholarly-citation credit and software-license credit are **kept distinct** (separate mechanisms/files).
- The **help documents each relevant feature and carries its lineage credit**.
- No method-implementing feature ships (now or future) without help + credit updated.

## OUTPUT
A maintenance pass that retroactively applies the credit-the-lineage principle: in-context scholarly credit +
library-add backfilled across existing tools (statcheck → Nuijten & Epskamp first), a complete third-party NOTICE
honoring dependency licenses + AGPL-3.0 (kept distinct from scholarly citation), and a help update that both
documents functionality and carries the lineage credits — with help-plus-credit established as part of "done" for
every future tool.
