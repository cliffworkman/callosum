//! Launches callosum's own FastAPI/uvicorn backend as a child process, waits for it to become
//! healthy, and tears it down cleanly on shutdown. See `.claude/docs/increment-notes/` for the
//! packaging design this implements (use the separately versioned app-local CPython runtime and
//! spawn it directly with `std::process::Command` — no `tauri-plugin-shell`/sidecar needed, since
//! nothing here is invoked from the webview).

use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::AtomicBool;
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::path::BaseDirectory;
use tauri::{AppHandle, Manager};

const HEALTH_TIMEOUT: Duration = Duration::from_secs(120);
const POLL_INTERVAL: Duration = Duration::from_millis(400);
const SPAWN_RETRY_WINDOW: Duration = Duration::from_secs(2);
const MAX_SPAWN_ATTEMPTS: u32 = 3;

/// Which backend process this is (browser-capture prerequisite, issue #61).
///
/// Every child below runs the SAME `app.backend.api.app:app`, so neither the port nor
/// `CALLOSUM_APP_VERSION` can tell them apart — and one of them, the Word HTTPS companion, runs with
/// the Remote Access gate deliberately disabled. A future browser connector host must be able to pick
/// out the one canonical UI backend rather than trusting whichever sibling answers first.
///
/// Set EXPLICITLY at every spawn site. The backend never infers it from the port,
/// `CALLOSUM_DISABLE_REMOTE_ACCESS`, or `CALLOSUM_TUNNEL_TARGET` — those stay independent controls,
/// and this is identity. A child launched without it reports no role at all, which is the fail-safe:
/// an undeclared process can never pass for the UI backend.
pub(crate) const INSTANCE_ROLE_ENV: &str = "CALLOSUM_INSTANCE_ROLE";
/// The canonical UI backend — the only role a browser capture may ever target.
pub(crate) const ROLE_UI: &str = "ui";
/// The Word add-in's HTTPS companion on fixed 8443 (Remote Access gate force-disabled).
pub(crate) const ROLE_WORD_HTTPS: &str = "word-https";
/// The Quick Tunnel's fail-closed origin.
pub(crate) const ROLE_TUNNEL_TARGET: &str = "tunnel-target";

pub struct ResolvedPaths {
    pub python_exe: PathBuf,
    pub source_root: PathBuf,
    pub db_url: String,
    pub library_dir: PathBuf,
    pub log_path: PathBuf,
    /// Where the last-successful port is remembered across launches (see `pick_port`) — plain text,
    /// no secrets, just an integer. Missing/unreadable/stale is never an error, only a cache miss.
    pub port_path: PathBuf,
    pub app_data_dir: PathBuf,
    pub settings_path: PathBuf,
    pub word_https_dir: PathBuf,
}

pub enum StartupError {
    ResolvePaths(String),
    SpawnFailed(String),
    Timeout,
    CrashedEarly(String),
}

impl StartupError {
    pub fn detail(&self) -> String {
        match self {
            StartupError::ResolvePaths(m) => format!("Couldn't find the callosum backend: {m}"),
            StartupError::SpawnFailed(m) => format!("Couldn't start callosum: {m}"),
            StartupError::Timeout => {
                "Callosum is taking longer than expected to start. Retry, or check the log file."
                    .into()
            }
            StartupError::CrashedEarly(tail) => format!("Callosum stopped unexpectedly:\n{tail}"),
        }
    }
}

/// The managed child process plus whatever OS handle keeps its descendants bound to its lifetime
/// (a Windows Job Object; on Unix the child is its own process-group leader instead — see `kill`).
pub struct BackendHandle {
    pub child: Child,
    #[cfg(windows)]
    _job: win32job::Job,
}

#[derive(Default)]
pub struct BackendState(pub Mutex<Option<BackendHandle>>);

#[derive(Default)]
pub struct WordHttpsState {
    pub handle: Mutex<Option<BackendHandle>>,
    pub starting: AtomicBool,
}

/// Resolve every path the backend needs relative to the *installed* app, never the dev source tree.
pub fn resolved_paths(app: &AppHandle) -> Result<ResolvedPaths, StartupError> {
    let resolve = |rel: &str| -> Result<PathBuf, StartupError> {
        app.path()
            .resolve(rel, BaseDirectory::Resource)
            .map_err(|e| StartupError::ResolvePaths(format!("{rel}: {e}")))
    };

    let python_exe = crate::python_runtime::installed_python(app)
        .map_err(|error| StartupError::ResolvePaths(error.detail()))?;

    let source_root = resolve("callosum-src")?;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| StartupError::ResolvePaths(format!("app data dir: {e}")))?;
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| StartupError::ResolvePaths(format!("creating {}: {e}", data_dir.display())))?;

    let home_dir = app
        .path()
        .home_dir()
        .map_err(|e| StartupError::ResolvePaths(format!("home dir: {e}")))?;
    // `library_dir` is only the DEFAULT location offered for the user's library -- nothing requires
    // it to exist, and nothing about startup depends on it. It used to abort startup when Tauri
    // could not resolve a Documents directory, which on Linux happens whenever XDG_DOCUMENTS_DIR is
    // unset and ~/.config/user-dirs.dirs is absent: a bare Xvfb CI session, or a minimal/headless
    // Debian install. The result was a splash stuck on "Starting…" with no backend ever spawned,
    // indistinguishable from a genuinely broken build. Fall back instead of failing closed.
    //
    // `CALLOSUM_LIBRARY_DIR_OVERRIDE` mirrors `CALLOSUM_SETTINGS_PATH`'s existing test-override
    // pattern below. Without it, a disposable/acceptance-test launch on a real developer machine
    // resolves the SAME Documents-folder default a real install would -- a real Edge click-through
    // acceptance run found this means "the library folder" (always auto-watched and auto-rescanned
    // on launch, and where a captured PDF's bytes are written) is the developer's REAL document
    // library, entirely independent of the isolated app-data directory. The auto-rescan itself
    // failed harmlessly on every real file it tried (`[Errno 22] Invalid argument`), but the
    // resulting request volume was enough to delay a capture's own requests past a real Edge
    // extension service worker's lifetime, aborting the capture mid-flight -- a genuine, confirmed
    // test-environment hazard this override exists to remove, not a product defect.
    let library_dir = std::env::var_os("CALLOSUM_LIBRARY_DIR_OVERRIDE")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            app.path()
                .document_dir()
                .unwrap_or_else(|_| home_dir.join("Documents"))
                .join("callosum-library")
        });
    let callosum_home = home_dir.join(".callosum");

    // sqlite:/// URLs want forward slashes even on Windows.
    let db_path = data_dir.join("callosum.sqlite");
    let db_url = format!("sqlite:///{}", db_path.to_string_lossy().replace('\\', "/"));

    let settings_path = std::env::var_os("CALLOSUM_SETTINGS_PATH")
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| callosum_home.join("app-settings.json"));
    let word_https_dir = settings_path
        .parent()
        .unwrap_or(&callosum_home)
        .join("word-https");

    Ok(ResolvedPaths {
        python_exe,
        source_root,
        db_url,
        library_dir,
        log_path: data_dir.join("backend.log"),
        port_path: data_dir.join("last-port.txt"),
        app_data_dir: data_dir,
        settings_path,
        word_https_dir,
    })
}

pub(crate) fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener); // small accepted TOCTOU race; see increment notes — self-healed by the retry loop below
    Ok(port)
}

/// Reuse whatever port worked last launch, if anything else hasn't grabbed it in the meantime — this
/// is what lets external tools that only know a fixed/remembered port (the LibreOffice adapter's own
/// `~/.callosum/libreoffice.json` sidecar config, a future Word HTTPS companion process) stay pointed
/// at the right place across ordinary restarts, without changing the actual access-control boundary
/// (CORS + `AccessControlMiddleware`, not port obscurity, already gate this — see increment notes).
fn read_preferred_port(path: &Path) -> Option<u16> {
    std::fs::read_to_string(path).ok()?.trim().parse().ok()
}

fn write_preferred_port(path: &Path, port: u16) {
    let _ = std::fs::write(path, port.to_string());
}

/// Try to bind `preferred` first (if given); fall back to a fresh OS-assigned free port otherwise or
/// on conflict. Same bind-then-drop-then-launch-uvicorn-on-it approach as `pick_free_port`, just with
/// an optional specific port to try first.
fn pick_port(preferred: Option<u16>) -> std::io::Result<u16> {
    if let Some(p) = preferred {
        if let Ok(listener) = TcpListener::bind(("127.0.0.1", p)) {
            let port = listener.local_addr()?.port();
            drop(listener);
            return Ok(port);
        }
    }
    pick_free_port()
}

/// Build (but do not spawn) the canonical UI backend's command.
///
/// Split out from `spawn_backend` purely so a test can assert on what actually launches — the same
/// reason `word_https_args` is its own function. The spawn path calls this, so the two cannot drift.
fn ui_backend_command(paths: &ResolvedPaths, app_version: &str, port: u16) -> Command {
    let mut cmd = Command::new(&paths.python_exe);
    cmd.args([
        "-m",
        "uvicorn",
        "app.backend.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        &port.to_string(),
    ])
    .current_dir(&paths.source_root)
    .env("CALLOSUM_DB_URL", &paths.db_url)
    .env("CALLOSUM_LIBRARY_DIR", &paths.library_dir)
    .env("CALLOSUM_APP_VERSION", app_version)
    .env("CALLOSUM_APP_DATA_DIR", &paths.app_data_dir)
    .env("CALLOSUM_WORD_HTTPS_DIR", &paths.word_https_dir)
    .env(INSTANCE_ROLE_ENV, ROLE_UI)
    .env("PYTHONNOUSERSITE", "1")
    .env("PYTHONDONTWRITEBYTECODE", "1")
    .env_remove("PYTHONHOME")
    .env_remove("PYTHONPATH")
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());
    cmd
}

/// Spawn uvicorn against `paths` on a freshly-picked port, retrying with a new port if the process
/// exits almost immediately (the classic "address already in use" case on a personal machine where
/// something else grabbed the port in the gap between `pick_free_port` and uvicorn's own bind).
pub fn spawn_backend(
    paths: &ResolvedPaths,
    app_version: &str,
    managed_local_ai_descriptor: Option<&std::path::Path>,
) -> Result<(BackendHandle, u16), StartupError> {
    let mut last_err = String::new();
    let preferred_port = read_preferred_port(&paths.port_path);
    for attempt in 0..MAX_SPAWN_ATTEMPTS {
        // Only the first attempt tries to reuse last launch's port — a retry means that port (or
        // whatever we picked) just failed, so keep falling back to a fresh random one same as before.
        let port = if attempt == 0 {
            pick_port(preferred_port)
        } else {
            pick_free_port()
        }
        .map_err(|e| StartupError::SpawnFailed(e.to_string()))?;
        let mut cmd = ui_backend_command(paths, app_version, port);
        if let Some(path) = managed_local_ai_descriptor {
            cmd.env(crate::managed_local_ai::DESCRIPTOR_ENV, path);
        } else {
            // Only Tauri may provision this path. Do not inherit a developer shell's stale/spoofed value.
            cmd.env_remove(crate::managed_local_ai::DESCRIPTOR_ENV);
        }
        // Runtime/model paths and backend controls belong exclusively to Tauri's process owner.
        for name in crate::managed_local_ai::OWNER_ONLY_ENV {
            cmd.env_remove(name);
        }

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x0800_0000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }
        #[cfg(unix)]
        {
            use std::os::unix::process::CommandExt;
            cmd.process_group(0); // becomes its own process-group leader — see kill_backend
        }

        let mut child = match cmd.spawn() {
            Ok(c) => c,
            Err(e) => {
                last_err = e.to_string();
                continue;
            }
        };

        drain_output(&mut child, &paths.log_path);

        // Give a doomed process (e.g. port lost the race) a moment to fail fast before we commit to it.
        std::thread::sleep(SPAWN_RETRY_WINDOW);
        match child.try_wait() {
            Ok(Some(status)) => {
                last_err = format!("backend exited immediately ({status})");
                continue; // try again with a new port
            }
            Ok(None) => {
                write_preferred_port(&paths.port_path, port);
                #[cfg(windows)]
                {
                    match confine_to_job(&child) {
                        Ok(job) => return Ok((BackendHandle { child, _job: job }, port)),
                        Err(e) => {
                            let _ = child.kill();
                            return Err(StartupError::SpawnFailed(format!("job object: {e}")));
                        }
                    }
                }
                #[cfg(not(windows))]
                {
                    return Ok((BackendHandle { child }, port));
                }
            }
            Err(e) => {
                last_err = e.to_string();
                continue;
            }
        }
    }
    Err(StartupError::SpawnFailed(last_err))
}

/// The user's explicit enable flag and complete app-owned certificate pair are both required before
/// Tauri will publish a companion process. Parsing failure is a safe OFF, never an inferred opt-in.
pub fn word_https_configured(paths: &ResolvedPaths) -> bool {
    if !cfg!(any(target_os = "windows", target_os = "macos")) {
        return false;
    }
    let enabled = std::fs::read_to_string(&paths.settings_path)
        .ok()
        .and_then(|raw| serde_json::from_str::<serde_json::Value>(&raw).ok())
        .and_then(|data| {
            data.get("word_https_enabled")
                .and_then(|value| value.as_bool())
        })
        .unwrap_or(false);
    enabled
        && paths.word_https_dir.join("localhost.crt").is_file()
        && paths.word_https_dir.join("localhost.key").is_file()
}

/// Start the fixed-port packaged Word companion. It shares the same application/database contract as the
/// main backend but receives the Remote Access recovery override only in this child. Every argument is direct
/// argv; no shell participates, and the bind address is a literal loopback address.
pub fn spawn_word_https(
    paths: &ResolvedPaths,
    app_version: &str,
) -> Result<BackendHandle, StartupError> {
    if !word_https_configured(paths) {
        return Err(StartupError::SpawnFailed(
            "Word support is not enabled or its certificate files are incomplete".into(),
        ));
    }
    let mut cmd = word_https_command(paths, app_version);
    for name in crate::managed_local_ai::OWNER_ONLY_ENV {
        cmd.env_remove(name);
    }
    spawn_managed_command(
        cmd,
        &paths.app_data_dir.join("word-https.log"),
        "Word HTTPS companion",
    )
}

/// Build (but do not spawn) the Word HTTPS companion's command — testable twin of `word_https_args`.
///
/// Note it carries BOTH `CALLOSUM_DISABLE_REMOTE_ACCESS=1` (its long-standing behavior control) and
/// its own instance role. They are deliberately separate: the role is what lets a connector refuse
/// this child, rather than having to infer "auth gate disabled" from an unrelated env var.
fn word_https_command(paths: &ResolvedPaths, app_version: &str) -> Command {
    let mut cmd = Command::new(&paths.python_exe);
    cmd.args(word_https_args(paths))
        .current_dir(&paths.source_root)
        .env("CALLOSUM_DB_URL", &paths.db_url)
        .env("CALLOSUM_LIBRARY_DIR", &paths.library_dir)
        .env("CALLOSUM_APP_VERSION", app_version)
        .env("CALLOSUM_WORD_HTTPS_DIR", &paths.word_https_dir)
        .env("CALLOSUM_DISABLE_REMOTE_ACCESS", "1")
        .env(INSTANCE_ROLE_ENV, ROLE_WORD_HTTPS)
        .env("PYTHONNOUSERSITE", "1")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .env_remove("PYTHONHOME")
        .env_remove("PYTHONPATH")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env_remove(crate::managed_local_ai::DESCRIPTOR_ENV);
    cmd
}

fn word_https_args(paths: &ResolvedPaths) -> Vec<OsString> {
    vec![
        "-m".into(),
        "uvicorn".into(),
        "app.backend.api.app:app".into(),
        "--host".into(),
        "127.0.0.1".into(),
        "--port".into(),
        "8443".into(),
        "--ssl-keyfile".into(),
        paths.word_https_dir.join("localhost.key").into_os_string(),
        "--ssl-certfile".into(),
        paths.word_https_dir.join("localhost.crt").into_os_string(),
    ]
}

/// Most raw bytes `drain_reader` buffers for one log line before emitting what it has and carrying on.
///
/// The bound is on the raw pending input, before any UTF-8 decoding. A line of this many bytes or more is
/// therefore written as several log lines (an intentional policy for pathological output such as a
/// megabyte of progress-bar text without a newline: the log stays readable and memory stays bounded).
/// Ordinary lines are far below the cap and are written exactly as `BufRead::lines()` would have.
const MAX_LOG_LINE_BYTES: usize = 64 * 1024;

/// Why `drain_reader` stopped.
#[derive(Debug, PartialEq, Eq)]
#[cfg_attr(not(test), allow(dead_code))]
enum DrainEnd {
    /// The child closed its end (or exited). The normal end of a drain.
    Eof,
    /// Reading the pipe itself failed, so the stream cannot continue. Stopping is correct here; unlike a
    /// decoding problem, this is a real transport failure.
    ReadError {
        kind: std::io::ErrorKind,
        message: String,
    },
}

/// What one `drain_reader` call did. Production only needs the side effects; the counters are the test seam.
#[derive(Debug)]
#[cfg_attr(not(test), allow(dead_code))]
struct DrainOutcome {
    end: DrainEnd,
    /// Log lines written (or attempted), including over-cap continuation lines.
    lines: u64,
    /// Lines whose decoding actually required U+FFFD replacement (not merely non-ASCII lines).
    lossy_lines: u64,
    /// Log writes that failed. They never stop the drain.
    log_write_errors: u64,
}

/// Consume `reader` (a child's stdout or stderr) to its end, writing each line to `sink`.
///
/// A child's output is a byte stream. The layers are kept separate on purpose:
/// 1. transport: raw bytes are read with `read_until`, so no byte sequence can make the read fail;
/// 2. framing: at most `MAX_LOG_LINE_BYTES` raw bytes per line, terminator stripped like `lines()` does
///    (one `\n`, then one `\r`; a bare `\r` is data);
/// 3. presentation: lossy UTF-8 decoding, only so the log stays valid UTF-8 (`last_lines` reads it back as a
///    `String`); this assumes nothing about the child's locale or code page;
/// 4. the log write, which is best effort.
///
/// Decoding problems and log-sink failures never stop the drain: the pipe's read end must stay open for as
/// long as the child lives, because a child that writes to a pipe nobody reads fails (#98: Python's cp1252
/// stderr wrote U+2014 as the invalid-UTF-8 byte 0x97, the old `lines().map_while(Result::ok)` loop ended
/// there, and the child's next stderr write raised `OSError(22)`). Only a genuine read error ends the drain
/// early, and it is reported to the log on a best-effort basis.
fn drain_reader<R: std::io::Read, W: std::io::Write>(
    reader: R,
    stream: &str,
    sink: &mut W,
) -> DrainOutcome {
    use std::io::Read;

    let mut reader = BufReader::new(reader);
    let mut chunk: Vec<u8> = Vec::new();
    let mut framed: Vec<u8> = Vec::new();
    let (mut lines, mut lossy_lines, mut log_write_errors) = (0u64, 0u64, 0u64);

    // Frame the raw bytes in `chunk` as one log line and write it. Never fails, never stops the drain.
    let mut emit = |chunk: &mut Vec<u8>, terminated: bool| {
        if terminated {
            chunk.pop(); // the `\n`
            if chunk.last() == Some(&b'\r') {
                chunk.pop();
            }
        }
        let text = String::from_utf8_lossy(chunk);
        if matches!(text, std::borrow::Cow::Owned(_)) {
            lossy_lines += 1;
        }
        framed.clear();
        framed.extend_from_slice(text.as_bytes());
        framed.push(b'\n');
        lines += 1;
        if sink.write_all(&framed).is_err() {
            log_write_errors += 1;
        }
    };

    let end = loop {
        chunk.clear();
        match (&mut reader)
            .take(MAX_LOG_LINE_BYTES as u64)
            .read_until(b'\n', &mut chunk)
        {
            // `read_until` retries `Interrupted` itself.
            Ok(0) => break DrainEnd::Eof,
            Ok(_) => {
                let terminated = chunk.last() == Some(&b'\n');
                emit(&mut chunk, terminated);
            }
            Err(error) => {
                // Bytes read before the error still belong in the log.
                if !chunk.is_empty() {
                    emit(&mut chunk, false);
                }
                break DrainEnd::ReadError {
                    kind: error.kind(),
                    message: error.to_string(),
                };
            }
        }
    };

    if let DrainEnd::ReadError { kind, message } = &end {
        let _ = writeln!(
            sink,
            "[callosum-supervisor] {stream} drain stopped: read error ({kind:?}): {message}"
        );
    }
    DrainOutcome {
        end,
        lines,
        lossy_lines,
        log_write_errors,
    }
}

/// Drain stdout/stderr on background threads into a rotating-by-restart log file — the only
/// debugging channel into a real user's machine, so keep it even after the health check passes.
///
/// Each stream is always consumed to its end, whatever the child writes and whether or not the log file
/// can be opened (then the output is discarded): see `drain_reader` for why.
fn drain_output(child: &mut Child, log_path: &Path) {
    for (stream, pipe) in [
        (
            "stdout",
            child
                .stdout
                .take()
                .map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        ),
        (
            "stderr",
            child
                .stderr
                .take()
                .map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        ),
    ]
    .into_iter()
    .filter_map(|(stream, pipe)| pipe.map(|pipe| (stream, pipe)))
    {
        let path = log_path.to_path_buf();
        std::thread::spawn(move || {
            match std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&path)
            {
                Ok(mut log) => drain_reader(pipe, stream, &mut log),
                Err(_) => drain_reader(pipe, stream, &mut std::io::sink()),
            };
        });
    }
}

/// Spawn one app-owned child with the same hidden-window/process-group and process-tree guarantees used by
/// the primary backend. Callers construct direct argv and a child-only environment before crossing this seam.
pub(crate) fn spawn_managed_command(
    mut command: Command,
    log_path: &Path,
    label: &str,
) -> Result<BackendHandle, StartupError> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        command.creation_flags(CREATE_NO_WINDOW);
    }
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        command.process_group(0);
    }
    let mut child = command
        .spawn()
        .map_err(|error| StartupError::SpawnFailed(format!("{label}: {error}")))?;
    drain_output(&mut child, log_path);
    std::thread::sleep(SPAWN_RETRY_WINDOW);
    match child.try_wait() {
        Ok(Some(status)) => Err(StartupError::SpawnFailed(format!(
            "{label} exited immediately ({status})"
        ))),
        Ok(None) => {
            #[cfg(windows)]
            {
                match confine_to_job(&child) {
                    Ok(job) => Ok(BackendHandle { child, _job: job }),
                    Err(error) => {
                        let _ = child.kill();
                        Err(StartupError::SpawnFailed(format!(
                            "{label} job object: {error}"
                        )))
                    }
                }
            }
            #[cfg(not(windows))]
            {
                Ok(BackendHandle { child })
            }
        }
        Err(error) => {
            let _ = child.kill();
            Err(StartupError::SpawnFailed(error.to_string()))
        }
    }
}

#[cfg(windows)]
fn confine_to_job(child: &Child) -> Result<win32job::Job, String> {
    use std::os::windows::io::AsRawHandle;
    let job = win32job::Job::create().map_err(|e| e.to_string())?;
    let mut info = job.query_extended_limit_info().map_err(|e| e.to_string())?;
    info.limit_kill_on_job_close();
    job.set_extended_limit_info(&info)
        .map_err(|e| e.to_string())?;
    job.assign_process(child.as_raw_handle() as isize)
        .map_err(|e| e.to_string())?;
    Ok(job)
}

fn last_lines(path: &PathBuf, n: usize) -> String {
    std::fs::read_to_string(path)
        .ok()
        .map(|s| {
            s.lines()
                .rev()
                .take(n)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .collect::<Vec<_>>()
                .join("\n")
        })
        .unwrap_or_default()
}

/// Poll `/health` until it answers 200, the backend dies, or `HEALTH_TIMEOUT` elapses. Uvicorn does
/// not bind its socket until *after* `app.py`'s eager ML imports finish, so a plain connection-refused
/// is the expected steady state early on, not an error — only a dead child or a blown deadline are.
pub async fn wait_for_health(
    handle: &mut BackendHandle,
    port: u16,
    log_path: &PathBuf,
) -> Result<(), StartupError> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| StartupError::SpawnFailed(e.to_string()))?;
    let url = format!("http://127.0.0.1:{port}/health");
    let deadline = Instant::now() + HEALTH_TIMEOUT;

    loop {
        if let Ok(resp) = client.get(&url).send().await {
            if resp.status().is_success() {
                return Ok(());
            }
        }
        if let Ok(Some(_status)) = handle.child.try_wait() {
            return Err(StartupError::CrashedEarly(last_lines(log_path, 20)));
        }
        if Instant::now() > deadline {
            return Err(StartupError::Timeout);
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

/// Readiness for the companion uses its exact generated certificate as the reqwest trust anchor. There is no
/// global invalid-certificate bypass, and the URL uses the certificate's literal 127.0.0.1 SAN.
pub async fn wait_for_word_https_health(
    handle: &mut BackendHandle,
    paths: &ResolvedPaths,
) -> Result<(), StartupError> {
    let cert_pem = std::fs::read(paths.word_https_dir.join("localhost.crt"))
        .map_err(|e| StartupError::SpawnFailed(format!("reading Word certificate: {e}")))?;
    let root = reqwest::Certificate::from_pem(&cert_pem)
        .map_err(|e| StartupError::SpawnFailed(format!("parsing Word certificate: {e}")))?;
    let client = reqwest::Client::builder()
        .add_root_certificate(root)
        .timeout(Duration::from_secs(2))
        .build()
        .map_err(|e| StartupError::SpawnFailed(e.to_string()))?;
    let deadline = Instant::now() + HEALTH_TIMEOUT;
    let log_path = paths.app_data_dir.join("word-https.log");
    loop {
        if let Ok(resp) = client.get("https://127.0.0.1:8443/health").send().await {
            if resp.status().is_success() {
                return Ok(());
            }
        }
        if let Ok(Some(_status)) = handle.child.try_wait() {
            return Err(StartupError::CrashedEarly(last_lines(&log_path, 20)));
        }
        if Instant::now() > deadline {
            return Err(StartupError::Timeout);
        }
        tokio::time::sleep(POLL_INTERVAL).await;
    }
}

/// Kill the whole backend process tree. On Windows the Job Object guarantees every descendant dies
/// with it (even on our own crash); on Unix, signal the process group the child leads, not just the
/// one PID — `joblib`/scikit-learn worker subprocesses would otherwise be orphaned, re-creating the
/// exact DB-lock failure mode incs 272-281 fought at the app layer.
pub fn kill_backend(state: &BackendState) {
    if let Some(mut handle) = state.0.lock().unwrap().take() {
        kill_handle(&mut handle);
    }
}

pub fn kill_word_https(state: &WordHttpsState) {
    if let Some(mut handle) = state.handle.lock().unwrap().take() {
        kill_handle(&mut handle);
    }
}

pub(crate) fn kill_handle(handle: &mut BackendHandle) {
    #[cfg(windows)]
    {
        let _ = handle.child.kill(); // the retained Job Object also guarantees tree cleanup
    }
    #[cfg(unix)]
    {
        let pid = handle.child.id() as i32;
        unsafe {
            libc::kill(-pid, libc::SIGTERM);
        }
        let _ = handle.child.wait();
    }
    let _ = handle.child.wait();
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture_paths(root: &Path) -> ResolvedPaths {
        ResolvedPaths {
            python_exe: root.join("python"),
            source_root: root.join("source"),
            db_url: "sqlite:///fixture.sqlite".into(),
            library_dir: root.join("library"),
            log_path: root.join("backend.log"),
            port_path: root.join("last-port.txt"),
            app_data_dir: root.join("app-data"),
            settings_path: root.join("settings.json"),
            word_https_dir: root.join("word-https"),
        }
    }

    #[test]
    fn word_https_requires_explicit_true_and_both_files() {
        let root = std::env::temp_dir().join(format!("callosum-word-https-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(root.join("word-https")).unwrap();
        let paths = fixture_paths(&root);
        std::fs::write(&paths.settings_path, r#"{"word_https_enabled":false}"#).unwrap();
        std::fs::write(paths.word_https_dir.join("localhost.crt"), "cert").unwrap();
        std::fs::write(paths.word_https_dir.join("localhost.key"), "key").unwrap();
        assert!(!word_https_configured(&paths));
        std::fs::write(&paths.settings_path, r#"{"word_https_enabled":true}"#).unwrap();
        assert!(word_https_configured(&paths));
        std::fs::remove_file(paths.word_https_dir.join("localhost.key")).unwrap();
        assert!(!word_https_configured(&paths));
        let _ = std::fs::remove_dir_all(root);
    }

    /// The value a built command would actually pass for `name` (`None` if it removes/omits it).
    fn env_value(cmd: &Command, name: &str) -> Option<String> {
        cmd.get_envs().find_map(|(key, value)| {
            (key == std::ffi::OsStr::new(name))
                .then(|| value.map(|v| v.to_string_lossy().into_owned()))
                .flatten()
        })
    }

    #[test]
    fn each_backend_child_declares_its_instance_role() {
        // Browser-capture prerequisite (#61): all three children serve the SAME FastAPI app, so a
        // connector host cannot tell them apart by port or version. Each must declare its own role.
        let paths = fixture_paths(Path::new("fixture root"));
        let ui = ui_backend_command(&paths, "0.5.15", 53459);
        let word = word_https_command(&paths, "0.5.15");

        assert_eq!(env_value(&ui, INSTANCE_ROLE_ENV).as_deref(), Some(ROLE_UI));
        assert_eq!(
            env_value(&word, INSTANCE_ROLE_ENV).as_deref(),
            Some(ROLE_WORD_HTTPS)
        );
    }

    #[test]
    fn instance_roles_are_pairwise_distinct() {
        // The whole point: siblings stay distinguishable even though they run the same application.
        let roles = [ROLE_UI, ROLE_WORD_HTTPS, ROLE_TUNNEL_TARGET];
        let unique: std::collections::BTreeSet<_> = roles.iter().collect();
        assert_eq!(unique.len(), roles.len());
        assert!(roles.iter().all(|role| !role.is_empty()));
    }

    #[test]
    fn instance_role_is_independent_of_the_remote_access_control() {
        // Role is identity, NOT a restatement of a behavior flag. The Word child keeps carrying
        // CALLOSUM_DISABLE_REMOTE_ACCESS=1 as before; the role is what a connector refuses it by, so
        // neither may be inferred from the other.
        let paths = fixture_paths(Path::new("fixture root"));
        let word = word_https_command(&paths, "0.5.15");

        assert_eq!(
            env_value(&word, "CALLOSUM_DISABLE_REMOTE_ACCESS").as_deref(),
            Some("1")
        );
        assert_eq!(
            env_value(&word, INSTANCE_ROLE_ENV).as_deref(),
            Some(ROLE_WORD_HTTPS)
        );
        // ...and the UI backend never inherits that control.
        let ui = ui_backend_command(&paths, "0.5.15", 53459);
        assert_eq!(env_value(&ui, "CALLOSUM_DISABLE_REMOTE_ACCESS"), None);
    }

    #[test]
    fn ui_backend_argv_stays_loopback_on_the_picked_port() {
        // Guards the command-construction extraction: the args must be what they were before.
        let paths = fixture_paths(Path::new("fixture root"));
        let cmd = ui_backend_command(&paths, "0.5.15", 53459);
        let args: Vec<_> = cmd
            .get_args()
            .map(|value| value.to_string_lossy().into_owned())
            .collect();

        assert_eq!(args[2], "app.backend.api.app:app");
        assert_eq!(args[4], "127.0.0.1");
        assert_eq!(args[6], "53459");
        assert!(!args.iter().any(|value| value == "0.0.0.0"));
    }

    #[test]
    fn word_https_argv_is_fixed_loopback_tls() {
        let paths = fixture_paths(Path::new("fixture root"));
        let args = word_https_args(&paths);
        let text: Vec<_> = args.iter().map(|value| value.to_string_lossy()).collect();
        assert_eq!(text[4], "127.0.0.1");
        assert_eq!(text[6], "8443");
        assert_eq!(text[7], "--ssl-keyfile");
        assert_eq!(text[9], "--ssl-certfile");
        assert!(!text.iter().any(|value| value.as_ref() == "0.0.0.0"));
    }

    // ---- #98: the supervisor must keep draining a live child's pipes ------------------------------
    //
    // Process-level regression through the REAL `drain_output`: the test re-executes its own binary as a
    // child whose stderr carries non-UTF-8 bytes followed by more valid output. The child writes with raw
    // `write_all(..).expect(..)`, so if the supervisor ever stops draining (and the pipe's read end closes),
    // the CHILD itself fails -- the same shape as #98 at the process boundary, asserted portably (no errno).

    const DRAIN_CHILD_ENV: &str = "CALLOSUM_DRAIN_TEST_CHILD";

    /// Helper executed as the child (never as a normal test). Emits valid text, invalid UTF-8, then several
    /// more valid lines separated by enough time that a dead reader would have been noticed by then.
    #[test]
    #[ignore = "helper: re-executed as a child by the drain regression tests"]
    fn drain_test_child_writer() {
        use std::io::Write;
        if std::env::var_os(DRAIN_CHILD_ENV).is_none() {
            return;
        }
        let mut out = std::io::stdout();
        let mut err = std::io::stderr();
        out.write_all(b"stdout-marker-1\n").expect("stdout write 1");
        out.flush().expect("stdout flush 1");
        err.write_all(b"valid-before\n")
            .expect("stderr valid-before");
        err.write_all(b"bad \x97 byte end\n")
            .expect("stderr invalid bytes");
        for i in 1..=3 {
            std::thread::sleep(Duration::from_millis(300));
            err.write_all(format!("valid-after-{i}\n").as_bytes())
                .unwrap_or_else(|e| {
                    panic!("stderr valid-after-{i} failed (pipe consumer gone?): {e}")
                });
        }
        out.write_all(b"stdout-marker-2\n").expect("stdout write 2");
        out.flush().expect("stdout flush 2");
    }

    /// Spawn the helper as a piped child, hand it to the real `drain_output`, and return
    /// (child exited successfully, exit description).
    fn run_drain_child(log_path: &Path) -> (bool, String) {
        let exe = std::env::current_exe().expect("current_exe");
        let module = module_path!()
            .split_once("::")
            .map(|(_, rest)| rest)
            .expect("module path has a crate prefix");
        let mut child = Command::new(exe)
            .args([
                "--exact",
                &format!("{module}::drain_test_child_writer"),
                "--ignored",
                "--nocapture",
                "--test-threads=1",
            ])
            .env(DRAIN_CHILD_ENV, "1")
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("spawn drain test child");
        drain_output(&mut child, log_path);
        let deadline = Instant::now() + Duration::from_secs(30);
        loop {
            match child.try_wait().expect("try_wait") {
                Some(status) => return (status.success(), format!("{status}")),
                None if Instant::now() > deadline => {
                    let _ = child.kill();
                    let _ = child.wait();
                    return (false, "timed out after 30s".into());
                }
                None => std::thread::sleep(Duration::from_millis(50)),
            }
        }
    }

    /// The drain threads are detached; wait until both stdout markers (and thus everything the child wrote)
    /// reached the log, or give up. Returns whatever the log holds.
    fn wait_for_log_marker(log_path: &Path, marker: &str) -> String {
        let deadline = Instant::now() + Duration::from_secs(15);
        loop {
            let text = std::fs::read_to_string(log_path).unwrap_or_default();
            if text.contains(marker) || Instant::now() > deadline {
                return text;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    fn drain_test_root(tag: &str) -> PathBuf {
        let root =
            std::env::temp_dir().join(format!("callosum-drain-{}-{tag}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        root
    }

    #[test]
    fn drain_survives_invalid_utf8_from_a_live_child() {
        let root = drain_test_root("invalid-utf8");
        let log = root.join("backend.log");

        let (child_ok, status) = run_drain_child(&log);
        let text = wait_for_log_marker(&log, "stdout-marker-2");

        assert!(
            child_ok,
            "child did not exit successfully ({status}); a dead pipe consumer harms the child. log:\n{text}"
        );
        assert!(text.contains("valid-before"), "log:\n{text}");
        assert!(
            text.contains("bad \u{FFFD} byte end"),
            "invalid bytes should be represented lossily, not dropped; log:\n{text}"
        );
        for i in 1..=3 {
            assert!(
                text.contains(&format!("valid-after-{i}")),
                "valid-after-{i} missing (drain stopped at the invalid line?); log:\n{text}"
            );
        }
        assert!(text.contains("stdout-marker-1"), "log:\n{text}");
        assert!(
            text.contains("stdout-marker-2"),
            "stdout stream not drained; log:\n{text}"
        );
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn drain_survives_an_unopenable_log_file() {
        let root = drain_test_root("unopenable-log");
        // Parent directory does not exist, so `OpenOptions::open` fails: no persistent log can be produced.
        let log = root.join("no-such-dir").join("backend.log");

        let (child_ok, status) = run_drain_child(&log);

        assert!(
            child_ok,
            "child did not exit successfully ({status}); a log-file failure must not close the child's pipes"
        );
        assert!(!log.exists());
        let _ = std::fs::remove_dir_all(root);
    }

    // ---- #98: `drain_reader` unit tests (no processes) -------------------------------------------
    //
    // Nothing here depends on ordering between the two streams: each test drains ONE reader into its own
    // sink. Cross-stream interleaving in the shared backend.log is not a property these tests (or the
    // implementation) claim.

    /// Drain `input` with the real `drain_reader`; return the bytes written to the log and the outcome.
    fn drain_bytes(input: &[u8]) -> (Vec<u8>, DrainOutcome) {
        let mut sink: Vec<u8> = Vec::new();
        let outcome = drain_reader(std::io::Cursor::new(input.to_vec()), "stderr", &mut sink);
        (sink, outcome)
    }

    /// What the pre-#98 loop wrote for input that is valid UTF-8: `lines()` + `writeln!`.
    fn reference_lines_writeln(input: &str) -> String {
        use std::io::{BufRead, Write};
        let mut out: Vec<u8> = Vec::new();
        for line in std::io::Cursor::new(input.as_bytes().to_vec())
            .lines()
            .map_while(Result::ok)
        {
            writeln!(out, "{line}").unwrap();
        }
        String::from_utf8(out).unwrap()
    }

    /// A reader that hands out at most `step` bytes per `read` call, to show that framing depends only on
    /// the byte stream and never on how the OS happened to chunk it.
    struct Trickle {
        data: Vec<u8>,
        pos: usize,
        step: usize,
    }

    impl std::io::Read for Trickle {
        fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
            let n = self.step.min(buf.len()).min(self.data.len() - self.pos);
            buf[..n].copy_from_slice(&self.data[self.pos..self.pos + n]);
            self.pos += n;
            Ok(n)
        }
    }

    /// Replays scripted `read` results, then reports EOF.
    struct Scripted {
        steps: std::collections::VecDeque<std::io::Result<Vec<u8>>>,
    }

    impl std::io::Read for Scripted {
        fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
            match self.steps.pop_front() {
                None => Ok(0),
                Some(Err(error)) => Err(error),
                Some(Ok(bytes)) => {
                    assert!(
                        bytes.len() <= buf.len(),
                        "scripted chunk larger than read buffer"
                    );
                    buf[..bytes.len()].copy_from_slice(&bytes);
                    Ok(bytes.len())
                }
            }
        }
    }

    struct FailingSink;

    impl std::io::Write for FailingSink {
        fn write(&mut self, _buf: &[u8]) -> std::io::Result<usize> {
            Err(std::io::Error::new(std::io::ErrorKind::Other, "disk full"))
        }
        fn flush(&mut self) -> std::io::Result<()> {
            Ok(())
        }
    }

    #[test]
    fn drain_reader_keeps_going_past_invalid_utf8() {
        let (log, outcome) = drain_bytes(b"before\nbad \x97 byte end\nafter-1\nafter-2\n");

        assert_eq!(outcome.end, DrainEnd::Eof);
        assert_eq!(outcome.lines, 4);
        assert_eq!(outcome.lossy_lines, 1);
        assert_eq!(outcome.log_write_errors, 0);
        // The log must stay valid UTF-8 (`last_lines` reads it with `read_to_string`).
        let text = String::from_utf8(log).expect("log written by drain_reader is valid UTF-8");
        assert_eq!(text, "before\nbad \u{FFFD} byte end\nafter-1\nafter-2\n");
    }

    #[test]
    fn drain_reader_output_is_readable_by_last_lines_after_invalid_bytes() {
        // The crash-diagnostics contract: `last_lines` returns empty for a log that is not valid UTF-8, so a
        // startup crash after a cp1252 byte would show the user nothing.
        let (log, _) = drain_bytes(b"one\ntwo \x97 dash\nthree\n");
        let path =
            std::env::temp_dir().join(format!("callosum-lastlines-{}.log", std::process::id()));
        std::fs::write(&path, &log).unwrap();

        let tail = last_lines(&path, 20);
        let _ = std::fs::remove_file(&path);

        assert_eq!(tail, "one\ntwo \u{FFFD} dash\nthree");
    }

    #[test]
    fn drain_reader_counts_lossy_only_when_replacement_was_needed() {
        // Non-ASCII but valid UTF-8 is NOT lossy.
        let (log, outcome) =
            drain_bytes("caf\u{e9} \u{2014} \u{65e5}\u{672c}\u{8a9e} \u{2713}\n".as_bytes());
        assert_eq!(outcome.lossy_lines, 0);
        assert_eq!(
            String::from_utf8(log).unwrap(),
            "caf\u{e9} \u{2014} \u{65e5}\u{672c}\u{8a9e} \u{2713}\n"
        );

        // A truncated multi-byte sequence is invalid and IS lossy.
        let (_, outcome) = drain_bytes(b"cut \xe2\x80 short\n");
        assert_eq!(outcome.lossy_lines, 1);
    }

    #[test]
    fn drain_reader_matches_lines_and_writeln_for_valid_utf8_below_the_cap() {
        let cases = [
            "",
            "\n",
            "\r\n",
            "one\n",
            "one\ntwo\nthree\n",
            "crlf-1\r\ncrlf-2\r\n",
            "mixed\nendings\r\nhere\n",
            "a\n\n\nb\n",          // empty lines are preserved
            "no trailing newline", // partial final line is still written
            "kept\npartial tail",
            "bare\rcr\ninside\n", // a bare CR is data, not a line delimiter
            "ends-with-cr\r",     // partial final line: no terminator, so the CR stays
            "double\r\r\nstrips-one\n", // only ONE CR is stripped, like lines()
            "caf\u{e9} \u{2014} \u{65e5}\u{672c}\u{8a9e} \u{2713}\nsecond\n",
        ];
        for input in cases {
            let (log, outcome) = drain_bytes(input.as_bytes());
            assert_eq!(
                String::from_utf8(log).unwrap(),
                reference_lines_writeln(input),
                "input {input:?}"
            );
            assert_eq!(outcome.end, DrainEnd::Eof, "input {input:?}");
            assert_eq!(outcome.lossy_lines, 0, "input {input:?}");
        }
    }

    // -- The 64 KiB cap. `MAX_LOG_LINE_BYTES` bounds the RAW pending input, before any UTF-8 decoding.
    // A line whose content reaches the cap is deliberately written as several log lines (continuation
    // lines); that is the pathological-output policy, not a bug. Payload bytes are position-tagged so that
    // a lost, duplicated or reordered byte at a boundary cannot go unnoticed.

    /// `len` bytes of printable ASCII cycling with a period that does not divide the cap.
    fn payload(len: usize) -> Vec<u8> {
        (0..len).map(|i| b'!' + (i % 89) as u8).collect()
    }

    fn drain_lengths_and_payload(input: &[u8]) -> (Vec<usize>, Vec<u8>, DrainOutcome) {
        let (log, outcome) = drain_bytes(input);
        let body = log
            .strip_suffix(b"\n")
            .expect("drain output ends with a newline");
        let lengths = body.split(|b| *b == b'\n').map(<[u8]>::len).collect();
        let bytes: Vec<u8> = log.iter().copied().filter(|b| *b != b'\n').collect();
        (lengths, bytes, outcome)
    }

    #[test]
    fn drain_reader_cap_boundary_matrix_conserves_every_byte() {
        const MAX: usize = MAX_LOG_LINE_BYTES;
        const AFTER: &[u8] = b"ordinary-line-after";
        struct Case {
            name: &'static str,
            content: usize, // payload bytes before the terminator / EOF
            newline: bool,  // terminated by a newline, or by EOF
            expected_lengths: Vec<usize>,
        }
        let case = |name, content, newline, expected_lengths| Case {
            name,
            content,
            newline,
            expected_lengths,
        };
        let cases = [
            // First newline at index MAX-1: the terminator is the MAX-th byte, so this is still one ordinary line.
            case("newline at MAX-1", MAX - 1, true, vec![MAX - 1]),
            // First newline at index MAX: the chunk is full before the newline is seen, so the MAX payload
            // bytes are one line and the lone newline then terminates an empty continuation line.
            case("newline at MAX", MAX, true, vec![MAX, 0]),
            // First newline at index MAX+1.
            case("newline at MAX+1", MAX + 1, true, vec![MAX, 1]),
            // Exactly MAX bytes then EOF: one partial final line, no phantom empty line.
            case("MAX then EOF", MAX, false, vec![MAX]),
            case("MAX+1 then EOF", MAX + 1, false, vec![MAX, 1]),
            // Several consecutive over-cap chunks before the newline.
            case(
                "three chunks then newline",
                3 * MAX + 7,
                true,
                vec![MAX, MAX, MAX, 7],
            ),
            case(
                "exactly 2*MAX then newline",
                2 * MAX,
                true,
                vec![MAX, MAX, 0],
            ),
        ];

        for case in cases {
            let body = payload(case.content);
            let mut input = body.clone();
            let mut expected_lengths = case.expected_lengths.clone();
            let mut expected_bytes = body;
            if case.newline {
                // A later ordinary line must still arrive after any continuation lines.
                input.extend_from_slice(
                    b"
",
                );
                input.extend_from_slice(AFTER);
                input.extend_from_slice(
                    b"
",
                );
                expected_lengths.push(AFTER.len());
                expected_bytes.extend_from_slice(AFTER);
            }

            let (lengths, bytes, outcome) = drain_lengths_and_payload(&input);

            assert_eq!(
                lengths, expected_lengths,
                "{}: continuation boundaries",
                case.name
            );
            assert!(
                bytes == expected_bytes,
                "{}: every payload byte must appear exactly once, in order (none lost, none duplicated)",
                case.name
            );
            assert_eq!(outcome.end, DrainEnd::Eof, "{}", case.name);
            assert_eq!(
                outcome.lines as usize,
                expected_lengths.len(),
                "{}",
                case.name
            );
            assert_eq!(outcome.lossy_lines, 0, "{}", case.name);
        }
    }

    #[test]
    fn drain_reader_framing_does_not_depend_on_how_the_os_chunks_the_pipe() {
        const MAX: usize = MAX_LOG_LINE_BYTES;
        let mut input = payload(MAX + 10);
        input.extend_from_slice(b"\nsecond\r\nthird");
        let (whole, _) = drain_bytes(&input);

        for step in [1, 7, 4096, MAX - 1, MAX, MAX + 1] {
            let mut sink: Vec<u8> = Vec::new();
            let reader = Trickle {
                data: input.clone(),
                pos: 0,
                step,
            };
            drain_reader(reader, "stdout", &mut sink);
            assert!(sink == whole, "read chunk size {step} changed the framing");
        }
    }

    #[test]
    fn drain_reader_splitting_a_multibyte_char_at_the_cap_is_lossy_not_fatal() {
        // The cap is on raw bytes, so a multi-byte character straddling it is split. That is part of the
        // pathological-line policy: replacement characters, never an error, and draining carries on.
        let mut input = vec![b'a'; MAX_LOG_LINE_BYTES - 1];
        input.extend_from_slice("\u{e9}".as_bytes()); // 2 bytes: the first is chunk-final, the second starts the next
        input.extend_from_slice(b"\nafter\n");

        let (log, outcome) = drain_bytes(&input);

        assert_eq!(outcome.end, DrainEnd::Eof);
        assert_eq!(outcome.lossy_lines, 2);
        let text = String::from_utf8(log).unwrap();
        assert!(text.ends_with("\nafter\n"));
        assert_eq!(text.matches('\u{FFFD}').count(), 2);
    }

    #[test]
    fn drain_reader_read_error_stops_keeps_earlier_bytes_and_reports_it() {
        use std::io::{Error, ErrorKind};
        let reader = Scripted {
            steps: [
                Ok(b"one\ntwo-partial".to_vec()),
                Err(Error::new(ErrorKind::Other, "boom")),
            ]
            .into(),
        };
        let mut sink: Vec<u8> = Vec::new();

        let outcome = drain_reader(reader, "stderr", &mut sink);

        assert_eq!(
            outcome.end,
            DrainEnd::ReadError {
                kind: ErrorKind::Other,
                message: "boom".into()
            }
        );
        assert_eq!(
            String::from_utf8(sink).unwrap(),
            "one\ntwo-partial\n[callosum-supervisor] stderr drain stopped: read error (Other): boom\n"
        );
    }

    #[test]
    fn drain_reader_retries_interrupted_reads() {
        use std::io::{Error, ErrorKind};
        let reader = Scripted {
            steps: [
                Ok(b"a\n".to_vec()),
                Err(Error::new(ErrorKind::Interrupted, "signal")),
                Ok(b"b\n".to_vec()),
            ]
            .into(),
        };
        let mut sink: Vec<u8> = Vec::new();

        let outcome = drain_reader(reader, "stdout", &mut sink);

        assert_eq!(outcome.end, DrainEnd::Eof);
        assert_eq!(String::from_utf8(sink).unwrap(), "a\nb\n");
    }

    #[test]
    fn drain_reader_consumes_everything_even_when_every_log_write_fails() {
        // A log that cannot be written (disk full, revoked, ...) must not stop the reads: the child's pipe
        // has to keep being emptied or the child itself starts failing (#98).
        let mut input = Vec::new();
        for i in 0..1000 {
            input.extend_from_slice(format!("line {i} \u{2014}\n").as_bytes());
            input.extend_from_slice(b"invalid \x97 line\n");
        }
        let mut reader = std::io::Cursor::new(input.clone());

        let outcome = drain_reader(&mut reader, "stderr", &mut FailingSink);

        assert_eq!(outcome.end, DrainEnd::Eof);
        assert_eq!(
            reader.position() as usize,
            input.len(),
            "the whole stream was consumed"
        );
        assert_eq!(outcome.lines, 2000);
        assert_eq!(outcome.log_write_errors, 2000);
    }

    #[test]
    fn drain_reader_into_a_discarding_sink_consumes_to_eof() {
        // The `io::sink()` used when the log file cannot be opened.
        let input = b"x \x97 y\nz\n".to_vec();
        let mut reader = std::io::Cursor::new(input.clone());
        let outcome = drain_reader(&mut reader, "stdout", &mut std::io::sink());
        assert_eq!(outcome.end, DrainEnd::Eof);
        assert_eq!(reader.position() as usize, input.len());
        assert_eq!(outcome.log_write_errors, 0);
    }
}
