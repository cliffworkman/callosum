// Inc 620: the plain (JSX-free, so node-testable) logic behind the "Library modernization" surfaces -- the Settings
// polling contract, the 0.6.0 notice wording for upgrades vs fresh installs, and the Settings deep link. The backend
// (GET /modernization -> summary) decides every state and sentence; nothing here invents progress or a time estimate.

// Index-build states that are still ongoing. inc 616's waiting_disk is recoverable and ongoing, so it keeps the panel
// refreshing (the inc-620 fix: the retrieval panel used to drop it and stop polling, leaving a stale display).
const INDEX_RUN_BUSY_STATES = ["queued", "running", "pausing"];
const INDEX_RUN_WAITING_STATES = ["retrying", "waiting_resources", "waiting_disk"];
const INDEX_RUN_ACTIVE_STATES = INDEX_RUN_BUSY_STATES.concat(INDEX_RUN_WAITING_STATES);

const MODERNIZATION_IDLE_MS = 15000;

// One bounded loop for the Settings model section: how long to wait before the next refresh, or null to stop.
// Busy builds refresh quickly; waits (disk, memory, network, retry) keep refreshing slowly so recovery shows up
// without reopening Settings. Inc 621: paused, complete and action-required states also keep a slow idle refresh, since
// an import, another window or a repaired model can change them with no action here. Only disabled and unknown stop.
function modernizationPollDelay(modernization, profiles) {
  const runs = ((profiles && profiles.profiles) || []).map(p => p && p.index_run).filter(Boolean);
  if (runs.some(r => INDEX_RUN_BUSY_STATES.includes(r.state))) return 2000;
  if (runs.some(r => INDEX_RUN_WAITING_STATES.includes(r.state))) return 5000;
  const state = modernization && modernization.summary && modernization.summary.state;
  if (state === "working") return 3000;
  if (state === "waiting") return 10000;
  if (state === "paused" || state === "complete" || state === "action_required") return MODERNIZATION_IDLE_MS;
  return null;
}

// What an idle tick compares: anything the two panels would show differently. Unchanged means the far costlier
// GET /embedding-profiles (seconds on a real library, against milliseconds here) is not needed on that tick.
function modernizationSignature(m) {
  return m ? JSON.stringify([m.intent, m.summary, m.effective_retrieval, m.retrieval_preference, m.verifier, m.model_recovery]) : null;
}

// The 0.6.0 notice explains background work an upgraded library will do; a library with no papers has nothing to
// modernize, so it gets the entry's fresh-install wording instead (when the entry provides one).
function whatsNewHeadline(pick, libraryEmpty) {
  if (!pick) return null;
  return libraryEmpty === true && typeof pick.freshHeadline === "string" && pick.freshHeadline ? pick.freshHeadline : pick.headline;
}

// Where both the Status entry (its backend nav) and the 0.6.0 notice action lead: one bounded descriptor, one dispatcher.
const MODERNIZATION_SETTINGS_NAV = { workspace: "settings", section: "modernization" };

// Settings is a lazily mounted scrolling page; after switching to it, bring one section (by element id) into view.
function _focusSettingsSection(id, attempts = 20) {
  if (typeof document === "undefined" || !id) return;
  const el = document.getElementById(id);
  if (el) { el.scrollIntoView({ block: "start" }); return; }
  if (attempts > 0) requestAnimationFrame(() => _focusSettingsSection(id, attempts - 1));
}
