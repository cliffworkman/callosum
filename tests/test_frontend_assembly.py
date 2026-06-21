"""Deterministic frontend-assembly smoke (no browser, no network).

The frontend ships as ordered ``app/frontend/js/*.jsx`` chunks concatenated by
``frontend.assemble_jsx`` and **precompiled to plain JS by esbuild** (inc 102) into the single
``<script>`` of ``frontend.build_frontend_document``, mirrored to the generated
``callosum-app.html`` by ``tools/build_frontend.py``. The most likely frontend regression is an
assembly break — a dropped chunk, a consumed placeholder left behind, a missing SRI tag, or a
``callosum-app.html`` left stale after a source edit. These guard exactly that, fast and offline.
The live browser smoke (``tests/e2e/``) covers runtime rendering and is opt-in for CI.

The transpiling tests require the build toolchain (``npm install`` → pinned esbuild); the
chunk-completeness test checks the raw concatenation, so it needs no toolchain.
"""

from __future__ import annotations

from app.backend.api.frontend import (
    FRONTEND_DIR,
    assemble_jsx,
    build_frontend_document,
    frontend_sources_available,
)
from app.backend.api.startup import PROJECT_ROOT

BUILT_ARTIFACT = PROJECT_ROOT / "callosum-app.html"


def test_frontend_sources_present():
    assert frontend_sources_available()


def test_assembles_and_placeholders_consumed():
    doc = build_frontend_document()
    assert isinstance(doc, str) and len(doc) > 100_000  # a real assembled document, not a stub
    assert "{{STYLES}}" not in doc and "{{SCRIPT}}" not in doc  # both placeholders filled
    assert '<div id="root"></div>' in doc  # the React mount point
    # The JSX is precompiled (inc 102) — plain JS, no in-browser Babel.
    assert 'type="text/babel"' not in doc and "babel.min.js" not in doc
    assert "React.createElement(" in doc  # proof the JSX was transpiled to the classic runtime


def test_all_cdn_scripts_have_sri():
    """Every third-party CDN <script> must carry a Subresource-Integrity hash (inc 53)."""
    doc = build_frontend_document()
    assert doc.count('integrity="sha384-') >= 2
    for src in ("react.production.min.js", "react-dom.production.min.js"):
        assert src in doc, f"missing CDN script {src}"


def test_every_js_chunk_is_included():
    # Checked against the RAW concatenation (pre-transpile), so completeness is verified without esbuild.
    chunks = sorted((FRONTEND_DIR / "js").glob("*.jsx"))
    assert chunks, "no js chunks found"
    raw = assemble_jsx()
    for chunk in chunks:
        text = chunk.read_text(encoding="utf-8")
        assert text in raw, f"{chunk.name} is missing from the assembled frontend"


def test_built_artifact_is_in_sync():
    """callosum-app.html must equal the live assembly — i.e. it was rebuilt after the last source
    edit (CLAUDE.md: re-run tools/build_frontend.py after editing app/frontend/)."""
    assert BUILT_ARTIFACT.is_file(), "callosum-app.html missing — run python tools/build_frontend.py"
    assert BUILT_ARTIFACT.read_text(encoding="utf-8") == build_frontend_document(), (
        "callosum-app.html is stale — re-run python tools/build_frontend.py"
    )
