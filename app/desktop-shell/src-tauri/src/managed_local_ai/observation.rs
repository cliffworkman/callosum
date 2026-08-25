//! Bounded, non-persistent observation of llama.cpp startup execution state.

use super::{ExecutionBackend, ExecutionState};
use std::io::{BufRead, BufReader, Read};
use std::process::Child;
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct RuntimeObservation {
    cuda_seen: bool,
    offloaded_layers: Option<u32>,
    total_layers: Option<u32>,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
enum ObservationProfile {
    #[default]
    Unsupported,
    LlamaCppB10516,
}

impl ObservationProfile {
    fn from_runtime_version(runtime_version: &str) -> Self {
        let version = runtime_version.to_ascii_lowercase();
        if version.contains("build 10516") && version.contains("commit b95502ba9") {
            Self::LlamaCppB10516
        } else {
            Self::Unsupported
        }
    }
}

#[derive(Clone)]
pub(super) struct SharedRuntimeObservation {
    state: Arc<Mutex<RuntimeObservation>>,
    profile: ObservationProfile,
}

impl Default for SharedRuntimeObservation {
    fn default() -> Self {
        Self::for_runtime_version("unknown")
    }
}

impl SharedRuntimeObservation {
    pub(super) fn for_runtime_version(runtime_version: &str) -> Self {
        Self {
            state: Arc::new(Mutex::new(RuntimeObservation::default())),
            profile: ObservationProfile::from_runtime_version(runtime_version),
        }
    }

    pub(super) fn execution(&self) -> Option<ExecutionState> {
        let observation = self.state.lock().expect("runtime observation poisoned");
        let gpu_layers = observation.offloaded_layers?;
        let total_layers = observation.total_layers?;
        if total_layers == 0 || gpu_layers > total_layers {
            return None;
        }
        let backend = if gpu_layers == 0 {
            ExecutionBackend::Cpu
        } else if observation.cuda_seen {
            ExecutionBackend::Cuda
        } else {
            return None;
        };
        Some(ExecutionState {
            backend,
            gpu_layers,
        })
    }

    #[cfg(test)]
    pub(super) fn observe_test_line(&self, line: &str) {
        observe_line(&self.state, self.profile, line);
    }
}

/// Capture only the startup lines required to prove execution state, then drain both streams to
/// a sink. Runtime output is never written to a terminal, file, descriptor, or application log.
pub(super) fn observe_child_output(
    child: &mut Child,
    runtime_version: &str,
) -> SharedRuntimeObservation {
    let observation = SharedRuntimeObservation::for_runtime_version(runtime_version);
    if let Some(stdout) = child.stdout.take() {
        start_drain(stdout, observation.state.clone(), observation.profile);
    }
    if let Some(stderr) = child.stderr.take() {
        start_drain(stderr, observation.state.clone(), observation.profile);
    }
    observation
}

fn start_drain<R>(
    stream: R,
    observation: Arc<Mutex<RuntimeObservation>>,
    profile: ObservationProfile,
) where
    R: Read + Send + 'static,
{
    std::thread::spawn(move || drain_stream(stream, observation, profile));
}

fn drain_stream<R>(
    stream: R,
    observation: Arc<Mutex<RuntimeObservation>>,
    profile: ObservationProfile,
) where
    R: Read,
{
    let mut reader = BufReader::new(stream);
    let mut line = Vec::new();
    loop {
        let complete = {
            let state = observation.lock().expect("runtime observation poisoned");
            matches!(state.offloaded_layers, Some(0))
                || state.offloaded_layers.is_some() && state.cuda_seen
        };
        if complete {
            let _ = std::io::copy(&mut reader, &mut std::io::sink());
            return;
        }
        line.clear();
        match reader.read_until(b'\n', &mut line) {
            Ok(0) | Err(_) => return,
            Ok(_) => observe_line(&observation, profile, &String::from_utf8_lossy(&line)),
        }
    }
}

fn observe_line(
    observation: &Arc<Mutex<RuntimeObservation>>,
    profile: ObservationProfile,
    line: &str,
) {
    let lower = line.to_ascii_lowercase();
    let mut state = observation.lock().expect("runtime observation poisoned");
    if profile == ObservationProfile::LlamaCppB10516 && is_b10516_cuda_marker(&lower) {
        state.cuda_seen = true;
    }
    if let Some((offloaded, total)) = parse_offload_counts(&lower) {
        state.offloaded_layers = Some(offloaded);
        state.total_layers = Some(total);
    }
}

fn is_b10516_cuda_marker(line: &str) -> bool {
    let line = b10516_log_payload(line);
    if let Some(device_count) = line
        .strip_prefix("ggml_cuda_init: found ")
        .and_then(|value| value.strip_suffix(" cuda devices"))
    {
        return !device_count.is_empty() && device_count.chars().all(|ch| ch.is_ascii_digit());
    }
    let Some(device) = line.strip_prefix("llama_prepare_model_devices: using device cuda") else {
        return false;
    };
    let digit_count = device.chars().take_while(|ch| ch.is_ascii_digit()).count();
    digit_count > 0 && device[digit_count..].starts_with(" (")
}

fn b10516_log_payload(line: &str) -> &str {
    let line = line.trim();
    let mut fields = line.splitn(3, char::is_whitespace);
    let Some(timestamp) = fields.next() else {
        return line;
    };
    let Some(level) = fields.next() else {
        return line;
    };
    let Some(payload) = fields.next() else {
        return line;
    };
    let timestamp_parts = timestamp.split('.').collect::<Vec<_>>();
    if timestamp_parts.len() == 4
        && timestamp_parts
            .iter()
            .all(|part| !part.is_empty() && part.chars().all(|ch| ch.is_ascii_digit()))
        && level == "i"
    {
        payload.trim_start()
    } else {
        line
    }
}

fn parse_offload_counts(line: &str) -> Option<(u32, u32)> {
    let after = line.split_once("offloaded ")?.1;
    let counts = after.split_once(" layers to gpu")?.0.trim();
    let (offloaded, total) = counts.split_once('/')?;
    Some((offloaded.trim().parse().ok()?, total.trim().parse().ok()?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    const PINNED_VERSION: &str = "version 0.1.2-dev (build 10516 commit b95502ba9)";

    #[test]
    fn parses_cpu_and_cuda_execution_without_retaining_log_text() {
        let cpu = SharedRuntimeObservation::default();
        cpu.observe_test_line("load_tensors: offloaded 0/25 layers to GPU");
        assert_eq!(
            cpu.execution(),
            Some(ExecutionState {
                backend: ExecutionBackend::Cpu,
                gpu_layers: 0,
            })
        );

        let cuda = SharedRuntimeObservation::for_runtime_version(PINNED_VERSION);
        cuda.observe_test_line("ggml_cuda_init: found 1 CUDA devices");
        cuda.observe_test_line("load_tensors: offloaded 8/25 layers to GPU");
        assert_eq!(
            cuda.execution(),
            Some(ExecutionState {
                backend: ExecutionBackend::Cuda,
                gpu_layers: 8,
            })
        );
    }

    #[test]
    fn gpu_offload_without_a_supported_backend_marker_is_unverified() {
        let observation = SharedRuntimeObservation::for_runtime_version(PINNED_VERSION);
        observation.observe_test_line("load_tensors: offloaded 8/25 layers to GPU");
        assert_eq!(observation.execution(), None);
    }

    #[test]
    fn parses_rebuilt_b10516_cuda_device_marker_for_partial_and_full_offload() {
        for layers in [8, 25] {
            let observation = SharedRuntimeObservation::for_runtime_version(PINNED_VERSION);
            observation.observe_test_line(
                "0.00.355.320 I llama_prepare_model_devices: using device CUDA0 (NVIDIA GeForce RTX 3050)",
            );
            observation.observe_test_line(&format!(
                "load_tensors: offloaded {layers}/25 layers to GPU"
            ));
            assert_eq!(
                observation.execution(),
                Some(ExecutionState {
                    backend: ExecutionBackend::Cuda,
                    gpu_layers: layers,
                })
            );
        }
    }

    #[test]
    fn rejects_unknown_versions_and_ambiguous_cuda_text() {
        for (version, marker) in [
            (
                "version 0.1.2-dev (build 10517 commit future)",
                "llama_prepare_model_devices: using device CUDA0 (GPU)",
            ),
            (PINNED_VERSION, "CUDA backend initialized"),
            (
                PINNED_VERSION,
                "llama_prepare_model_devices: using device CUDA (GPU)",
            ),
            (
                PINNED_VERSION,
                "not-a-b10516-prefix I llama_prepare_model_devices: using device CUDA0 (GPU)",
            ),
        ] {
            let observation = SharedRuntimeObservation::for_runtime_version(version);
            observation.observe_test_line(marker);
            observation.observe_test_line("load_tensors: offloaded 8/25 layers to GPU");
            assert_eq!(observation.execution(), None);
        }
    }

    #[test]
    fn invalid_utf8_before_execution_evidence_does_not_abort_observation() {
        let observation = SharedRuntimeObservation::for_runtime_version(PINNED_VERSION);
        let mut trace = b"model metadata: invalid ".to_vec();
        trace.extend_from_slice(&[0xff, b'\n']);
        trace.extend_from_slice(
            b"0.00.191.881 I llama_prepare_model_devices: using device CUDA0 (GPU)\n",
        );
        trace.extend_from_slice(b"0.00.307.266 I load_tensors: offloaded 17/17 layers to GPU\n");
        drain_stream(
            Cursor::new(trace),
            observation.state.clone(),
            observation.profile,
        );
        assert_eq!(
            observation.execution(),
            Some(ExecutionState {
                backend: ExecutionBackend::Cuda,
                gpu_layers: 17,
            })
        );
    }
}
