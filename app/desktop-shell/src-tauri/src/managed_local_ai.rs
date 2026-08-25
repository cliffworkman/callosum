//! Developer-only ownership of a local llama.cpp-style server for synthesis Overview.
//!
//! This module owns the child process and secrets. Python receives only a private descriptor path
//! after model readiness and an authenticated inference probe both succeed.

use serde::Serialize;
use std::ffi::OsString;
use std::net::TcpListener;
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
const CONTEXT_TOKENS: u32 = 4096;
const MAX_OUTPUT_TOKENS: u32 = 256;
const READINESS_TIMEOUT: Duration = Duration::from_secs(180);
const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(4);
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
struct DeveloperConfig {
    runtime: PathBuf,
    model: PathBuf,
    declared_build_backend: ExecutionBackend,
    gpu_layers: u32,
    threads: u16,
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
        }))
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
pub async fn start_if_enabled(
    data_dir: &Path,
    state: &ManagedLocalAiState,
) -> Result<Option<PathBuf>, ManagedAiError> {
    let Some(config) = DeveloperConfig::from_environment()? else {
        return Ok(None);
    };
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
    let runtime_observation = observe_child_output(&mut child);
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
        context_tokens: CONTEXT_TOKENS,
        max_output_tokens: MAX_OUTPUT_TOKENS,
        temperature: 0.0,
        seed: 42,
        requested_execution,
        observed_execution: readiness.observed_execution,
        qualification_state: "DEVELOPER_TEST_ONLY",
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
        CONTEXT_TOKENS.to_string().into(),
        "--n-predict".into(),
        MAX_OUTPUT_TOKENS.to_string().into(),
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

fn process_is_running(state: &ManagedLocalAiState) -> Result<bool, ManagedAiError> {
    let mut guard = state.0.lock().expect("managed local AI state poisoned");
    let handle = guard.as_mut().ok_or(ManagedAiError::Exited)?;
    handle
        .child
        .try_wait()
        .map(|status| status.is_none())
        .map_err(|_| ManagedAiError::Exited)
}

fn start_crash_monitor(state: ManagedLocalAiState) {
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_millis(500));
        let exited = {
            let mut guard = state.0.lock().expect("managed local AI state poisoned");
            let Some(handle) = guard.as_mut() else { return };
            matches!(handle.child.try_wait(), Ok(Some(_)) | Err(_))
        };
        if exited {
            if let Some(handle) = state
                .0
                .lock()
                .expect("managed local AI state poisoned")
                .take()
            {
                cleanup_files(&handle);
            }
            return;
        }
    });
}

/// Remove eligibility first, request bounded graceful tree shutdown, then force cleanup.
pub fn shutdown(state: &ManagedLocalAiState) {
    let Some(mut handle) = state
        .0
        .lock()
        .expect("managed local AI state poisoned")
        .take()
    else {
        return;
    };
    cleanup_files(&handle);
    request_graceful_shutdown(&mut handle);
    let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
    while Instant::now() < deadline {
        if matches!(handle.child.try_wait(), Ok(Some(_))) {
            return;
        }
        std::thread::sleep(Duration::from_millis(80));
    }
    force_shutdown(&mut handle);
}

#[cfg(windows)]
fn request_graceful_shutdown(handle: &mut ManagedLocalAiHandle) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = Command::new("taskkill")
        .args(["/PID", &handle.child.id().to_string(), "/T"])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(unix)]
fn request_graceful_shutdown(handle: &mut ManagedLocalAiHandle) {
    unsafe {
        libc::kill(-(handle.child.id() as i32), libc::SIGTERM);
    }
}

#[cfg(windows)]
fn force_shutdown(handle: &mut ManagedLocalAiHandle) {
    let _ = handle.child.kill();
    let _ = handle.child.wait();
}

#[cfg(unix)]
fn force_shutdown(handle: &mut ManagedLocalAiHandle) {
    unsafe {
        libc::kill(-(handle.child.id() as i32), libc::SIGKILL);
    }
    let _ = handle.child.wait();
}

fn cleanup_files(handle: &ManagedLocalAiHandle) {
    remove_private_file(&handle.descriptor_path);
    remove_private_file(&handle.token_path);
}

fn confine_process(
    child: Child,
    descriptor_path: PathBuf,
    token_path: PathBuf,
) -> Result<ManagedLocalAiHandle, ManagedAiError> {
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        let mut child = child;
        let job = win32job::Job::create().map_err(|_| ManagedAiError::Spawn)?;
        let mut info = job
            .query_extended_limit_info()
            .map_err(|_| ManagedAiError::Spawn)?;
        info.limit_kill_on_job_close();
        job.set_extended_limit_info(&info)
            .map_err(|_| ManagedAiError::Spawn)?;
        if job.assign_process(child.as_raw_handle() as isize).is_err() {
            let _ = child.kill();
            return Err(ManagedAiError::Spawn);
        }
        Ok(ManagedLocalAiHandle {
            child,
            descriptor_path,
            token_path,
            _job: job,
        })
    }
    #[cfg(not(windows))]
    {
        Ok(ManagedLocalAiHandle {
            child,
            descriptor_path,
            token_path,
        })
    }
}

fn pick_free_port() -> Result<u16, ManagedAiError> {
    let listener = TcpListener::bind((HOST, 0))
        .map_err(|_| ManagedAiError::Io("loopback port allocation failed"))?;
    Ok(listener
        .local_addr()
        .map_err(|_| ManagedAiError::Io("loopback port allocation failed"))?
        .port())
}

#[cfg(test)]
mod tests;
