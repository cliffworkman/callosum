# Blinded human calibration guidance

Review the nine semantic controls first. Do not open or request the decode key before control and candidate coding
is complete and locked. The packet contains two opaque candidates and 144 randomized candidate responses.

Use the unchanged `synthesis-overview-v1` semantic codebook and the frozen calibration severity, detectability,
verification-burden, and utility fields. No weighted score or recommendation threshold applies.

## Detectability interpretation boundary

Detectability in this packet means **evidence-present expert-review detectability**: how detectable an issue is to an
expert who can compare the Overview directly with the synthetic verified claims printed alongside it. It is **not**
an estimate of detectability during ordinary use, where attention, time, evidence presentation, and domain
knowledge may differ.

## Higher judgment-dependence categories

The frozen categories remain unchanged, but two require comparatively more authorship judgment:

- distinguishing a materially misleading critical omission from ordinary summary compression;
- distinguishing material framing distortion from harmless stylistic or rhetorical variation.

Apply the frozen operational definitions consistently, record the supporting rationale in `notes`, and flag genuine
ambiguity rather than resolving it from assumptions about model identity. These cautions clarify interpretation;
they do not relax or rescore the historical zero-tolerance scientific gates.

Packet SHA-256: `be16f671b3a3e326344002be82c3f9246fd522c3d4175daa53a776936afdfdbc`.
