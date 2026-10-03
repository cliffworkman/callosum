"""The two-round E2E orchestrator for a role-bound topology.

    W -> verify -> R -> C -> P -> W -> verify -> R -> C -> render

W is bounded extraction (retrieve, context gate, evidence selection, claim formation); *verify* is the unchanged local
source verification; R judges each source-verified claim's responsiveness; C audits coverage over the ledger; P plans one
bounded recovery round; the renderer is deterministic. Stages a topology does not bind (R in a model-coverage arm) are
skipped by topology and appear nowhere; stages with nothing to act on (no new evidence, no planned search) are recorded
as skipped with their reason. A mechanical failure at any stage is NO ANSWER and fails closed: it is never converted
into a semantic verdict and never falls back to a different mechanism.

``execute`` is the sequencing core (injectable retrieval, fakeable clients). ``run_topology`` wraps it with the guards a
scored run needs: frozen contracts, a clean recorded code tree, a verified library copy, and the runtime it builds.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import platform
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from experiments.ask_cli_revised import __main__ as cli
from experiments.ask_cli_revised import (
    backends,
    discovery,
    e2e_checks,
    e2e_contracts,
    hierarchy_contract,
    library_copy,
    overview,
    overview_audit,
    overview_render,
    parent_synthesis,
    parent_synthesis_audit,
    parent_synthesis_ledger,
    parent_synthesis_render,
    provenance,
    retrieval,
    stages,
    sufficiency_diagnostic,
    sufficiency_freeze,
    sufficiency_recovery_targets,
)
from experiments.ask_cli_revised import sufficiency_model_scope as mscope
from experiments.ask_cli_revised import topology as topo
from experiments.ask_cli_revised.ledger_renderer import audit_final, render_answer
from experiments.ask_cli_revised.qwen import QwenTasks
from experiments.ask_cli_revised.request_contract import build_request_contract, request_subquestions
from experiments.ask_cli_revised.runtime import QwenUnavailableError, build_runtime
from experiments.ask_cli_revised.supervisor_eval.ollama_client import OllamaClient
from experiments.ask_cli_revised.trace import TraceWriter

_ROLES = ("W", "R", "C", "P")
_MODEL_KINDS = {"managed_local", "ollama"}


@dataclass
class Sink:
    """Everything the retrieval/verification stages accumulate across both rounds."""

    all_records: list = field(default_factory=list)
    chunk_hits: list = field(default_factory=list)
    context_growth: list = field(default_factory=list)
    evidence_packets: list = field(default_factory=list)
    propositions: list = field(default_factory=list)
    verifications: list = field(default_factory=list)
    direct_papers: list = field(default_factory=list)
    axis_noms: list = field(default_factory=list)
    candidate_papers: list = field(default_factory=list)
    nominations_by_subq: dict = field(default_factory=dict)
    axis_cache: dict = field(default_factory=dict)


@dataclass
class Bound:
    """A profile's roles made callable: the worker, and one policy-governed Supervisor per model-bound R / C / P."""

    qwen: QwenTasks
    supervisors: dict


def _endpoint_model(binding: topo.Binding) -> tuple[str, str] | None:
    if binding.kind == "managed_local":
        return binding.endpoint, binding.model
    if binding.kind == "ollama":
        return binding.endpoint, binding.model
    return None


def _roles(profile: topo.Profile) -> tuple[str, ...]:
    """W/R/C/P always; S only when the profile binds it (so a Wave-1 profile's records are unchanged)."""
    return (*_ROLES, "S") if profile.S.kind != "off" else _ROLES


def endpoints_used(profile: topo.Profile) -> list[str]:
    return sorted({em[0] for role in _roles(profile) if (em := _endpoint_model(getattr(profile, role)))})


def bind(profile: topo.Profile, *, rt, clients: dict, trace, managed_chat=backends.ManagedLocalChat) -> Bound:
    worker = profile.W
    if worker.kind == "managed_local":
        worker_config = rt.qwen_config
    else:
        worker_config = backends.NativeWorker(
            client=clients[worker.endpoint], model=worker.model, base_options=topo.SUPERVISOR_BASE_OPTIONS,
            think=worker.think,
        )  # fmt: skip
    supervisors = {}
    for role in ("R", "C", "P"):
        binding = getattr(profile, role)
        if binding.kind == "managed_local":
            client = managed_chat(rt.qwen_config)
        elif binding.kind == "ollama":
            client = clients[binding.endpoint]
        else:
            continue
        supervisors[role] = stages.Supervisor(
            role=role, binding=binding, client=client, base_options=topo.SUPERVISOR_BASE_OPTIONS, trace=trace
        )
    if profile.S.kind == "ollama":  # each S-enabled profile owns its own options envelope (topo.Profile.S_options);
        supervisors["S"] = stages.Supervisor(                             # validate() guarantees it is set here
            role="S", binding=profile.S, client=clients[profile.S.endpoint],
            base_options=profile.S_options, trace=trace,
        )  # fmt: skip
    return Bound(qwen=QwenTasks(config=worker_config, trace=trace), supervisors=supervisors)


# ---- retrieval rounds (patched in the sequencing tests; real everywhere else) ------------------------------------------


def _initial_pass(conn, *, rt, qwen, subquestions, sink: Sink, trace) -> None:
    """Round-one W: discover, retrieve, grow context, select, form claims, and source-verify. R has not run yet."""
    trace.write_json("04_graph_rescue.json", discovery.graph_rescue_stage(conn))
    for subquestion in subquestions:
        sid = subquestion["subquestion_id"]
        text = subquestion["text"]
        nominations, nomination_log = discovery.nominate_papers(
            conn,
            subquestion_text=text,
            model=rt.model,
            vector_store=rt.vector_store,
            axis_cache=sink.axis_cache,
        )
        sink.nominations_by_subq[sid] = nominations
        for row in nomination_log:
            target = sink.axis_noms if str(row.get("reason", "")).startswith("axis:") else sink.direct_papers
            target.append({**row, "subquestion_id": sid})
        sink.candidate_papers.append({"subquestion_id": sid, "papers": [cli._paper_record(nom) for nom in nominations]})
        hits = retrieval.within_paper_retrieve(
            conn,
            subquestion_id=sid,
            subquestion_text=text,
            paper_ids=[nom.paper_id for nom in nominations],
            model=rt.model,
            vector_store=rt.vector_store,
        )
        cli._process_hits(
            conn,
            rt=rt,
            qwen=qwen,
            subquestion=subquestion,
            hits=hits,
            reason_by_paper={nom.paper_id: nom.reasons for nom in nominations},
            origin="initial",
            trace=trace,
            all_records=sink.all_records,
            chunk_hits=sink.chunk_hits,
            context_growth=sink.context_growth,
            evidence_packets=sink.evidence_packets,
            propositions=sink.propositions,
            verifications=sink.verifications,
            map_claims=False,
        )


def _recover_round(conn, *, rt, qwen, subquestions, gaps, plan, sink: Sink, trace) -> list[dict]:
    """Round-two W: execute exactly the planned action per unresolved item; claim mapping stays deferred to R."""
    return cli._recover(
        conn,
        rt=rt,
        qwen=qwen,
        subquestions=subquestions,
        gaps=gaps,
        initial_nominations=sink.nominations_by_subq,
        all_records=sink.all_records,
        axis_cache=sink.axis_cache,
        trace=trace,
        chunk_hits=sink.chunk_hits,
        context_growth=sink.context_growth,
        evidence_packets=sink.evidence_packets,
        propositions=sink.propositions,
        verifications=sink.verifications,
        plan=plan,
        map_claims=False,
    )


def seed_pass_from(path):
    """Smoke only: hand round one the source-verified claims of an earlier run instead of running W.

    A worker whose gate discards nearly everything leaves R / C / P nothing to judge in a small smoke, so their live
    plumbing would go unexercised. The seeded claims keep their recorded source verification and evidence spans, are
    reset to pending (R has not judged them), and are marked ``seeded``. The ledger must be for the same request.
    """
    raw = Path(path).read_bytes()
    ledger = json.loads(raw.decode("utf-8"))
    digest = hashlib.sha256(raw).hexdigest()

    def _seed(conn, *, rt, qwen, subquestions, sink: Sink, trace) -> dict:
        if ledger["request_contract"]["question_hash"] != subquestions[0].get("question_hash"):
            raise ValueError("the seed ledger is for a different request")
        wanted = set()
        for row in ledger["verified_propositions"]:
            record = {key: value for key, value in row.items() if key != "proposition_id"}
            record["obligation_ids"] = []
            record["mapping_state"] = "pending"
            record["provenance"] = {**record.get("provenance", {}), "origin": "initial", "seeded": True}
            sink.all_records.append(record)
            wanted.add((row["paper_id"], row["evidence_anchor_chunk_id"], row["evidence_span_id"]))
        for span in ledger["evidence_spans"]:
            if (span["paper_id"], span["chunk_id"], span["span_id"]) in wanted:
                sink.evidence_packets.append(
                    {
                        "origin": "initial",
                        "paper_id": span["paper_id"],
                        "discarded": False,
                        "candidate_spans": [
                            {"chunk_id": span["chunk_id"], "span_id": span["span_id"], "text": span["text"]}
                        ],
                    }
                )
        return {"seeded_claims": len(ledger["verified_propositions"]), "ledger_sha256": digest}

    return _seed


@contextlib.contextmanager
def smoke_caps(limits: dict | None):
    """Lower the retrieval breadth caps for an unscored plumbing smoke run, restoring them on exit."""
    limits = limits or {}
    saved = (discovery.PER_SUBQ_PAPER_CAP, retrieval.WITHIN_PAPER_TOP_K)
    try:
        if "per_subq_paper_cap" in limits:
            discovery.PER_SUBQ_PAPER_CAP = limits["per_subq_paper_cap"]
        if "within_paper_top_k" in limits:
            retrieval.WITHIN_PAPER_TOP_K = limits["within_paper_top_k"]
        yield
    finally:
        discovery.PER_SUBQ_PAPER_CAP, retrieval.WITHIN_PAPER_TOP_K = saved


def _caps() -> dict:
    return {
        "paper_knn_top_k": discovery.PAPER_KNN_TOP_K,
        "axis_top_k": discovery.AXIS_TOP_K,
        "per_subq_paper_cap": discovery.PER_SUBQ_PAPER_CAP,
        "within_paper_top_k": retrieval.WITHIN_PAPER_TOP_K,
        "per_paper_chunk_cap": retrieval.PER_PAPER_CHUNK_CAP,
        "max_growth_iters": retrieval.MAX_GROWTH_ITERS,
        "max_packet_chars": retrieval.MAX_PACKET_CHARS,
    }


# ---- the sequence ------------------------------------------------------------------------------------------------------


def _authority(profile: topo.Profile) -> dict:
    if profile.C.kind == "det":
        return {"kind": "det", "role": "R"}  # deterministic coverage consumes R's mappings
    return {"kind": "model", "role": "C", "model": profile.C.model}


def _binding_record(binding: topo.Binding) -> dict:
    return {"kind": binding.kind, "model": binding.model, "endpoint": binding.endpoint, "think": binding.think}


# ---- Phase 20b: production initial model-assisted sufficiency wiring, feature-gated off --------------------------------


class SufficiencyModelAssistRefused(RuntimeError):
    """`--sufficiency-model-assist` was requested but a required precondition failed. Mirrors
    `AuthorizationRefused`/`HierarchyRejected`'s fail-closed convention: no silent fallback from an
    EXPLICITLY requested model-assisted path to deterministic-only mapping, and no silent
    degradation of its preconditions (a thinking-enabled W binding, an unresolvable model identity,
    no active sufficiency contract at all)."""


def _sufficiency_u1_context(profile: topo.Profile, bound: Bound) -> tuple[object, dict]:
    """Phase 20b's ONE enforcement point for the mandatory nomination-context invariant (the
    researcher decision this phase opened with): production model assistance may never run
    through a bare `model_client` -- this function always constructs `model_client` and
    `nomination_context` TOGETHER, so no caller below it can produce one without the other merely
    by omission. Raises `SufficiencyModelAssistRefused` before any call if the active W binding
    cannot safely support nomination:

    - thinking must be exactly `False`. Nomination's output cap is a small, fixed
      `_NOMINATION_OUTPUT_TOKENS` (`qwen.py`) with no per-call override anywhere in this codebase;
      a thinking-enabled worker would silently starve every nomination call before it ever emits a
      parseable answer (the Phase-20 audit's own §5 finding) -- never mutated, never silently
      disabled, just refused up front with a clear configuration error.
    - the resolved `model_client` (the SAME `bound.qwen` the W role already uses for claim
      formation -- confirmed by direct inspection of `bind()`, never a second nomination worker or
      a separate Qwen lifecycle) must expose a non-empty `model_name` (`qwen.QwenTasks.model_name`),
      so a receipt's provenance is never silently `None` merely because the adapter failed to
      expose an already-known identity.

    `all_eligible_policy()` is this function's own fixed U1 policy -- every structurally eligible
    scope may attempt one fresh call this pass, demand-driven by the mapper exactly as Phase 19
    already proved (nothing here pre-calls every inventory scope)."""
    if profile.W.think is not False:
        raise SufficiencyModelAssistRefused(
            "--sufficiency-model-assist requires the active W binding's thinking setting to be "
            f"exactly False (current: {profile.W.think!r}); nomination's fixed-size output cap has "
            "no per-call thinking override, and a thinking-enabled worker would silently starve "
            "every nomination call before it could emit a parseable answer"
        )
    model_client = bound.qwen
    model_name = getattr(model_client, "model_name", None)
    if not model_name:
        raise SufficiencyModelAssistRefused(
            "--sufficiency-model-assist requires the active W binding's client to expose a "
            "resolvable model_name, but none was found"
        )
    return model_client, mscope.new_nomination_context(mscope.all_eligible_policy())


class _SufficiencyPostRecoveryDryClient:
    """Phase 22: counting-only, never-live fake -- always declines, never asserts a real
    nomination. Used ONLY to let the real, unmodified `compute_diagnostic_sufficiency_map` perform
    its own candidate-construction work against the post-recovery sealed ledger, so the SET of
    reachable `(ModelNominationScope, request_context)` keys can be enumerated without any network
    call or live model request -- the identical technique Phase 21's own offline fresh-call-cap
    derivation used."""

    model_name = "phase22-post-recovery-dry-enumeration-never-live"

    def nominate_sufficiency_role(self, *, category_description, candidates):
        return []


def _sufficiency_post_recovery_request_inventory(
    sealed: dict, sufficiency_contract: dict, sufficiency_parent_of: dict
) -> frozenset:
    """Phase 22: candidate-construction-only dry enumeration (no network, no live model call) of
    every `(ModelNominationScope, request_context)` reached with nonempty candidates against the
    POST-RECOVERY sealed ledger. Never reimplements any mapper logic -- it calls the real
    `compute_diagnostic_sufficiency_map` with `_SufficiencyPostRecoveryDryClient` and reads back
    which composite keys resolved to status `"fresh"` (the same status Phase 21's own cap
    derivation filtered on).

    Safe (model-output invariant) for every mechanism currently in real use -- ordinary single/
    multi-instance mapping, `build_multi_instances` partitioning, role-fork multiplicity, and
    `map_paired_requirement`'s own-evidence-first dispatch (confirmed by direct trace of each
    during the Phase-22 audit: a role's own candidate rows and `(scope, request_context)` identity
    are fixed before any role is processed, independent of nomination outcome -- role-forking only
    changes CALL COUNT per key, which `resolve_nomination`'s own in-pass memoization already
    collapses to one physical call regardless). Explicitly NOT proven safe for a `model_nomination_
    only` role under `all_requested_categories` (`map_cardinality_requirement`'s own dormant,
    never-yet-triggered multi-term identity gap) -- this function would simply propagate that same
    loud `ValueError` refusal rather than silently mis-enumerating, since it calls the identical
    production function with no bypass.

    NOT authoritative for final semantic answers or final forked instance structure -- only
    `sufficiency_map_initial` (the REAL U1 map) is ever consulted for historical role-fill state
    (`sufficiency_recovery_targets.project_fresh_request_keys`'s own documented division of
    labor)."""
    ctx = mscope.new_nomination_context(mscope.all_eligible_policy())
    sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
        sealed,
        sufficiency_contract,
        sufficiency_parent_of or {},
        model_client=_SufficiencyPostRecoveryDryClient(),
        nomination_context=ctx,
    )
    return frozenset(key for key, receipt in ctx["in_pass_receipts"].items() if receipt["status"] == "fresh")


def _nomination_pass_summary(nomination_context: dict | None) -> dict:
    """Internal run diagnostics only (audit §14) -- never user-facing prose, never raw model text:
    `new_nomination_receipt` carries no chain-of-thought/raw-scratch field to begin with, so this
    is satisfied by construction, not an extra redaction step here."""
    if nomination_context is None:
        return {"enabled": False}
    receipts = list(nomination_context["in_pass_receipts"].values())
    by_status: dict[str, int] = {}
    for receipt in receipts:
        by_status[receipt["status"]] = by_status.get(receipt["status"], 0) + 1
    return {"enabled": True, "scopes_reached": len(receipts), "by_status": by_status}


def execute(
    *,
    rt,
    profile: topo.Profile,
    contract: dict,
    trace,
    guard,
    bound: Bound,
    smoke_limits: dict | None = None,
    seed_pass=None,
    entail=None,
    sufficiency_contract: dict | None = None,
    sufficiency_parent_of: dict | None = None,
    sufficiency_recovery_gate_enabled: bool = False,
    parent_synthesis_enabled: bool = False,
    sufficiency_model_assist_enabled: bool = False,
) -> dict:
    if "S" in bound.supervisors and entail is None:
        # Fail closed before any stage, trace file or model call: an overview is never shown unscreened.
        raise ValueError("the overview stage (S) needs a local entailment scorer (entail=) to screen its statements")
    if contract.get("version") == hierarchy_contract.HIER_VERSION:
        hierarchy_contract.assert_executable(contract)  # fail closed before any stage, trace file or model call
        if seed_pass is not None or any(
            k in (smoke_limits or {}) for k in ("max_initial_subquestions", "max_recovery_gaps")
        ):
            raise ValueError(
                "a hierarchical run may not slice its children or seed its claims (that would silently drop or replace approved children)"
            )
    # Phase 20b: validated and (when valid) constructed BEFORE any stage, trace file, or model call
    # -- the same fail-closed posture as the two checks immediately above. No silent fallback from
    # an explicitly requested model-assisted path to deterministic-only mapping: every precondition
    # is checked exactly once, here, never re-derived or silently skipped later. `sufficiency_
    # u1_model_client`/`sufficiency_u1_context` stay (None, None) -- byte-identical to every
    # pre-Phase-20b caller -- unless assistance is both requested and safe to run.
    sufficiency_u1_model_client = None
    sufficiency_u1_context = None
    if sufficiency_model_assist_enabled:
        if sufficiency_contract is None:
            raise SufficiencyModelAssistRefused(
                "--sufficiency-model-assist was requested but no sufficiency contract is active "
                "for this run (sufficiency_contract is None) -- there is no deterministic "
                "sufficiency mapping for a model to assist"
            )
        sufficiency_u1_model_client, sufficiency_u1_context = _sufficiency_u1_context(profile, bound)
    subquestions = request_subquestions(contract)
    obligations = [sq["obligations"][0] for sq in subquestions]
    question = contract["original_question"]
    smoke = smoke_limits or {}
    sink = Sink()
    stage_log: list[dict] = []
    skipped: list[dict] = []

    @contextlib.contextmanager
    def stage(name: str, role: str):
        binding = getattr(profile, role)
        swap_seconds = 0.0
        target = _endpoint_model(binding)
        if target is not None:
            swap_seconds = guard.enter(target[0], target[1], phase=name)["wall_seconds"]
        entry = {"stage": name, "role": role, "binding": _binding_record(binding), "swap_seconds": swap_seconds}
        started = time.monotonic()
        try:
            yield entry
        finally:
            entry["wall_seconds"] = round(time.monotonic() - started, 3)
            stage_log.append(entry)
            if target is not None:
                guard.observe(name)

    def skip(name: str, reason: str) -> None:
        skipped.append({"stage": name, "reason": reason})

    def responsiveness(name: str) -> None:
        if "R" not in bound.supervisors:
            return  # R is off by topology: absent, not skipped
        with stage(name, "R") as entry:
            entry["detail"] = stages.run_responsiveness(
                bound.supervisors["R"], question=question, obligations=obligations, records=sink.all_records
            )

    def coverage(name: str, *, classify_pids: set[str] | None = None) -> dict:
        with stage(name, "C"):
            if profile.C.kind == "det":
                # det_coverage has no analogous re-sealing drift: it only ever reads each record's
                # own `obligation_ids`, and R (`run_responsiveness`) already skips already-mapped
                # records -- an old record's attachment is append-only-stable for free, upstream.
                return stages.det_coverage(subquestions, sink.all_records, authority=_authority(profile))
            return stages.run_coverage_audit(
                bound.supervisors["C"],
                question=question,
                obligations=obligations,
                subquestions=subquestions,
                records=sink.all_records,
                authority=_authority(profile),
                classify_pids=classify_pids,
            )

    trace.write_json("01_request_contract.json", contract)
    with rt.engine.connect() as conn:
        with stage("W1", "W") as entry:
            initial_subquestions = subquestions[: smoke.get("max_initial_subquestions") or len(subquestions)]
            first_round = seed_pass or _initial_pass
            detail = first_round(
                conn, rt=rt, qwen=bound.qwen, subquestions=initial_subquestions, sink=sink, trace=trace
            )
            if detail:
                entry["detail"] = detail
        responsiveness("R1")
        coverage_initial = coverage("C1")
        # Phase 17 §C/§E: a cheap, exact snapshot of the ledger AS OF C1 -- a plain list copy, no
        # seal() call yet (records are append-only/stable before this point, so a shallow copy is
        # sufficient; the actual `seal()` build is deferred into the recovery branch below, where
        # it is only paid when a round genuinely adds new source-verified evidence).
        pre_recovery_records = list(sink.all_records)

        # Diagnostic semantic answer-sufficiency (§ "Production activation / gating strategy",
        # item (A)): always computed, deterministic-only, whenever a frozen SufficiencyContract
        # is supplied -- independent of whether any model-assisted nomination role is ever bound.
        # Inert for every profile/run that does not pass `sufficiency_contract` (every existing
        # call site): `sufficiency_map_initial` stays None and nothing below this block executes.
        sufficiency_map_initial = None
        sufficiency_u1_receipts_snapshot = None
        if sufficiency_contract is not None and contract.get("version") == hierarchy_contract.HIER_VERSION:
            early_sealed = stages.seal(
                contract, subquestions, sink.all_records, sink.evidence_packets, coverage_initial
            )
            if sufficiency_u1_model_client is not None:
                # Model-assisted U1: brought under the SAME W-role residency/stage accounting as
                # every other bound.qwen call in this function (audit §11) -- compute_diagnostic_
                # sufficiency_map may make zero to several physical nomination calls internally
                # (Phase-19's own resolve_nomination decides exactly how many), the same "one
                # stage() bounds a variable-count-of-calls phase" shape W1/W2 already use for the
                # retrieval rounds. Never reproduces any of Phase-19's own scope/fingerprint/
                # memoization/failure-fallback logic here.
                with stage("U1", "W") as entry:
                    sufficiency_map_initial = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
                        early_sealed,
                        sufficiency_contract,
                        sufficiency_parent_of or {},
                        model_client=sufficiency_u1_model_client,
                        nomination_context=sufficiency_u1_context,
                    )
                    sufficiency_diagnostic.compute_direction_and_effectiveness(early_sealed, sufficiency_map_initial)
                    entry["detail"] = _nomination_pass_summary(sufficiency_u1_context)
            else:
                started = time.monotonic()
                sufficiency_map_initial = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
                    early_sealed, sufficiency_contract, sufficiency_parent_of or {}
                )
                sufficiency_diagnostic.compute_direction_and_effectiveness(early_sealed, sufficiency_map_initial)
                stage_log.append(
                    {
                        "stage": "U1",
                        "role": "U",
                        "binding": {"kind": "deterministic_sufficiency_mapping", "model": None},
                        "swap_seconds": 0.0,
                        "wall_seconds": round(time.monotonic() - started, 3),
                    }
                )
            # Phase 20b §9: an explicit, immutable snapshot -- never the live, still-mutable U1
            # context object itself -- so a later U2 pass can hold these decisions fixed without
            # any possibility of mutating the authoritative U1 receipt record.
            if sufficiency_u1_context is not None:
                sufficiency_u1_receipts_snapshot = dict(sufficiency_u1_context["in_pass_receipts"])

        gaps = [row for row in coverage_initial["obligations"] if row["state"] != stages.JUDGED_RESPONSIVE]
        if smoke.get("max_recovery_gaps"):
            gaps = gaps[: smoke["max_recovery_gaps"]]
        # Sufficiency-driven recovery gating (item (B)): OFF by default, and a wholly separate
        # opt-in from the diagnostic pass above -- a `judged_responsive`-but-incomplete child
        # additionally becomes a gap only when the caller has explicitly turned this on AND
        # supplied a sufficiency contract. `sufficiency_recovery_targets.compute_recovery_targets`
        # (Phase 12) replaces the earlier child-level boolean collapse Phase 11's own audit found
        # sufficiency-blind: each distinct semantic search obligation -- a missing role, an
        # unsatisfied alternative group, an unverified relationship, open_list breadth, an
        # at_least_n deficit, or a provisional-fill corroboration (possibly redirected to its true
        # upstream origin) -- becomes its own synthetic obligation row, with a role-aware hint in
        # `display`/`note` instead of the generic coverage note. A structured target's own
        # `field_id`/`subquestion_id` is its SEARCH OWNER's real child id (never a fresh per-target
        # id) -- `cli._recover`'s own obligation-filtering needs that to resolve the right
        # subquestion text (verified end to end: `gaps` carries no internal dedup by field_id, so
        # several structured rows sharing one child's id execute as independent searches, each
        # correctly accounted). Per-target identity instead rides the inert `_recovery_target_id`
        # key, read back afterward for reporting, never consulted by `_recover` itself. A
        # structured target is appended REGARDLESS of whether the generic pass already gapped the
        # same child -- Phase 11 found the generic query itself sufficiency-blind, so "this child
        # is already being searched generically" says nothing about whether this SPECIFIC role/
        # instance/relationship obligation is being searched for; suppressing here would silently
        # discard exactly the precision this mechanism exists to add.
        # `compute_recovery_targets`'s own target_id-based dedup is this round's complete
        # one-attempt-per-target budget; persisting attempts across REPEATED calls (a future
        # multi-round increment) is left unbuilt here, the same disclosed scope boundary the prior
        # boolean gate already carried.
        # Phase 22: pre-initialized to `None` (never computed) whenever the gate is off, so the
        # U2 seam below can tell "no recovery round was ever authorized to generate targets" apart
        # from "a round ran and genuinely found zero obligations" without a second flag or branch.
        recovery_targets_initial = None
        if sufficiency_recovery_gate_enabled and sufficiency_map_initial is not None:
            recovery_targets_initial = sufficiency_recovery_targets.compute_recovery_targets(
                sufficiency_map_initial, sufficiency_parent_of or {}
            )
            for target in recovery_targets_initial.values():
                hint = sufficiency_recovery_targets.recovery_query_hint(target, sufficiency_map_initial)
                gaps.append(
                    {
                        "field_id": target["search_child_id"],
                        "subquestion_id": target["search_child_id"],
                        "display": hint,
                        "note": hint,
                        "_recovery_target_id": target["target_id"],
                    }
                )
        if not coverage_initial["assessed"]:
            plan_record = {
                "source": profile.P.kind,
                "state": "skipped",
                "plan": {},
                "reason_code": "coverage_not_assessed",
            }
            skip("P1", "coverage_not_assessed")
        elif not gaps:
            plan_record = {
                "source": profile.P.kind,
                "state": "skipped",
                "plan": {},
                "reason_code": "no_unresolved_items",
            }
            skip("P1", "no_unresolved_items")
        else:
            with stage("P1", "P"):
                if profile.P.kind == "legacy":
                    plan_record = stages.legacy_plan(obligations)
                else:
                    plan_record = stages.run_recovery_plan(
                        bound.supervisors["P"],
                        question=question,
                        obligations=obligations,
                        subquestions=subquestions,
                        records=sink.all_records,
                        coverage=coverage_initial,
                    )

        plan = plan_record["plan"]
        planned_search = [g["field_id"] for g in gaps if plan.get(g["field_id"]) in cli._SEARCH_ACTIONS]
        recovery_log: list[dict] = []
        coverage_final = coverage_initial
        sealed_initial = None  # Phase 17 §E: set only when a round genuinely adds new evidence
        if planned_search:
            before = len(stages.source_verified(sink.all_records))
            with stage("W2", "W"):
                recovery_log = _recover_round(
                    conn,
                    rt=rt,
                    qwen=bound.qwen,
                    subquestions=subquestions,
                    gaps=gaps,
                    plan=plan,
                    sink=sink,
                    trace=trace,
                )
            if len(stages.source_verified(sink.all_records)) > before:
                responsiveness("R2")
                # Phase 17 §A/§C/§E: strict append-only C2 sealing. `sealed_initial` is C1's own
                # ledger, sealed purely/locally (no model call) from the EXACT pre-recovery
                # snapshot; `verify_stable_prefix_and_new_pids` proves the old pids still name the
                # same physical records and returns exactly the new suffix BEFORE any C2 model
                # call is made (fails closed, not after a wasted call); C2 then classifies only
                # that new suffix against the FULL obligation set (never narrowed to the
                # triggering child -- §G), and the final `seal()` below merges old-preserved +
                # new-classified into one cumulative ledger.
                sealed_initial = stages.seal(
                    contract, subquestions, pre_recovery_records, sink.evidence_packets, coverage_initial
                )
                new_pids = stages.verify_stable_prefix_and_new_pids(sealed_initial, sink.all_records)
                coverage_final = coverage("C2", classify_pids=new_pids)
            else:
                if "R" in bound.supervisors:
                    skip("R2", "no_new_source_verified_evidence")
                skip("C2", "no_new_source_verified_evidence")
        elif plan_record["state"] == "planned":
            skip("W2", "no_search_action_planned")
        elif plan_record["state"] == "no_answer":
            skip("W2", "recovery_plan_no_answer")

    sealed = stages.seal(
        contract, subquestions, sink.all_records, sink.evidence_packets, coverage_final, prior_sealed=sealed_initial
    )
    sealed_hash = hashlib.sha256(json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    sufficiency_map_final = sufficiency_map_initial
    sufficiency_u2_context = None  # stays None unless the block below actually recomputes U2
    # Phase 24: minimal additive manifest diagnostic (§12) -- None whenever U2 never recomputes at
    # all (byte-identical absence to sufficiency_u2_context above), never a reimplementation of F
    # itself (the real frozenset lives only in sufficiency_u2_fresh_request_keys below).
    sufficiency_u2_fresh_request_key_count = None
    if (
        sufficiency_contract is not None
        and contract.get("version") == hierarchy_contract.HIER_VERSION
        and planned_search
    ):
        # Only re-run when the recovery round actually added anything (mirrors the existing
        # R2/C2 gate exactly, e2e.py's own `if len(...) > before:` check above) -- otherwise the
        # initial map is already the final one and re-running would be wasted, identical work.
        started = time.monotonic()
        sufficiency_u2_fresh_request_keys: frozenset = frozenset()
        if sufficiency_u1_model_client is not None:
            # Phase 22: target-scoped post-recovery remap. `recovery_targets_initial` is `None`
            # whenever the gate was off (§22 pre-initialization above) -- the ONLY gate this
            # capability rides; no second feature flag. When it IS populated, derive the exact,
            # finite fresh-request set F this one targeted pass may authorize:
            #   1. a candidate-construction-only dry pass (no network, no live call) enumerates
            #      every (scope, request_context) the POST-RECOVERY evidence can reach --
            #      `_sufficiency_post_recovery_request_inventory`, the identical technique Phase
            #      21's own offline call-cap derivation used;
            #   2. `sufficiency_recovery_targets.project_fresh_request_keys` -- a pure function,
            #      no model call, no mutation -- projects the ORIGINAL (pre-recovery) targets onto
            #      that inventory, using `sufficiency_map_initial` (never the dry pass's own
            #      final, model-output-dependent instance tree) as the sole authority for which
            #      existing requests are already settled.
            # `exact_request_set_policy(F)` is the ONLY policy used here regardless of gate state
            # -- when the gate was off (or a round ran but genuinely found zero targets), F is
            # simply empty, which authorizes nothing: byte-identical in EFFECT to Phase 20b/21's
            # own `exact_scope_set_policy(set())`, just expressed through the one unified,
            # request-granular policy kind rather than two different "authorize nothing" shapes.
            if recovery_targets_initial:
                post_recovery_keys = _sufficiency_post_recovery_request_inventory(
                    sealed, sufficiency_contract, sufficiency_parent_of or {}
                )
                initial_keys = frozenset((sufficiency_u1_receipts_snapshot or {}).keys())
                sufficiency_u2_fresh_request_keys = sufficiency_recovery_targets.project_fresh_request_keys(
                    recovery_targets_initial,
                    sufficiency_contract,
                    sufficiency_map_initial,
                    initial_keys,
                    post_recovery_keys,
                )
            sufficiency_u2_context = mscope.new_nomination_context(
                mscope.exact_request_set_policy(sufficiency_u2_fresh_request_keys),
                prior_receipts=sufficiency_u1_receipts_snapshot,
            )
        sufficiency_u2_fresh_request_key_count = len(sufficiency_u2_fresh_request_keys)
        sufficiency_map_final = sufficiency_diagnostic.compute_diagnostic_sufficiency_map(
            sealed,
            sufficiency_contract,
            sufficiency_parent_of or {},
            model_client=sufficiency_u1_model_client,
            nomination_context=sufficiency_u2_context,
        )
        sufficiency_diagnostic.compute_direction_and_effectiveness(sealed, sufficiency_map_final)
        if sufficiency_u2_context is not None:
            # Hard call-budget assertion (audit §19/§20): no physical fresh attempt may ever occur
            # for a key outside the precomputed F -- authorization is a pure membership check
            # (`exact_request_set_policy`), so this should be structurally impossible; asserted
            # anyway as the same bounded-run discipline Phase 21's own precomputed cap enforced.
            fresh_attempted_statuses = {
                "fresh",
                "fresh_no_candidates",
                "fresh_failed_fallback_to_prior",
                "fresh_failed_no_valid_prior",
            }
            actual_fresh_keys = frozenset(
                key
                for key, receipt in sufficiency_u2_context["in_pass_receipts"].items()
                if receipt["status"] in fresh_attempted_statuses
            )
            if not actual_fresh_keys <= sufficiency_u2_fresh_request_keys:
                raise RuntimeError(
                    f"Phase-22 U2 call-budget violation: {actual_fresh_keys - sufficiency_u2_fresh_request_keys!r} "
                    "made a fresh attempt outside the precomputed authorized set F -- authorization is a pure "
                    "membership check against F, so this indicates a real bug, never an evidence/policy edge case."
                )
        u2_entry = {
            "stage": "U2",
            "role": "U",
            # Deliberately NEVER wrapped in stage("U2", "W"): held-fixed replay carries no model
            # residency cost; a targeted remap's own fresh calls are small and bounded by |F| --
            # neither case needs the W-role residency guard a variable-count-of-calls PHASE would
            # (unlike U1, which can genuinely swap W's residency for the duration of its pass).
            # Honestly labelled by what actually happened this pass, never a fixed string: zero
            # fresh keys this time is "held fixed," one or more is a genuine targeted remap.
            "binding": (
                {"kind": "deterministic_sufficiency_mapping", "model": None}
                if sufficiency_u1_model_client is None
                else {
                    "kind": (
                        "sufficiency_model_assist_held_fixed"
                        if not sufficiency_u2_fresh_request_keys
                        else "sufficiency_model_assist_targeted_remap"
                    ),
                    "model": sufficiency_u1_model_client.model_name,
                    "fresh_request_count": len(sufficiency_u2_fresh_request_keys),
                }
            ),
            "swap_seconds": 0.0,
            "wall_seconds": round(time.monotonic() - started, 3),
        }
        if sufficiency_u2_context is not None:
            u2_entry["detail"] = _nomination_pass_summary(sufficiency_u2_context)
        stage_log.append(u2_entry)
    # Same primitive as the pre-round call above, re-run against the (possibly recovery-updated)
    # final map -- one shared function, two call sites, never two independently-computed
    # recovery-need checks (the prior design's own redundancy, closed by Phase 12).
    recovery_targets_final = (
        sufficiency_recovery_targets.compute_recovery_targets(sufficiency_map_final, sufficiency_parent_of or {})
        if sufficiency_map_final is not None
        else {}
    )
    overview_record, reasoning = None, ""
    child_overview_manifest: dict[str, dict] | None = None
    if "S" in bound.supervisors:
        if contract.get("version") == hierarchy_contract.HIER_VERSION:
            # Stage B (2026-09-29 authorization): one screened Overview per approved child, from a
            # strictly-filtered (per hierarchy_contract.build_child_sealed_ledger) child-scoped sealed
            # ledger -- never one flat call over the whole 11-child ledger, which would be exactly the
            # parent-level meta-synthesis this architecture does not yet authorize. The top-level
            # 14_final_answer.md (built below via render_answer(sealed), unchanged) stays the
            # deterministic, hierarchy-aware rendering; these are additional, separately-named,
            # per-child artifacts alongside it -- overview.build_overview/overview_render/overview_audit
            # are reused completely unmodified, generic over whatever sealed ledger they're handed.
            child_overview_manifest = {}
            for sq in subquestions:  # subquestion_id == child_id in the hierarchical arm
                child_id = sq["subquestion_id"]
                child_sealed = hierarchy_contract.build_child_sealed_ledger(sealed, child_id)
                child_hash = hashlib.sha256(
                    json.dumps(child_sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                with stage(f"S1:{child_id}", "S") as entry:
                    child_record, child_reasoning = overview.build_overview(
                        child_sealed, child_hash, supervisor=bound.supervisors["S"], entail=entail
                    )
                    entry["detail"] = overview.stage_detail(child_record)
                record_file = f"14a_overview.{child_id}.json"
                answer_file = f"14_final_answer.{child_id}.md"
                detail_file = f"14b_detailed_inspection.{child_id}.md"
                # detail_file/record_file: purely referential -- the footer names the real per-child
                # file that will actually exist on disk (written just below), not the generic flat-run
                # name researcher_answer defaults to.
                answer_text, _ = overview_render.researcher_answer(
                    child_sealed, child_record, detail_file=detail_file, record_file=record_file
                )
                trace.write_json(record_file, child_record)
                if child_reasoning:
                    trace.write_report(f"14c_overview_reasoning.{child_id}.txt", [child_reasoning])
                answer_path = trace.write_report(answer_file, [answer_text.rstrip("\n")])
                detail_path = trace.write_report(
                    detail_file, [overview_render.detailed_inspection(child_sealed, child_record).rstrip("\n")]
                )
                child_audit = overview_audit.audit_overview(
                    child_sealed,
                    child_hash,
                    child_record,
                    answer_path.read_text(encoding="utf-8"),
                    detail_path.read_text(encoding="utf-8"),
                    detail_file=detail_file,
                    record_file=record_file,
                )
                child_overview_manifest[child_id] = {
                    "sealed_ledger_hash": child_hash,
                    "state": child_record["state"],
                    "record_file": record_file,
                    "answer_file": answer_file,
                    "detail_file": detail_file,
                    "overview_audit": child_audit,
                }
            trace.write_json("14_child_overview_manifest.json", child_overview_manifest)
        else:
            # After the last coverage stage, over the SEALED ledger, which this never modifies: the overview is a
            # separate, separately hashed artifact that references the ledger hash.
            with stage("S1", "S") as entry:
                overview_record, reasoning = overview.build_overview(
                    sealed, sealed_hash, supervisor=bound.supervisors["S"], entail=entail
                )
                entry["detail"] = overview.stage_detail(overview_record)
    parent_synthesis_result = None
    if parent_synthesis_enabled and contract.get("version") == hierarchy_contract.HIER_VERSION:
        parent_synthesis_result = _parent_synthesis_outputs(
            trace=trace,
            stage=stage,
            bound=bound,
            sealed=sealed,
            sealed_hash=sealed_hash,
            sufficiency_map_final=sufficiency_map_final,
            recovery_targets_final=recovery_targets_final,
            question=question,
            entail=entail,
        )
    text, render_manifest = render_answer(sealed)

    trace.write_json("02_direct_papers.json", sink.direct_papers)
    trace.write_json("03_axis_nominations.json", sink.axis_noms)
    trace.write_json("05_candidate_papers.json", sink.candidate_papers)
    trace.write_jsonl("06_chunk_retrieval.jsonl", sink.chunk_hits)
    trace.write_jsonl("07_context_growth.jsonl", sink.context_growth)
    trace.write_jsonl("08_evidence_packets.jsonl", sink.evidence_packets)
    trace.write_jsonl("09_propositions.jsonl", sink.propositions)
    trace.write_jsonl("10_verification.jsonl", sink.verifications)
    trace.write_json("12_coverage_audit.initial.json", coverage_initial)
    trace.write_json("12_coverage_audit.json", coverage_final)
    if sufficiency_map_initial is not None:
        trace.write_json("17_sufficiency_map.initial.json", sufficiency_map_initial)
    if sufficiency_map_final is not None:
        trace.write_json("17_sufficiency_map.json", sufficiency_map_final)
    if sufficiency_u1_context is not None:
        # Phase 20b §13: the next non-colliding artifact number after Phase 20a's own "17_*" pair.
        # Structured, inspectable fields only (scope/model/fingerprint/candidates/accepted/status
        # -- exactly `new_nomination_receipt`'s own shape, which carries no chain-of-thought or raw
        # model text to begin with). `final` is `null` whenever U2 never ran (no recovery activity)
        # or ran fully held-fixed with no context of its own (never reached here, since a context
        # is only ever absent when model assistance itself is off, which this whole block is
        # already gated on) -- in Phase 20b it is always present once U2 actually recomputes.
        trace.write_json(
            "18_sufficiency_model_assist.json",
            {
                "enabled": True,
                "model_name": sufficiency_u1_model_client.model_name,
                "think": profile.W.think,
                "initial": list(sufficiency_u1_context["in_pass_receipts"].values()),
                "final": (
                    list(sufficiency_u2_context["in_pass_receipts"].values())
                    if sufficiency_u2_context is not None
                    else None
                ),
            },
        )
    trace.write_json("13_recovery_plan.json", {**plan_record, "unresolved_items": [g["field_id"] for g in gaps]})
    trace.write_json("13_gap_recovery.json", recovery_log)
    trace.write_json("11_verified_ledger.json", {**sealed, "sealed_hash": sealed_hash})
    if overview_record is None:
        final_path = trace.write_report("14_final_answer.md", [text.rstrip("\n")])
        trace.write_json("14_render_manifest.json", render_manifest)
        final_audit = audit_final(sealed, final_path.read_text(encoding="utf-8"))
    else:
        # Two files: the researcher-facing answer, and the detailed inspection (the ledger rendering, unchanged, plus the
        # construction record). Nothing is dropped; the second file is where every exclusion and receipt lives.
        answer_text, answer_manifest = overview_render.researcher_answer(sealed, overview_record)
        trace.write_json(overview_render.RECORD_FILE, overview_record)
        if reasoning:
            trace.write_report("14c_overview_reasoning.txt", [reasoning])  # private: model reasoning over library text
        answer_path = trace.write_report(overview_render.ANSWER_FILE, [answer_text.rstrip("\n")])
        detail_path = trace.write_report(
            overview_render.DETAIL_FILE, [overview_render.detailed_inspection(sealed, overview_record).rstrip("\n")]
        )
        trace.write_json("14_render_manifest.json", {**render_manifest, "researcher_answer": answer_manifest})
        final_audit = audit_final(sealed, text)
        final_audit["overview_audit"] = overview_audit.audit_overview(
            sealed,
            sealed_hash,
            overview_record,
            answer_path.read_text(encoding="utf-8"),
            detail_path.read_text(encoding="utf-8"),
        )
    trace.write_json("14_final_audit.json", final_audit)
    trace.write_json("stage_log.json", {"stages": stage_log, "skipped": skipped})
    trace.flush_qwen()
    trace.flush_events()
    result_out = {
        "sealed": sealed,
        "sealed_hash": sealed_hash,
        "stage_log": stage_log,
        "skipped": skipped,
        "recovery_plan": plan_record,
        "recovery_log": recovery_log,
        "coverage_initial": coverage_initial,
        "coverage_final": coverage_final,
        "final_audit": final_audit,
        "render_manifest": render_manifest,
        "overview": overview_record,
        "child_overview_manifest": child_overview_manifest,  # Stage B: None for a non-hierarchical run
        "sufficiency_map_initial": sufficiency_map_initial,  # None unless a sufficiency_contract was supplied
        "sufficiency_map_final": sufficiency_map_final,
        # what WOULD trigger recovery if the gate were on -- structured RecoveryTargets (Phase 12),
        # not the earlier child-level boolean shape; key renamed from the prior
        # "sufficiency_recovery_candidates" since the shape itself changed (confirmed by grep: no
        # consumer outside this file parses the old key/shape).
        "sufficiency_recovery_targets": recovery_targets_final,
        # Phase 24 (§12, minimal additive manifest diagnostics): the BEFORE-recovery inventory
        # execute() already computes internally for injection into `gaps` -- exposed here so a
        # caller (run_topology()'s own manifest; Phase 23's harness previously had to recompute
        # this post-hoc, read-only, via a second call to the same pure function) never needs to
        # reimplement or re-derive it. `None` exactly when the gate never ran (byte-identical to
        # the pre-Phase-24 absence of this key).
        "sufficiency_recovery_targets_initial": recovery_targets_initial,
        # Phase 24 (§12/§13): |F|'s own count only -- never the raw key set (that stays exclusively
        # in the "18_sufficiency_model_assist.json" trace artifact's receipts). Named precisely per
        # Phase 23a's corrected terminology: this is the fresh-AUTHORIZED request-key count, not a
        # physical-call count (`sufficiency_model_assist.final.by_status` already carries the
        # fresh/fresh_no_candidates/held_fixed breakdown whenever model assistance is on).
        "sufficiency_u2_fresh_request_key_count": sufficiency_u2_fresh_request_key_count,
        # Phase 20b: internal run diagnostics only (audit §14) -- never user-facing prose. `None`
        # unless model assistance actually ran (byte-identical absence to every pre-Phase-20b
        # caller, including Phase 20a's own deterministic-only path).
        "sufficiency_model_assist": (
            {
                "enabled": True,
                "model_name": sufficiency_u1_model_client.model_name,
                "think": profile.W.think,
                "initial": _nomination_pass_summary(sufficiency_u1_context),
                "final": _nomination_pass_summary(sufficiency_u2_context),
            }
            if sufficiency_u1_model_client is not None
            else None
        ),
        "supervisor_records": {role: sup.records for role, sup in bound.supervisors.items()},
        "records_total": len(sink.all_records),
    }
    if parent_synthesis_result is not None:
        result_out["parent_synthesis"] = parent_synthesis_result
    return result_out


def _parent_synthesis_outputs(
    *, trace, stage, bound, sealed, sealed_hash, sufficiency_map_final, recovery_targets_final, question, entail
) -> dict:
    """Phase 27: the bounded parent realization, run after every child stage and the final sufficiency state.
    It writes only the additive 15* artifacts. It never feeds search, recovery, U2, the sufficiency state or the
    per-child Overview back, and it never replaces the top-level 14_final_answer.md."""
    if sufficiency_map_final is None:
        record = parent_synthesis_render.declined_record(reason="no_sufficiency_map", sealed_hash=sealed_hash)
        trace.write_json(parent_synthesis_render.RECORD_FILE, record)
        return {"record": record}
    claims = parent_synthesis_ledger.build_claim_ledger(sufficiency_map_final, sealed)
    gaps = parent_synthesis_ledger.build_gap_report(recovery_targets_final, sufficiency_map_final=sufficiency_map_final)
    realization = parent_synthesis.realize(
        claims,
        sealed,
        supervisor=bound.supervisors.get("S"),
        entail=entail,
        question=question,
        call_context=lambda: stage(parent_synthesis.STAGE_LABEL, "S"),
    )
    record = parent_synthesis_render.construction_record(
        claims,
        gaps,
        sealed_hash=sealed_hash,
        sufficiency_map_hash=parent_synthesis_ledger.sufficiency_map_hash(sufficiency_map_final),
        realization=realization,
    )
    answer = parent_synthesis_render.render_answer(
        claims,
        gaps,
        realized_text={s["claim_id"]: s["final_text"] for s in realization["segments"]},
        cite=True,
    )
    trace.write_json(parent_synthesis_render.RECORD_FILE, record)
    trace.write_report(parent_synthesis_render.ANSWER_FILE, [answer.rstrip("\n")])
    trace.write_report(
        parent_synthesis_render.INSPECTION_FILE,
        [parent_synthesis_render.render_inspection(claims, gaps, realization).rstrip("\n")],
    )
    audit = parent_synthesis_audit.audit_parent_synthesis(sufficiency_map_final, sealed, recovery_targets_final, record)
    return {"record": record, "audit": audit}


# ---- the guarded run ---------------------------------------------------------------------------------------------------


class ModelMissingError(RuntimeError):
    """A model the profile binds is not installed on the Ollama endpoint it is bound to."""


def require_models(clients: dict, profile: topo.Profile) -> dict[str, str]:
    """Digest of every bound model, or ``ModelMissingError`` naming what is absent and where (before any work starts)."""
    listed: dict[str, dict[str, str]] = {}
    for endpoint, client in clients.items():
        digests = {}
        for entry in client.tags():
            name = entry.get("name") or entry.get("model")
            digests[name] = entry.get("digest")
            if name.endswith(":latest"):  # an untagged alias is listed with its implicit tag
                digests[name[: -len(":latest")]] = entry.get("digest")
        listed[endpoint] = digests
    found, missing = {}, []
    for role in _roles(profile):
        target = _endpoint_model(getattr(profile, role))
        if target is None:
            continue
        endpoint, model = target
        if model in listed[endpoint]:
            found[model] = listed[endpoint][model]
        else:
            missing.append(f"{model} (endpoint {endpoint}, role {role})")
    if missing:
        raise ModelMissingError("bound model(s) not installed: " + "; ".join(missing))
    return found


def _versions(clients: dict) -> dict:
    versions = {}
    for endpoint, client in clients.items():
        with contextlib.suppress(Exception):
            versions[endpoint] = client.version()
    return versions


def _default_sufficiency_loader(contract: dict) -> tuple[dict | None, dict | None]:
    """Phase 20a's default ``sufficiency_loader``: sources the frozen, human-reviewed sufficiency
    contract (``sufficiency_freeze.load_verified``) and derives its parent map structurally from
    this exact hierarchy contract's own ``child["parent"]`` field (``hierarchy_contract.
    parent_of``) -- one source of truth for each, never a second, independently-maintained copy.

    Returns ``(None, None)`` when no sufficiency contract has been authored/frozen for this
    question at all (today, every question except q_aib) -- a benign absence, not an error:
    ``execute()`` already treats ``sufficiency_contract=None`` as "deterministic sufficiency
    mapping is simply not run for this question", exactly as before Phase 20a existed. An
    existing-but-unverifiable frozen artifact (a tampered hash, a missing/mismatched review) is
    NOT swallowed here -- ``sufficiency_freeze.load_verified`` raises
    ``SufficiencyContractRejected``, which propagates and fails the run loudly, the same
    fail-closed posture every other contract/pin/authorization check in this module already has.
    """
    contract_by_child = sufficiency_freeze.load_verified()
    if contract_by_child is None:
        return None, None
    return contract_by_child, hierarchy_contract.parent_of(contract)


def run_topology(
    profile_name: str,
    question_key: str,
    *,
    db_path,
    library_frozen,
    out_dir,
    git_root,
    scored: bool = True,
    smoke_limits: dict | None = None,
    smoke_seed=None,
    hierarchy: bool = False,
    experiment_authorization=None,
    hierarchy_loader=None,
    authorization_checker=None,
    sufficiency_loader=_default_sufficiency_loader,
    sufficiency_model_assist: bool = False,
    sufficiency_recovery_gate: bool = False,
    parent_synthesis: bool = False,
    git_state_fn=provenance.git_state,
    verify_library=library_copy.verify,
    verify_contracts=e2e_contracts.verify_frozen,
    runtime_factory=build_runtime,
    client_factory=OllamaClient,
    managed_chat=backends.ManagedLocalChat,
    sampler=None,
) -> dict:
    """One arm on one question. Refuses to start unless every comparison precondition holds; returns the manifest."""
    if scored and (smoke_limits or smoke_seed):
        raise ValueError("a scored run may not carry smoke limits or a seeded ledger")
    # A hierarchical run is verified and gated FIRST: nothing below (git, library, models, runtime, trace directory) runs until it passes.
    if sufficiency_model_assist and not hierarchy:
        # Phase 20b §2/§21: validated here too, independently of parse_args' own `--hierarchy`
        # combo check -- run_topology() is a real, directly-callable unit (every *RefusalTests
        # class in this file calls it without going through the CLI parser at all), so it must
        # not depend on the CLI layer alone to enforce its own preconditions.
        raise ValueError("--sufficiency-model-assist requires --hierarchy")
    if sufficiency_recovery_gate and not hierarchy:
        # Phase 24: the same independent-of-the-CLI-parser precondition as the model-assist check
        # above, for the same reason. Deliberately NOT required to pair with sufficiency_model_
        # assist -- execute()'s own recovery-gate block only depends on sufficiency_map_initial
        # existing, which a deterministic-only (model-assist-off) sufficiency pass already
        # produces; recovery and model assistance are independent capabilities (Phase 24 audit).
        raise ValueError("--sufficiency-recovery requires --hierarchy")
    if parent_synthesis and not hierarchy:
        # Phase 27: the same independent-of-the-CLI-parser precondition as the flags above.
        raise ValueError("--parent-synthesis requires --hierarchy")
    hier_contract = None
    if hierarchy:
        if question_key != "aib":
            raise ValueError("only the aib request has an approved hierarchy")
        if smoke_seed or any(k in (smoke_limits or {}) for k in ("max_initial_subquestions", "max_recovery_gaps")):
            raise ValueError("a hierarchical run may not slice its children or seed its claims")
        hier_question = e2e_contracts.E2E_QUESTIONS["aib"]
        hier_contract = (hierarchy_loader or hierarchy_contract.load_contract_for_live)(hier_question)
        (authorization_checker or hierarchy_contract.check_authorization)(experiment_authorization, hier_question)
    effective_key = hierarchy_contract.HIER_QUESTION_KEY if hierarchy else question_key
    profile = topo.resolve_profile(profile_name)
    question = e2e_contracts.E2E_QUESTIONS[question_key]
    verify_contracts()
    git = git_state_fn(git_root)
    if scored:
        provenance.assert_clean(git)
    library_before = verify_library(db_path, library_frozen)

    contract = hier_contract if hierarchy else build_request_contract(question)
    # Phase 20a: the deterministic sufficiency-mapping block inside execute() has existed since an
    # earlier phase but was never reachable from this real topology path -- sufficiency_contract/
    # sufficiency_parent_of simply weren't sourced or threaded through. Sourced ONLY for a
    # hierarchical run (sufficiency is a hierarchy-specific concept today, exactly like `contract`
    # itself); a non-hierarchical run's behavior is completely unchanged (both stay None, same as
    # before this phase). `sufficiency_model_assist` (Phase 20b) is a bare bool threaded straight
    # into execute() unchanged -- run_topology() never constructs a model_client or
    # nomination_context itself; execute()'s own `_sufficiency_u1_context` is the single
    # enforcement point for that invariant, regardless of which caller reaches it.
    sufficiency_contract = sufficiency_parent_of = None
    if hierarchy:
        sufficiency_contract, sufficiency_parent_of = sufficiency_loader(contract)
    trace = TraceWriter(out_dir)
    trace.write_json(
        "00_question.json", {"question_key": effective_key, "question": question, "hash": contract["question_hash"]}
    )
    seed_pass = seed_pass_from(smoke_seed) if smoke_seed else None
    clients = {endpoint: client_factory(topo.ENDPOINTS[endpoint]) for endpoint in endpoints_used(profile)}

    def close_clients() -> None:
        for client in clients.values():
            with contextlib.suppress(Exception):
                client.close()

    try:
        digests = require_models(clients, profile)
    except Exception:
        close_clients()
        raise
    needs_qwen = any(getattr(profile, role).kind == "managed_local" for role in _roles(profile))
    try:
        rt = runtime_factory(db_path, want_verifier=True, want_qwen=needs_qwen)
    except QwenUnavailableError as exc:
        close_clients()
        trace.write_json("BLOCKED.json", {"blocked": True, "reason": str(exc)})
        return {"blocked": True, "reason": str(exc)}
    guard = backends.ResidencyGuard(clients)
    started = time.monotonic()
    issues: list[str] = []
    sampler_summary = None
    result = None
    try:
        bound = bind(profile, rt=rt, clients=clients, trace=trace, managed_chat=managed_chat)
        versions = _versions(clients)
        if sampler is not None:
            sampler.start(f"{profile_name}-{question_key}")
        try:
            with smoke_caps(smoke_limits):
                caps = _caps()
                result = execute(
                    rt=rt, profile=profile, contract=contract, trace=trace, guard=guard, bound=bound,
                    smoke_limits=smoke_limits, seed_pass=seed_pass,
                    # the local NLI scorer the run already uses for claim verification; screens the overview's statements
                    entail=rt.verifier.support_scorer.support_and_contradiction_many if profile.S.kind != "off" else None,
                    sufficiency_contract=sufficiency_contract, sufficiency_parent_of=sufficiency_parent_of,
                    sufficiency_model_assist_enabled=sufficiency_model_assist,
                    sufficiency_recovery_gate_enabled=sufficiency_recovery_gate,
                    parent_synthesis_enabled=parent_synthesis,
                )  # fmt: skip
        except Exception as exc:
            trace.write_json("RUN_FAILED.json", {"error_type": type(exc).__name__, "message": str(exc)[:500]})
            raise
        finally:
            if sampler is not None:
                sampler_summary = sampler.stop()
    finally:
        with contextlib.suppress(Exception):
            guard.release_all()
        close_clients()
        rt.close()

    try:
        library_after = verify_library(db_path, library_frozen)
    except library_copy.LibraryCopyDrift as exc:
        library_after = None
        issues.append(f"library_copy_drift_after_run: {exc}")

    report = e2e_checks.mechanical_report(trace.dir, profile=profile, question_key=effective_key)
    trace.write_json("16_mechanical_checks.json", report)
    issues += report["technical_validity"]["issues"]

    manifest = {
        "created": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "name": profile.name,
            **{role: _binding_record(getattr(profile, role)) for role in _roles(profile)},
        },
        "question_key": effective_key,
        "question_hash": contract["question_hash"],
        "model_facing_sha256": (
            hierarchy_contract.model_facing_sha256(contract)
            if hierarchy
            else e2e_contracts.frozen_record(question)["model_facing_sha256"]
        ),
        "scored": scored,
        "smoke_limits": smoke_limits,
        "git": git,
        "library": library_before,
        "library_unchanged_after_run": library_after == library_before,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "ollama_versions": versions,
        "model_digests": digests,
        "caps": caps,
        "supervisor_base_options": topo.SUPERVISOR_BASE_OPTIONS,
        "keep_alive": topo.KEEP_ALIVE,
        "wall_timeout_seconds": topo.WALL_TIMEOUT_SECONDS,
        "stage_log": result["stage_log"],
        "skipped": result["skipped"],
        "residency_events": guard.events,
        "residency_observations": guard.observations,
        "sealed_hash": result["sealed_hash"],
        "records_total": result["records_total"],
        "verified_claims": len(result["sealed"]["verified_propositions"]),
        "sampler": sampler_summary,
        "mechanical_checks": {name: check["ok"] for name, check in report["checks"].items()},
        "gate_no_answer": report["no_answer"]["gate"],
        "technical_validity": {"valid": not issues, "issues": issues},
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    if hierarchy:
        manifest["request_kind"] = contract["version"]
        manifest["hierarchy"] = hierarchy_contract.manifest_record(contract)
        # Phase 20a: a thin presence/coverage summary only -- the full map is already the separate
        # "17_sufficiency_map.initial.json"/"17_sufficiency_map.json" trace artifacts execute()
        # itself writes (unchanged by this phase); duplicating the whole map into the manifest too
        # would be unrelated scope this phase doesn't need.
        manifest["sufficiency"] = {
            "contract_supplied": sufficiency_contract is not None,
            "mapped_children": sorted(result["sufficiency_map_initial"] or {}),
            # Phase 20b: None whenever model assistance didn't run -- byte-identical to Phase 20a's
            # own shape otherwise. The full per-scope receipts are the separate
            # "18_sufficiency_model_assist.json" trace artifact; this is only the thin summary
            # _nomination_pass_summary already computed inside execute() itself.
            "model_assist": result.get("sufficiency_model_assist"),
            # Phase 24: minimal additive reachability/activation diagnostics -- never a duplicate of
            # the detailed Phase-22 trace artifacts (the full RecoveryTarget/receipt detail stays in
            # "17_sufficiency_map.*.json"/"18_sufficiency_model_assist.json"). `requested` is the raw
            # flag this call received; `enabled` is whether the gate was actually live for this run
            # (requires a sufficiency map to have existed at all, exactly execute()'s own gating
            # condition); the remaining three are honest post-hoc observations of what happened, not
            # a re-derivation of recovery semantics.
            "recovery_gate_requested": sufficiency_recovery_gate,
            "recovery_gate_enabled": sufficiency_recovery_gate and result["sufficiency_map_initial"] is not None,
            "recovery_targets_initial_count": len(result.get("sufficiency_recovery_targets_initial") or {}),
            "recovery_round_executed": any(s["stage"] == "W2" for s in result["stage_log"]),
            "u2_fresh_request_key_count": result.get("sufficiency_u2_fresh_request_key_count"),
        }
    if result.get("overview") is not None:
        manifest["overview"] = overview.manifest_record(result["overview"])
    if parent_synthesis:
        # Phase 27: minimal additive diagnostics. The full construction record stays in 15a_parent_synthesis.json.
        ps_record = (result.get("parent_synthesis") or {}).get("record") or {}
        manifest["parent_synthesis"] = {
            "requested": True,
            "enabled": ps_record.get("realization_state") not in (None, "declined"),
            "realization_state": ps_record.get("realization_state"),
            "skip_reason": ps_record.get("skip_reason"),
            "call_attempted": ps_record.get("call_attempted", False),
            "fallback_used": ps_record.get("fallback_used", False),
            "claim_count": len(ps_record.get("claim_ledger", [])),
            "gap_count": len(ps_record.get("gap_report", [])),
            "grounded_segment_count": ps_record.get("grounded_count", 0),
            "fallback_segment_count": ps_record.get("fallback_count", 0),
        }
    trace.write_json("15_run_manifest.json", manifest)
    return manifest


# ---- command line --------------------------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
# Unscored plumbing smoke: the same code path over a sliver of the work. Recorded in the manifest, never scored.
SMOKE_LIMITS = {
    "per_subq_paper_cap": 4,
    "within_paper_top_k": 8,
    "max_initial_subquestions": 3,
    "max_recovery_gaps": 2,
}
# A hierarchical smoke may only lower the retrieval caps: slicing children or recovery gaps would silently drop approved children.
HIER_SMOKE_LIMITS = {
    "per_subq_paper_cap": SMOKE_LIMITS["per_subq_paper_cap"],
    "within_paper_top_k": SMOKE_LIMITS["within_paper_top_k"],
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=sorted(topo.profile_names()))
    parser.add_argument("--question", choices=sorted(e2e_contracts.E2E_QUESTIONS))
    parser.add_argument("--db", help="path to the frozen COPY of the library (never the live library)")
    parser.add_argument("--library-frozen", help="its frozen fingerprint (default: <db>.fingerprint.json)")
    parser.add_argument("--out", help="run directory (private; outside the repository tree)")
    parser.add_argument("--smoke", action="store_true", help="unscored plumbing smoke over a sliver of the work")
    parser.add_argument("--smoke-seed", help="with --smoke: an earlier run's ledger whose claims replace round-one W")
    parser.add_argument("--juno-sampler", action="store_true", help="sample JUNO GPU/RAM/swap around the run")
    parser.add_argument(
        "--hierarchy",
        action="store_true",
        help="run the approved v8 hierarchy of --question aib (verified first; needs reviewed pins)",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="with --hierarchy: verify readiness and print what the models would see; touches nothing",
    )
    parser.add_argument(
        "--experiment-authorization", help="authorization JSON for a live hierarchical run (see EXPERIMENT_GATE.md)"
    )
    parser.add_argument(
        "--sufficiency-model-assist",
        action="store_true",
        help=(
            "with --hierarchy: model-assisted initial sufficiency mapping through the Phase-19 "
            "nomination infrastructure (bound.qwen, ALL_ELIGIBLE U1 / held-fixed U2). Default off; "
            "requires the active W binding's thinking to be exactly False"
        ),
    )
    parser.add_argument(
        "--parent-synthesis",
        action="store_true",
        help=(
            "with --hierarchy: after the per-child stages and the final sufficiency state, make ONE bounded "
            "local S2 call that phrases the deterministic parent claim ledger, validating each claim against its "
            "own authorized evidence, with a deterministic fallback for every claim not validated. Default off."
        ),
    )
    parser.add_argument(
        "--sufficiency-recovery",
        action="store_true",
        help=(
            "with --hierarchy: let a missing/partial/provisional-corroboration requirement also "
            "drive one bounded recovery round via synthetic RecoveryTarget search gaps, then a "
            "Phase-22 target-scoped U2 remap. Default off. Independent of --sufficiency-model-assist "
            "(a deterministic-only sufficiency map can drive a recovery round on its own -- the "
            "model-assist flag only governs whether any role may be filled by model nomination at "
            "all, never whether recovery itself may run)"
        ),
    )
    args = parser.parse_args(argv)
    if args.smoke_seed and not args.smoke:
        parser.error("--smoke-seed requires --smoke")
    if args.preflight_only and not args.hierarchy:
        parser.error("--preflight-only requires --hierarchy")
    if args.hierarchy and args.question not in (None, "aib"):
        parser.error("--hierarchy is only approved for --question aib")
    if args.hierarchy and args.smoke_seed:
        parser.error("--smoke-seed cannot be combined with --hierarchy (it would replace approved children)")
    if args.sufficiency_model_assist and not args.hierarchy:
        parser.error("--sufficiency-model-assist requires --hierarchy")
    if args.sufficiency_recovery and not args.hierarchy:
        parser.error("--sufficiency-recovery requires --hierarchy")
    if args.parent_synthesis and not args.hierarchy:
        parser.error("--parent-synthesis requires --hierarchy")
    if not args.preflight_only:
        missing = [f"--{name}" for name in ("profile", "question", "db", "out") if getattr(args, name) is None]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
        args.library_frozen = args.library_frozen or f"{args.db}.fingerprint.json"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.hierarchy:
        # Verified and gated before ANY side effect, including the sampler's output directory below.
        hier_question = e2e_contracts.E2E_QUESTIONS["aib"]
        try:
            if args.preflight_only:
                print(
                    hierarchy_contract.preflight_report(hierarchy_contract.load_contract_for_preflight(hier_question))
                )
                if args.profile:
                    resolved = topo.resolve_profile(args.profile)
                    if resolved.S.kind != "off":
                        print("\n" + overview.preflight_report(resolved.S_options))
                return 0
            hierarchy_contract.load_contract_for_live(hier_question)
            hierarchy_contract.check_authorization(args.experiment_authorization, hier_question)
        except hierarchy_contract.HierarchyRejected as exc:
            print("[e2e] HIERARCHY REFUSED:")
            for problem in exc.problems:
                print(f"  - {problem}")
            return 3
        except hierarchy_contract.AuthorizationRefused as exc:
            print(f"[e2e] AUTHORIZATION REFUSED: {exc}")
            return 3
    sampler = None
    if args.juno_sampler:
        from experiments.ask_cli_revised.supervisor_eval.juno_resources import JunoSampler

        Path(args.out).mkdir(parents=True, exist_ok=True)
        sampler = JunoSampler(out_dir=Path(args.out))
    manifest = run_topology(
        args.profile,
        args.question,
        db_path=args.db,
        library_frozen=args.library_frozen,
        out_dir=args.out,
        git_root=ROOT,
        scored=not args.smoke,
        smoke_limits=(HIER_SMOKE_LIMITS if args.hierarchy else SMOKE_LIMITS) if args.smoke else None,
        smoke_seed=args.smoke_seed,
        hierarchy=args.hierarchy,
        experiment_authorization=args.experiment_authorization,
        sufficiency_model_assist=args.sufficiency_model_assist,
        sufficiency_recovery_gate=args.sufficiency_recovery,
        parent_synthesis=args.parent_synthesis,
        sampler=sampler,
    )
    if manifest.get("blocked"):
        print(f"[e2e] BLOCKED: {manifest['reason']}")
        return 2
    print(
        f"[e2e] {args.profile}/{args.question}: {manifest['records_total']} records "
        f"({manifest['verified_claims']} source-verified), "
        f"{manifest['elapsed_seconds']}s, technical validity {manifest['technical_validity']['valid']}, "
        f"gate NO ANSWER {manifest['gate_no_answer']['no_answer']}/{manifest['gate_no_answer']['calls']}"
    )
    return 0 if manifest["technical_validity"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
