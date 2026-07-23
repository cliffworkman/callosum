# Security audit — LibreOffice current-section refresh (2026-07-23)

## Scope

Increment 358 adds a fixed **Refresh current section** Writer command. It derives one bounded main-text range from
Writer outline levels, sends the existing full-document citation render request, and transactionally writes back
only recognized Callosum ReferenceMarks in that range. It also makes the real-UNO test harness use a unique
temporary LibreOffice profile per run. No backend endpoint, dependency, document schema, or public integration is
added.

## Threat review

- **Input validation / output encoding:** section membership is calculated only from Writer `OutlineLevel` values
  and same-text range comparisons. Only marks already accepted by `scan_citations_in_order` can enter the plan;
  rendered output follows the existing plain-text `_replace_mark_text` path.
- **Injection:** the fixed
  `service:com.callosum.cite.Dispatcher?refreshCurrentSection` menu URL must resolve against the local action
  registry in package tests. No dynamic code, shell, SQL, HTML, or user-controlled dispatch is introduced.
- **SSRF / external calls / egress:** the command reuses the configured Callosum base URL and existing local
  citation-render endpoint. The request is identical in scope to existing refreshes; no new host, provider, or
  LLM path is added.
- **Secrets:** none read, stored, displayed, or transmitted.
- **Resource caps:** paragraph and citation scans are linear in the current document. The render remains the
  existing bounded full citation payload; Writer mutation is restricted to the finite set of marks in one
  outline subtree.
- **File-path safety:** the harness profile name is generated under the fixed `.local/lo_roundtrip` directory
  from the orchestrator PID and nanosecond timestamp. Teardown removes that exact path only after terminating the
  processes it started. Shipped extension behavior adds no filesystem operation.
- **State integrity:** the existing UndoManager transaction and rollback verification cover the targeted plan.
  Section refresh does not clear the document-wide citation-dirty flag, avoiding a false-clean state elsewhere.
- **Supply chain:** no dependency or package-entry change. Extension version 0.8.0 uses the existing builder.

## Negative-path checks

- Unit coverage fixes the outline contract for preamble, parent section, nested subsection, and heading-free
  document; invalid cursor scope and citation-free sections perform no render or mutation.
- The real Writer round trip creates actual paragraph breaks and Heading 1/Heading 2 outline levels, then proves
  that only the current heading subtree changes.
- The first real-UNO attempt caught an invalid soft-line-break fixture; the corrected fixture and unique-profile
  harness prevent a false pass and stale-profile startup failures.

## Result

**Security Audit: PASS**
