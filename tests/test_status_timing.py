"""Calibrated Status timing model: privacy, confidence, and bounded local history."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.backend.api.job_timing import synthesis_timing_key
from integrations.gemini.generator import LLMConfig

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "app" / "frontend" / "js" / "04bb_status_timing.jsx"


def _run_node(body: str) -> dict:
    prelude = """
const timing = {
  STATUS_TIMING_SCHEMA, STATUS_TIMING_MAX_RECEIPTS, _estimateStatusStage,
  _formatTimingDuration, _loadTimingHistory, _recordStatusReceipts,
  _timingWorkloadBucket, _statusTimingWording
};
const storage = new Storage();
"""
    script = f"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync({json.dumps(str(MODEL))}, 'utf8');
const testBody = {json.dumps(body)};
class Storage {{
  constructor() {{ this.values = new Map(); }}
  getItem(key) {{ return this.values.has(key) ? this.values.get(key) : null; }}
  setItem(key, value) {{ this.values.set(key, value); }}
}}
const testPrelude = {json.dumps(prelude)};
vm.runInNewContext(source + testPrelude + testBody, {{ console, Storage }});
"""
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def test_timing_history_is_private_bounded_and_configuration_specific() -> None:
    data = _run_node(
        """
for (let i = 0; i < 260; i++) {
  timing._recordStatusReceipts({
    store: 'summary_jobs', job_id: `job-${i}`,
    completed_stages: [{key:'generate', duration_seconds:5 + (i % 3), timing_key:'gemini|model-a', workload_size:4}]
  }, storage);
}
timing._recordStatusReceipts({
  store:'summary_jobs', job_id:'secret-fixture', title:'PRIVATE PAPER TITLE', prompt:'PRIVATE PROMPT',
  completed_stages:[{key:'generate', duration_seconds:9, timing_key:'anthropic|model-b', workload_size:4}]
}, storage);
const raw = storage.getItem('callosum.status-timing.v1');
const history = timing._loadTimingHistory(storage);
console.log(JSON.stringify({
  count: history.receipts.length,
  modelA: timing._estimateStatusStage({key:'generate', timing_key:'gemini|model-a', workload_size:4}, storage),
  modelB: timing._estimateStatusStage({key:'generate', timing_key:'anthropic|model-b', workload_size:4}, storage),
  leaks: raw.includes('PRIVATE')
}));
"""
    )
    assert data["count"] <= 200
    assert data["modelA"]["sample_size"] == 24
    assert data["modelB"] is None
    assert data["leaks"] is False


def test_confidence_ladder_ranges_overruns_and_schema_reset() -> None:
    data = _run_node(
        """
const makeJob = (id, duration, variable=false) => ({
  store:'critical_review_jobs', job_id:id,
  completed_stages:[{key:'nli', duration_seconds:duration, timing_key:'nli|model-a|cpu', workload_size:60, variable}]
});
[10,10.2,9.9].forEach((d,i) => timing._recordStatusReceipts(makeJob(`m-${i}`, d), storage));
const stage = {key:'nli', timing_key:'nli|model-a|cpu', workload_size:60};
const moderate = timing._estimateStatusStage(stage, storage);
const moderateWording = timing._statusTimingWording(stage, 2, 'Local AI', storage);
[10.1,9.8,10.3,10,10.2].forEach((d,i) => timing._recordStatusReceipts(makeJob(`h-${i}`, d), storage));
const high = timing._estimateStatusStage(stage, storage);
const highWording = timing._statusTimingWording(stage, 9.8, 'Local AI', storage);
const overrun = timing._statusTimingWording(stage, 30, 'Local AI', storage);
storage.setItem('callosum.status-timing.v1', JSON.stringify({schema:999, receipts:[{id:'bad'}]}));
const reset = timing._loadTimingHistory(storage);
console.log(JSON.stringify({moderate, moderateWording, high, highWording, overrun, reset}));
"""
    )
    assert data["moderate"]["confidence"] == "moderate"
    assert data["moderateWording"].startswith("Usually ")
    assert data["high"]["confidence"] == "high"
    assert data["highWording"] == "Finishing soon"
    assert data["overrun"] == "Taking longer than recent runs"
    assert data["reset"] == {"schema": 1, "receipts": []}


def test_no_history_uses_provider_or_elapsed_only_fallback() -> None:
    data = _run_node(
        """
console.log(JSON.stringify({
  provider: timing._statusTimingWording({key:'generate', timing_key:'provider-a', workload_size:2, variable:true}, 7, 'Provider AI', storage),
  local: timing._statusTimingWording({key:'nli', timing_key:'local-a', workload_size:20}, 7, 'Local AI', storage),
  clamped: timing._formatTimingDuration(-50)
}));
"""
    )
    assert data == {"provider": "Timing varies by provider", "local": None, "clamped": "0s"}


def test_synthesis_timing_identity_separates_endpoint_without_leaking_endpoint_or_secret() -> None:
    first = LLMConfig(
        provider="custom-provider",
        model="model-a",
        wire_format="chat_completions",
        base_url="https://first.example/v1/?token=RECOGNIZABLE_SECRET",
        api_key="RECOGNIZABLE_API_KEY",
    )
    equivalent = LLMConfig(**{**first.__dict__, "api_key": "ROTATED_KEY"})
    other_endpoint = LLMConfig(**{**first.__dict__, "base_url": "https://second.example/v1"})
    first_key = synthesis_timing_key(first)
    assert first_key == synthesis_timing_key(equivalent)
    assert first_key != synthesis_timing_key(other_endpoint)
    assert "example" not in first_key
    assert "SECRET" not in first_key
    assert "API_KEY" not in first_key
