#!/usr/bin/env python3
"""Build the QA surface map for callosum, and check route coverage against it.

This is the linchpin of the QA mechanism: it turns "every surface an end user can touch"
into a *computed* artifact instead of a hand-maintained list, so coverage can never silently
drift as the app grows.

Two sources of truth, both parsed statically (no app import, no running server, pure stdlib —
runs identically in CI, on Windows/PowerShell, and in a Codex sandbox):

  * API surface   — every ``@router.<method>("<path>")`` decorator under
                    ``app/backend/api/routers/`` (the routers are bare ``APIRouter()`` with
                    absolute paths, so the decorator path *is* the served path).
  * Frontend surface — every interactive element / event handler in ``app/frontend/js/*.jsx``
                    (``<button> <input> <select> <textarea>`` and ``onClick/onChange/onBlur/
                    onInput/onKeyDown/onSubmit``), each pinned to chunk + line.

Usage
-----
    python tools/qa/build_surface_map.py extract            # write surface-map.json (default)
    python tools/qa/build_surface_map.py extract --stdout   # print, don't write
    python tools/qa/build_surface_map.py check              # diff route declarations vs. map

``check`` reads the QA route files in ``.claude/qa-routes/*.md``. Each route declares the
surfaces it exercises in a machine block at the top of the file:

    <!-- qa-coverage
    api: GET /papers, POST /papers/export, /papers/{paper_id}/*
    fe: 10_pdf_layer.jsx, 25_detail.jsx#L42
    -->

Matching is prefix/glob-friendly:
  * an api token matches a route id exactly, OR as a trailing ``*`` prefix
    (``/papers/{paper_id}/*`` covers every method+subpath under it),
  * an fe token matches a chunk name (covers the whole chunk) or a specific ``chunk#Lnn``.

Exit code: ``check`` exits non-zero if any **API** surface is uncovered (hard gate). Uncovered
**frontend** elements are reported but do not fail the build by default (static JSX analysis
can't resolve a handler to behavior, so the FE side is a checklist, not a precise gate) — pass
``--strict-fe`` to make uncovered FE elements fail too.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- locate the repo root relative to this file (tools/qa/build_surface_map.py) -------------
THIS = Path(__file__).resolve()
REPO_ROOT = THIS.parents[2]
ROUTERS_DIR = REPO_ROOT / "app" / "backend" / "api" / "routers"
FRONTEND_JS_DIR = REPO_ROOT / "app" / "frontend" / "js"
QA_ROUTES_DIR = REPO_ROOT / ".claude" / "qa-routes"
OUTPUT = REPO_ROOT / "tools" / "qa" / "surface-map.json"

HTTP_METHODS = {"get", "post", "patch", "delete", "put", "head", "options"}

# interactive frontend tokens we treat as "a surface an end user can touch"
FE_TAG_RE = re.compile(r"<(button|input|select|textarea)\b", re.IGNORECASE)
FE_HANDLER_RE = re.compile(r"\b(onClick|onChange|onBlur|onInput|onKeyDown|onKeyUp|onSubmit|onDoubleClick)\s*=")


@dataclass
class ApiSurface:
    id: str
    method: str
    path: str
    router: str
    line: int


@dataclass
class FeSurface:
    id: str
    chunk: str
    line: int
    kind: str
    snippet: str


@dataclass
class SurfaceMap:
    api: list[ApiSurface] = field(default_factory=list)
    fe: list[FeSurface] = field(default_factory=list)


# --------------------------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------------------------
def _iter_source_files(directory: Path, suffix: str) -> list[Path]:
    """Real source files only — skip the stray ``*.tmp.*`` atomic-write orphans in the tree."""
    return sorted(p for p in directory.glob(f"*{suffix}") if ".tmp." not in p.name and p.is_file())


def extract_api(routers_dir: Path = ROUTERS_DIR) -> list[ApiSurface]:
    surfaces: list[ApiSurface] = []
    for py in _iter_source_files(routers_dir, ".py"):
        if py.name == "__init__.py":
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                parsed = _route_from_decorator(dec)
                if parsed is None:
                    continue
                method, path = parsed
                surfaces.append(
                    ApiSurface(
                        id=f"{method} {path}",
                        method=method,
                        path=path,
                        router=py.name,
                        line=dec.lineno,
                    )
                )
    # stable, deduped (a path can legitimately appear once per method)
    seen: dict[str, ApiSurface] = {}
    for s in surfaces:
        seen.setdefault(s.id, s)
    return sorted(seen.values(), key=lambda s: (s.path, s.method))


def _route_from_decorator(dec: ast.expr) -> tuple[str, str] | None:
    """Return (METHOD, path) for ``@router.get("/x")`` style decorators, else None."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute) or func.attr.lower() not in HTTP_METHODS:
        return None
    # func.value should be a name like ``router``; don't over-constrain — accept any.
    if not dec.args:
        return None
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return func.attr.upper(), first.value
    return None


def extract_fe(frontend_dir: Path = FRONTEND_JS_DIR) -> list[FeSurface]:
    surfaces: list[FeSurface] = []
    for jsx in _iter_source_files(frontend_dir, ".jsx"):
        for i, raw in enumerate(jsx.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            for m in FE_TAG_RE.finditer(raw):
                surfaces.append(_fe(jsx.name, i, f"tag:{m.group(1).lower()}", line))
            for m in FE_HANDLER_RE.finditer(raw):
                surfaces.append(_fe(jsx.name, i, m.group(1), line))
    return surfaces


def _fe(chunk: str, line: int, kind: str, raw: str) -> FeSurface:
    snippet = (raw[:160] + "…") if len(raw) > 160 else raw
    return FeSurface(id=f"{chunk}#L{line}", chunk=chunk, line=line, kind=kind, snippet=snippet)


def _git_rev() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:
        return None


def build_map() -> SurfaceMap:
    return SurfaceMap(api=extract_api(), fe=extract_fe())


def map_to_dict(sm: SurfaceMap) -> dict:
    return {
        "schema": "callosum-qa-surface-map/1",
        "git_rev": _git_rev(),
        "counts": {
            "api": len(sm.api),
            "fe": len(sm.fe),
            "fe_chunks": len({f.chunk for f in sm.fe}),
        },
        "api": [vars(s) for s in sm.api],
        "fe": [vars(s) for s in sm.fe],
    }


# --------------------------------------------------------------------------------------------
# coverage check
# --------------------------------------------------------------------------------------------
COVERAGE_BLOCK_RE = re.compile(r"<!--\s*qa-coverage\s*(.*?)-->", re.DOTALL | re.IGNORECASE)


def _parse_coverage_block(text: str) -> tuple[list[str], list[str]]:
    """Pull the (api, fe) token lists out of a route file's qa-coverage comment block."""
    m = COVERAGE_BLOCK_RE.search(text)
    if not m:
        return [], []
    api_tokens: list[str] = []
    fe_tokens: list[str] = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.lower().startswith("api:"):
            api_tokens += [t.strip() for t in line[4:].split(",") if t.strip()]
        elif line.lower().startswith("fe:"):
            fe_tokens += [t.strip() for t in line[3:].split(",") if t.strip()]
    return api_tokens, fe_tokens


def _api_covered(route_id: str, tokens: list[str]) -> bool:
    for tok in tokens:
        if tok == route_id:
            return True
        # bare-path token (no method) → match any method on that exact path
        if " " not in tok and tok == route_id.split(" ", 1)[1]:
            return True
        # trailing-* prefix glob, with or without a leading METHOD
        if tok.endswith("*"):
            prefix = tok[:-1]
            if route_id.startswith(prefix):
                return True
            if " " not in tok and route_id.split(" ", 1)[1].startswith(prefix):
                return True
    return False


def _fe_covered(fe_id: str, chunk: str, tokens: list[str]) -> bool:
    for tok in tokens:
        if tok == fe_id:
            return True
        if tok == chunk:  # whole-chunk claim
            return True
        if tok.endswith("*") and fe_id.startswith(tok[:-1]):
            return True
    return False


def run_check(strict_fe: bool = False) -> int:
    sm = build_map()
    if not QA_ROUTES_DIR.exists():
        print(f"[qa] no route dir at {QA_ROUTES_DIR} — nothing declared yet.", file=sys.stderr)
        api_tokens: list[str] = []
        fe_tokens: list[str] = []
    else:
        api_tokens, fe_tokens = [], []
        for route in sorted(QA_ROUTES_DIR.glob("*.md")):
            a, f = _parse_coverage_block(route.read_text(encoding="utf-8"))
            api_tokens += a
            fe_tokens += f

    uncovered_api = [s.id for s in sm.api if not _api_covered(s.id, api_tokens)]
    uncovered_fe = [f"{s.id} ({s.kind})" for s in sm.fe if not _fe_covered(s.id, s.chunk, fe_tokens)]

    print(
        f"[qa] API surfaces: {len(sm.api)}  | covered: {len(sm.api) - len(uncovered_api)}  | uncovered: {len(uncovered_api)}"
    )
    print(
        f"[qa] FE surfaces:  {len(sm.fe)}  | covered: {len(sm.fe) - len(uncovered_fe)}  | uncovered: {len(uncovered_fe)}"
    )

    if uncovered_api:
        print("\n[qa] UNCOVERED API surfaces (hard gate):")
        for sid in uncovered_api:
            print(f"  - {sid}")
    if uncovered_fe:
        print(f"\n[qa] uncovered FE surfaces ({'hard gate' if strict_fe else 'checklist'}):")
        for sid in uncovered_fe[:60]:
            print(f"  - {sid}")
        if len(uncovered_fe) > 60:
            print(f"  … and {len(uncovered_fe) - 60} more")

    failed = bool(uncovered_api) or (strict_fe and bool(uncovered_fe))
    if failed:
        print("\n[qa] FAIL — add or extend a QA route to cover the surfaces above (see .claude/QA-POLICY.md).")
        return 1
    print("\n[qa] OK — every gated surface is claimed by a QA route.")
    return 0


# --------------------------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="callosum QA surface map / coverage check")
    sub = parser.add_subparsers(dest="cmd")

    p_extract = sub.add_parser("extract", help="build surface-map.json")
    p_extract.add_argument("--stdout", action="store_true", help="print instead of writing the file")
    p_extract.add_argument("--out", type=Path, default=OUTPUT)

    p_check = sub.add_parser("check", help="diff route declarations against the surface map")
    p_check.add_argument("--strict-fe", action="store_true", help="fail on uncovered frontend elements too")

    args = parser.parse_args(argv)
    cmd = args.cmd or "extract"

    if cmd == "extract":
        payload = map_to_dict(build_map())
        text = json.dumps(payload, indent=2)
        if getattr(args, "stdout", False):
            print(text)
        else:
            args.out.write_text(text + "\n", encoding="utf-8")
            print(f"[qa] wrote {args.out}  (api={payload['counts']['api']}, fe={payload['counts']['fe']})")
        return 0

    if cmd == "check":
        return run_check(strict_fe=getattr(args, "strict_fe", False))

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
