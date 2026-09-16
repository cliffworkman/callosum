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
//! Registered ONLY under `dev_native_host_name` by `tools/run_dev.py`'s `_register_dev_connector`,
//! never shipped, never referenced by the production installer.

use std::env;
use std::process::Command;

fn main() {
    let launcher_path = env::current_exe().expect("current_exe should always resolve");
    let dir = launcher_path.parent().expect("exe always has a parent dir");
    let real_binary = dir.join("callosum_connector.exe");

    let args: Vec<String> = env::args().skip(1).collect();
    let status = Command::new(real_binary)
        .args(&args)
        .env("CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD", "1")
        .status()
        .expect("failed to launch callosum_connector.exe next to this launcher");

    std::process::exit(status.code().unwrap_or(1));
}
