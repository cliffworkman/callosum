//! Callosum ownership of its local llama.cpp-style generation provider.
//!
//! This module owns the child process and secrets. Python receives only a private descriptor path
//! after model readiness and an authenticated inference probe both succeed.

use serde::Serialize;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

mod files;
use files::{
    digest_bytes, digest_file, prepare_private_dir, random_token, remove_private_file,
    runtime_bundle_identity, runtime_version, write_private_file,
};
mod observation;
use observation::{observe_child_output, SharedRuntimeObservation};
mod install;
pub use install::LocalAiInstallState;
#[cfg(target_os = "macos")]
mod install_macos;
mod preview;
pub use preview::{local_ai_status, setup_and_start, start_for_startup, LocalAiStatus};
mod process;
#[cfg(test)]
use process::force_shutdown;
pub use process::shutdown;
use process::{confine_process, pick_free_port, process_is_running, start_crash_monitor};

const ENABLE_ENV: &str = "CALLOSUM_LOCAL_AI_ENABLED";
const RUNTIME_ENV: &str = "CALLOSUM_LOCAL_AI_RUNTIME";
const MODEL_ENV: &str = "CALLOSUM_LOCAL_AI_MODEL";
const GPU_LAYERS_ENV: &str = "CALLOSUM_LOCAL_AI_GPU_LAYERS";
const BUILD_BACKEND_ENV: &str = "CALLOSUM_LOCAL_AI_BUILD_BACKEND";
const THREADS_ENV: &str = "CALLOSUM_LOCAL_AI_THREADS";
pub const DESCRIPTOR_ENV: &str = "CALLOSUM_MANAGED_LOCAL_AI_DESCRIPTOR";
pub const OWNER_ONLY_ENV: [&str; 5] = [
    RUNTIME_ENV,
    MODEL_ENV,
    GPU_LAYERS_ENV,
    BUILD_BACKEND_ENV,
    THREADS_ENV,
];
const HOST: &str = "127.0.0.1";
const MODEL_ALIAS: &str = "callosum-managed-local";
const QUALIFICATION_CONTEXT_TOKENS: u32 = 4096;
const PREVIEW_CONTEXT_TOKENS: u32 = 12_288;
const OVERVIEW_OUTPUT_TOKENS: u32 = 256;
const PREVIEW_OUTPUT_TOKENS: u32 = 2048;
const READINESS_TIMEOUT: Duration = Duration::from_secs(180);
const POLL_INTERVAL: Duration = Duration::from_millis(300);

#[derive(Debug)]
pub enum ManagedAiError {
    InvalidConfig(&'static str),
    Io(&'static str),
    Spawn,
    Exited,
    ReadinessTimeout,
    ReadinessProbe,
    ExecutionUnverified,
    ExecutionMismatch,
}

impl ManagedAiError {
    pub fn detail(&self) -> &'static str {
        match self {
            Self::InvalidConfig(message) => message,
            Self::Io(message) => message,
            Self::Spawn => "the managed local AI runtime could not start",
            Self::Exited => "the managed local AI runtime exited before it became ready",
            Self::ReadinessTimeout => "the managed local AI model did not become ready in time",
            Self::ReadinessProbe => {
                "the managed local AI endpoint failed its authenticated readiness probe"
            }
            Self::ExecutionUnverified => {
                "the managed local AI runtime did not expose verifiable execution state"
            }
            Self::ExecutionMismatch => {
                "the managed local AI runtime execution state did not match its request"
            }
        }
    }

    pub fn code(&self) -> &'static str {
        match self {
            Self::InvalidConfig(message) if message.contains("architecture") => {
                "LOCAL_AI_UNSUPPORTED_ARCHITECTURE"
            }
            Self::InvalidConfig(message) if message.contains("not been set up") => {
                "LOCAL_AI_MODEL_NOT_INSTALLED"
            }
            Self::InvalidConfig(_) => "LOCAL_AI_CONFIGURATION_INVALID",
            Self::Io(message)
                if message.contains("identity mismatch") || message.contains("checksum") =>
            {
                "LOCAL_AI_INTEGRITY_CHECK_FAILED"
            }
            Self::Io(message) if message.contains("download") => "LOCAL_AI_DOWNLOAD_FAILED",
            Self::Io(_) => "LOCAL_AI_RUNTIME_INSTALL_FAILED",
            Self::Spawn => "LOCAL_AI_RUNTIME_NOT_STARTED",
            Self::Exited => "LOCAL_AI_RUNTIME_EXITED",
            Self::ReadinessTimeout => "LOCAL_AI_RUNTIME_TIMEOUT",
            Self::ReadinessProbe => "LOCAL_AI_RUNTIME_UNREACHABLE",
            Self::ExecutionUnverified => "LOCAL_AI_EXECUTION_UNVERIFIED",
            Self::ExecutionMismatch => "LOCAL_AI_EXECUTION_MISMATCH",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
enum ExecutionBackend {
    Cpu,
    Cuda,
}

impl ExecutionBackend {
    fn from_environment() -> Result<Self, ManagedAiError> {
        match std::env::var(BUILD_BACKEND_ENV).ok().as_deref() {
            Some("cpu") => Ok(Self::Cpu),
            Some("cuda") => Ok(Self::Cuda),
            _ => Err(ManagedAiError::InvalidConfig(
                "CALLOSUM_LOCAL_AI_BUILD_BACKEND must be cpu or cuda",
            )),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
struct ExecutionState {
    backend: ExecutionBackend,
    gpu_layers: u32,
}

#[derive(Debug, Clone)]
pub(super) struct DeveloperConfig {
    runtime: PathBuf,
    model: PathBuf,
    declared_build_backend: ExecutionBackend,
    gpu_layers: u32,
    threads: u16,
    context_tokens: u32,
    max_output_tokens: u32,
    qualification_state: &'static str,
    expected_model_digest: Option<&'static str>,
    expected_launcher_digest: Option<&'static str>,
    expected_bundle_digest: Option<&'static str>,
}

impl DeveloperConfig {
    fn from_environment() -> Result<Option<Self>, ManagedAiError> {
        if std::env::var(ENABLE_ENV).ok().as_deref() != Some("1") {
            return Ok(None);
        }
        let runtime = required_path(RUNTIME_ENV, false)?;
        let model = required_path(MODEL_ENV, true)?;
        let declared_build_backend = ExecutionBackend::from_environment()?;
        let gpu_layers = parse_i32_env(GPU_LAYERS_ENV, 0, 0, 999)? as u32;
        let threads = parse_i32_env(THREADS_ENV, 4, 1, 128)? as u16;
        if gpu_layers > 0 && declared_build_backend != ExecutionBackend::Cuda {
            return Err(ManagedAiError::InvalidConfig(
                "GPU layers require a cuda managed runtime build",
            ));
        }
        Ok(Some(Self {
            runtime,
            model,
            declared_build_backend,
            gpu_layers,
            threads,
            context_tokens: QUALIFICATION_CONTEXT_TOKENS,
            max_output_tokens: OVERVIEW_OUTPUT_TOKENS,
            qualification_state: "DEVELOPER_TEST_ONLY",
            expected_model_digest: None,
            expected_launcher_digest: None,
            expected_bundle_digest: None,
        }))
    }

    fn production(paths: install::InstalledPaths) -> Self {
        Self {
            runtime: paths.runtime,
            model: paths.model,
            declared_build_backend: ExecutionBackend::Cpu,
            gpu_layers: 0,
            threads: 4,
            context_tokens: PREVIEW_CONTEXT_TOKENS,
            max_output_tokens: PREVIEW_OUTPUT_TOKENS,
            qualification_state: "LOCAL_AI_PREVIEW",
            expected_model_digest: Some(install::MODEL_SHA256),
            #[cfg(any(windows, target_os = "macos"))]
            expected_launcher_digest: Some(install::RUNTIME_LAUNCHER_SHA256),
            #[cfg(not(any(windows, target_os = "macos")))]
            expected_launcher_digest: None,
            #[cfg(any(windows, target_os = "macos"))]
            expected_bundle_digest: Some(install::RUNTIME_BUNDLE_SHA256),
            #[cfg(not(any(windows, target_os = "macos")))]
            expected_bundle_digest: None,
        }
    }

    fn requested_execution(&self) -> ExecutionState {
        ExecutionState {
            backend: if self.gpu_layers == 0 {
                ExecutionBackend::Cpu
            } else {
                self.declared_build_backend
            },
            gpu_layers: self.gpu_layers,
        }
    }
}

#[derive(Serialize)]
struct TargetDescriptor {
    schema_version: u8,
    target_id: String,
    kind: &'static str,
    endpoint: String,
    wire_format: &'static str,
    credential_ref: String,
    model_alias: &'static str,
    runtime_family: &'static str,
    runtime_version: String,
    runtime_binary_digest: String,
    runtime_bundle_manifest_digest: String,
    declared_build_backend: ExecutionBackend,
    model_artifact_digest: String,
    chat_template_digest: Option<String>,
    context_tokens: u32,
    max_output_tokens: u32,
    temperature: f32,
    seed: u32,
    requested_execution: ExecutionState,
    observed_execution: ExecutionState,
    qualification_state: &'static str,
}

struct ReadinessEvidence {
    chat_template_digest: Option<String>,
    observed_execution: ExecutionState,
}

pub struct ManagedLocalAiHandle {
    child: Child,
    descriptor_path: PathBuf,
    token_path: PathBuf,
    #[cfg(windows)]
    _job: win32job::Job,
}

#[derive(Clone, Default)]
pub struct ManagedLocalAiState(Arc<Mutex<Option<ManagedLocalAiHandle>>>);

/// Start the developer runtime when explicitly enabled. Any failure is fail-closed for Overview but
/// does not prevent the primary Callosum backend from starting.
#[cfg(test)]
pub async fn start_if_enabled(
    data_dir: &Path,
    state: &ManagedLocalAiState,
) -> Result<Option<PathBuf>, ManagedAiError> {
    let Some(config) = DeveloperConfig::from_environment()? else {
        return Ok(None);
    };
    start_config(data_dir, state, config).await
}

pub(super) async fn start_config(
    data_dir: &Path,
    state: &ManagedLocalAiState,
    config: DeveloperConfig,
) -> Result<Option<PathBuf>, ManagedAiError> {
    shutdown(state);
    let private_dir = data_dir.join("managed-local-ai");
    prepare_private_dir(&private_dir)?;
    let token_path = private_dir.join("auth-token");
    let descriptor_path = private_dir.join("target.json");
    remove_private_file(&token_path);
    remove_private_file(&descriptor_path);

    let port = pick_free_port()?;
    let runtime_identity = runtime_bundle_identity(&config.runtime)?;
    let model_digest = digest_file(&config.model)?;
    if config
        .expected_model_digest
        .is_some_and(|expected| expected != model_digest)
        || config
            .expected_launcher_digest
            .is_some_and(|expected| expected != runtime_identity.launcher_digest)
        || config
            .expected_bundle_digest
            .is_some_and(|expected| expected != runtime_identity.manifest_digest)
    {
        return Err(ManagedAiError::Io(
            "managed Local AI installation identity mismatch",
        ));
    }
    let runtime_version = runtime_version(&config.runtime)?;
    let token = random_token()?;
    write_private_file(&token_path, token.as_bytes())?;
    let mut command = build_command(&config, port, &token_path);
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(_) => {
            remove_private_file(&token_path);
            return Err(ManagedAiError::Spawn);
        }
    };
    let runtime_observation = observe_child_output(&mut child, &runtime_version);
    let handle = match confine_process(child, descriptor_path.clone(), token_path.clone()) {
        Ok(handle) => handle,
        Err(error) => {
            remove_private_file(&token_path);
            return Err(error);
        }
    };
    *state.0.lock().expect("managed local AI state poisoned") = Some(handle);

    let endpoint = format!("http://{HOST}:{port}");
    let requested_execution = config.requested_execution();
    let readiness = match wait_until_ready(
        state,
        &endpoint,
        &token,
        requested_execution,
        &runtime_observation,
        READINESS_TIMEOUT,
    )
    .await
    {
        Ok(value) => value,
        Err(error) => {
            shutdown(state);
            return Err(error);
        }
    };
    let descriptor = TargetDescriptor {
        schema_version: 2,
        target_id: format!(
            "llama-cpp-{}-{}",
            &runtime_identity.manifest_digest[..12],
            &model_digest[..12]
        ),
        kind: "device_local",
        endpoint,
        wire_format: "chat_completions",
        credential_ref: token_path.to_string_lossy().into_owned(),
        model_alias: MODEL_ALIAS,
        runtime_family: "llama.cpp",
        runtime_version,
        runtime_binary_digest: runtime_identity.launcher_digest,
        runtime_bundle_manifest_digest: runtime_identity.manifest_digest,
        declared_build_backend: config.declared_build_backend,
        model_artifact_digest: model_digest,
        chat_template_digest: readiness.chat_template_digest,
        context_tokens: config.context_tokens,
        max_output_tokens: config.max_output_tokens,
        temperature: 0.0,
        seed: 42,
        requested_execution,
        observed_execution: readiness.observed_execution,
        qualification_state: config.qualification_state,
    };
    let bytes = match serde_json::to_vec_pretty(&descriptor) {
        Ok(bytes) => bytes,
        Err(_) => {
            shutdown(state);
            return Err(ManagedAiError::Io("descriptor encoding failed"));
        }
    };
    if let Err(error) = write_private_file(&descriptor_path, &bytes) {
        shutdown(state);
        return Err(error);
    }
    start_crash_monitor(state.clone());
    Ok(Some(descriptor_path))
}

fn required_path(name: &'static str, gguf: bool) -> Result<PathBuf, ManagedAiError> {
    let raw = std::env::var_os(name).ok_or(ManagedAiError::InvalidConfig(match name {
        RUNTIME_ENV => "CALLOSUM_LOCAL_AI_RUNTIME is required when local AI is enabled",
        _ => "CALLOSUM_LOCAL_AI_MODEL is required when local AI is enabled",
    }))?;
    let path = std::fs::canonicalize(raw)
        .map_err(|_| ManagedAiError::InvalidConfig("managed local AI path is invalid"))?;
    if !path.is_file() {
        return Err(ManagedAiError::InvalidConfig(
            "managed local AI path must name a file",
        ));
    }
    if gguf
        && path
            .extension()
            .and_then(|value| value.to_str())
            .map(str::to_ascii_lowercase)
            .as_deref()
            != Some("gguf")
    {
        return Err(ManagedAiError::InvalidConfig(
            "managed local AI model must be a GGUF file",
        ));
    }
    Ok(path)
}

fn parse_i32_env(
    name: &'static str,
    default: i32,
    minimum: i32,
    maximum: i32,
) -> Result<i32, ManagedAiError> {
    let Some(raw) = std::env::var(name).ok() else {
        return Ok(default);
    };
    let value = raw.parse::<i32>().map_err(|_| {
        ManagedAiError::InvalidConfig("managed local AI numeric setting is invalid")
    })?;
    if !(minimum..=maximum).contains(&value) {
        return Err(ManagedAiError::InvalidConfig(
            "managed local AI numeric setting is out of range",
        ));
    }
    Ok(value)
}

fn build_command(config: &DeveloperConfig, port: u16, token_path: &Path) -> Command {
    let mut command = Command::new(&config.runtime);
    command
        // Resolve adjacent shared libraries from the allowlisted runtime bundle. Self-contained
        // Linux llama.cpp packages require this; the same working directory is harmless elsewhere.
        .current_dir(
            config
                .runtime
                .parent()
                .expect("validated runtime file has a parent directory"),
        )
        .args(server_args(config, port, token_path))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    command
}

fn server_args(config: &DeveloperConfig, port: u16, token_path: &Path) -> Vec<OsString> {
    let args = vec![
        "--model".into(),
        config.model.as_os_str().to_owned(),
        "--host".into(),
        HOST.into(),
        "--port".into(),
        port.to_string().into(),
        "--ctx-size".into(),
        config.context_tokens.to_string().into(),
        "--n-predict".into(),
        config.max_output_tokens.to_string().into(),
        "--threads".into(),
        config.threads.to_string().into(),
        "--temp".into(),
        "0".into(),
        "--seed".into(),
        "42".into(),
        "--api-key-file".into(),
        token_path.as_os_str().to_owned(),
        "--alias".into(),
        MODEL_ALIAS.into(),
        "--no-webui".into(),
        "--log-verbosity".into(),
        // b10516 reports actual offload at trace level. The owner retains only that numeric
        // startup observation; all other child-stream content is discarded as it is read.
        "4".into(),
        "--log-colors".into(),
        "off".into(),
        "--offline".into(),
        "--n-gpu-layers".into(),
        config.gpu_layers.to_string().into(),
    ];
    args
}

async fn wait_until_ready(
    state: &ManagedLocalAiState,
    endpoint: &str,
    token: &str,
    requested_execution: ExecutionState,
    runtime_observation: &SharedRuntimeObservation,
    timeout: Duration,
) -> Result<ReadinessEvidence, ManagedAiError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(4))
        .no_proxy()
        .build()
        .map_err(|_| ManagedAiError::ReadinessProbe)?;
    let deadline = Instant::now() + timeout;
    let mut endpoint_verified = false;
    loop {
        if !process_is_running(state)? {
            return Err(ManagedAiError::Exited);
        }
        if let Ok(response) = client.get(format!("{endpoint}/health")).send().await {
            if response.status().is_success() {
                if let Ok(template) = authenticated_probe(&client, endpoint, token).await {
                    endpoint_verified = true;
                    match verify_execution(requested_execution, runtime_observation.execution()) {
                        Ok(observed_execution) => {
                            return Ok(ReadinessEvidence {
                                chat_template_digest: template,
                                observed_execution,
                            });
                        }
                        Err(ManagedAiError::ExecutionMismatch) => {
                            return Err(ManagedAiError::ExecutionMismatch);
                        }
                        Err(ManagedAiError::ExecutionUnverified) => {}
                        Err(error) => return Err(error),
                    }
                }
            }
        }
        if Instant::now() >= deadline {
            return if endpoint_verified && runtime_observation.execution().is_none() {
                Err(ManagedAiError::ExecutionUnverified)
            } else {
                Err(ManagedAiError::ReadinessTimeout)
            };
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

fn verify_execution(
    requested: ExecutionState,
    observed: Option<ExecutionState>,
) -> Result<ExecutionState, ManagedAiError> {
    let observed = observed.ok_or(ManagedAiError::ExecutionUnverified)?;
    if observed != requested {
        return Err(ManagedAiError::ExecutionMismatch);
    }
    Ok(observed)
}

async fn authenticated_probe(
    client: &reqwest::Client,
    endpoint: &str,
    token: &str,
) -> Result<Option<String>, ManagedAiError> {
    let models: serde_json::Value = client
        .get(format!("{endpoint}/v1/models"))
        .send()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .error_for_status()
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .json()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?;
    let alias_present = models["data"].as_array().is_some_and(|items| {
        items
            .iter()
            .any(|item| item["id"].as_str() == Some(MODEL_ALIAS))
    });
    if !alias_present {
        return Err(ManagedAiError::ReadinessProbe);
    }
    let props: serde_json::Value = client
        .get(format!("{endpoint}/props"))
        .bearer_auth(token)
        .send()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .error_for_status()
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .json()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?;
    let template_digest = props["chat_template"].as_str().map(digest_bytes);
    let response: serde_json::Value = client
        .post(format!("{endpoint}/v1/chat/completions"))
        .bearer_auth(token)
        .json(&serde_json::json!({
            "model": MODEL_ALIAS,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 1,
            "temperature": 0,
            "seed": 42
        }))
        .send()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .error_for_status()
        .map_err(|_| ManagedAiError::ReadinessProbe)?
        .json()
        .await
        .map_err(|_| ManagedAiError::ReadinessProbe)?;
    if !response["choices"][0]["message"]["content"].is_string() {
        return Err(ManagedAiError::ReadinessProbe);
    }
    Ok(template_digest)
}

#[cfg(test)]
mod tests;
