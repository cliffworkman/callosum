//! Verified embedded bytes -> one stable managed directory. Never accepts a caller path.
use crate::preview_state::{plain, write};
use base64::Engine;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, path::Path};

pub const PACKAGE: &str = include_str!("../../connector/preview-package.json");
const FILES: &[&str] = &[
    "background.js",
    "manifest.json",
    "options.html",
    "options.js",
    "icons/icon16.png",
    "icons/icon32.png",
    "icons/icon48.png",
    "icons/icon128.png",
];

#[derive(Deserialize)]
pub struct Entry {
    pub sha256: String,
    pub base64: String,
}
#[derive(Deserialize)]
pub struct Package {
    pub version: String,
    pub extension_id: String,
    pub sha256: String,
    pub files: BTreeMap<String, Entry>,
}
#[derive(Serialize, Deserialize)]
pub struct Receipt {
    pub version: String,
    pub sha256: String,
    pub files: BTreeMap<String, String>,
}
pub fn package() -> Package {
    serde_json::from_str(PACKAGE).expect("verified embedded preview package")
}
pub fn hash(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn ensure_root(root: &Path) -> Result<(), String> {
    // Reject symlinks/junctions at every existing ancestor before creating anything.
    for parent in root.ancestors() {
        if parent.exists() && !plain(parent) {
            return Err("Preview path contains a link or reparse point.".into());
        }
    }
    std::fs::create_dir_all(root).map_err(|_| "Cannot create the managed preview directory.")?;
    Ok(())
}

fn inspect(dir: &Path, prefix: &str, found: &mut Vec<String>) -> Result<(), String> {
    if !plain(dir) {
        return Err("Preview folder contains a link. Files left untouched.".into());
    }
    for entry in std::fs::read_dir(dir).map_err(|_| "Cannot inspect preview files.")? {
        let path = entry.map_err(|_| "Cannot inspect preview entry.")?.path();
        if !plain(&path) {
            return Err("Preview contains a link/reparse point; files left untouched.".into());
        }
        let name = path
            .file_name()
            .and_then(|s| s.to_str())
            .ok_or("Unexpected preview filename.")?;
        let relative = format!("{prefix}{name}");
        if path.is_dir() {
            if relative != "icons" {
                return Err("Unexpected preview directory; files left untouched.".into());
            }
            inspect(&path, "icons/", found)?;
        } else if path.is_file() {
            found.push(relative);
        } else {
            return Err("Unexpected preview file type.".into());
        }
    }
    Ok(())
}

pub fn verified(root: &Path) -> Result<Receipt, String> {
    if !plain(root) || !plain(&root.join("receipt.json")) {
        return Err("Prepare the extension first.".into());
    }
    if std::fs::metadata(root.join("receipt.json"))
        .map_err(|_| "Missing preview receipt.")?
        .len()
        > 8192
    {
        return Err("Invalid preview receipt.".into());
    }
    let bytes = std::fs::read(root.join("receipt.json")).map_err(|_| "Missing preview receipt.")?;
    if bytes.len() > 8192 {
        return Err("Invalid preview receipt.".into());
    }
    let receipt: Receipt =
        serde_json::from_slice(&bytes).map_err(|_| "Invalid preview receipt.")?;
    let mut names = Vec::new();
    inspect(&root.join("extension"), "", &mut names)?;
    names.sort();
    let mut expected: Vec<_> = FILES.iter().map(|s| s.to_string()).collect();
    expected.sort();
    if names != expected || receipt.files.keys().cloned().collect::<Vec<_>>() != expected {
        return Err("Unexpected or missing preview files. Disable preview and inspect the folder; files left untouched.".into());
    }
    for (name, expected) in &receipt.files {
        let file = root.join("extension").join(name);
        let size = std::fs::metadata(&file)
            .map_err(|_| "Cannot inspect preview file.")?
            .len();
        if size > 1024 * 1024
            || hash(&std::fs::read(file).map_err(|_| "Cannot read preview file.")?) != *expected
        {
            return Err("Preview files were modified. Files left untouched; remove the extension in your browser before repairing.".into());
        }
    }
    Ok(receipt)
}

fn remove_verified_dir(dir: &Path) -> Result<(), String> {
    // Called only after exact inventory + hash verification. No recursive deletion.
    for name in FILES {
        std::fs::remove_file(dir.join(name))
            .map_err(|_| "Could not remove an owned preview file.")?;
    }
    std::fs::remove_dir(dir.join("icons"))
        .map_err(|_| "Could not remove empty icons directory.")?;
    std::fs::remove_dir(dir).map_err(|_| "Could not remove empty preview directory.".into())
}

pub fn prepare(root: &Path) -> Result<(), String> {
    prepare_package(root, package())
}

fn prepare_package(root: &Path, package: Package) -> Result<(), String> {
    ensure_root(root)?;
    if root.join("extension").exists() {
        verified(root)?;
    }
    let stage = root.join("staging");
    let previous = root.join("previous");
    if stage.exists() || previous.exists() {
        return Err("An interrupted update needs inspection; no files replaced.".into());
    }
    std::fs::create_dir(&stage).map_err(|_| "Cannot stage preview update.")?;
    std::fs::create_dir(stage.join("icons")).map_err(|_| "Cannot stage preview icons.")?;
    let mut hashes = BTreeMap::new();
    if package.files.len() != FILES.len() {
        return Err("Invalid embedded package inventory.".into());
    }
    for name in FILES {
        let entry = package
            .files
            .get(*name)
            .ok_or("Missing embedded preview file.")?;
        let bytes = base64::engine::general_purpose::STANDARD
            .decode(&entry.base64)
            .map_err(|_| "Invalid embedded file.")?;
        if hash(&bytes) != entry.sha256 {
            return Err("Embedded preview checksum mismatch.".into());
        }
        std::fs::write(stage.join(name), bytes).map_err(|_| "Cannot write staged preview file.")?;
        hashes.insert(name.to_string(), entry.sha256.clone());
    }
    let destination = root.join("extension");
    let replacing = destination.exists();
    if replacing {
        std::fs::rename(&destination, &previous)
            .map_err(|_| "Close the extension's Options page before updating.")?;
    }
    if std::fs::rename(&stage, &destination).is_err() {
        if replacing {
            let _ = std::fs::rename(&previous, &destination);
        }
        return Err("Could not activate preview files; previous version retained.".into());
    }
    let receipt = Receipt {
        version: package.version,
        sha256: package.sha256,
        files: hashes,
    };
    write(
        root,
        "receipt.json",
        &serde_json::to_value(receipt).unwrap(),
    )?;
    verified(root)?;
    if replacing {
        remove_verified_dir(&previous)?;
    }
    Ok(())
}

pub fn cleanup(root: &Path) -> Result<(), String> {
    if root.join("extension").exists() {
        verified(root)?;
        remove_verified_dir(&root.join("extension"))?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn scratch() -> std::path::PathBuf {
        let mut random = [0u8; 16];
        getrandom::fill(&mut random).unwrap();
        std::env::temp_dir()
            .canonicalize()
            .unwrap()
            .join(format!("callosum-preview-test-{}", hash(&random)))
    }
    #[test]
    fn exact_package_update_and_cleanup() {
        let root = scratch();
        prepare(&root).unwrap();
        let first = verified(&root).unwrap();
        prepare(&root).unwrap();
        assert_eq!(verified(&root).unwrap().sha256, first.sha256);
        cleanup(&root).unwrap();
        assert!(!root.join("extension").exists());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn update_preserves_path_and_replaces_only_verified_previous_version() {
        let root = scratch();
        let mut old = package();
        old.version = "0.0.1".into();
        let manifest = &mut old.files.get_mut("manifest.json").unwrap();
        let mut content: serde_json::Value = serde_json::from_slice(
            &base64::engine::general_purpose::STANDARD
                .decode(&manifest.base64)
                .unwrap(),
        )
        .unwrap();
        content["version"] = "0.0.1".into();
        let bytes = serde_json::to_vec(&content).unwrap();
        manifest.sha256 = hash(&bytes);
        manifest.base64 = base64::engine::general_purpose::STANDARD.encode(bytes);
        old.sha256 = "synthetic-previous-version".into();
        prepare_package(&root, old).unwrap();
        assert_eq!(verified(&root).unwrap().version, "0.0.1");
        // A new app reading this directory does not change it until explicit Prepare.
        let path = root.join("extension").canonicalize().unwrap();
        prepare(&root).unwrap();
        assert_eq!(root.join("extension").canonicalize().unwrap(), path);
        assert_eq!(verified(&root).unwrap().version, package().version);
        assert!(!root.join("previous").exists());
        cleanup(&root).unwrap();
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn unexpected_and_modified_files_are_never_overwritten_or_removed() {
        let root = scratch();
        prepare(&root).unwrap();
        std::fs::write(root.join("extension/foreign.exe"), b"untouched").unwrap();
        assert!(prepare(&root).is_err());
        assert!(cleanup(&root).is_err());
        assert_eq!(
            std::fs::read(root.join("extension/foreign.exe")).unwrap(),
            b"untouched"
        );
        std::fs::remove_file(root.join("extension/foreign.exe")).unwrap();
        std::fs::write(root.join("extension/background.js"), b"modified").unwrap();
        assert!(cleanup(&root).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[cfg(unix)]
    #[test]
    fn symlinked_files_and_roots_fail_closed() {
        let root = scratch();
        prepare(&root).unwrap();
        let outside = scratch();
        std::fs::write(&outside, b"private").unwrap();
        std::fs::remove_file(root.join("extension/background.js")).unwrap();
        std::os::unix::fs::symlink(&outside, root.join("extension/background.js")).unwrap();
        assert!(prepare(&root).is_err());
        assert!(cleanup(&root).is_err());
        assert_eq!(std::fs::read(&outside).unwrap(), b"private");
        std::fs::remove_dir_all(root).unwrap();
        std::fs::remove_file(outside).unwrap();
    }
}
