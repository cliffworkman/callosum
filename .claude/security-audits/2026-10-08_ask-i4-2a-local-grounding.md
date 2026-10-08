# I4-2a local-grounding integration security review

Scope: authorized offline experiment integration of pure local assertion/target primitives at the single
sufficiency_mapping.py consumer seam. No API, external integration, auth, dependency, or runtime file path added.

- Input validation: sealed replay hashes verified before consumption; dependency states fail closed for missing,
  blank, unsupported, ambiguous, or multi-target context. Duplicate ids rejected. Plural spans require identical
  sealed text before assertion joining; zero-hit units make no span claim. Negative tests cover unequal/absent
  coordinate metadata, failed joins, missing scope, malformed admissibility, and unsupported future versions.
- Provenance/output: full local assertion exact_text and sealed offsets retained; plural order and anchor proved.
  Candidate policy remains unassessed, not represented as approved. No rendering or executable-text path added;
  existing AnswerPlan renderer invariants pass. No shell, SQL, HTML or template interpolation introduced.
- SSRF/egress/secrets: pure in-memory mapping only, no new service endpoints or credential use. Replay holds
  nominations fixed. Offline suite denies sockets except subtrees that install their own stricter guards.
  Optional entry-point tests use scripted clients/runtime and endpoint_guard.refuse_all().
- Resource caps/path safety: processing is bounded by the existing caller-provided unit/role collection; no
  recursive input expansion, regex vocabulary growth, file ingestion, or production filesystem mutation added.
  The test-only CLI writes only the explicitly supplied output path and verifies frozen artifact identities.
- Supply chain/auth: no new dependency, no access-control changes; psutil collection issue handled by running
  seven optional offline tests in the existing dependency-complete environment, without installation.
- Negative checks: coordinate matrix 12 passed; focused suite 1371 passed/9 xfailed/85 subtests, only the two
  independently confirmed baseline pin failures. Static allow-list negative tests reject a second consumer.
  v4 full replay matches required hash; v5 full semantic output and diagnostics unchanged by repair.

Security Audit: PASS
