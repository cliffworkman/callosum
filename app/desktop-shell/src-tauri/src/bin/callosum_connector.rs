//! The production browser-capture connector host (#61 Phase 2, Part 1) -- a Chrome/Edge native
//! messaging host, launched fresh by the browser for each message exchange. Deliberately thin:
//!
//! It MAY: resolve the packaged UI backend from packaged state alone (no port probing), verify
//! `instance_role == "ui"`, apply build-identity eligibility, read the local pairing secret and
//! exchange it at `/capture/session`, and report structured connector state back to the extension.
//!
//! It MAY NOT: parse page metadata, resolve DOIs, fetch pages, download PDFs, or mutate the
//! Library. Identity, admission and attachment semantics stay in Python (`app/backend/capture/`).
//! This binary never calls anything but `/health` and `/capture/session`.
//!
//! Chrome/Edge native messaging framing: one message is a 4-byte little-endian `u32` length
//! followed by that many bytes of UTF-8 JSON, on stdin/stdout. `std::io::Stdout` writes raw bytes
//! with no text-mode translation (unlike Python's default stdout on Windows), so no binary-mode
//! reconfiguration is needed here.

use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;

use serde::{Deserialize, Serialize};

const PROTOCOL_VERSION: u32 = 1;
const CONNECTOR_HOST_VERSION: &str = env!("CARGO_PKG_VERSION");
const DEV_BUILD_ENV: &str = "CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD";
const APP_IDENTIFIER: &str = "com.callosum.desktop";

/// The identity config every consumer (this binary, the NSIS hook generator, the extension's dev
/// tooling, and tests) reads from the same file -- see that file's own `_comment` fields for why
/// `production_extension_ids` starts empty. Embedded at compile time: this is a released binary,
/// not something that reads its own source tree at runtime.
const IDENTITY_JSON: &str = include_str!("../../../connector/identity.json");

#[derive(Deserialize)]
struct Identity {
    // Not read outside `#[cfg(test)]` -- the wire check uses the compiled-in PROTOCOL_VERSION
    // constant (see main()), not this JSON copy. Kept here purely so
    // `identity_json_is_internally_consistent` can catch identity.json and this binary's compiled
    // protocol version ever drifting apart.
    #[allow(dead_code)]
    protocol_version: u32,
    native_host_name: String,
    dev_native_host_name: String,
    production_extension_ids: Vec<String>,
    dev_extension_id: String,
}

impl Identity {
    fn load() -> Self {
        serde_json::from_str(IDENTITY_JSON).expect("connector/identity.json must parse: it is committed and built-in")
    }
}

/// Never collapsed into a generic "not installed" -- each is a state the extension renders
/// distinct, stable copy for. `host_unavailable` is deliberately ABSENT from this enum: a host
/// that cannot be reached at all never gets the chance to report anything, so that state is
/// inferred client-side (the extension's `chrome.runtime.lastError` / no-response case), not
/// emitted here. `pairing_unavailable` is this implementation's one addition beyond the plan's
/// original enumeration -- see `resolve` below for why it earns a distinct, honest state rather
/// than being folded into an existing one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RuntimeState {
    Available,
    CallosumClosed,
    CallosumStarting,
    VersionIncompatible,
    NotEligibleInstance,
    PairingUnavailable,
}

impl RuntimeState {
    fn as_str(self) -> &'static str {
        match self {
            RuntimeState::Available => "available",
            RuntimeState::CallosumClosed => "callosum_closed",
            RuntimeState::CallosumStarting => "callosum_starting",
            RuntimeState::VersionIncompatible => "version_incompatible",
            RuntimeState::NotEligibleInstance => "not_eligible_instance",
            RuntimeState::PairingUnavailable => "pairing_unavailable",
        }
    }
}

#[derive(Deserialize)]
struct ExtensionRequest {
    id: Option<String>,
    protocol_version: Option<u32>,
}

#[derive(Serialize, Default)]
struct ConnectorResponse {
    protocol_version: u32,
    connector_host_version: &'static str,
    connector_identity: String,
    app_version: Option<String>,
    instance_role: Option<String>,
    runtime_state: &'static str,
    session_token: Option<String>,
    backend_base_url: Option<String>,
    echo_of: Option<String>,
}

#[derive(Deserialize, Default, Debug, PartialEq, Eq)]
struct HealthBody {
    instance_role: Option<String>,
    app_version: Option<String>,
}

#[derive(Deserialize)]
struct PairingFile {
    pairing_secret: Option<String>,
}

#[derive(Serialize)]
struct SessionRequest<'a> {
    pairing_secret: &'a str,
}

#[derive(Deserialize)]
struct SessionResponse {
    session_token: String,
}

// ---------------------------------------------------------------------------------------------
// Pure logic -- no I/O, so these are unit-tested directly without a filesystem or a real server.
// ---------------------------------------------------------------------------------------------

/// Exact match only. `origin` is what Chrome passes as argv[1]: `chrome-extension://<32 lowercase
/// a-p chars>/`. No prefix, substring, or wildcard match is ever accepted -- this is defense in
/// depth behind the browser's own `allowed_origins` manifest enforcement, never a replacement for
/// it (steering point 3): a hostile webpage or unapproved extension is already refused by Chrome
/// before this binary is even launched with a matching argv[1] in the first place.
fn caller_extension_id(origin: &str) -> Option<&str> {
    let rest = origin.strip_prefix("chrome-extension://")?;
    let id = rest.strip_suffix('/').unwrap_or(rest);
    (id.len() == 32 && id.bytes().all(|b| (b'a'..=b'p').contains(&b))).then_some(id)
}

fn caller_is_allowed(origin: Option<&str>, identity: &Identity, allow_dev_build: bool) -> bool {
    let Some(id) = origin.and_then(caller_extension_id) else {
        return false;
    };
    identity.production_extension_ids.iter().any(|allowed| allowed == id)
        || (allow_dev_build && id == identity.dev_extension_id)
}

/// Packaged `ui` is always eligible. A `dev-` build is eligible ONLY with the dev-build flag, so a
/// production connector cannot be tricked into trusting a development checkout. An undeclared or
/// sibling role, or a wholly unknown build identity (no `CALLOSUM_APP_VERSION`, no git checkout to
/// fall back to), is never eligible -- fail-closed on ambiguity, matching `reported_instance_role`'s
/// own documented fail-safe.
fn instance_is_eligible(instance_role: Option<&str>, app_version: Option<&str>, allow_dev_build: bool) -> bool {
    if instance_role != Some("ui") {
        return false;
    }
    match app_version {
        Some(v) if v.starts_with("dev-") => allow_dev_build,
        Some(_) => true,
        None => false,
    }
}

fn read_port(path: &Path) -> Option<u16> {
    std::fs::read_to_string(path).ok()?.trim().parse().ok()
}

// ---------------------------------------------------------------------------------------------
// I/O boundary -- everything below touches the filesystem, the network, or a process list. Each
// testable seam takes explicit paths/clients rather than resolving them internally, so tests never
// need real env-var mutation (racy across parallel `cargo test` threads) to redirect them.
// ---------------------------------------------------------------------------------------------

#[cfg(windows)]
fn shell_process_running() -> bool {
    // Mirrors the research probe's own technique (`observe_packaged_role.py`), which already
    // proved this is a reliable way to tell "still starting" from "not running at all" without a
    // Windows-API dependency this crate doesn't already have.
    Command::new("tasklist")
        .args(["/FI", "IMAGENAME eq callosum-shell.exe", "/NH"])
        .output()
        .map(|out| String::from_utf8_lossy(&out.stdout).to_lowercase().contains("callosum-shell.exe"))
        .unwrap_or(false)
}

#[cfg(not(windows))]
fn shell_process_running() -> bool {
    false // Stage 2 is Windows-first (NSIS + registry native messaging); never claim "starting" elsewhere.
}

/// Resolve the canonical UI backend from packaged state alone -- the port file is read ONCE and
/// only that exact port is ever contacted. No range scan, no fallback port, matching the
/// prerequisite research this increment is built on.
fn resolve_backend(port_file: &Path, client: &reqwest::blocking::Client) -> Result<HealthBody, RuntimeState> {
    let Some(port) = read_port(port_file) else {
        return Err(if shell_process_running() {
            RuntimeState::CallosumStarting
        } else {
            RuntimeState::CallosumClosed
        });
    };
    let url = format!("http://127.0.0.1:{port}/health");
    if let Some(body) = try_health(client, &url) {
        return Ok(body);
    }
    // One short, bounded retry -- covers the narrow window where `pick_port` (backend.rs) is
    // rebinding the remembered port and uvicorn has not started listening yet. Never a loop: a
    // click-triggered native-messaging exchange must not hang the browser for a long-running
    // model-import startup (`wait_for_health`'s own 120s budget is for the desktop shell's splash
    // screen, not for a synchronous per-click round trip).
    if shell_process_running() {
        std::thread::sleep(Duration::from_millis(700));
        if let Some(body) = try_health(client, &url) {
            return Ok(body);
        }
        return Err(RuntimeState::CallosumStarting);
    }
    Err(RuntimeState::CallosumClosed)
}

fn try_health(client: &reqwest::blocking::Client, url: &str) -> Option<HealthBody> {
    let response = client.get(url).send().ok()?;
    if !response.status().is_success() {
        return None;
    }
    response.json::<HealthBody>().ok()
}

fn read_pairing_secret(pairing_file: &Path) -> Option<String> {
    let raw = std::fs::read_to_string(pairing_file).ok()?;
    let parsed: PairingFile = serde_json::from_str(&raw).ok()?;
    parsed.pairing_secret.filter(|s| !s.trim().is_empty())
}

fn open_session(client: &reqwest::blocking::Client, base_url: &str, secret: &str) -> Option<String> {
    let response = client
        .post(format!("{base_url}/capture/session"))
        .json(&SessionRequest { pairing_secret: secret })
        .send()
        .ok()?;
    if !response.status().is_success() {
        return None;
    }
    response.json::<SessionResponse>().ok().map(|r| r.session_token)
}

/// Same placement rule Python's `pairing.pairing_file_path()` uses -- beside the settings file, so
/// `CALLOSUM_SETTINGS_PATH` keeps tests hermetic and production sits under `~/.callosum/`. Computed
/// identically in both languages rather than one process telling the other where to look.
fn pairing_file_path() -> PathBuf {
    let settings_path = std::env::var_os("CALLOSUM_SETTINGS_PATH")
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| home_dir().join(".callosum").join("app-settings.json"));
    settings_path
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(home_dir)
        .join("capture-pairing.json")
}

fn home_dir() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_default()
}

/// The same per-user app-data directory Tauri's `app_data_dir()` resolves for identifier
/// `com.callosum.desktop` (confirmed against `backend.rs::resolved_paths`) -- this binary has no
/// `AppHandle` of its own (the browser launches it directly, outside any Tauri context), so it
/// replicates the OS-specific known-folder rule rather than depending on a running Tauri app.
fn app_data_dir() -> PathBuf {
    if cfg!(windows) {
        PathBuf::from(std::env::var_os("APPDATA").unwrap_or_default()).join(APP_IDENTIFIER)
    } else if cfg!(target_os = "macos") {
        home_dir().join("Library").join("Application Support").join(APP_IDENTIFIER)
    } else {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home_dir().join(".local").join("share"))
            .join(APP_IDENTIFIER)
    }
}

fn log_event(line: &str) {
    let dir = app_data_dir();
    if std::fs::create_dir_all(&dir).is_err() {
        return;
    }
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(dir.join("connector-host.log")) {
        let _ = writeln!(file, "{} {line}", chrono_stamp());
    }
}

/// A dependency-free timestamp -- this crate does not otherwise need a datetime library just for a
/// diagnostic log line, and seconds-since-epoch is plenty to correlate against a user's bug report.
fn chrono_stamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn read_message() -> Option<Vec<u8>> {
    let mut stdin = std::io::stdin();
    let mut len_bytes = [0u8; 4];
    stdin.read_exact(&mut len_bytes).ok()?;
    let len = u32::from_le_bytes(len_bytes) as usize;
    let mut payload = vec![0u8; len];
    stdin.read_exact(&mut payload).ok()?;
    Some(payload)
}

fn write_message(response: &ConnectorResponse) {
    let Ok(data) = serde_json::to_vec(response) else { return };
    let mut stdout = std::io::stdout();
    let _ = stdout.write_all(&(data.len() as u32).to_le_bytes());
    let _ = stdout.write_all(&data);
    let _ = stdout.flush();
}

fn main() {
    let identity = Identity::load();
    let allow_dev_build = std::env::var(DEV_BUILD_ENV).as_deref() == Ok("1");
    let caller_origin = std::env::args().nth(1);

    // Defense in depth (steering point 3): verify the caller BEFORE reading anything off stdin. A
    // rejected caller gets no reply at all -- not a structured refusal -- so nothing here ever
    // hands an unapproved caller a shaped protocol response to learn from. From the extension's
    // side this is indistinguishable from "the host could not be reached," which is exactly the
    // already-defined `host_unavailable` state; no new UI-facing vocabulary is needed for a path
    // that Chrome's own `allowed_origins` enforcement should make unreachable in practice.
    if !caller_is_allowed(caller_origin.as_deref(), &identity, allow_dev_build) {
        log_event(&format!(
            "caller_rejected origin={:?}",
            caller_origin.as_deref().unwrap_or("<none>")
        ));
        return;
    }

    let Some(raw) = read_message() else {
        return;
    };
    let Ok(request) = serde_json::from_slice::<ExtensionRequest>(&raw) else {
        return;
    };

    if request.protocol_version != Some(PROTOCOL_VERSION) {
        write_message(&ConnectorResponse {
            protocol_version: PROTOCOL_VERSION,
            connector_host_version: CONNECTOR_HOST_VERSION,
            connector_identity: if allow_dev_build { identity.dev_native_host_name.clone() } else { identity.native_host_name.clone() },
            runtime_state: RuntimeState::VersionIncompatible.as_str(),
            echo_of: request.id,
            ..Default::default()
        });
        return;
    }

    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .expect("a plain loopback HTTP client always builds");
    let port_file = app_data_dir().join("last-port.txt");

    let mut response = ConnectorResponse {
        protocol_version: PROTOCOL_VERSION,
        connector_host_version: CONNECTOR_HOST_VERSION,
        connector_identity: if allow_dev_build { identity.dev_native_host_name.clone() } else { identity.native_host_name.clone() },
        echo_of: request.id.clone(),
        ..Default::default()
    };

    match resolve_backend(&port_file, &client) {
        Err(state) => response.runtime_state = state.as_str(),
        Ok(body) => {
            response.instance_role = body.instance_role.clone();
            response.app_version = body.app_version.clone();
            if !instance_is_eligible(body.instance_role.as_deref(), body.app_version.as_deref(), allow_dev_build) {
                response.runtime_state = RuntimeState::NotEligibleInstance.as_str();
            } else {
                let port = read_port(&port_file).expect("resolve_backend already read this port successfully");
                let base_url = format!("http://127.0.0.1:{port}");
                let session = read_pairing_secret(&pairing_file_path()).and_then(|secret| open_session(&client, &base_url, &secret));
                match session {
                    Some(token) => {
                        response.session_token = Some(token);
                        response.backend_base_url = Some(base_url);
                        response.runtime_state = RuntimeState::Available.as_str();
                    }
                    // The pairing file may not exist yet (a startup race, or `ensure_pairing_secret()`
                    // failed closed -- see app.py's lifespan wiring), or the backend refused the
                    // secret it holds. Both are "capture cannot be authorized right now," a state the
                    // plan's original enumeration did not name; folding it into `not_eligible_instance`
                    // would misreport a correctly-identified UI backend as the wrong process, and
                    // folding it into `callosum_closed` would misreport a running backend as absent.
                    None => response.runtime_state = RuntimeState::PairingUnavailable.as_str(),
                }
            }
        }
    }

    log_event(&format!("resolved runtime_state={}", response.runtime_state));
    write_message(&response);
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::net::TcpListener;

    #[test]
    fn caller_id_requires_exact_chrome_extension_scheme_and_length() {
        assert_eq!(
            caller_extension_id("chrome-extension://joepcflpilfcdllmbfihgcihaloahcdd/"),
            Some("joepcflpilfcdllmbfihgcihaloahcdd")
        );
        assert_eq!(caller_extension_id("chrome-extension://joepcflpilfcdllmbfihgcihaloahcdd"), Some("joepcflpilfcdllmbfihgcihaloahcdd"));
        assert_eq!(caller_extension_id("https://joepcflpilfcdllmbfihgcihaloahcdd/"), None); // wrong scheme
        assert_eq!(caller_extension_id("chrome-extension://short/"), None); // wrong length
        assert_eq!(caller_extension_id("chrome-extension://JOEPCFLPILFCDLLMBFIHGCIHALOAHCD1/"), None); // out-of-alphabet
    }

    #[test]
    fn caller_allowlist_rejects_prefix_and_substring_matches() {
        let identity = Identity {
            protocol_version: 1,
            native_host_name: "org.callosum.connector".into(),
            dev_native_host_name: "org.callosum.connector.dev".into(),
            production_extension_ids: vec!["a".repeat(32)],
            dev_extension_id: "b".repeat(32),
        };
        assert!(caller_is_allowed(Some(&format!("chrome-extension://{}/", "a".repeat(32))), &identity, false));
        // A longer id that merely CONTAINS the allowed id as a substring must never match.
        let attacker = format!("{}extra-32-char-suffix-padding!!!!", "a".repeat(32));
        assert_eq!(attacker.len(), 32 + "extra-32-char-suffix-padding!!!!".len());
        assert!(!caller_is_allowed(Some(&format!("chrome-extension://{attacker}/")), &identity, false));
        // The dev id is refused unless the dev-build flag is set, even though it's a "known" id.
        assert!(!caller_is_allowed(Some(&format!("chrome-extension://{}/", "b".repeat(32))), &identity, false));
        assert!(caller_is_allowed(Some(&format!("chrome-extension://{}/", "b".repeat(32))), &identity, true));
        assert!(!caller_is_allowed(None, &identity, true));
    }

    #[test]
    fn eligibility_accepts_packaged_ui_and_gates_dev_builds_on_the_flag() {
        assert!(instance_is_eligible(Some("ui"), Some("0.5.15"), false));
        assert!(!instance_is_eligible(Some("ui"), Some("dev-4ed3196"), false));
        assert!(instance_is_eligible(Some("ui"), Some("dev-4ed3196"), true));
        assert!(!instance_is_eligible(Some("word-https"), Some("0.5.15"), false));
        assert!(!instance_is_eligible(Some("tunnel-target"), Some("0.5.15"), true));
        assert!(!instance_is_eligible(None, Some("0.5.15"), true));
        assert!(!instance_is_eligible(Some("ui"), None, true)); // unknown build identity never passes
    }

    #[test]
    fn identity_json_is_internally_consistent() {
        let identity = Identity::load();
        assert_eq!(identity.protocol_version, PROTOCOL_VERSION);
        assert_ne!(identity.native_host_name, identity.dev_native_host_name);
        assert_eq!(identity.dev_extension_id.len(), 32);
        assert!(!identity.production_extension_ids.contains(&identity.dev_extension_id));
    }

    #[test]
    fn resolving_the_backend_never_probes_a_port_other_than_the_recorded_one() {
        let dir = std::env::temp_dir().join(format!("callosum-connector-test-noscan-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let port_file = dir.join("last-port.txt");

        // Something IS listening locally, on a DIFFERENT port than the (missing) port file names.
        // If resolution ever scanned rather than trusting packaged state alone, it could find this.
        let decoy = TcpListener::bind("127.0.0.1:0").unwrap();
        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = decoy.accept() {
                let mut buf = [0u8; 256];
                let _ = stream.read(&mut buf);
            }
        });

        let client = reqwest::blocking::Client::builder().timeout(Duration::from_millis(300)).build().unwrap();
        let result = resolve_backend(&port_file, &client);
        assert_eq!(result, Err(RuntimeState::CallosumClosed));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn resolving_the_backend_reports_the_recorded_ports_health_body() {
        let dir = std::env::temp_dir().join(format!("callosum-connector-test-health-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let port_file = dir.join("last-port.txt");

        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        std::fs::write(&port_file, port.to_string()).unwrap();
        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut buf = [0u8; 1024];
                let _ = stream.read(&mut buf);
                let body = r#"{"instance_role":"ui","app_version":"0.5.15"}"#;
                let response = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(),
                    body
                );
                let _ = stream.write_all(response.as_bytes());
            }
        });

        let client = reqwest::blocking::Client::builder().timeout(Duration::from_secs(2)).build().unwrap();
        let body = resolve_backend(&port_file, &client).expect("the recorded port answers /health");
        assert_eq!(body.instance_role.as_deref(), Some("ui"));
        assert_eq!(body.app_version.as_deref(), Some("0.5.15"));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn missing_port_file_and_no_shell_process_is_closed_not_starting() {
        let dir = std::env::temp_dir().join(format!("callosum-connector-test-closed-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let port_file = dir.join("last-port.txt"); // never written
        let client = reqwest::blocking::Client::builder().timeout(Duration::from_millis(200)).build().unwrap();
        assert_eq!(resolve_backend(&port_file, &client), Err(RuntimeState::CallosumClosed));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn pairing_secret_is_read_from_beside_the_settings_file() {
        let dir = std::env::temp_dir().join(format!("callosum-connector-test-pairing-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let pairing_file = dir.join("capture-pairing.json");
        std::fs::write(&pairing_file, r#"{"pairing_secret": "abc123"}"#).unwrap();
        assert_eq!(read_pairing_secret(&pairing_file).as_deref(), Some("abc123"));
        assert_eq!(read_pairing_secret(&dir.join("missing.json")), None);
        std::fs::write(&pairing_file, r#"{"pairing_secret": "   "}"#).unwrap();
        assert_eq!(read_pairing_secret(&pairing_file), None); // blank secret treated as absent
        let _ = std::fs::remove_dir_all(&dir);
    }
}
