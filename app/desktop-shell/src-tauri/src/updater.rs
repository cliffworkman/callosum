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

/// The download itself is silent for INSTALL purposes (no dialog interrupts the user), but the
/// frontend Status popover shows it as a real in-progress row instead of a black box — the same
/// "don't leave the user guessing how long this takes" rationale as the cross-feature Status
/// popover (inc 415/406). These two events are Windows/macOS-only (Linux never downloads silently).
#[derive(Serialize, Clone)]
struct DownloadingPayload {
    version: String,
}

#[derive(Serialize, Clone)]
struct ProgressPayload {
    version: String,
    downloaded: u64,
    total: Option<u64>,
}

/// The result of a check, returned to the Settings "Check for updates" button (inc "desktop-shell
/// auto-updater" follow-up) as well as discarded by the silent periodic loop. `Downloading` means
/// the check itself found a newer version and handed off to the background download — it does NOT
/// wait for that download to finish (a manual click shouldn't block on a potentially large
/// transfer); the existing update-downloading/update-progress/update-ready events carry the rest.
#[derive(Serialize, Clone)]
#[serde(tag = "kind")]
pub enum CheckOutcome {
    UpToDate,
    Downloading { version: String },
    Ready { version: String },
    Failed { detail: String },
}

/// Holds whatever's needed to finish an update once the user clicks through — never anything
/// bigger than that. On Windows/macOS: `ready` is the downloaded bytes + the `Update` handle
/// needed to call `.install()`; `downloading` is the in-flight version (if any), so a manual check
/// while a download is already underway reports it instead of starting a second concurrent one. On
/// Linux: `notified` is the version already surfaced to the frontend, so a later check (periodic or
/// manual) reports the same version instead of re-emitting the event every 6 hours.
#[derive(Default)]
pub struct UpdateState {
    #[cfg(any(target_os = "macos", windows))]
    ready: Mutex<Option<(Update, Vec<u8>)>>,
    #[cfg(any(target_os = "macos", windows))]
    downloading: Mutex<Option<String>>,
    #[cfg(target_os = "linux")]
    notified: Mutex<Option<String>>,
}

/// The updater's current phase, in exactly the shape `useDesktopUpdate` already keeps in state, so
/// seeding from this is indistinguishable from having received the events live.
///
/// **Why this exists.** The check loop starts on `setup()` and fires 30s later, but the `main`
/// window is only created once the backend is healthy -- a cold start that the splash itself warns
/// "can take a minute the first time". So `update-downloading`/`update-ready` are routinely
/// broadcast *before any window is listening*, and Tauri does not replay events: the toast never
/// appears, the Status popover stays empty, and the update is invisible even though it downloaded
/// fine. Polling once on mount closes that race instead of narrowing it (a longer startup delay
/// would only make the window smaller, never zero). Same hazard the splash's own `backend-status`
/// event has -- see backlog #78.
#[derive(Serialize, Clone)]
#[serde(tag = "phase", rename_all = "lowercase")]
pub enum UpdateSnapshot {
    Idle,
    Downloading {
        version: String,
        downloaded: u64,
        total: Option<u64>,
    },
    Ready {
        version: String,
        notes: Option<String>,
        action: &'static str,
    },
}

#[tauri::command]
pub fn current_update_state(app: AppHandle) -> UpdateSnapshot {
    use tauri::Manager;
    let state = app.state::<UpdateState>();
    #[cfg(any(target_os = "macos", windows))]
    {
        if let Some((update, _)) = state.ready.lock().unwrap().as_ref() {
            return UpdateSnapshot::Ready {
                version: update.version.clone(),
                notes: update.body.clone(),
                action: "restart",
            };
        }
        if let Some(version) = state.downloading.lock().unwrap().clone() {
            // Byte counts are not retained across the seam; the live progress events carry them.
            // Reporting an honest unknown beats inventing a figure (invariant #5).
            return UpdateSnapshot::Downloading {
                version,
                downloaded: 0,
                total: None,
            };
        }
    }
    #[cfg(target_os = "linux")]
    {
        if let Some(version) = state.notified.lock().unwrap().clone() {
            return UpdateSnapshot::Ready {
                version,
                notes: None,
                action: "open-page",
            };
        }
    }
    let _ = &state;
    UpdateSnapshot::Idle
}

pub async fn run_periodic_check(app: AppHandle) {
    tokio::time::sleep(STARTUP_DELAY).await;
    loop {
        #[cfg(any(target_os = "macos", windows))]
        {
            let _ = check_desktop(&app).await;
        }
        #[cfg(target_os = "linux")]
        {
            let _ = check_linux(&app).await;
        }
        tokio::time::sleep(CHECK_INTERVAL).await;
    }
}

/// Manual on-demand check, invoked from Settings. Reuses the exact same check functions the
/// silent periodic loop calls — the only difference is the caller actually reads the outcome.
#[tauri::command]
pub async fn check_for_updates_now(app: AppHandle) -> CheckOutcome {
    #[cfg(any(target_os = "macos", windows))]
    {
        check_desktop(&app).await
    }
    #[cfg(target_os = "linux")]
    {
        check_linux(&app).await
    }
}

#[cfg(any(target_os = "macos", windows))]
async fn check_desktop(app: &AppHandle) -> CheckOutcome {
    use tauri::Manager;
    let state = app.state::<UpdateState>();
    if let Some((existing, _)) = state.ready.lock().unwrap().as_ref() {
        // Re-emit rather than returning silently. The first `update-ready` may have been broadcast
        // before the main window existed (see `current_update_state`), and a Tauri event is never
        // replayed -- so without this, an update that went ready early could never surface a toast
        // again for the rest of the session, no matter how many times the user checked.
        let _ = app.emit(
            "update-ready",
            UpdateReadyPayload {
                version: existing.version.clone(),
                notes: existing.body.clone(),
                action: "restart",
            },
        );
        return CheckOutcome::Ready {
            version: existing.version.clone(),
        };
    }
    if let Some(version) = state.downloading.lock().unwrap().clone() {
        let _ = app.emit(
            "update-downloading",
            DownloadingPayload {
                version: version.clone(),
            },
        );
        return CheckOutcome::Downloading { version };
    }
    let Ok(updater) = app.updater() else {
        return CheckOutcome::Failed {
            detail: "The updater isn't available on this build.".into(),
        };
    };
    let update = match updater.check().await {
        Ok(Some(update)) => update,
        Ok(None) => return CheckOutcome::UpToDate,
        Err(e) => {
            return CheckOutcome::Failed {
                detail: e.to_string(),
            }
        }
    };
    let version = update.version.clone();
    *state.downloading.lock().unwrap() = Some(version.clone());
    spawn_download(app.clone(), update);
    CheckOutcome::Downloading { version }
}

/// The actual download, run to completion in its own spawned task so a manual check-for-updates
/// click returns as soon as a newer version is *found*, not once it's fully downloaded. Progress
/// and completion both ride the same events the silent periodic path always used.
#[cfg(any(target_os = "macos", windows))]
fn spawn_download(app: AppHandle, update: Update) {
    tauri::async_runtime::spawn(async move {
        use tauri::Manager;
        let state = app.state::<UpdateState>();
        let version = update.version.clone();
        let notes = update.body.clone();
        let _ = app.emit(
            "update-downloading",
            DownloadingPayload {
                version: version.clone(),
            },
        );
        let downloaded = Mutex::new(0u64);
        let last_emitted = Mutex::new(0u64);
        const PROGRESS_EMIT_STEP: u64 = 256 * 1024; // coalesce chunk callbacks so the webview isn't flooded
        let progress_app = app.clone();
        let progress_version = version.clone();
        let result = update
            .download(
                move |chunk_len, content_len| {
                    let mut total = downloaded.lock().unwrap();
                    *total += chunk_len as u64;
                    let mut last = last_emitted.lock().unwrap();
                    let done = content_len.map(|c| *total >= c).unwrap_or(false);
                    if *total - *last >= PROGRESS_EMIT_STEP || done {
                        *last = *total;
                        let _ = progress_app.emit(
                            "update-progress",
                            ProgressPayload {
                                version: progress_version.clone(),
                                downloaded: *total,
                                total: content_len,
                            },
                        );
                    }
                },
                || {},
            )
            .await;
        *state.downloading.lock().unwrap() = None;
        let Ok(bytes) = result else { return };
        *state.ready.lock().unwrap() = Some((update, bytes));
        let _ = app.emit(
            "update-ready",
            UpdateReadyPayload {
                version,
                notes,
                action: "restart",
            },
        );
    });
}

#[cfg(target_os = "linux")]
async fn check_linux(app: &AppHandle) -> CheckOutcome {
    use tauri::Manager;
    let state = app.state::<UpdateState>();
    if let Some(version) = state.notified.lock().unwrap().clone() {
        return CheckOutcome::Ready { version };
    }
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            return CheckOutcome::Failed {
                detail: e.to_string(),
            }
        }
    };
    let resp = match client
        .get("https://api.github.com/repos/cliffworkman/callosum/releases/latest")
        .header("User-Agent", "callosum-desktop-shell")
        .send()
        .await
    {
        Ok(r) => r,
        // offline — fail closed, no retry storm; the next 6h periodic tick tries again regardless
        Err(_) => {
            return CheckOutcome::Failed {
                detail: "Couldn't reach GitHub — check your connection.".into(),
            }
        }
    };
    let json: serde_json::Value = match resp.json().await {
        Ok(j) => j,
        Err(_) => {
            return CheckOutcome::Failed {
                detail: "Unexpected response from GitHub.".into(),
            }
        }
    };
    let Some(tag) = json.get("tag_name").and_then(|v| v.as_str()) else {
        return CheckOutcome::Failed {
            detail: "Unexpected response from GitHub.".into(),
        };
    };
    let remote = tag.trim_start_matches('v').to_string();
    let current = app.package_info().version.to_string();
    if is_newer(&remote, &current) {
        *state.notified.lock().unwrap() = Some(remote.clone());
        let _ = app.emit(
            "update-ready",
            UpdateReadyPayload {
                version: remote.clone(),
                notes: None,
                action: "open-page",
            },
        );
        CheckOutcome::Ready { version: remote }
    } else {
        CheckOutcome::UpToDate
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
    (
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
        parts.next().unwrap_or(0),
    )
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
