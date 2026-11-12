"""Local, model-free self-test of the P1b harness (run before publishing the qualification branch).

    python -B tools/qualification/p1b/p1b_selftest.py

No checkpoint is downloaded or loaded. Checks:
* the frozen fixture (shape, pinned revisions, unchanged thresholds, quote-in-chunk, lengths) and the corpus digest;
* the predeclared limits in the probe equal the predeclaration;
* the probe's real ``seed``, ``measure``, ``failclosed``, ``arm_worker``, ``worker_status``, ``stop_worker`` and
  ``evaluate`` phases end to end on a temporary database, with fake CrossEncoder/SentenceTransformer objects injected
  through ``ModelRuntimeRegistry`` factories (the app's own resolution, verifier and status code runs unchanged);
* that an armed run row is claimable by the worker protocol with the issued token;
* ``evaluate`` and ``concurrency_established`` on synthetic receipts (pass, performance fail, missing overlap);
* PowerShell syntax of the driver and the workflow's trigger, permission and credential settings;
* the v1/v2/v3 predeclaration pins and the v3 settling constants (inc 639); ``p1b_driver_selftest.ps1`` covers the
  per-process noise rule and idle settling on synthetic snapshots with a simulated clock.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))
RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: object = "") -> None:
    RESULTS.append((name, bool(ok), str(detail)[:300]))
    print(f"{'PASS' if ok else 'FAIL'} {name} {str(detail)[:300]}")


# --- fakes (stand-ins for the checkpoints; never a measurement) ----------------------------------------------------
class _Config(SimpleNamespace):
    pass


class DebertaV2TokenizerFake:  # name prefix satisfies the DeBERTa tokenizer contract
    pass


P1_FIXTURE = json.loads((REPO / "tools/qualification/p1/fixtures/p1-probe-v1.json").read_text(encoding="utf-8"))
P1_REFERENCE = {
    tuple(pair): row
    for pair, row in zip(
        P1_FIXTURE["deberta"]["pairs_premise_hypothesis"], P1_FIXTURE["deberta"]["reference_probabilities"], strict=True
    )
}


class FakeCrossEncoder:
    """Carries real torch parameters in ``dtype`` and rounds its scores through that dtype, as a float16 model's
    predict() would before casting to float32; the frozen P1 pairs return the P1 float32 reference."""

    def __init__(self, labels: dict[int, str], model_type: str, tokenizer: object, dtype: str = "float32") -> None:
        import torch

        self.model = SimpleNamespace(config=_Config(id2label=labels, model_type=model_type))
        self.config = self.model.config
        self.tokenizer = tokenizer
        self.dtype = getattr(torch, dtype)
        self.weights = torch.nn.Linear(2, 3).to(self.dtype)
        if model_type == "deberta-v2":  # the snapshot revision transformers records on a cache load
            self.model.config._commit_hash = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"

    def named_parameters(self):  # type: ignore[no-untyped-def]
        return self.weights.named_parameters()

    def named_buffers(self):  # type: ignore[no-untyped-def]
        return self.weights.named_buffers()

    def predict(self, pairs, apply_softmax=True):  # type: ignore[no-untyped-def]
        import numpy
        import torch

        rows = self._scores(pairs)
        return torch.tensor(rows, dtype=torch.float64).to(self.dtype).float().numpy().astype(numpy.float32)

    def _scores(self, pairs):  # type: ignore[no-untyped-def]
        out = []
        for premise, hypothesis in pairs:
            if (premise, hypothesis) in P1_REFERENCE and self.model.config.id2label[0] == "entailment":
                out.append(P1_REFERENCE[(premise, hypothesis)])
                continue
            overlap = len(set(premise.lower().split()) & set(hypothesis.lower().split())) / max(
                1, len(set(hypothesis.lower().split()))
            )
            ent = min(0.95, overlap)
            out.append(
                [ent, 0.05, max(0.0, 0.95 - ent)]
                if self.model.config.id2label[0] == "entailment"
                else [max(0.0, 0.95 - ent), ent, 0.05]
            )
        return out


class FakeSentenceTransformer:
    max_seq_length = 256
    _modules: dict = {}

    def get_sentence_embedding_dimension(self) -> int:
        return 384

    def encode(self, texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True):  # type: ignore[no-untyped-def]
        import hashlib
        import math

        vectors = []
        for text in texts:
            raw = [b / 255.0 - 0.5 for b in hashlib.sha256(text.encode()).digest()] * 12
            norm = math.sqrt(sum(x * x for x in raw))
            vectors.append([x / norm for x in raw])
        import numpy

        return numpy.array(vectors, dtype=numpy.float32)


DEBERTA_FAKE_DTYPE = {"dtype": "float32"}  # a test switch: "float16" emulates the defect run 41948518913 measured


def fake_cross_encoder(identity):  # type: ignore[no-untyped-def]
    if "DeBERTa" in identity.model_name:
        return FakeCrossEncoder(
            {0: "entailment", 1: "neutral", 2: "contradiction"},
            "deberta-v2",
            DebertaV2TokenizerFake(),
            DEBERTA_FAKE_DTYPE["dtype"],
        )
    return FakeCrossEncoder({0: "contradiction", 1: "entailment", 2: "neutral"}, "bert", object())


def fake_app_factory(engine):  # type: ignore[no-untyped-def]
    from app.backend.model_runtime import ModelRuntimeRegistry

    registry = ModelRuntimeRegistry(
        sentence_transformer_factory=lambda identity: FakeSentenceTransformer(),
        cross_encoder_factory=fake_cross_encoder,
    )
    return SimpleNamespace(state=SimpleNamespace(engine=engine, model_runtime_registry=registry))


# --- checks --------------------------------------------------------------------------------------------------------
def fixture_checks() -> dict:
    import p1b_probe as probe

    from app.backend.model_runtime import PINNED_MODEL_REVISIONS
    from app.backend.summarization.nli_profiles import DEBERTA_NLI_PROFILE_KEY, NLI_PROFILES
    from app.backend.summarization.verification import VerificationConfig

    fx = json.loads((HERE / "fixtures" / "p1b-pairs-v1.json").read_text(encoding="utf-8"))
    record("fixture_21_pairs", len(fx["pairs"]) == 21 and len({p["id"] for p in fx["pairs"]}) == 21)
    record("fixture_quote_in_chunk", all(p["quote"] in p["chunk_text"] for p in fx["pairs"]))
    record(
        "fixture_quote_lengths",
        all(250 <= len(p["quote"]) <= 500 for p in fx["pairs"]),
        sorted(len(p["quote"]) for p in fx["pairs"]),
    )
    record("fixture_distractors", len(fx["distractor_chunks"]) == 9)
    record(
        "fixture_revisions_pinned",
        all(
            PINNED_MODEL_REVISIONS[fx["models"][k]["model"]] == fx["models"][k]["revision"]
            for k in ("deberta", "minilm2", "minilm")
        ),
    )
    labels = NLI_PROFILES[DEBERTA_NLI_PROFILE_KEY].id2label
    record("fixture_label_order", [labels[i] for i in sorted(labels)] == fx["models"]["deberta"]["label_order"])
    cfg = VerificationConfig()
    record(
        "fixture_thresholds_unchanged",
        {k: getattr(cfg, k) for k in fx["verification_thresholds"]} == fx["verification_thresholds"],
    )
    driver = (HERE / "p1b_qualify.ps1").read_text(encoding="utf-8")
    digest = probe.corpus_digest(fx["indexing_corpus"])
    record("corpus_digest_pinned_in_driver", f"$CorpusSha = '{digest}'" in driver, digest)
    text = (HERE / "P1B_PREDECLARATION.md").read_text(encoding="utf-8")
    record(
        "limits_match_predeclaration",
        probe.LIMITS
        == {"warm_solo_s": 7.2, "warm_concurrent_s": 8.8, "peak_working_set_mb": 2520, "peak_commit_mb": 2870}
        and "≤ 7.2 s" in text
        and "≤ 8.8 s" in text
        and "≤ 2,520 MB" in text
        and "≤ 2,870 MB" in text,
    )
    import hashlib

    v2 = (HERE / "P1B_PREDECLARATION_V2.md").read_bytes()
    v2_text = v2.decode("utf-8")
    record(
        "predeclaration_v1_unchanged_and_pinned",
        "$PredeclarationSha = '6a5a2d85adce3c91d05a81ce506373d190c5e7474ecb9eb6873f75bc8d93e063'" in driver
        and hashlib.sha256((HERE / "P1B_PREDECLARATION.md").read_bytes()).hexdigest()
        == "6a5a2d85adce3c91d05a81ce506373d190c5e7474ecb9eb6873f75bc8d93e063",
    )
    record(
        "predeclaration_v2_pinned_in_driver",
        f"$PredeclarationV2Sha = '{hashlib.sha256(v2).hexdigest()}'" in driver,
        hashlib.sha256(v2).hexdigest(),
    )
    record(
        "v2_limits_unchanged",
        all(x in v2_text for x in ("≤ 7.2 s", "≤ 8.8 s", "≤ 2,520 MB", "≤ 2,870 MB"))
        and "acd2723c" in v2_text
        and "fixtures/p1b-pairs-v1.json" in v2_text,
    )
    v3 = (HERE / "P1B_PREDECLARATION_V3.md").read_bytes()
    v3_text = v3.decode("utf-8")
    record(
        "predeclaration_v2_unchanged",
        hashlib.sha256(v2).hexdigest() == "cd04c73ad591d8ef1af48dd4cca720103f64bd3e0e2eee40f7da6af13633d030",
        hashlib.sha256(v2).hexdigest(),
    )
    record(
        "predeclaration_v3_pinned_in_driver",
        f"$PredeclarationV3Sha = '{hashlib.sha256(v3).hexdigest()}'" in driver
        and "'predeclaration_v3_sha256' 'integrity'" in driver,
        hashlib.sha256(v3).hexdigest(),
    )
    record(
        "v3_limits_unchanged",
        all(
            x in v3_text
            for x in ("≤ 7.2 s", "≤ 8.8 s", "≤ 2,520 MB", "≤ 2,870 MB", "acd2723c", "0.25 CPU-s per wall-second")
        ),
    )
    noise = (HERE / "p1b_noise.ps1").read_text(encoding="utf-8")
    constants = {
        "$NoiseForeignCpuRatio = 0.25 ": "0.25 CPU-s per wall-second",
        "$SettleQuietRatio = 0.20 ": "0.20 CPU-s per wall-second",
        "$SettleWindowSec = 10.0 ": "| Window | 10 s",
        "$SettleWindows = 3 ": "3 consecutive quiet windows (30 s)",
        "$SettleAttemptSec = 180.0 ": "180 s per settling attempt",
        "$SettleTotalSec = 600.0 ": "600 s of settling in total",
    }
    record(
        "v3_settling_constants_match_predeclaration",
        all(k in noise and v in v3_text for k, v in constants.items())
        and "$NoiseForeignCpuRatio = " not in driver
        and ". $NoiseModule" in driver,
        [k for k, v in constants.items() if k not in noise or v not in v3_text],
    )
    record(
        "v3_settling_solo_only_and_before_measurement",
        "if ($Condition -eq 'solo') {\n                $st = Wait-IdleSettled" in driver
        and driver.index("$st = Wait-IdleSettled") < driver.index("$r = Invoke-Phase $Stage 'measure'"),
    )
    record(
        "v3_settling_never_alters_processes",
        not any(
            x in noise for x in ("Stop-Process", "Kill(", "PriorityClass", "Suspend", "Stop-Service", "Set-Service")
        ),
    )
    stages = driver.split("$Stages = ", 1)[1].split("\n\n", 1)[0]
    order = [s.strip(" '\n") for s in stages.replace("\n", ",").split(",") if s.strip(" '\n")]
    record(
        "precision_stage_before_any_timing",
        order.index("tokenize") + 1 == order.index("precision") == order.index("seed") - 1
        and order.index("precision") < order.index("warmup")
        and "Phase-Stage 'precision' 'precision' $true 900 $true)) { return }" in driver,
        order,
    )
    allowed = driver.split("$AllowedChanges = @(", 1)[1].split(")", 1)[0]
    record(
        "allowlist_is_exactly_the_correction",
        sorted(x.strip().strip("'") for x in allowed.replace("\n", ",").split(",") if x.strip())
        == sorted(
            [
                "^tools/qualification/p1b/",
                r"^\.github/workflows/p1b-qualification\.yml$",
                r"^app/backend/model_runtime\.py$",
                r"^app/backend/summarization/verification\.py$",
                r"^app/backend/summarization/stance\.py$",
                r"^tests/test_nli_precision\.py$",
                r"^tests/test_desktop_packaging\.py$",
            ]
        ),
        allowed,
    )
    return fx


def run_phase(probe, phase: str, args: argparse.Namespace) -> dict:  # type: ignore[no-untyped-def]
    probe.CHECKS.clear()
    probe.DATA.clear()
    try:
        probe.PHASES[phase](args)
    except Exception as exc:  # noqa: BLE001
        probe.check("phase_exception", "integrity", False, f"{type(exc).__name__}: {exc}")
    return {"phase": phase, "checks": list(probe.CHECKS), "data": json.loads(json.dumps(probe.DATA, default=str))}


def pipeline_checks(fx: dict) -> None:
    import p1b_probe as probe

    from app.backend.embeddings import index_runs, resources
    from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY
    from app.backend.persistence.database import make_engine

    big = resources.ResourceSnapshot(
        total_physical_mb=16384,
        available_physical_mb=12000,
        commit_limit_mb=20000,
        available_commit_mb=14000,
        source="selftest",
    )
    resources.measure = lambda: big  # the app's memory precheck reads this; the laptop's own memory is irrelevant here
    probe.fake_app = fake_app_factory
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        small = json.loads(json.dumps(fx))
        small["indexing_corpus"].update(papers=3, chunks_per_paper=5)
        fixture = Path(tmp, "fixture.json")
        fixture.write_text(json.dumps(small), encoding="utf-8")
        Path(tmp, "db").mkdir()
        args = argparse.Namespace(
            work=tmp,
            state=tmp,
            repo=str(REPO),
            fixture=str(fixture),
            corpus_sha256=probe.corpus_digest(small["indexing_corpus"]),
            model=None,
            condition="solo",
            label="t",
            warm=2,
            worker_pid=0,
            plan=None,
        )
        res = run_phase(probe, "seed", args)
        record("seed_phase", all(c["ok"] for c in res["checks"]), res["checks"])
        precision_checks(probe, args)
        out = {}
        for model in ("deberta", "minilm2"):
            args.model = model
            res = run_phase(probe, "measure", args)
            out[model] = res
            record(
                f"measure_{model}_checks",
                all(c["ok"] for c in res["checks"]),
                [c for c in res["checks"] if not c["ok"]] or len(res["checks"]),
            )
            d = res["data"]
            record(
                f"measure_{model}_shape",
                len(d.get("warm_seconds", [])) == 2 and len(d["calls"]) == 3 and d["cold"]["cold_seconds"] > 0,
                {"status_counts": d.get("status_counts"), "provenance": d.get("provenance", {}).get("profile")},
            )
        # The hosted run measures with CALLOSUM_MODEL_PROVISIONING=1, where an explicit DeBERTa choice also needs a
        # verified checkpoint state; exercise that branch with the state injected the way the app's tests do.
        os.environ.pop("CALLOSUM_DISABLE_MODEL_PROVISIONING")
        os.environ["CALLOSUM_MODEL_PROVISIONING"] = "1"
        args.model = "deberta"
        for state, expect_ok in (("verified", True), ("absent", False)):

            def with_state(engine, state=state):  # type: ignore[no-untyped-def]
                api = fake_app_factory(engine)
                api.state.deberta_model_state = lambda: state
                return api

            probe.fake_app = with_state
            res = run_phase(probe, "measure", args)
            failed = [c["detail"] for c in res["checks"] if not c["ok"]]
            ok = not failed if expect_ok else any("VerifierUnavailableError" in str(f) for f in failed)
            record(f"measure_deberta_provisioning_enabled_{state}", ok, failed or len(res["checks"]))
        probe.fake_app = fake_app_factory
        os.environ.pop("CALLOSUM_MODEL_PROVISIONING")
        os.environ["CALLOSUM_DISABLE_MODEL_PROVISIONING"] = "1"
        res = run_phase(probe, "failclosed", args)
        record(
            "failclosed_phase",
            all(c["ok"] for c in res["checks"]) and len(res["checks"]) == 7,
            [(c["id"], c["ok"]) for c in res["checks"]],
        )
        res = run_phase(probe, "arm_worker", args)
        record("arm_worker_phase", all(c["ok"] for c in res["checks"]), res["checks"])
        engine = make_engine(probe.db_url(args))
        record(
            "armed_row_claimable_by_worker",
            index_runs.claim_for_worker(
                engine,
                ARCTIC_S_PROFILE_KEY,
                token=Path(tmp, "worker-token").read_text(encoding="ascii"),
                pid=os.getpid(),
            ),
        )
        args.condition, args.model, args.worker_pid = "concurrent", "deberta", os.getpid()
        res = run_phase(probe, "measure", args)
        ok, evidence = probe.concurrency_established(res)
        record(
            "concurrent_measure_records_worker",
            all(c["ok"] for c in res["checks"])
            and evidence["alive_every_call"]
            and evidence["chunks_committed_during_warm"] == 0
            and not ok,
            evidence,
        )
        res = run_phase(probe, "stop_worker", args)
        record("stop_worker_phase", all(c["ok"] for c in res["checks"]), res["checks"])
        res = run_phase(probe, "worker_status", args)
        record(
            "worker_status_hides_token",
            "worker_token" not in (res["data"]["row"] or {}) and res["data"]["row"]["intent"] == "pause",
        )
        engine.dispose()


def precision_checks(probe, args: argparse.Namespace) -> None:  # type: ignore[no-untyped-def]
    """v2 §3: the pre-timing precision gate passes a float32 model and refuses a float16 one, whichever layer sees it."""
    res = run_phase(probe, "precision", args)
    failed = [c for c in res["checks"] if not c["ok"]]
    required = {
        "float32_requested_by_app",
        "app_load_in_float32",
        "loaded_parameters_float32",
        "effective_device_cpu",
        "effective_backend_torch",
        "loaded_checkpoint_identity",
        "p1_reference_parity",
        "p1_app_extraction_parity",
        "p1_outputs_not_float16",
        "p1_statuses_unchanged",
    }
    seen = {c["id"] for c in res["checks"]}
    record("precision_phase_float32", not failed and required <= seen, failed or sorted(required - seen))
    DEBERTA_FAKE_DTYPE["dtype"] = "float16"  # a model the app's loader never saw (injected factory): probe-side checks
    try:
        res = run_phase(probe, "precision", args)
        args.model = "deberta"
        measured = run_phase(probe, "measure", args)
    finally:
        DEBERTA_FAKE_DTYPE["dtype"] = "float32"
        args.model = None
    failed = {c["id"] for c in res["checks"] if not c["ok"]}
    record(
        "precision_phase_refuses_float16_parameters",
        failed == {"loaded_parameters_float32", "p1_outputs_not_float16"},
        sorted(failed),
    )
    failed = {c["id"] for c in measured["checks"] if not c["ok"]}
    record(
        "measure_refuses_float16_deberta",
        failed == {"deberta_parameters_float32", "deberta_outputs_not_float16"},
        sorted(failed),
    )
    # Through the app's real loader: a library that ignores dtype=float32 is refused before any score exists.
    import sentence_transformers

    def ignoring(model_name, **kwargs):  # type: ignore[no-untyped-def]
        return fake_cross_encoder(SimpleNamespace(model_name=model_name))

    from app.backend.model_runtime import ModelRuntimeRegistry

    saved, saved_app = getattr(sentence_transformers, "CrossEncoder", None), probe.fake_app
    sentence_transformers.CrossEncoder = ignoring
    probe.fake_app = lambda engine: SimpleNamespace(
        state=SimpleNamespace(engine=engine, model_runtime_registry=ModelRuntimeRegistry())
    )
    DEBERTA_FAKE_DTYPE["dtype"] = "float16"
    try:
        res = run_phase(probe, "precision", args)
    finally:
        DEBERTA_FAKE_DTYPE["dtype"] = "float32"
        sentence_transformers.CrossEncoder, probe.fake_app = saved, saved_app
    failed = [c for c in res["checks"] if not c["ok"]]
    record(
        "precision_phase_app_loader_refuses_ignored_dtype",
        [c["id"] for c in failed] == ["app_load_in_float32"]
        and "ModelPrecisionError" in str(failed[0]["detail"])
        and not any(c["id"] == "p1_reference_parity" for c in res["checks"]),
        [(c["id"], str(c["detail"])[:120]) for c in failed],
    )


def synthetic(
    model: str,
    condition: str,
    warm: list[float],
    ws: float = 2.0e9,
    cm: float = 2.2e9,
    progress: int = 40,
    cpu: float = 0.5,
) -> dict:
    calls = [
        {"start": 0.0, "end": 1.0, "before": {"worker": None, "row": None}, "after": {"worker": None, "row": None}}
    ]
    for i, w in enumerate(warm):
        s = 10.0 * (i + 1)
        worker = condition == "concurrent"
        calls.append(
            {
                "start": s,
                "end": s + w,
                "before": {
                    "worker": {"alive": True, "cpu_s": 100.0} if worker else None,
                    "row": {"indexed_chunks": 100 + (progress if i else 0) * 0} if worker else None,
                },
                "after": {
                    "worker": {"alive": True, "cpu_s": 100.0 + cpu * w} if worker else None,
                    "row": {"indexed_chunks": 100 + progress} if worker else None,
                },
            }
        )
    return {
        "data": {
            "warm_seconds": warm,
            "calls": calls,
            "cold": {"cold_seconds": 20.0, "first_call_seconds": 6.0},
            "memory_samples": {"end": {"peak_working_set_bytes": ws, "peak_commit_bytes": cm}},
        }
    }


def evaluate_checks() -> None:
    import p1b_probe as probe

    def results(solo, conc, **kw):  # type: ignore[no-untyped-def]
        r = {f"deberta_solo_{i + 1}": synthetic("deberta", "solo", solo[i]) for i in range(3)}
        r.update({f"deberta_concurrent_{i + 1}": synthetic("deberta", "concurrent", conc[i], **kw) for i in range(3)})
        r["minilm2_solo_1"] = synthetic("minilm2", "solo", [3.0] * 8)
        return r

    ok8 = [[5.0] * 8] * 3
    checks, summary = probe.evaluate(results(ok8, [[6.0] * 8] * 3), {})
    record("evaluate_pass", all(c["ok"] for c in checks), [(c["id"], c["ok"]) for c in checks])
    slow = [[5.0] * 8, [5.0] * 8, [7.0, 7.0, 7.0, 7.3, 7.3, 7.3, 7.3, 7.3]]  # one process median 7.3 > 7.2
    checks, _ = probe.evaluate(results(slow, [[6.0] * 8] * 3), {})
    failed = {c["id"]: c["kind"] for c in checks if not c["ok"]}
    record("evaluate_largest_process_median_fails", failed == {"deberta_solo_warm_median": "performance"}, failed)
    checks, _ = probe.evaluate(results(ok8, [[6.0] * 8] * 3, progress=0), {})
    failed = {c["id"]: c["kind"] for c in checks if not c["ok"]}
    record(
        "evaluate_missing_overlap_is_inconclusive_not_pass",
        failed == {"deberta_concurrent_overlap_established": "infrastructure"}
        and not any(c["id"] == "deberta_concurrent_warm_median" for c in checks),
        failed,
    )
    checks, _ = probe.evaluate(results(ok8, [[6.0] * 8] * 3, cpu=0.05), {})
    record(
        "evaluate_idle_worker_not_concurrent",
        any(c["id"] == "deberta_concurrent_overlap_established" and not c["ok"] for c in checks),
    )
    checks, _ = probe.evaluate(results(ok8, [[6.0] * 8] * 3, ws=2.53e9), {})
    failed = {c["id"]: c["kind"] for c in checks if not c["ok"]}
    record("evaluate_memory_limit_in_decimal_mb", failed == {"deberta_peak_working_set": "performance"}, failed)
    r = results(ok8, [[6.0] * 8] * 3)
    del r["deberta_solo_3"]
    checks, _ = probe.evaluate(r, {"deberta_solo": ["deberta_solo_3", "deberta_solo_3_repeat"]})
    failed = {c["id"]: c["kind"] for c in checks if not c["ok"]}
    record(
        "evaluate_missing_process_is_inconclusive",
        set(failed.values()) == {"infrastructure"} and "deberta_solo_measurements_complete" in failed,
        failed,
    )


def static_checks() -> None:
    for script in ("p1b_qualify.ps1", "p1b_noise.ps1", "p1b_driver_selftest.ps1"):
        cmd = f"$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{HERE / script}',[ref]$null,[ref]$e); @($e).Count"
        out = subprocess.run(["pwsh", "-NoProfile", "-Command", cmd], capture_output=True, text=True, check=False)  # noqa: S603,S607
        record(f"pwsh_syntax_{script}", out.stdout.strip() == "0", out.stdout.strip() + out.stderr.strip())
    driver = subprocess.run(  # noqa: S603,S607
        ["pwsh", "-NoProfile", "-File", str(HERE / "p1b_driver_selftest.ps1")],
        capture_output=True,
        text=True,
        check=False,
    )
    record(
        "driver_process_bookkeeping", driver.returncode == 0, driver.stdout.strip().splitlines()[-1:] + [driver.stderr]
    )
    wf = (REPO / ".github" / "workflows" / "p1b-qualification.yml").read_text(encoding="utf-8")
    trigger = wf.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    record(
        "workflow_trigger_branch_only", trigger.strip() == 'push:\n    branches: ["qualify/p1b-0.6.0"]', trigger.strip()
    )
    record(
        "workflow_read_only_no_credentials",
        "contents: read" in wf and "persist-credentials: false" in wf and "secrets." not in wf,
    )
    record(
        "workflow_cannot_arm_gate",
        "DEBERTA_RELEASE_GATES"
        not in (HERE / "p1b_probe.py").read_text(encoding="utf-8").split("def phase_failclosed")[0],
    )
    p1 = (REPO / ".github" / "workflows" / "p1-qualification.yml").read_text(encoding="utf-8")
    record("p1_workflow_untouched", 'branches: ["qualify/p1-0.6.0"]' in p1)


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", CALLOSUM_DISABLE_MODEL_PROVISIONING="1")
    os.environ.pop("CALLOSUM_DB_URL", None)  # never the user's library
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as home:
        os.environ["HF_HOME"] = home
        os.environ["CALLOSUM_SETTINGS_PATH"] = str(Path(home, "settings.json"))
        os.environ["CALLOSUM_MODEL_PROVISIONING_DIR"] = home
        fx = fixture_checks()
        pipeline_checks(fx)
        evaluate_checks()
        static_checks()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} self-test checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
