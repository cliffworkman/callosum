# Future track — CRediT statement builder (METHODS panel)

**Disposition for CC:** Capture into the backlog + `.claude/docs/future-tracks/`. Low-risk, build-ready. Runs
through the Principles gate (clears trivially) + a light security audit (the only egress is the optional DOI fetch
for the attribution paper — the existing OA-metadata path). **Working name "CRediTer"; the final name must be
distinct from "tenzing"** (see Attribution).

## One line
Rapidly build a CRediT contribution statement via a fast authors × roles grid and inject it into the manuscript
through the Word-link — killing one of the more tedious admin chores in manuscript prep.

## What it is / why it matters
CRediT (Contributor Roles Taxonomy; the open NISO standard) is credit-transparency infrastructure — it exists to
make invisible labor visible (the data curators, technicians, and early-career contributors that authorship-order
erases; the metaphor is Tenzing Norgay, who summited Everest and got a fraction of Hillary's credit). So this is
not merely admin-automation; it's a credit-equity tool wearing a convenience coat, and it belongs in the METHODS
suite beside PUBLISHERS and the citation-equity auditor.

## Attribution (load-bearing — a tool about credit that failed to credit would be self-refuting)
- **Built in the lineage of `tenzing`** (Marton Kovacs, Alex Holcombe, Frederik Aust, Balazs Aczel — the Shiny
  app / R package that pioneered this CRediT-statement workflow). Credit tenzing **prominently in-context** and
  **offer its paper to the user's library** (the active-attribution pattern — see the cross-cutting
  credit-the-lineage principle).
- **Distinct name, never "Tenzing."** Reusing the existing tool's name would collide with an active tool in the
  same niche and read as appropriation rather than homage — the opposite of the goal. Honor it by citation +
  library-add, not by taking the name.
- **Implement the open CRediT/NISO standard fresh** (the taxonomy is open; anyone may implement it). If any actual
  tenzing code or output templates are reused, honor its license; a fresh implementation keeps it clear regardless.

## The standard (get it exactly right — it's a fixed open taxonomy)
- The **14 CRediT roles**: Conceptualization, Data curation, Formal analysis, Funding acquisition, Investigation,
  Methodology, Project administration, Resources, Software, Supervision, Validation, Visualization, Writing –
  original draft, Writing – review & editing.
- Optional **degree of contribution** per role (lead / equal / supporting), per the NISO standard.
- Because the taxonomy is fixed and open, this tool **can be authoritative about format** — unlike the
  judgment-heavy METHODS tools, there's a correct answer here, so no hedging needed.

## Input UX (make-or-break — the chore being killed is "write it out," so the input mustn't become the new chore)
- A fast **authors × 14-roles matrix** (checkbox grid), with the optional lead/equal/supporting qualifier.
- **Pre-populate the author list** from manuscript metadata or the user's library where possible, so names aren't
  retyped. (Future: ORCID — CRediT+ORCID is where the standard is heading; roles can be pushed to ORCID records.)

## Output
- **v1 core:** the human-readable contributorship statement, injected into the manuscript via the Word-link.
- **Stretch:** machine-readable CRediT (JATS/XML) for submission systems that ingest it — kills the
  submission-time step too, not just the writing step.

## Honest scope
It is a statement **builder**, not a contribution **verifier** — it formats what the authors assert; it cannot
and does not check whether someone "really" performed a role. Say so plainly.

## The Beck & Christensen paper
Cliff's paper with Beck & Christensen motivates this tool. If it makes specific arguments about how contributorship
should be represented (beyond the vanilla standard), reflect them — Cliff to provide the reference and specifics.

## Callosum-fit
METHODS panel (alongside PUBLISHERS, citation-equity); Word-link injection; library integration for the tenzing
attribution (dogfoods the acquisition path); fully local except the optional attribution-paper DOI fetch.

## Gates
- **Principles gate:** clears trivially (open standard, attribution-forward, builder-not-verifier honest).
- **Security audit:** light — the only egress is the optional attribution-paper DOI fetch (existing OA-metadata
  path); validate the bibliography/author input.

## Tests / acceptance criteria
- The 14 roles + lead/equal/supporting are implemented per the NISO standard.
- The authors × roles grid produces a correct human-readable statement, injected via the Word-link.
- The author list pre-populates from manuscript/library where available (no forced retyping).
- tenzing is **credited in-context** and its paper is **offered to the library**; the tool's name is **not
  "Tenzing."**
- The tool presents itself as a builder, not a verifier.

## OUTPUT
A METHODS-panel CRediT statement builder (distinct name, not "Tenzing"): a fast authors × 14-roles grid with
optional lead/equal/supporting, author list pre-populated from manuscript/library, producing a human-readable
contributorship statement injected via the Word-link (machine-readable CRediT/XML as a stretch); implementing the
open NISO standard authoritatively; crediting tenzing in-context and offering its paper to the library; honest
that it builds, not verifies; low-gate and local but for the optional attribution fetch.
