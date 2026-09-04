//! Immutable, independently distributed Python runtime used by the desktop backend.
//!
//! The trusted input-derived runtime ID is compiled into the shell. A signed release manifest binds
//! that ID to one exact archive and extracted tree. Installation occurs only under the current
//! user's local application-data directory; an app/package update never mutates that directory.

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine as _;
use flate2::read::GzDecoder;
use minisign_verify::{PublicKey, Signature};
use reqwest::blocking::{Client, Response};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};
use tauri::path::BaseDirectory;
use tauri::{AppHandle, Emitter, Manager};

const INPUTS_JSON: &str = include_str!("../../packaging/python-runtime-inputs.json");
const PUBLIC_KEY: &str = "untrusted comment: minisign public key: EDF3A3180C3324BA\nRWS6JDMMGKPz7QM6yWxfov3gNpZ7Yut6CGKjl4J7IS5dt5j5o3JCWcdw\n";
const RELEASE_BASE: &str = "https://github.com/cliffworkman/callosum/releases/download";
const TREE_DOMAIN: &[u8] = b"callosum-python-runtime-tree-v1\n";
const RECEIPT: &str = "runtime-install.json";
const MAX_MANIFEST_BYTES: u64 = 2 * 1024 * 1024;
const MAX_SIGNATURE_BYTES: u64 = 64 * 1024;
const MAX_ARCHIVE_BYTES: u64 = 3 * 1024 * 1024 * 1024;
const MAX_UNPACKED_BYTES: u64 = 8 * 1024 * 1024 * 1024;
const MAX_ENTRIES: u64 = 150_000;
const DOWNLOAD_BUFFER_BYTES: usize = 1024 * 1024;

#[derive(Debug)]
pub struct RuntimeError {
    code: &'static str,
    detail: String,
}

impl RuntimeError {
    fn new(code: &'static str, detail: impl Into<String>) -> Self {
        Self {
            code,
            detail: detail.into(),
        }
    }

    pub fn detail(&self) -> String {
        format!("{} ({})", self.detail, self.code)
    }
}

#[derive(Debug, Deserialize)]
struct RuntimeInputs {
    platforms: BTreeMap<String, TrustedPlatform>,
}

#[derive(Debug, Clone, Deserialize)]
struct TrustedPlatform {
    runtime_id: String,
    os: String,
    arch: String,
    python_version: String,
    python_build: String,
    python_relative_path: String,
    glibc_min: Option<String>,
    distribution_boundary: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct RuntimeManifest {
    schema_version: u8,
    packaging_schema: String,
    runtime_id: String,
    platform: String,
    arch: String,
    python_version: String,
    python_build: String,
    python_relative_path: String,
    archive_url: String,
    archive_bytes: u64,
    archive_sha256: String,
    tree_sha256: String,
    entry_count: u64,
    unpacked_bytes: u64,
    glibc_min: Option<String>,
    distribution_boundary: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
struct InstallReceipt {
    schema_version: u8,
    runtime_id: String,
    manifest_sha256: String,
    archive_sha256: String,
    tree_sha256: String,
    python_relative_path: String,
}

#[derive(Debug, Clone, Eq, PartialEq)]
struct TreeEntry {
    relative: String,
    kind: &'static str,
    size: u64,
    identity: String,
    executable: bool,
}

impl TreeEntry {
    fn digest_line(&self) -> String {
        format!(
            "{}\t{}\t{}\t{}\t{}\n",
            self.kind,
            self.relative,
            self.size,
            self.identity,
            u8::from(self.executable)
        )
    }
}

fn platform_key() -> Result<&'static str, RuntimeError> {
    if cfg!(all(windows, target_arch = "x86_64")) {
        Ok("windows-x86_64")
    } else if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        Ok("macos-aarch64")
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        Ok("macos-x86_64")
    } else if cfg!(all(
        target_os = "linux",
        target_arch = "x86_64",
        target_env = "gnu"
    )) {
        Ok("linux-x86_64")
    } else {
        Err(RuntimeError::new(
            "PYTHON_RUNTIME_PLATFORM_UNSUPPORTED",
            "This operating-system architecture has no managed Callosum Python runtime.",
        ))
    }
}

fn trusted_platform() -> Result<TrustedPlatform, RuntimeError> {
    let inputs: RuntimeInputs = serde_json::from_str(INPUTS_JSON).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_SPEC_INVALID",
            "Callosum's built-in Python runtime specification is invalid.",
        )
    })?;
    let trusted = inputs
        .platforms
        .get(platform_key()?)
        .cloned()
        .ok_or_else(|| {
            RuntimeError::new(
                "PYTHON_RUNTIME_PLATFORM_UNSUPPORTED",
                "This operating-system architecture has no managed Callosum Python runtime.",
            )
        })?;
    validate_host_compatibility(&trusted)?;
    Ok(trusted)
}

fn validate_host_compatibility(trusted: &TrustedPlatform) -> Result<(), RuntimeError> {
    #[cfg(all(target_os = "linux", target_env = "gnu"))]
    if let Some(required) = trusted.glibc_min.as_deref() {
        use std::ffi::CStr;
        // SAFETY: glibc owns a process-lifetime NUL-terminated version string.
        let actual = unsafe { CStr::from_ptr(libc::gnu_get_libc_version()) }
            .to_str()
            .map_err(|_| {
                RuntimeError::new(
                    "PYTHON_RUNTIME_GLIBC_UNKNOWN",
                    "Callosum could not determine this Linux system's glibc version.",
                )
            })?;
        if version_pair(actual) < version_pair(required) {
            return Err(RuntimeError::new(
                "PYTHON_RUNTIME_GLIBC_UNSUPPORTED",
                format!(
                    "This runtime requires glibc {required} or newer; this system has {actual}."
                ),
            ));
        }
    }
    #[cfg(not(all(target_os = "linux", target_env = "gnu")))]
    let _ = trusted;
    Ok(())
}

#[cfg_attr(not(all(target_os = "linux", target_env = "gnu")), allow(dead_code))]
fn version_pair(value: &str) -> (u32, u32) {
    let mut parts = value.split('.').filter_map(|part| part.parse::<u32>().ok());
    (parts.next().unwrap_or(0), parts.next().unwrap_or(0))
}

fn runtime_root(local_data: &Path) -> PathBuf {
    local_data.join("python-runtimes")
}

fn final_runtime_dir(local_data: &Path, trusted: &TrustedPlatform) -> PathBuf {
    runtime_root(local_data).join(&trusted.runtime_id)
}

fn receipt_is_valid(dir: &Path, trusted: &TrustedPlatform) -> bool {
    let bytes = match std::fs::read(dir.join(RECEIPT)) {
        Ok(bytes) if bytes.len() <= MAX_MANIFEST_BYTES as usize => bytes,
        _ => return false,
    };
    let receipt: InstallReceipt = match serde_json::from_slice(&bytes) {
        Ok(receipt) => receipt,
        Err(_) => return false,
    };
    receipt.schema_version == 1
        && receipt.runtime_id == trusted.runtime_id
        && receipt.python_relative_path == trusted.python_relative_path
        && is_sha256(&receipt.manifest_sha256)
        && is_sha256(&receipt.archive_sha256)
        && is_sha256(&receipt.tree_sha256)
        && dir.join(&trusted.python_relative_path).is_file()
}

pub fn installed_python(app: &AppHandle) -> Result<PathBuf, RuntimeError> {
    let trusted = trusted_platform()?;
    let local_data = app.path().app_local_data_dir().map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DATA_DIR_UNAVAILABLE",
            format!("Callosum could not resolve its local data directory: {error}"),
        )
    })?;
    let dir = final_runtime_dir(&local_data, &trusted);
    if receipt_is_valid(&dir, &trusted) {
        Ok(dir.join(trusted.python_relative_path))
    } else {
        Err(RuntimeError::new(
            "PYTHON_RUNTIME_NOT_INSTALLED",
            "Callosum's managed Python runtime is not installed or is incomplete.",
        ))
    }
}

pub async fn ensure_runtime(app: AppHandle) -> Result<PathBuf, RuntimeError> {
    if let Ok(path) = installed_python(&app) {
        return Ok(path);
    }
    let worker_app = app.clone();
    tauri::async_runtime::spawn_blocking(move || provision_runtime(&worker_app))
        .await
        .map_err(|_| {
            RuntimeError::new(
                "PYTHON_RUNTIME_PROVISION_TASK_FAILED",
                "Callosum's Python runtime setup task stopped unexpectedly.",
            )
        })?
}

fn provision_runtime(app: &AppHandle) -> Result<PathBuf, RuntimeError> {
    let local_data = app.path().app_local_data_dir().map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DATA_DIR_UNAVAILABLE",
            format!("Callosum could not resolve its local data directory: {error}"),
        )
    })?;
    let emit = |stage: &str, message: &str, done: Option<u64>, total: Option<u64>| {
        emit_progress(app, stage, message, done, total);
    };
    provision_into(&local_data, &emit, Some(app))
}

/// The whole provisioning chain, addressed by a plain directory rather than a live Tauri app.
///
/// Split out so a real end-to-end test can drive download → checksum → extraction → smoke test →
/// atomic activation against the actually-published artifact. That path had no coverage at all, and
/// it is the one that decides whether a fresh install has a Python interpreter, so "it compiles" is
/// nowhere near sufficient assurance.
fn provision_into(
    local_data: &Path,
    progress: ProgressSink,
    app: Option<&AppHandle>,
) -> Result<PathBuf, RuntimeError> {
    let trusted = trusted_platform()?;
    let root = runtime_root(local_data);
    std::fs::create_dir_all(&root).map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DIRECTORY_FAILED",
            format!("Callosum could not create its runtime directory: {error}"),
        )
    })?;
    let final_dir = final_runtime_dir(local_data, &trusted);
    if receipt_is_valid(&final_dir, &trusted) {
        return Ok(final_dir.join(&trusted.python_relative_path));
    }

    progress(
        "runtime_manifest",
        "Checking the managed Python runtime…",
        None,
        None,
    );
    let client = download_client()?;
    let tag = format!("python-runtime-{}", trusted.runtime_id);
    let manifest_url = format!("{RELEASE_BASE}/{tag}/runtime-manifest.json");
    let signature_url = format!("{manifest_url}.sig");
    let manifest_bytes = download_small(&client, &manifest_url, MAX_MANIFEST_BYTES)?;
    let signature_bytes = download_small(&client, &signature_url, MAX_SIGNATURE_BYTES)?;
    verify_manifest_signature(&manifest_bytes, &signature_bytes)?;
    let manifest: RuntimeManifest = serde_json::from_slice(&manifest_bytes).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_MANIFEST_INVALID",
            "The signed Python runtime manifest is malformed.",
        )
    })?;
    validate_manifest(&manifest, &trusted, &tag)?;
    let manifest_sha256 = sha256_bytes(&manifest_bytes);

    if let Some(app) = app {
        if let Some(path) = try_migrate_legacy(
            app,
            progress,
            &root,
            &final_dir,
            &trusted,
            &manifest,
            &manifest_sha256,
        )? {
            return Ok(path);
        }
    }

    let archive = root.join(format!(".{}.tar.gz.partial", trusted.runtime_id));
    if archive.exists() {
        let _ = std::fs::remove_file(&archive);
    }
    progress(
        "runtime_download",
        "Downloading Callosum's one-time Python runtime…",
        Some(0),
        Some(manifest.archive_bytes),
    );
    download_archive(progress, &client, &manifest, &archive)?;
    let result = install_archive(
        progress,
        &archive,
        &root,
        &final_dir,
        &trusted,
        &manifest,
        &manifest_sha256,
    );
    let _ = std::fs::remove_file(&archive);
    result
}

fn download_client() -> Result<Client, RuntimeError> {
    Client::builder()
        .timeout(Duration::from_secs(3600))
        .connect_timeout(Duration::from_secs(20))
        .no_proxy()
        .redirect(reqwest::redirect::Policy::limited(8))
        .build()
        .map_err(|_| {
            RuntimeError::new(
                "PYTHON_RUNTIME_DOWNLOAD_CLIENT_FAILED",
                "Callosum could not prepare the runtime download.",
            )
        })
}

fn response_checked(response: Response) -> Result<Response, RuntimeError> {
    let response = response.error_for_status().map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_FAILED",
            format!("The runtime host returned an error: {error}"),
        )
    })?;
    if !download_host_allowed(response.url().host_str().unwrap_or_default()) {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_HOST_REJECTED",
            "The runtime download redirected to an untrusted host.",
        ));
    }
    Ok(response)
}

fn download_small(client: &Client, url: &str, maximum: u64) -> Result<Vec<u8>, RuntimeError> {
    let response = response_checked(client.get(url).send().map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_FAILED",
            format!("Callosum could not reach the runtime host: {error}"),
        )
    })?)?;
    if response.content_length().is_some_and(|size| size > maximum) {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_TOO_LARGE",
            "The runtime metadata exceeded its safe size limit.",
        ));
    }
    let mut bytes = Vec::new();
    response
        .take(maximum + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| {
            RuntimeError::new(
                "PYTHON_RUNTIME_DOWNLOAD_INTERRUPTED",
                "The runtime metadata download was interrupted.",
            )
        })?;
    if bytes.len() as u64 > maximum {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_TOO_LARGE",
            "The runtime metadata exceeded its safe size limit.",
        ));
    }
    Ok(bytes)
}

/// Parse a minisign signature that may be stored either plainly or base64-wrapped.
///
/// `tauri signer sign` -- the signer this project already uses for updater artifacts, and which the
/// runtime workflow reuses -- writes the whole 4-line minisign document **base64-encoded**, while
/// `minisign_verify::Signature::decode` expects that document verbatim. Handing it the raw file
/// therefore rejects every genuine signature. Both encodings are accepted here so the verifier
/// matches what the signer actually produces without being brittle if that ever changes; anything
/// that is neither still fails closed.
fn decode_signature(signature: &[u8]) -> Option<Signature> {
    if let Ok(text) = std::str::from_utf8(signature) {
        if let Ok(parsed) = Signature::decode(text) {
            return Some(parsed);
        }
        let unwrapped = BASE64.decode(text.trim().as_bytes()).ok()?;
        let unwrapped_text = std::str::from_utf8(&unwrapped).ok()?;
        return Signature::decode(unwrapped_text).ok();
    }
    None
}

fn verify_manifest_signature(manifest: &[u8], signature: &[u8]) -> Result<(), RuntimeError> {
    let key = PublicKey::decode(PUBLIC_KEY).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_PUBLIC_KEY_INVALID",
            "Callosum's built-in runtime verification key is invalid.",
        )
    })?;
    let signature = decode_signature(signature).ok_or_else(|| {
        RuntimeError::new(
            "PYTHON_RUNTIME_SIGNATURE_INVALID",
            "The Python runtime signature is malformed.",
        )
    })?;
    key.verify(manifest, &signature, false).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_SIGNATURE_MISMATCH",
            "The Python runtime manifest did not pass Callosum's signature check.",
        )
    })
}

fn validate_manifest(
    manifest: &RuntimeManifest,
    trusted: &TrustedPlatform,
    tag: &str,
) -> Result<(), RuntimeError> {
    let expected_archive = format!("{RELEASE_BASE}/{tag}/{}.tar.gz", trusted.runtime_id);
    let identity_matches = manifest.schema_version == 1
        && manifest.packaging_schema == "callosum-python-runtime-v1"
        && manifest.runtime_id == trusted.runtime_id
        && manifest.platform == trusted.os
        && manifest.arch == trusted.arch
        && manifest.python_version == trusted.python_version
        && manifest.python_build == trusted.python_build
        && manifest.python_relative_path == trusted.python_relative_path
        && manifest.archive_url == expected_archive
        && manifest.glibc_min == trusted.glibc_min
        && manifest.distribution_boundary == trusted.distribution_boundary;
    let bounds_hold = manifest.archive_bytes > 0
        && manifest.archive_bytes <= MAX_ARCHIVE_BYTES
        && manifest.unpacked_bytes > 0
        && manifest.unpacked_bytes <= MAX_UNPACKED_BYTES
        && manifest.entry_count > 0
        && manifest.entry_count <= MAX_ENTRIES
        && is_sha256(&manifest.archive_sha256)
        && is_sha256(&manifest.tree_sha256);
    if !identity_matches || !bounds_hold {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_MANIFEST_MISMATCH",
            "The signed Python runtime manifest does not match this Callosum build.",
        ));
    }
    Ok(())
}

/// Where provisioning reports progress.
///
/// Deliberately not an `AppHandle`: the download → checksum → extract → smoke-test → activate chain
/// is the part that must actually be proven end to end, and tying it to a live Tauri app would make
/// that untestable. `provision_runtime` passes a sink that emits to the splash window; a test passes
/// one that records. Arguments are `(stage, message, done, total)`.
type ProgressSink<'a> = &'a dyn Fn(&str, &str, Option<u64>, Option<u64>);

fn download_archive(
    progress: ProgressSink,
    client: &Client,
    manifest: &RuntimeManifest,
    destination: &Path,
) -> Result<(), RuntimeError> {
    let mut response =
        response_checked(client.get(&manifest.archive_url).send().map_err(|error| {
            RuntimeError::new(
                "PYTHON_RUNTIME_DOWNLOAD_FAILED",
                format!("Callosum could not reach the runtime host: {error}"),
            )
        })?)?;
    if response.content_length() != Some(manifest.archive_bytes) {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_ARCHIVE_SIZE_MISMATCH",
            "The Python runtime download size did not match its signed manifest.",
        ));
    }
    let mut output = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(destination)
        .map_err(|error| {
            RuntimeError::new(
                "PYTHON_RUNTIME_PARTIAL_CREATE_FAILED",
                format!("Callosum could not create the partial runtime download: {error}"),
            )
        })?;
    let mut digest = Sha256::new();
    let mut total = 0_u64;
    let mut buffer = vec![0_u8; DOWNLOAD_BUFFER_BYTES];
    loop {
        let read = response.read(&mut buffer).map_err(|_| {
            RuntimeError::new(
                "PYTHON_RUNTIME_DOWNLOAD_INTERRUPTED",
                "The Python runtime download was interrupted.",
            )
        })?;
        if read == 0 {
            break;
        }
        total = total.saturating_add(read as u64);
        if total > manifest.archive_bytes {
            return Err(RuntimeError::new(
                "PYTHON_RUNTIME_ARCHIVE_SIZE_MISMATCH",
                "The Python runtime download exceeded its signed size.",
            ));
        }
        digest.update(&buffer[..read]);
        output.write_all(&buffer[..read]).map_err(|error| {
            RuntimeError::new(
                "PYTHON_RUNTIME_DOWNLOAD_WRITE_FAILED",
                format!("Callosum could not save the runtime download: {error}"),
            )
        })?;
        progress(
            "runtime_download",
            "Downloading Callosum's one-time Python runtime…",
            Some(total),
            Some(manifest.archive_bytes),
        );
    }
    output.sync_all().map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_DOWNLOAD_WRITE_FAILED",
            format!("Callosum could not finish saving the runtime download: {error}"),
        )
    })?;
    let actual = format!("{:x}", digest.finalize());
    if total != manifest.archive_bytes || actual != manifest.archive_sha256 {
        let _ = std::fs::remove_file(destination);
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_ARCHIVE_CHECKSUM_MISMATCH",
            "The Python runtime download did not pass its integrity check.",
        ));
    }
    Ok(())
}

fn install_archive(
    progress: ProgressSink,
    archive: &Path,
    root: &Path,
    final_dir: &Path,
    trusted: &TrustedPlatform,
    manifest: &RuntimeManifest,
    manifest_sha256: &str,
) -> Result<PathBuf, RuntimeError> {
    progress(
        "runtime_extract",
        "Verifying and preparing Callosum's Python runtime…",
        None,
        None,
    );
    let staging = root.join(format!(
        ".{}.staging-{}",
        trusted.runtime_id,
        std::process::id()
    ));
    if staging.exists() {
        std::fs::remove_dir_all(&staging).map_err(|error| {
            RuntimeError::new(
                "PYTHON_RUNTIME_STAGING_RESET_FAILED",
                format!("Callosum could not reset runtime staging: {error}"),
            )
        })?;
    }
    std::fs::create_dir(&staging).map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_STAGING_CREATE_FAILED",
            format!("Callosum could not create runtime staging: {error}"),
        )
    })?;
    let install = (|| {
        extract_verified(archive, &staging, manifest)?;
        smoke_test(&staging.join(&trusted.python_relative_path))?;
        write_receipt(&staging, trusted, manifest, manifest_sha256)?;
        activate_staging(&staging, final_dir, trusted)?;
        Ok(())
    })();
    if install.is_err() || staging.exists() {
        let _ = std::fs::remove_dir_all(&staging);
    }
    install?;
    progress("runtime_ready", "Python runtime ready.", None, None);
    Ok(final_dir.join(&trusted.python_relative_path))
}

fn activate_staging(
    staging: &Path,
    final_dir: &Path,
    trusted: &TrustedPlatform,
) -> Result<(), RuntimeError> {
    if final_dir.exists() {
        if receipt_is_valid(final_dir, trusted) {
            std::fs::remove_dir_all(staging).map_err(|error| {
                RuntimeError::new(
                    "PYTHON_RUNTIME_STAGING_RESET_FAILED",
                    format!("Callosum could not discard redundant runtime staging: {error}"),
                )
            })?;
            return Ok(());
        }
        std::fs::remove_dir_all(final_dir).map_err(|error| {
            RuntimeError::new(
                "PYTHON_RUNTIME_INVALID_REPAIR_FAILED",
                format!("Callosum could not replace an incomplete runtime: {error}"),
            )
        })?;
    }
    std::fs::rename(staging, final_dir).map_err(|error| {
        RuntimeError::new(
            "PYTHON_RUNTIME_ACTIVATION_FAILED",
            format!("Callosum could not activate the verified runtime: {error}"),
        )
    })
}

fn extract_verified(
    archive_path: &Path,
    staging: &Path,
    manifest: &RuntimeManifest,
) -> Result<(), RuntimeError> {
    let file = File::open(archive_path).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_ARCHIVE_MISSING",
            "The verified Python runtime archive is missing.",
        )
    })?;
    let mut archive = tar::Archive::new(GzDecoder::new(file));
    let mut paths = HashSet::new();
    let mut entries = Vec::new();
    #[cfg(unix)]
    let mut links: Vec<(PathBuf, String)> = Vec::new();
    let mut unpacked = 0_u64;
    for item in archive.entries().map_err(|_| invalid_archive())? {
        let mut item = item.map_err(|_| invalid_archive())?;
        let path = item.path().map_err(|_| invalid_archive())?;
        let relative = archive_relative_path(&path)?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let relative_text = relative
            .to_str()
            .ok_or_else(invalid_archive)?
            .replace('\\', "/");
        if !paths.insert(relative_text.clone()) {
            return Err(invalid_archive());
        }
        let destination = staging.join(&relative);
        let entry_type = item.header().entry_type();
        if entry_type.is_dir() {
            std::fs::create_dir_all(&destination).map_err(|_| invalid_archive())?;
            continue;
        }
        if entries.len() as u64 >= manifest.entry_count || entries.len() as u64 >= MAX_ENTRIES {
            return Err(invalid_archive());
        }
        if entry_type.is_symlink() {
            #[cfg(windows)]
            return Err(invalid_archive());
            #[cfg(unix)]
            {
                let target = item
                    .link_name()
                    .map_err(|_| invalid_archive())?
                    .ok_or_else(invalid_archive)?;
                let target = target.to_str().ok_or_else(invalid_archive)?.to_string();
                validate_link_target(&relative, &target)?;
                links.push((relative.clone(), target.clone()));
                entries.push(TreeEntry {
                    relative: relative_text,
                    kind: "link",
                    size: 0,
                    identity: target,
                    executable: false,
                });
                continue;
            }
        }
        if !entry_type.is_file() {
            return Err(invalid_archive());
        }
        let size = item.size();
        unpacked = unpacked.checked_add(size).ok_or_else(invalid_archive)?;
        if unpacked > manifest.unpacked_bytes || unpacked > MAX_UNPACKED_BYTES {
            return Err(invalid_archive());
        }
        if let Some(parent) = destination.parent() {
            std::fs::create_dir_all(parent).map_err(|_| invalid_archive())?;
        }
        let mut output = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&destination)
            .map_err(|_| invalid_archive())?;
        let mut digest = Sha256::new();
        let copied = std::io::copy(&mut item, &mut DigestWriter::new(&mut output, &mut digest))
            .map_err(|_| invalid_archive())?;
        if copied != size {
            return Err(invalid_archive());
        }
        let mode = item.header().mode().map_err(|_| invalid_archive())?;
        let executable = mode & 0o111 != 0;
        set_file_mode(&destination, executable)?;
        entries.push(TreeEntry {
            relative: relative_text,
            kind: "file",
            size,
            identity: format!("{:x}", digest.finalize()),
            executable,
        });
    }
    #[cfg(unix)]
    for (relative, target) in links {
        let destination = staging.join(relative);
        if let Some(parent) = destination.parent() {
            std::fs::create_dir_all(parent).map_err(|_| invalid_archive())?;
        }
        std::os::unix::fs::symlink(target, destination).map_err(|_| invalid_archive())?;
    }
    entries.sort_by(|left, right| left.relative.cmp(&right.relative));
    if entries.len() as u64 != manifest.entry_count
        || unpacked != manifest.unpacked_bytes
        || tree_digest(&entries) != manifest.tree_sha256
    {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_TREE_MISMATCH",
            "The extracted Python runtime did not match its signed tree identity.",
        ));
    }
    Ok(())
}

struct DigestWriter<'a> {
    output: &'a mut File,
    digest: &'a mut Sha256,
}

impl<'a> DigestWriter<'a> {
    fn new(output: &'a mut File, digest: &'a mut Sha256) -> Self {
        Self { output, digest }
    }
}

impl Write for DigestWriter<'_> {
    fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
        let written = self.output.write(buffer)?;
        self.digest.update(&buffer[..written]);
        Ok(written)
    }

    fn flush(&mut self) -> std::io::Result<()> {
        self.output.flush()
    }
}

fn archive_relative_path(path: &Path) -> Result<PathBuf, RuntimeError> {
    let mut components = path.components();
    match components.next() {
        Some(Component::Normal(root)) if root == "python-runtime" => {}
        _ => return Err(invalid_archive()),
    }
    let mut relative = PathBuf::new();
    for component in components {
        match component {
            Component::Normal(part) => relative.push(part),
            _ => return Err(invalid_archive()),
        }
    }
    Ok(relative)
}

#[cfg_attr(not(unix), allow(dead_code))]
fn validate_link_target(relative: &Path, target: &str) -> Result<(), RuntimeError> {
    if target.is_empty() || target.contains('\\') || Path::new(target).is_absolute() {
        return Err(invalid_archive());
    }
    let mut depth = relative
        .parent()
        .map_or(0_usize, |path| path.components().count());
    for component in Path::new(target).components() {
        match component {
            Component::CurDir => {}
            Component::Normal(_) => depth += 1,
            Component::ParentDir if depth > 0 => depth -= 1,
            _ => return Err(invalid_archive()),
        }
    }
    Ok(())
}

fn tree_digest(entries: &[TreeEntry]) -> String {
    let mut digest = Sha256::new();
    digest.update(TREE_DOMAIN);
    for entry in entries {
        digest.update(entry.digest_line().as_bytes());
    }
    format!("{:x}", digest.finalize())
}

fn set_file_mode(path: &Path, executable: bool) -> Result<(), RuntimeError> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = if executable { 0o755 } else { 0o644 };
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode))
            .map_err(|_| invalid_archive())?;
    }
    #[cfg(not(unix))]
    let _ = (path, executable);
    Ok(())
}

fn smoke_test(python: &Path) -> Result<(), RuntimeError> {
    if !python.is_file() {
        return Err(RuntimeError::new(
            "PYTHON_RUNTIME_INTERPRETER_MISSING",
            "The verified runtime did not contain its expected Python interpreter.",
        ));
    }
    // Capture the interpreter's output to a file rather than discarding it. A bare "did not pass its
    // import check" with no reason is unactionable, and this is the single most likely place for a
    // platform-specific failure to disappear: it is the first execution of a freshly downloaded,
    // unsigned binary, where macOS in particular can refuse or kill the process for reasons only the
    // child itself reports. A file rather than a pipe because the wait loop below uses try_wait, and a
    // filled pipe with no reader would deadlock.
    let transcript = std::env::temp_dir().join(format!(
        "callosum-runtime-smoke-{}-{}.log",
        std::process::id(),
        Instant::now().elapsed().as_nanos()
    ));
    let capture = File::create(&transcript).ok();
    let sink = |file: &Option<File>| match file.as_ref().and_then(|handle| handle.try_clone().ok())
    {
        Some(handle) => Stdio::from(handle),
        None => Stdio::null(),
    };
    let smoke_detail = |fallback: &str| -> String {
        let text = std::fs::read_to_string(&transcript).unwrap_or_default();
        let tail: String = text
            .lines()
            .rfind(|line| !line.trim().is_empty())
            .unwrap_or("")
            .chars()
            .take(300)
            .collect();
        if tail.is_empty() {
            fallback.to_string()
        } else {
            format!("{fallback} ({tail})")
        }
    };
    let mut child = Command::new(python)
        .args([
            "-c",
            "import fastapi,numpy,sentence_transformers,torch,uvicorn; print('callosum-runtime-ok')",
        ])
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .stdout(sink(&capture))
        .stderr(sink(&capture))
        .spawn()
        .map_err(|error| {
            let _ = std::fs::remove_file(&transcript);
            RuntimeError::new(
                "PYTHON_RUNTIME_SMOKE_START_FAILED",
                format!("The managed Python runtime could not start: {error}"),
            )
        })?;
    let deadline = Instant::now() + Duration::from_secs(180);
    loop {
        match child.try_wait() {
            Ok(Some(status)) if status.success() => {
                let _ = std::fs::remove_file(&transcript);
                return Ok(());
            }
            Ok(Some(status)) => {
                let detail = smoke_detail(&format!(
                    "The managed Python runtime did not pass its import check; it exited with {status}"
                ));
                let _ = std::fs::remove_file(&transcript);
                return Err(RuntimeError::new("PYTHON_RUNTIME_SMOKE_FAILED", detail));
            }
            Ok(None) if Instant::now() < deadline => std::thread::sleep(Duration::from_millis(100)),
            Ok(None) => {
                let _ = child.kill();
                let _ = child.wait();
                let detail = smoke_detail("The managed Python runtime import check timed out.");
                let _ = std::fs::remove_file(&transcript);
                return Err(RuntimeError::new("PYTHON_RUNTIME_SMOKE_TIMEOUT", detail));
            }
            Err(_) => {
                let _ = std::fs::remove_file(&transcript);
                return Err(RuntimeError::new(
                    "PYTHON_RUNTIME_SMOKE_FAILED",
                    "Callosum could not observe the managed Python runtime import check.",
                ));
            }
        }
    }
}

fn write_receipt(
    staging: &Path,
    trusted: &TrustedPlatform,
    manifest: &RuntimeManifest,
    manifest_sha256: &str,
) -> Result<(), RuntimeError> {
    let receipt = InstallReceipt {
        schema_version: 1,
        runtime_id: trusted.runtime_id.clone(),
        manifest_sha256: manifest_sha256.to_string(),
        archive_sha256: manifest.archive_sha256.clone(),
        tree_sha256: manifest.tree_sha256.clone(),
        python_relative_path: trusted.python_relative_path.clone(),
    };
    let bytes = serde_json::to_vec_pretty(&receipt).map_err(|_| invalid_archive())?;
    let path = staging.join(RECEIPT);
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(|_| invalid_archive())?;
    file.write_all(&bytes)
        .and_then(|_| file.sync_all())
        .map_err(|_| invalid_archive())
}

/// Reuse the runtime already inside an older installation instead of re-downloading it.
///
/// Not Windows-only: the point of this work is that updating should not mean re-fetching an
/// unchanged ~1.2 GB environment, and a macOS or Linux user upgrading from a bundled install has
/// that runtime sitting on disk exactly like a Windows user does. The logic is platform-agnostic —
/// resolve the legacy resource directory, require the tree digest to equal the signed manifest
/// exactly, then copy, smoke-test and activate. Anything short of an exact match returns `Ok(None)`
/// and provisioning falls through to the ordinary download, so being wrong here costs bandwidth,
/// never correctness.
fn try_migrate_legacy(
    app: &AppHandle,
    progress: ProgressSink,
    root: &Path,
    final_dir: &Path,
    trusted: &TrustedPlatform,
    manifest: &RuntimeManifest,
    manifest_sha256: &str,
) -> Result<Option<PathBuf>, RuntimeError> {
    let legacy = match app
        .path()
        .resolve("python-runtime", BaseDirectory::Resource)
    {
        Ok(path) if path.is_dir() => path,
        _ => return Ok(None),
    };
    progress(
        "runtime_migration",
        "Reusing the Python runtime from your current Callosum installation…",
        None,
        None,
    );
    let entries = filesystem_entries(&legacy)?;
    if entries.len() as u64 != manifest.entry_count
        || entries.iter().map(|entry| entry.size).sum::<u64>() != manifest.unpacked_bytes
        || tree_digest(&entries) != manifest.tree_sha256
    {
        return Ok(None);
    }
    let staging = root.join(format!(
        ".{}.legacy-staging-{}",
        trusted.runtime_id,
        std::process::id()
    ));
    if staging.exists() {
        let _ = std::fs::remove_dir_all(&staging);
    }
    copy_directory(&legacy, &staging)?;
    smoke_test(&staging.join(&trusted.python_relative_path))?;
    write_receipt(&staging, trusted, manifest, manifest_sha256)?;
    if final_dir.exists() {
        std::fs::remove_dir_all(final_dir).map_err(|_| {
            RuntimeError::new(
                "PYTHON_RUNTIME_INVALID_REPAIR_FAILED",
                "Callosum could not replace an incomplete runtime.",
            )
        })?;
    }
    std::fs::rename(&staging, final_dir).map_err(|_| {
        RuntimeError::new(
            "PYTHON_RUNTIME_ACTIVATION_FAILED",
            "Callosum could not activate the migrated runtime.",
        )
    })?;
    Ok(Some(final_dir.join(&trusted.python_relative_path)))
}

/// Describe an on-disk runtime tree in exactly the terms `tree_digest` expects.
///
/// Must mirror `extract_verified`'s rules precisely, since the whole point is to compare the result
/// against the signed `tree_sha256`. Two of those rules are genuinely platform-specific and were the
/// reason this was originally Windows-only:
///
/// * **Executability.** On Unix it is the mode bit (`0o111`), matching what `extract_verified` reads
///   from the tar header. On Windows there is no such bit, so the packager's convention -- PATHEXT
///   launcher extensions -- is what a byte-identical legacy bundle will have been recorded with.
/// * **Symlinks.** The Unix runtime really does contain them (`bin/python3 -> python3.11`), so they
///   are recorded as `kind: "link"` with the target as identity, exactly as extraction does. On
///   Windows a symlink in this tree is unexpected and still fails closed.
fn filesystem_entries(root: &Path) -> Result<Vec<TreeEntry>, RuntimeError> {
    fn visit(
        root: &Path,
        current: &Path,
        entries: &mut Vec<TreeEntry>,
    ) -> Result<(), RuntimeError> {
        for item in std::fs::read_dir(current).map_err(|_| invalid_archive())? {
            let path = item.map_err(|_| invalid_archive())?.path();
            let metadata = std::fs::symlink_metadata(&path).map_err(|_| invalid_archive())?;
            let relative = || -> Result<String, RuntimeError> {
                Ok(path
                    .strip_prefix(root)
                    .map_err(|_| invalid_archive())?
                    .to_str()
                    .ok_or_else(invalid_archive)?
                    .replace('\\', "/"))
            };
            if metadata.is_dir() {
                visit(root, &path, entries)?;
                continue;
            }
            #[cfg(unix)]
            if metadata.file_type().is_symlink() {
                let target = std::fs::read_link(&path).map_err(|_| invalid_archive())?;
                entries.push(TreeEntry {
                    relative: relative()?,
                    kind: "link",
                    size: 0,
                    identity: target.to_str().ok_or_else(invalid_archive)?.to_string(),
                    executable: false,
                });
                continue;
            }
            if !metadata.is_file() {
                return Err(invalid_archive());
            }
            #[cfg(unix)]
            let executable = {
                use std::os::unix::fs::PermissionsExt;
                metadata.permissions().mode() & 0o111 != 0
            };
            #[cfg(not(unix))]
            let executable = path.extension().is_some_and(|extension| {
                matches!(
                    extension.to_string_lossy().to_ascii_lowercase().as_str(),
                    "exe" | "com" | "bat" | "cmd"
                )
            });
            entries.push(TreeEntry {
                relative: relative()?,
                kind: "file",
                size: metadata.len(),
                identity: sha256_file(&path)?,
                executable,
            });
        }
        Ok(())
    }
    let mut entries = Vec::new();
    visit(root, root, &mut entries)?;
    entries.sort_by(|left, right| left.relative.cmp(&right.relative));
    Ok(entries)
}

fn copy_directory(source: &Path, destination: &Path) -> Result<(), RuntimeError> {
    std::fs::create_dir(destination).map_err(|_| invalid_archive())?;
    for item in std::fs::read_dir(source).map_err(|_| invalid_archive())? {
        let path = item.map_err(|_| invalid_archive())?.path();
        let target = destination.join(path.file_name().ok_or_else(invalid_archive)?);
        let metadata = std::fs::symlink_metadata(&path).map_err(|_| invalid_archive())?;
        if metadata.is_dir() {
            copy_directory(&path, &target)?;
            continue;
        }
        // The Unix runtime contains real symlinks; recreate them rather than dereferencing, so the
        // copy still digests to the same tree identity the signed manifest describes.
        #[cfg(unix)]
        if metadata.file_type().is_symlink() {
            let link = std::fs::read_link(&path).map_err(|_| invalid_archive())?;
            std::os::unix::fs::symlink(link, &target).map_err(|_| invalid_archive())?;
            continue;
        }
        if !metadata.is_file() {
            return Err(invalid_archive());
        }
        // fs::copy carries the permission bits on Unix, so the executable bit -- which is part of the
        // tree identity there -- survives the migration.
        std::fs::copy(&path, &target).map_err(|_| invalid_archive())?;
    }
    Ok(())
}

fn sha256_file(path: &Path) -> Result<String, RuntimeError> {
    let mut file = File::open(path).map_err(|_| invalid_archive())?;
    let mut digest = Sha256::new();
    let mut buffer = vec![0_u8; DOWNLOAD_BUFFER_BYTES];
    loop {
        let read = file.read(&mut buffer).map_err(|_| invalid_archive())?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn invalid_archive() -> RuntimeError {
    RuntimeError::new(
        "PYTHON_RUNTIME_ARCHIVE_INVALID",
        "The Python runtime archive contained an invalid or unsafe entry.",
    )
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn is_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn download_host_allowed(host: &str) -> bool {
    host == "github.com"
        || host == "release-assets.githubusercontent.com"
        || host == "objects.githubusercontent.com"
}

fn emit_progress(
    app: &AppHandle,
    state: &str,
    detail: &str,
    downloaded_bytes: Option<u64>,
    total_bytes: Option<u64>,
) {
    let _ = app.emit_to(
        "splash",
        "backend-status",
        serde_json::json!({
            "state": state,
            "detail": detail,
            "downloaded_bytes": downloaded_bytes,
            "total_bytes": total_bytes,
        }),
    );
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn trusted_runtime_id_is_not_the_application_version() {
        let trusted = trusted_platform().unwrap();
        assert!(trusted.runtime_id.contains("-py3.11-s1-"));
        assert!(!trusted.runtime_id.contains("0.5.4"));
        assert_eq!(
            trusted.runtime_id.len(),
            trusted.runtime_id.rfind('-').unwrap() + 17
        );
    }

    #[test]
    fn receipt_requires_matching_identity_and_interpreter() {
        let root = std::env::temp_dir().join(format!(
            "callosum-python-runtime-receipt-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let trusted = trusted_platform().unwrap();
        assert!(!receipt_is_valid(&root, &trusted));
        std::fs::write(root.join(RECEIPT), b"not json").unwrap();
        assert!(!receipt_is_valid(&root, &trusted));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn archive_paths_reject_traversal_and_wrong_root() {
        assert_eq!(
            archive_relative_path(Path::new("python-runtime/bin/python3")).unwrap(),
            PathBuf::from("bin/python3")
        );
        assert!(archive_relative_path(Path::new("other/bin/python3")).is_err());
        assert!(archive_relative_path(Path::new("python-runtime/../outside")).is_err());
        assert!(validate_link_target(Path::new("lib/a"), "../../outside").is_err());
        assert!(validate_link_target(Path::new("lib/a"), "../inside").is_ok());
        assert!(validate_link_target(Path::new("lib/a"), "/outside").is_err());
    }

    #[test]
    fn manifest_validation_is_exact_and_bounded() {
        let trusted = trusted_platform().unwrap();
        let tag = format!("python-runtime-{}", trusted.runtime_id);
        let mut manifest = RuntimeManifest {
            schema_version: 1,
            packaging_schema: "callosum-python-runtime-v1".into(),
            runtime_id: trusted.runtime_id.clone(),
            platform: trusted.os.clone(),
            arch: trusted.arch.clone(),
            python_version: trusted.python_version.clone(),
            python_build: trusted.python_build.clone(),
            python_relative_path: trusted.python_relative_path.clone(),
            archive_url: format!("{RELEASE_BASE}/{tag}/{}.tar.gz", trusted.runtime_id),
            archive_bytes: 1,
            archive_sha256: "a".repeat(64),
            tree_sha256: "b".repeat(64),
            entry_count: 1,
            unpacked_bytes: 1,
            glibc_min: trusted.glibc_min.clone(),
            distribution_boundary: trusted.distribution_boundary.clone(),
        };
        assert!(validate_manifest(&manifest, &trusted, &tag).is_ok());
        manifest.runtime_id.push_str("-wrong");
        assert!(validate_manifest(&manifest, &trusted, &tag).is_err());
        manifest.runtime_id = trusted.runtime_id.clone();

        // archive_url is the field that decides where ~365 MB of executable content is fetched from,
        // so it must be pinned to a value this build computes rather than trusted from the document.
        // Signing alone would not help if the signer were ever compromised or misused.
        for hostile in [
            "https://example.invalid/evil.tar.gz",
            // Same allowlisted host, attacker-chosen path -- host checks alone would pass this.
            &format!(
                "{RELEASE_BASE}/python-runtime-other/{}.tar.gz",
                trusted.runtime_id
            ),
        ] {
            manifest.archive_url = hostile.to_string();
            assert!(
                validate_manifest(&manifest, &trusted, &tag).is_err(),
                "archive_url {hostile} must be rejected"
            );
        }
    }

    #[test]
    fn symlink_targets_may_not_escape_the_runtime_root() {
        // A tar symlink is the classic way to write outside an extraction root. Nothing covered this
        // despite validate_link_target being the only thing standing in front of it.
        for (relative, target) in [
            ("bin/python3", "../../../../etc/passwd"),
            ("bin/python3", "/etc/passwd"),
            ("python3", ".."),
            ("bin/python3", "..\\..\\windows"),
            ("bin/python3", ""),
        ] {
            assert!(
                validate_link_target(Path::new(relative), target).is_err(),
                "escaping link {relative} -> {target} must be rejected"
            );
        }
        // Ordinary in-tree links remain valid: python-build-standalone ships bin/python3 as one.
        for (relative, target) in [("bin/python3", "python3.11"), ("bin/python3", "../lib/x")] {
            assert!(
                validate_link_target(Path::new(relative), target).is_ok(),
                "in-tree link {relative} -> {target} must be accepted"
            );
        }
    }

    #[test]
    fn updater_public_key_is_valid_but_bad_signature_is_rejected() {
        PublicKey::decode(PUBLIC_KEY).unwrap();
        assert!(verify_manifest_signature(b"manifest", b"not a signature").is_err());
    }

    #[test]
    fn compatibility_versions_compare_numerically() {
        assert!(version_pair("2.36") >= version_pair("2.35"));
        assert!(version_pair("2.9") < version_pair("2.35"));
    }

    #[test]
    fn tree_digest_uses_canonical_ordered_lines() {
        let entries = vec![TreeEntry {
            relative: "bin/python3".into(),
            kind: "file",
            size: 3,
            identity: "a".repeat(64),
            executable: true,
        }];
        assert_eq!(tree_digest(&entries), tree_digest(&entries));
        assert_ne!(tree_digest(&entries), tree_digest(&[]));
    }

    #[test]
    fn staging_activation_is_atomic_and_replaces_only_invalid_target() {
        let root = std::env::temp_dir().join(format!(
            "callosum-python-runtime-activation-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        let staging = root.join("staging");
        let target = root.join("target");
        std::fs::create_dir_all(&staging).unwrap();
        std::fs::write(staging.join("new"), b"new").unwrap();
        std::fs::create_dir_all(&target).unwrap();
        std::fs::write(target.join("incomplete"), b"old").unwrap();

        activate_staging(&staging, &target, &trusted_platform().unwrap()).unwrap();
        assert!(target.join("new").is_file());
        assert!(!target.join("incomplete").exists());
        assert!(!staging.exists());
        let _ = std::fs::remove_dir_all(root);
    }

    /// The signature this project actually publishes, verified by the code that actually runs.
    ///
    /// Every other test here builds its own fixtures, so nothing exercised the one contract that
    /// cannot be assumed: `tauri signer sign` writes the `.sig` file **base64-encoded**, while
    /// `minisign_verify::Signature::decode` expects plain minisign text. A mismatch there rejects
    /// every genuine runtime, on every platform, with no bundled Python left to fall back on.
    #[test]
    fn published_manifest_signature_verifies_against_the_builtin_key() {
        let trusted = trusted_platform().unwrap();
        let tag = format!("python-runtime-{}", trusted.runtime_id);
        let manifest_url = format!("{RELEASE_BASE}/{tag}/runtime-manifest.json");
        let client = download_client().unwrap();

        let manifest = match download_small(&client, &manifest_url, MAX_MANIFEST_BYTES) {
            Ok(bytes) => bytes,
            // Offline or the artifact is not published for this platform yet: skip rather than
            // fail, so a disconnected `cargo test` stays green. The gate that matters is CI.
            Err(_) => return,
        };
        let signature =
            download_small(&client, &format!("{manifest_url}.sig"), MAX_SIGNATURE_BYTES).unwrap();

        verify_manifest_signature(&manifest, &signature).expect(
            "the published runtime manifest must verify against the built-in key -- if this fails, \
             first-run provisioning is broken for every user",
        );
    }

    /// The whole first-run path, against the artifact users will actually receive.
    ///
    /// Ignored because it downloads ~365 MB and unpacks ~1.2 GB; run it deliberately with
    /// `cargo test -- --ignored provisions_the_published_runtime`. It is the only thing that proves
    /// a fresh install ends up with a working interpreter, which since `python-runtime` left
    /// `bundle.resources` is the difference between a working app and a dead one.
    #[test]
    #[ignore = "downloads and unpacks the real published Python runtime (~365 MB / ~1.2 GB)"]
    fn provisions_the_published_runtime_end_to_end() {
        let local_data = std::env::temp_dir().join(format!(
            "callosum-runtime-e2e-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs()
        ));
        std::fs::create_dir_all(&local_data).unwrap();

        let stages = std::sync::Mutex::new(Vec::new());
        let record = |stage: &str, _message: &str, _done: Option<u64>, _total: Option<u64>| {
            let mut seen = stages.lock().unwrap();
            if seen.last().map(String::as_str) != Some(stage) {
                seen.push(stage.to_string());
            }
        };

        let python = provision_into(&local_data, &record, None).expect("provisioning must succeed");

        assert!(python.is_file(), "interpreter missing at {python:?}");
        // The receipt is what makes a second launch skip all of this; without it every start would
        // re-provision, which is the cost this whole architecture exists to remove.
        let trusted = trusted_platform().unwrap();
        assert!(receipt_is_valid(
            &final_runtime_dir(&local_data, &trusted),
            &trusted
        ));
        // Idempotence: provisioning again must reuse the installed runtime, not redownload it.
        let again = provision_into(&local_data, &record, None).unwrap();
        assert_eq!(python, again);

        let seen = stages.lock().unwrap().clone();
        assert!(seen.contains(&"runtime_download".to_string()), "{seen:?}");
        assert!(seen.contains(&"runtime_ready".to_string()), "{seen:?}");

        let _ = std::fs::remove_dir_all(&local_data);
    }
}
