"""P1 packaged-interpreter qualification probe: runs INSIDE the recovered packaged runtime (``python.exe -I -B``).

One phase per process, so the two models are never resident together and each process's memory is its own:

* ``identity``  -- interpreter path, flags and installed distributions against the signed runtime manifest.
* ``provision`` -- the application's own inc-615 ``Provisioner`` fetches only the two P1 manifests (network allowed).
* ``verify``    -- offline: every manifest file re-hashed, static contracts, provisioning receipt, cache contents.
* ``netcheck``  -- offline boundary negative controls (connections must be refused by the OS; Hub online access off).
* ``arctic``    -- offline: the app's profile resolver loads Arctic S; parity against the frozen reference.
* ``deberta``   -- offline: the app's support-scorer resolver loads DeBERTa (contract-checked); numerical parity and
  app-derived statuses against the frozen fixture.

Every phase writes ``{"phase", "checks": [{id, kind, ok, detail}], "data"}`` to ``--out``. ``kind`` decides what a
failed check means for the verdict (``p1_qualify.ps1``): integrity/contract/scientific/isolation failures are FAIL,
infrastructure failures are INCONCLUSIVE. A phase never reports a check it did not perform.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

CHECKS: list[dict] = []
DATA: dict = {}


def check(check_id: str, kind: str, ok: bool, detail: object = "") -> bool:
    CHECKS.append({"id": check_id, "kind": kind, "ok": bool(ok), "detail": detail})
    return bool(ok)


def memory() -> dict:
    """Own-process working set and commit (``GetProcessMemoryInfo``), in MiB."""

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {}
    mib = 1024 * 1024
    return {
        "working_set_mib": round(counters.WorkingSetSize / mib, 1),
        "peak_working_set_mib": round(counters.PeakWorkingSetSize / mib, 1),
        "commit_mib": round(counters.PagefileUsage / mib, 1),
        "peak_commit_mib": round(counters.PeakPagefileUsage / mib, 1),
    }


def sample(label: str) -> None:
    DATA.setdefault("memory", {})[label] = memory()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def offline_env() -> dict:
    keys = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HOME", "HF_HUB_CACHE", "CALLOSUM_MODEL_PROVISIONING_DIR")
    return {k: os.environ.get(k) for k in keys}


def require_offline() -> bool:
    env = offline_env()
    ok = env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1"
    return check("offline_environment", "isolation", ok, env)


def fake_app() -> SimpleNamespace:
    """The minimal ``app.state`` the app's own resolvers read: an app-owned model registry, nothing injected."""
    from app.backend.model_runtime import ModelRuntimeRegistry

    return SimpleNamespace(state=SimpleNamespace(model_runtime_registry=ModelRuntimeRegistry()))


# --- phases --------------------------------------------------------------------------------------------------------
def phase_identity(args: argparse.Namespace) -> None:
    from importlib import metadata

    exe = Path(sys.executable).resolve()
    expected = Path(args.expected_python).resolve()
    check("interpreter_is_packaged_runtime", "integrity", exe == expected, {"sys.executable": str(exe)})
    check("prefix_inside_runtime", "integrity", Path(sys.prefix).resolve() == expected.parent, sys.prefix)
    check("isolated_mode", "integrity", sys.flags.isolated == 1, sys.flags.isolated)
    check("no_bytecode_writes", "integrity", sys.dont_write_bytecode is True, sys.dont_write_bytecode)
    check("python_version", "integrity", sys.version.split()[0] == args.python_version, sys.version)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    pinned = {}
    for line in manifest["resolved_packages"]:
        name, _, version = line.partition("==")
        if version:
            pinned[name.lower().replace("_", "-").replace(".", "-")] = version
    installed = {
        d.metadata["Name"].lower().replace("_", "-").replace(".", "-"): d.version for d in metadata.distributions()
    }
    mismatched = {k: [v, installed.get(k)] for k, v in pinned.items() if installed.get(k) != v}
    check("distributions_match_signed_manifest", "integrity", not mismatched, mismatched or f"{len(pinned)} pinned")
    DATA["versions"] = {
        k: installed.get(k) for k in ("torch", "transformers", "sentence-transformers", "huggingface-hub")
    }
    DATA["sys_path"] = sys.path


def phase_provision(args: argparse.Namespace) -> None:
    from app.backend.model_provisioning import MANIFESTS
    from app.backend.model_provisioning.provisioner import VERIFIED, Provisioner, default_cache_dir

    cache = default_cache_dir()
    inside = Path(cache).resolve().is_relative_to(Path(args.work).resolve())
    if not check("hf_cache_is_disposable", "isolation", inside, str(cache)):
        return
    DATA["tracks"] = {}
    for track in ("arctic-s", "deberta-v3-base"):  # serial, one checkpoint at a time
        started = time.monotonic()
        status = Provisioner(MANIFESTS[track], cache_dir=cache, state_dir=Path(args.state)).provision_once()
        DATA["tracks"][track] = {**status, "seconds": round(time.monotonic() - started, 1)}
        state, kind = status["state"], status.get("error_kind")
        # A transport problem is the runner's, not the checkpoint's; an integrity/contract failure is a real FAIL.
        verdict_kind = (
            "integrity" if kind in {"integrity", "contract", "pinned_revision_unavailable"} else "infrastructure"
        )
        check(f"provisioned_{track}", verdict_kind, state == VERIFIED, {"state": state, "error_kind": kind})


def phase_verify(args: argparse.Namespace) -> None:
    require_offline()
    from app.backend.model_provisioning import MANIFESTS
    from app.backend.model_provisioning.manifests import ContractMismatch, check_static_contract
    from app.backend.model_provisioning.provisioner import Provisioner, default_cache_dir
    from app.backend.model_provisioning.runner import local_files_only_for
    from app.backend.model_runtime import PINNED_MODEL_REVISIONS

    cache = default_cache_dir()
    for track, manifest in MANIFESTS.items():
        check(
            f"pinned_revision_{track}",
            "integrity",
            PINNED_MODEL_REVISIONS[manifest.repo_id] == manifest.revision == args.revisions[manifest.repo_id],
            manifest.revision,
        )
        provisioner = Provisioner(manifest, cache_dir=cache, state_dir=Path(args.state))
        root = provisioner.snapshot_root
        bad = []
        for f in manifest.files:
            path = root / f.path
            if not path.is_file() or path.stat().st_size != f.size or sha256(path) != f.sha256:
                bad.append(f.path)
        check(
            f"manifest_files_{track}",
            "integrity",
            not bad,
            bad or f"{len(manifest.files)} files, digest {manifest.digest}",
        )
        try:
            check_static_contract(manifest, root)
            check(f"static_contract_{track}", "contract", True, manifest.contract)
        except ContractMismatch as exc:
            check(f"static_contract_{track}", "contract", False, str(exc))
        check(f"provisioning_receipt_{track}", "integrity", provisioner.is_verified(), provisioner.status()["state"])
        check(f"app_loads_offline_{track}", "isolation", local_files_only_for(manifest.repo_id) is True, "")
    repos = sorted(p.name for p in Path(cache).glob("models--*"))
    expected = sorted("models--" + m.repo_id.replace("/", "--") for m in MANIFESTS.values())
    check("cache_holds_only_p1_models", "isolation", repos == expected, repos)
    partial = [str(p) for p in Path(cache).rglob("*.incomplete")]
    check("no_partial_downloads", "integrity", not partial, partial)


def _connect(host: str, port: int) -> dict:
    import socket

    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=10):
            return {"connected": True}
    except OSError as exc:
        return {
            "connected": False,
            "winerror": getattr(exc, "winerror", None),
            "error": f"{type(exc).__name__}: {exc}",
            "seconds": round(time.monotonic() - started, 2),
        }


def phase_netcheck(args: argparse.Namespace) -> None:
    require_offline()
    attempts = {f"{host}:443": _connect(host, 443) for host in [args.target_ip, *args.target_hosts]}
    DATA["attempts"] = attempts
    for name, result in attempts.items():
        if result["connected"]:
            check(f"blocked_{name}", "isolation", False, "connection succeeded: the outbound block is not enforced")
        else:
            # 10013 (WSAEACCES) is what Windows Firewall returns to a blocked program. Any other error (timeout, DNS,
            # refused) does not prove the block, so it is inconclusive rather than a pass.
            check(f"blocked_{name}", "infrastructure", result["winerror"] == 10013, result)
    from huggingface_hub import constants, hf_hub_download

    check("hub_offline_constant", "isolation", constants.HF_HUB_OFFLINE is True, constants.HF_HUB_OFFLINE)
    try:
        hf_hub_download("sentence-transformers/all-MiniLM-L6-v2", "config.json", revision=args.unprovisioned_revision)
        check("unprovisioned_model_unavailable", "isolation", False, "an unprovisioned file was returned")
    except Exception as exc:  # noqa: BLE001 -- any refusal is the expected outcome; it is recorded verbatim
        check("unprovisioned_model_unavailable", "isolation", True, f"{type(exc).__name__}: {str(exc)[:200]}")


def phase_arctic(args: argparse.Namespace) -> None:
    if not require_offline():
        return
    sample("start")
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))["arctic"]
    from app.backend.api.dependencies import resolve_profile_embedding_model
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, PROFILES

    profile = PROFILES[ARCTIC_S_PROFILE_KEY]
    check(
        "profile_identity",
        "contract",
        (profile.model_name, profile.revision) == (fixture["model"], fixture["revision"]),
        profile.model_version,
    )
    sample("imports")
    model = resolve_profile_embedding_model(fake_app(), profile)
    check("resolver_local_files_only", "isolation", model.local_files_only is True, model.local_files_only)
    started = time.monotonic()
    vectors = model.encode_documents(fixture["texts"])  # loads under the app's pooling/max-seq contract check
    DATA["first_encode_seconds"] = round(time.monotonic() - started, 2)
    sample("after_load_and_encode")
    check("dimension", "contract", all(len(v) == 384 for v in vectors) and model.dimension == 384, len(vectors[0]))
    loaded = model._runtime.loaded_model if model._runtime is not None else None  # noqa: SLF001
    revision = getattr(getattr(loaded, "model_card_data", None), "base_model_revision", None)
    DATA["loaded_revision_card"] = revision
    cosines = [cosine(v, r) for v, r in zip(vectors, fixture["reference_embeddings"], strict=True)]
    historical = [cosine(v, r) for v, r in zip(vectors, fixture["historical_packaged_embeddings"], strict=True)]
    DATA["cosine_vs_reference"] = cosines
    DATA["cosine_vs_historical_packaged"] = historical  # informational only
    DATA["max_abs_component_difference"] = max(
        abs(a - b)
        for v, r in zip(vectors, fixture["reference_embeddings"], strict=True)
        for a, b in zip(v, r, strict=True)
    )
    check(
        "cosine_parity",
        "scientific",
        min(cosines) >= fixture["min_cosine"],
        {"min": min(cosines), "required": fixture["min_cosine"]},
    )
    query = model.encode_queries([fixture["texts"][2]])[0]  # the app's query-prefix path: no reference, shape only
    check(
        "query_path_shape",
        "contract",
        len(query) == 384 and abs(math.sqrt(sum(x * x for x in query)) - 1) < 1e-4,
        len(query),
    )
    DATA["vectors"] = vectors
    sample("end")


def phase_deberta(args: argparse.Namespace) -> None:
    if not require_offline():
        return
    sample("start")
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    nli = fixture["deberta"]
    from dataclasses import replace

    from app.backend.api.dependencies import resolve_support_scorer
    from app.backend.summarization.nli_profiles import (
        DEBERTA_NLI_PROFILE_KEY,
        NLI_PROFILES,
        NliProfileConfigurationError,
        verify_nli_checkpoint,
    )
    from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig

    profile = NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY]
    labels = [profile.id2label[i] for i in sorted(profile.id2label)]
    check(
        "profile_identity",
        "contract",
        (profile.model_name, profile.revision) == (nli["model"], nli["revision"]),
        profile.revision,
    )
    check("profile_label_order", "contract", labels == nli["label_order"], labels)
    config = VerificationConfig()
    current = {k: getattr(config, k) for k in fixture["verification_thresholds"]}
    check("thresholds_unchanged", "scientific", current == fixture["verification_thresholds"], current)
    sample("imports")
    app = fake_app()
    started = time.monotonic()
    scorer = resolve_support_scorer(app, nli_profile=profile)  # loads offline and runs verify_nli_checkpoint
    DATA["load_seconds"] = round(time.monotonic() - started, 2)
    sample("after_load")
    runtime = scorer._runtime  # noqa: SLF001
    check(
        "resolver_local_files_only",
        "isolation",
        scorer.local_files_only is True and runtime.identity.local_files_only,
        "",
    )
    check("no_embedding_fallback", "contract", scorer.fallback_scorer is None, "")
    check(
        "checkpoint_contract_verified", "contract", True, "verify_nli_checkpoint passed inside resolve_support_scorer"
    )
    wrong = replace(profile, id2label={0: "contradiction", 1: "entailment", 2: "neutral"})
    try:
        runtime.run(lambda model: verify_nli_checkpoint(model, wrong))
        check("contract_fails_closed", "contract", False, "a wrong label order was accepted")
    except NliProfileConfigurationError as exc:
        check("contract_fails_closed", "contract", True, str(exc)[:200])
    pairs = [tuple(p) for p in nli["pairs_premise_hypothesis"]]
    raw = runtime.run(lambda model: [[float(x) for x in row] for row in model.predict(pairs, apply_softmax=True)])
    app_values = scorer.support_and_contradiction_many(pairs)  # the app's (entailment, contradiction) extraction
    sample("after_inference")
    diff = max(
        abs(a - b)
        for row, ref in zip(raw, nli["reference_probabilities"], strict=True)
        for a, b in zip(row, ref, strict=True)
    )
    app_diff = max(
        max(abs(e - ref[0]), abs((c if c is not None else math.inf) - ref[2]))
        for (e, c), ref in zip(app_values, nli["reference_probabilities"], strict=True)
    )
    historical = max(
        abs(a - b)
        for row, ref in zip(raw, nli["historical_packaged_probabilities"], strict=True)
        for a, b in zip(row, ref, strict=True)
    )
    DATA.update(probabilities=raw, app_values=app_values, historical_packaged_max_abs_difference=historical)
    limit = nli["max_abs_probability_difference"]
    check("probability_parity", "scientific", diff <= limit, {"max_abs": diff, "limit": limit})
    check("app_extraction_parity", "scientific", app_diff <= limit, {"max_abs": app_diff, "limit": limit})
    status_of = LocalCitationVerifier._status  # noqa: SLF001 -- the app's own status rule, unchanged
    flips = []
    for item in fixture["expected_statuses"]:
        ent, con = app_values[item["pair"]]
        got = status_of(
            SimpleNamespace(config=config),
            retrieval_confidence=item["retrieval_confidence"],
            quote_confidence=item["quote_confidence"],
            support_confidence=ent,
            contradiction_confidence=con,
        )
        if got != item["status"]:
            flips.append({**item, "observed": got})
    check(
        "app_status_stable", "scientific", not flips, flips or f"{len(fixture['expected_statuses'])} statuses unchanged"
    )
    sample("end")


PHASES = {
    "identity": phase_identity,
    "provision": phase_provision,
    "verify": phase_verify,
    "netcheck": phase_netcheck,
    "arctic": phase_arctic,
    "deberta": phase_deberta,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=sorted(PHASES))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fixture")
    parser.add_argument("--manifest")
    parser.add_argument("--expected-python")
    parser.add_argument("--python-version")
    parser.add_argument("--target-ip")
    parser.add_argument("--target-hosts", nargs="*", default=[])
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))  # -I keeps the checkout off sys.path unless named explicitly
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8")) if args.fixture else {}
    args.revisions = {fixture[k]["model"]: fixture[k]["revision"] for k in ("arctic", "deberta") if k in fixture}
    from app.backend.model_runtime import PINNED_MODEL_REVISIONS

    args.unprovisioned_revision = PINNED_MODEL_REVISIONS["sentence-transformers/all-MiniLM-L6-v2"]
    try:
        PHASES[args.phase](args)
    except Exception as exc:  # noqa: BLE001 -- recorded as a failed check; the driver turns it into the verdict
        kind = "infrastructure" if args.phase == "provision" else "integrity"
        check("phase_exception", kind, False, f"{type(exc).__name__}: {exc}")
        DATA["traceback"] = traceback.format_exc()
    DATA["final_memory"] = memory()
    Path(args.out).write_text(
        json.dumps({"phase": args.phase, "checks": CHECKS, "data": DATA}, indent=1), encoding="utf-8"
    )
    return 0 if CHECKS and all(c["ok"] for c in CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
