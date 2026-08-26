# Increment 503 — Clean funded Gemini calibration rerun

**Date:** 2026-08-25/26
**Production behavior:** unchanged

## Result

Reran the frozen `benchmark-calibration-v1` study from request 1 using funded Gemini access. No prior Gemini response
was reused. The final manifest remained `d2ac2c7fa036258b56cebdc2804c8b8b165aff2038a48bb326c83e477ec83b72`.

Track A completed 24/24 HTTP and mechanically usable responses, with zero structural-reference failures, 22/24
sentence adherence, and zero suspected truncation. It therefore **passes synthesis-overview-v1 Stage 1 mechanics**.

Track B completed 72/72 requests. Sixty-nine were mechanically usable. All three failures were the Q24
maximal-context repetitions: each reached the 256-token cap, was truncated, and failed structural references. Q04
was usable in all repetitions but exceeded the requested two-to-four-sentence form in all three. No retry or failed
provider attempt occurred.

Fresh usage was 21,373 input and 11,978 output tokens, with a paid-list-price equivalent of $0.0069285. The provider
did not expose actual billed cost.

A mixed blinded packet now contains nine semantic controls, two opaque candidates, and 144 randomized responses.
The packet and decode key remain separate in gitignored research storage. The challenge holdout is unopened.

## Decision

**READY FOR BLINDED HUMAN CALIBRATION**

Human reviewers must validate semantic controls first and then code candidate responses without decoding identity.
Mechanical passage is not scientific qualification.
