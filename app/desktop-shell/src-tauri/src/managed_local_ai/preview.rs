//! Product-facing setup, startup, and status orchestration for the pinned Local AI Preview.

use super::{
    install, start_config, DeveloperConfig, LocalAiInstallState, ManagedAiError,
    ManagedLocalAiState,
};
use serde::Serialize;
use std::path::{Path, PathBuf};

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
}

/// At packaged-app startup, preserve the explicit developer path, otherwise start the pinned
/// production target only when the user selected the managed Local AI provider.
pub async fn start_for_startup(
    data_dir: &Path,
    settings_path: &Path,
    state: &ManagedLocalAiState,
) -> Result<Option<PathBuf>, ManagedAiError> {
    if let Some(config) = DeveloperConfig::from_environment()? {
        return start_config(data_dir, state, config).await;
    }
    if !settings_select_managed_local(settings_path) {
        return Ok(None);
    }
    let paths = install::installed_paths(data_dir)?.ok_or(ManagedAiError::InvalidConfig(
        "Local AI is selected but has not been set up",
    ))?;
    start_config(data_dir, state, DeveloperConfig::production(paths)).await
}

pub async fn setup_and_start(
    data_dir: &Path,
    state: &ManagedLocalAiState,
    install_state: &LocalAiInstallState,
) -> Result<LocalAiStatus, ManagedAiError> {
    if install_state.snapshot().0.is_some() {
        return Err(ManagedAiError::InvalidConfig(
            "Local AI setup is already running",
        ));
    }
    install_state.set(Some("checking"), None);
    let data_dir_owned = data_dir.to_path_buf();
    let progress = install_state.clone();
    let paths = tokio::task::spawn_blocking(move || {
        if let Some(paths) = install::installed_paths(&data_dir_owned)? {
            #[cfg(windows)]
            if install::verify_install(&paths).is_ok() {
                progress.set(None, None);
                return Ok(paths);
            }
        }
        install::install_windows(&data_dir_owned, &progress)
    })
    .await
    .map_err(|_| ManagedAiError::Io("Local AI setup worker failed"))??;
    install_state.set(Some("preparing"), None);
    let result = start_config(data_dir, state, DeveloperConfig::production(paths)).await;
    match result {
        Ok(_) => {
            install_state.set(None, None);
            Ok(local_ai_status(data_dir, state, install_state))
        }
        Err(error) => {
            install_state.set(None, Some(error.detail()));
            Err(error)
        }
    }
}

pub fn local_ai_status(
    data_dir: &Path,
    state: &ManagedLocalAiState,
    install_state: &LocalAiInstallState,
) -> LocalAiStatus {
    let (stage, error) = install_state.snapshot();
    let installed = install::installed_paths(data_dir).ok().flatten().is_some();
    let running = state
        .0
        .lock()
        .expect("managed local AI state poisoned")
        .as_mut()
        .is_some_and(|handle| matches!(handle.child.try_wait(), Ok(None)));
    let (status, detail) = if let Some(stage) = stage {
        (stage, None)
    } else if let Some(error) = error {
        ("error", Some(error.to_string()))
    } else if running {
        ("ready", None)
    } else if installed {
        ("installed", None)
    } else if cfg!(windows) {
        ("not_installed", None)
    } else {
        (
            "unsupported",
            Some("Local AI Preview setup currently supports Windows x64.".to_string()),
        )
    };
    LocalAiStatus {
        state: status,
        detail,
        installed,
        running,
        model_id: install::MODEL_ID,
        model_bytes: install::MODEL_BYTES,
        evidence: "testing",
        execution: "on_device",
    }
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
}
