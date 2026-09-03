//! Pinned platform acquisition for the Local AI Preview.
//!
//! This is deliberately not a model catalog. It installs one exact publisher-owned GGUF and one
//! exact upstream llama.cpp CPU bundle, verifies both before promotion, and exposes no arbitrary URL
//! or path input.

use super::files::{digest_file, prepare_private_dir, runtime_bundle_identity};
use super::ManagedAiError;
use serde::Serialize;
use sha2::{Digest, Sha256};
#[cfg(windows)]
use std::fs::File;
#[cfg(any(windows, target_os = "macos"))]
use std::fs::OpenOptions;
#[cfg(windows)]
use std::io::BufReader;
#[cfg(any(windows, target_os = "macos"))]
use std::io::{Read, Write};
#[cfg(windows)]
use std::path::Component;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Instant;

pub(super) const MODEL_SHA256: &str =
    "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e";
pub(super) const MODEL_BYTES: u64 = 1_117_320_736;
pub(super) const MODEL_FILENAME: &str = "qwen2.5-1.5b-instruct-q4_k_m.gguf";
pub(super) const MODEL_ID: &str = "Qwen2.5-1.5B-Instruct Q4_K_M";
pub(super) const MODEL_REVISION: &str = "91cad51170dc346986eccefdc2dd33a9da36ead9";
const MODEL_URL: &str = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true";

#[cfg(windows)]
const RUNTIME_ARCHIVE_URL: &str = "https://github.com/ggml-org/llama.cpp/releases/download/b10516/llama-b10516-bin-win-cpu-x64.zip";
#[cfg(windows)]
const RUNTIME_ARCHIVE_SHA256: &str =
    "fbbbc55e0eb2e1b07f9dcb9488616c98ed47d9003b90e15e7c8c7812c4307cd3";
#[cfg(windows)]
const RUNTIME_ARCHIVE_BYTES: u64 = 18_506_923;
#[cfg(windows)]
pub(super) const RUNTIME_LAUNCHER_SHA256: &str =
    "5a3cbd5613c45ef2d53d3afc6734fd9e67229c0066c2415626ddc7c18901d36c";
#[cfg(windows)]
pub(super) const RUNTIME_BUNDLE_SHA256: &str =
    "7748201a13dd4e2269a97a8144aa02fc5a0325e10bb777518241ce95e721366c";

#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
const RUNTIME_ARCHIVE_URL: &str = "https://github.com/ggml-org/llama.cpp/releases/download/b10516/llama-b10516-bin-macos-arm64.tar.gz";
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
const RUNTIME_ARCHIVE_SHA256: &str =
    "ee3324327d621026ae80c24031670e65fa62a0b23a3a027dbe2f65f240affd30";
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
const RUNTIME_ARCHIVE_BYTES: u64 = 11_089_823;
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
pub(super) const RUNTIME_LAUNCHER_SHA256: &str =
    "d0878274b8d6bd3c8ea26a78eb66cd1ffd943d007c62b9dff31c8aa99922d713";
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
pub(super) const RUNTIME_BUNDLE_SHA256: &str =
    "3517f73521fc59ad58f7e0f5697f88a324271a39e5b0dded8e08b5db29bbbdcb";

#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
const RUNTIME_ARCHIVE_URL: &str = "https://github.com/ggml-org/llama.cpp/releases/download/b10516/llama-b10516-bin-macos-x64.tar.gz";
#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
const RUNTIME_ARCHIVE_SHA256: &str =
    "b7adecf7bd2cde577ddabee8357a72409165d8104f43b4acee9f1b98cc9c447a";
#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
const RUNTIME_ARCHIVE_BYTES: u64 = 11_395_897;
#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
pub(super) const RUNTIME_LAUNCHER_SHA256: &str =
    "f3136584b712d052374aa14765bea077721dc886af647228483ce79e2d838964";
#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
pub(super) const RUNTIME_BUNDLE_SHA256: &str =
    "9621e3a085f91d8c3091540c80684cde76dd637862fa0e07910744a8f63534f3";

const INSTALL_DIR: &str = "managed-local-ai-install";
#[cfg(windows)]
const RUNTIME_DIR: &str = "llama-b10516-win-cpu-x64";
#[cfg(all(target_os = "macos", target_arch = "aarch64"))]
pub(super) const RUNTIME_DIR: &str = "llama-b10516-macos-arm64";
#[cfg(all(target_os = "macos", target_arch = "x86_64"))]
pub(super) const RUNTIME_DIR: &str = "llama-b10516-macos-x64";
#[cfg(windows)]
const RUNTIME_LAUNCHER: &str = "llama-server.exe";
#[cfg(target_os = "macos")]
const RUNTIME_LAUNCHER: &str = "llama-server";
#[cfg(windows)]
const RUNTIME_PARTIAL: &str = "runtime.zip.partial";
#[cfg(target_os = "macos")]
const RUNTIME_PARTIAL: &str = "runtime.tar.gz.partial";
const RECEIPT_FILENAME: &str = "install.json";
const DOWNLOAD_BUFFER_BYTES: usize = 64 * 1024;

#[derive(Clone, Default)]
pub struct LocalAiInstallState(Arc<Mutex<InstallProgress>>);

#[derive(Clone, Default)]
struct InstallProgress {
    stage: Option<&'static str>,
    detail: Option<&'static str>,
    downloaded_bytes: Option<u64>,
    total_bytes: Option<u64>,
    download_started: Option<Instant>,
    error_code: Option<&'static str>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) struct InstallProgressSnapshot {
    pub(super) stage: Option<&'static str>,
    pub(super) detail: Option<&'static str>,
    pub(super) downloaded_bytes: Option<u64>,
    pub(super) total_bytes: Option<u64>,
    pub(super) eta_seconds: Option<u64>,
    pub(super) error_code: Option<&'static str>,
}

#[derive(Debug, Clone)]
pub(super) struct InstalledPaths {
    pub(super) runtime: PathBuf,
    pub(super) model: PathBuf,
}

#[derive(Debug, Serialize)]
struct InstallReceipt<'a> {
    schema_version: u8,
    model_id: &'a str,
    model_revision: &'a str,
    model_sha256: &'a str,
    model_bytes: u64,
    model_source: &'a str,
    model_license: &'a str,
    runtime_family: &'a str,
    runtime_version: &'a str,
    runtime_archive_sha256: &'a str,
    runtime_launcher_sha256: &'a str,
    runtime_bundle_manifest_sha256: &'a str,
    runtime_source: &'a str,
    runtime_license: &'a str,
    declared_build_backend: &'a str,
}

impl LocalAiInstallState {
    pub(super) fn set(&self, stage: Option<&'static str>, detail: Option<&'static str>) {
        *self.0.lock().expect("local AI install state poisoned") = InstallProgress {
            stage,
            detail,
            ..InstallProgress::default()
        };
    }

    pub(super) fn set_error(&self, error: &ManagedAiError) {
        *self.0.lock().expect("local AI install state poisoned") = InstallProgress {
            detail: Some(error.detail()),
            error_code: Some(error.code()),
            ..InstallProgress::default()
        };
    }

    fn begin_download(&self, stage: &'static str, total_bytes: u64) {
        *self.0.lock().expect("local AI install state poisoned") = InstallProgress {
            stage: Some(stage),
            downloaded_bytes: Some(0),
            total_bytes: Some(total_bytes),
            download_started: Some(Instant::now()),
            ..InstallProgress::default()
        };
    }

    fn record_downloaded(&self, downloaded_bytes: u64) {
        let mut progress = self.0.lock().expect("local AI install state poisoned");
        progress.downloaded_bytes = Some(downloaded_bytes);
    }

    pub(super) fn snapshot(&self) -> InstallProgressSnapshot {
        let progress = self.0.lock().expect("local AI install state poisoned");
        let eta_seconds = match (
            progress.downloaded_bytes,
            progress.total_bytes,
            progress.download_started,
        ) {
            (Some(current), Some(total), Some(started)) if current > 0 && current < total => {
                let elapsed = started.elapsed().as_secs_f64();
                (elapsed >= 0.5).then(|| {
                    ((total - current) as f64 * elapsed / current as f64)
                        .ceil()
                        .min(u64::MAX as f64) as u64
                })
            }
            (Some(current), Some(total), _) if current >= total => Some(0),
            _ => None,
        };
        InstallProgressSnapshot {
            stage: progress.stage,
            detail: progress.detail,
            downloaded_bytes: progress.downloaded_bytes,
            total_bytes: progress.total_bytes,
            eta_seconds,
            error_code: progress.error_code,
        }
    }
}

pub(super) fn install_root(data_dir: &Path) -> PathBuf {
    data_dir.join(INSTALL_DIR)
}

pub(super) fn installed_paths(data_dir: &Path) -> Result<Option<InstalledPaths>, ManagedAiError> {
    #[cfg(not(any(windows, target_os = "macos")))]
    {
        let _ = data_dir;
        return Ok(None);
    }
    #[cfg(any(windows, target_os = "macos"))]
    {
        let root = install_root(data_dir);
        let runtime = root.join(RUNTIME_DIR).join(RUNTIME_LAUNCHER);
        let model = root.join(MODEL_FILENAME);
        let receipt = root.join(RECEIPT_FILENAME);
        if !runtime.is_file() || !model.is_file() || !receipt.is_file() {
            return Ok(None);
        }
        if model.metadata().map(|meta| meta.len()).unwrap_or(0) != MODEL_BYTES {
            return Ok(None);
        }
        Ok(Some(InstalledPaths { runtime, model }))
    }
}

#[cfg(any(windows, target_os = "macos"))]
pub(super) fn install_platform(
    data_dir: &Path,
    progress: &LocalAiInstallState,
) -> Result<InstalledPaths, ManagedAiError> {
    let root = install_root(data_dir);
    prepare_private_dir(&root)?;
    let runtime_archive = root.join(RUNTIME_PARTIAL);
    let model_partial = root.join(format!("{MODEL_FILENAME}.partial"));

    progress.begin_download("downloading_runtime", RUNTIME_ARCHIVE_BYTES);
    download_exact(
        RUNTIME_ARCHIVE_URL,
        &runtime_archive,
        RUNTIME_ARCHIVE_BYTES,
        RUNTIME_ARCHIVE_SHA256,
        progress,
    )?;
    progress.set(Some("preparing_runtime"), None);
    #[cfg(windows)]
    extract_runtime_windows(&root, &runtime_archive)?;
    #[cfg(target_os = "macos")]
    super::install_macos::extract_runtime(&root, &runtime_archive)?;
    let _ = std::fs::remove_file(&runtime_archive);

    progress.begin_download("downloading_model", MODEL_BYTES);
    download_exact(
        MODEL_URL,
        &model_partial,
        MODEL_BYTES,
        MODEL_SHA256,
        progress,
    )?;
    progress.set(Some("verifying"), None);
    let model = root.join(MODEL_FILENAME);
    replace_file(&model_partial, &model)?;

    let paths = InstalledPaths {
        runtime: root.join(RUNTIME_DIR).join(RUNTIME_LAUNCHER),
        model,
    };
    verify_install(&paths)?;
    write_receipt(&root)?;
    progress.set(None, None);
    Ok(paths)
}

#[cfg(not(any(windows, target_os = "macos")))]
pub(super) fn install_platform(
    _data_dir: &Path,
    progress: &LocalAiInstallState,
) -> Result<InstalledPaths, ManagedAiError> {
    progress.set(
        None,
        Some("This operating-system architecture is not supported by Local AI Preview."),
    );
    Err(ManagedAiError::InvalidConfig(
        "this operating-system architecture is not supported by Local AI Preview",
    ))
}

#[cfg(any(windows, target_os = "macos"))]
fn download_exact(
    url: &str,
    partial: &Path,
    expected_bytes: u64,
    expected_sha256: &str,
    progress: &LocalAiInstallState,
) -> Result<(), ManagedAiError> {
    if partial.exists() {
        std::fs::remove_file(partial)
            .map_err(|_| ManagedAiError::Io("partial Local AI download could not be reset"))?;
    }
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(3600))
        .connect_timeout(std::time::Duration::from_secs(20))
        .no_proxy()
        .redirect(reqwest::redirect::Policy::limited(8))
        .build()
        .map_err(|_| ManagedAiError::Io("Local AI download client failed"))?;
    let mut response = client
        .get(url)
        .send()
        .and_then(reqwest::blocking::Response::error_for_status)
        .map_err(|_| ManagedAiError::Io("Local AI download failed"))?;
    let host = response.url().host_str().unwrap_or_default();
    if !download_host_allowed(host) || response.content_length() != Some(expected_bytes) {
        return Err(ManagedAiError::Io("Local AI download identity mismatch"));
    }
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    let mut output = options
        .open(partial)
        .map_err(|_| ManagedAiError::Io("Local AI partial download creation failed"))?;
    let mut hasher = Sha256::new();
    let mut total = 0_u64;
    let mut buffer = vec![0_u8; DOWNLOAD_BUFFER_BYTES];
    loop {
        let read = response
            .read(&mut buffer)
            .map_err(|_| ManagedAiError::Io("Local AI download interrupted"))?;
        if read == 0 {
            break;
        }
        total = total.saturating_add(read as u64);
        if total > expected_bytes {
            return Err(ManagedAiError::Io(
                "Local AI download exceeded expected size",
            ));
        }
        hasher.update(&buffer[..read]);
        output
            .write_all(&buffer[..read])
            .map_err(|_| ManagedAiError::Io("Local AI download write failed"))?;
        progress.record_downloaded(total);
    }
    output
        .sync_all()
        .map_err(|_| ManagedAiError::Io("Local AI download flush failed"))?;
    let digest = format!("{:x}", hasher.finalize());
    if total != expected_bytes || digest != expected_sha256 {
        let _ = std::fs::remove_file(partial);
        return Err(ManagedAiError::Io("Local AI download checksum mismatch"));
    }
    Ok(())
}

fn download_host_allowed(host: &str) -> bool {
    host == "github.com"
        || host == "release-assets.githubusercontent.com"
        || host == "objects.githubusercontent.com"
        || host == "huggingface.co"
        || host.ends_with(".hf.co")
}

#[cfg(windows)]
fn extract_runtime_windows(root: &Path, archive_path: &Path) -> Result<(), ManagedAiError> {
    let staging = root.join(format!("{RUNTIME_DIR}.partial"));
    if staging.exists() {
        std::fs::remove_dir_all(&staging)
            .map_err(|_| ManagedAiError::Io("partial Local AI runtime could not be reset"))?;
    }
    std::fs::create_dir(&staging)
        .map_err(|_| ManagedAiError::Io("Local AI runtime staging failed"))?;
    let file = File::open(archive_path)
        .map_err(|_| ManagedAiError::Io("Local AI runtime archive missing"))?;
    let mut archive = zip::ZipArchive::new(BufReader::new(file))
        .map_err(|_| ManagedAiError::Io("Local AI runtime archive invalid"))?;
    let mut launcher_found = false;
    for index in 0..archive.len() {
        let mut entry = archive
            .by_index(index)
            .map_err(|_| ManagedAiError::Io("Local AI runtime archive invalid"))?;
        let enclosed = entry
            .enclosed_name()
            .ok_or(ManagedAiError::Io("Local AI runtime archive path invalid"))?;
        let mut components = enclosed.components();
        let Some(Component::Normal(name)) = components.next() else {
            return Err(ManagedAiError::Io("Local AI runtime archive path invalid"));
        };
        if components.next().is_some() {
            return Err(ManagedAiError::Io("Local AI runtime archive path invalid"));
        }
        let name = name
            .to_str()
            .ok_or(ManagedAiError::Io("Local AI runtime archive path invalid"))?;
        if !runtime_entry_allowed(name) {
            continue;
        }
        launcher_found |= name.eq_ignore_ascii_case("llama-server.exe");
        let destination = staging.join(name);
        let mut output = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&destination)
            .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
        std::io::copy(&mut entry, &mut output)
            .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
        output
            .sync_all()
            .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
    }
    if !launcher_found {
        return Err(ManagedAiError::Io("Local AI runtime launcher missing"));
    }
    let final_dir = root.join(RUNTIME_DIR);
    if final_dir.exists() {
        std::fs::remove_dir_all(&final_dir)
            .map_err(|_| ManagedAiError::Io("Local AI runtime repair failed"))?;
    }
    std::fs::rename(&staging, &final_dir)
        .map_err(|_| ManagedAiError::Io("Local AI runtime promotion failed"))?;
    Ok(())
}

#[cfg(windows)]
fn runtime_entry_allowed(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    lower == "llama-server.exe" || lower.ends_with(".dll")
}

#[cfg(any(windows, target_os = "macos"))]
fn replace_file(source: &Path, destination: &Path) -> Result<(), ManagedAiError> {
    if destination.exists() {
        std::fs::remove_file(destination)
            .map_err(|_| ManagedAiError::Io("Local AI model repair failed"))?;
    }
    std::fs::rename(source, destination)
        .map_err(|_| ManagedAiError::Io("Local AI model promotion failed"))
}

#[cfg(any(windows, target_os = "macos"))]
pub(super) fn verify_install(paths: &InstalledPaths) -> Result<(), ManagedAiError> {
    if !file_identity_matches(&paths.model, MODEL_BYTES, MODEL_SHA256)? {
        return Err(ManagedAiError::Io(
            "installed Local AI model identity mismatch",
        ));
    }
    let identity = runtime_bundle_identity(&paths.runtime)?;
    if identity.launcher_digest != RUNTIME_LAUNCHER_SHA256
        || identity.manifest_digest != RUNTIME_BUNDLE_SHA256
    {
        return Err(ManagedAiError::Io(
            "installed Local AI runtime identity mismatch",
        ));
    }
    Ok(())
}

fn file_identity_matches(
    path: &Path,
    expected_bytes: u64,
    expected_sha256: &str,
) -> Result<bool, ManagedAiError> {
    if path.metadata().map(|meta| meta.len()).unwrap_or(0) != expected_bytes {
        return Ok(false);
    }
    Ok(digest_file(path)? == expected_sha256)
}

#[cfg(any(windows, target_os = "macos"))]
fn write_receipt(root: &Path) -> Result<(), ManagedAiError> {
    let receipt = InstallReceipt {
        schema_version: 1,
        model_id: MODEL_ID,
        model_revision: MODEL_REVISION,
        model_sha256: MODEL_SHA256,
        model_bytes: MODEL_BYTES,
        model_source: "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        model_license: "Apache-2.0",
        runtime_family: "llama.cpp",
        runtime_version: "b10516 / b95502ba9",
        runtime_archive_sha256: RUNTIME_ARCHIVE_SHA256,
        runtime_launcher_sha256: RUNTIME_LAUNCHER_SHA256,
        runtime_bundle_manifest_sha256: RUNTIME_BUNDLE_SHA256,
        runtime_source: "ggml-org/llama.cpp release b10516",
        runtime_license: "MIT",
        declared_build_backend: "cpu",
    };
    let bytes = serde_json::to_vec_pretty(&receipt)
        .map_err(|_| ManagedAiError::Io("Local AI install receipt encoding failed"))?;
    let partial = root.join(format!("{RECEIPT_FILENAME}.partial"));
    if partial.exists() {
        let _ = std::fs::remove_file(&partial);
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&partial)
        .map_err(|_| ManagedAiError::Io("Local AI install receipt write failed"))?;
    file.write_all(&bytes)
        .and_then(|_| file.sync_all())
        .map_err(|_| ManagedAiError::Io("Local AI install receipt write failed"))?;
    let destination = root.join(RECEIPT_FILENAME);
    if destination.exists() {
        std::fs::remove_file(&destination)
            .map_err(|_| ManagedAiError::Io("Local AI install receipt repair failed"))?;
    }
    std::fs::rename(partial, destination)
        .map_err(|_| ManagedAiError::Io("Local AI install receipt promotion failed"))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_root(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "callosum-local-install-{label}-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ))
    }

    #[test]
    fn pinned_model_identity_is_exact_and_not_mutable_latest() {
        assert_eq!(MODEL_SHA256.len(), 64);
        assert!(MODEL_URL.contains(MODEL_REVISION));
        assert!(MODEL_URL.ends_with("qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true"));
        assert!(!MODEL_URL.contains("/main/"));
    }

    #[cfg(windows)]
    #[test]
    fn runtime_archive_boundary_allows_only_launcher_and_libraries() {
        assert!(runtime_entry_allowed("llama-server.exe"));
        assert!(runtime_entry_allowed("ggml-cpu-x64.dll"));
        assert!(!runtime_entry_allowed("llama-cli.exe"));
        assert!(!runtime_entry_allowed("model.gguf"));
        assert!(!runtime_entry_allowed("target.json"));
    }

    #[cfg(windows)]
    #[test]
    fn download_hosts_are_narrowly_allowlisted() {
        assert!(download_host_allowed("github.com"));
        assert!(download_host_allowed(
            "release-assets.githubusercontent.com"
        ));
        assert!(download_host_allowed("us.aws.cdn.hf.co"));
        assert!(!download_host_allowed("github.com.example.org"));
        assert!(!download_host_allowed("example.org"));
    }

    #[test]
    fn exact_file_identity_rejects_partial_and_wrong_checksum() {
        let root = test_root("identity");
        std::fs::create_dir_all(&root).unwrap();
        let file = root.join("artifact.bin");
        std::fs::write(&file, b"exact pinned bytes").unwrap();
        let digest = digest_file(&file).unwrap();
        assert!(file_identity_matches(&file, 18, &digest).unwrap());
        assert!(!file_identity_matches(&file, 19, &digest).unwrap());
        assert!(!file_identity_matches(&file, 18, &"0".repeat(64)).unwrap());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn install_progress_reports_bytes_eta_and_resets_without_large_stack_state() {
        let state = LocalAiInstallState::default();
        state.begin_download("downloading_model", 1_000);
        {
            let mut progress = state.0.lock().unwrap();
            progress.download_started = Some(Instant::now() - std::time::Duration::from_secs(10));
        }
        state.record_downloaded(250);
        let snapshot = state.snapshot();
        assert_eq!(snapshot.stage, Some("downloading_model"));
        assert_eq!(snapshot.detail, None);
        assert_eq!(snapshot.downloaded_bytes, Some(250));
        assert_eq!(snapshot.total_bytes, Some(1_000));
        assert!(snapshot
            .eta_seconds
            .is_some_and(|seconds| (29..=31).contains(&seconds)));

        state.set(Some("verifying"), None);
        assert_eq!(
            state.snapshot(),
            InstallProgressSnapshot {
                stage: Some("verifying"),
                detail: None,
                downloaded_bytes: None,
                total_bytes: None,
                eta_seconds: None,
                error_code: None,
            }
        );
    }

    #[cfg(windows)]
    #[test]
    fn partial_or_wrong_size_install_is_never_discovered_as_installed() {
        let data_dir = test_root("partial");
        let root = install_root(&data_dir);
        let runtime = root.join(RUNTIME_DIR);
        std::fs::create_dir_all(&runtime).unwrap();
        std::fs::write(runtime.join("llama-server.exe"), b"not the pinned runtime").unwrap();
        std::fs::write(root.join(RECEIPT_FILENAME), b"{}").unwrap();
        std::fs::write(root.join(format!("{MODEL_FILENAME}.partial")), b"partial").unwrap();
        assert!(installed_paths(&data_dir).unwrap().is_none());
        std::fs::write(root.join(MODEL_FILENAME), b"wrong size").unwrap();
        assert!(installed_paths(&data_dir).unwrap().is_none());
        std::fs::remove_dir_all(data_dir).unwrap();
    }
}
