//! Local desktop-owned opt-in. No caller-provided paths; shared by shell and normal host.
use serde_json::{json, Value};
use std::path::Path;

pub fn now() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

pub fn plain(path: &Path) -> bool {
    let Ok(meta) = std::fs::symlink_metadata(path) else {
        return false;
    };
    if meta.file_type().is_symlink() {
        return false;
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if meta.file_attributes() & 0x400 != 0 {
            return false;
        }
    }
    true
}

pub fn read(root: &Path, name: &str) -> Option<Value> {
    if !plain(root) || !plain(&root.join(name)) {
        return None;
    }
    if std::fs::metadata(root.join(name)).ok()?.len() > 8192 {
        return None;
    }
    let bytes = std::fs::read(root.join(name)).ok()?;
    if bytes.len() > 8192 {
        return None;
    }
    serde_json::from_slice(&bytes).ok()
}

pub fn generation(root: &Path) -> Option<String> {
    let state = read(root, "enabled.json")?;
    if state["enabled"] != true {
        return None;
    }
    let value = state["generation"].as_str()?;
    if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        return None;
    }
    Some(value.into())
}

pub fn write(root: &Path, name: &str, value: &Value) -> Result<(), String> {
    if !plain(root) {
        return Err("Preview directory is not a regular local directory.".into());
    }
    let target = root.join(name);
    if target.exists() && !plain(&target) {
        return Err("Preview state contains a link; no changes made.".into());
    }
    // Fixed state names, same-user directory. create_new refuses stale/symlink temporary files.
    let tmp = root.join(format!("{name}.tmp"));
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    use std::io::Write;
    let mut file = options
        .open(&tmp)
        .map_err(|_| "Cannot create private preview state; inspect a stale temporary file.")?;
    file.write_all(value.to_string().as_bytes())
        .and_then(|_| file.sync_all())
        .map_err(|_| "Cannot save preview state.")?;
    drop(file);
    std::fs::rename(&tmp, &target).map_err(|_| "Cannot replace preview state.".into())
}

pub fn complete_verification(
    root: &Path,
    version: &str,
    expected_version: &str,
    session_generation: &str,
) -> Result<(), &'static str> {
    if version != expected_version {
        return Err("version_incompatible");
    }
    let generation = generation(root).ok_or("preview_disabled")?;
    if generation != session_generation {
        return Err("preview_disabled");
    }
    let challenge = read(root, "challenge.json").ok_or("verification_not_requested")?;
    let expires = challenge["expires"].as_u64().unwrap_or(0);
    if challenge["generation"] != generation || expires < now() || expires > now() + 60 {
        return Err("verification_not_requested");
    }
    let nonce = challenge["nonce"]
        .as_str()
        .filter(|n| n.len() == 64)
        .ok_or("verification_not_requested")?;
    write(
        root,
        "verified.json",
        &json!({"nonce":nonce,"generation":generation,"at":now(),"version":version}),
    )
    .map_err(|_| "verification_not_requested")
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn verification_requires_current_opt_in_challenge_and_version() {
        let root = std::env::temp_dir().canonicalize().unwrap().join(format!(
            "preview-state-{}-{}",
            std::process::id(),
            now()
        ));
        std::fs::create_dir(&root).unwrap();
        assert_eq!(
            complete_verification(&root, "1", "1", &"a".repeat(64)),
            Err("preview_disabled")
        );
        write(
            &root,
            "enabled.json",
            &json!({"enabled":true,"generation":"a".repeat(64)}),
        )
        .unwrap();
        assert_eq!(
            complete_verification(&root, "1", "1", &"a".repeat(64)),
            Err("verification_not_requested")
        );
        for (generation, expires) in [("b", now() + 30), ("a", now() - 1), ("a", now() + 120)] {
            write(&root,"challenge.json",&json!({"generation":generation.repeat(64),"nonce":"c".repeat(64),"expires":expires})).unwrap();
            assert_eq!(
                complete_verification(&root, "1", "1", &"a".repeat(64)),
                Err("verification_not_requested")
            );
        }
        write(
            &root,
            "challenge.json",
            &json!({"generation":"a".repeat(64),"nonce":"c".repeat(64),"expires":now()+60}),
        )
        .unwrap();
        assert_eq!(
            complete_verification(&root, "old", "1", &"a".repeat(64)),
            Err("version_incompatible")
        );
        complete_verification(&root, "1", "1", &"a".repeat(64)).unwrap();
        assert_eq!(
            read(&root, "verified.json").unwrap()["nonce"],
            "c".repeat(64)
        );
        write(
            &root,
            "enabled.json",
            &json!({"enabled":false,"generation":"d".repeat(64)}),
        )
        .unwrap();
        assert_eq!(
            complete_verification(&root, "1", "1", &"a".repeat(64)),
            Err("preview_disabled")
        );
        std::fs::remove_dir_all(root).unwrap();
    }
}
