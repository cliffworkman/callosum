//! Safe extraction for the pinned official llama.cpp macOS arm64 archive.

use super::install::RUNTIME_DIR;
use super::ManagedAiError;
use flate2::read::GzDecoder;
use std::fs::{File, OpenOptions};
use std::io::{BufReader, Write};
use std::os::unix::fs::{symlink, OpenOptionsExt, PermissionsExt};
use std::path::{Component, Path};

const ARCHIVE_ROOT: &str = "llama-b10516";
const LAUNCHER: &str = "llama-server";

pub(super) fn extract_runtime(root: &Path, archive_path: &Path) -> Result<(), ManagedAiError> {
    let staging = root.join(format!("{RUNTIME_DIR}.partial"));
    if staging.exists() {
        std::fs::remove_dir_all(&staging)
            .map_err(|_| ManagedAiError::Io("partial Local AI runtime could not be reset"))?;
    }
    std::fs::create_dir(&staging)
        .map_err(|_| ManagedAiError::Io("Local AI runtime staging failed"))?;
    std::fs::set_permissions(&staging, std::fs::Permissions::from_mode(0o700))
        .map_err(|_| ManagedAiError::Io("Local AI runtime staging permissions failed"))?;

    let file = File::open(archive_path)
        .map_err(|_| ManagedAiError::Io("Local AI runtime archive missing"))?;
    let mut archive = tar::Archive::new(GzDecoder::new(BufReader::new(file)));
    let mut launcher_found = false;
    let mut links = Vec::new();
    let entries = archive
        .entries()
        .map_err(|_| ManagedAiError::Io("Local AI runtime archive invalid"))?;
    for item in entries {
        let mut entry = item.map_err(|_| ManagedAiError::Io("Local AI runtime archive invalid"))?;
        let name = {
            let path = entry
                .path()
                .map_err(|_| ManagedAiError::Io("Local AI runtime archive path invalid"))?;
            archive_entry_name(&path)?.map(str::to_owned)
        };
        let Some(name) = name else {
            continue;
        };
        if !runtime_entry_allowed(&name) {
            continue;
        }
        let kind = entry.header().entry_type();
        if kind.is_file() {
            let destination = staging.join(&name);
            let mut output = OpenOptions::new()
                .write(true)
                .create_new(true)
                .mode(if name == LAUNCHER { 0o700 } else { 0o600 })
                .open(&destination)
                .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
            std::io::copy(&mut entry, &mut output)
                .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
            output
                .flush()
                .and_then(|_| output.sync_all())
                .map_err(|_| ManagedAiError::Io("Local AI runtime extraction failed"))?;
            launcher_found |= name == LAUNCHER;
        } else if kind.is_symlink() {
            let target = entry
                .link_name()
                .map_err(|_| ManagedAiError::Io("Local AI runtime link invalid"))?
                .ok_or(ManagedAiError::Io("Local AI runtime link invalid"))?;
            let target = single_safe_name(&target)?;
            if !runtime_entry_allowed(target) {
                return Err(ManagedAiError::Io("Local AI runtime link target invalid"));
            }
            links.push((name, target.to_owned()));
        } else {
            return Err(ManagedAiError::Io("Local AI runtime archive entry invalid"));
        }
    }
    if !launcher_found {
        return Err(ManagedAiError::Io("Local AI runtime launcher missing"));
    }
    links.sort();
    for (name, target) in links {
        symlink(&target, staging.join(name))
            .map_err(|_| ManagedAiError::Io("Local AI runtime link creation failed"))?;
    }
    validate_runtime_links(&staging)?;
    let final_dir = root.join(RUNTIME_DIR);
    if final_dir.exists() {
        std::fs::remove_dir_all(&final_dir)
            .map_err(|_| ManagedAiError::Io("Local AI runtime repair failed"))?;
    }
    std::fs::rename(&staging, &final_dir)
        .map_err(|_| ManagedAiError::Io("Local AI runtime promotion failed"))?;
    Ok(())
}

fn archive_entry_name(path: &Path) -> Result<Option<&str>, ManagedAiError> {
    let mut components = path.components();
    let Some(Component::Normal(root)) = components.next() else {
        return Err(ManagedAiError::Io("Local AI runtime archive path invalid"));
    };
    if root != ARCHIVE_ROOT {
        return Err(ManagedAiError::Io("Local AI runtime archive root invalid"));
    }
    let Some(Component::Normal(name)) = components.next() else {
        return Ok(None);
    };
    if components.next().is_some() {
        return Err(ManagedAiError::Io("Local AI runtime archive path invalid"));
    }
    name.to_str()
        .map(Some)
        .ok_or(ManagedAiError::Io("Local AI runtime archive path invalid"))
}

fn single_safe_name(path: &Path) -> Result<&str, ManagedAiError> {
    let mut components = path.components();
    let Some(Component::Normal(name)) = components.next() else {
        return Err(ManagedAiError::Io("Local AI runtime link target invalid"));
    };
    if components.next().is_some() {
        return Err(ManagedAiError::Io("Local AI runtime link target invalid"));
    }
    name.to_str()
        .ok_or(ManagedAiError::Io("Local AI runtime link target invalid"))
}

fn runtime_entry_allowed(name: &str) -> bool {
    name == LAUNCHER || name.to_ascii_lowercase().ends_with(".dylib")
}

fn validate_runtime_links(root: &Path) -> Result<(), ManagedAiError> {
    let canonical_root = std::fs::canonicalize(root)
        .map_err(|_| ManagedAiError::Io("Local AI runtime staging failed"))?;
    for item in std::fs::read_dir(root)
        .map_err(|_| ManagedAiError::Io("Local AI runtime staging failed"))?
    {
        let path = item
            .map_err(|_| ManagedAiError::Io("Local AI runtime staging failed"))?
            .path();
        if path
            .file_name()
            .and_then(|name| name.to_str())
            .is_none_or(|name| !runtime_entry_allowed(name))
        {
            continue;
        }
        let canonical = std::fs::canonicalize(path)
            .map_err(|_| ManagedAiError::Io("Local AI runtime link invalid"))?;
        if !canonical.starts_with(&canonical_root) || !canonical.is_file() {
            return Err(ManagedAiError::Io("Local AI runtime link escapes its root"));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn archive_boundary_accepts_only_the_pinned_root_and_runtime_files() {
        assert_eq!(
            archive_entry_name(Path::new("llama-b10516/llama-server")).unwrap(),
            Some("llama-server")
        );
        assert!(runtime_entry_allowed("libggml-metal.0.20.2.dylib"));
        assert!(!runtime_entry_allowed("llama-cli"));
        assert!(archive_entry_name(Path::new("../llama-server")).is_err());
        assert!(archive_entry_name(Path::new("other/llama-server")).is_err());
        assert!(archive_entry_name(Path::new("llama-b10516/nested/llama-server")).is_err());
        assert!(single_safe_name(Path::new("../outside.dylib")).is_err());
    }
}
