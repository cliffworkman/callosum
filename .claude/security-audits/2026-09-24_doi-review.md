# Local DOI review correction — security review

Scope: c7a7c10b-based extraction, derived queue explanation/candidate, and existing review UI.
No new endpoint, network destination, dependency, runtime, migration, or privilege.

Untrusted PDF text remains evidence, never canonical identity. Body/reference/component
observations cannot trigger automatic admission. PLOS component filtering never invents a
parent DOI. Ambiguous records stay unselected. Candidate rendering uses React text nodes;
no HTML injection, PDF-derived path, or PDF-derived URL fetch was added.

The existing preview endpoint performs on-demand DOI resolution; queue reads do not.
Confirmation still uses shared resolver-backed admission and attachment safety. The UI
prevents input changes while lookup is pending and clears previews when input changes,
so a displayed lookup cannot silently authorize another typed DOI. A source label records
provenance only, never confers trust. Original observations and prior actions are retained.

Validation: new real-PDF API/browser tests exercise unresolved lookup and admission,
explicit confirmation, read-only preview and candidate/manual provenance; existing capture
trust-boundary tests are included. No live QA data is used for mutation. No secrets appear
in saved diagnostics. See the investigation report for receipts and remaining heuristic limits.


Finalization addendum: extraction/lookup exceptions are mapped only from existing fixed
pipeline dispositions to fixed review copy; raw exceptions are never interpolated.
Fault-injection tests include a private-path/token sentinel and prove it is absent from
review output, while queued bytes survive and canonical admission remains untouched.
Lucien identified this truthfulness edge; Codex implemented and validated the correction.
