mod backend;
mod updater;

use backend::{kill_backend, resolved_paths, spawn_backend, wait_for_health, BackendState};
use tauri::{AppHandle, Emitter, Manager, WebviewUrl, WebviewWindowBuilder};
use updater::UpdateState;

/// Resolve paths, spawn the backend, poll it healthy, then swap the splash window for the real
/// callosum UI. Shared between first launch (`setup()`) and the splash page's Retry button.
async fn start_backend_and_show_main(app: AppHandle) {
    let paths = match resolved_paths(&app) {
        Ok(p) => p,
        Err(e) => {
            emit_status(&app, "failed", &e.detail());
            return;
        }
    };

    emit_status(&app, "starting", "Starting Callosum… this can take a minute the first time.");

    let app_version = app.package_info().version.to_string();
    let (mut handle, port) = match spawn_backend(&paths, &app_version) {
        Ok(v) => v,
        Err(e) => {
            emit_status(&app, "failed", &e.detail());
            return;
        }
    };

    if let Err(e) = wait_for_health(&mut handle, port, &paths.log_path).await {
        let detail = e.detail();
        let _ = handle.child.kill();
        emit_status(&app, "failed", &detail);
        return;
    }

    *app.state::<BackendState>().0.lock().unwrap() = Some(handle);

    let url = format!("http://127.0.0.1:{port}").parse().expect("valid loopback URL");
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
}

fn emit_status(app: &AppHandle, state: &str, detail: &str) {
    let _ = app.emit_to(
        "splash",
        "backend-status",
        serde_json::json!({ "state": state, "detail": detail }),
    );
}

#[tauri::command]
async fn retry_backend(app: AppHandle) -> Result<(), String> {
    // A previous attempt (if any) already returned its BackendHandle to None on failure, so this
    // is safe to re-run unconditionally — there is nothing to tear down first.
    start_backend_and_show_main(app).await;
    Ok(())
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
        .manage(UpdateState::default())
        .invoke_handler(tauri::generate_handler![
            retry_backend,
            updater::install_update_now,
            updater::open_release_page,
            updater::check_for_updates_now
        ])
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(start_backend_and_show_main(handle));
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
            }
        });
}
