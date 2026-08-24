// Privacy-safe, device-local calibration for the Status popover. Receipts contain only
// controlled configuration labels, coarse numeric workload buckets, and durations.
// No prompt, paper, claim, citation, provider secret, or endpoint is ever stored.
const STATUS_TIMING_SCHEMA = 1;
const STATUS_TIMING_STORAGE_KEY = "callosum.status-timing.v1";
const STATUS_TIMING_MAX_RECEIPTS = 200;
const STATUS_TIMING_MAX_PER_SHAPE = 24;

function _timingWorkloadBucket(size) {
  if (!Number.isFinite(size) || size < 0) return "unknown";
  if (size <= 8) return "0-8";
  if (size <= 32) return "9-32";
  if (size <= 128) return "33-128";
  if (size <= 512) return "129-512";
  return "513+";
}

function _formatTimingDuration(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const remainder = value % 60;
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

function _emptyTimingHistory() { return { schema: STATUS_TIMING_SCHEMA, receipts: [] }; }

function _statusTimingStorage() {
  try { return globalThis.localStorage || null; } catch (_) { return null; }
}

function _validTimingReceipt(item) {
  return !!item && typeof item.id === "string" && item.id.length <= 180 &&
    typeof item.timing_key === "string" && item.timing_key.length <= 400 &&
    typeof item.stage === "string" && item.stage.length <= 80 &&
    typeof item.bucket === "string" && Number.isFinite(item.duration) &&
    item.duration >= 0 && item.duration <= (24 * 60 * 60);
}

function _loadTimingHistory(storage = _statusTimingStorage()) {
  if (!storage) return _emptyTimingHistory();
  try {
    const parsed = JSON.parse(storage.getItem(STATUS_TIMING_STORAGE_KEY) || "null");
    if (!parsed || parsed.schema !== STATUS_TIMING_SCHEMA || !Array.isArray(parsed.receipts)) {
      return _emptyTimingHistory();
    }
    return { schema: STATUS_TIMING_SCHEMA, receipts: parsed.receipts.filter(_validTimingReceipt).slice(-STATUS_TIMING_MAX_RECEIPTS) };
  } catch (_) {
    return _emptyTimingHistory();
  }
}

function _saveTimingHistory(history, storage = _statusTimingStorage()) {
  if (!storage) return;
  try { storage.setItem(STATUS_TIMING_STORAGE_KEY, JSON.stringify(history)); } catch (_) { /* storage is optional */ }
}

function _recordStatusReceipts(job, storage = _statusTimingStorage()) {
  if (!job || job.status === "error" || !Array.isArray(job.completed_stages) || !job.completed_stages.length) return;
  const history = _loadTimingHistory(storage);
  const known = new Set(history.receipts.map(item => item.id));
  let changed = false;
  for (const stage of job.completed_stages) {
    const id = `${job.store}:${job.job_id}:${stage.key}`;
    const receipt = {
      id,
      timing_key: String(stage.timing_key || "").slice(0, 400),
      stage: String(stage.key || "").slice(0, 80),
      bucket: _timingWorkloadBucket(stage.workload_size),
      duration: Number(stage.duration_seconds),
      variable: !!stage.variable,
    };
    if (known.has(id) || !_validTimingReceipt(receipt)) continue;
    history.receipts.push(receipt);
    known.add(id);
    changed = true;
  }
  if (!changed) return;
  const groupedCounts = new Map();
  history.receipts = history.receipts.reverse().filter(item => {
    const shape = `${item.timing_key}|${item.stage}|${item.bucket}`;
    const count = groupedCounts.get(shape) || 0;
    groupedCounts.set(shape, count + 1);
    return count < STATUS_TIMING_MAX_PER_SHAPE;
  }).reverse().slice(-STATUS_TIMING_MAX_RECEIPTS);
  _saveTimingHistory(history, storage);
}

function _timingQuantile(sorted, q) {
  if (!sorted.length) return null;
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const fraction = position - lower;
  return sorted[lower] + ((sorted[lower + 1] ?? sorted[lower]) - sorted[lower]) * fraction;
}

function _estimateStatusStage(stage, storage = _statusTimingStorage()) {
  if (!stage || !stage.timing_key || !stage.key) return null;
  const bucket = _timingWorkloadBucket(stage.workload_size);
  const matches = _loadTimingHistory(storage).receipts.filter(item =>
    item.timing_key === stage.timing_key && item.stage === stage.key && item.bucket === bucket
  );
  if (matches.length < 3) return null;
  const values = matches.map(item => item.duration).sort((a, b) => a - b);
  const median = _timingQuantile(values, 0.5);
  // A 10% scheduler/host-state guard around the empirical range keeps the
  // user-facing wording deliberately broader than the small local sample.
  const lower = Math.max(0, (matches.length < 5 ? values[0] : _timingQuantile(values, 0.1)) * 0.9);
  const upper = (matches.length < 5 ? values[values.length - 1] : _timingQuantile(values, 0.9)) * 1.1;
  const spread = median > 0 ? (upper - lower) / median : Infinity;
  const variable = !!stage.variable || matches.some(item => item.variable);
  return {
    confidence: matches.length >= 8 && spread <= 0.35 && !variable ? "high" : "moderate",
    median,
    lower,
    upper,
    sample_size: matches.length,
  };
}

function _statusTimingWording(stage, elapsed, computeKind, storage = _statusTimingStorage()) {
  const estimate = _estimateStatusStage(stage, storage);
  if (estimate) {
    if (elapsed >= estimate.upper) return "Taking longer than recent runs";
    if (estimate.confidence === "high") {
      const remaining = Math.max(1, Math.round(estimate.median - elapsed));
      return remaining <= 1 ? "Finishing soon" : `About ${_formatTimingDuration(remaining)} remaining`;
    }
    const usualLow = _formatTimingDuration(Math.max(1, estimate.lower));
    const usualHigh = _formatTimingDuration(Math.max(1, estimate.upper));
    // "for this step," not "total": the calibration is per-STAGE (a multi-stage job's stages each get
    // their own receipts), and this reads next to a job-level elapsed-time counter in the Status row --
    // "total" would misread as describing the whole job's duration.
    return `Usually ${usualLow}–${usualHigh} for this step`;
  }
  if (stage?.variable || (!stage && (computeKind || "").includes("Provider"))) return "Timing varies by provider";
  return null;
}

// Stage-scoped counterpart to 04c_status.jsx's _statusElapsed: the calibrated-timing comparison above must
// be checked against how long the CURRENT STAGE has run, never the whole job's elapsed time -- a multi-stage
// job's later stages would otherwise compare against the sum of every prior stage's duration too, so a
// normal-speed run reads as "taking longer than recent runs" by its last stage. Applies the exact same
// observed-at/clock-drift treatment _statusElapsed already applies at the job level (base value from the last
// poll + time ticked locally since that poll while still running), just against job.stage.elapsed_seconds
// (itself computed server-side from stage.started_at) instead of the job-level total.
function _statusStageElapsed(job, now) {
  if (!job || !job.stage) return null;
  const base = Math.max(0, Number(job.stage.elapsed_seconds) || 0);
  return job.status === "running" ? base + Math.max(0, (now - (job.observed_at || now)) / 1000) : base;
}
