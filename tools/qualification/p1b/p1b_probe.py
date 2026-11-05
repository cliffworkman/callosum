"""P1b qualification probe: runs INSIDE the recovered packaged runtime (``python.exe -I -B``), one phase per process.

* ``identity``   -- delegated unchanged to the P1 probe (interpreter, flags, distributions vs the signed manifest).
* ``provision``  -- network allowed: the app's ``Provisioner`` for Arctic S and DeBERTa (committed byte manifests);
  ``snapshot_download`` at the pinned revision for MiniLM and MiniLM2, which have no committed manifest, with a full
  file inventory (size, SHA-256) written as a receipt.
* ``verify``     -- offline: manifests re-hashed, baseline inventories re-hashed against the receipt, cache contents.
* ``netcheck``   -- offline boundary negative controls.
* ``tokenize``   -- offline: token lengths of the frozen pairs under both pinned NLI tokenizers (before any timing).
* ``seed``       -- disposable SQLite library: app Alembic chain, the fixture chunks, the synthetic indexing corpus.
* ``measure``    -- one fresh measurement process: app verifier resolution, one cold and N warm ``verify_many`` calls.
* ``failclosed`` -- the app's fail-closed paths under simulated memory refusal and injected inference failure.
* ``arm_worker`` / ``stop_worker`` / ``worker_status`` -- the Arctic S run row, armed as ``IndexSupervisor`` does.
* ``evaluate``   -- pure aggregation of the measurement results against the predeclared limits.

Every phase writes ``{"phase", "checks": [{id, kind, ok, detail}], "data"}`` to ``--out``. ``kind`` decides the verdict
(``p1b_qualify.ps1``): integrity/contract/scientific/isolation/performance failures are FAIL, infrastructure
failures are INCONCLUSIVE. A phase never reports a check it did not perform.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import random
import statistics
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
CHECKS: list[dict] = []
DATA: dict = {}

# Predeclared (P1B_PREDECLARATION.md §7); evaluate() is the only reader.
LIMITS = {"warm_solo_s": 7.2, "warm_concurrent_s": 8.8, "peak_working_set_mb": 2520, "peak_commit_mb": 2870}
CONCURRENCY_MIN_CPU_RATIO = 0.10
PROCESSES_PER_CONDITION = 3
WARM_REPETITIONS = 8
BASELINE_PATTERNS = ["*.json", "*.txt", "*.safetensors", "1_Pooling/*", "README.md"]
BASELINE_IGNORE = ["onnx/*", "openvino/*"]
WORKER_THREADS = 4
WORKER_BATCH = 8


def check(check_id: str, kind: str, ok: bool, detail: object = "") -> bool:
    CHECKS.append({"id": check_id, "kind": kind, "ok": bool(ok), "detail": detail})
    return bool(ok)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_fixture(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def require_offline() -> bool:
    keys = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HOME")
    env = {k: os.environ.get(k) for k in keys}
    return check(
        "offline_environment", "isolation", env["HF_HUB_OFFLINE"] == "1" and env["TRANSFORMERS_OFFLINE"] == "1", env
    )


# --- Windows process accounting ------------------------------------------------------------------------------------
class _Counters(ctypes.Structure):
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


def _kernel32():  # type: ignore[no-untyped-def]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    k.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_Counters), ctypes.c_ulong]
    return k


def memory() -> dict:
    """Own-process working set and private commit, current and OS peak, in bytes."""
    k = _kernel32()
    counters = _Counters()
    counters.cb = ctypes.sizeof(_Counters)
    if not k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {}
    return {
        "working_set_bytes": counters.WorkingSetSize,
        "peak_working_set_bytes": counters.PeakWorkingSetSize,
        "commit_bytes": counters.PagefileUsage,
        "peak_commit_bytes": counters.PeakPagefileUsage,
        "t": time.time(),
    }


def _times(handle) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    """(creation as Unix seconds, kernel+user CPU seconds) for an open process handle."""
    k = _kernel32()
    created, exited, kernel, user = (ctypes.c_ulonglong() for _ in range(4))
    if not k.GetProcessTimes(
        handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)
    ):
        raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
    return (created.value - 116444736000000000) / 1e7, (kernel.value + user.value) / 1e7


def own_creation_time() -> float:
    return _times(_kernel32().GetCurrentProcess())[0]


def other_process(pid: int) -> dict:
    """Alive flag and CPU seconds of another process (the Arctic worker), without signalling it."""
    k = _kernel32()
    handle = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return {"alive": False, "cpu_s": None, "error": ctypes.get_last_error(), "t": time.time()}
    try:
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(handle, ctypes.byref(code))
        return {"alive": code.value == 259, "cpu_s": _times(handle)[1], "t": time.time()}  # 259 = STILL_ACTIVE
    finally:
        k.CloseHandle(handle)


# --- the synthetic library -----------------------------------------------------------------------------------------
def corpus_texts(spec: dict):  # type: ignore[no-untyped-def]
    rng = random.Random(spec["seed"])
    vocab = spec["vocabulary"]
    for _ in range(spec["papers"] * spec["chunks_per_paper"]):
        yield " ".join(rng.choice(vocab) for _ in range(spec["words_per_chunk"])).capitalize() + "."


def corpus_digest(spec: dict) -> str:
    digest = hashlib.sha256()
    for text in corpus_texts(spec):
        digest.update(text.encode("utf-8") + b"\n")
    return digest.hexdigest()


def db_url(args: argparse.Namespace) -> str:
    return "sqlite:///" + str(Path(args.work) / "db" / "library.sqlite").replace("\\", "/")


def fake_app(engine):  # type: ignore[no-untyped-def]
    """The ``app.state`` the app's resolvers read: an app-owned model registry and the engine, nothing injected."""
    from app.backend.model_runtime import ModelRuntimeRegistry

    return SimpleNamespace(state=SimpleNamespace(engine=engine, model_runtime_registry=ModelRuntimeRegistry()))


def fixture_chunk_ids(engine) -> list[int]:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.backend.persistence.schema import chunks

    with engine.connect() as conn:
        rows = conn.execute(
            select(chunks.c.id).where(chunks.c.chunking_strategy == "p1b-fixture-v1").order_by(chunks.c.id)
        ).all()
    return [int(r[0]) for r in rows]


# --- phases --------------------------------------------------------------------------------------------------------
def phase_identity(args: argparse.Namespace) -> None:
    sys.path.insert(0, str(HERE.parent / "p1"))
    import p1_probe  # the P1 identity phase, unchanged

    p1_probe.phase_identity(args)
    CHECKS.extend(p1_probe.CHECKS)
    DATA.update(p1_probe.DATA)


def phase_provision(args: argparse.Namespace) -> None:
    from huggingface_hub import snapshot_download

    from app.backend.model_provisioning import MANIFESTS
    from app.backend.model_provisioning.provisioner import VERIFIED, Provisioner, default_cache_dir

    cache = default_cache_dir()
    if not check(
        "hf_cache_is_disposable",
        "isolation",
        Path(cache).resolve().is_relative_to(Path(args.work).resolve()),
        str(cache),
    ):
        return
    DATA["tracks"] = {}
    for track in ("arctic-s", "deberta-v3-base"):  # serial; committed byte manifests
        started = time.monotonic()
        status = Provisioner(MANIFESTS[track], cache_dir=cache, state_dir=Path(args.state)).provision_once()
        DATA["tracks"][track] = {**status, "seconds": round(time.monotonic() - started, 1)}
        kind = status.get("error_kind")
        verdict_kind = (
            "integrity" if kind in {"integrity", "contract", "pinned_revision_unavailable"} else "infrastructure"
        )
        check(
            f"provisioned_{track}",
            verdict_kind,
            status["state"] == VERIFIED,
            {"state": status["state"], "error_kind": kind},
        )
    fixture = load_fixture(args.fixture)
    receipt = {
        "note": (
            "MiniLM and MiniLM2 have revision pins but no committed byte manifest. This inventory was taken from the "
            "Hub at the pinned revision in this run; the Hub client's own transfer check is the only upstream check. "
            "It is weaker than a committed manifest and is not presented as one."
        ),
        "models": {},
    }
    for key in ("minilm", "minilm2"):
        spec = fixture["models"][key]
        started = time.monotonic()
        try:
            root = Path(
                snapshot_download(
                    spec["model"],
                    revision=spec["revision"],
                    cache_dir=cache,
                    allow_patterns=BASELINE_PATTERNS,
                    ignore_patterns=BASELINE_IGNORE,
                )
            )
        except Exception as exc:  # noqa: BLE001 -- a transfer problem is the runner's, recorded verbatim
            check(f"provisioned_{key}", "infrastructure", False, f"{type(exc).__name__}: {str(exc)[:300]}")
            continue
        files = sorted(p for p in root.rglob("*") if p.is_file())
        inventory = [
            {"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size, "sha256": sha256_file(p)} for p in files
        ]
        receipt["models"][key] = {
            "repo": spec["model"],
            "revision": spec["revision"],
            "snapshot_dir": root.name,
            "allow_patterns": BASELINE_PATTERNS,
            "ignore_patterns": BASELINE_IGNORE,
            "source": "https://huggingface.co (huggingface_hub.snapshot_download)",
            "seconds": round(time.monotonic() - started, 1),
            "files": inventory,
        }
        check(f"pinned_revision_{key}", "integrity", root.name == spec["revision"], root.name)
        check(
            f"provisioned_{key}",
            "infrastructure",
            any(f["path"].endswith(".safetensors") for f in inventory),
            f"{len(inventory)} files, {sum(f['bytes'] for f in inventory)} bytes",
        )
    (Path(args.state) / "baseline-inventory.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    DATA["baseline_inventory"] = receipt


def phase_verify(args: argparse.Namespace) -> None:
    require_offline()
    from app.backend.model_provisioning import MANIFESTS
    from app.backend.model_provisioning.manifests import ContractMismatch, check_static_contract
    from app.backend.model_provisioning.provisioner import Provisioner, default_cache_dir
    from app.backend.model_provisioning.runner import local_files_only_for
    from app.backend.model_runtime import PINNED_MODEL_REVISIONS

    cache = Path(default_cache_dir())
    for track, manifest in MANIFESTS.items():
        check(
            f"pinned_revision_{track}",
            "integrity",
            PINNED_MODEL_REVISIONS[manifest.repo_id] == manifest.revision,
            manifest.revision,
        )
        provisioner = Provisioner(manifest, cache_dir=cache, state_dir=Path(args.state))
        root = provisioner.snapshot_root
        bad = [
            f.path
            for f in manifest.files
            if not (root / f.path).is_file()
            or (root / f.path).stat().st_size != f.size
            or sha256_file(root / f.path) != f.sha256
        ]
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
    receipt = json.loads((Path(args.state) / "baseline-inventory.json").read_text(encoding="utf-8"))
    for key, model in receipt["models"].items():
        root = cache / ("models--" + model["repo"].replace("/", "--")) / "snapshots" / model["revision"]
        bad = [
            f["path"]
            for f in model["files"]
            if not (root / f["path"]).is_file() or sha256_file(root / f["path"]) != f["sha256"]
        ]
        present = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
        extra = sorted(set(present) - {f["path"] for f in model["files"]})
        check(
            f"baseline_inventory_{key}",
            "integrity",
            not bad and not extra,
            {"changed": bad, "extra": extra} if bad or extra else f"{len(present)} files",
        )
        check(
            f"pinned_revision_{key}",
            "integrity",
            PINNED_MODEL_REVISIONS[model["repo"]] == model["revision"],
            model["revision"],
        )
    repos = sorted(p.name for p in cache.glob("models--*"))
    expected = sorted(
        "models--" + r.replace("/", "--")
        for r in [m.repo_id for m in MANIFESTS.values()] + [m["repo"] for m in receipt["models"].values()]
    )
    check("cache_holds_only_p1b_models", "isolation", repos == expected, repos)
    check("specter_absent", "isolation", not any("specter" in r.lower() for r in repos), repos)
    partial = [str(p) for p in cache.rglob("*.incomplete")]
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
        else:  # only WSAEACCES (10013) proves the firewall refused this program; anything else is inconclusive
            check(f"blocked_{name}", "infrastructure", result["winerror"] == 10013, result)
    from huggingface_hub import constants, hf_hub_download

    check("hub_offline_constant", "isolation", constants.HF_HUB_OFFLINE is True, constants.HF_HUB_OFFLINE)
    fixture = load_fixture(args.fixture)
    try:  # a file of a provisioned repository that the provisioning patterns excluded
        hf_hub_download(
            fixture["models"]["minilm"]["model"], "onnx/model.onnx", revision=fixture["models"]["minilm"]["revision"]
        )
        check("unprovisioned_file_unavailable", "isolation", False, "an unprovisioned file was returned")
    except Exception as exc:  # noqa: BLE001 -- the refusal is the expected outcome
        check("unprovisioned_file_unavailable", "isolation", True, f"{type(exc).__name__}: {str(exc)[:200]}")


def phase_tokenize(args: argparse.Namespace) -> None:
    if not require_offline():
        return
    from transformers import AutoTokenizer

    fixture = load_fixture(args.fixture)
    pairs = [(p["quote"], p["sentence"]) for p in fixture["pairs"]]
    DATA["tokens"] = {}
    for key in ("deberta", "minilm2"):
        spec = fixture["models"][key]
        tokenizer = AutoTokenizer.from_pretrained(spec["model"], revision=spec["revision"], local_files_only=True)
        lengths = [len(tokenizer(premise, hypothesis)["input_ids"]) for premise, hypothesis in pairs]
        limit = int(min(tokenizer.model_max_length, 512))  # both checkpoints have 512 positions
        DATA["tokens"][key] = {
            "per_pair": lengths,
            "min": min(lengths),
            "median": statistics.median(lengths),
            "max": max(lengths),
            "total": sum(lengths),
            "model_max_length": limit,
        }
        check(f"no_truncation_{key}", "integrity", max(lengths) <= limit, {"max": max(lengths), "limit": limit})


def phase_seed(args: argparse.Namespace) -> None:
    from sqlalchemy import func, insert, select

    from alembic import command
    from app.backend.api.startup import _alembic_config
    from app.backend.persistence.database import make_engine
    from app.backend.persistence.schema import attachments, chunks, papers

    fixture = load_fixture(args.fixture)
    url = db_url(args)
    Path(args.work, "db").mkdir(exist_ok=True)
    started = time.monotonic()
    command.upgrade(_alembic_config(url), "head")
    DATA["migrate_seconds"] = round(time.monotonic() - started, 1)
    engine = make_engine(url)

    def add(conn, title: str, texts: list[str], strategy: str, n: int) -> None:  # type: ignore[no-untyped-def]
        pid = conn.execute(
            insert(papers).values(
                title=title,
                csl_json={"type": "article-journal", "title": title},
                processing_tier="fully-chunked",
                imported_source="p1b-synthetic",
            )
        ).inserted_primary_key[0]
        checksum = f"p1b-synthetic-{n:06d}"
        aid = conn.execute(
            insert(attachments).values(
                paper_id=pid,
                storage_mode="managed",
                availability="missing",
                content_type="application/pdf",
                role="article-fulltext",
                checksum=checksum,
            )
        ).inserted_primary_key[0]
        conn.execute(
            insert(chunks),
            [
                {
                    "paper_id": pid,
                    "attachment_id": aid,
                    "text": text,
                    "page_start": i + 1,
                    "page_end": i + 1,
                    "bbox_coordinate_system": "pdf-points-top-left",
                    "extraction_tool": "p1b-synthetic",
                    "extraction_version": "1",
                    "chunking_strategy": strategy,
                    "chunk_version": f"{strategy}-{n}-{i}",
                    "source_attachment_checksum": checksum,
                }
                for i, text in enumerate(texts)
            ],
        )

    started = time.monotonic()
    with engine.begin() as conn:
        n = 0
        for item in fixture["pairs"]:
            n += 1
            add(conn, f"Synthetic fixture paper {item['id']}", [item["chunk_text"]], "p1b-fixture-v1", n)
        for i, text in enumerate(fixture["distractor_chunks"]):
            n += 1
            add(conn, f"Synthetic distractor paper {i + 1:02d}", [text], "p1b-fixture-v1", n)
        spec = fixture["indexing_corpus"]
        texts = corpus_texts(spec)
        for paper in range(spec["papers"]):
            n += 1
            add(
                conn,
                f"Synthetic indexing paper {paper + 1:03d}",
                [next(texts) for _ in range(spec["chunks_per_paper"])],
                "p1b-corpus-v1",
                n,
            )
        counts = {
            "papers": conn.execute(select(func.count()).select_from(papers)).scalar_one(),
            "chunks": conn.execute(select(func.count()).select_from(chunks)).scalar_one(),
        }
    DATA["seed_seconds"] = round(time.monotonic() - started, 1)
    DATA["counts"] = counts
    digest = corpus_digest(fixture["indexing_corpus"])
    DATA["corpus_sha256"] = digest
    expected = 30 + spec["papers"] * spec["chunks_per_paper"]
    check(
        "library_seeded", "integrity", counts["chunks"] == expected and counts["papers"] == 30 + spec["papers"], counts
    )
    check("corpus_digest", "integrity", digest == args.corpus_sha256, digest)
    ids = fixture_chunk_ids(engine)
    check("fixture_chunk_ids", "integrity", ids == list(range(1, 31)), ids)
    engine.dispose()


def _status_matrix(results) -> list[str]:  # type: ignore[no-untyped-def]
    return [r.status for r in results]


def phase_measure(args: argparse.Namespace) -> None:
    created = own_creation_time()
    started = time.time()
    if not require_offline():
        return
    import torch  # noqa: F401 -- imported first, as the app's verifier path does on load
    from sqlalchemy import select

    from app.backend.api.dependencies import resolve_embedding_model
    from app.backend.api.routers.summaries import _verifier
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY
    from app.backend.embeddings.resources import ResourcePolicy, measure
    from app.backend.embeddings.vector_store import SQLiteVecVectorStore
    from app.backend.persistence.database import make_engine
    from app.backend.persistence.schema_index_runs import embedding_index_runs
    from app.backend.summarization.generators import CandidateCitation
    from app.backend.summarization.nli_profiles import BASELINE_NLI_PROFILE_KEY, DEBERTA_NLI_PROFILE_KEY, NLI_PROFILES
    from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig, _source_chunk_for_id
    from app.backend.summarization.verifier_resolution import set_nli_user_preference

    imported = time.time()
    samples = {"after_imports": memory()}
    fixture = load_fixture(args.fixture)
    key = {"deberta": DEBERTA_NLI_PROFILE_KEY, "minilm2": BASELINE_NLI_PROFILE_KEY}[args.model]
    profile = NLI_PROFILES[key]
    expected = fixture["models"][args.model]
    DATA.update(
        label=args.label,
        model=args.model,
        condition=args.condition,
        pid=os.getpid(),
        threads={
            "torch_intra": torch.get_num_threads(),
            "torch_interop": torch.get_num_interop_threads(),
            "cpu_count": os.cpu_count(),
        },
        torch_version=torch.__version__,
    )
    snapshot = measure()
    DATA["resource_policy"] = {**ResourcePolicy.for_machine(snapshot).as_dict(), "snapshot": snapshot.as_dict()}
    engine = make_engine(db_url(args))
    api = fake_app(engine)
    with engine.begin() as conn:
        set_nli_user_preference(conn, key)
    config = VerificationConfig()
    current = {k: getattr(config, k) for k in fixture["verification_thresholds"]}
    check("thresholds_unchanged", "scientific", current == fixture["verification_thresholds"], current)
    scorer, provenance = _verifier(api, engine, None)  # the app's synthesis verifier resolution (inc 619)
    resolved = time.time()
    samples["after_verifier_resolution"] = memory()
    record = provenance["verification_nli"]
    DATA["provenance"] = record
    check(
        "effective_verifier",
        "contract",
        (record["profile"], record["model_name"], record["revision"]) == (key, expected["model"], expected["revision"])
        and record["fallback_reason"] == (None if args.model == "deberta" else "user_choice")
        and record["preference"] == "user"
        and record["embedding_fallback"] is False,
        {
            k: record[k]
            for k in ("profile", "model_name", "revision", "fallback_reason", "preference", "embedding_fallback")
        },
    )
    check(
        "provenance_thresholds",
        "scientific",
        (record["support_threshold"], record["contradiction_threshold"], record["similarity_threshold"])
        == (0.55, 0.55, 0.7),
        [record["support_threshold"], record["contradiction_threshold"], record["similarity_threshold"]],
    )
    runtime = scorer._runtime  # noqa: SLF001
    check(
        "scorer_identity",
        "contract",
        runtime is not None
        and (runtime.identity.model_name, runtime.identity.revision) == (expected["model"], expected["revision"]),
        None if runtime is None else [runtime.identity.model_name, runtime.identity.revision],
    )
    check("no_embedding_fallback", "contract", scorer.fallback_scorer is None, "")
    if args.model == "deberta":
        check(
            "deberta_local_files_only",
            "isolation",
            scorer.local_files_only is True and runtime.identity.local_files_only,
            "",
        )
        check(
            "deberta_contract_verified_at_resolution",
            "contract",
            runtime.loaded_model is not None,
            "verify_nli_checkpoint ran inside resolve_support_scorer",
        )
        labels = [profile.id2label[i] for i in sorted(profile.id2label)]
        check("deberta_label_order", "contract", labels == expected["label_order"], labels)
    model = resolve_embedding_model(api)  # MiniLM, the verification-similarity model
    verifier = LocalCitationVerifier(
        model=model, vector_store=SQLiteVecVectorStore(), config=config, support_scorer=scorer
    )
    ids = fixture_chunk_ids(engine)
    with engine.connect() as conn:
        pool = [_source_chunk_for_id(conn, cid) for cid in ids]
    items = [
        (p["sentence"], CandidateCitation(chunk_id=ids[i], quote=p["quote"])) for i, p in enumerate(fixture["pairs"])
    ]

    def worker_row() -> dict | None:
        if args.condition != "concurrent":
            return None
        with engine.connect() as conn:
            row = conn.execute(
                select(embedding_index_runs.c.indexed_chunks, embedding_index_runs.c.state).where(
                    embedding_index_runs.c.profile_key == ARCTIC_S_PROFILE_KEY
                )
            ).first()
        return None if row is None else {"indexed_chunks": int(row[0]), "state": row[1]}

    def call(index: int) -> dict:
        before = {
            "worker": other_process(args.worker_pid) if args.worker_pid else None,
            "row": worker_row(),
            "system": measure().as_dict(),
        }
        with engine.begin() as conn:
            t0 = time.perf_counter()
            w0 = time.time()
            results = verifier.verify_many(conn, items=items, source_chunks=pool)
            seconds = time.perf_counter() - t0
            w1 = time.time()
        after = {
            "worker": other_process(args.worker_pid) if args.worker_pid else None,
            "row": worker_row(),
            "system": measure().as_dict(),
        }
        return {
            "index": index,
            "seconds": seconds,
            "start": w0,
            "end": w1,
            "before": before,
            "after": after,
            "statuses": _status_matrix(results),
            "memory": memory(),
            "support": [r.support_confidence for r in results],
            "contradiction": [r.contradiction_confidence for r in results],
            "retrieval": [r.retrieval_confidence for r in results],
            "quote": [r.quote_confidence for r in results],
        }

    calls = [call(0)]
    cold_end = calls[0]["end"]
    samples["after_cold"] = memory()
    DATA["cold"] = {
        "process_created": created,
        "probe_started": started,
        "imports_done": imported,
        "verifier_resolved": resolved,
        "first_call_returned": cold_end,
        "cold_seconds": cold_end - created,
        "first_call_seconds": calls[0]["seconds"],
        "interpreter_start_seconds": started - created,
        "imports_seconds": imported - started,
        "verifier_resolution_seconds": resolved - imported,
    }
    for i in range(1, args.warm + 1):
        calls.append(call(i))
    samples["end"] = memory()
    DATA["calls"] = calls
    DATA["warm_seconds"] = [c["seconds"] for c in calls[1:]]
    DATA["memory_samples"] = samples
    statuses = [c["statuses"] for c in calls]
    check(
        "results_complete",
        "contract",
        all(len(s) == len(items) for s in statuses)
        and all(x is not None and math.isfinite(x) for c in calls for x in c["support"] + c["contradiction"]),
        f"{len(calls)} calls x {len(items)} items",
    )
    check("statuses_stable_across_calls", "scientific", all(s == statuses[0] for s in statuses), statuses[0])
    DATA["max_abs_support_difference_across_calls"] = max(
        abs(a - b) for c in calls for a, b in zip(c["support"], calls[0]["support"], strict=True)
    )
    DATA["status_counts"] = {s: statuses[0].count(s) for s in sorted(set(statuses[0]))}
    nli_entries = [
        e for e in api.state.model_runtime_registry.runtime_entries() if e.identity.family == "cross-encoder"
    ]
    check(
        "single_nli_model_resident",
        "contract",
        [e.identity.model_name for e in nli_entries] == [expected["model"]],
        [e.identity.model_name for e in nli_entries],
    )
    engine.dispose()


def phase_failclosed(args: argparse.Namespace) -> None:
    if not require_offline():
        return
    from dataclasses import replace

    from app.backend.api.dependencies import resolve_embedding_model
    from app.backend.api.routers.summaries import _verifier
    from app.backend.embeddings.resources import ResourceSnapshot
    from app.backend.embeddings.vector_store import SQLiteVecVectorStore
    from app.backend.model_provisioning import DEBERTA_RELEASE_GATES
    from app.backend.model_provisioning.runner import deberta_auto_provisioning_armed
    from app.backend.persistence.database import make_engine
    from app.backend.summarization.generators import CandidateCitation
    from app.backend.summarization.nli_profiles import (
        BASELINE_NLI_PROFILE_KEY,
        DEBERTA_NLI_PROFILE_KEY,
        NLI_PROFILES,
        NliProfileConfigurationError,
        verify_nli_checkpoint,
    )
    from app.backend.summarization.verification import LocalCitationVerifier, NLIInferenceError, _source_chunk_for_id
    from app.backend.summarization.verifier_resolution import (
        NliPreference,
        VerifierUnavailableError,
        decide,
        memory_check,
        set_nli_user_preference,
    )

    check(
        "release_gate_not_armed",
        "contract",
        DEBERTA_RELEASE_GATES.get("packaged_runtime_acceptance") is False
        and not deberta_auto_provisioning_armed(DEBERTA_RELEASE_GATES),
        dict(DEBERTA_RELEASE_GATES),
    )
    automatic = decide(
        NliPreference(None),
        gates_armed=deberta_auto_provisioning_armed(DEBERTA_RELEASE_GATES),
        model_state=lambda: "verified",
        checkpoint_required=True,
        memory=lambda: None,
    )  # type: ignore[arg-type,return-value]
    check(
        "automatic_selection_stays_minilm2",
        "contract",
        automatic.profile.key == BASELINE_NLI_PROFILE_KEY and automatic.fallback_reason == "not_qualified",
        [automatic.profile.key, automatic.fallback_reason],
    )
    low = ResourceSnapshot(
        total_physical_mb=16384,
        available_physical_mb=600,
        commit_limit_mb=20000,
        available_commit_mb=600,
        source="simulated",
    )
    try:
        decision = decide(
            NliPreference(DEBERTA_NLI_PROFILE_KEY),
            gates_armed=False,
            model_state=lambda: "verified",
            checkpoint_required=True,
            memory=lambda: memory_check(lambda: low, resident=False),
        )
        check("explicit_deberta_refused_on_low_memory", "contract", False, f"returned {decision.profile.key}")
    except VerifierUnavailableError as exc:
        check("explicit_deberta_refused_on_low_memory", "contract", True, str(exc)[:200])
    engine = make_engine(db_url(args))
    api = fake_app(engine)
    with engine.begin() as conn:
        set_nli_user_preference(conn, DEBERTA_NLI_PROFILE_KEY)
    scorer, _ = _verifier(api, engine, None)
    runtime = scorer._runtime  # noqa: SLF001
    wrong = replace(NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY], id2label={0: "contradiction", 1: "entailment", 2: "neutral"})
    try:
        runtime.run(lambda m: verify_nli_checkpoint(m, wrong))
        check("wrong_label_order_refused", "contract", False, "accepted")
    except NliProfileConfigurationError as exc:
        check("wrong_label_order_refused", "contract", True, str(exc)[:200])

    class FailingRuntime:  # the loaded DeBERTa runtime, with an allocation failure injected into inference
        identity = runtime.identity

        def run(self, operation):  # type: ignore[no-untyped-def]
            def fail(model):  # type: ignore[no-untyped-def]
                raise RuntimeError("simulated allocation failure: not enough memory")

            return runtime.run(fail)

    failing = replace(scorer, _runtime=FailingRuntime())
    fixture = load_fixture(args.fixture)
    with engine.connect() as conn:
        pool = [_source_chunk_for_id(conn, cid) for cid in fixture_chunk_ids(engine)]
    verifier = LocalCitationVerifier(
        model=resolve_embedding_model(api), vector_store=SQLiteVecVectorStore(), support_scorer=failing
    )
    items = [
        (p["sentence"], CandidateCitation(chunk_id=pool[i].chunk_id, quote=p["quote"]))
        for i, p in enumerate(fixture["pairs"])
    ]
    try:
        with engine.begin() as conn:
            verifier.verify_many(conn, items=items, source_chunks=pool)
        check("inference_failure_fails_closed", "contract", False, "verify_many returned results")
    except NLIInferenceError as exc:
        check("inference_failure_fails_closed", "contract", True, str(exc)[:200])
    names = [
        e.identity.model_name
        for e in api.state.model_runtime_registry.runtime_entries()
        if e.identity.family == "cross-encoder"
    ]
    check("no_substitute_nli_loaded", "contract", names == [fixture["models"]["deberta"]["model"]], names)
    engine.dispose()


def phase_arm_worker(args: argparse.Namespace) -> None:
    import uuid

    from app.backend.embeddings import disk_guard, index_runs
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, get_profile
    from app.backend.model_provisioning.runner import checkpoint_pending
    from app.backend.persistence.database import make_engine

    engine = make_engine(db_url(args))
    profile = get_profile(ARCTIC_S_PROFILE_KEY)
    check("arctic_checkpoint_not_pending", "integrity", not checkpoint_pending(profile.model_name), profile.model_name)
    row = index_runs.upsert_requested(
        engine, profile, batch_size=WORKER_BATCH
    )  # what the Settings "Build" action records
    remaining = max(0, int(row["eligible_chunks"]) - int(row["indexed_chunks"]))
    disk = disk_guard.check(db_url(args), batch_size=WORKER_BATCH, remaining_chunks=remaining)
    check("disk_guard_allows_start", "infrastructure", disk.ok, disk.row_values())
    token = uuid.uuid4().hex
    index_runs.update_run(
        engine,
        ARCTIC_S_PROFILE_KEY,
        state="running",
        worker_token=token,
        worker_pid=None,
        worker_started_at=index_runs.now(),
        heartbeat_at=index_runs.now(),
        attempts=int(row["attempts"]) + 1,
        next_retry_at=None,
        failure_kind=None,
        failure_detail=None,
        diagnostic=None,
        **disk.row_values(),
    )  # as IndexSupervisor._maybe_launch
    Path(args.state, "worker-token").write_text(token, encoding="ascii")  # private: the state dir is never uploaded
    DATA.update(
        token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        profile=profile.key,
        model_version=profile.model_version,
        eligible_chunks=int(row["eligible_chunks"]),
        batch_size=WORKER_BATCH,
        threads=WORKER_THREADS,
    )
    check("run_row_armed", "integrity", int(row["eligible_chunks"]) > 0, int(row["eligible_chunks"]))
    engine.dispose()


def _run_row(args: argparse.Namespace) -> dict | None:
    from app.backend.embeddings import index_runs
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY
    from app.backend.persistence.database import make_engine

    engine = make_engine(db_url(args))
    with engine.connect() as conn:
        row = index_runs.get_run(conn, ARCTIC_S_PROFILE_KEY)
    engine.dispose()
    return (
        None
        if row is None
        else {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items() if k != "worker_token"}
    )


def phase_worker_status(args: argparse.Namespace) -> None:
    row = _run_row(args)
    DATA["row"] = row
    check("run_row_readable", "infrastructure", row is not None, "")


def phase_stop_worker(args: argparse.Namespace) -> None:
    from app.backend.embeddings import index_runs
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY
    from app.backend.persistence.database import make_engine

    engine = make_engine(db_url(args))
    index_runs.update_run(engine, ARCTIC_S_PROFILE_KEY, intent="pause")  # the worker honours it between batches
    engine.dispose()
    DATA["row"] = _run_row(args)
    check(
        "pause_intent_recorded",
        "infrastructure",
        (DATA["row"] or {}).get("intent") == "pause",
        (DATA["row"] or {}).get("intent"),
    )


# --- evaluation (pure; unit-tested by p1b_selftest.py) -------------------------------------------------------------
def concurrency_established(result: dict) -> tuple[bool, dict]:
    """A condition B process counts as concurrent only if the worker was alive and busy during every warm call and its
    committed progress rose across the warm window (P1B_PREDECLARATION.md §7)."""
    warm = result["data"]["calls"][1:]
    ratios, alive = [], True
    for c in warm:
        b, a = c["before"]["worker"], c["after"]["worker"]
        if not (b and a and b["alive"] and a["alive"] and b["cpu_s"] is not None and a["cpu_s"] is not None):
            alive = False
            ratios.append(None)
            continue
        ratios.append((a["cpu_s"] - b["cpu_s"]) / max(1e-9, c["end"] - c["start"]))
    first, last = warm[0]["before"]["row"], warm[-1]["after"]["row"]
    progress = None if not (first and last) else last["indexed_chunks"] - first["indexed_chunks"]
    busy = all(r is not None and r >= CONCURRENCY_MIN_CPU_RATIO for r in ratios)
    ok = alive and busy and progress is not None and progress > 0
    return ok, {
        "alive_every_call": alive,
        "worker_cpu_ratio_per_call": ratios,
        "chunks_committed_during_warm": progress,
        "min_cpu_ratio_required": CONCURRENCY_MIN_CPU_RATIO,
    }


def evaluate(results: dict[str, dict], discarded: dict[str, list[str]]) -> tuple[list[dict], dict]:
    """``results`` maps label -> measure-phase result for the COUNTED processes; ``discarded`` maps condition -> the
    labels the noise rule discarded. Returns (checks, summary)."""
    checks: list[dict] = []
    summary: dict = {"limits": LIMITS, "conditions": {}}

    def add(cid: str, kind: str, ok: bool, detail: object) -> None:
        checks.append({"id": cid, "kind": kind, "ok": bool(ok), "detail": detail})

    def counted(prefix: str) -> list[tuple[str, dict]]:
        return sorted((k, v) for k, v in results.items() if k.startswith(prefix))

    deberta_memory = []
    for condition, prefix, limit_key in (
        ("solo", "deberta_solo_", "warm_solo_s"),
        ("concurrent", "deberta_concurrent_", "warm_concurrent_s"),
    ):
        rows = counted(prefix)
        info: dict = {"processes": {}}
        summary["conditions"][f"deberta_{condition}"] = info
        info["discarded"] = discarded.get(f"deberta_{condition}", [])
        if len(rows) != PROCESSES_PER_CONDITION or any(
            len(v["data"].get("warm_seconds", [])) != WARM_REPETITIONS for _, v in rows
        ):
            add(
                f"deberta_{condition}_measurements_complete",
                "infrastructure",
                False,
                {
                    "processes": [k for k, _ in rows],
                    "warm_counts": [len(v["data"].get("warm_seconds", [])) for _, v in rows],
                },
            )
            continue
        add(f"deberta_{condition}_measurements_complete", "infrastructure", True, [k for k, _ in rows])
        established = True
        for label, v in rows:
            d = v["data"]
            warm = d["warm_seconds"]
            mem = d["memory_samples"]["end"]
            deberta_memory.append((label, mem["peak_working_set_bytes"], mem["peak_commit_bytes"]))
            entry = {
                "warm_seconds": warm,
                "median_s": statistics.median(warm),
                "min_s": min(warm),
                "max_s": max(warm),
                "cold_s": d["cold"]["cold_seconds"],
                "first_call_s": d["cold"]["first_call_seconds"],
                "peak_working_set_bytes": mem["peak_working_set_bytes"],
                "peak_commit_bytes": mem["peak_commit_bytes"],
            }
            if condition == "concurrent":
                ok, evidence = concurrency_established(v)
                entry["concurrency"] = {"established": ok, **evidence}
                established = established and ok
            info["processes"][label] = entry
        medians = [e["median_s"] for e in info["processes"].values()]
        info.update(
            acceptance_statistic_s=max(medians),
            median_range_s=[min(medians), max(medians)],
            pooled_median_s=statistics.median([x for e in info["processes"].values() for x in e["warm_seconds"]]),
            limit_s=LIMITS[limit_key],
        )
        if condition == "concurrent":
            add(
                "deberta_concurrent_overlap_established",
                "infrastructure",
                established,
                {k: e["concurrency"] for k, e in info["processes"].items()},
            )
            if not established:
                info["evaluated"] = False
                continue
        info["evaluated"] = True
        add(
            f"deberta_{condition}_warm_median",
            "performance",
            max(medians) <= LIMITS[limit_key],
            {"largest_process_median_s": max(medians), "process_medians_s": medians, "limit_s": LIMITS[limit_key]},
        )
    if deberta_memory:
        ws = max(m[1] for m in deberta_memory)
        cm = max(m[2] for m in deberta_memory)
        summary["memory"] = {
            "processes": [
                {
                    "label": m[0],
                    "peak_working_set_mb": m[1] / 1e6,
                    "peak_working_set_mib": m[1] / 2**20,
                    "peak_commit_mb": m[2] / 1e6,
                    "peak_commit_mib": m[2] / 2**20,
                }
                for m in deberta_memory
            ],
            "peak_working_set_mb": ws / 1e6,
            "peak_commit_mb": cm / 1e6,
        }
        complete = len(deberta_memory) == 2 * PROCESSES_PER_CONDITION
        add("deberta_memory_measurements_complete", "infrastructure", complete, [m[0] for m in deberta_memory])
        add(
            "deberta_peak_working_set",
            "performance",
            ws / 1e6 <= LIMITS["peak_working_set_mb"],
            {"peak_mb": ws / 1e6, "limit_mb": LIMITS["peak_working_set_mb"]},
        )
        add(
            "deberta_peak_commit",
            "performance",
            cm / 1e6 <= LIMITS["peak_commit_mb"],
            {"peak_mb": cm / 1e6, "limit_mb": LIMITS["peak_commit_mb"]},
        )
    else:
        add("deberta_memory_measurements_complete", "infrastructure", False, "no DeBERTa process measured")
    summary["minilm2_reference"] = {
        k: {
            "warm_seconds": v["data"]["warm_seconds"],
            "median_s": statistics.median(v["data"]["warm_seconds"]),
            "cold_s": v["data"]["cold"]["cold_seconds"],
            "peak_working_set_bytes": v["data"]["memory_samples"]["end"]["peak_working_set_bytes"],
        }
        for k, v in sorted(results.items())
        if k.startswith("minilm2_") and v["data"].get("warm_seconds")
    }
    return checks, summary


def phase_evaluate(args: argparse.Namespace) -> None:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    results = {label: json.loads(Path(path).read_text(encoding="utf-8")) for label, path in plan["counted"].items()}
    checks, summary = evaluate(results, plan.get("discarded", {}))
    CHECKS.extend(checks)
    DATA["summary"] = summary


PHASES = {
    "identity": phase_identity,
    "provision": phase_provision,
    "verify": phase_verify,
    "netcheck": phase_netcheck,
    "tokenize": phase_tokenize,
    "seed": phase_seed,
    "measure": phase_measure,
    "failclosed": phase_failclosed,
    "arm_worker": phase_arm_worker,
    "worker_status": phase_worker_status,
    "stop_worker": phase_stop_worker,
    "evaluate": phase_evaluate,
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
    parser.add_argument("--corpus-sha256")
    parser.add_argument("--target-ip")
    parser.add_argument("--target-hosts", nargs="*", default=[])
    parser.add_argument("--model", choices=["deberta", "minilm2"])
    parser.add_argument("--condition", choices=["solo", "concurrent"])
    parser.add_argument("--label")
    parser.add_argument("--warm", type=int, default=WARM_REPETITIONS)
    parser.add_argument("--worker-pid", type=int, default=0)
    parser.add_argument("--plan")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))  # -I keeps the checkout off sys.path unless named explicitly
    try:
        PHASES[args.phase](args)
    except Exception as exc:  # noqa: BLE001 -- recorded as a failed check; the driver turns it into the verdict
        kind = "infrastructure" if args.phase in {"provision", "evaluate"} else "integrity"
        check("phase_exception", kind, False, f"{type(exc).__name__}: {exc}")
        DATA["traceback"] = traceback.format_exc()
    if sys.platform == "win32":
        DATA["final_memory"] = memory()
    Path(args.out).write_text(
        json.dumps({"phase": args.phase, "checks": CHECKS, "data": DATA}, indent=1, default=str), encoding="utf-8"
    )
    return 0 if CHECKS and all(c["ok"] for c in CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
