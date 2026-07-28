//! Auto-update checking (inc "desktop-shell auto-updater"). Windows/macOS use Tauri's official
//! updater plugin (minisign-signed artifacts); Linux — packaged `.deb`-only, which that plugin
//! doesn't support (it needs AppImage, explicitly abandoned for this project — see
//! `desktop-shell-linux.yml`'s own header) — gets a much simpler version-check-only fallback
//! against the public GitHub releases API, surfaced as "open the release page" instead of a
//! silent install. Both paths emit the same `"update-ready"` event so the frontend (`04d_update
//! .jsx`) only ever needs one listener; only a small serializable payload ever crosses into the
//! webview — same posture as `backend.rs`'s `BackendHandle` never leaving Rust.

use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter};

#[cfg(any(target_os = "macos", windows))]
use tauri_plugin_updater::{Update, UpdaterExt};

const STARTUP_DELAY: Duration = Duration::from_secs(30); // let the backend's own cold start have priority
const CHECK_INTERVAL: Duration = Duration::from_secs(6 * 60 * 60);
#[cfg(target_os = "linux")]
const RELEASES_PAGE: &str = "https://github.com/cliffworkman/callosum/releases/latest";

#[derive(Serialize, Clone)]
struct UpdateReadyPayload {
    version: String,
    notes: Option<String>,
    action: &'static str, // "restart" (Windows/macOS, silent download already done) | "open-page" (Linux)
}

/// Holds whatever's needed to finish an update once the user clicks through — never anything
/// bigger than that. On Windows/macOS this is the downloaded bytes + the `Update` handle needed
/// to call `.install()`; on Linux it's just "have we already told the frontend," so a later check
/// doesn't re-emit the same event every 6 hours.
#[derive(Default)]
pub struct UpdateState {
    #[cfg(any(target_os = "macos", windows))]
    ready: Mutex<Option<(Update, Vec<u8>)>>,
    #[cfg(target_os = "linux")]
    notified: Mutex<bool>,
}

pub async fn run_periodic_check(app: AppHandle) {
    tokio::time::sleep(STARTUP_DELAY).await;
    loop {
        #[cfg(any(target_os = "macos", windows))]
        check_desktop(&app).await;
        #[cfg(target_os = "linux")]
        check_linux(&app).await;
        tokio::time::sleep(CHECK_INTERVAL).await;
    }
}

#[cfg(any(target_os = "macos", windows))]
async fn check_desktop(app: &AppHandle) {
    use tauri::Manager;
    let state = app.state::<UpdateState>();
    if state.ready.lock().unwrap().is_some() {
        return; // a Ready update already awaits the user's click — never clobber it with a re-check
    }
    // Every failure branch below (no updater handle, offline, a malformed manifest, a failed
    // download) is an expected, benign steady state — not exceptional — so each just returns
    // quietly and lets the next periodic tick try again, matching backend.rs's own terse style.
    let Ok(updater) = app.updater() else { return };
    let update = match updater.check().await {
        Ok(Some(update)) => update,
        _ => return, // None (already current) or Err (offline / bad manifest) — both a no-op here
    };
    let version = update.version.clone();
    let notes = update.body.clone();
    // Silent by design — this is the "pushed automatically" half. No UI during the download itself;
    // the toast only appears once it's actually ready to apply.
    let Ok(bytes) = update.download(|_chunk_len, _content_len| {}, || {}).await else { return };
    *state.ready.lock().unwrap() = Some((update, bytes));
    let _ = app.emit(
        "update-ready",
        UpdateReadyPayload { version, notes, action: "restart" },
    );
}

#[cfg(target_os = "linux")]
async fn check_linux(app: &AppHandle) {
    use tauri::Manager;
    let state = app.state::<UpdateState>();
    if *state.notified.lock().unwrap() {
        return;
    }
    let client = match reqwest::Client::builder().timeout(Duration::from_secs(10)).build() {
        Ok(c) => c,
        Err(_) => return,
    };
    let resp = match client
        .get("https://api.github.com/repos/cliffworkman/callosum/releases/latest")
        .header("User-Agent", "callosum-desktop-shell")
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return, // offline — fail closed, no retry storm; the next 6h tick tries again
    };
    let json: serde_json::Value = match resp.json().await {
        Ok(j) => j,
        Err(_) => return,
    };
    let Some(tag) = json.get("tag_name").and_then(|v| v.as_str()) else {
        return;
    };
    let remote = tag.trim_start_matches('v');
    let current = app.package_info().version.to_string();
    if is_newer(remote, &current) {
        *state.notified.lock().unwrap() = true;
        let _ = app.emit(
            "update-ready",
            UpdateReadyPayload { version: remote.to_string(), notes: None, action: "open-page" },
        );
    }
}

// Pure logic, kept compiled in test builds on any OS (not just target_os = "linux", its only real
// caller) so `cargo test` can actually exercise it from this Windows dev machine too.
#[cfg(any(test, target_os = "linux"))]
fn is_newer(remote: &str, current: &str) -> bool {
    parse_version(remote) > parse_version(current)
}

#[cfg(any(test, target_os = "linux"))]
fn parse_version(v: &str) -> (u32, u32, u32) {
    let mut parts = v.split('.').map(|p| p.parse::<u32>().unwrap_or(0));
    (parts.next().unwrap_or(0), parts.next().unwrap_or(0), parts.next().unwrap_or(0))
}

/// Windows/macOS: installs the already-downloaded update and restarts. A no-op elsewhere (the
/// frontend only ever invokes this in response to an `action: "restart"` event, which only that
/// platform pair ever emits) — kept always-defined so `lib.rs`'s `invoke_handler` list needs no
/// per-platform cfg-splitting of its own.
#[tauri::command]
pub fn install_update_now(app: AppHandle) -> Result<(), String> {
    #[cfg(any(target_os = "macos", windows))]
    {
        use tauri::Manager;
        let state = app.state::<UpdateState>();
        let taken = state.ready.lock().unwrap().take();
        if let Some((update, bytes)) = taken {
            update.install(bytes).map_err(|e| e.to_string())?;
            // Triggers the SAME RunEvent::ExitRequested/Exit lib.rs already handles to kill the
            // backend child process cleanly — no new cleanup path needed for the restart case.
            app.request_restart();
        }
        Ok(())
    }
    #[cfg(not(any(target_os = "macos", windows)))]
    {
        let _ = app;
        Ok(())
    }
}

/// Linux: opens the GitHub release page in the system browser. A no-op elsewhere.
#[tauri::command]
pub fn open_release_page() -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(RELEASES_PAGE)
            .spawn()
            .map(|_| ())
            .map_err(|e| e.to_string())
    }
    #[cfg(not(target_os = "linux"))]
    {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newer_patch_is_detected() {
        assert!(is_newer("0.3.1", "0.3.0"));
    }

    #[test]
    fn same_version_is_not_newer() {
        assert!(!is_newer("0.3.0", "0.3.0"));
    }

    #[test]
    fn older_version_is_not_newer() {
        assert!(!is_newer("0.2.9", "0.3.0"));
    }

    #[test]
    fn minor_bump_is_detected_over_a_higher_patch() {
        assert!(is_newer("0.4.0", "0.3.9"));
    }
}
