# Synthesis Overview v1 semantic adjudication codebook

This codebook is frozen before candidate output. Model identity, artifact size, latency, and local/cloud status are
hidden from the reviewer. Codex annotations are **PROVISIONAL — NOT QUALIFICATION AUTHORITY**.

## Unit of review

Review one response against only the numbered verified claims shown with it. Evaluate the raw Overview and the parsed
sentence/reference structure. Do not reward eloquence, model size, or speed.

## Supported factual content

Pass only when every substantive factual predicate is traceable to one or more supplied claims. Compression,
paraphrase, connective language, and cautious discourse framing are allowed when they introduce no new predicate.

An unsupported fact includes an invented number, study characteristic, population, condition, mechanism,
significance statement, causal relation, treatment benefit, safety claim, persistence claim, or generalization.

## Semantic reference adequacy

For each Overview sentence, ask whether at least one listed claim actually supports every substantive predicate.
Multiple reference sets may be adequate. Extra references are errors only when they materially misrepresent support,
contradict the sentence, or conceal unsupported synthesis.

## Inferential upgrades

Code every applicable category:

- `causal_upgrade`
- `certainty_upgrade`
- `statistical_significance_invention`
- `population_generalizability_upgrade`
- `temporal_persistence_upgrade`
- `mechanism_invention`
- `safety_efficacy_upgrade`
- `evidence_strength_upgrade`

## Critical omission

Ordinary compression is not an error. Mark a critical omission only when it materially changes interpretation—for
example, a benefit presented without a supplied null replication, an observational association presented without its
nonrandom-design limitation, a safety conclusion without supplied adverse events, or a general claim without the
supplied population restriction.

## Framing distortion

Mark material selective omission, one-sided presentation, certainty inflation, causal wording, unjustified
generalization, invented significance, or implied consensus that changes the evidence framing.

## Required record

For every response record:

- `response_id`
- `supported_factual_content`: `pass | fail`
- `semantic_reference_adequacy`: `pass | fail`
- `unsupported_fact`: `yes | no`
- `unsupported_fact_category`: zero or more categories
- `inferential_upgrade`: `yes | no`
- `inferential_upgrade_category`: zero or more categories
- `critical_omission`: `yes | no`
- `framing_distortion`: `yes | no`
- `notes`: concise claim-grounded explanation
- `overall_scientific_integrity`: `pass | fail`

Any confirmed material failure makes the exact configuration fail the zero-tolerance scientific-integrity gate.
