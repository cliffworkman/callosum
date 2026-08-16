#!/usr/bin/env python3
"""Keep the public website catalogue synchronized with user-facing product surfaces.

Normal use is read-only and CI-safe::

    python tools/qa/check_website_coverage.py

After reviewing every affected website claim and visual, acknowledge an intentional UI change::

    python tools/qa/check_website_coverage.py --refresh --note "Reviewed the new Foo workflow."

The refresh command records a combined source fingerprint plus exact image checksums and dimensions.
It is an explicit review receipt, not an automatic claim that a screenshot is still accurate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "www" / "showcase-coverage.json"
SHOWCASE = ROOT / "www" / "showcase.html"
INDEX = ROOT / "www" / "index.html"
README = ROOT / "README.md"
QA_ROUTES = ROOT / ".claude" / "qa-routes"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.hrefs: list[str] = []
        self.images: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        element_id = values.get("id")
        if element_id:
            if element_id in self.ids:
                self.duplicate_ids.add(element_id)
            self.ids.add(element_id)
        if "href" in values:
            self.hrefs.append(values["href"])
        if tag == "img":
            self.images.append(values)


def _parse(path: Path) -> SiteParser:
    parser = SiteParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def _source_files() -> list[Path]:
    patterns = (
        "app/frontend/index.html",
        "app/frontend/styles.css",
        "app/frontend/js/*.jsx",
        "app/backend/help/help_content.md",
        "adapters/libreoffice/**/*.py",
        "adapters/word/**/*",
        "adapters/google_docs/**/*",
        "tui/**/*.py",
        "mcp_server/**/*.py",
    )
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in ROOT.glob(pattern) if path.is_file() and "__pycache__" not in path.parts)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def _source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in _source_files():
        relative = path.relative_to(ROOT).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path.relative_to(ROOT)}")
    return struct.unpack(">II", header[16:24])


def _git_rev() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or "unknown"


def refresh(note: str) -> int:
    if not note.strip():
        raise SystemExit("--refresh requires a non-empty --note describing the visual/copy review")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    data["review"] = {
        "reviewed_at": date.today().isoformat(),
        "reviewed_rev": _git_rev(),
        "source_fingerprint": _source_fingerprint(),
        "note": note.strip(),
    }
    for relative, metadata in data["figures"].items():
        path = ROOT / "www" / relative
        width, height = _png_dimensions(path)
        metadata.update(
            {
                "captured_at": metadata.get("captured_at") or date.today().isoformat(),
                "reviewed_at": date.today().isoformat(),
                "width": width,
                "height": height,
                "sha256": _sha256(path),
            }
        )
    REGISTRY.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"[website] refreshed review receipt at {_git_rev()} ({len(data['figures'])} figures)")
    return 0


def check() -> int:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    showcase = _parse(SHOWCASE)
    index = _parse(INDEX)
    errors: list[str] = []

    expected_routes = {path.stem for path in QA_ROUTES.glob("route_*.md") if path.name != "_TEMPLATE.md"}
    mapped_routes = set(data["qa_routes"])
    excluded_routes = data.get("excluded_qa_routes", {})
    for route, reason in excluded_routes.items():
        if not reason.strip():
            errors.append(f"excluded QA route has no reason: {route}")
        if route not in expected_routes:
            errors.append(f"excluded QA route no longer exists, remove the stale exclusion: {route}")
        if route in mapped_routes:
            errors.append(f"QA route is both mapped and excluded: {route}")
    for route in sorted(expected_routes - mapped_routes - set(excluded_routes)):
        errors.append(f"unmapped public QA route: {route}")
    for route in sorted(mapped_routes - expected_routes):
        errors.append(f"registry names missing QA route: {route}")

    for label, target in {**data["qa_routes"], **data["external_surfaces"]}.items():
        if not target.startswith("#") or target[1:] not in showcase.ids:
            errors.append(f"{label} points to missing showcase anchor {target}")

    if showcase.duplicate_ids:
        errors.append(f"duplicate showcase ids: {', '.join(sorted(showcase.duplicate_ids))}")

    figure_sources = {image["src"] for image in showcase.images if image.get("src", "").startswith("shots/")}
    registered_figures = set(data["figures"])
    for source in sorted(figure_sources - registered_figures):
        errors.append(f"unregistered showcase image: {source}")
    for source in sorted(registered_figures - figure_sources):
        errors.append(f"registered image is not used by showcase: {source}")

    review_date = data["review"].get("reviewed_at", "")
    for relative, metadata in data["figures"].items():
        path = ROOT / "www" / relative
        if not path.is_file():
            errors.append(f"missing image: {relative}")
            continue
        try:
            width, height = _png_dimensions(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if (width, height) != (metadata.get("width"), metadata.get("height")):
            errors.append(f"dimension drift: {relative} is {width}x{height}")
        if _sha256(path) != metadata.get("sha256"):
            errors.append(f"image checksum drift: {relative}")
        if max(metadata.get("captured_at", ""), metadata.get("reviewed_at", "")) < review_date:
            errors.append(f"stale visual receipt: {relative} predates the website review")

    image_by_source = {image.get("src"): image for image in showcase.images}
    for source in figure_sources:
        image = image_by_source[source]
        if not image.get("alt"):
            errors.append(f"missing alt text: {source}")
        if not image.get("width") or not image.get("height"):
            errors.append(f"missing intrinsic dimensions: {source}")

    index_href_targets = {
        href.split("showcase.html", 1)[1] for href in index.hrefs if href.startswith("showcase.html#cap-")
    }
    for target in data["index_links"]:
        if target not in index_href_targets:
            errors.append(f"homepage is missing required deep link: {target}")
        if target[1:] not in showcase.ids:
            errors.append(f"homepage deep link target does not exist: {target}")

    positioning = " ".join(data["canonical_positioning"].split())
    for path in (INDEX, SHOWCASE, README):
        prose = " ".join(path.read_text(encoding="utf-8").split())
        if positioning not in prose:
            errors.append(f"canonical positioning drift: {path.relative_to(ROOT)}")

    current_fingerprint = _source_fingerprint()
    recorded_fingerprint = data["review"].get("source_fingerprint")
    if current_fingerprint != recorded_fingerprint:
        errors.append(
            "user-facing source changed since website review; inspect affected claims/visuals, then run "
            'check_website_coverage.py --refresh --note "…"'
        )

    if errors:
        print("[website] FAIL — showcase coverage drift detected:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"[website] OK — {len(mapped_routes)} QA routes ({len(excluded_routes)} excluded), "
        f"{len(data['external_surfaces'])} external surfaces, {len(registered_figures)} current figures"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="record a completed website visual/copy review")
    parser.add_argument("--note", default="", help="required review note when --refresh is used")
    args = parser.parse_args()
    return refresh(args.note) if args.refresh else check()


if __name__ == "__main__":
    raise SystemExit(main())
