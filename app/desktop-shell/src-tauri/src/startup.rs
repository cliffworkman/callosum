//! Owns the current startup/splash state so the splash can SEED from a snapshot on load — closing the
//! backlog-#78 lost-early-events race (inc 594, #39).
//!
//! `setup()` spawns the startup task immediately, but the splash window's JS `listen("backend-status")` may
//! only register *after* the first `record()` fires — and Tauri never replays an event, so that first stage
//! (e.g. "checking the runtime") is lost and the splash sits on its initial copy until the next event. This is
//! the same hazard `updater::current_update_state` already documents for the `main` window. The fix is the same:
//! Rust owns the current state, and the splash queries it once on load (`current_startup_state`) to seed, then
//! listens for live updates. A live event always wins over the seed, so seeding is indistinguishable from having
//! received the event.
//!
//! `record()` is the single seam BOTH emit paths (lib.rs `emit_status`, python_runtime.rs `emit_progress`) route
//! through, so the queryable snapshot and the broadcast event can never diverge. The `state` field is a stable,
//! structured stage key (never free prose) — the splash switches on it; `detail` is human text shown as
//! secondary copy, never parsed for control flow.

use std::sync::Mutex;
use std::time::Instant;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

/// The current startup snapshot, in exactly the shape the splash renders. `state` is one of the real lifecycle
/// stages only (never an invented one): idle | runtime_check | runtime_manifest | runtime_migration |
/// runtime_download | runtime_extract | runtime_ready | starting | failed.
#[derive(Serialize, Clone)]
pub struct StartupSnapshot {
    pub state: String,
    pub detail: String,
    pub downloaded_bytes: Option<u64>,
    pub total_bytes: Option<u64>,
    pub elapsed_ms: u64,
}

impl Default for StartupSnapshot {
    fn default() -> Self {
        Self {
            state: "idle".to_string(),
            detail: String::new(),
            downloaded_bytes: None,
            total_bytes: None,
            elapsed_ms: 0,
        }
    }
}

/// App-managed startup state. `started_at` is fixed at construction (before the startup task is spawned), so
/// `elapsed_ms` is an honest "how long has startup been running" — used by the splash for a non-fake indeterminate
/// wait indicator, never to fabricate an ETA.
pub struct StartupState {
    inner: Mutex<StartupSnapshot>,
    started_at: Instant,
}

impl Default for StartupState {
    fn default() -> Self {
        Self {
            inner: Mutex::new(StartupSnapshot::default()),
            started_at: Instant::now(),
        }
    }
}

/// Update the owned snapshot AND broadcast it as `backend-status`. Both must always agree — that's the whole
/// point of a single seam.
pub fn record(
    app: &AppHandle,
    state: &str,
    detail: &str,
    downloaded_bytes: Option<u64>,
    total_bytes: Option<u64>,
) {
    let managed = app.state::<StartupState>();
    let elapsed_ms = managed.started_at.elapsed().as_millis() as u64;
    let snapshot = StartupSnapshot {
        state: state.to_string(),
        detail: detail.to_string(),
        downloaded_bytes,
        total_bytes,
        elapsed_ms,
    };
    if let Ok(mut guard) = managed.inner.lock() {
        *guard = snapshot.clone();
    }
    let _ = app.emit_to("splash", "backend-status", snapshot);
}

/// The queryable seed (the #78 fix). Returns the latest recorded snapshot with a FRESH `elapsed_ms`, so a splash
/// that loads mid-startup shows the right elapsed even for a state recorded seconds earlier.
#[tauri::command]
pub fn current_startup_state(app: AppHandle) -> StartupSnapshot {
    let managed = app.state::<StartupState>();
    let mut snapshot = managed
        .inner
        .lock()
        .map(|g| g.clone())
        .unwrap_or_default();
    snapshot.elapsed_ms = managed.started_at.elapsed().as_millis() as u64;
    snapshot
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_snapshot_is_idle_with_no_progress() {
        let snap = StartupSnapshot::default();
        assert_eq!(snap.state, "idle");
        assert!(snap.downloaded_bytes.is_none() && snap.total_bytes.is_none());
        assert_eq!(snap.elapsed_ms, 0);
    }

    #[test]
    fn snapshot_serializes_with_the_splash_field_names() {
        let snap = StartupSnapshot {
            state: "runtime_download".to_string(),
            detail: "Downloading…".to_string(),
            downloaded_bytes: Some(10),
            total_bytes: Some(100),
            elapsed_ms: 1234,
        };
        let json = serde_json::to_string(&snap).unwrap();
        // the splash reads exactly these keys (no rename); a drift here would silently break progress rendering.
        for key in [
            "\"state\":\"runtime_download\"",
            "\"detail\":\"Downloading",
            "\"downloaded_bytes\":10",
            "\"total_bytes\":100",
            "\"elapsed_ms\":1234",
        ] {
            assert!(json.contains(key), "missing {key} in {json}");
        }
    }
}
