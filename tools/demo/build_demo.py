"""Build the shared Callosum frontend as a self-contained static online demo artifact."""

# ruff: noqa: E402 -- direct script execution needs the repository root on sys.path before app imports.

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.api.frontend import build_frontend_document
from app.backend.api.startup import PROJECT_ROOT
from app.backend.demo_coverage import DemoCoverageCatalogue
from app.backend.demo_snapshot import SNAPSHOT_SCHEMA_VERSION, DemoSnapshot, assert_public_snapshot_bytes
from tools.qa.check_demo_experience_coverage import DEFAULT_LEDGER as DEFAULT_EXPERIENCE_LEDGER
from tools.qa.check_demo_experience_coverage import validate as validate_experience_coverage

REACT_CDN = (
    '<script crossorigin="anonymous" integrity="sha384-tMH8h3BGESGckSAVGZ82T9n90ztNXxvdwvdM6UoR56cYcf+0iGXBliJ29D+wZ/x8" '
    'src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>'
)
REACT_DOM_CDN = (
    '<script crossorigin="anonymous" integrity="sha384-bm7MnzvK++ykSwVJ2tynSE5TRdN+xL418osEVF2DE/L/gfWHj91J2Sphe582B1Bh" '
    'src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>'
)
CSP = (
    "default-src 'self'; base-uri 'self'; connect-src 'self'; font-src 'self' data:; "
    "img-src 'self' data: blob:; object-src 'none'; "
    "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; worker-src 'self' blob:"
)


def _base_path(value: str) -> str:
    path = "/" + value.strip("/") + "/" if value.strip("/") else "/"
    if "?" in path or "#" in path or "\\" in path:
        raise ValueError("base path must be a plain URL path")
    if any(part in {".", ".."} for part in unquote(path).split("/")):
        raise ValueError("base path cannot contain traversal segments")
    return path


def _copy(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"missing pinned demo dependency: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clear_output(output_dir: Path) -> None:
    """Clear generated files while tolerating Windows/Dropbox handles on already-empty directories."""

    if not output_dir.exists():
        return
    for path in sorted((item for item in output_dir.rglob("*") if item.is_file()), reverse=True):
        path.unlink()
    for path in sorted((item for item in output_dir.rglob("*") if item.is_dir()), reverse=True):
        try:
            path.rmdir()
        except PermissionError:
            if any(path.iterdir()):
                raise


def _about_page(snapshot: DemoSnapshot, base_path: str) -> str:
    rows = []
    for paper in snapshot.api.papers:
        license_record = paper.document.license
        rows.append(
            "<article><h2>" + html.escape(license_record.work_title) + "</h2>"
            "<p>" + html.escape(license_record.attribution) + "</p>"
            '<p><a href="' + html.escape(license_record.canonical_url, quote=True) + '">Canonical source</a> · '
            '<a href="'
            + html.escape(license_record.license_url, quote=True)
            + '">'
            + html.escape(license_record.license_name)
            + "</a></p>"
            "<p><b>Bundled:</b> "
            + html.escape(license_record.bundled_material)
            + ". "
            + html.escape(license_record.redistribution_basis)
            + "</p>"
            "<p><b>Verified:</b> "
            + html.escape(license_record.verified_via)
            + " on "
            + html.escape(license_record.verified_on)
            + ".</p>"
            + ("<p>" + html.escape(license_record.notice or "") + "</p>" if license_record.notice else "")
            + "</article>"
        )
    registration_rows = []
    for audit in snapshot.api.synthesis.registration_license_audits:
        registration_rows.append(
            "<article><h2>Registration "
            + html.escape(audit.external_id)
            + " ("
            + html.escape(audit.provider)
            + ")</h2><p><b>License:</b> "
            + html.escape(audit.license_name)
            + ". <b>Bundled:</b> metadata and bounded evidence only.</p><p>"
            + html.escape(audit.notice)
            + '</p><p><a href="'
            + html.escape(audit.canonical_url, quote=True)
            + '">Inspect the complete canonical record</a></p><p><b>Verified:</b> '
            + html.escape(audit.verified_via)
            + " on "
            + html.escape(audit.verified_on)
            + ".</p></article>"
        )
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="%s"><base href="%s"><title>Callosum demo corpus and limits</title>
<style>body{max-width:760px;margin:40px auto;padding:0 20px;font:16px/1.55 system-ui;color:#1c1b19;background:#fbfaf7}h1,h2{line-height:1.2}h2{font-size:1.15rem;margin-top:2rem}article{border-top:1px solid #e6e2d8}code{background:#f4f2ec;padding:2px 4px}a{color:#2f2a6b}</style></head>
<body><p><a href="index.html">← Return to the demo</a></p><h1>Corpus, licenses, and limits</h1>
<p>This is an immutable, static snapshot. It contains no backend, database, credentials, analytics, AI service, or sync connection. Saved synthesis prose is AI-proposed; the evidence and local verification states are the inspectable artifact.</p>
<p>Functional: library browsing/search, PDF reading, saved methods and reporting-checklist inspection, completed Status-receipt navigation, saved synthesis/Critique/registration-crosswalk inspection, evidence navigation, a reviewed saved Feed, saved literature search, journal and funding results, followed-author works, Cite, Meta-Reference, CRediT, Statements, Meta-Analyze, and bundled Help. Every real workspace and subtab is visible and labeled by capability. Prerecorded results use the same production response models and renderers as live Callosum. Disabled: every persistent mutation, rerun/regeneration, import, provider setting, external refresh, acquisition, sync, AI call, and desktop integration.</p>
<h1>Curated works</h1>%s<h1>Registration license audit</h1>%s</body></html>""" % (
        html.escape(CSP, quote=True),
        html.escape(base_path, quote=True),
        "".join(rows),
        "".join(registration_rows),
    )


def build_demo(
    snapshot_path: Path,
    output_dir: Path,
    base_path: str,
    coverage_path: Path = PROJECT_ROOT / "demo" / "coverage-v1.json",
) -> None:
    base_path = _base_path(base_path)
    payload = snapshot_path.read_bytes()
    assert_public_snapshot_bytes(payload)
    snapshot = DemoSnapshot.model_validate_json(payload)
    coverage = DemoCoverageCatalogue.model_validate_json(coverage_path.read_bytes())
    validate_experience_coverage(DEFAULT_EXPERIENCE_LEDGER)
    if coverage.snapshot_schema_version != snapshot.manifest.snapshot_schema_version:
        raise ValueError("demo coverage catalogue targets a different snapshot schema; update it deliberately")
    coverage_by_id = {item.id: item for item in coverage.items}
    for surface, capability in snapshot.manifest.workspace_capabilities.items():
        item = coverage_by_id.get(surface)
        if item is None:
            raise ValueError(f"demo coverage catalogue is missing workspace capability {surface!r}")
        if item.status != capability.mode:
            raise ValueError(f"coverage/capability status drift for {surface!r}: {item.status} != {capability.mode}")
    resolved_output = output_dir.resolve()
    resolved_root = PROJECT_ROOT.resolve()
    if resolved_output == resolved_root:
        raise ValueError("demo output must be a dedicated directory, not the Callosum workspace")
    if output_dir.exists() and resolved_root not in resolved_output.parents:
        raise ValueError("refusing to clear an existing demo output outside the Callosum workspace")
    _clear_output(output_dir)
    (output_dir / "assets").mkdir(parents=True)
    (output_dir / "documents").mkdir(parents=True)

    document = build_frontend_document()
    document = document.replace(REACT_CDN, '<script src="assets/react.production.min.js"></script>')
    document = document.replace(REACT_DOM_CDN, '<script src="assets/react-dom.production.min.js"></script>')
    document = document.replace(
        "`https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.min.js`",
        'new URL("assets/pdf.min.js", document.baseURI).toString()',
    )
    document = document.replace(
        "`https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/pdf.worker.min.js`",
        'new URL("assets/pdf.worker.min.mjs", document.baseURI).toString()',
    )
    # Live provider code remains shared, but the static artifact carries no usable loopback endpoint literals.
    document = document.replace("localhost:", "loopback-disabled:").replace("127.0.0.1:", "loopback-disabled:")
    if "cdnjs.cloudflare.com/ajax/libs/react" in document:
        raise ValueError("demo build failed to replace the React CDN dependencies")
    document = document.replace(
        "<head>",
        f'<head>\n<meta http-equiv="Content-Security-Policy" content="{CSP}">\n<base href="{html.escape(base_path, quote=True)}">',
        1,
    )
    document = document.replace(
        '<div id="root"></div>',
        '<div id="root"></div>\n<script src="demo-config.js"></script>\n<script src="demo-runtime.js"></script>',
        1,
    )
    (output_dir / "index.html").write_text(document, encoding="utf-8")
    (output_dir / "404.html").write_text(document, encoding="utf-8")
    route_dir = output_dir / "synthesis"
    route_dir.mkdir(exist_ok=True)
    (route_dir / "index.html").write_text(document, encoding="utf-8")
    (output_dir / "snapshot-v1.json").write_bytes(payload)
    _copy(coverage_path, output_dir / "coverage-v1.json")
    _copy(DEFAULT_EXPERIENCE_LEDGER, output_dir / "experience-coverage-v1.json")
    config = {
        "snapshot_schema_version": snapshot.manifest.snapshot_schema_version,
        "initial_workspace": snapshot.manifest.initial_workspace,
        "initial_paper_id": snapshot.manifest.initial_paper_id,
        "initial_summary_id": snapshot.manifest.initial_summary_id,
        "capabilities": snapshot.manifest.capabilities.model_dump(mode="json"),
        "workspace_capabilities": {
            key: value.model_dump(mode="json") for key, value in snapshot.manifest.workspace_capabilities.items()
        },
    }
    (output_dir / "demo-config.js").write_text(
        "window.CALLOSUM_DEMO = Object.freeze(" + json.dumps(config, sort_keys=True) + ");\n",
        encoding="utf-8",
    )
    (output_dir / "demo-about.html").write_text(_about_page(snapshot, base_path), encoding="utf-8")
    (output_dir / "_headers").write_text(
        "/*\n"
        f"  Content-Security-Policy: {CSP}; frame-ancestors 'none'\n"
        "  Referrer-Policy: no-referrer\n"
        "  X-Content-Type-Options: nosniff\n"
        "  X-Frame-Options: DENY\n",
        encoding="utf-8",
    )

    _copy(PROJECT_ROOT / "demo" / "demo-runtime.js", output_dir / "demo-runtime.js")
    _copy(
        PROJECT_ROOT / "node_modules" / "react" / "umd" / "react.production.min.js",
        output_dir / "assets" / "react.production.min.js",
    )
    _copy(
        PROJECT_ROOT / "node_modules" / "react-dom" / "umd" / "react-dom.production.min.js",
        output_dir / "assets" / "react-dom.production.min.js",
    )
    _copy(PROJECT_ROOT / "node_modules" / "pdfjs-dist" / "build" / "pdf.min.mjs", output_dir / "assets" / "pdf.min.mjs")
    pdf_worker = output_dir / "assets" / "pdf.worker.min.mjs"
    _copy(
        PROJECT_ROOT / "node_modules" / "pdfjs-dist" / "build" / "pdf.worker.min.mjs",
        pdf_worker,
    )
    # PDF.js's browser shim carries a synthetic Node HOME. It is not host data, but a public artifact should not
    # contain any home-directory-shaped path, so normalize that inert fallback before the final scan.
    worker_text = pdf_worker.read_text(encoding="utf-8")
    if "/home/web_user" not in worker_text:
        raise ValueError("pinned PDF.js worker no longer has the expected synthetic HOME marker")
    pdf_worker.write_text(worker_text.replace("/home/web_user", "/"), encoding="utf-8")
    for paper in snapshot.api.papers:
        if paper.document.asset_path:
            name = Path(paper.document.asset_path).name
            source = PROJECT_ROOT / "demo" / "documents" / name
            if source.read_bytes()[:5] != b"%PDF-":
                raise ValueError(f"demo document is not a PDF: {name}")
            if _sha256(source) != paper.document.sha256:
                raise ValueError(f"demo document does not match the snapshot hash: {name}")
            _copy(source, output_dir / "documents" / name)

    forbidden = (
        "cdnjs.cloudflare.com",
        "unpkg.com",
        "localhost:",
        "127.0.0.1:",
        "C:\\Users\\",
        "/Users/",
        "/home/",
        "-----BEGIN PRIVATE KEY-----",
        "ghp_",
        "xoxb-",
    )
    for file in output_dir.rglob("*"):
        if not file.is_file() or file.suffix.lower() not in {".html", ".js", ".mjs", ".json", ".css"}:
            continue
        text = file.read_text(encoding="utf-8", errors="strict")
        hit = next((marker for marker in forbidden if marker in text), None)
        if hit:
            raise ValueError(f"demo artifact contains forbidden live/external marker {hit!r} in {file}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=PROJECT_ROOT / "demo" / "snapshot-v1.json")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "dist-demo")
    parser.add_argument("--base-path", default="/callosum-demo/")
    parser.add_argument("--coverage", type=Path, default=PROJECT_ROOT / "demo" / "coverage-v1.json")
    args = parser.parse_args()
    base_path = _base_path(args.base_path)
    build_demo(args.snapshot, args.output, base_path, args.coverage)
    print(
        json.dumps(
            {"artifact": str(args.output), "base_path": base_path, "snapshot_schema": SNAPSHOT_SCHEMA_VERSION},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
