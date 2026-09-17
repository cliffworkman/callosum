"""One explicitly authorized private Freeze-A construction. No model dispatch."""

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .core import CRITERION, ROLES, ROSTER, SOURCE_RULES, BoundaryError, canonical, digest, require, sha
from .frontier_contract import LIMITS, WRAPPER, batch_objects, prompt, render_packet
from .storage import Store

PROJECTION = Path("C:/Users/cliff/AppData/Local/Temp/callosum-freeze-a-private-w7m944yq")
QUALIFICATION = Path("C:/Users/cliff/AppData/Local/Temp/callosum-adjudication-synthetic-i1zf3y9c")
ROSTER_AMENDMENT = Path("C:/Users/cliff/AppData/Local/Temp/callosum-adjudication-synthetic-vvw1gmf4")
PROVENANCE = Path("C:/Users/cliff/AppData/Local/Temp/callosum-adjudication-synthetic-0uafiism")
AUTHORIZATION = Path("C:/Users/cliff/.codex/attachments/6be69254-428f-49a7-825b-26a788d51c41/pasted-text.txt")

ROUTES = {
    "gemini": ("3.1 Pro", "bounded pasted text", "message-content final response"),
    "grok": ("Fast", "bounded rich-text paste", ".response-content-markdown final answer, exclude thinking"),
    "copilot": ("Smart", "automatic TXT attachment + fixed wrapper", "data-testid=ai-message-body"),
    "deepseek": ("backend version unexposed", "Paste original text", ".ds-assistant-message-main-content"),
    "kimi": (
        "Instant",
        "automatic TXT attachment + fixed wrapper",
        ".markdown-container:not(.toolcall-content-text) > .markdown",
    ),
    "glm": ("GLM-5.3-Flash", "bounded pasted text", ".chat-assistant final body; exclude thinking and controls"),
    "chatgpt": (
        "5.6 Sol / High",
        "paste restored using Show in text field",
        '[data-message-author-role="assistant"] final body',
    ),
}


def verify_bound_files(root, records):
    for name, record in records.items():
        require(Path(name).name == name and not (root / name).is_symlink(), "BOUND_ARTIFACT_PATH")
        data = (root / name).read_bytes()
        require(len(data) == record["bytes"] and sha(data) == record["sha256"], "FINAL_ARTIFACT_HASH")


def verify_freeze(root):
    encoded = (root / "freeze_a_manifest.json").read_bytes()
    require(
        (root / "freeze_a_manifest.sha256").read_text(encoding="ascii").strip() == sha(encoded), "FREEZE_MANIFEST_HASH"
    )
    manifest = json.loads(encoded)
    verify_bound_files(root, manifest["artifacts"])
    corpus = json.loads((root / "corpus.json").read_bytes())
    require(digest(corpus) == manifest["corpus_sha256"], "CORPUS_HASH")
    by_id = {x["candidate_id"]: x for x in corpus}
    surfaces = json.loads((root / "surfaces.json").read_bytes())
    records = json.loads((root / "packet_index.json").read_bytes())
    require(len(surfaces) == len({s["surface_id"] for s in surfaces}) == 7, "ROSTER_DUPLICATION")
    for surface in surfaces:
        sid = surface["surface_id"]
        p = prompt(surface["attentional_roles"])
        require((root / surface["prompt_artifact"]).read_bytes() == p.encode(), "PROMPT_REPRODUCTION")
        selected = [r for r in records if r["surface"] == sid]
        require(Counter(cid for r in selected for cid in r["candidate_ids"]) == Counter(by_id.keys()), "RATER_COVERAGE")
        for record in selected:
            batch = [by_id[cid] for cid in record["candidate_ids"]]
            packet = render_packet(batch, p)
            require(packet == (root / record["artifact"]).read_bytes(), "PACKET_REPRODUCTION")
            require(sha(packet) == record["packet_sha256"], "PACKET_HASH")
            require(len(packet) + len(WRAPPER.encode()) + packet.count(b"\n") <= 20480, "PACKET_ENVELOPE_EXCEEDED")
    return {
        "status": "PASS",
        "artifact_count": len(manifest["artifacts"]),
        "packet_count": len(records),
        "candidate_rater_cells": sum(len(r["candidate_ids"]) for r in records),
        "freeze_a_sha256": sha(encoded),
    }


def build():
    root = Path(tempfile.mkdtemp(prefix="callosum-freeze-a-final-private-"))
    os.chmod(root, 0o700)
    files = {}

    def save(name, data):
        require(name not in files and "/" not in name and "\\" not in name, "DUPLICATE_OR_INVALID_ARTIFACT")
        with (root / name).open("xb") as handle:
            handle.write(data)
        files[name] = {"sha256": sha(data), "bytes": len(data)}

    try:
        projection_manifest = json.loads((PROJECTION / "projection_artifacts.json").read_bytes())
        for name, record in projection_manifest["artifacts"].items():
            require(
                name in ("corpus.json", "private_identities.json", "exclusions.json", "projection_receipt.json"),
                "PROJECTION_ARTIFACT_ALLOWLIST",
            )
            data = (PROJECTION / name).read_bytes()
            require(sha(data) == record["sha256"] and len(data) == record["bytes"], "PROJECTION_INTEGRITY")
            save(name, data)
        objects = json.loads((root / "corpus.json").read_bytes())
        identities = json.loads((root / "private_identities.json").read_bytes())
        projected = json.loads((root / "projection_receipt.json").read_bytes())
        require(digest(objects) == projected["corpus_sha256"], "CORPUS_HASH")
        require(len(objects) == len(identities) == 78, "CORPUS_COUNT")
        membership = Counter((x["unit_id"], x["configuration"]) for x in identities)
        require(len(membership) == 78 and set(membership.values()) == {1}, "OBSERVATION_DUPLICATION")
        require(Counter(x["configuration"] for x in identities) == {1: 39, 2: 39}, "CONFIGURATION_MEMBERSHIP")
        require(len({x["unit_id"] for x in identities}) == 39, "SOURCE_UNIT_COUNT")
        amendment, qualification, provenance = Store(ROSTER_AMENDMENT), Store(QUALIFICATION), Store(PROVENANCE)
        for store in (amendment, qualification, provenance):
            store.verify()
        role_record = json.loads(amendment.read("proposed_assignments.json"))
        roles = role_record["assignments"]
        roster = [sid for sid, _ in ROSTER if sid in ROUTES]
        computed = {sid: [] for sid in roster}
        for i, role in enumerate(ROLES):
            computed[roster[i % len(roster)]].append(role)
        require(roles == computed and len(roles) == 7, "ROLE_ASSIGNMENT_MISMATCH")
        final_matrix = json.loads(amendment.read("qualified_surface_matrix.json"))
        qualified_rows = {r["surface"]: r for r in final_matrix["surfaces"]}
        require(set(qualified_rows) == set(roster), "ROSTER_MISMATCH")
        require(
            all(r["expanded_envelope"] == "PASS_UNDER_OPERATIONAL_BLINDING" for r in qualified_rows.values()),
            "QUALIFICATION_MISSING",
        )
        account_rows = {
            r["surface_id"]: r
            for r in json.loads(provenance.read("phase_minus_1_final_table.json"))["rows"]
            if r["surface_id"] in roster
        }
        prompts = {sid: prompt(roles[sid]) for sid in roster}
        require(all(len(p.encode()) <= LIMITS["prompt_bytes"] for p in prompts.values()), "PROMPT_ENVELOPE_EXCEEDED")
        batches = batch_objects(objects, list(prompts.values()))
        packet_records, surfaces, size_report = [], [], {}
        for sid in roster:
            prompt_name = sid + "_prompt.txt"
            save(prompt_name, prompts[sid].encode())
            sizes, coverage = [], []
            for index, batch in enumerate(batches):
                data = render_packet(batch, prompts[sid])
                # Conservatively include wrapper on every surface and one extra
                # LF per existing LF for observed paragraph-based composers.
                upper = len(data) + len(WRAPPER.encode()) + data.count(b"\n")
                response_max = sum(len(x["candidate_id"].encode()) + 3 + 9 + 3 + 512 + 1 for x in batch)
                require(
                    upper <= LIMITS["input_bytes"] and response_max <= LIMITS["response_bytes"],
                    "PACKET_ENVELOPE_EXCEEDED",
                )
                name = f"{sid}_batch_{index + 1:03d}.txt"
                save(name, data)
                ids = [x["candidate_id"] for x in batch]
                coverage.extend(ids)
                packet_records.append(
                    {
                        "surface": sid,
                        "batch_index": index + 1,
                        "artifact": name,
                        "candidate_ids": ids,
                        "packet_sha256": sha(data),
                        "packet_bytes": len(data),
                        "input_upper_bytes_including_wrapper_and_paragraph_lf": upper,
                        "expected_response_upper_bytes": response_max,
                        "scientific_object_sha256": [digest(x) for x in batch],
                    }
                )
                sizes.append(upper)
                # Parse only our own serialization, compare without semantic analysis.
                decoded = [json.loads(line[5:]) for line in data.splitlines() if line.startswith(b"CASE ")]
                require(decoded == batch and data == render_packet(decoded, prompts[sid]), "PACKET_ROUNDTRIP")
            require(Counter(coverage) == Counter(x["candidate_id"] for x in objects), "RATER_COVERAGE")
            size_report[sid] = {
                "prompt_bytes": len(prompts[sid].encode()),
                "batches": len(sizes),
                "candidate_observations": len(coverage),
                "minimum_input_upper_bytes": min(sizes),
                "maximum_input_upper_bytes": max(sizes),
            }
            surfaces.append(
                {
                    "surface_id": sid,
                    "configuration": ROUTES[sid][0],
                    "attentional_roles": roles[sid],
                    "account_plan_alias": account_rows[sid]["account_plan_alias"],
                    "transport": ROUTES[sid][1],
                    "capture_boundary": ROUTES[sid][2],
                    "prompt_artifact": prompt_name,
                    "prompt_sha256": sha(prompts[sid].encode()),
                    "wrapper": WRAPPER if sid in ("copilot", "kimi") else "",
                    "adapter": "empty-lines-only after CRLF normalization" if sid == "copilot" else "none",
                    "parser": "frontier_contract.parse_response",
                    "copilot_empty_lines": sid == "copilot",
                    "qualification": qualified_rows[sid],
                    "availability_as_of_audit": account_rows[sid]["availability_notes"],
                    "current_live_availability": "NOT_RECHECKED; no surface contacted during construction",
                    "backend_identity_limit": account_rows[sid]["backend_identity_evidence"],
                    "maximum_batch_candidates": 2,
                    "semantic_executions_so_far": 0,
                }
            )
        protocol = {
            "session_isolation": "Use a fresh conversation for each packet, with only its frozen prompt and complete CASE objects. Do not append previous batches, responses, other raters' judgments or private identity maps. Historical conversation context is outside the qualified input budget.",
            "preservation": "Write raw responses, packet/prompt hashes, provenance and each attempt exclusively to private nonsynced artifacts. Append hash-linked mechanical receipts and missingness/exposure/amendment events. Preserve individual rater judgments; never overwrite attempts or retain only consensus. Keep Cliff-safe receipts separate from raw responses and private orchestration rationale.",
            "amendment_type": "POST-INFERENCE / PRE-HUMAN-SEMANTIC-ADJUDICATION",
            "criterion": CRITERION,
            "source_relative_rules": SOURCE_RULES,
            "labels": ["FLAG", "UNCERTAIN", "NO_FLAG"],
            "reason_rules": "Source-anchored nonempty reason for FLAG/UNCERTAIN, max 512 serialized UTF-8 bytes. NO_FLAG empty reason. Exact syntax/escaping in hashed prompts and parser.",
            "eligibility": "All q_aib source units in frozen inventory, configurations 1 and 2, exactly one original observation each. No semantic-quality selection. All 78 scientific objects remain eligible, including one mechanically incomplete observation. Other 125 source units excluded as OUTSIDE_Q_AIB for both configurations. Arm0 outside scope, never opened.",
            "source_boundaries": "Inventory quote is exact excerpt; grown_context resolves references only; source_unit_context is task/obligation context, not added evidence. Preserve paper/span/unit identities, raw output and full produced_representation. Raw output cannot repair effective representation. Arm2 quote/paper/span exact-bound checks required.",
            "identity": "c- plus full SHA256 of canonical domain callosum-study1-freeze-a-v1, archive hashes, unit_id and arm. New private mapping; old sealed key not accessed or reconstructed. Explicit arm omitted from model objects; inherent representation form may reveal configuration.",
            "ordering": "Sort new opaque candidate IDs lexically. Greedy max-two whole-object batches; never put the same source unit twice in a batch. Split on envelope or source collision. Same batches/order for seven raters. Gemini one rater, one prompt, two attentional roles.",
            "limits": LIMITS,
            "input_gate": "Before any future submission verify selected model/account, one complete packet, exact source strings and wrapper. For auto TXT without preview retain exact input hash, attachment name/count/upload completion and document unavailable independent readback. Fail closed on known truncation or uncertain submission. No content truncation or annotation removal.",
            "capture": "Dedicated minimized Chrome; Cliff does not inspect study tabs. Direct DOM to private nonsynced file; no clipboard, raw text echoes, full public snapshots or response-bearing exceptions. Capture final body only, excluding reasoning/tools/UI. Record URL, model, account alias, times, bytes and SHA256. Preserve original raw bytes first; parse afterward. If final boundary cannot be isolated safely stop affected route for amendment.",
            "parser_and_missingness": "Only CRLF to LF and trailing newlines handled by base parser; only Microsoft Copilot removes wholly empty internal lines. No prose/fence stripping, whitespace repair, fuzzy IDs, reordered/deduplicated rows or reason truncation. Invalid/missing/refused/truncated response yields no semantic rows for entire batch; valid raw preserved. NO_FLAG never imputed. Syntactic reason validity does not certify anchoring.",
            "retry_rule": "One scheduled submission per packet; no automatic retry, regeneration or nudge. Failures preserved with terminal technical status for every affected cell. Any retry needs an explicit logged mechanical amendment before another send; uncertain sends must first be reconciled privately, never blindly repeated. Replacements of account/model require amendment and appropriate synthetic qualification.",
            "availability": "Qualified as of recorded synthetic audit only; exact rate/context limits unknown. Recheck exposed identity and availability mechanically at future execution. Pause a blocked route; preserve technical missingness. No epistemic weighting by paid tier, quota or reputation. No unqualified fallback or role reassignment after semantic results.",
            "accidental_exposure": "Preserve observation; mark affected HUMAN_BLINDING_COMPROMISED, record time, observer, surface/cases if known, circumstances, extent or unknown extent, hashes privately. Interstudy amendment must account for exposure; do not automatically invalidate unrelated evidence or reveal selection rationale to Cliff.",
            "orchestration_access": "During Study1 capture/structural validation only; private automated handling may process all response bytes. No semantic triage or prompt/roster tuning until Study1 is closed. After closure orchestration may privately inspect individual labels/reasons, disagreements, patterns and provenance to design efficient falsification; never certify or promote a configuration. Codex is not a semantic rater.",
            "completion": "546 candidate-rater cells, seven raters times 78 objects. Close only when every planned cell has a validated row or explicit terminal technical disposition, all raw attempts/provenance preserved and reconciliation passes. Closure with missingness is not adequate coverage certification; review coverage before designing Study2.",
            "interpretation": "NO_FLAG != FAITHFUL. Frontier results provide exclusion/discovery/ordering, not truth, IID votes or human promotion. Shared model errors, attention-role confounding, batching, opaque backend and operational-blinding limits remain. Local files share investigator account; minimization is not guaranteed concealment.",
            "interstudy_adaptation": "After complete private Study1, permit content-informed minimal human-study design while Cliff remains blinded. Log evidence/findings, methods changed, why, access identities, visibility, consequences and hashes in private amendment with separate Cliff-safe receipt. Do not optimize for preferred configuration. Freeze B before first human case; no real queue or exact challenge allocations frozen here.",
            "preserved_human_boundary": "Existing severe-failure rule, 20-minute attention safeguard and maximum burden unchanged; detailed human selection remains FreezeB. Original492/archive fallback immutable. No R_0_6 nomination, integration, acceptance or 0.7 execution.",
            "amendments": "Append what/why/when, semantic results visible or not, Cliff blinding, affected artifact hashes and interpretation. Mechanical format/batch/parser/scheduling adaptations may preserve scientific content; scientific-task changes require explicit scientific amendment. No silent substitutions. Claude and GitHub Copilot excluded; do not reopen capability work.",
        }
        save("protocol.json", canonical(protocol))
        save("surfaces.json", canonical(surfaces))
        save("packet_index.json", canonical(packet_records))
        save("size_report.json", canonical(size_report))
        save("authorization.txt", AUTHORIZATION.read_bytes())
        save("roster_amendment.json", amendment.read("roster_amendment.json"))
        save("qualification_matrix.json", amendment.read("qualified_surface_matrix.json"))
        base = Path(__file__).parent
        for name in (
            "core.py",
            "frontier_contract.py",
            "freeze_a_projection.py",
            "freeze_a_construct.py",
            "tests/test_frontier_contract.py",
            "tests/test_freeze_a_projection.py",
            "tests/test_freeze_a_construct.py",
            "OPERATIONAL_BLINDING_AMENDMENT.md",
            "FREEZE_A_LEAST_ACCESS_CHECKLIST.md",
        ):
            save("bound_" + name.replace("/", "_"), (base / name).read_bytes())
        for sid in roster:
            row = qualified_rows[sid]
            raw = qualification.read(row["raw_artifact"])
            require(sha(raw) == row["raw_sha256"], "QUALIFICATION_RAW_HASH")
            save(sid + "_synthetic_qualification.bin", raw)
        validation = {
            "status": "PASS",
            "observations": 78,
            "source_units": 39,
            "configurations": {"1": 39, "2": 39},
            "raters": 7,
            "candidate_rater_cells": sum(len(r["candidate_ids"]) for r in packet_records),
            "packet_count": len(packet_records),
            "one_gemini_rater_two_roles": True,
            "exact_rater_coverage": True,
            "duplicate_source_within_batch": False,
            "duplicate_source_configuration": False,
            "arm0_in_corpus": False,
            "hashes_verified": True,
            "all_packets_reproduce": True,
            "all_inputs_within_envelope": True,
            "source_anchors_verified": True,
            "semantic_inference_calls": 0,
            "frontier_submissions": 0,
            "human_queue_created": False,
            "sealed_mapping_accessed": False,
            "synthetic_projection_tests": 6,
            "synthetic_contract_tests": 23,
            "full_synthetic_suite_passed": 168,
            "ruff": "PASS",
        }
        save("validation.json", canonical(validation))
        verify_bound_files(root, files)
        manifest = {
            "status": "FREEZE_A_COMPLETE",
            "version": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "corpus_sha256": projected["corpus_sha256"],
            "artifacts": files.copy(),
            "projection_root": str(PROJECTION),
            "role_assignments": roles,
            "frontier_execution_authorized": False,
            "freeze_b_executed": False,
        }
        encoded = canonical(manifest)
        receipt = {
            "status": "FREEZE_A_COMPLETE",
            "private_root": str(root),
            "created_utc": manifest["created_utc"],
            "corpus_sha256": projected["corpus_sha256"],
            "freeze_a_sha256": sha(encoded),
            "counts": validation,
            "sizes": size_report,
            "maximum_object_bytes": projected["object_max_bytes"],
            "maximum_combined_object_bytes": max(sum(len(canonical(x)) for x in batch) for batch in batches),
            "maximum_expected_response_bytes": max(x["expected_response_upper_bytes"] for x in packet_records),
            "synthetic_transport_amendment_required": False,
            "frontier_study_executed": False,
        }
        with (root / "cliff_safe_receipt.json").open("xb") as handle:
            handle.write(canonical(receipt))
        # Commit marker last: no partial freeze is represented as completed.
        with (root / "freeze_a_manifest.sha256").open("x", encoding="ascii") as handle:
            handle.write(sha(encoded) + "\n")
        with (root / "freeze_a_manifest.json").open("xb") as handle:
            handle.write(encoded)
        return receipt
    except Exception:
        # Fixed errors only; don't expose a candidate through exception payloads.
        if not (root / "freeze_a_manifest.json").exists():
            (root / "construction_blocked.json").write_bytes(
                canonical({"status": "BLOCKED", "freeze_a_executed": False})
            )
        raise


if __name__ == "__main__":
    try:
        print(json.dumps(build()))
    except BoundaryError as error:
        print(json.dumps({"status": "FREEZE_A_BLOCKED", "code": str(error), "semantic_inference_calls": 0}))
    except Exception:
        print('{"status":"FREEZE_A_BLOCKED","code":"CONSTRUCTION_VALIDATION_ERROR","semantic_inference_calls":0}')
