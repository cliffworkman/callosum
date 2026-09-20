//! Per-user native-messaging host registration for the browser-capture connector on macOS (#61).
//!
//! Windows registers through NSIS installer hooks (registry). macOS has no installer: the app is dragged to
//! /Applications, so nothing can run "at install". The smallest lifecycle that fits is registration **at every
//! launch of the installed app**: locate the sidecar connector inside *this* running bundle, and write the small
//! per-user host manifest Chrome (and, best-effort, Edge) read, pointing at that absolute path. Because the check
//! runs on every launch, a stale path (the app moved) is repaired the next time Callosum starts.
//!
//! Identity: the host name and the `allowed_origins` come only from `connector/identity.json`, compiled in with
//! `include_str!` exactly like the connector host itself -- no second copy of any extension ID lives here.
//!
//! Deliberately NOT done here (each waits for evidence from a real Mac rather than being coded around blind):
//! stripping quarantine from the connector, process-name detection, any Gatekeeper workaround.
//!
//! The decision logic is plain functions over explicit paths, so it is unit-tested on every OS in CI; only the
//! thin `register_on_startup` wiring is macOS-only.
#![cfg_attr(not(target_os = "macos"), allow(dead_code))]

use serde::Serialize;
use serde_json::{json, Value};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

/// The single source of connector identity (host name + store extension IDs). Same file the connector host,
/// the NSIS generator and the tests read.
const IDENTITY_JSON: &str = include_str!("../../connector/identity.json");
const EXTENSION_ID_LEN: usize = 32;
/// Tauri places an `externalBin` sidecar next to the main executable (target-triple suffix stripped). This is the
/// documented convention and the conservative implementation; the macOS workflow OBSERVES the real installed layout
/// (and `connector-registration.json` records the path actually used), so a mismatch shows up as evidence.
const CONNECTOR_FILE_NAME: &str = "callosum-connector";
const REPORT_FILE_NAME: &str = "connector-registration.json";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Identity {
    pub native_host_name: String,
    pub allowed_origins: Vec<String>,
}

fn valid_extension_id(id: &str) -> bool {
    id.len() == EXTENSION_ID_LEN && id.bytes().all(|b| (b'a'..=b'p').contains(&b))
}

/// Chrome's rule: lowercase alphanumerics/underscores in dot-separated, non-empty segments.
fn valid_host_name(name: &str) -> bool {
    !name.is_empty()
        && name.split('.').all(|segment| {
            !segment.is_empty()
                && segment
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
        })
}

pub fn parse_identity(raw: &str) -> Result<Identity, String> {
    let value: Value = serde_json::from_str(raw).map_err(|e| format!("identity.json is not valid JSON: {e}"))?;
    let name = value
        .get("native_host_name")
        .and_then(Value::as_str)
        .ok_or("identity.json has no native_host_name string")?;
    if !valid_host_name(name) {
        return Err(format!("invalid native_host_name {name:?}"));
    }
    let ids = value
        .get("production_extension_ids")
        .and_then(Value::as_array)
        .ok_or("identity.json has no production_extension_ids array")?;
    let dev_id = value.get("dev_extension_id").and_then(Value::as_str);
    let mut seen = HashSet::new();
    let mut origins = Vec::new();
    for id in ids {
        let id = id.as_str().ok_or("production_extension_ids must be strings")?;
        if !valid_extension_id(id) {
            return Err(format!("invalid production extension id {id:?}"));
        }
        if !seen.insert(id) {
            return Err(format!("duplicate production extension id {id:?}"));
        }
        if Some(id) == dev_id {
            return Err("the development extension id must never be a production id".to_string());
        }
        origins.push(format!("chrome-extension://{id}/"));
    }
    Ok(Identity { native_host_name: name.to_string(), allowed_origins: origins })
}

pub fn embedded_identity() -> Result<Identity, String> {
    parse_identity(IDENTITY_JSON)
}

/// The exact manifest text written for the browser. `path` is absolute by construction (callers pass the resolved
/// bundle path); Chrome ignores a manifest whose path is relative.
pub fn manifest_json(identity: &Identity, connector_path: &Path) -> String {
    let manifest = json!({
        "name": identity.native_host_name,
        "description": "Callosum browser-capture connector",
        "path": connector_path.to_string_lossy(),
        "type": "stdio",
        "allowed_origins": identity.allowed_origins,
    });
    let mut text = serde_json::to_string_pretty(&manifest).expect("a JSON value always serializes");
    text.push('\n');
    text
}

/// A location the OS may remove or randomise underneath us: never persist a manifest that points into one.
/// App Translocation copies a quarantined app to a randomised read-only path; a mounted disk image disappears on eject.
pub fn unstable_location_reason(path: &Path) -> Option<&'static str> {
    let text = path.to_string_lossy();
    if text.contains("/AppTranslocation/") {
        Some("the app is running from a macOS App Translocation path")
    } else if text.starts_with("/Volumes/") {
        Some("the app is running from a mounted volume (disk image)")
    } else {
        None
    }
}

/// Where the sidecar sits relative to the running executable (Tauri convention; verified by CI, recorded in the report).
pub fn locate_connector(current_exe: &Path) -> Option<PathBuf> {
    Some(current_exe.parent()?.join(CONNECTOR_FILE_NAME))
}

#[cfg(unix)]
fn is_executable_file(path: &Path) -> bool {
    use std::os::unix::fs::PermissionsExt;
    std::fs::metadata(path)
        .map(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
        .unwrap_or(false)
}

#[cfg(not(unix))]
fn is_executable_file(path: &Path) -> bool {
    path.is_file()
}

#[derive(Debug, Clone)]
pub struct BrowserTarget {
    pub name: &'static str,
    /// The browser's user-data directory; Chromium reads per-user host manifests from `<this>/NativeMessagingHosts`.
    pub user_data_dir: PathBuf,
    /// `true` = always ensure the directory + manifest (Chrome: the hard utility target, so silent non-registration
    /// would be worse than one small manifest). `false` = best effort: only when the browser's directory exists.
    pub ensure: bool,
}

pub fn browser_targets(home: &Path) -> Vec<BrowserTarget> {
    let support = home.join("Library").join("Application Support");
    vec![
        BrowserTarget { name: "Google Chrome", user_data_dir: support.join("Google").join("Chrome"), ensure: true },
        BrowserTarget { name: "Microsoft Edge", user_data_dir: support.join("Microsoft Edge"), ensure: false },
    ]
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "outcome", content = "detail", rename_all = "snake_case")]
pub enum Outcome {
    Registered,
    Unchanged,
    SkippedBrowserAbsent,
    SkippedUnstableLocation(String),
    Failed(String),
}

#[derive(Debug, Clone, Serialize)]
pub struct BrowserResult {
    pub browser: String,
    pub manifest_path: Option<String>,
    #[serde(flatten)]
    pub outcome: Outcome,
}

#[derive(Debug, Clone, Serialize)]
pub struct Registration {
    pub schema: u32,
    pub connector_path: String,
    pub native_host_name: String,
    pub results: Vec<BrowserResult>,
}

fn write_atomically(path: &Path, text: &str) -> std::io::Result<()> {
    let dir = path.parent().unwrap_or_else(|| Path::new("."));
    let tmp = dir.join(format!(".{}.tmp", path.file_name().map(|n| n.to_string_lossy()).unwrap_or_default()));
    std::fs::write(&tmp, text)?;
    std::fs::rename(&tmp, path)
}

/// Register (or repair) the host manifest for every target browser. Never panics; every outcome is reported.
pub fn register(identity: &Identity, connector_path: &Path, home: &Path) -> Registration {
    let targets = browser_targets(home);
    let refuse_all = |outcome: Outcome| Registration {
        schema: 1,
        connector_path: connector_path.to_string_lossy().into_owned(),
        native_host_name: identity.native_host_name.clone(),
        results: targets
            .iter()
            .map(|t| BrowserResult { browser: t.name.to_string(), manifest_path: None, outcome: outcome.clone() })
            .collect(),
    };
    if let Some(reason) = unstable_location_reason(connector_path) {
        return refuse_all(Outcome::SkippedUnstableLocation(reason.to_string()));
    }
    if !connector_path.is_absolute() {
        return refuse_all(Outcome::Failed("the connector path is not absolute".to_string()));
    }
    if !is_executable_file(connector_path) {
        return refuse_all(Outcome::Failed("the bundled connector is missing or not executable".to_string()));
    }
    let text = manifest_json(identity, connector_path);
    let results = targets
        .iter()
        .map(|target| {
            let manifest_dir = target.user_data_dir.join("NativeMessagingHosts");
            let manifest_path = manifest_dir.join(format!("{}.json", identity.native_host_name));
            let outcome = if !target.ensure && !target.user_data_dir.is_dir() {
                Outcome::SkippedBrowserAbsent
            } else if std::fs::read_to_string(&manifest_path).map(|current| current == text).unwrap_or(false) {
                Outcome::Unchanged
            } else {
                match std::fs::create_dir_all(&manifest_dir).and_then(|_| write_atomically(&manifest_path, &text)) {
                    Ok(()) => Outcome::Registered,
                    Err(error) => Outcome::Failed(format!("could not write the manifest: {error}")),
                }
            };
            BrowserResult {
                browser: target.name.to_string(),
                manifest_path: Some(manifest_path.to_string_lossy().into_owned()),
                outcome,
            }
        })
        .collect();
    Registration {
        schema: 1,
        connector_path: connector_path.to_string_lossy().into_owned(),
        native_host_name: identity.native_host_name.clone(),
        results,
    }
}

/// Run at shell startup on macOS. Non-fatal by design: browser capture is an optional integration, so a
/// registration problem is recorded (stderr + `connector-registration.json` beside the app data) and never
/// stops Callosum from starting.
#[cfg(target_os = "macos")]
pub fn register_on_startup(app_data_dir: &Path) {
    let outcome = (|| -> Result<Registration, String> {
        let identity = embedded_identity()?;
        let exe = std::env::current_exe().map_err(|e| format!("current_exe unavailable: {e}"))?;
        let connector = locate_connector(&exe).ok_or("the running executable has no parent directory")?;
        let home = std::env::var_os("HOME").ok_or("HOME is not set")?;
        Ok(register(&identity, &connector, Path::new(&home)))
    })();
    let report = match outcome {
        Ok(registration) => serde_json::to_value(&registration).unwrap_or(Value::Null),
        Err(reason) => json!({ "schema": 1, "error": reason }),
    };
    eprintln!("Browser connector registration: {report}");
    let text = serde_json::to_string_pretty(&report).unwrap_or_default() + "\n";
    if let Err(error) = std::fs::create_dir_all(app_data_dir)
        .and_then(|_| write_atomically(&app_data_dir.join(REPORT_FILE_NAME), &text))
    {
        eprintln!("Could not record the connector registration report: {error}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const CHROME_ID: &str = "cccccccccccccccccccccccccccccccc"; // 32 x 'c' (a-p)
    const EDGE_ID: &str = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
    const DEV_ID: &str = "dddddddddddddddddddddddddddddddd";

    fn scratch(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("callosum-registration-{}-{tag}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn fake_connector(dir: &Path) -> PathBuf {
        let path = dir.join("Applications").join("Callosum.app").join("Contents").join("MacOS").join(CONNECTOR_FILE_NAME);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, b"#!/bin/sh\n").unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
        path
    }

    fn identity_json(ids: &[&str], dev: &str) -> String {
        json!({ "native_host_name": "org.callosum.connector", "production_extension_ids": ids, "dev_extension_id": dev })
            .to_string()
    }

    #[test]
    fn the_embedded_identity_is_the_single_source_and_is_valid() {
        let raw: Value = serde_json::from_str(IDENTITY_JSON).unwrap();
        let identity = embedded_identity().expect("the committed identity.json must parse and validate");
        assert_eq!(identity.native_host_name, raw["native_host_name"].as_str().unwrap());
        assert_eq!(identity.allowed_origins.len(), raw["production_extension_ids"].as_array().unwrap().len());
        assert!(!identity.allowed_origins.iter().any(|o| o.contains(raw["dev_extension_id"].as_str().unwrap())));
    }

    #[test]
    fn allowed_origins_are_exact_and_ordered_and_only_from_production_ids() {
        let identity = parse_identity(&identity_json(&[CHROME_ID, EDGE_ID], DEV_ID)).unwrap();
        assert_eq!(
            identity.allowed_origins,
            vec![format!("chrome-extension://{CHROME_ID}/"), format!("chrome-extension://{EDGE_ID}/")]
        );
    }

    #[test]
    fn invalid_duplicate_and_leaked_dev_ids_are_rejected() {
        assert!(parse_identity(&identity_json(&["short"], DEV_ID)).is_err());
        assert!(parse_identity(&identity_json(&["zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"], DEV_ID)).is_err()); // outside a-p
        assert!(parse_identity(&identity_json(&[CHROME_ID, CHROME_ID], DEV_ID)).is_err());
        assert!(parse_identity(&identity_json(&[DEV_ID], DEV_ID)).is_err()); // dev id must never be a production id
        let bad_host = json!({ "native_host_name": "Not A Host", "production_extension_ids": [], "dev_extension_id": DEV_ID });
        assert!(parse_identity(&bad_host.to_string()).is_err());
    }

    #[test]
    fn the_manifest_has_the_exact_shape_with_an_absolute_path() {
        let identity = parse_identity(&identity_json(&[CHROME_ID], DEV_ID)).unwrap();
        let path = Path::new("/Applications/Callosum.app/Contents/MacOS/callosum-connector");
        let manifest: Value = serde_json::from_str(&manifest_json(&identity, path)).unwrap();
        assert_eq!(manifest["name"], "org.callosum.connector");
        assert_eq!(manifest["description"], "Callosum browser-capture connector");
        assert_eq!(manifest["type"], "stdio");
        assert_eq!(manifest["path"], "/Applications/Callosum.app/Contents/MacOS/callosum-connector");
        assert_eq!(manifest["allowed_origins"], json!([format!("chrome-extension://{CHROME_ID}/")]));
    }

    #[test]
    fn translocated_and_disk_image_locations_are_unstable() {
        for bad in [
            "/private/var/folders/ab/xyz/T/AppTranslocation/0123-4567/d/Callosum.app/Contents/MacOS/callosum-connector",
            "/Volumes/Callosum/Callosum.app/Contents/MacOS/callosum-connector",
        ] {
            assert!(unstable_location_reason(Path::new(bad)).is_some(), "{bad}");
        }
        for fine in [
            "/Applications/Callosum.app/Contents/MacOS/callosum-connector",
            "/Users/someone/Applications/Callosum.app/Contents/MacOS/callosum-connector",
            "/Users/someone/Downloads/Callosum.app/Contents/MacOS/callosum-connector",
        ] {
            assert!(unstable_location_reason(Path::new(fine)).is_none(), "{fine}");
        }
    }

    #[test]
    fn the_connector_is_located_next_to_the_main_executable() {
        let exe = Path::new("/Applications/Callosum.app/Contents/MacOS/callosum-shell");
        assert_eq!(
            locate_connector(exe).unwrap(),
            Path::new("/Applications/Callosum.app/Contents/MacOS/callosum-connector")
        );
    }

    #[test]
    fn chrome_is_always_ensured_and_edge_only_when_present_and_repair_is_idempotent() {
        let home = scratch("ensure");
        let connector = fake_connector(&home);
        let identity = parse_identity(&identity_json(&[CHROME_ID], DEV_ID)).unwrap();

        // Fresh home: Chrome's directory does not exist yet -- it is still registered (deterministic), Edge is skipped.
        let first = register(&identity, &connector, &home);
        let chrome = first.results.iter().find(|r| r.browser == "Google Chrome").unwrap();
        let edge = first.results.iter().find(|r| r.browser == "Microsoft Edge").unwrap();
        assert_eq!(chrome.outcome, Outcome::Registered);
        assert_eq!(edge.outcome, Outcome::SkippedBrowserAbsent);
        let manifest_path = PathBuf::from(chrome.manifest_path.clone().unwrap());
        assert!(manifest_path.ends_with("Library/Application Support/Google/Chrome/NativeMessagingHosts/org.callosum.connector.json"));
        let written: Value = serde_json::from_str(&std::fs::read_to_string(&manifest_path).unwrap()).unwrap();
        assert_eq!(written["path"], &*connector.to_string_lossy());

        // A second launch changes nothing.
        assert_eq!(register(&identity, &connector, &home).results[0].outcome, Outcome::Unchanged);

        // Edge appears later -> registered on the next launch; the app "moved" -> the stale path is repaired.
        std::fs::create_dir_all(home.join("Library/Application Support/Microsoft Edge")).unwrap();
        let moved_home = scratch("ensure-moved");
        let moved = fake_connector(&moved_home);
        let repaired = register(&identity, &moved, &home);
        assert_eq!(repaired.results[0].outcome, Outcome::Registered);
        assert_eq!(repaired.results[1].outcome, Outcome::Registered);
        let rewritten: Value = serde_json::from_str(&std::fs::read_to_string(&manifest_path).unwrap()).unwrap();
        assert_eq!(rewritten["path"], &*moved.to_string_lossy());
        let _ = std::fs::remove_dir_all(&home);
        let _ = std::fs::remove_dir_all(&moved_home);
    }

    #[test]
    fn nothing_is_written_from_an_unstable_or_missing_connector() {
        let home = scratch("guards");
        let identity = parse_identity(&identity_json(&[CHROME_ID], DEV_ID)).unwrap();
        let translocated = Path::new("/private/var/folders/x/T/AppTranslocation/uuid/d/Callosum.app/Contents/MacOS/callosum-connector");
        for result in register(&identity, translocated, &home).results {
            assert!(matches!(result.outcome, Outcome::SkippedUnstableLocation(_)));
            assert!(result.manifest_path.is_none());
        }
        let missing = home.join("Applications/Callosum.app/Contents/MacOS/callosum-connector");
        for result in register(&identity, &missing, &home).results {
            assert!(matches!(result.outcome, Outcome::Failed(_)));
        }
        assert!(!home.join("Library").exists(), "a refused registration must not create any browser directory");
        let _ = std::fs::remove_dir_all(&home);
    }

    #[cfg(unix)]
    #[test]
    fn a_non_executable_connector_is_refused() {
        use std::os::unix::fs::PermissionsExt;
        let home = scratch("noexec");
        let connector = fake_connector(&home);
        std::fs::set_permissions(&connector, std::fs::Permissions::from_mode(0o644)).unwrap();
        let identity = parse_identity(&identity_json(&[CHROME_ID], DEV_ID)).unwrap();
        for result in register(&identity, &connector, &home).results {
            assert!(matches!(result.outcome, Outcome::Failed(_)));
        }
        let _ = std::fs::remove_dir_all(&home);
    }

    #[test]
    fn only_the_callosum_manifest_is_written_and_third_party_manifests_are_untouched() {
        let home = scratch("neighbours");
        let connector = fake_connector(&home);
        let dir = home.join("Library/Application Support/Google/Chrome/NativeMessagingHosts");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("com.example.other.json"), "{\"name\":\"com.example.other\"}").unwrap();
        let identity = parse_identity(&identity_json(&[CHROME_ID], DEV_ID)).unwrap();
        register(&identity, &connector, &home);
        let mut names: Vec<String> = std::fs::read_dir(&dir).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).collect();
        names.sort();
        assert_eq!(names, vec!["com.example.other.json".to_string(), "org.callosum.connector.json".to_string()]);
        assert_eq!(std::fs::read_to_string(dir.join("com.example.other.json")).unwrap(), "{\"name\":\"com.example.other\"}");
        let _ = std::fs::remove_dir_all(&home);
    }
}
