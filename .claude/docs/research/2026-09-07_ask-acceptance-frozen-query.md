# Frozen next-day Ask acceptance query (recorded before any rebuilt-Ask result)

- **Frozen:** 2026-09-07, by Cliff, before implementation evaluation.
- **Purpose:** the single broad, multifaceted acceptance query for the rebuilt Ask (query-planner + evidence-hygiene). Chosen from subject matter Cliff's library actually covers; recorded verbatim so it cannot be cherry-picked after seeing results (steering #10/#11).

## Frozen broad acceptance query (verbatim)

> Synthesize the neural and biological systems implicated in late-life depression and its relationship to cognitive decline and dementia based on the literature in my library. I am particularly interested in serotonergic function, amyloid, glucose metabolism, gray-matter structure, memory and executive function, and other relevant neurobiological or cognitive findings. Give me a structured account of the systems and processes involved, what role each appears to play, and where the literature reports mixed, null, or uncertain findings.

## Structure (for reference)

- Broad phenomenon: neural/biological systems in late-life depression ↔ cognitive decline/dementia.
- Named facets: serotonergic function; amyloid; glucose metabolism; gray-matter structure; memory & executive function; ("and other relevant … findings").
- Related findings + structured account of systems/processes and their roles.
- Explicit request for mixed / null / uncertain findings (coverage/gaps).

## Acceptance judgement (NOT raw claim count)

Verified-synthesis usefulness · facet coverage · contributing-paper breadth · evidence hygiene · provenance · explicit gaps.

## Narrow regression queries (must remain unchanged vs today's single-query path)

Recorded here so they are also frozen; each must return behavior identical to the current `scope_type="query"` path (planner not invoked):

- A single-topic factual lookup, e.g. "What sample size did <a specific paper> use?"
- A single-region/single-mechanism question, e.g. "What did <paper> report about hippocampal volume in late-life depression?"

(Exact narrow strings to be finalized against the corpus during evaluation; they must be short, single-topic, and pre-gate-classified as narrow.)
