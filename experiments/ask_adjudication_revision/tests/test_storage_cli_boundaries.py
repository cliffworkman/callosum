import io
import json
import socket
import subprocess

import pytest

from experiments.ask_adjudication_revision.__main__ import main
from experiments.ask_adjudication_revision.capability import suite
from experiments.ask_adjudication_revision.core import canonical, sha
from experiments.ask_adjudication_revision.demo import run_demo
from experiments.ask_adjudication_revision.storage import Store


class Pipe:
    def __init__(self, raw, *, tty=False):
        self.buffer = io.BytesIO(raw)
        self.tty = tty

    def isatty(self):
        return self.tty


def test_capture_is_exclusive_private_and_receipt_is_allowlisted():
    store = Store.create()
    packet = suite()[0]
    secret = b"SYNTHETIC_PRIVATE_REPLY do not echo"
    receipt = store.capture(packet, secret, surface_id="claude")
    assert set(receipt) == {"capture_success", "bytes", "sha256"}
    assert secret not in canonical(receipt)
    assert store.read(f"claude_{packet.packet_id}_attempt1.bin") == secret
    with pytest.raises(FileExistsError):
        store.capture(packet, b"replacement", surface_id="claude")
    assert store.verify()["artifact_count"] == 1
    # Same packet sent to another surface has its own identity.
    store.capture(packet, packet.expected, surface_id="gemini")
    assert store.verify()["artifact_count"] == 2


def test_retry_requires_preserved_failure_and_logged_amendment():
    store = Store.create()
    packet = suite()[0]
    with pytest.raises(ValueError, match="FIRST_ATTEMPT"):
        store.capture(packet, packet.expected, surface_id="claude", attempt=2)
    store.capture(packet, b"incomplete", surface_id="claude")
    with pytest.raises(ValueError, match="AMENDMENT"):
        store.capture(packet, packet.expected, surface_id="claude", attempt=2)
    amendment = store.write(
        "amendment_test.json", canonical({"why": "synthetic mechanical correction"}), kind="MECHANICAL_AMENDMENT"
    )
    store.capture(packet, packet.expected, surface_id="claude", attempt=2, amendment_id=amendment["sha256"])
    assert store.read(f"claude_{packet.packet_id}_attempt1.bin") == b"incomplete"
    with pytest.raises(ValueError, match="RETRY_LIMIT"):
        store.capture(packet, packet.expected, surface_id="claude", attempt=3)
    assert store.verify()["artifact_count"] == 3


def test_cannot_retry_successful_capability_response():
    store = Store.create()
    packet = suite()[0]
    store.capture(packet, packet.expected, surface_id="claude")
    amendment = store.write("amendment_test.json", b"{}", kind="MECHANICAL_AMENDMENT")
    with pytest.raises(ValueError, match="UNNECESSARY"):
        store.capture(packet, packet.expected, surface_id="claude", attempt=2, amendment_id=amendment["sha256"])


def test_tamper_or_orphan_fails_verification():
    store = Store.create()
    store.write("fixture.bin", b"original")
    store.path("fixture.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="ARTIFACT_INTEGRITY"):
        store.verify()
    other = Store.create()
    other.path("orphan.bin").write_bytes(b"crash before journal")
    with pytest.raises(ValueError, match="UNJOURNALED"):
        other.verify()
    with pytest.raises(ValueError, match="UNJOURNALED"):
        other.write("later.bin", b"must not continue after indeterminate write")


def test_journal_tamper_and_lock_fail_closed():
    store = Store.create()
    store.write("fixture.bin", b"original")
    path = store.root / "journal" / "000000.json"
    event = json.loads(path.read_bytes())
    event["previous"] = "tampered"
    path.write_bytes(canonical(event))
    with pytest.raises(ValueError, match="JOURNAL_INTEGRITY"):
        store.verify()
    other = Store.create()
    (other.root / "write.lock").mkdir()
    with pytest.raises(ValueError, match="BUSY_OR_INDETERMINATE"):
        other.write("fixture.bin", b"must not write")


@pytest.mark.parametrize(
    "name", ["../outside.bin", "owner.json", "C:/outside.bin", "nested/file.json", "file.json:stream"]
)
def test_no_arbitrary_file_paths(name):
    store = Store.create()
    with pytest.raises(ValueError):
        store.read(name)


def test_cli_prepares_only_synthetic_material_and_does_not_qualify_surfaces():
    out = io.StringIO()
    assert main(["prepare-capability"], stdout=out) == 0
    result = json.loads(out.getvalue())
    assert result["inference_calls"] == 0
    store = Store(result["run"])
    manifest = json.loads(store.read("capability_manifest.json"))
    assert manifest["all_surfaces"] == "UNTESTED"
    assert manifest["live_submission_implemented"] is False
    assert len(manifest["packets"]) == 3
    assert json.loads(store.read("claude_capability_template.json"))["origin"] == "UNOBSERVED"


def test_cli_capture_and_error_never_echo_semantic_or_exception_content():
    prepared = io.StringIO()
    main(["prepare-capability"], stdout=prepared)
    run = json.loads(prepared.getvalue())["run"]
    packet = suite()[0]
    secret = b"SYNTHETIC_SECRET_FROM_SURFACE"
    out = io.StringIO()
    args = ["capture-capability", "--run", run, "--surface", "claude", "--packet-id", packet.packet_id]
    assert main(args, stdin=Pipe(secret), stdout=out) == 0
    assert secret.decode() not in out.getvalue()
    assert json.loads(out.getvalue()) == {"capture_success": True, "bytes": len(secret), "sha256": sha(secret)}
    error = io.StringIO()
    assert main(args, stdin=Pipe(secret), stdout=error) == 2
    assert error.getvalue() == '{"success": false, "error": "OPERATION_BLOCKED_OR_INVALID"}\n'
    tty = io.StringIO()
    assert main(args, stdin=Pipe(secret, tty=True), stdout=tty) == 2
    assert secret.decode() not in tty.getvalue()


def test_offline_guard_blocks_network_subprocess_model_and_prohibited_archive_reads(tmp_path):
    with pytest.raises(ValueError, match="OFFLINE_EXECUTION"):
        socket.getaddrinfo("example.invalid", 443)
    with socket.socket() as sock:
        with pytest.raises(ValueError, match="OFFLINE_EXECUTION"):
            sock.connect(("127.0.0.1", 1))
    with pytest.raises(ValueError, match="OFFLINE_EXECUTION"):
        subprocess.Popen(["must-not-launch"])
    with pytest.raises(ValueError, match="MODEL_PRODUCTION"):
        __import__("torch")
    # Only invented paths are attempted; guard rejects before OS open.
    with pytest.raises(ValueError, match="ARCHIVE_ACCESS"):
        (tmp_path / "SEALED_ARM_KEY.json").read_bytes()
    with pytest.raises(ValueError, match="ARCHIVE_ACCESS"):
        (tmp_path / "arm1_outputs.jsonl").read_bytes()
    with pytest.raises(ValueError, match="PRODUCTION_WRITE"):
        (tmp_path / "app" / "fake.py").write_text("must not write")


def test_full_synthetic_rehearsal_keeps_private_design_out_of_human_export():
    store = run_demo()
    assert store.verify()["artifact_count"] > 0
    human = store.read("human_fixture_a.json")
    for forbidden in (b"selection_rationale", b"frontier", b"NO_FLAG", b"UNCERTAIN concern", b"unflagged"):
        assert forbidden not in human
    completion = json.loads(store.read("simulation_completion.json"))
    assert completion["real_human_labels"] == completion["inference_calls"] == 0


def test_cli_invalid_arguments_do_not_echo_input(capsys):
    out = io.StringIO()
    with pytest.raises(SystemExit):
        main(["SYNTHETIC_PRIVATE_UNRECOGNIZED_COMMAND"], stdout=out)
    assert out.getvalue() == '{"success": false, "error": "INVALID_COMMAND"}\n'
    assert "SYNTHETIC_PRIVATE" not in capsys.readouterr().err


def test_implementation_identity_is_package_local():
    from experiments.ask_adjudication_revision.manifest import implementation_manifest

    manifest = implementation_manifest()
    assert manifest["real_study_enabled"] is False
    assert manifest["files"]
    assert all(
        ".." not in name and not name.startswith("/") and len(value) == 64 for name, value in manifest["files"].items()
    )
