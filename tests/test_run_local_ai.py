"""Inc 569 / backlog #72 — the dev Local AI launcher's decidable logic.

The process lifecycle (spawn, readiness, teardown) is verified by real runs recorded in
INCREMENT-569-NOTES.md and the security audit, not faked here — the same posture the LibreOffice adapter
takes. What IS tested here is everything decidable without a running llama-server, above all the one
property the whole tool depends on: that the descriptor it writes is accepted by the **unmodified**
production validator. If that ever drifts, this fails instead of a developer losing an afternoon.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backend.llm.managed_local import (
    EXPECTED_PREVIEW_MODEL_DIGEST,
    ManagedLocalTargetError,
    load_preview_target,
)
from tools import run_local_ai

MANIFEST = {
    "runtime_launcher_sha256": "5a" * 32,
    "runtime_bundle_manifest_sha256": "77" * 32,
    "model_sha256": EXPECTED_PREVIEW_MODEL_DIGEST,
    "declared_build_backend": "cpu",
}


def _publish(tmp_path: Path, *, template_digest: str | None = "4e" * 32) -> Path:
    credential = run_local_ai._write_credential(tmp_path, "f" * 64)
    run_local_ai._publish(
        tmp_path,
        MANIFEST,
        60683,
        credential,
        "version: 0.1.2-dev (build 10516, commit b95502ba9)",
        template_digest,
    )
    return tmp_path


def test_published_descriptor_is_accepted_by_the_production_loader(tmp_path: Path, monkeypatch) -> None:
    """The load-bearing test. The launcher's whole justification is that it changes NO production code, so
    its output must satisfy `load_preview_target()` exactly as the Tauri shell's own descriptor does."""
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(_publish(tmp_path)))

    target = load_preview_target()

    assert target.endpoint == "http://127.0.0.1:60683"  # literal loopback, re-checked by _strict_endpoint
    assert target.qualification_state == "LOCAL_AI_PREVIEW"
    assert target.requested_execution == target.observed_execution
    assert target.context_tokens == 12_288 and target.max_output_tokens == 2048
    assert target.credential_ref.name == "auth-token"
    assert target.credential_ref.parent == tmp_path / "managed-local-ai"


def test_descriptor_omits_rather_than_invents_a_missing_chat_template(tmp_path: Path, monkeypatch) -> None:
    """`/props` may not report a template. The validator accepts null, so record absence as absence."""
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(_publish(tmp_path, template_digest=None)))

    assert load_preview_target().chat_template_digest is None


def test_a_stale_descriptor_is_removed_before_a_new_run(tmp_path: Path) -> None:
    """A descriptor outliving its server makes the backend report Local AI as available and then fail on
    every request. Startup must never inherit one from a previously hard-killed run."""
    managed = tmp_path / "managed-local-ai"
    managed.mkdir(parents=True)
    (managed / "target.json").write_text("{stale}", encoding="utf-8")

    run_local_ai._write_credential(tmp_path, "a" * 64)

    assert not (managed / "target.json").exists()


def test_swapped_artifacts_are_refused_before_launch(tmp_path: Path) -> None:
    """Re-hashing before exec is what makes re-using files this tool did not fetch defensible."""
    launcher, model = tmp_path / "llama-server", tmp_path / "model.gguf"
    launcher.write_bytes(b"swapped")
    model.write_bytes(b"swapped")

    with pytest.raises(SystemExit, match="runtime launcher digest mismatch"):
        run_local_ai._verify(MANIFEST, launcher, model)


def test_a_non_preview_model_is_refused(tmp_path: Path) -> None:
    """A self-consistent install of some other model would still be rejected by load_preview_target(); fail
    early with an explanation rather than late with a digest error."""
    artifact = tmp_path / "a"
    artifact.write_bytes(b"x")
    # Self-consistent: the receipt's digests match the files, so the per-artifact loop passes and the
    # preview-identity check is what refuses. (An INCONSISTENT receipt fails earlier, which the
    # swapped-artifact test above already covers.)
    digest = run_local_ai._sha256(artifact)
    manifest = dict(MANIFEST, runtime_launcher_sha256=digest, model_sha256=digest)

    with pytest.raises(SystemExit, match="not the pinned preview model"):
        run_local_ai._verify(manifest, artifact, artifact)


@pytest.mark.parametrize(
    "log_text, expected",
    [
        ("load_tensors: offloaded 0/25 layers to GPU", None),
        ("load_tensors: offloaded 25/25 layers to GPU", "offloaded 25 layers"),
        # A GPU being PRESENT is not a GPU being USED. Under `-ngl 0` this is genuine CPU execution, and
        # refusing here would block every developer whose machine merely has an NVIDIA card.
        ("ggml_cuda_init: found 1 CUDA devices\noffloaded 0/25 layers to GPU", None),
        ("llama_model_loader: loaded meta data", "Could not observe layer offload"),
    ],
)
def test_execution_claim_is_observed_never_assumed(tmp_path: Path, log_text: str, expected: str | None) -> None:
    """`requested_execution == observed_execution` is enforced by the validator, so the launcher must not
    assert CPU execution it never saw. Note the last case: an absent offload line FAILS rather than
    defaulting to cpu — silence is not proof (PRINCIPLES #6)."""
    log = tmp_path / "llama-server.log"
    log.write_text(log_text, encoding="utf-8")

    if expected is None:
        run_local_ai._verify_observed_execution(log)  # must not raise
    else:
        with pytest.raises(SystemExit, match=expected):
            run_local_ai._verify_observed_execution(log)


def test_missing_installation_explains_itself_rather_than_crashing(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no downloader"):
        run_local_ai._find_artifacts(tmp_path)


def test_descriptor_directory_shape_is_what_the_validator_requires(tmp_path: Path, monkeypatch) -> None:
    """Both loaders require the path to end in `managed-local-ai/target.json`; prove the writer agrees."""
    _publish(tmp_path)
    descriptor = tmp_path / "managed-local-ai" / "target.json"

    assert json.loads(descriptor.read_text(encoding="utf-8"))["schema_version"] == 2
    monkeypatch.setenv("CALLOSUM_APP_DATA_DIR", str(tmp_path / "wrong-place"))
    with pytest.raises(ManagedLocalTargetError):
        load_preview_target()
