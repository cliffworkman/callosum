//! Process-tree confinement, crash invalidation, and bounded shutdown.

use super::files::remove_private_file;
use super::{ManagedAiError, ManagedLocalAiHandle, ManagedLocalAiState, HOST};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

const SHUTDOWN_TIMEOUT: Duration = Duration::from_secs(4);

pub(super) fn process_is_running(state: &ManagedLocalAiState) -> Result<bool, ManagedAiError> {
    let mut guard = state.0.lock().expect("managed local AI state poisoned");
    let handle = guard.as_mut().ok_or(ManagedAiError::Exited)?;
    handle
        .child
        .try_wait()
        .map(|status| status.is_none())
        .map_err(|_| ManagedAiError::Exited)
}

pub(super) fn start_crash_monitor(state: ManagedLocalAiState) {
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_millis(500));
        let exited = {
            let mut guard = state.0.lock().expect("managed local AI state poisoned");
            let Some(handle) = guard.as_mut() else { return };
            matches!(handle.child.try_wait(), Ok(Some(_)) | Err(_))
        };
        if exited {
            if let Some(handle) = state
                .0
                .lock()
                .expect("managed local AI state poisoned")
                .take()
            {
                cleanup_files(&handle);
            }
            return;
        }
    });
}

/// Remove eligibility first, request bounded graceful tree shutdown, then force cleanup.
pub fn shutdown(state: &ManagedLocalAiState) {
    let Some(mut handle) = state
        .0
        .lock()
        .expect("managed local AI state poisoned")
        .take()
    else {
        return;
    };
    cleanup_files(&handle);
    request_graceful_shutdown(&mut handle);
    let deadline = Instant::now() + SHUTDOWN_TIMEOUT;
    while Instant::now() < deadline {
        if matches!(handle.child.try_wait(), Ok(Some(_))) {
            return;
        }
        std::thread::sleep(Duration::from_millis(80));
    }
    force_shutdown(&mut handle);
}

#[cfg(windows)]
fn request_graceful_shutdown(handle: &mut ManagedLocalAiHandle) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    let _ = Command::new("taskkill")
        .args(["/PID", &handle.child.id().to_string(), "/T"])
        .creation_flags(CREATE_NO_WINDOW)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status();
}

#[cfg(unix)]
fn request_graceful_shutdown(handle: &mut ManagedLocalAiHandle) {
    unsafe {
        libc::kill(-(handle.child.id() as i32), libc::SIGTERM);
    }
}

#[cfg(windows)]
pub(super) fn force_shutdown(handle: &mut ManagedLocalAiHandle) {
    let _ = handle.child.kill();
    let _ = handle.child.wait();
}

#[cfg(unix)]
pub(super) fn force_shutdown(handle: &mut ManagedLocalAiHandle) {
    unsafe {
        libc::kill(-(handle.child.id() as i32), libc::SIGKILL);
    }
    let _ = handle.child.wait();
}

fn cleanup_files(handle: &ManagedLocalAiHandle) {
    remove_private_file(&handle.descriptor_path);
    remove_private_file(&handle.token_path);
}

pub(super) fn confine_process(
    child: Child,
    descriptor_path: PathBuf,
    token_path: PathBuf,
) -> Result<ManagedLocalAiHandle, ManagedAiError> {
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        let mut child = child;
        let job = win32job::Job::create().map_err(|_| ManagedAiError::Spawn)?;
        let mut info = job
            .query_extended_limit_info()
            .map_err(|_| ManagedAiError::Spawn)?;
        info.limit_kill_on_job_close();
        job.set_extended_limit_info(&info)
            .map_err(|_| ManagedAiError::Spawn)?;
        if job.assign_process(child.as_raw_handle() as isize).is_err() {
            let _ = child.kill();
            return Err(ManagedAiError::Spawn);
        }
        Ok(ManagedLocalAiHandle {
            child,
            descriptor_path,
            token_path,
            _job: job,
        })
    }
    #[cfg(not(windows))]
    {
        Ok(ManagedLocalAiHandle {
            child,
            descriptor_path,
            token_path,
        })
    }
}

pub(super) fn pick_free_port() -> Result<u16, ManagedAiError> {
    let listener = TcpListener::bind((HOST, 0))
        .map_err(|_| ManagedAiError::Io("loopback port allocation failed"))?;
    Ok(listener
        .local_addr()
        .map_err(|_| ManagedAiError::Io("loopback port allocation failed"))?
        .port())
}
