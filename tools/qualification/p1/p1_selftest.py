"""Local, model-free self-test of the P1 qualification harness (run before publishing the qualification branch).

    python -B tools/qualification/p1/p1_selftest.py [--manifest runtime-manifest.json --signature runtime-manifest.json.sig]

Checks, none of which downloads, loads a model or needs the hosted runner:
* the frozen fixture: shapes, pinned revisions, unchanged thresholds, and expected statuses re-derived with the app's
  own status rule from the frozen reference probabilities;
* the extraction and tree-digest scripts against the packaging code on a synthetic runtime archive, plus three
  malformed archives that must be refused;
* the Minisign verifier on the real manifest (when given) and on a tampered copy;
* PowerShell syntax of every script and the workflow's trigger, permission and credential settings.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")


def pwsh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["pwsh", "-NoProfile", *args], capture_output=True, text=True, check=False)  # noqa: S603,S607


def fixture_checks() -> None:
    from app.backend.model_runtime import PINNED_MODEL_REVISIONS
    from app.backend.summarization.verification import LocalCitationVerifier, VerificationConfig

    fx = json.loads((HERE / "fixtures" / "p1-probe-v1.json").read_text(encoding="utf-8"))
    arctic, nli = fx["arctic"], fx["deberta"]
    record(
        "fixture_arctic_shape", len(arctic["texts"]) == 3 and all(len(v) == 384 for v in arctic["reference_embeddings"])
    )
    record(
        "fixture_deberta_shape",
        len(nli["pairs_premise_hypothesis"]) == 2 and all(len(r) == 3 for r in nli["reference_probabilities"]),
    )
    record(
        "fixture_revisions_pinned",
        PINNED_MODEL_REVISIONS[arctic["model"]] == arctic["revision"]
        and PINNED_MODEL_REVISIONS[nli["model"]] == nli["revision"],
    )
    record("fixture_criteria", arctic["min_cosine"] == 0.99999 and nli["max_abs_probability_difference"] == 0.001)
    cfg = VerificationConfig()
    current = {k: getattr(cfg, k) for k in fx["verification_thresholds"]}
    record("fixture_thresholds_match_app", current == fx["verification_thresholds"], str(current))
    derived = [
        LocalCitationVerifier._status(  # noqa: SLF001
            SimpleNamespace(config=cfg),
            retrieval_confidence=e["retrieval_confidence"],
            quote_confidence=e["quote_confidence"],
            support_confidence=nli["reference_probabilities"][e["pair"]][0],
            contradiction_confidence=nli["reference_probabilities"][e["pair"]][2],
        )
        == e["status"]
        for e in fx["expected_statuses"]
    ]
    record("fixture_statuses_rederived", len(derived) == 4 and all(derived))


def _archive(path: Path, files: dict[str, bytes], extra: list[tarfile.TarInfo] | None = None) -> None:
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        root = tarfile.TarInfo("python-runtime")
        root.type = tarfile.DIRTYPE
        tar.addfile(root)
        for name, data in files.items():
            info = tarfile.TarInfo(f"python-runtime/{name}")
            info.size = len(data)
            info.mode = 0o755 if name.endswith(".exe") else 0o644
            tar.addfile(info, io.BytesIO(data))
        for info in extra or []:
            tar.addfile(info, io.BytesIO(b"x" * info.size) if info.isfile() else None)


def extraction_checks(tmp: Path) -> None:
    sys.path.insert(0, str(REPO / "app" / "desktop-shell" / "packaging"))
    import package_python_runtime as pkg  # the packaging code is the reference implementation

    tree = tmp / "src"
    files = {
        "python.exe": b"MZ fake",
        "Lib/os.py": b"# os\n",
        "Lib/site-packages/a/b.py": b"print(1)\n",
        "DLLs/x.pyd": b"\0" * 4096,
        "Lib/été.txt": b"unicode",
    }
    for name, data in files.items():
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).write_bytes(data)
    entries = pkg._tree_entries(tree)  # noqa: SLF001
    archive = tmp / "rt.tar.gz"
    pkg._write_archive(archive, tree, entries)  # noqa: SLF001
    manifest = tmp / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "entry_count": len(entries),
                "unpacked_bytes": sum(e.size for e in entries),
                "tree_sha256": pkg._tree_digest(entries),
            }
        ),  # noqa: SLF001
        encoding="utf-8",
    )
    expected = pkg._tree_digest(entries)  # noqa: SLF001
    run = pwsh(
        "-File",
        str(HERE / "p1_extract_runtime.ps1"),
        "-Archive",
        str(archive),
        "-Dest",
        str(tmp / "out"),
        "-ManifestPath",
        str(manifest),
        "-ListOut",
        str(tmp / "list.txt"),
    )
    record(
        "extract_matches_packaging_digest",
        run.returncode == 0 and "EXTRACT-STREAM TREE MATCH" in run.stdout and expected in run.stdout,
        expected,
    )
    digest = pwsh("-File", str(HERE / "p1_tree_digest.ps1"), "-Root", str(tmp / "out"))
    record("tree_digest_matches_packaging_digest", f"digest {expected}" in digest.stdout, digest.stdout.strip())

    traversal = tarfile.TarInfo("python-runtime/../evil.txt")
    traversal.size = 1
    link = tarfile.TarInfo("python-runtime/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "python.exe"
    wrong_root = tarfile.TarInfo("other-root/file.txt")
    wrong_root.size = 1
    for label, extra in (("traversal", traversal), ("symlink", link), ("wrong_root", wrong_root)):
        bad = tmp / f"bad-{label}.tar.gz"
        _archive(bad, {"python.exe": b"MZ"}, [extra])
        big = tmp / f"m-{label}.json"
        big.write_text(
            json.dumps({"entry_count": 10, "unpacked_bytes": 10**6, "tree_sha256": "0" * 64}), encoding="utf-8"
        )
        res = pwsh(
            "-File",
            str(HERE / "p1_extract_runtime.ps1"),
            "-Archive",
            str(bad),
            "-Dest",
            str(tmp / f"o-{label}"),
            "-ManifestPath",
            str(big),
            "-ListOut",
            str(tmp / f"l-{label}.txt"),
        )
        record(f"extract_refuses_{label}", res.returncode != 0 and "INVALID ARCHIVE" in (res.stdout + res.stderr))


def signature_checks(manifest: Path | None, signature: Path | None, tmp: Path) -> None:
    if manifest is None or signature is None:
        record("signature_real_manifest", True, "skipped: no manifest given")
        return
    import p1_minisign

    rust = (REPO / "app" / "desktop-shell" / "src-tauri" / "src" / "python_runtime.rs").read_text(encoding="utf-8")
    try:
        p1_minisign.verify(manifest.read_bytes(), signature.read_bytes(), rust)
        record("signature_real_manifest", True)
    except Exception as exc:  # noqa: BLE001
        record("signature_real_manifest", False, repr(exc))
    tampered = manifest.read_bytes().replace(b'"schema_version": 1', b'"schema_version": 2')
    try:
        p1_minisign.verify(tampered, signature.read_bytes(), rust)
        record("signature_rejects_tampered", False)
    except Exception:  # noqa: BLE001
        record("signature_rejects_tampered", True)


def static_checks() -> None:
    for script in sorted(HERE.glob("*.ps1")):
        res = pwsh(
            "-Command",
            f"$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{script}',[ref]$null,[ref]$e); "
            "if ($e) { $e | % { $_.ToString() }; exit 1 }",
        )
        record(f"powershell_parses_{script.name}", res.returncode == 0, res.stdout.strip())
    import yaml

    workflow = REPO / ".github" / "workflows" / "p1-qualification.yml"
    text = workflow.read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    triggers = doc.get(True) or doc.get("on")  # PyYAML reads the bare key `on` as boolean True
    record("workflow_push_branch_only", triggers == {"push": {"branches": ["qualify/p1-0.6.0"]}}, str(triggers))
    record("workflow_read_only_permissions", doc.get("permissions") == {"contents": "read"})
    job = doc["jobs"]["p1"]
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    record("workflow_no_persisted_credentials", checkout["with"]["persist-credentials"] is False)
    record("workflow_pinned_runner", job["runs-on"] == "windows-2025")
    record("workflow_uses_no_secrets", "secrets." not in text and "GITHUB_TOKEN" not in text)
    others = []
    for path in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        if path == workflow:
            continue
        other = yaml.safe_load(path.read_text(encoding="utf-8"))
        on = other.get(True) or other.get("on") or {}
        push = on.get("push") if isinstance(on, dict) else None
        if isinstance(push, dict) and push.get("branches") not in (None, ["main"]):
            others.append(path.name)
        if isinstance(push, dict) and "branches" not in push and "tags" not in push:
            others.append(path.name)
    record("no_other_workflow_runs_on_branch_push", not others, str(others))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--signature", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(HERE))
    fixture_checks()
    with tempfile.TemporaryDirectory() as tmp:
        extraction_checks(Path(tmp))
        signature_checks(args.manifest, args.signature, Path(tmp))
    static_checks()
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed" + (f"; FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
