# Future track — Citation-equity audit (METHODS panel)

**Disposition for CC:** Capture into the backlog + `.claude/docs/future-tracks/`. Do not build yet.
Equity-sensitive; the **identity-agnostic** design below is load-bearing — build only this shape. Runs through the
Principles gate (should clear) + the **security audit gate** (new OpenAlex egress + bibliography ingestion). The
gender/identity module is **explicitly deferred and separately gated** — not part of the core.

## One line
Audit a reference list for the *structural machinery* that reproduces inequitable citation — prestige
concentration, self-citation, Matthew-effect over-citation, venue/institutional concentration, Global-South
under-citation — and surface topically-relevant overlooked work the user may have missed, with an inspectable
"why this is a substitute" trail. **No author-identity inference.**

## The reframe (why identity-agnostic)
The original impulse — fight patriarchal skew in referencing — is better served by measuring the *machinery* than
by inferring gender. Name→binary-gender inference reifies the binary it aims to dissolve, is cis-normative,
infers an undisclosed attribute, and is systematically less accurate for non-Western names (Lockhart, King &
Munsch 2023: >43% error for Chinese women, 100% for non-binary scholars) — so it reproduces the inequity it
fights. The structural metrics measure the machinery directly; gender skew is one *output* of that machinery. The
reframe gets *closer* to the goal, not further, and fits Callosum's spine (inspectable evidence, no
sensitive-attribute inference, surface-don't-adjudicate).

**Honest scope note:** this tool answers a slightly different question than "what's my gender balance?" It
surfaces structural concentration and overlooked relevant work; it does **not** produce a gender-balance number.
Say so plainly.

## Scope
- **In:** structural + topical audit of a reference list; topical remediation (surface overlooked relevant work).
- **Out of the core:** any author-identity (gender/race) inference — see the deferred module.

## The audit (identity-agnostic structural + topical signals)
Computed from the reference list + OpenAlex metadata, each with an inspectable basis:
- **Self-citation rate** (King et al. 2017) — share of references to the user's own prior work.
- **Citation concentration / Matthew-effect skew** — over-reliance on already-highly-cited work vs. the topical
  field (Merton 1968; Perc 2014).
- **Venue/prestige concentration** — distribution across journals; over-concentration in a few high-prestige
  venues.
- **Institutional concentration** — affiliation distribution (the prestige "Howard-Harvard" effect).
- **Global-South / geographic under-citation** — affiliation-country distribution vs. the topical field's actual
  output (OpenAlex affiliations).
- **Topical-coverage gaps** — topically-central work the reference list omits.

Each metric is **descriptive, not a verdict** — it shows the shape of the reference list against the field, with
the basis inspectable. Never a pass/fail score; never a penalty.

## The remediation (purely topical — the distinctive feature)
- Surface **topically-relevant overlooked work** via content embeddings (SPECTER/SciNCL or the local
  sentence-transformers stack) over OpenAlex.
- **Inspectable substitution rationale** — show *why* each candidate is a real topical match (shared method,
  concept, dataset, overlapping findings, same subfield). Same inspectable-evidence move as the rest of Callosum.
- **Hard constraints (veto-level):**
  - Only ever **ADD / surface** overlooked relevant work; **never suggest dropping** a relevant citation.
  - **Never present author identity as the reason to cite.** The suggestion layer is identity-agnostic; equity
    improves as a *byproduct* of better scholarship.
  - **No quota, no tokenism framing.** "Here's relevant work you overlooked," never "add this to hit a target."

## Veto-level lines
- No author-identity inference in the core.
- Suggestions only add relevant work; never drop, never penalize.
- Identity is never the reason-to-cite at the suggestion layer.
- Every metric and every suggestion shows its inspectable basis (verify-everything; flag-not-adjudicate).
- Descriptive, never a pass/fail verdict.

## The deferred gender/identity module (separately gated — NOT in the core)
If ever built (only on explicit demand, behind its own gate and consent):
- **Opt-in**, off by default.
- **Self-ID-first:** prefer self-reported data (ORCID / publisher self-report) over inference.
- **Probabilistic fallback with explicit uncertainty** + an "unknown / non-binary-not-representable" category —
  never a hard binary label.
- **Aggregate-only** — never a per-author label, never a regression variable.
- **Suppress rather than mislead:** if per-subgroup error can't be bounded for the reference list's name
  distribution (e.g., a high share of East-Asian names), **suppress the number** rather than publish a biased one.
- **Governed by Lockhart, King & Munsch (2023) five principles:** critical refusal; align mechanism with method
  (name inference measures *ascription*, not self-identity); population-specific inference; high-accuracy
  subgroups only; aggregate estimates with bias checked on the target population.
- **Honest-limitations language (drop-in):** "This tool does not determine anyone's gender. Any gender-balance
  estimate is an aggregate approximation from probabilistic name→gender data, systematically less accurate for
  non-Western names and unable to represent transgender or non-binary scholars; it is shown only in aggregate,
  with uncertainty, never as an individual label. Remediation suggestions are based on topical relevance, not
  author identity."
- **Dated deferral rationale (preserve):** "As of 21 June 2026, no method was found that both avoids the
  reification, cis-normativity, undisclosed-attribute, and non-Western-name-accuracy problems of name→gender
  inference AND provides a per-reference gender verdict; the only approach that resolves the former for
  individuals — self-identification — is unavailable for arbitrary cited references."

## Callosum-fit
- Lives in the **METHODS panel** (alongside PUBLISHERS — both equity-flavored, both inspectable-evidence,
  both surface-don't-adjudicate; a coherent suite).
- Reads the reference list from the bibliography (the word-processor integration — select reference list →
  choose the tool → report in Callosum).
- Uses **OpenAlex** (already the acquisition/discovery resolver backbone — consistent dependency) for citations,
  affiliations, venues, topics, author disambiguation.
- **Local embeddings** (SPECTER/SciNCL or the existing sentence-transformers stack) for topical matching —
  local-first. Reference-list processing is local; OpenAlex calls are metadata fetches behind the egress gate.

## Gates
- **Principles gate:** identity-agnostic, inspectable, surface-don't-penalize, honest-limitations — expect a clean
  pass for the core. (The deferred module needs its own gate.)
- **Security audit gate:** fires — new OpenAlex egress (DOI/metadata lookups for the reference list + candidate
  pool) + bibliography ingestion path. Validate parsing inputs, response shapes, fail closed; OpenAlex polite-pool
  `email` attribution.

## Tests / acceptance criteria
- The audit computes the structural signals from a reference list + OpenAlex with **no identity inference**
  anywhere in the core (test asserts no gender/race code path).
- Each metric shows its **inspectable basis**; none is a pass/fail score.
- Remediation surfaces topically-relevant overlooked work with a **why-this-substitute** rationale; a test asserts
  suggestions **only add** (no "drop this" path) and **never reference author identity**.
- The reference list is processed **locally**; OpenAlex calls are metadata-only, behind the egress gate, with
  polite-pool attribution.
- The gender module is **absent from the core** and, if scaffolded, is **inert behind its own gate** (no per-author
  labels, aggregate-only, suppressible).

## OUTPUT
A METHODS-panel citation-equity tool: an identity-agnostic structural-and-topical audit (self-citation,
Matthew-effect concentration, venue/institutional concentration, Global-South under-citation, topical-coverage
gaps) presented descriptively with inspectable bases, plus purely-topical remediation that surfaces overlooked
relevant work with a why-this-substitute trail (add-only, never identity-driven); the gender/identity module
explicitly deferred as an opt-in, self-ID-first, aggregate, caveated, Lockhart-governed add-on behind its own
gate; built on OpenAlex + local embeddings, reference-list processing local, honest that it measures structural
concentration rather than a gender number.
