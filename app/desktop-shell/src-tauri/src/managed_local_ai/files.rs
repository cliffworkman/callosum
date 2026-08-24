//! Private-file, ACL, and immutable runtime-identity helpers for the managed local AI owner.

use super::ManagedAiError;
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{BufReader, Read, Write};
use std::path::Path;
use std::process::{Command, Stdio};

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
    let mut buffer = [0_u8; 1024 * 1024];
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
