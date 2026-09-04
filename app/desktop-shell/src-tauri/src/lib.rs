mod backend;
mod managed_local_ai;
mod python_runtime;
mod quick_tunnel;
mod updater;

use backend::{
    kill_backend, kill_word_https, resolved_paths, spawn_backend, spawn_word_https,
    wait_for_health, wait_for_word_https_health, word_https_configured, BackendState,
    WordHttpsState,
};
use managed_local_ai::{
    local_ai_status as managed_local_ai_status, setup_and_start, shutdown as shutdown_local_ai,
    start_for_startup, LocalAiInstallState, LocalAiStatus, ManagedLocalAiState,
};
use quick_tunnel::QuickTunnelState;
use std::sync::atomic::Ordering;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use updater::UpdateState;

/// Resolve paths, spawn the backend, poll it healthy, then swap the splash window for the real
/// callosum UI. Shared between first launch (`setup()`) and the splash page's Retry button.
async fn start_backend_and_show_main(app: AppHandle) {
    emit_status(
        &app,
        "runtime_check",
        "Checking Callosum's managed Python runtime…",
    );
    if let Err(error) = python_runtime::ensure_runtime(app.clone()).await {
        emit_status(&app, "failed", &error.detail());
        return;
    }
    let paths = match resolved_paths(&app) {
        Ok(p) => p,
        Err(e) => {
            emit_status(&app, "failed", &e.detail());
            return;
        }
    };

    emit_status(
        &app,
        "starting",
        "Starting Callosum… this can take a minute the first time.",
    );

    let local_ai_state = app.state::<ManagedLocalAiState>().inner().clone();
    let local_ai_install_state = app.state::<LocalAiInstallState>().inner().clone();
    let descriptor = match start_for_startup(
        &paths.app_data_dir,
        &paths.settings_path,
        &local_ai_state,
        &local_ai_install_state,
    )
    .await
    {
        Ok(path) => path,
        Err(error) => {
            // Local AI fails closed without preventing the rest of Callosum from starting. Python will
            // preserve the selected provider as unavailable; it never substitutes a cloud target.
            eprintln!("Managed local AI unavailable: {}", error.detail());
            None
        }
    };

    let app_version = app.package_info().version.to_string();
    let (mut handle, port) = match spawn_backend(&paths, &app_version, descriptor.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            shutdown_local_ai(&local_ai_state);
            emit_status(&app, "failed", &e.detail());
            return;
        }
    };

    if let Err(e) = wait_for_health(&mut handle, port, &paths.log_path).await {
        let detail = e.detail();
        let _ = handle.child.kill();
        shutdown_local_ai(&local_ai_state);
        emit_status(&app, "failed", &detail);
        return;
    }

    *app.state::<BackendState>().0.lock().unwrap() = Some(handle);

    let url = format!("http://127.0.0.1:{port}")
        .parse()
        .expect("valid loopback URL");
    if WebviewWindowBuilder::new(&app, "main", WebviewUrl::External(url))
        .title("Callosum")
        .inner_size(1200.0, 900.0)
        .min_inner_size(800.0, 600.0)
        .build()
        .is_ok()
    {
        if let Some(splash) = app.get_webview_window("splash") {
            let _ = splash.close();
        }
    }

    // The main UI is usable as soon as its HTTP backend is healthy. The optional Word companion starts in
    // parallel so an enabled integration never adds a second full app-import delay to ordinary launch.
    if word_https_configured(&paths) {
        let word_app = app.clone();
        tauri::async_runtime::spawn(async move {
            if let Err(error) = start_word_https_inner(word_app).await {
                eprintln!("Word HTTPS companion unavailable: {error}");
            }
        });
    }
}

#[tauri::command]
fn local_ai_status(
    app: AppHandle,
    state: tauri::State<'_, ManagedLocalAiState>,
    install_state: tauri::State<'_, LocalAiInstallState>,
) -> Result<LocalAiStatus, String> {
    let paths = resolved_paths(&app).map_err(|error| error.detail())?;
    Ok(managed_local_ai_status(
        &paths.app_data_dir,
        state.inner(),
        install_state.inner(),
        &app.package_info().version.to_string(),
    ))
}

#[tauri::command]
async fn setup_local_ai(
    app: AppHandle,
    state: tauri::State<'_, ManagedLocalAiState>,
    install_state: tauri::State<'_, LocalAiInstallState>,
) -> Result<LocalAiStatus, String> {
    let paths = resolved_paths(&app).map_err(|error| error.detail())?;
    setup_and_start(&paths.app_data_dir, state.inner(), install_state.inner())
        .await
        .map_err(|error| error.detail().to_string())
}

#[tauri::command]
fn stop_local_ai(state: tauri::State<'_, ManagedLocalAiState>) {
    shutdown_local_ai(state.inner());
}

fn emit_status(app: &AppHandle, state: &str, detail: &str) {
    if state == "failed" {
        record_startup_failure(app, detail);
    }
    let _ = app.emit_to(
        "splash",
        "backend-status",
        serde_json::json!({ "state": state, "detail": detail }),
    );
}

/// Also write a startup failure somewhere readable, not only onto the splash window.
///
/// When startup fails the app stays alive showing the reason on the splash and never writes
/// `backend.log`, because that file is only created after the backend child spawns. The reason
/// therefore exists solely as pixels — unreadable over SSH, unreadable in CI (where a screenshot can
/// be blocked by a screen-recording consent prompt), and unaskable of a user who can only say "it
/// says starting forever". This is the same silence inc 568 removed from axis labelling, in the one
/// place where nothing else can speak.
///
/// The app-data directory is preferred, but a failure to resolve it is itself a plausible cause, so
/// the temp directory is the fallback rather than giving up.
fn record_startup_failure(app: &AppHandle, detail: &str) {
    let line = format!(
        "{} startup failed: {detail}\n",
        chrono_free_timestamp_or_default()
    );
    let target = app
        .path()
        .app_data_dir()
        .ok()
        .map(|dir| {
            let _ = std::fs::create_dir_all(&dir);
            dir.join("startup-error.log")
        })
        .unwrap_or_else(|| std::env::temp_dir().join("callosum-startup-error.log"));
    let _ = std::fs::write(&target, line);
}

/// Seconds since the Unix epoch. No date crate is a dependency here and one is not worth adding for
/// a diagnostic line; the ordering is what matters, not a human-formatted date.
fn chrono_free_timestamp_or_default() -> String {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|value| format!("t={}", value.as_secs()))
        .unwrap_or_else(|_| "t=unknown".to_string())
}

#[tauri::command]
async fn retry_backend(app: AppHandle) -> Result<(), String> {
    // A previous attempt (if any) already returned its BackendHandle to None on failure, so this
    // is safe to re-run unconditionally — there is nothing to tear down first.
    start_backend_and_show_main(app).await;
    Ok(())
}

async fn start_word_https_inner(app: AppHandle) -> Result<(), String> {
    let state = app.state::<WordHttpsState>();
    if state
        .handle
        .lock()
        .map_err(|_| "Word HTTPS state is unavailable")?
        .is_some()
    {
        return Ok(());
    }

    if state
        .starting
        .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .is_err()
    {
        let deadline = Instant::now() + Duration::from_secs(125);
        while state.starting.load(Ordering::Acquire) && Instant::now() < deadline {
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        return if state
            .handle
            .lock()
            .map_err(|_| "Word HTTPS state is unavailable")?
            .is_some()
        {
            Ok(())
        } else {
            Err("The Word HTTPS companion did not become ready".into())
        };
    }

    let result = start_word_https_owned(&app, state.inner()).await;
    state.starting.store(false, Ordering::Release);
    result
}

async fn start_word_https_owned(app: &AppHandle, state: &WordHttpsState) -> Result<(), String> {
    let paths = resolved_paths(app).map_err(|error| error.detail())?;
    let version = app.package_info().version.to_string();
    let mut handle = spawn_word_https(&paths, &version).map_err(|error| error.detail())?;
    if let Err(error) = wait_for_word_https_health(&mut handle, &paths).await {
        let _ = handle.child.kill();
        let _ = handle.child.wait();
        return Err(error.detail());
    }
    *state
        .handle
        .lock()
        .map_err(|_| "Word HTTPS state is unavailable")? = Some(handle);
    Ok(())
}

#[tauri::command]
async fn start_word_https_companion(app: AppHandle) -> Result<(), String> {
    start_word_https_inner(app).await
}

#[tauri::command]
fn stop_word_https_companion(state: tauri::State<'_, WordHttpsState>) {
    kill_word_https(state.inner());
}

#[tauri::command]
fn quick_tunnel_status(
    state: tauri::State<'_, QuickTunnelState>,
) -> quick_tunnel::QuickTunnelStatus {
    quick_tunnel::status(state.inner())
}

#[tauri::command]
async fn start_quick_tunnel(
    app: AppHandle,
    state: tauri::State<'_, QuickTunnelState>,
) -> Result<quick_tunnel::QuickTunnelStatus, String> {
    let paths = resolved_paths(&app).map_err(|error| error.detail())?;
    let version = app.package_info().version.to_string();
    quick_tunnel::start(&paths, &version, state.inner()).await
}

#[tauri::command]
fn stop_quick_tunnel(state: tauri::State<'_, QuickTunnelState>) -> quick_tunnel::QuickTunnelStatus {
    quick_tunnel::stop(state.inner())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            let window = app
                .get_webview_window("main")
                .or_else(|| app.get_webview_window("splash"));
            if let Some(w) = window {
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(BackendState::default())
        .manage(WordHttpsState::default())
        .manage(QuickTunnelState::default())
        .manage(ManagedLocalAiState::default())
        .manage(LocalAiInstallState::default())
        .manage(UpdateState::default())
        .invoke_handler(tauri::generate_handler![
            retry_backend,
            start_word_https_companion,
            stop_word_https_companion,
            quick_tunnel_status,
            start_quick_tunnel,
            stop_quick_tunnel,
            local_ai_status,
            setup_local_ai,
            stop_local_ai,
            updater::install_update_now,
            updater::open_release_page,
            updater::check_for_updates_now
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            // Supervise the startup task rather than firing and forgetting it. A panic inside a
            // spawned task is swallowed by the async runtime: no crash report, no status, no log --
            // the splash would simply sit on "Checking Callosum's managed Python runtime…" forever,
            // which is indistinguishable from a slow first-run download. Turning that into a visible,
            // recorded failure is the difference between a diagnosable report and "it hangs".
            let supervised = tauri::async_runtime::spawn(start_backend_and_show_main(handle));
            let watchdog = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if supervised.await.is_err() {
                    emit_status(
                        &watchdog,
                        "failed",
                        "Callosum's startup task stopped unexpectedly before the backend could start.",
                    );
                }
            });
            let handle2 = app.handle().clone();
            tauri::async_runtime::spawn(updater::run_periodic_check(handle2));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if matches!(
                event,
                tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit
            ) {
                kill_backend(app_handle.state::<BackendState>().inner());
                kill_word_https(app_handle.state::<WordHttpsState>().inner());
                quick_tunnel::stop(app_handle.state::<QuickTunnelState>().inner());
                shutdown_local_ai(app_handle.state::<ManagedLocalAiState>().inner());
            }
        });
}
