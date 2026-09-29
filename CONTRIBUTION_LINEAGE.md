# Contribution lineage — Phase 2 (0.6.0 Ask consolidation, 2026-09-29)

Per `.claude/CREDIT-THE-LINEAGE.md`'s contribution-lineage section: who introduced, challenged, tested, reframed,
implemented, or materially changed an idea as it developed. This covers Phase 2's own work; Phase 1's inventory and
the pre-Phase-1 architectural history are summarized only where they bear directly on a Phase 2 decision.

---

**Cliff Workman — Origin**
The q_aib parent research request itself, and the overall intended architecture: hierarchical decomposition into
independently-researched children, selective (not indiscriminate) recovery-time context widening, and NLI
citation-boundary repair as three integration streams.

**Cliff Workman — Disposition**
Approved the 11-child v8 hierarchy (`researcher_approved` records CD-1 through CD-5, D10) and, specifically, c6
("RESEARCHER DECISION: c6 IS ACCEPTED. Cliff confirms that c6 faithfully represents his original request for
specific brain areas..."). Corrected the recovery-widening semantics mid-development ("Cliff's correction, session
2026-09-27: no hard exclusion exists, so a deferred candidate must stay revisitable" — `contract_directed/
recovery.py`'s own docstring). Authorized this Phase 2 integration itself, with its explicit stop conditions —
itself a disposition-level decision about how consolidation should proceed and where it must halt for a
researcher decision rather than an implementation choice.

**Prior Claude session(s) — Implementation**
Built the pieces Phase 2 integrated or preserved: `contract_directed/neighborhood.py`'s deterministic +/-3
window construction; `contract_directed/recovery.py`'s selective recovery-planning machinery; the `decompose/`
hierarchy-construction engine (child-writer, deterministic traceability checks, relational-obligation parser,
clarification applier) that produced the frozen v8 hierarchy across its v2-v8 development history;
`hierarchy_contract.py`'s loader/rollup/preflight/manifest machinery; `ledger_renderer.py`'s hierarchy-rendering
additions (`_roll_child`/`_item_heading`/`_contract_block`/`_reconciliation_section`); `overview_guards.py`'s NLI
citation-boundary repair (`strip_redundant_unit_markers`, commit `15d7592b`); and the `ask-e2e` session's own
CLI/hierarchy-execution wiring (`e2e.py`/`stages.py`/`__main__.py`/`request_contract.py`) — which Phase 2 Section
4 found had already been fully carried forward into the committed lineage by the time this integration began.

**A prior session/process (2026-09-29, the Sept 29 flat E2E run) — Evidence**
Surfaced the original finding that the system read adjacent chunks during recovery but persisted only a
truncated single-chunk proposition anchor downstream — the finding Phase 2 Section 6 was chartered to trace and
that this session's own work (below) turned from a one-off observation into a regression-tested, code-level fact.

**This session (Phase 2 integration) — Implementation**
Created the integrated worktree from `ask-contract-directed`'s tip; independently snapshotted `ask-e2e`'s dirty
tree before touching anything; reconciled all six required integration-layer files against their common ancestor
(finding, and confirming with evidence, that zero net-new porting was needed — a material finding in its own
right, not merely mechanical); preserved the 30-file design-time hierarchy-construction tooling suite in place
with its non-runtime status documented; wrote `retrieval.recovery_neighborhood_context()`, porting
`neighborhood.build_neighborhood()` into the flat pipeline's recovery round specifically (and only there); wrote
the accompanying deterministic test coverage; wrote the integration manifest, the topology-doc update, and this
lineage record.

**This session (Phase 2 integration) — Evidence**
Wrote `MultiChunkEvidenceCollapsesToASingleAnchorTests`, a concrete, real-fixture test proving (not merely citing)
that a multi-chunk packet reaches claim formation as full context, that a claim can synthesize facts across
chunks, but that only one chunk is ever persisted as the evidence anchor — converting Section 6's Sept-29
observation into a locked-down regression fact with a specific, inspectable failure shape.

**This session (Phase 2 integration) — Critique**
Found, via exhaustive call-path search and a live `preflight_report()` run (not inference from the authorization's
own framing), that no "child-answer synthesis, Qwen3.5:9B thinking-OFF" stage exists anywhere in the codebase —
correcting an assumption embedded in the Phase 2 authorization's own Section 8 wording (that this was a
config/wiring gap to verify and reconcile) with the concrete finding that no such stage was ever built to
reconcile the configuration of. Reported as Section 15's stop condition #7 rather than silently built.

**This session (Phase 2 integration) — Reframing**
Distinguished, for the c6 provenance question, "approval absent" from "approval present but the downstream
report generator's display keys off a field (`approval_ref`) that one JSON record happens to omit" — resolving
what the Phase 1 inventory had flagged as an open inconsistency into a specific, evidenced, non-blocking
explanation, confirmed three independent ways (raw JSON, the real contract loader, and the real preflight
report) rather than asserted once.
