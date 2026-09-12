// Generic, release-keyed "What's new" banner (#43, inc 593). Replaces the bespoke, hardcoded
// LocalAiWhatsNewHint: one mechanism, driven by the in-repo registry `app/frontend/whatsnew.json` (injected at
// build time as `window.CALLOSUM_WHATSNEW`, a map of EXACT semantic version → {headline, actionKind}). The
// release drift gate (tools/check_whatsnew_coverage.py) mechanically requires every shipped desktop version to
// have either an entry here or an explicit no-banner decline — so release↔banner drift can't happen silently.
//
// Behavior: on mount, compare the running app_version (/health) to the last-seen version (localStorage). Show
// the single NEWEST entry whose version is > lastSeen and ≤ app_version (never announce a future version).
// Dismiss stamps lastSeen = app_version (everything up to now is seen). The frontend NEVER derives behavior
// from arbitrary prose: `actionKind` is a typed, bounded key (unknown → no action button).

const WHATSNEW_LASTSEEN_KEY = "callosum.whatsnew.lastseen";
const _LOCAL_AI_LEGACY_KEY = "callosum.local-ai-whatsnew.v1"; // old bespoke hint's dismissal (migrated once)
const _LOCAL_AI_VERSION = "0.5.5"; // the version the Local AI entry is keyed at (see whatsnew.json)

// Parse "X.Y.Z" → [X,Y,Z] ints, or null if malformed (a legacy/garbage stored value must fail safe, never throw).
function _semverParts(v) {
  if (typeof v !== "string") return null;
  const m = v.trim().match(/^(\d+)\.(\d+)\.(\d+)$/);
  return m ? [Number(m[1]), Number(m[2]), Number(m[3])] : null;
}

// Semantic (not lexical) compare: -1 / 0 / 1. Unparseable operands sort as lowest (so a malformed lastSeen means
// "nothing seen" → the newest entry shows, the safe default). 0.5.10 > 0.5.9 (the lexical trap this avoids).
function _semverCmp(a, b) {
  const pa = _semverParts(a);
  const pb = _semverParts(b);
  if (!pa && !pb) return 0;
  if (!pa) return -1;
  if (!pb) return 1;
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] < pb[i] ? -1 : 1;
  }
  return 0;
}

// The typed action routing. A whatsnew entry's `actionKind` maps to a {label, handler} here; anything else (or
// null) yields no action button — behavior is never taken from free text in the registry.
function _whatsNewAction(actionKind, handlers) {
  if (actionKind === "local-ai" && handlers.onOpenLocalAi) {
    return { label: "Set up Local AI", run: handlers.onOpenLocalAi };
  }
  return null;
}

// Pick the newest entry to show given the running version + last-seen version. Pure + testable.
function pickWhatsNew(entries, appVersion, lastSeen) {
  if (!entries || typeof entries !== "object" || !_semverParts(appVersion)) return null;
  let best = null; // { version, headline, actionKind }
  for (const [version, entry] of Object.entries(entries)) {
    if (!entry || typeof entry.headline !== "string") continue;
    if (_semverParts(version) === null) continue; // ignore a malformed registry key
    if (_semverCmp(version, lastSeen) <= 0) continue; // already seen (or older than last-seen)
    if (_semverCmp(version, appVersion) > 0) continue; // never announce a version newer than what's running
    if (best === null || _semverCmp(version, best.version) > 0) {
      best = { version, headline: entry.headline, actionKind: entry.actionKind || null };
    }
  }
  return best;
}

function WhatsNewBanner({ readOnly, onOpenLocalAi }) {
  const [appVersion, setAppVersion] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  // One-time migration: a user who dismissed the old Local AI hint shouldn't see it again under the new key.
  useEffect(() => {
    try {
      const seen = _loadLayout(WHATSNEW_LASTSEEN_KEY, "");
      if (!seen && _loadLayout(_LOCAL_AI_LEGACY_KEY, "0") === "1") {
        _saveLayout(WHATSNEW_LASTSEEN_KEY, _LOCAL_AI_VERSION);
      }
    } catch (e) { /* localStorage may be unavailable; the banner simply shows */ }
  }, []);

  // Fetch the running version once (only when read-write is confirmed — a read-only companion shows no banner).
  useEffect(() => {
    if (readOnly !== false) return;
    let alive = true;
    api("/health").then(r => { if (alive && r.ok && r.data) setAppVersion(r.data.app_version || null); });
    return () => { alive = false; };
  }, [readOnly]);

  if (readOnly !== false || dismissed || !appVersion) return null;
  const entries = (typeof window !== "undefined" && window.CALLOSUM_WHATSNEW) || {};
  let lastSeen = "";
  try { lastSeen = _loadLayout(WHATSNEW_LASTSEEN_KEY, ""); } catch (e) { lastSeen = ""; }
  const pick = pickWhatsNew(entries, appVersion, lastSeen);
  if (!pick) return null;

  const action = _whatsNewAction(pick.actionKind, { onOpenLocalAi });
  const dismiss = () => {
    setDismissed(true);
    try { _saveLayout(WHATSNEW_LASTSEEN_KEY, appVersion); } catch (e) { /* best-effort */ }
  };
  return (
    <div className="axis-hint workspace-whatsnew" role="region" aria-label="What's new">
      <span>{pick.headline}</span>
      <div className="workspace-whatsnew-actions">
        {action && <button type="button" className="btn btn-link" onClick={() => { action.run(); dismiss(); }}>{action.label}</button>}
        <button type="button" className="btn-icon workspace-whatsnew-dismiss" aria-label="Dismiss what's new" title="Dismiss" onClick={dismiss}>×</button>
      </div>
    </div>
  );
}
