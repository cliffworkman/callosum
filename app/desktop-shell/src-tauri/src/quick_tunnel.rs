//! Explicit, app-owned Cloudflare Quick Tunnel lifecycle for Google Docs and Word on the web.
//!
//! The connector never targets the ordinary UI backend. It targets a second Uvicorn child carrying
//! `CALLOSUM_TUNNEL_TARGET=1`, whose access middleware fails closed whenever Remote access is off. This avoids
//! treating cloudflared's loopback-forwarded requests as trusted local traffic during a setting transition.

use crate::backend::{
    kill_handle, pick_free_port, spawn_managed_command, BackendHandle, ResolvedPaths, StartupError,
};
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

const READY_TIMEOUT: Duration = Duration::from_secs(120);
const URL_TIMEOUT: Duration = Duration::from_secs(45);
const POLL_INTERVAL: Duration = Duration::from_millis(250);

struct QuickTunnelHandle {
    target: BackendHandle,
    connector: BackendHandle,
    url: String,
}

#[derive(Default)]
pub struct QuickTunnelState {
    handle: Mutex<Option<QuickTunnelHandle>>,
    starting: AtomicBool,
}

#[derive(Clone, Debug, Serialize)]
pub struct QuickTunnelStatus {
    pub available: bool,
    pub running: bool,
    pub url: Option<String>,
    pub detail: String,
}

pub async fn start(
    paths: &ResolvedPaths,
    app_version: &str,
    state: &QuickTunnelState,
) -> Result<QuickTunnelStatus, String> {
    if state
        .starting
        .compare_exchange(false, true, Ordering::AcqRel, Ordering::Acquire)
        .is_err()
    {
        return Err("The Quick Tunnel is already starting.".into());
    }
    let result = start_owned(paths, app_version, state).await;
    state.starting.store(false, Ordering::Release);
    result
}

async fn start_owned(
    paths: &ResolvedPaths,
    app_version: &str,
    state: &QuickTunnelState,
) -> Result<QuickTunnelStatus, String> {
    if let Some(current) = live_status(state, cloudflared_path().is_some()) {
        return Ok(current);
    }
    if !remote_access_enabled(&paths.settings_path) {
        return Err(
            "Turn on Remote access and copy its token before starting a Quick Tunnel.".into(),
        );
    }
    let cloudflared = cloudflared_path().ok_or(
        "cloudflared is not installed. Install Cloudflare cloudflared, restart Callosum, and try again.",
    )?;
    let (mut target, target_port) =
        spawn_tunnel_target(paths, app_version).map_err(|error| error.detail())?;
    if let Err(error) = wait_for_tunnel_target(&mut target, target_port).await {
        kill_handle(&mut target);
        return Err(error.detail());
    }

    let log_path = paths.app_data_dir.join("quick-tunnel.log");
    let config_path = paths.app_data_dir.join("quick-tunnel-config.yml");
    std::fs::write(&config_path, "no-autoupdate: true\n").map_err(|error| {
        format!("Couldn't create the isolated Quick Tunnel configuration: {error}")
    })?;
    let _ = std::fs::remove_file(&log_path);
    let mut command = Command::new(cloudflared);
    command
        .args([
            "tunnel",
            "--config",
            &config_path.to_string_lossy(),
            "--no-autoupdate",
            "--loglevel",
            "info",
            "--url",
            &format!("http://127.0.0.1:{target_port}"),
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut connector = match spawn_managed_command(command, &log_path, "Quick Tunnel connector") {
        Ok(handle) => handle,
        Err(error) => {
            kill_handle(&mut target);
            return Err(error.detail());
        }
    };
    let url = match wait_for_url(&mut connector, &log_path).await {
        Ok(url) => url,
        Err(error) => {
            kill_handle(&mut connector);
            kill_handle(&mut target);
            return Err(error);
        }
    };
    *state
        .handle
        .lock()
        .map_err(|_| "Quick Tunnel state is unavailable")? = Some(QuickTunnelHandle {
        target,
        connector,
        url: url.clone(),
    });
    Ok(QuickTunnelStatus {
        available: true,
        running: true,
        url: Some(url),
        detail: "Quick Tunnel URL created; it may take a moment to become reachable. Keep it and the bearer token private.".into(),
    })
}

pub fn status(state: &QuickTunnelState) -> QuickTunnelStatus {
    let available = cloudflared_path().is_some();
    live_status(state, available).unwrap_or_else(|| QuickTunnelStatus {
        available,
        running: false,
        url: None,
        detail: if available {
            "Quick Tunnel is stopped.".into()
        } else {
            "cloudflared is not installed.".into()
        },
    })
}

fn live_status(state: &QuickTunnelState, available: bool) -> Option<QuickTunnelStatus> {
    let mut guard = state.handle.lock().ok()?;
    let handle = guard.as_mut()?;
    let target_alive = matches!(handle.target.child.try_wait(), Ok(None));
    let connector_alive = matches!(handle.connector.child.try_wait(), Ok(None));
    if !target_alive || !connector_alive {
        if let Some(mut stopped) = guard.take() {
            kill_handle(&mut stopped.connector);
            kill_handle(&mut stopped.target);
        }
        return None;
    }
    Some(QuickTunnelStatus {
        available,
        running: true,
        url: Some(handle.url.clone()),
        detail: "Quick Tunnel URL created; it may take a moment to become reachable. Keep it and the bearer token private.".into(),
    })
}

pub fn stop(state: &QuickTunnelState) -> QuickTunnelStatus {
    if let Ok(mut guard) = state.handle.lock() {
        if let Some(mut handle) = guard.take() {
            kill_handle(&mut handle.connector);
            kill_handle(&mut handle.target);
        }
    }
    QuickTunnelStatus {
        available: cloudflared_path().is_some(),
        running: false,
        url: None,
        detail: "Quick Tunnel is stopped.".into(),
    }
}

fn remote_access_enabled(settings_path: &Path) -> bool {
    std::fs::read_to_string(settings_path)
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|data| {
            data.get("remote_access_enabled")
                .and_then(|value| value.as_bool())
        })
        .unwrap_or(false)
}

fn spawn_tunnel_target(
    paths: &ResolvedPaths,
    app_version: &str,
) -> Result<(BackendHandle, u16), StartupError> {
    let port = pick_free_port().map_err(|error| StartupError::SpawnFailed(error.to_string()))?;
    let mut command = Command::new(&paths.python_exe);
    command
        .args([
            "-m",
            "uvicorn",
            "app.backend.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            &port.to_string(),
            "--no-access-log",
        ])
        .current_dir(&paths.source_root)
        .env("CALLOSUM_DB_URL", &paths.db_url)
        .env("CALLOSUM_LIBRARY_DIR", &paths.library_dir)
        .env("CALLOSUM_APP_VERSION", app_version)
        .env("CALLOSUM_SETTINGS_PATH", &paths.settings_path)
        .env("CALLOSUM_WORD_HTTPS_DIR", &paths.word_https_dir)
        .env("CALLOSUM_TUNNEL_TARGET", "1")
        .env_remove("CALLOSUM_DISABLE_REMOTE_ACCESS")
        .env_remove(crate::managed_local_ai::DESCRIPTOR_ENV)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    for name in crate::managed_local_ai::OWNER_ONLY_ENV {
        command.env_remove(name);
    }
    let log_path = paths.app_data_dir.join("quick-tunnel-backend.log");
    spawn_managed_command(command, &log_path, "Quick Tunnel backend").map(|handle| (handle, port))
}

async fn wait_for_tunnel_target(handle: &mut BackendHandle, port: u16) -> Result<(), StartupError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|error| StartupError::SpawnFailed(error.to_string()))?;
    let health = format!("http://127.0.0.1:{port}/health");
    let gated = format!("http://127.0.0.1:{port}/settings");
    let deadline = Instant::now() + READY_TIMEOUT;
    loop {
        let healthy = matches!(client.get(&health).send().await, Ok(response) if response.status().is_success());
        let gate_proven = matches!(client.get(&gated).send().await, Ok(response) if response.status().as_u16() == 401);
        if healthy && gate_proven {
            return Ok(());
        }
        if matches!(handle.child.try_wait(), Ok(Some(_))) {
            return Err(StartupError::CrashedEarly(
                "The dedicated tunnel backend stopped before its bearer gate was ready.".into(),
            ));
        }
        if Instant::now() > deadline {
            return Err(StartupError::Timeout);
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

async fn wait_for_url(handle: &mut BackendHandle, log_path: &Path) -> Result<String, String> {
    let deadline = Instant::now() + URL_TIMEOUT;
    loop {
        if let Ok(raw) = std::fs::read_to_string(log_path) {
            if let Some(url) = extract_quick_tunnel_url(&raw) {
                return Ok(url);
            }
        }
        if matches!(handle.child.try_wait(), Ok(Some(_))) {
            return Err("cloudflared stopped before creating a Quick Tunnel URL.".into());
        }
        if Instant::now() > deadline {
            return Err("cloudflared did not create a Quick Tunnel URL in time.".into());
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

fn extract_quick_tunnel_url(raw: &str) -> Option<String> {
    raw.split_ascii_whitespace().find_map(|token| {
        let candidate = token.trim_matches(|character: char| {
            !character.is_ascii_alphanumeric() && !matches!(character, ':' | '/' | '.' | '-')
        });
        let host = candidate.strip_prefix("https://")?;
        let label = host.strip_suffix(".trycloudflare.com")?;
        if !label.is_empty()
            && label
                .bytes()
                .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
        {
            Some(candidate.to_string())
        } else {
            None
        }
    })
}

fn cloudflared_path() -> Option<PathBuf> {
    if let Some(path) = known_cloudflared_paths()
        .into_iter()
        .find(|path| path.is_file())
    {
        return Some(path);
    }
    if let Some(path) = std::env::var_os("PATH") {
        for directory in std::env::split_paths(&path) {
            for name in cloudflared_names() {
                let candidate = directory.join(name);
                if candidate.is_file() {
                    return Some(candidate);
                }
            }
        }
    }
    None
}

fn cloudflared_names() -> &'static [&'static str] {
    if cfg!(windows) {
        &["cloudflared.exe"]
    } else {
        &["cloudflared"]
    }
}

fn known_cloudflared_paths() -> Vec<PathBuf> {
    if cfg!(windows) {
        vec![
            PathBuf::from(r"C:\Program Files (x86)\cloudflared\cloudflared.exe"),
            PathBuf::from(r"C:\Program Files\cloudflared\cloudflared.exe"),
        ]
    } else {
        vec![
            PathBuf::from("/opt/homebrew/bin/cloudflared"),
            PathBuf::from("/usr/local/bin/cloudflared"),
            PathBuf::from("/usr/bin/cloudflared"),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_only_strict_trycloudflare_urls() {
        let raw = "INF Your quick Tunnel has been created! Visit it at https://quiet-river-42.trycloudflare.com |";
        assert_eq!(
            extract_quick_tunnel_url(raw).as_deref(),
            Some("https://quiet-river-42.trycloudflare.com")
        );
        assert!(extract_quick_tunnel_url("https://attacker.example").is_none());
        assert!(extract_quick_tunnel_url("https://bad_label.trycloudflare.com").is_none());
    }

    #[test]
    fn remote_access_opt_in_is_explicit_true() {
        let root =
            std::env::temp_dir().join(format!("callosum-quick-tunnel-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let settings = root.join("settings.json");
        std::fs::write(&settings, r#"{"remote_access_enabled":false}"#).unwrap();
        assert!(!remote_access_enabled(&settings));
        std::fs::write(&settings, r#"{"remote_access_enabled":true}"#).unwrap();
        assert!(remote_access_enabled(&settings));
        let _ = std::fs::remove_dir_all(root);
    }

    #[cfg(windows)]
    #[test]
    #[ignore = "requires installed cloudflared and explicit CALLOSUM_TEST_PYTHON"]
    fn live_quick_tunnel_is_gated_fails_closed_and_cleans_up() {
        tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
            .unwrap()
            .block_on(live_quick_tunnel_acceptance());
    }

    #[cfg(windows)]
    async fn live_quick_tunnel_acceptance() {
        let python = PathBuf::from(
            std::env::var_os("CALLOSUM_TEST_PYTHON")
                .expect("set CALLOSUM_TEST_PYTHON to an isolated test-capable Python"),
        );
        let repo_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(3)
            .unwrap()
            .to_path_buf();
        let root =
            std::env::temp_dir().join(format!("callosum-live-quick-tunnel-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("app-data")).unwrap();
        std::fs::create_dir_all(root.join("library")).unwrap();
        let settings_path = root.join("settings.json");
        std::fs::write(&settings_path, r#"{"remote_access_enabled":true}"#).unwrap();
        let paths = ResolvedPaths {
            python_exe: python,
            source_root: repo_root,
            db_url: format!(
                "sqlite:///{}",
                root.join("callosum.sqlite")
                    .to_string_lossy()
                    .replace('\\', "/")
            ),
            library_dir: root.join("library"),
            log_path: root.join("backend.log"),
            port_path: root.join("last-port.txt"),
            app_data_dir: root.join("app-data"),
            settings_path: settings_path.clone(),
            word_https_dir: root.join("word-https"),
        };
        let (mut target, target_port) = spawn_tunnel_target(&paths, "test")
            .map_err(|error| error.detail())
            .unwrap();
        wait_for_tunnel_target(&mut target, target_port)
            .await
            .map_err(|error| error.detail())
            .unwrap();
        let local = format!("http://127.0.0.1:{target_port}");
        assert_eq!(wait_for_local_status(&local, "/health", 200).await, 200);
        assert_eq!(wait_for_local_status(&local, "/settings", 401).await, 401);
        std::fs::write(&settings_path, r#"{"remote_access_enabled":false}"#).unwrap();
        assert_eq!(wait_for_local_status(&local, "/settings", 403).await, 403);
        kill_handle(&mut target);

        std::fs::write(&settings_path, r#"{"remote_access_enabled":true}"#).unwrap();
        let state = QuickTunnelState::default();
        let started = start(&paths, "test", &state).await.unwrap();
        assert!(started.url.unwrap().starts_with("https://"));
        let connector_log =
            std::fs::read_to_string(root.join("app-data/quick-tunnel.log")).unwrap();
        assert!(!connector_log.contains("credentials-file"));
        assert!(!connector_log.contains(".cloudflared"));
        assert!(!stop(&state).running);
        assert!(!status(&state).running);
        let _ = std::fs::remove_dir_all(root);
    }

    #[cfg(windows)]
    async fn wait_for_local_status(base: &str, path: &str, expected: u16) -> u16 {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap();
        let deadline = Instant::now() + Duration::from_secs(10);
        loop {
            let last = match client.get(format!("{base}{path}")).send().await {
                Ok(response) => {
                    if response.status().as_u16() == expected {
                        return expected;
                    }
                    response.status().to_string()
                }
                Err(error) => error.to_string(),
            };
            assert!(
                Instant::now() < deadline,
                "local Quick Tunnel target did not return {expected}; last result: {last}"
            );
            tokio::time::sleep(POLL_INTERVAL).await;
        }
    }
}
