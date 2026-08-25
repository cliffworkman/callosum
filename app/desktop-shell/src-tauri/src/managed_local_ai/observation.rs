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

#[derive(Clone, Default)]
pub(super) struct SharedRuntimeObservation(Arc<Mutex<RuntimeObservation>>);

impl SharedRuntimeObservation {
    pub(super) fn execution(&self) -> Option<ExecutionState> {
        let observation = self.0.lock().expect("runtime observation poisoned");
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
        observe_line(&self.0, line);
    }
}

/// Capture only the startup lines required to prove execution state, then drain both streams to
/// a sink. Runtime output is never written to a terminal, file, descriptor, or application log.
pub(super) fn observe_child_output(child: &mut Child) -> SharedRuntimeObservation {
    let observation = SharedRuntimeObservation::default();
    if let Some(stdout) = child.stdout.take() {
        start_drain(stdout, observation.0.clone());
    }
    if let Some(stderr) = child.stderr.take() {
        start_drain(stderr, observation.0.clone());
    }
    observation
}

fn start_drain<R>(stream: R, observation: Arc<Mutex<RuntimeObservation>>)
where
    R: Read + Send + 'static,
{
    std::thread::spawn(move || {
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
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
            match reader.read_line(&mut line) {
                Ok(0) | Err(_) => return,
                Ok(_) => observe_line(&observation, &line),
            }
        }
    });
}

fn observe_line(observation: &Arc<Mutex<RuntimeObservation>>, line: &str) {
    let lower = line.to_ascii_lowercase();
    let mut state = observation.lock().expect("runtime observation poisoned");
    if lower.contains("ggml_cuda") {
        state.cuda_seen = true;
    }
    if let Some((offloaded, total)) = parse_offload_counts(&lower) {
        state.offloaded_layers = Some(offloaded);
        state.total_layers = Some(total);
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

        let cuda = SharedRuntimeObservation::default();
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
        let observation = SharedRuntimeObservation::default();
        observation.observe_test_line("load_tensors: offloaded 8/25 layers to GPU");
        assert_eq!(observation.execution(), None);
    }
}
