"""The splash's structured startup-state contract (#39, inc 594): every `state` string the desktop shell
records (lib.rs `emit_status` + python_runtime.rs `progress`) must have a `STAGE_LABELS` entry in splash.js, so
the splash switches on the structured state and never has to parse the human `detail` for a real stage. Also
pins the queryable-snapshot seam so the #78 late-listener race stays fixed."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "app" / "desktop-shell"
LIB_RS = SHELL / "src-tauri" / "src" / "lib.rs"
PY_RUNTIME_RS = SHELL / "src-tauri" / "src" / "python_runtime.rs"
STARTUP_RS = SHELL / "src-tauri" / "src" / "startup.rs"
SPLASH_JS = SHELL / "splash" / "splash.js"

# The states lib.rs emits are string literals passed as emit_status(..., "state", ...); python_runtime.rs emits
# them as progress("state", ...). Collect both, minus "failed" (handled by its own branch, not a stage label).
_EMIT_STATUS = re.compile(r'emit_status\([^,]+,\s*"([a-z_]+)"')
_PROGRESS = re.compile(r'progress\(\s*"([a-z_]+)"')


def _emitted_states() -> set[str]:
    states: set[str] = set()
    states.update(_EMIT_STATUS.findall(LIB_RS.read_text(encoding="utf-8")))
    states.update(_PROGRESS.findall(PY_RUNTIME_RS.read_text(encoding="utf-8")))
    return states


def test_every_recorded_startup_state_has_a_splash_stage_label():
    js = SPLASH_JS.read_text(encoding="utf-8")
    label_keys = set(re.findall(r"^\s*([a-z_]+):\s*\"", js, re.MULTILINE))  # STAGE_LABELS keys
    for state in _emitted_states():
        assert state in label_keys, (
            f"startup state {state!r} is recorded by the shell but has no STAGE_LABELS entry in splash.js — "
            f"the splash would fall back to parsing `detail` for it (#39 structured-state contract)."
        )


def test_failed_is_emitted_and_handled_distinctly():
    # `failed` must be an emitted state and the splash must special-case it (Retry, no bar) rather than treat it
    # as a normal stage label.
    assert "failed" in _emitted_states()
    js = SPLASH_JS.read_text(encoding="utf-8")
    assert 'state === "failed"' in js and "retryEl.hidden = false" in js


def test_splash_seeds_from_the_queryable_snapshot_then_listens():
    # The #78 fix: seed from current_startup_state on load, THEN listen — a late-registered listener never loses
    # the first stage.
    js = SPLASH_JS.read_text(encoding="utf-8")
    assert 'invoke("current_startup_state")' in js
    assert 'listen("backend-status"' in js
    # both emit paths route through the single owned seam (record), so snapshot and event never diverge
    lib = LIB_RS.read_text(encoding="utf-8")
    pyrt = PY_RUNTIME_RS.read_text(encoding="utf-8")
    assert "startup::record(" in lib and "crate::startup::record(" in pyrt
    assert "pub fn current_startup_state(" in STARTUP_RS.read_text(encoding="utf-8")


def test_no_fake_progress_for_non_measurable_phases():
    # Honest progress: the bar shows only when byte totals exist; slow non-measurable phases show elapsed, never
    # a fabricated percentage/ETA.
    js = SPLASH_JS.read_text(encoding="utf-8")
    assert "SLOW_INDETERMINATE" in js and "formatElapsed(" in js
    assert "aria-live" in (SHELL / "splash" / "index.html").read_text(encoding="utf-8")
