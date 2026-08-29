# Security audit — Word citation-coverage audit (increment 528)

**Date:** 2026-08-29
**Surface:** `adapters/word/` only; served Help and internal documentation
**Result:** **PASS**

## Trigger and boundary

The increment changes three or more files and adds a user-facing document scan, so the audit gate applies. It
adds no route, fetch, provider/model call, filesystem operation, persistence, dependency, credential, setting,
schema, prompt, scientific threshold, or document mutation. Word's existing **Document diagnostics…** remains
the sole fresh library-existence/retraction preflight; this increment does not duplicate or weaken it.

## Document-data handling

The scan reads only main-story paragraph text/outline/table metadata and existing Callosum Content Control tags.
Inline citation controls map to their containing main-text paragraphs. Citation controls inside native footnotes
or endnotes map through the note's WordApi 1.5 `reference` range, never by copying note or manuscript text to a
server. Session-local WordApi 1.6 paragraph IDs exist only during the `Word.run` batch and are not persisted,
logged, embedded, or returned to Callosum.

Callosum-managed full/section bibliography paragraphs and table cells are excluded from the prose signal. The
report contains paragraph numbers, counts, and at most 20 previews capped at 150 characters. It is written via
`textContent`, so manuscript text cannot become executable markup. No raw text enters a URL, request, credential,
Custom XML Part, document setting, telemetry channel, or durable receipt.

## Egress, credentials, and privacy

There is no network call in the audit path. Desktop and Word-on-the-web execute the scan inside Word's Office.js
context; the relay token and Callosum API are not consulted. The task pane holds the transient rows/report only
for the click's execution. No provider, metadata source, local model, NLI model, or library endpoint sees prose.

## Scientific and Principles alignment

The signal states only that no Callosum citation anchor occurs across three consecutive substantive paragraphs.
It does not classify claims, judge support, infer missing evidence, or say a citation is required. The report
explicitly calls itself a structural review prompt and disclaims unsupported-prose/citation-need conclusions.
This aligns with Principles #2 (signal, not verdict), #5 (the human decides), and #6 (silence is not a
certificate). The tempting misaligned implementation—NLI/LLM claim scoring or labeling prose "unsupported"—is
absent.

## Resource and failure bounds

One explicit click causes a bounded number of Office.js syncs and a linear local paragraph pass. Stored result
previews cap at 20 and 150 characters each. No polling, retry loop, background timer, tokenization, persistence,
or database contention is introduced. WordApi below 1.6 fails explicitly rather than guessing paragraph
membership. Office.js load/sync errors publish no clean result and leave the document unchanged.

## Residual manual boundary

No available agent can drive Word. Correct native-note anchor placement, managed-bibliography/table exclusion,
paragraph numbering, rendering, WordApi gating, and zero-mutation behavior remain on the consolidated manual
desktop/Word-on-the-web checklist. Pure Node tests cover scan thresholds, run boundaries, exclusions, counts,
preview/result caps, and static Office.js wiring.

**Security Audit: PASS**
