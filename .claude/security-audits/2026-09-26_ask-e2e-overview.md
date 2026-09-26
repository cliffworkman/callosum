# Security audit — Ask E2E overview stage (role S), offline implementation

Scope: `experiments/ask_cli_revised/overview*.py` and their integration. Experimental, not shipped. This audit covers the offline
implementation only; a live run is separately gated (`EXPERIMENT_GATE.md`) and gets its own review.

## Threat review

| area | finding |
|---|---|
| New endpoint / external fetch / dependency / file ingestion | **None.** No API route, no HTTP client, no new package. The only network path is the pre-existing `OllamaClient`, which refuses any non-loopback host. |
| Data egress | None added. S runs on the isolated loopback Ollama; passages never leave the machine. Invariant #3 is untouched. |
| Untrusted input | Passages are untrusted PDF text placed in the S prompt (prompt-injection surface). Model output is untrusted too. |
| Injection into the model | A passage containing instructions can at most steer S's wording. It cannot cite a passage it was not shown (closed `enum`; a schema violation is a NO ANSWER), and every statement must then pass the deterministic screen and local NLI against the passages, and is shown with its exact passage. Residual: an instruction that is itself a passage's own claim can be restated, and is displayed beside its verbatim source. |
| Injection into the output | Model text and passages are markdown-escaped (`_literal`) wherever they are rendered; tests cover links, HTML and heading injection. |
| Resource caps | 12 passages, 600 chars/passage, 12,000 prompt chars, 6 statements x 400 chars, every schema field bounded; worst case recomputed from the schema and pinned against the allowance. One model call, no retry. |
| Secrets / paths | None handled. The private reasoning trace stays in the private run directory. |
| Tamper resistance | The final audit re-derives units, eligibility, every statement's screen result and both rendered files from the sealed ledger; a tampered record makes checks fail and never crashes the audit. |

## Negative-path results (all offline; `net_guard offline`, canary in the same process)

Unparseable, capped, schema-invalid and over-context model output become explicit NO ANSWER states; an NLI failure, a fallback
scorer and a wrong-length score list withhold every statement; a missing scorer refuses before any stage; an edited artifact, a
forged eligibility flag, a forged NLI score, a smuggled withheld statement and a wrong ledger hash each fail the audit. 18 of 18
single-safeguard mutations are caught by the test suite. The guard receipt for the final runs lists only the four deliberate canary
probes.

Security Audit: PASS (offline implementation; live execution not yet authorized or reviewed)
