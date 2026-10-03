//! Dev-only native-messaging entry point (#61 Phase 2 acceptance follow-up).
//!
//! Chrome/Edge native-messaging manifests can only name a single executable `path` with no extra
//! fixed arguments and no way to set an environment variable -- so making the *shipped*
//! `callosum_connector` binary accept the DEV extension id (gated behind
//! `CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD`) for a developer's manually-launched Edge/Chrome needs some
//! kind of wrapper the manifest's `path` can point at instead of the real binary directly.
//!
//! The first version of that wrapper was a generated `.bat` file (`set VAR=1` then exec the real
//! binary). It worked when invoked directly by hand, but a real Edge click-through acceptance run
//! found it FAILS the real native-messaging exchange consistently: `reqwest`'s blocking HTTP client
//! inside `callosum_connector`, when launched as a grandchild of `cmd.exe` with its stdio piped
//! (exactly how Chrome invokes a native-messaging host), reliably times out connecting to
//! `127.0.0.1` -- while the identical binary invoked directly (no `cmd.exe` in the process chain)
//! connects instantly, every time, with no code difference at all. Root cause not pinned down
//! further than "going through `cmd.exe /c` with piped stdio breaks it"; the fix taken here is to
//! stop going through `cmd.exe` at all. This is a real, compiled, native Windows executable: it
//! inherits stdin/stdout/stderr by default (exactly the pipes Chrome set up) and forwards them to
//! the real binary unchanged, with no shell in the process chain.
//!
//! macOS (#61: the first concrete browser-capture user is on a Mac): the same launcher is used with the same
//! stdio-inheriting `status()` semantics -- there is no `cmd.exe` in a macOS process chain, so the Windows
//! failure does not apply, but the launcher stays a compiled binary (not a shell wrapper) so the two platforms
//! behave identically. Whether Chrome-on-macOS needs anything different (e.g. `exec` instead of a child) is
//! decided by real-hardware evidence, not assumed here.
//!
//! Registered ONLY under `dev_native_host_name` by `tools/run_dev.py`'s `_register_dev_connector`,
//! never shipped, never referenced by the production installer.

use std::env;
use std::process::Command;

/// The real connector's file name next to this launcher (`callosum_connector[.exe]`).
fn real_connector_name() -> &'static str {
    if cfg!(windows) {
        "callosum_connector.exe"
    } else {
        "callosum_connector"
    }
}

fn main() {
    let launcher_path = env::current_exe().expect("current_exe should always resolve");
    let dir = launcher_path.parent().expect("exe always has a parent dir");
    let real_binary = dir.join(real_connector_name());

    let args: Vec<String> = env::args().skip(1).collect();
    let status = Command::new(real_binary)
        .args(&args)
        .env("CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD", "1")
        .status()
        .unwrap_or_else(|error| panic!("failed to launch {} next to this launcher: {error}", real_connector_name()));

    std::process::exit(status.code().unwrap_or(1));
}

#[cfg(test)]
mod tests {
    use super::real_connector_name;

    #[test]
    fn the_real_connector_name_matches_the_platform() {
        if cfg!(windows) {
            assert_eq!(real_connector_name(), "callosum_connector.exe");
        } else {
            assert_eq!(real_connector_name(), "callosum_connector");
        }
    }
}
