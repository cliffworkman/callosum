"""Serve-time assembly of the modular frontend into a single self-contained document.

The frontend source lives under `app/frontend/` (a shell template + one CSS file + ordered
`js/*.jsx` chunks). This assembles them into ONE document served at `/` — preserving the
project's single-file-to-the-browser, no-extra-file-serving-surface guarantees: the JSX chunks
are concatenated (no module boundaries) and **precompiled to plain JS by esbuild** (inc 102),
then injected into the single `<script>`. (Through inc 101 the JSX was transpiled in the browser
by `babel-standalone`; precompiling drops that ~500KB CDN download + runtime transform and the
two dev-console Babel messages it caused.) The IIFE esbuild emits keeps every chunk in one shared
scope, identical to the former single `<script type="text/babel">`.

esbuild is a **build-time** dependency (`package.json`, installed via `npm install`/`npm ci`);
the running server only ever serves the prebuilt `callosum-app.html` (no Node at serve time). The
rare live-assembly fallback transpiles on demand and raises a clear error if esbuild is absent.
Only project-owned files are read; the result is cached after the first build.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from app.backend.api.startup import PROJECT_ROOT

FRONTEND_DIR = PROJECT_ROOT / "app" / "frontend"
_ESBUILD_CLI = PROJECT_ROOT / "node_modules" / "esbuild" / "bin" / "esbuild"
# Classic-runtime JSX → global React; IIFE wrap = one shared scope for all concatenated chunks.
_ESBUILD_ARGS = [
    "--loader=jsx",
    "--jsx=transform",
    "--jsx-factory=React.createElement",
    "--jsx-fragment=React.Fragment",
    "--format=iife",
    "--target=esnext",
]

_cache: str | None = None


def frontend_sources_available() -> bool:
    return (FRONTEND_DIR / "index.html").is_file() and (FRONTEND_DIR / "js").is_dir()


def assemble_jsx() -> str:
    """Concatenate the ordered js/*.jsx chunks into one raw (pre-transpile) script.

    Sorted by filename so the numeric prefixes (00_, 10_, …) fix definition order: every
    top-level const/function must be defined before App uses it (one shared script scope).
    """
    return "".join(path.read_text(encoding="utf-8") for path in sorted((FRONTEND_DIR / "js").glob("*.jsx")))


def _transpile_jsx(jsx: str) -> str:
    """Precompile concatenated JSX → plain JS via esbuild (build-time). Raises a clear error if esbuild is absent.

    Cross-platform invocation gotcha: esbuild's installer leaves `node_modules/esbuild/bin/esbuild` as a tiny JS
    shim on **Windows** (run it with `node`), but on **Linux/macOS** it replaces it with the NATIVE binary — which
    must be executed **directly** (`node <native-binary>` raises `SyntaxError: Invalid or unexpected token`). So
    the command branches on the OS. (Caught only once CI actually ran the inc-102 build path on a Linux runner.)
    """
    if not _ESBUILD_CLI.is_file():
        raise RuntimeError(
            "Frontend build needs esbuild. Run `npm install` at the project root "
            "(installs the pinned esbuild from package.json), then rebuild."
        )
    if sys.platform == "win32":
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Frontend build needs Node on PATH to run esbuild. Install Node, then rebuild.")
        cmd = [node, str(_ESBUILD_CLI), *_ESBUILD_ARGS]
    else:
        cmd = [str(_ESBUILD_CLI), *_ESBUILD_ARGS]  # native binary (or shebang script) — exec directly, no `node`
    result = subprocess.run(cmd, input=jsx, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"esbuild failed to transpile the frontend JSX:\n{result.stderr.strip()}")
    return result.stdout


def build_frontend_document() -> str:
    """Assemble (and cache) index.html + styles.css + the esbuild-precompiled js/*.jsx into one HTML string."""
    global _cache
    if _cache is not None:
        return _cache
    template = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    styles = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
    script = _transpile_jsx(assemble_jsx())
    _cache = template.replace("{{STYLES}}", styles).replace("{{SCRIPT}}", script)
    return _cache
