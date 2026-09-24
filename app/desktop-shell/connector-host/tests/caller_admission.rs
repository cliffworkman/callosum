//! Real-binary tests of the connector host's caller admission (#61 Phase 1 store-readiness).
//!
//! Every test launches the ACTUAL compiled `callosum_connector` binary exactly the way a browser does: origin as
//! argv[1], one length-prefixed native-messaging frame on stdin. That is the only way to prove the properties the
//! unit tests can only assert about isolated functions: that a rejected caller gets **no reply at all** (no
//! shaped response to learn from), leaves the `caller_rejected` trace, and exits cleanly -- and that the dev-build
//! flag has to be exactly `1`.
//!
//! The identity is compiled in (`include_str!`), so these run against the identity that ships. None of them assumes
//! that identity is empty: they use ids that are provably NOT configured, so they stay valid unchanged once real
//! store ids are populated (real-id admission is proven by the unit tests with synthetic identities and, later, by
//! store-installed acceptance). Each run is hermetic: APPDATA / USERPROFILE / HOME / XDG_DATA_HOME /
//! CALLOSUM_SETTINGS_PATH all point into a throwaway directory, so nothing here touches a real Callosum install.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU32, Ordering};

const HOST: &str = env!("CARGO_BIN_EXE_callosum_connector");
const IDENTITY_JSON: &str = include_str!("../../connector/identity.json");
const DEV_FLAG: &str = "CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD";

static RUN: AtomicU32 = AtomicU32::new(0);

struct Outcome {
    stdout: Vec<u8>,
    success: bool,
    log: String,
}

fn identity() -> serde_json::Value {
    serde_json::from_str(IDENTITY_JSON).expect("identity.json parses")
}

fn dev_id() -> String {
    identity()["dev_extension_id"]
        .as_str()
        .expect("dev id")
        .to_string()
}

fn origin(id: &str) -> String {
    format!("chrome-extension://{id}/")
}

/// A well-formed extension id that is neither configured for production nor the dev id, whatever identity.json holds.
fn unconfigured_id() -> String {
    let identity = identity();
    let taken: Vec<String> = identity["production_extension_ids"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .iter()
        .filter_map(|value| value.as_str().map(str::to_string))
        .chain(std::iter::once(dev_id()))
        .collect();
    ('a'..='p')
        .map(|letter| letter.to_string().repeat(32))
        .find(|candidate| !taken.contains(candidate))
        .expect("at most 17 ids are configured, so one of the 16 uniform ids is free")
}

fn frame(json: &str) -> Vec<u8> {
    let mut bytes = (json.len() as u32).to_le_bytes().to_vec();
    bytes.extend_from_slice(json.as_bytes());
    bytes
}

fn find_log(dir: &Path) -> Option<PathBuf> {
    for entry in std::fs::read_dir(dir).ok()?.flatten() {
        let path = entry.path();
        if path.is_dir() {
            if let Some(found) = find_log(&path) {
                return Some(found);
            }
        } else if path
            .file_name()
            .is_some_and(|name| name == "connector-host.log")
        {
            return Some(path);
        }
    }
    None
}

/// Launch the host as a browser would. `origin_arg = None` means "no argv[1]"; `flag = None` leaves the dev flag unset.
fn run_host(origin_arg: Option<&str>, flag: Option<&str>, message: &str) -> Outcome {
    let root = std::env::temp_dir().join(format!(
        "callosum-connector-admission-{}-{}",
        std::process::id(),
        RUN.fetch_add(1, Ordering::SeqCst)
    ));
    let _ = std::fs::remove_dir_all(&root);
    for sub in ["appdata", "home", "xdg", "settings"] {
        std::fs::create_dir_all(root.join(sub)).unwrap();
    }

    let mut command = Command::new(HOST);
    if let Some(arg) = origin_arg {
        command.arg(arg);
    }
    command
        .env_remove(DEV_FLAG)
        .env("APPDATA", root.join("appdata"))
        .env("USERPROFILE", root.join("home"))
        .env("HOME", root.join("home"))
        .env("XDG_DATA_HOME", root.join("xdg"))
        .env(
            "CALLOSUM_SETTINGS_PATH",
            root.join("settings").join("app-settings.json"),
        )
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    if let Some(value) = flag {
        command.env(DEV_FLAG, value);
    }

    let mut child = command.spawn().expect("the connector host binary starts");
    {
        let mut stdin = child.stdin.take().expect("piped stdin");
        // A correctly rejected caller never reads this, so the pipe may already be closed: ignore write errors.
        let _ = stdin.write_all(&frame(message));
    }
    let output = child.wait_with_output().expect("the host exits on its own");
    let log = find_log(&root)
        .and_then(|path| std::fs::read_to_string(path).ok())
        .unwrap_or_default();
    let _ = std::fs::remove_dir_all(&root);
    Outcome {
        stdout: output.stdout,
        success: output.status.success(),
        log,
    }
}

fn hello() -> &'static str {
    r#"{"id":"admission-test","protocol_version":1}"#
}

fn assert_rejected_silently(outcome: &Outcome, what: &str) {
    assert!(
        outcome.stdout.is_empty(),
        "{what}: a rejected caller must get NO reply, got {} bytes",
        outcome.stdout.len()
    );
    assert!(
        outcome.success,
        "{what}: rejection is a clean exit, not a crash"
    );
    assert!(
        outcome.log.contains("caller_rejected"),
        "{what}: rejection must leave its trace, log was {:?}",
        outcome.log
    );
}

fn reply_json(outcome: &Outcome) -> serde_json::Value {
    assert!(outcome.stdout.len() > 4, "expected a framed reply");
    let length = u32::from_le_bytes(outcome.stdout[..4].try_into().unwrap()) as usize;
    assert_eq!(
        outcome.stdout.len(),
        4 + length,
        "exactly one well-formed frame"
    );
    serde_json::from_slice(&outcome.stdout[4..]).expect("reply is JSON")
}

#[test]
fn an_unconfigured_extension_gets_no_reply_and_is_logged_as_rejected() {
    // Well-formed, but not configured anywhere. Also exercised WITH the dev flag: the flag only ever admits the dev id.
    let unknown = origin(&unconfigured_id());
    for flag in [None, Some("1")] {
        assert_rejected_silently(&run_host(Some(&unknown), flag, hello()), "unconfigured id");
    }
}

#[test]
fn every_malformed_origin_is_refused_before_anything_is_read() {
    let dev = dev_id();
    let malformed = vec![
        String::new(),
        "chrome-extension://".to_string(),
        origin(&"A".repeat(32)),            // wrong case
        origin(&"a".repeat(31)),            // short
        format!("edge-extension://{dev}/"), // not a scheme any browser sends
        format!("https://{dev}/"),
        format!("chrome-extension://{dev}/extra"), // extra path
        format!("chrome-extension://user@{dev}/"), // credentials
        dev.clone(),                               // no scheme at all
    ];
    for candidate in malformed {
        // Even with the dev flag set, none of these is the dev id's exact origin.
        assert_rejected_silently(
            &run_host(Some(&candidate), Some("1"), hello()),
            &format!("origin {candidate:?}"),
        );
    }
}

#[test]
fn a_missing_argv_origin_is_rejected() {
    assert_rejected_silently(&run_host(None, Some("1"), hello()), "no argv[1]");
}

#[test]
fn the_dev_extension_id_is_refused_unless_the_dev_flag_is_exactly_one() {
    let dev = origin(&dev_id());
    for flag in [
        None,
        Some("0"),
        Some("true"),
        Some("yes"),
        Some(""),
        Some("1 "),
        Some(" 1"),
    ] {
        assert_rejected_silently(
            &run_host(Some(&dev), flag, hello()),
            &format!("dev id with flag {flag:?}"),
        );
    }
}

#[test]
fn the_flagged_dev_extension_is_admitted_and_answers_one_framed_reply() {
    let outcome = run_host(Some(&origin(&dev_id())), Some("1"), hello());
    assert!(outcome.success);
    assert!(
        !outcome.log.contains("caller_rejected"),
        "an admitted caller must not be logged as rejected"
    );
    let reply = reply_json(&outcome);
    assert_eq!(reply["protocol_version"], 1);
    // The reply names the DEV host identity, never the production one.
    assert_eq!(
        reply["connector_identity"],
        identity()["dev_native_host_name"]
    );
    assert_eq!(reply["echo_of"], "admission-test");
    // No Callosum is running against this hermetic app-data dir, so it is closed (or, if a real shell happens
    // to be running on this machine, "starting") -- never available, and never a session.
    let state = reply["runtime_state"].as_str().expect("runtime_state");
    assert!(
        ["callosum_closed", "callosum_starting"].contains(&state),
        "unexpected state {state}"
    );
    assert!(reply["session_token"].is_null());
    assert!(outcome.log.contains("resolved runtime_state="));
}

#[test]
fn an_admitted_caller_speaking_the_wrong_protocol_version_is_told_so_without_touching_the_backend()
{
    let outcome = run_host(
        Some(&origin(&dev_id())),
        Some("1"),
        r#"{"id":"v","protocol_version":999}"#,
    );
    let reply = reply_json(&outcome);
    assert_eq!(reply["runtime_state"], "version_incompatible");
    assert!(reply["session_token"].is_null());
    assert!(reply["backend_base_url"].is_null());
}
