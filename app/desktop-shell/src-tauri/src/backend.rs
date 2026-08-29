//! Launches callosum's own FastAPI/uvicorn backend as a child process, waits for it to become
//! healthy, and tears it down cleanly on shutdown. See `.claude/docs/increment-notes/` for the
//! packaging design this implements (bundle a portable CPython + real deps via `bundle.resources`,
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

    #[cfg(windows)]
    let python_exe = resolve("python-runtime/python.exe")?;
    #[cfg(not(windows))]
    let python_exe = resolve("python-runtime/bin/python3")?;

    let source_root = resolve("callosum-src")?;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| StartupError::ResolvePaths(format!("app data dir: {e}")))?;
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| StartupError::ResolvePaths(format!("creating {}: {e}", data_dir.display())))?;

    let docs_dir = app
        .path()
        .document_dir()
        .map_err(|e| StartupError::ResolvePaths(format!("documents dir: {e}")))?;
    let library_dir = docs_dir.join("callosum-library");
    let home_dir = app
        .path()
        .home_dir()
        .map_err(|e| StartupError::ResolvePaths(format!("home dir: {e}")))?;
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

fn pick_free_port() -> std::io::Result<u16> {
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
        .env("CALLOSUM_WORD_HTTPS_DIR", &paths.word_https_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
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
    let mut cmd = Command::new(&paths.python_exe);
    cmd.args(word_https_args(paths))
        .current_dir(&paths.source_root)
        .env("CALLOSUM_DB_URL", &paths.db_url)
        .env("CALLOSUM_LIBRARY_DIR", &paths.library_dir)
        .env("CALLOSUM_APP_VERSION", app_version)
        .env("CALLOSUM_WORD_HTTPS_DIR", &paths.word_https_dir)
        .env("CALLOSUM_DISABLE_REMOTE_ACCESS", "1")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env_remove(crate::managed_local_ai::DESCRIPTOR_ENV);
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
        cmd.process_group(0);
    }

    let mut child = cmd
        .spawn()
        .map_err(|e| StartupError::SpawnFailed(format!("Word HTTPS companion: {e}")))?;
    drain_output(&mut child, &paths.app_data_dir.join("word-https.log"));
    std::thread::sleep(SPAWN_RETRY_WINDOW);
    match child.try_wait() {
        Ok(Some(status)) => Err(StartupError::SpawnFailed(format!(
            "Word HTTPS companion exited immediately ({status})"
        ))),
        Ok(None) => {
            #[cfg(windows)]
            {
                match confine_to_job(&child) {
                    Ok(job) => Ok(BackendHandle { child, _job: job }),
                    Err(error) => {
                        let _ = child.kill();
                        Err(StartupError::SpawnFailed(format!(
                            "Word HTTPS job object: {error}"
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

/// Drain stdout/stderr on background threads into a rotating-by-restart log file — the only
/// debugging channel into a real user's machine, so keep it even after the health check passes.
fn drain_output(child: &mut Child, log_path: &Path) {
    for pipe in [
        child
            .stdout
            .take()
            .map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        child
            .stderr
            .take()
            .map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let path = log_path.to_path_buf();
        std::thread::spawn(move || {
            use std::io::Write;
            let reader = BufReader::new(pipe);
            if let Ok(mut f) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&path)
            {
                for line in reader.lines().map_while(Result::ok) {
                    let _ = writeln!(f, "{line}");
                }
            }
        });
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

fn kill_handle(handle: &mut BackendHandle) {
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
}
