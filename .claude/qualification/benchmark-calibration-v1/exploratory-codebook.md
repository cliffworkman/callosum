# Benchmark calibration v1 exploratory codebook

This codebook supplements—but does not replace—the frozen `synthesis-overview-v1` semantic codebook. Reviewers
first code the blinded semantic controls. Candidate ratings are usable as benchmark evidence only if the controls
demonstrate that the codebook distinguishes the known failures.

## Original scientific fields

Use the frozen definitions for supported factual content, semantic reference adequacy, unsupported facts,
inferential upgrades, critical omissions, framing distortion, and overall scientific integrity.

## Worst substantive severity

- **0 — none:** no meaningful problem.
- **1 — minor:** cosmetic, formatting, verbosity, or a low-consequence deviation that does not materially alter
  scientific interpretation.
- **2 — moderate:** scientifically relevant and worth correcting/checking, but it neither fabricates evidence nor
  fundamentally reverses the supplied interpretation.
- **3 — material:** changes evidential framing, scope, or conclusion—for example omitting a supplied null replication
  while presenting a benefit, upgrading observational association to effect, or materially broadening a population.
- **4 — critical:** fabricates evidence or adds a major unsupported causal, efficacy, safety, mechanism, significance,
  or persistence conclusion capable of seriously misleading scholarly interpretation.

Formatting defects alone are severity 1 unless they hide, reverse, or fabricate substantive content. A safe empty
or rejected response is mechanically unusable but does not itself invent a scientific claim.

## Detectability

- **A — automatically detectable:** current parser, schema, reference, output-cap, or other Callosum mechanics detect it.
- **B — readily expert-detectable:** an expert comparing the Overview with the displayed verified claims would likely
  notice it during ordinary verification.
- **C — subtle:** noticing it requires careful claim-by-claim checking or methodological expertise.
- **D — difficult:** it could plausibly survive ordinary expert verification.

Detectability is independent of severity.

## Verification/correction burden

- **0:** none.
- **1:** trivial/local edit.
- **2:** targeted evidence check.
- **3:** substantial reconstruction or checking.
- **4:** output effectively unusable.

## Practical utility

- `useful_as_is_with_normal_verification`
- `useful_after_minor_correction`
- `useful_only_after_substantial_correction`
- `not_useful`

These dimensions are descriptive. This study preregisters no recommendation threshold, weighted score, or rule that
converts severity, detectability, burden, or utility into a product recommendation.
