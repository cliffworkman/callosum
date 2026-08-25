//! Private-file, ACL, and immutable runtime-identity helpers for the managed local AI owner.

use super::ManagedAiError;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{BufReader, Read, Write};
use std::path::{Component, Path};
use std::process::{Command, Stdio};

const DIGEST_BUFFER_BYTES: usize = 64 * 1024;
const MANIFEST_VERSION: &str = "callosum-managed-runtime-bundle-v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub(super) struct RuntimeBundleIdentity {
    pub(super) launcher_digest: String,
    pub(super) manifest_digest: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ManifestEntry {
    relative_path: String,
    size: u64,
    digest: String,
}

pub(super) fn random_token() -> Result<String, ManagedAiError> {
    let mut bytes = [0_u8; 32];
    getrandom::fill(&mut bytes)
        .map_err(|_| ManagedAiError::Io("secure token generation failed"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

pub(super) fn prepare_private_dir(path: &Path) -> Result<(), ManagedAiError> {
    std::fs::create_dir_all(path)
        .map_err(|_| ManagedAiError::Io("private runtime directory creation failed"))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o700))
            .map_err(|_| ManagedAiError::Io("private runtime directory permissions failed"))?;
    }
    #[cfg(windows)]
    restrict_windows_acl(path, true)?;
    Ok(())
}

pub(super) fn write_private_file(path: &Path, bytes: &[u8]) -> Result<(), ManagedAiError> {
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(path)
        .map_err(|_| ManagedAiError::Io("private runtime file creation failed"))?;
    if file.write_all(bytes).and_then(|_| file.flush()).is_err() {
        drop(file);
        remove_private_file(path);
        return Err(ManagedAiError::Io("private runtime file write failed"));
    }
    #[cfg(windows)]
    if let Err(error) = restrict_windows_acl(path, false) {
        drop(file);
        remove_private_file(path);
        return Err(error);
    }
    Ok(())
}

#[cfg(windows)]
fn restrict_windows_acl(path: &Path, directory: bool) -> Result<(), ManagedAiError> {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let identity = Command::new("whoami")
        .args(["/user", "/fo", "csv", "/nh"])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .map_err(|_| ManagedAiError::Io("private runtime ACL identity failed"))?;
    let text = String::from_utf8_lossy(&identity.stdout);
    let sid = text
        .trim()
        .trim_matches('"')
        .split("\",\"")
        .nth(1)
        .filter(|value| value.starts_with("S-1-"))
        .ok_or(ManagedAiError::Io("private runtime ACL identity failed"))?;
    let grant = if directory {
        format!("*{sid}:(OI)(CI)F")
    } else {
        format!("*{sid}:F")
    };
    let status = Command::new("icacls")
        .arg(path)
        .args(["/inheritance:r", "/grant:r", &grant])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map_err(|_| ManagedAiError::Io("private runtime ACL update failed"))?;
    if !status.success() {
        return Err(ManagedAiError::Io("private runtime ACL update failed"));
    }
    Ok(())
}

pub(super) fn remove_private_file(path: &Path) {
    if path.is_file() {
        let _ = std::fs::remove_file(path);
    }
}

pub(super) fn digest_file(path: &Path) -> Result<String, ManagedAiError> {
    let file = File::open(path).map_err(|_| ManagedAiError::Io("runtime identity read failed"))?;
    let mut reader = BufReader::new(file);
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; DIGEST_BUFFER_BYTES];
    loop {
        let read = reader
            .read(&mut buffer)
            .map_err(|_| ManagedAiError::Io("runtime identity read failed"))?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

pub(super) fn runtime_bundle_identity(
    runtime: &Path,
) -> Result<RuntimeBundleIdentity, ManagedAiError> {
    let runtime = std::fs::canonicalize(runtime)
        .map_err(|_| ManagedAiError::Io("runtime bundle root is invalid"))?;
    let root = runtime
        .parent()
        .ok_or(ManagedAiError::Io("runtime bundle root is invalid"))?;
    let root = std::fs::canonicalize(root)
        .map_err(|_| ManagedAiError::Io("runtime bundle root is invalid"))?;
    let mut entries = Vec::new();
    for item in std::fs::read_dir(&root)
        .map_err(|_| ManagedAiError::Io("runtime bundle enumeration failed"))?
    {
        let path = item
            .map_err(|_| ManagedAiError::Io("runtime bundle enumeration failed"))?
            .path();
        if path != runtime && !is_runtime_library(&path) {
            continue;
        }
        let relative_path = safe_bundle_relative_path(&root, &path)?;
        let canonical = std::fs::canonicalize(&path)
            .map_err(|_| ManagedAiError::Io("runtime bundle entry is invalid"))?;
        if !canonical.starts_with(&root) || !canonical.is_file() {
            return Err(ManagedAiError::Io("runtime bundle entry escapes its root"));
        }
        let size = std::fs::metadata(&canonical)
            .map_err(|_| ManagedAiError::Io("runtime bundle entry is invalid"))?
            .len();
        entries.push(ManifestEntry {
            relative_path,
            size,
            digest: digest_file(&canonical)?,
        });
    }
    entries.sort_by(|left, right| left.relative_path.cmp(&right.relative_path));
    if !entries.iter().any(|entry| {
        runtime
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| entry.relative_path == name)
    }) {
        return Err(ManagedAiError::Io("runtime launcher is absent from bundle"));
    }
    let launcher_digest = digest_file(&runtime)?;
    Ok(RuntimeBundleIdentity {
        launcher_digest,
        manifest_digest: digest_manifest_entries(&entries),
    })
}

fn is_runtime_library(path: &Path) -> bool {
    let Some(name) = path.file_name().and_then(|value| value.to_str()) else {
        return false;
    };
    let lower = name.to_ascii_lowercase();
    lower.ends_with(".dll")
        || lower.ends_with(".dylib")
        || (["libggml", "libllama", "libmtmd"]
            .iter()
            .any(|prefix| lower.starts_with(prefix))
            && lower.contains(".so"))
}

fn safe_bundle_relative_path(root: &Path, path: &Path) -> Result<String, ManagedAiError> {
    let relative = path
        .strip_prefix(root)
        .map_err(|_| ManagedAiError::Io("runtime bundle entry escapes its root"))?;
    let mut components = relative.components();
    let Some(Component::Normal(name)) = components.next() else {
        return Err(ManagedAiError::Io("runtime bundle entry is invalid"));
    };
    if components.next().is_some() {
        return Err(ManagedAiError::Io("runtime bundle entry is invalid"));
    }
    name.to_str()
        .map(str::to_owned)
        .ok_or(ManagedAiError::Io("runtime bundle entry name is invalid"))
}

fn digest_manifest_entries(entries: &[ManifestEntry]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(MANIFEST_VERSION.as_bytes());
    hasher.update(b"\n");
    for entry in entries {
        hasher.update(entry.relative_path.as_bytes());
        hasher.update(b"\t");
        hasher.update(entry.size.to_string().as_bytes());
        hasher.update(b"\t");
        hasher.update(entry.digest.as_bytes());
        hasher.update(b"\n");
    }
    format!("{:x}", hasher.finalize())
}

pub(super) fn digest_bytes(value: &str) -> String {
    format!("{:x}", Sha256::digest(value.as_bytes()))
}

pub(super) fn runtime_version(runtime: &Path) -> Result<String, ManagedAiError> {
    let output = Command::new(runtime)
        .arg("--version")
        .stdin(Stdio::null())
        .output()
        .map_err(|_| ManagedAiError::Io("runtime version probe failed"))?;
    let combined = format!(
        "{} {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let version = combined
        .lines()
        .map(str::trim)
        .find(|line| line.contains("version") || line.contains("build"))
        .unwrap_or("unknown")
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric() || " ._()-".contains(*ch))
        .take(160)
        .collect::<String>();
    Ok(if version.is_empty() {
        "unknown".into()
    } else {
        version
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_dir(label: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!(
            "callosum-files-{label}-{}",
            random_token().expect("test token")
        ));
        std::fs::create_dir_all(&root).expect("test directory");
        root
    }

    fn write_large_file(path: &Path) {
        let mut file = File::create(path).expect("large test file");
        let chunk = vec![0x5a_u8; 64 * 1024];
        for _ in 0..128 {
            file.write_all(&chunk).expect("large test write");
        }
    }

    #[test]
    fn streaming_digest_handles_empty_tiny_and_large_files_deterministically() {
        let root = test_dir("digest");
        let empty = root.join("empty");
        let tiny = root.join("tiny");
        let large = root.join("large");
        File::create(&empty).unwrap();
        std::fs::write(&tiny, b"abc").unwrap();
        write_large_file(&large);

        assert_eq!(
            digest_file(&empty).unwrap(),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
        assert_eq!(
            digest_file(&tiny).unwrap(),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        assert_eq!(digest_file(&large).unwrap(), digest_file(&large).unwrap());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn large_digest_succeeds_on_a_stack_smaller_than_the_old_buffer() {
        let root = test_dir("small-stack");
        let large = root.join("large");
        write_large_file(&large);
        let expected = digest_file(&large).unwrap();
        let worker_path = large.clone();
        let actual = std::thread::Builder::new()
            .stack_size(512 * 1024)
            .spawn(move || digest_file(&worker_path).unwrap())
            .unwrap()
            .join()
            .unwrap();
        assert_eq!(actual, expected);
        std::fs::remove_dir_all(root).unwrap();
    }

    fn create_bundle(root: &Path, backend_bytes: &[u8], reverse: bool) -> std::path::PathBuf {
        let runtime = root.join(if cfg!(windows) {
            "llama-server.exe"
        } else {
            "llama-server"
        });
        let entries = [
            (runtime.clone(), b"same launcher".to_vec()),
            (root.join("backend.dll"), backend_bytes.to_vec()),
            (root.join("llama.dll"), b"shared".to_vec()),
        ];
        let indices: &[usize] = if reverse { &[2, 1, 0] } else { &[0, 1, 2] };
        for index in indices {
            std::fs::write(&entries[*index].0, &entries[*index].1).unwrap();
        }
        runtime
    }

    #[test]
    fn bundle_manifest_is_ordered_root_independent_and_backend_sensitive() {
        let first = test_dir("bundle-first");
        let second = test_dir("bundle-second");
        let third = test_dir("bundle-third");
        let first_runtime = create_bundle(&first, b"cpu backend", false);
        let second_runtime = create_bundle(&second, b"cpu backend", true);
        let third_runtime = create_bundle(&third, b"cuda backend", false);

        let first_identity = runtime_bundle_identity(&first_runtime).unwrap();
        let second_identity = runtime_bundle_identity(&second_runtime).unwrap();
        let third_identity = runtime_bundle_identity(&third_runtime).unwrap();
        assert_eq!(first_identity, second_identity);
        assert_eq!(
            first_identity.launcher_digest,
            third_identity.launcher_digest
        );
        assert_ne!(
            first_identity.manifest_digest,
            third_identity.manifest_digest
        );

        for root in [first, second, third] {
            std::fs::remove_dir_all(root).unwrap();
        }
    }

    #[test]
    fn bundle_relative_paths_reject_traversal_and_nested_entries() {
        let root = Path::new("runtime-root");
        assert!(safe_bundle_relative_path(root, &root.join("..\u{2f}outside.dll")).is_err());
        assert!(safe_bundle_relative_path(root, &root.join("nested").join("backend.dll")).is_err());
        assert_eq!(
            safe_bundle_relative_path(root, &root.join("backend.dll")).unwrap(),
            "backend.dll"
        );
    }

    #[cfg(unix)]
    #[test]
    fn bundle_manifest_rejects_symlink_escape() {
        use std::os::unix::fs::symlink;
        let root = test_dir("escape-root");
        let outside = test_dir("escape-outside");
        let runtime = root.join("llama-server");
        std::fs::write(&runtime, b"runtime").unwrap();
        let outside_library = outside.join("backend.dll");
        std::fs::write(&outside_library, b"outside").unwrap();
        symlink(&outside_library, root.join("backend.dll")).unwrap();
        assert!(runtime_bundle_identity(&runtime).is_err());
        std::fs::remove_dir_all(root).unwrap();
        std::fs::remove_dir_all(outside).unwrap();
    }
}
