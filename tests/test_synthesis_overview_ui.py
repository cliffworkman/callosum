"""Executable frontend contracts for supplementary Overview retry recovery."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_SOURCE = ROOT / "app" / "frontend" / "js" / "19b_synthesis_overview.jsx"
LIB_SOURCE = ROOT / "app" / "frontend" / "js" / "00_lib.jsx"


def _function_source(path: Path, declaration: str) -> str:
    source = path.read_text(encoding="utf-8")
    start = source.index(declaration)
    end = source.index("\n}\n", start) + 2
    return source[start:end]


def _run_node(source: str, body: str) -> dict:
    script = f"{source}\n{body}"
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_overview_age_parsing_and_stuck_threshold_boundary() -> None:
    source = OVERVIEW_SOURCE.read_text(encoding="utf-8")
    constant = "const OVERVIEW_STUCK_AFTER_SECONDS = 60;"
    data = _run_node(
        f"{constant}\n{_function_source(OVERVIEW_SOURCE, 'function _overviewAgeSeconds')}",
        """
const now = Date.parse('2026-08-24T12:00:00Z');
Date.now = () => now;
const naiveUtcAge = _overviewAgeSeconds('2026-08-24T11:59:30');
const below = _overviewAgeSeconds(new Date(now - 59900).toISOString());
const boundary = _overviewAgeSeconds(new Date(now - 60000).toISOString());
console.log(JSON.stringify({
  missing: _overviewAgeSeconds(null),
  invalid: _overviewAgeSeconds('not-a-date'),
  future: _overviewAgeSeconds(new Date(now + 5000).toISOString()),
  naiveUtcAge,
  below,
  boundary,
  belowStuck: below >= OVERVIEW_STUCK_AFTER_SECONDS,
  boundaryStuck: boundary >= OVERVIEW_STUCK_AFTER_SECONDS,
}));
""",
    )

    assert constant in source
    assert data == {
        "missing": None,
        "invalid": None,
        "future": 0,
        "naiveUtcAge": 30,
        "below": 59.9,
        "boundary": 60,
        "belowStuck": False,
        "boundaryStuck": True,
    }


def test_api_post_preserves_http_status_for_retry_decisions() -> None:
    source = """
const API_BASE = '';
const API_LABEL = 'same-origin API';
let nextResponse;
const callosumFetch = async () => nextResponse;
const _startTrackedApiOperation = () => null;
const _finishTrackedApiOperation = () => {};
const _notifyAuthRequired = () => {};
""" + _function_source(LIB_SOURCE, "async function apiPost")
    data = _run_node(
        source,
        """
(async () => {
  nextResponse = {ok:false, status:409, json:async () => ({detail:'already running'})};
  const conflict = await apiPost('/summaries/1/overview/retry', {});
  nextResponse = {ok:false, status:500, json:async () => ({detail:'failed'})};
  const failure = await apiPost('/summaries/1/overview/retry', {});
  nextResponse = {ok:true, status:200, json:async () => ({accepted:true})};
  const success = await apiPost('/summaries/1/overview/retry', {});
  console.log(JSON.stringify({conflict, failure, success}));
})();
""",
    )

    assert data["conflict"] == {"ok": False, "status": 409, "error": "already running"}
    assert data["failure"] == {"ok": False, "status": 500, "error": "failed"}
    assert data["success"] == {"ok": True, "data": {"accepted": True}}
