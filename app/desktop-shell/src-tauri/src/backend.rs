//! Launches callosum's own FastAPI/uvicorn backend as a child process, waits for it to become
//! healthy, and tears it down cleanly on shutdown. See `.claude/docs/increment-notes/` for the
//! packaging design this implements (bundle a portable CPython + real deps via `bundle.resources`,
//! spawn it directly with `std::process::Command` — no `tauri-plugin-shell`/sidecar needed, since
//! nothing here is invoked from the webview).

use std::io::{BufRead, BufReader};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager};
use tauri::path::BaseDirectory;

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
                "Callosum is taking longer than expected to start. Retry, or check the log file.".into()
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
    job: win32job::Job,
}

#[derive(Default)]
pub struct BackendState(pub Mutex<Option<BackendHandle>>);

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

    // sqlite:/// URLs want forward slashes even on Windows.
    let db_path = data_dir.join("callosum.sqlite");
    let db_url = format!("sqlite:///{}", db_path.to_string_lossy().replace('\\', "/"));

    Ok(ResolvedPaths {
        python_exe,
        source_root,
        db_url,
        library_dir,
        log_path: data_dir.join("backend.log"),
    })
}

fn pick_free_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    let port = listener.local_addr()?.port();
    drop(listener); // small accepted TOCTOU race; see increment notes — self-healed by the retry loop below
    Ok(port)
}

/// Spawn uvicorn against `paths` on a freshly-picked port, retrying with a new port if the process
/// exits almost immediately (the classic "address already in use" case on a personal machine where
/// something else grabbed the port in the gap between `pick_free_port` and uvicorn's own bind).
pub fn spawn_backend(paths: &ResolvedPaths, app_version: &str) -> Result<(BackendHandle, u16), StartupError> {
    let mut last_err = String::new();
    for _ in 0..MAX_SPAWN_ATTEMPTS {
        let port = pick_free_port().map_err(|e| StartupError::SpawnFailed(e.to_string()))?;
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
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

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
                #[cfg(windows)]
                {
                    match confine_to_job(&child) {
                        Ok(job) => return Ok((BackendHandle { child, job }, port)),
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

/// Drain stdout/stderr on background threads into a rotating-by-restart log file — the only
/// debugging channel into a real user's machine, so keep it even after the health check passes.
fn drain_output(child: &mut Child, log_path: &PathBuf) {
    for pipe in [
        child.stdout.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
        child.stderr.take().map(|s| Box::new(s) as Box<dyn std::io::Read + Send>),
    ]
    .into_iter()
    .flatten()
    {
        let path = log_path.clone();
        std::thread::spawn(move || {
            use std::io::Write;
            let reader = BufReader::new(pipe);
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&path) {
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
    job.set_extended_limit_info(&mut info).map_err(|e| e.to_string())?;
    job.assign_process(child.as_raw_handle() as isize)
        .map_err(|e| e.to_string())?;
    Ok(job)
}

fn last_lines(path: &PathBuf, n: usize) -> String {
    std::fs::read_to_string(path)
        .ok()
        .map(|s| s.lines().rev().take(n).collect::<Vec<_>>().into_iter().rev().collect::<Vec<_>>().join("\n"))
        .unwrap_or_default()
}

/// Poll `/health` until it answers 200, the backend dies, or `HEALTH_TIMEOUT` elapses. Uvicorn does
/// not bind its socket until *after* `app.py`'s eager ML imports finish, so a plain connection-refused
/// is the expected steady state early on, not an error — only a dead child or a blown deadline are.
pub async fn wait_for_health(handle: &mut BackendHandle, port: u16, log_path: &PathBuf) -> Result<(), StartupError> {
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

/// Kill the whole backend process tree. On Windows the Job Object guarantees every descendant dies
/// with it (even on our own crash); on Unix, signal the process group the child leads, not just the
/// one PID — `joblib`/scikit-learn worker subprocesses would otherwise be orphaned, re-creating the
/// exact DB-lock failure mode incs 272-281 fought at the app layer.
pub fn kill_backend(state: &BackendState) {
    if let Some(mut handle) = state.0.lock().unwrap().take() {
        #[cfg(windows)]
        {
            let _ = handle.child.kill(); // job drop below also guarantees this; belt-and-suspenders
            drop(handle.job);
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
}
