//! Only the packaged main webview may perform these fixed local actions; no HTTP mutation API.
use crate::{browser_preview_files as files, preview_state as state};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{path::Path, sync::Mutex};
use tauri::{AppHandle, Manager, WebviewWindow};
use tauri_plugin_opener::OpenerExt;
static LOCK: Mutex<()> = Mutex::new(());

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Status,
    Enable,
    Prepare,
    OpenFolder,
    Verify,
    Disable,
}

fn nonce() -> Result<String, String> {
    let mut bytes = [0u8; 32];
    getrandom::fill(&mut bytes).map_err(|_| "Could not create a verification challenge.")?;
    Ok(files::hash(&bytes))
}

pub fn trusted(label: &str, url: &tauri::Url, port: u16) -> bool {
    label == "main"
        && url.scheme() == "http"
        && url.host_str() == Some("127.0.0.1")
        && url.port() == Some(port)
        && url.path() == "/"
        && url.username().is_empty()
        && url.password().is_none()
}

fn register(app: &AppHandle, root: &Path) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        crate::connector_registration::register_on_startup(
            root.parent().ok_or("Invalid preview root")?,
        );
        let report: Value = serde_json::from_slice(
            &std::fs::read(root.parent().unwrap().join("connector-registration.json"))
                .map_err(|_| "No registration report")?,
        )
        .map_err(|_| "Invalid registration report")?;
        if report["results"].as_array().is_none_or(|r| {
            r.is_empty()
                || r.iter().any(|v| {
                    v["outcome"] == "failed" || v["outcome"] == "skipped_unstable_location"
                })
        }) {
            return Err("Install Callosum in Applications, reopen it, then Prepare again.".into());
        }
    }
    #[cfg(windows)]
    {
        let connector = app
            .path()
            .resource_dir()
            .map_err(|_| "Missing resources")?
            .join("connector/callosum-connector.exe");
        if !connector.is_file() {
            return Err("Packaged connector missing. Reinstall Callosum.".into());
        }
        let identity: Value =
            serde_json::from_str(include_str!("../../connector/identity.json")).unwrap();
        let mut ids = identity["production_extension_ids"]
            .as_array()
            .unwrap()
            .clone();
        ids.push(identity["preview_extension_id"].clone());
        let origins: Vec<String> = ids
            .iter()
            .map(|v| format!("chrome-extension://{}/", v.as_str().unwrap()))
            .collect();
        // Keep NSIS ownership/uninstall checks intact: use its one shared manifest path.
        let host = identity["native_host_name"]
            .as_str()
            .ok_or("Invalid host identity")?;
        let manifest_dir = connector.parent().ok_or("Missing connector directory")?;
        let manifest_name = format!("{host}.json");
        state::write(
            manifest_dir,
            &manifest_name,
            &json!({"name":identity["native_host_name"],"description":"Callosum browser connector","type":"stdio","path":connector,"allowed_origins":origins}),
        )?;
        let reg = std::env::var_os("SystemRoot")
            .map(std::path::PathBuf::from)
            .ok_or("Windows directory unavailable")?
            .join("System32/reg.exe");
        for browser in ["Google\\Chrome", "Microsoft\\Edge"] {
            use std::os::windows::process::CommandExt;
            let status = std::process::Command::new(&reg)
                .args([
                    "ADD",
                    &format!("HKCU\\Software\\{browser}\\NativeMessagingHosts\\{host}"),
                    "/ve",
                    "/t",
                    "REG_SZ",
                    "/d",
                ])
                .arg(manifest_dir.join(&manifest_name))
                .arg("/f")
                .creation_flags(0x08000000)
                .output()
                .map_err(|_| "Cannot register native host")?;
            if !status.status.success() {
                return Err(
                    "Native host registration failed. Check browser policy or reinstall Callosum."
                        .into(),
                );
            }
        }
    }
    let _ = (app, root);
    Ok(())
}

#[tauri::command]
pub fn browser_preview(
    app: AppHandle,
    window: WebviewWindow,
    action: Action,
) -> Result<Value, String> {
    if !cfg!(any(windows, target_os = "macos")) {
        return Err("Browser Capture preview is available on Windows and macOS only.".into());
    }
    let data = app
        .path()
        .app_data_dir()
        .map_err(|_| "Application data directory unavailable")?;
    let port = std::fs::read_to_string(data.join("last-port.txt"))
        .ok()
        .and_then(|s| s.trim().parse::<u16>().ok())
        .ok_or("Backend is not ready")?;
    if !trusted(
        window.label(),
        &window
            .url()
            .map_err(|_| "Cannot verify the desktop origin")?,
        port,
    ) {
        return Err("Preview setup is available only in the packaged Callosum main window.".into());
    }
    let _guard = LOCK.lock().map_err(|_| "Preview setup is busy")?;
    let root = data.join("browser-capture-preview");
    files::ensure_root(&root)?;
    match action {
        Action::Enable => {
            if state::generation(&root).is_none() {
                state::write(
                    &root,
                    "enabled.json",
                    &json!({"enabled":true,"generation":nonce()?}),
                )?;
            }
        }
        Action::Disable => {
            state::write(
                &root,
                "enabled.json",
                &json!({"enabled":false,"generation":nonce()?}),
            )?;
            if let Err(reason) = files::cleanup(&root) {
                return Ok(
                    json!({"enabled":false,"cleanup_error":reason,"message":"Preview disabled. Modified files were retained. Remove the extension in your browser."}),
                );
            }
        }
        Action::Prepare => {
            state::generation(&root).ok_or("Enable early access first.")?;
            files::prepare(&root)?;
            state::write(&root, "challenge.json", &json!({"expires":0}))?;
            register(&app, &root)?;
        }
        Action::OpenFolder => {
            files::verified(&root)?;
            app.opener()
                .open_path(
                    root.join("extension").to_string_lossy().to_string(),
                    None::<&str>,
                )
                .map_err(|_| "Could not open the extension folder.")?;
        }
        Action::Verify => {
            let generation = state::generation(&root).ok_or("Enable early access first.")?;
            let installed = files::verified(&root)?;
            if installed.sha256 != files::package().sha256 {
                return Err(
                    "Prepare the current extension and reload it in the browser first.".into(),
                );
            }
            state::write(
                &root,
                "challenge.json",
                &json!({"nonce":nonce()?,"generation":generation,"expires":state::now()+60}),
            )?;
        }
        Action::Status => {}
    }
    let package = files::package();
    let enabled = state::generation(&root);
    let installed = files::verified(&root);
    let mut connection = "not_checked";
    if let (Some(generation), Some(challenge)) = (&enabled, state::read(&root, "challenge.json")) {
        if challenge["generation"] == *generation {
            connection = if challenge["expires"].as_u64().unwrap_or(0) < state::now() {
                "expired"
            } else {
                "waiting"
            };
            if let Some(receipt) = state::read(&root, "verified.json") {
                if connection == "waiting"
                    && receipt["nonce"] == challenge["nonce"]
                    && receipt["generation"] == *generation
                    && receipt["version"] == package.version
                {
                    connection = "verified";
                }
            }
        }
    }
    Ok(
        json!({"enabled":enabled.is_some(),"prepared":installed.is_ok(),"update_available":installed.as_ref().is_ok_and(|r| r.sha256!=package.sha256),
        "package_error":installed.as_ref().err(),"version":package.version,"prepared_version":installed.as_ref().ok().map(|r|&r.version),"sha256":package.sha256,"extension_id":package.extension_id,
        "folder":root.join("extension"),"connection":connection,
        "verified_at":if connection=="verified" {state::read(&root,"verified.json").map(|r|r["at"].clone())} else {None},"store_available":false}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn exact_main_backend_origin_only() {
        for (label, url) in [
            ("main", "https://127.0.0.1:1234/"),
            ("splash", "http://127.0.0.1:1234/"),
            ("main", "http://127.0.0.1:1235/"),
            ("main", "https://evil.test/"),
            ("main", "http://localhost:1234/"),
            ("main", "http://127.0.0.1:1234/docs"),
        ] {
            assert!(!trusted(label, &url.parse().unwrap(), 1234));
        }
        assert!(trusted(
            "main",
            &"http://127.0.0.1:1234/".parse().unwrap(),
            1234
        ));
    }
}
