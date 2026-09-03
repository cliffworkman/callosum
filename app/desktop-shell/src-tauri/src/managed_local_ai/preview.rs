//! Product-facing setup, startup, and status orchestration for the pinned Local AI Preview.

use super::{
    install, start_config, DeveloperConfig, LocalAiInstallState, ManagedAiError,
    ManagedLocalAiState,
};
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

#[derive(Debug, Serialize)]
pub struct LocalAiDiagnostic {
    pub code: &'static str,
    pub feature: &'static str,
    pub message: String,
    pub suggested_action: &'static str,
    pub callosum_version: String,
    pub platform: String,
    pub timestamp: Option<String>,
    pub details: BTreeMap<&'static str, String>,
}

#[derive(Debug, Serialize)]
pub struct LocalAiStatus {
    pub state: &'static str,
    pub detail: Option<String>,
    pub installed: bool,
    pub running: bool,
    pub model_id: &'static str,
    pub model_bytes: u64,
    pub evidence: &'static str,
    pub execution: &'static str,
    pub downloaded_bytes: Option<u64>,
    pub total_bytes: Option<u64>,
    pub eta_seconds: Option<u64>,
    pub diagnostic: Option<LocalAiDiagnostic>,
}

/// At packaged-app startup, preserve the explicit developer path, otherwise start the pinned
/// production target only when the user selected the managed Local AI provider.
pub async fn start_for_startup(
    data_dir: &Path,
    settings_path: &Path,
    state: &ManagedLocalAiState,
    install_state: &LocalAiInstallState,
) -> Result<Option<PathBuf>, ManagedAiError> {
    if let Some(config) = DeveloperConfig::from_environment()? {
        return start_config(data_dir, state, config).await;
    }
    if !settings_select_managed_local(settings_path) {
        return Ok(None);
    }
    let paths = match install::installed_paths(data_dir) {
        Ok(Some(paths)) => paths,
        Ok(None) => {
            let error =
                ManagedAiError::InvalidConfig("Local AI is selected but has not been set up");
            install_state.set_error(&error);
            return Err(error);
        }
        Err(error) => {
            install_state.set_error(&error);
            return Err(error);
        }
    };
    match start_config(data_dir, state, DeveloperConfig::production(paths)).await {
        Ok(result) => Ok(result),
        Err(error) => {
            install_state.set_error(&error);
            Err(error)
        }
    }
}

pub async fn setup_and_start(
    data_dir: &Path,
    state: &ManagedLocalAiState,
    install_state: &LocalAiInstallState,
) -> Result<LocalAiStatus, ManagedAiError> {
    if install_state.snapshot().stage.is_some() {
        return Err(ManagedAiError::InvalidConfig(
            "Local AI setup is already running",
        ));
    }
    install_state.set(Some("checking"), None);
    let data_dir_owned = data_dir.to_path_buf();
    let progress = install_state.clone();
    let install_result = tokio::task::spawn_blocking(move || {
        if let Some(paths) = install::installed_paths(&data_dir_owned)? {
            #[cfg(any(windows, all(target_os = "macos", target_arch = "aarch64")))]
            if install::verify_install(&paths).is_ok() {
                progress.set(None, None);
                return Ok(paths);
            }
        }
        install::install_platform(&data_dir_owned, &progress)
    })
    .await
    .map_err(|_| ManagedAiError::Io("Local AI setup worker failed"));
    let paths = match install_result {
        Ok(Ok(paths)) => paths,
        Ok(Err(error)) => {
            install_state.set_error(&error);
            return Err(error);
        }
        Err(error) => {
            install_state.set_error(&error);
            return Err(error);
        }
    };
    install_state.set(Some("preparing"), None);
    let result = start_config(data_dir, state, DeveloperConfig::production(paths)).await;
    match result {
        Ok(_) => {
            install_state.set(None, None);
            Ok(local_ai_status(
                data_dir,
                state,
                install_state,
                env!("CARGO_PKG_VERSION"),
            ))
        }
        Err(error) => {
            install_state.set_error(&error);
            Err(error)
        }
    }
}

pub fn local_ai_status(
    data_dir: &Path,
    state: &ManagedLocalAiState,
    install_state: &LocalAiInstallState,
    app_version: &str,
) -> LocalAiStatus {
    let progress = install_state.snapshot();
    let installed = install::installed_paths(data_dir).ok().flatten().is_some();
    let running = state
        .0
        .lock()
        .expect("managed local AI state poisoned")
        .as_mut()
        .is_some_and(|handle| matches!(handle.child.try_wait(), Ok(None)));
    let supported = cfg!(any(
        windows,
        all(target_os = "macos", target_arch = "aarch64")
    ));
    let (status, detail) = if let Some(stage) = progress.stage {
        (stage, None)
    } else if let Some(error) = progress.detail {
        ("error", Some(error.to_string()))
    } else if running {
        ("ready", None)
    } else if installed {
        ("installed", None)
    } else if supported {
        ("not_installed", None)
    } else {
        (
            "unsupported",
            Some("This Callosum build does not support Local AI on this operating-system architecture.".to_string()),
        )
    };
    let diagnostic = status_diagnostic(status, detail.as_deref(), progress.error_code, app_version);
    LocalAiStatus {
        state: status,
        detail,
        installed,
        running,
        model_id: install::MODEL_ID,
        model_bytes: install::MODEL_BYTES,
        evidence: "testing",
        execution: "on_device",
        downloaded_bytes: progress.downloaded_bytes,
        total_bytes: progress.total_bytes,
        eta_seconds: progress.eta_seconds,
        diagnostic,
    }
}

fn status_diagnostic(
    status: &str,
    detail: Option<&str>,
    error_code: Option<&'static str>,
    app_version: &str,
) -> Option<LocalAiDiagnostic> {
    let (code, message, action) = match status {
        "error" => (
            error_code.unwrap_or("LOCAL_AI_SETUP_FAILED"),
            detail.unwrap_or("Local AI setup failed.").to_string(),
            "Retry Set up Local AI; if it fails again, copy these diagnostics into your report.",
        ),
        "unsupported" => (
            "LOCAL_AI_UNSUPPORTED_ARCHITECTURE",
            detail
                .unwrap_or("Local AI is unsupported by this build.")
                .to_string(),
            "Use the Apple Silicon macOS or Windows x64 Callosum build.",
        ),
        "installed" => (
            "LOCAL_AI_RUNTIME_NOT_RUNNING",
            "The verified Local AI files are installed, but the runtime is not running."
                .to_string(),
            "Choose Prepare Local AI to start it.",
        ),
        _ => return None,
    };
    let mut details = BTreeMap::new();
    details.insert("architecture", std::env::consts::ARCH.to_string());
    details.insert("operating_system", std::env::consts::OS.to_string());
    details.insert("runtime", "managed llama.cpp b10516".to_string());
    details.insert(
        "endpoint",
        "127.0.0.1 (authenticated ephemeral port)".to_string(),
    );
    Some(LocalAiDiagnostic {
        code,
        feature: "Local AI",
        message,
        suggested_action: action,
        callosum_version: app_version.to_string(),
        platform: format!("{} {}", std::env::consts::OS, std::env::consts::ARCH),
        timestamp: None,
        details,
    })
}

fn settings_select_managed_local(settings_path: &Path) -> bool {
    std::fs::read_to_string(settings_path)
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|value| value["provider"].as_str().map(str::to_owned))
        .as_deref()
        == Some("managed_local")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_selection_is_explicit_and_fail_closed() {
        let root = std::env::temp_dir().join("callosum-preview-settings-test");
        let _ = std::fs::create_dir_all(&root);
        let settings = root.join("settings.json");
        std::fs::write(&settings, r#"{"provider":"gemini"}"#).unwrap();
        assert!(!settings_select_managed_local(&settings));
        std::fs::write(&settings, r#"{"provider":"managed_local"}"#).unwrap();
        assert!(settings_select_managed_local(&settings));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn unavailable_states_have_copy_safe_actionable_diagnostics() {
        let diagnostic = status_diagnostic(
            "error",
            Some("the managed local AI runtime could not start"),
            Some("LOCAL_AI_RUNTIME_NOT_STARTED"),
            "0.5.3",
        )
        .unwrap();
        assert_eq!(diagnostic.code, "LOCAL_AI_RUNTIME_NOT_STARTED");
        assert_eq!(diagnostic.callosum_version, "0.5.3");
        assert_eq!(
            diagnostic.details["endpoint"],
            "127.0.0.1 (authenticated ephemeral port)"
        );
        let serialized = serde_json::to_string(&diagnostic).unwrap();
        assert!(!serialized.contains("auth-token"));
        assert!(!serialized.contains("api-key"));
        assert!(!serialized.contains("Users\\"));

        let unsupported = status_diagnostic("unsupported", None, None, "0.5.3").unwrap();
        assert_eq!(unsupported.code, "LOCAL_AI_UNSUPPORTED_ARCHITECTURE");
        assert!(status_diagnostic("ready", None, None, "0.5.3").is_none());
    }
}
