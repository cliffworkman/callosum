use super::*;
use std::io::{Read, Write};
use std::net::TcpListener;

static ENV_LOCK: Mutex<()> = Mutex::new(());

fn test_dir(label: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!("callosum-{label}-{}", random_token().unwrap()));
    std::fs::create_dir_all(&path).unwrap();
    path
}

fn assert_no_content_stdout(stdout: &[u8], context: &str) {
    let text = String::from_utf8_lossy(stdout);
    let cleaned = text
        .lines()
        .filter(|line| {
            *line
                != "warning: The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead."
        })
        .collect::<Vec<_>>()
        .join("\n");
    assert!(
        cleaned.trim().is_empty(),
        "{context} emitted stdout: {text}"
    );
}

fn fake_config(root: &Path) -> DeveloperConfig {
    let runtime = root.join(if cfg!(windows) {
        "llama-server.exe"
    } else {
        "llama-server"
    });
    let model = root.join("instrument.gguf");
    std::fs::write(&runtime, b"runtime").unwrap();
    std::fs::write(&model, b"model").unwrap();
    DeveloperConfig {
        runtime,
        model,
        declared_build_backend: ExecutionBackend::Cpu,
        gpu_layers: 0,
        threads: 4,
        context_tokens: QUALIFICATION_CONTEXT_TOKENS,
        max_output_tokens: OVERVIEW_OUTPUT_TOKENS,
        qualification_state: "DEVELOPER_TEST_ONLY",
        expected_model_digest: None,
        expected_launcher_digest: None,
        expected_bundle_digest: None,
    }
}

#[test]
fn enabled_runtime_requires_existing_runtime_and_gguf_paths() {
    let _guard = ENV_LOCK.lock().unwrap();
    let previous = [ENABLE_ENV, RUNTIME_ENV, MODEL_ENV].map(|name| (name, std::env::var_os(name)));
    std::env::set_var(ENABLE_ENV, "1");
    std::env::remove_var(RUNTIME_ENV);
    std::env::remove_var(MODEL_ENV);
    assert!(matches!(
        DeveloperConfig::from_environment(),
        Err(ManagedAiError::InvalidConfig(_))
    ));

    let root = test_dir("invalid-config");
    let not_gguf = root.join("model.txt");
    std::fs::write(&not_gguf, b"not a model").unwrap();
    std::env::set_var(RUNTIME_ENV, std::env::current_exe().unwrap());
    std::env::set_var(MODEL_ENV, &not_gguf);
    assert!(matches!(
        DeveloperConfig::from_environment(),
        Err(ManagedAiError::InvalidConfig(_))
    ));
    for (name, value) in previous {
        match value {
            Some(value) => std::env::set_var(name, value),
            None => std::env::remove_var(name),
        }
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn developer_configuration_requires_truthful_supported_build_backend() {
    let _guard = ENV_LOCK.lock().unwrap();
    let names = [
        ENABLE_ENV,
        RUNTIME_ENV,
        MODEL_ENV,
        BUILD_BACKEND_ENV,
        GPU_LAYERS_ENV,
    ];
    let previous = names.map(|name| (name, std::env::var_os(name)));
    let root = test_dir("backend-config");
    let model = root.join("instrument.gguf");
    std::fs::write(&model, b"model").unwrap();
    std::env::set_var(ENABLE_ENV, "1");
    std::env::set_var(RUNTIME_ENV, std::env::current_exe().unwrap());
    std::env::set_var(MODEL_ENV, &model);
    std::env::set_var(BUILD_BACKEND_ENV, "vulkan");
    assert!(matches!(
        DeveloperConfig::from_environment(),
        Err(ManagedAiError::InvalidConfig(_))
    ));
    std::env::set_var(BUILD_BACKEND_ENV, "cpu");
    std::env::set_var(GPU_LAYERS_ENV, "8");
    assert!(matches!(
        DeveloperConfig::from_environment(),
        Err(ManagedAiError::InvalidConfig(_))
    ));
    for (name, value) in previous {
        match value {
            Some(value) => std::env::set_var(name, value),
            None => std::env::remove_var(name),
        }
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn server_argv_is_strict_loopback_authenticated_and_shell_free() {
    let root = test_dir("argv");
    let config = fake_config(&root);
    let token_path = root.join("auth-token");
    let command = build_command(&config, 32123, &token_path);
    assert_eq!(command.get_current_dir(), config.runtime.parent());
    let args = server_args(&config, 32123, &token_path);
    let values = args
        .iter()
        .map(|value| value.to_string_lossy())
        .collect::<Vec<_>>();

    assert!(values
        .windows(2)
        .any(|pair| pair == ["--host", "127.0.0.1"]));
    assert!(!values
        .iter()
        .any(|value| value == "0.0.0.0" || value == "localhost"));
    assert!(values
        .windows(2)
        .any(|pair| pair[0] == "--api-key-file" && pair[1] == token_path.to_string_lossy()));
    assert!(values
        .windows(2)
        .any(|pair| pair == ["--alias", MODEL_ALIAS]));
    assert!(values.contains(&"--no-webui".into()));
    assert!(values
        .windows(2)
        .any(|pair| pair == ["--log-verbosity", "4"]));
    assert!(values
        .windows(2)
        .any(|pair| pair == ["--log-colors", "off"]));
    assert!(values.contains(&"--offline".into()));
    assert!(values
        .windows(2)
        .any(|pair| pair == ["--n-gpu-layers", "0"]));
    assert!(!values.iter().any(|value| value.contains("Bearer")
        || value.len() == 64 && value.chars().all(|c| c.is_ascii_hexdigit())));
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn server_argv_always_carries_exact_offload_value() {
    let root = test_dir("offload-argv");
    let token_path = root.join("auth-token");
    for layers in [0, 8, 25] {
        let mut config = fake_config(&root);
        config.gpu_layers = layers;
        config.declared_build_backend = if layers == 0 {
            ExecutionBackend::Cpu
        } else {
            ExecutionBackend::Cuda
        };
        let values = server_args(&config, 32123, &token_path)
            .iter()
            .map(|value| value.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        assert!(values
            .windows(2)
            .any(|pair| pair == ["--n-gpu-layers", &layers.to_string()]));
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn server_argv_uses_the_exact_configuration_context() {
    let root = test_dir("context-argv");
    let token_path = root.join("auth-token");
    for context_tokens in [QUALIFICATION_CONTEXT_TOKENS, PREVIEW_CONTEXT_TOKENS] {
        let mut config = fake_config(&root);
        config.context_tokens = context_tokens;
        let values = server_args(&config, 32123, &token_path)
            .iter()
            .map(|value| value.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        assert!(values
            .windows(2)
            .any(|pair| pair == ["--ctx-size", &context_tokens.to_string()]));
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn tokens_are_strong_random_and_private_descriptor_has_no_secret_or_model_path() {
    let first = random_token().unwrap();
    let second = random_token().unwrap();
    assert_eq!(first.len(), 64);
    assert_ne!(first, second);
    assert!(first.chars().all(|value| value.is_ascii_hexdigit()));

    let descriptor = TargetDescriptor {
        schema_version: 2,
        target_id: "llama-cpp-a-b".into(),
        kind: "device_local",
        endpoint: "http://127.0.0.1:1234".into(),
        wire_format: "chat_completions",
        credential_ref: "private/auth-token".into(),
        model_alias: MODEL_ALIAS,
        runtime_family: "llama.cpp",
        runtime_version: "version 1".into(),
        runtime_binary_digest: "a".repeat(64),
        runtime_bundle_manifest_digest: "d".repeat(64),
        declared_build_backend: ExecutionBackend::Cpu,
        model_artifact_digest: "b".repeat(64),
        chat_template_digest: Some("c".repeat(64)),
        context_tokens: QUALIFICATION_CONTEXT_TOKENS,
        max_output_tokens: OVERVIEW_OUTPUT_TOKENS,
        temperature: 0.0,
        seed: 42,
        requested_execution: ExecutionState {
            backend: ExecutionBackend::Cpu,
            gpu_layers: 0,
        },
        observed_execution: ExecutionState {
            backend: ExecutionBackend::Cpu,
            gpu_layers: 0,
        },
        qualification_state: "DEVELOPER_TEST_ONLY",
    };
    let encoded = serde_json::to_string(&descriptor).unwrap();
    assert!(!encoded.contains(&first));
    assert!(!encoded.contains("instrument.gguf"));
    assert!(!encoded.contains("llama-server.exe"));
}

#[test]
fn private_files_are_created_without_overwrite() {
    let root = test_dir("private");
    let path = root.join("auth-token");
    write_private_file(&path, b"first").unwrap();
    assert!(write_private_file(&path, b"second").is_err());
    assert_eq!(std::fs::read(&path).unwrap(), b"first");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        assert_eq!(
            std::fs::metadata(&path).unwrap().permissions().mode() & 0o777,
            0o600
        );
    }
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn readiness_probe_requires_alias_auth_and_valid_chat_shape() {
    tokio::runtime::Runtime::new().unwrap().block_on(async {
        let (endpoint, server) = fake_readiness_server("correct-token", false);
        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let mut result = authenticated_probe(&client, &endpoint, "correct-token").await;
        for _ in 0..10 {
            if result.is_ok() {
                break;
            }
            tokio::time::sleep(Duration::from_millis(50)).await;
            result = authenticated_probe(&client, &endpoint, "correct-token").await;
        }
        let digest = result.unwrap();
        assert_eq!(digest, Some(digest_bytes("template-v1")));
        server.join().unwrap();

        let (endpoint, server) = fake_readiness_server("correct-token", false);
        assert!(authenticated_probe(&client, &endpoint, "wrong-token")
            .await
            .is_err());
        server.join().unwrap();

        let (endpoint, server) = fake_readiness_server("correct-token", true);
        assert!(authenticated_probe(&client, &endpoint, "correct-token")
            .await
            .is_err());
        server.join().unwrap();
    });
}

fn fake_readiness_server(
    expected_token: &'static str,
    malformed_chat: bool,
) -> (String, std::thread::JoinHandle<()>) {
    let listener = TcpListener::bind((HOST, 0)).unwrap();
    listener.set_nonblocking(true).unwrap();
    let endpoint = format!("http://{}:{}", HOST, listener.local_addr().unwrap().port());
    let server = std::thread::spawn(move || {
        let deadline = Instant::now() + Duration::from_secs(15);
        while Instant::now() < deadline {
            let (mut stream, _) = match listener.accept() {
                Ok(value) => value,
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    std::thread::sleep(Duration::from_millis(10));
                    continue;
                }
                Err(error) => panic!("fake readiness listener failed: {error}"),
            };
            let request = read_http_request(&mut stream);
            let lower = request.to_ascii_lowercase();
            let authenticated = lower.contains(&format!("authorization: bearer {expected_token}"));
            let (status, body, terminal) = if lower.starts_with("get /health ") {
                (200, r#"{"status":"ok"}"#.into(), false)
            } else if lower.starts_with("get /v1/models ") {
                (
                    200,
                    format!(r#"{{"data":[{{"id":"{MODEL_ALIAS}"}}]}}"#),
                    false,
                )
            } else if lower.starts_with("get /props ") && authenticated {
                (200, r#"{"chat_template":"template-v1"}"#.into(), false)
            } else if lower.starts_with("post /v1/chat/completions ") && authenticated {
                let body = if malformed_chat {
                    r#"{"choices":[]}"#.into()
                } else {
                    r#"{"choices":[{"message":{"content":"O"}}]}"#.into()
                };
                (200, body, true)
            } else {
                (401, r#"{"error":"unauthorized"}"#.into(), true)
            };
            let reason = if status == 200 { "OK" } else { "Unauthorized" };
            let _ = write!(
                stream,
                "HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                body.len()
            );
            if terminal {
                return;
            }
        }
        panic!("fake readiness server timed out before a terminal request");
    });
    (endpoint, server)
}

#[test]
fn execution_verification_accepts_exact_state_and_rejects_mismatch() {
    let cases = [
        (
            ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0,
            },
            ["load_tensors: offloaded 0/25 layers to GPU", ""],
            true,
        ),
        (
            ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0,
            },
            [
                "ggml_cuda_init: found 1 CUDA devices",
                "load_tensors: offloaded 8/25 layers to GPU",
            ],
            false,
        ),
        (
            ExecutionState {
                backend: ExecutionBackend::Cuda,
                gpu_layers: 8,
            },
            [
                "ggml_cuda_init: found 1 CUDA devices",
                "load_tensors: offloaded 8/25 layers to GPU",
            ],
            true,
        ),
        (
            ExecutionState {
                backend: ExecutionBackend::Cuda,
                gpu_layers: 8,
            },
            [
                "ggml_cuda_init: found 1 CUDA devices",
                "load_tensors: offloaded 16/25 layers to GPU",
            ],
            false,
        ),
        (
            ExecutionState {
                backend: ExecutionBackend::Cuda,
                gpu_layers: 25,
            },
            [
                "ggml_cuda_init: found 1 CUDA devices",
                "load_tensors: offloaded 25/25 layers to GPU",
            ],
            true,
        ),
    ];
    for (requested, lines, accepted) in cases {
        let observation = SharedRuntimeObservation::for_runtime_version(
            "version 0.1.2-dev (build 10516 commit b95502ba9)",
        );
        for line in lines {
            observation.observe_test_line(line);
        }
        let result = verify_execution(requested, observation.execution());
        if accepted {
            assert_eq!(result.unwrap(), requested);
        } else {
            assert!(matches!(result, Err(ManagedAiError::ExecutionMismatch)));
        }
    }
    assert!(matches!(
        verify_execution(
            ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0
            },
            None
        ),
        Err(ManagedAiError::ExecutionUnverified)
    ));
}

fn read_http_request(stream: &mut std::net::TcpStream) -> String {
    stream
        .set_read_timeout(Some(Duration::from_secs(2)))
        .unwrap();
    let mut bytes = Vec::new();
    let mut buffer = [0_u8; 1024];
    loop {
        let read = stream.read(&mut buffer).unwrap_or(0);
        if read == 0 {
            break;
        }
        bytes.extend_from_slice(&buffer[..read]);
        if let Some(header_end) = bytes.windows(4).position(|window| window == b"\r\n\r\n") {
            let headers = String::from_utf8_lossy(&bytes[..header_end]);
            let content_length = headers
                .lines()
                .find_map(|line| {
                    let (name, value) = line.split_once(':')?;
                    name.eq_ignore_ascii_case("content-length")
                        .then(|| value.trim().parse::<usize>().ok())
                        .flatten()
                })
                .unwrap_or(0);
            if bytes.len() >= header_end + 4 + content_length {
                break;
            }
        }
    }
    String::from_utf8_lossy(&bytes).into_owned()
}

#[test]
fn shutdown_removes_descriptor_and_token_and_terminates_child() {
    let root = test_dir("shutdown");
    let descriptor_path = root.join("target.json");
    let token_path = root.join("auth-token");
    std::fs::write(&descriptor_path, b"descriptor").unwrap();
    std::fs::write(&token_path, b"token").unwrap();
    let child = long_running_child();
    let pid = child.id();
    let handle = confine_process(child, descriptor_path.clone(), token_path.clone()).unwrap();
    let state = ManagedLocalAiState::default();
    *state.0.lock().unwrap() = Some(handle);

    shutdown(&state);

    assert!(!descriptor_path.exists());
    assert!(!token_path.exists());
    assert!(!process_exists(pid));
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn crash_monitor_invalidates_descriptor_and_token() {
    let root = test_dir("crash-monitor");
    let descriptor_path = root.join("target.json");
    let token_path = root.join("auth-token");
    std::fs::write(&descriptor_path, b"descriptor").unwrap();
    std::fs::write(&token_path, b"token").unwrap();
    let handle = confine_process(
        long_running_child(),
        descriptor_path.clone(),
        token_path.clone(),
    )
    .unwrap();
    let state = ManagedLocalAiState::default();
    *state.0.lock().unwrap() = Some(handle);
    start_crash_monitor(state.clone());
    state
        .0
        .lock()
        .unwrap()
        .as_mut()
        .unwrap()
        .child
        .kill()
        .unwrap();
    let deadline = Instant::now() + Duration::from_secs(3);
    while (descriptor_path.exists() || token_path.exists() || state.0.lock().unwrap().is_some())
        && Instant::now() < deadline
    {
        std::thread::sleep(Duration::from_millis(50));
    }
    assert!(!descriptor_path.exists());
    assert!(!token_path.exists());
    assert!(state.0.lock().unwrap().is_none());
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn forced_shutdown_fallback_terminates_child() {
    let root = test_dir("forced-shutdown");
    let descriptor_path = root.join("target.json");
    let token_path = root.join("auth-token");
    let child = long_running_child();
    let pid = child.id();
    let mut handle = confine_process(child, descriptor_path, token_path).unwrap();
    force_shutdown(&mut handle);
    assert!(!process_exists(pid));
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn short_readiness_deadline_fails_closed_and_cleans_up() {
    let root = test_dir("readiness-timeout");
    let descriptor_path = root.join("target.json");
    let token_path = root.join("auth-token");
    std::fs::write(&descriptor_path, b"descriptor").unwrap();
    std::fs::write(&token_path, b"token").unwrap();
    let handle = confine_process(
        long_running_child(),
        descriptor_path.clone(),
        token_path.clone(),
    )
    .unwrap();
    let state = ManagedLocalAiState::default();
    *state.0.lock().unwrap() = Some(handle);
    let unused_port = pick_free_port().unwrap();
    let result = tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(wait_until_ready(
            &state,
            &format!("http://{HOST}:{unused_port}"),
            "unused-token",
            ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0,
            },
            &SharedRuntimeObservation::default(),
            Duration::from_millis(80),
        ));
    assert!(matches!(result, Err(ManagedAiError::ReadinessTimeout)));
    shutdown(&state);
    assert!(!descriptor_path.exists());
    assert!(!token_path.exists());
    std::fs::remove_dir_all(root).unwrap();
}

#[cfg(windows)]
fn long_running_child() -> Child {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Start-Sleep -Seconds 30",
        ])
        .creation_flags(CREATE_NO_WINDOW)
        .spawn()
        .unwrap()
}

#[cfg(unix)]
fn long_running_child() -> Child {
    use std::os::unix::process::CommandExt;
    let mut command = Command::new("sleep");
    command.arg("30").process_group(0).spawn().unwrap()
}

#[cfg(windows)]
fn process_exists(pid: u32) -> bool {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let output = Command::new("tasklist")
        .args(["/FI", &format!("PID eq {pid}"), "/FO", "CSV", "/NH"])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .unwrap();
    String::from_utf8_lossy(&output.stdout).contains(&pid.to_string())
}

#[cfg(unix)]
fn process_exists(pid: u32) -> bool {
    unsafe { libc::kill(pid as i32, 0) == 0 }
}

#[test]
#[ignore = "requires developer-supplied llama-server, GGUF, and Python paths"]
fn live_managed_runtime_routes_existing_python_overview_path() {
    let python =
        std::env::var_os("CALLOSUM_LOCAL_AI_PYTHON").expect("set CALLOSUM_LOCAL_AI_PYTHON");
    let root = test_dir("live");
    let state = ManagedLocalAiState::default();
    let descriptor = tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(start_if_enabled(&root, &state))
        .unwrap()
        .expect("CALLOSUM_LOCAL_AI_ENABLED must be 1");
    let payload: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&descriptor).unwrap()).unwrap();
    let requested_layers = std::env::var(GPU_LAYERS_ENV)
        .unwrap_or_else(|_| "0".into())
        .parse::<u32>()
        .unwrap();
    let requested_backend = if requested_layers == 0 { "cpu" } else { "cuda" };
    assert_eq!(payload["schema_version"], 2);
    assert_eq!(
        payload["declared_build_backend"],
        std::env::var(BUILD_BACKEND_ENV).unwrap()
    );
    assert_eq!(payload["requested_execution"]["backend"], requested_backend);
    assert_eq!(
        payload["requested_execution"]["gpu_layers"],
        requested_layers
    );
    assert_eq!(
        payload["observed_execution"],
        payload["requested_execution"]
    );
    assert!(payload["runtime_binary_digest"].as_str().is_some());
    assert!(payload["runtime_bundle_manifest_digest"].as_str().is_some());
    eprintln!(
        "managed-local acceptance identity: {}",
        serde_json::json!({
            "runtime_family": payload["runtime_family"],
            "runtime_version": payload["runtime_version"],
            "launcher_sha256": payload["runtime_binary_digest"],
            "bundle_manifest_sha256": payload["runtime_bundle_manifest_digest"],
            "declared_build_backend": payload["declared_build_backend"],
            "requested_execution": payload["requested_execution"],
            "observed_execution": payload["observed_execution"],
            "model_artifact_sha256": payload["model_artifact_digest"],
            "chat_template_sha256": payload["chat_template_digest"],
        })
    );
    let endpoint = payload["endpoint"].as_str().unwrap();
    let credential_path = PathBuf::from(payload["credential_ref"].as_str().unwrap());
    let token = std::fs::read_to_string(&credential_path).unwrap();
    let model_name = std::env::var_os(MODEL_ENV)
        .and_then(|path| PathBuf::from(path).file_name().map(|name| name.to_owned()))
        .unwrap();
    let model_name = model_name.to_string_lossy();

    tokio::runtime::Runtime::new().unwrap().block_on(async {
        let client = reqwest::Client::builder().no_proxy().build().unwrap();
        let models = client
            .get(format!("{endpoint}/v1/models"))
            .send()
            .await
            .unwrap()
            .text()
            .await
            .unwrap();
        assert!(models.contains(MODEL_ALIAS));
        assert!(!models.contains(model_name.as_ref()));
        let body = serde_json::json!({
            "model": MODEL_ALIAS,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "max_tokens": 1
        });
        assert_eq!(
            client
                .post(format!("{endpoint}/v1/chat/completions"))
                .json(&body)
                .send()
                .await
                .unwrap()
                .status(),
            reqwest::StatusCode::UNAUTHORIZED
        );
        assert_eq!(
            client
                .post(format!("{endpoint}/v1/chat/completions"))
                .bearer_auth("wrong-token")
                .json(&body)
                .send()
                .await
                .unwrap()
                .status(),
            reqwest::StatusCode::UNAUTHORIZED
        );
        assert!(client
            .post(format!("{endpoint}/v1/chat/completions"))
            .bearer_auth(&token)
            .json(&body)
            .send()
            .await
            .unwrap()
            .status()
            .is_success());
    });

    let source_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .expect("desktop crate has repository root")
        .to_path_buf();
    let python_code = r#"
from app.backend.llm.managed_local import resolve_managed_local_overview
from app.backend.provider_runtime import ProviderClientRuntime
from integrations.gemini.overview import GeminiOverviewGenerator
from integrations.gemini.overview import _parse_overview_response, _prompt
import os
import json
import urllib.request
assert os.getenv("CALLOSUM_LOCAL_AI_RUNTIME") is None
assert os.getenv("CALLOSUM_LOCAL_AI_MODEL") is None
assert os.getenv("CALLOSUM_LOCAL_AI_BUILD_BACKEND") is None
claims = [
    "The intervention group reported a lower mean score than the comparison group.",
    "The study used a randomized design with blinded outcome assessment.",
    "Participants completed the same outcome measure at baseline and follow-up.",
    "The report described attrition separately for each study group.",
    "The analysis included a prespecified sensitivity check.",
]
runtime = ProviderClientRuntime()
if os.getenv("CALLOSUM_PHASE35_DIRECT_OVERVIEW") == "1":
    descriptor = json.load(open(os.environ["CALLOSUM_MANAGED_LOCAL_AI_DESCRIPTOR"], encoding="utf-8"))
    token = open(descriptor["credential_ref"], encoding="ascii").read()
    body = json.dumps({
        "model": descriptor["model_alias"],
        "messages": [{"role": "user", "content": _prompt(claims)}],
        "max_tokens": 256,
        "temperature": 0,
        "seed": 42,
    }).encode("utf-8")
    request = urllib.request.Request(
        descriptor["endpoint"] + "/v1/chat/completions",
        data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = json.load(response)["choices"][0]["message"]["content"]
    items = _parse_overview_response(content)
else:
    resolution = resolve_managed_local_overview(runtime)
    assert resolution.enabled and resolution.config is not None
    items = GeminiOverviewGenerator(config=resolution.config).generate(
        verified_claims=claims,
        scope_ref={"scope_type": "developer-poc"},
    )
assert items and all(item.claim_indices for item in items)
runtime.close()
"#;
    if std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_SKIP_SMOKE").is_none() {
        let output = Command::new(&python)
            .arg("-c")
            .arg(python_code)
            .current_dir(&source_root)
            .env(ENABLE_ENV, "1")
            .env(DESCRIPTOR_ENV, &descriptor)
            .env_remove(RUNTIME_ENV)
            .env_remove(MODEL_ENV)
            .env_remove(GPU_LAYERS_ENV)
            .env_remove(BUILD_BACKEND_ENV)
            .env_remove(THREADS_ENV)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "production Python Overview path failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert_no_content_stdout(&output.stdout, "production Python Overview path");
    }

    // Optional Phase-4 scientific qualification stage. This remains an ignored developer test:
    // the managed owner publishes the readiness-gated descriptor, while the reusable Python
    // harness exercises the unchanged production prompt/complete()/parser/reference path.
    if let (Some(candidate), Some(stage), Some(repetitions), Some(qualification_output)) = (
        std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_CANDIDATE"),
        std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_STAGE"),
        std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_REPETITIONS"),
        std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_OUTPUT"),
    ) {
        let qualification_runner = std::env::var_os("CALLOSUM_OVERVIEW_QUALIFICATION_RUNNER")
            .map(PathBuf::from)
            .unwrap_or_else(|| source_root.join("tools/qualification/overview_battery.py"));
        let qualification = Command::new(&python)
            .arg(qualification_runner)
            .arg("execute")
            .arg("--candidate")
            .arg(candidate)
            .arg("--stage")
            .arg(stage)
            .arg("--repetitions")
            .arg(repetitions)
            .arg("--output")
            .arg(&qualification_output)
            .current_dir(&source_root)
            .env(ENABLE_ENV, "1")
            .env(DESCRIPTOR_ENV, &descriptor)
            .env_remove(RUNTIME_ENV)
            .env_remove(MODEL_ENV)
            .env_remove(GPU_LAYERS_ENV)
            .env_remove(BUILD_BACKEND_ENV)
            .env_remove(THREADS_ENV)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .unwrap();
        assert!(
            qualification.status.success(),
            "Overview qualification stage failed: {}",
            String::from_utf8_lossy(&qualification.stderr)
        );
        assert_no_content_stdout(&qualification.stdout, "Overview qualification stage");
        assert!(Path::new(&qualification_output).is_file());
    }
    assert!(std::fs::read_dir(root.join("managed-local-ai"))
        .unwrap()
        .all(|entry| matches!(
            entry.unwrap().file_name().to_str(),
            Some("target.json" | "auth-token")
        )));

    shutdown(&state);
    assert!(!descriptor.exists());
    assert!(!credential_path.exists());
    std::fs::remove_dir_all(root).unwrap();
}

#[cfg(windows)]
#[test]
#[ignore = "downloads the pinned 1.1 GB preview model into CALLOSUM_LOCAL_AI_LIVE_INSTALL_DIR"]
fn live_pinned_preview_installs_and_runs_three_generation_contracts() {
    let root = PathBuf::from(
        std::env::var_os("CALLOSUM_LOCAL_AI_LIVE_INSTALL_DIR")
            .expect("set CALLOSUM_LOCAL_AI_LIVE_INSTALL_DIR outside the repository"),
    );
    std::fs::create_dir_all(&root).unwrap();
    let python =
        std::env::var_os("CALLOSUM_LOCAL_AI_PYTHON").unwrap_or_else(|| OsString::from("python"));
    let state = ManagedLocalAiState::default();
    let install_state = LocalAiInstallState::default();
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let status = runtime
        .block_on(setup_and_start(&root, &state, &install_state))
        .expect("pinned preview setup and readiness");
    assert_eq!(status.state, "ready");

    let descriptor = root.join("managed-local-ai").join("target.json");
    let payload: serde_json::Value =
        serde_json::from_slice(&std::fs::read(&descriptor).unwrap()).unwrap();
    assert_eq!(payload["qualification_state"], "LOCAL_AI_PREVIEW");
    assert_eq!(payload["model_artifact_digest"], install::MODEL_SHA256);
    assert_eq!(payload["context_tokens"], PREVIEW_CONTEXT_TOKENS);
    assert_eq!(payload["max_output_tokens"], PREVIEW_OUTPUT_TOKENS);
    assert_eq!(payload["requested_execution"]["gpu_layers"], 0);
    assert_eq!(
        payload["observed_execution"],
        payload["requested_execution"]
    );

    let source_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(Path::parent)
        .and_then(Path::parent)
        .expect("desktop crate has repository root")
        .to_path_buf();
    let python_code = r#"
from dataclasses import replace
from app.backend.llm.managed_local import (
    load_preview_target, managed_summary_generator, with_managed_output_contract,
)
from app.backend.llm.providers import requires_egress
from app.backend.provider_runtime import ProviderClientRuntime
from app.backend.summarization.generators import SourceChunk
from integrations.gemini.help_assistant import GeminiHelpAssistant
from integrations.gemini.overview import GeminiOverviewGenerator

runtime = ProviderClientRuntime()
config = load_preview_target().config(runtime)
assert config.provider == "managed_local"
assert not requires_egress(config)
claims = [
    "The randomized study found a lower mean score in the intervention group.",
    "A second study found no difference between groups.",
    "Both studies enrolled adults from one city.",
    "Outcome assessors were blinded in the randomized study.",
]
overview_config = with_managed_output_contract(config, "synthesis_overview")
overview = GeminiOverviewGenerator(config=overview_config).generate(verified_claims=claims, scope_ref={})
assert overview and all(item.claim_indices for item in overview)
chunks = [
    SourceChunk(chunk_id=i, paper_id=i, attachment_id=i, text=text, page_start=1,
                page_end=1, chunk_version="smoke")
    for i, text in enumerate(claims, 1)
]
summary = managed_summary_generator(config).generate(
    source_chunks=chunks, scope_ref={"scope_type": "papers", "paper_ids": [1, 2, 3, 4]}
)
assert summary and all(item.citations for item in summary)
help_answer = GeminiHelpAssistant(config=replace(config, help_assistant_enabled=True)).answer(
    message="How do I create a synthesis?", history=[]
)
assert help_answer.answer
runtime.close()
"#;
    let output = Command::new(python)
        .arg("-c")
        .arg(python_code)
        .current_dir(source_root)
        .env("CALLOSUM_APP_DATA_DIR", &root)
        .env_remove(ENABLE_ENV)
        .env_remove(DESCRIPTOR_ENV)
        .env_remove("GOOGLE_API_KEY")
        .env_remove("OPENAI_API_KEY")
        .env_remove("ANTHROPIC_API_KEY")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "preview Python pathways failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_no_content_stdout(&output.stdout, "preview Python pathways");

    shutdown(&state);
    assert!(!descriptor.exists());
    assert!(install::installed_paths(&root).unwrap().is_some());
}

#[test]
#[ignore = "requires CALLOSUM_LOCAL_AI_RUNTIME and CALLOSUM_LOCAL_AI_COMPARE_RUNTIME"]
fn live_runtime_bundles_distinguish_identical_launchers() {
    let first = std::env::var_os(RUNTIME_ENV).expect("set CALLOSUM_LOCAL_AI_RUNTIME");
    let second = std::env::var_os("CALLOSUM_LOCAL_AI_COMPARE_RUNTIME")
        .expect("set CALLOSUM_LOCAL_AI_COMPARE_RUNTIME");
    let first = runtime_bundle_identity(Path::new(&first)).unwrap();
    let second = runtime_bundle_identity(Path::new(&second)).unwrap();
    eprintln!(
        "launcher={} first_bundle={} second_bundle={}",
        first.launcher_digest, first.manifest_digest, second.manifest_digest
    );
    assert_eq!(first.launcher_digest, second.launcher_digest);
    assert_ne!(first.manifest_digest, second.manifest_digest);
}

#[test]
#[ignore = "requires a developer-supplied CUDA llama-server and GGUF"]
fn live_runtime_execution_mismatch_is_not_published() {
    let config = DeveloperConfig::from_environment()
        .unwrap()
        .expect("enable the developer runtime");
    assert!(config.gpu_layers > 0);
    let root = test_dir("live-mismatch");
    let private_dir = root.join("managed-local-ai");
    prepare_private_dir(&private_dir).unwrap();
    let descriptor_path = private_dir.join("target.json");
    let token_path = private_dir.join("auth-token");
    let token = random_token().unwrap();
    write_private_file(&token_path, token.as_bytes()).unwrap();
    let port = pick_free_port().unwrap();
    let mut child = build_command(&config, port, &token_path).spawn().unwrap();
    let version = runtime_version(&config.runtime).unwrap();
    let observation = observe_child_output(&mut child, &version);
    let handle = confine_process(child, descriptor_path.clone(), token_path.clone()).unwrap();
    let state = ManagedLocalAiState::default();
    *state.0.lock().unwrap() = Some(handle);
    let result = tokio::runtime::Runtime::new()
        .unwrap()
        .block_on(wait_until_ready(
            &state,
            &format!("http://{HOST}:{port}"),
            &token,
            ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0,
            },
            &observation,
            Duration::from_secs(30),
        ));
    assert!(matches!(result, Err(ManagedAiError::ExecutionMismatch)));
    shutdown(&state);
    assert!(!descriptor_path.exists());
    assert!(!token_path.exists());
    std::fs::remove_dir_all(root).unwrap();
}
