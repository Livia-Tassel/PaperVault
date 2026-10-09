use rand::RngCore;
use serde::Serialize;
use serde_json::{json, Value};
use std::{io::{BufRead, Write}, path::PathBuf, sync::{Arc, Mutex}, time::{Duration, Instant}};
use tauri::{Emitter, Manager};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendConnection {
    base_url: String,
    token: String,
}

#[derive(Default)]
struct BackendState {
    connection: Option<BackendConnection>,
    error: Option<String>,
    terminated: bool,
    child: Option<CommandChild>,
    #[cfg(windows)]
    job: Option<ProcessJob>,
}

type SharedBackend = Arc<Mutex<BackendState>>;

#[cfg(windows)]
struct ProcessJob(usize);

#[cfg(windows)]
impl ProcessJob {
    fn attach(pid: u32) -> Result<Self, String> {
        use windows_sys::Win32::{Foundation::CloseHandle, System::{JobObjects::*, Threading::*}};
        unsafe {
            let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
            if job.is_null() { return Err(format!("创建后台进程组失败: {}", std::io::Error::last_os_error())); }
            let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits as *const _ as *const _, std::mem::size_of_val(&limits) as u32) == 0 {
                CloseHandle(job);
                return Err(format!("设置后台进程组失败: {}", std::io::Error::last_os_error()));
            }
            let process = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, 0, pid);
            if process.is_null() {
                CloseHandle(job);
                return Err(format!("打开后台进程失败: {}", std::io::Error::last_os_error()));
            }
            let assigned = AssignProcessToJobObject(job, process);
            CloseHandle(process);
            if assigned == 0 {
                CloseHandle(job);
                return Err(format!("管理后台进程失败: {}", std::io::Error::last_os_error()));
            }
            Ok(Self(job as usize))
        }
    }
}

#[cfg(windows)]
impl Drop for ProcessJob {
    fn drop(&mut self) {
        unsafe { windows_sys::Win32::Foundation::CloseHandle(self.0 as _); }
    }
}

#[tauri::command]
async fn backend_connection(state: tauri::State<'_, SharedBackend>) -> Result<BackendConnection, String> {
    let started = Instant::now();
    loop {
        {
            let backend = state.lock().map_err(|_| "后台状态不可用")?;
            if let Some(connection) = &backend.connection { return Ok(connection.clone()); }
            if let Some(error) = &backend.error { return Err(error.clone()); }
        }
        if started.elapsed() > Duration::from_secs(90) {
            return Err("后台服务启动超时。请检查日志、磁盘空间和安全软件后重启。".into());
        }
        tauri::async_runtime::spawn_blocking(|| std::thread::sleep(Duration::from_millis(100))).await.map_err(|e| e.to_string())?;
    }
}

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..").canonicalize().unwrap_or_else(|_| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../.."))
}

fn start_backend(app: &tauri::AppHandle, state: SharedBackend) -> Result<(), Box<dyn std::error::Error>> {
    let mut token_bytes = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut token_bytes);
    let token: String = token_bytes.iter().map(|b| format!("{b:02x}")).collect();
    // Model weights are colocated under this directory; keep them out of Windows roaming profiles.
    let config_dir = std::env::var_os("PAPERVAULT_CONFIG_PATH").map(PathBuf::from).unwrap_or(app.path().app_local_data_dir()?);
    let log_dir = app.path().app_log_dir()?;
    std::fs::create_dir_all(&config_dir)?;
    std::fs::create_dir_all(&log_dir)?;
    let command = if cfg!(debug_assertions) {
        let root = project_root();
        let python = if cfg!(windows) { root.join(".venv/Scripts/python.exe") } else { root.join(".venv/bin/python") };
        if !python.is_file() { return Err(format!("开发环境缺少 {}；请运行引导脚本。", python.display()).into()); }
        app.shell().command(python).args(["-m", "papervault"]).current_dir(&root).env("PYTHONPATH", root.join("backend")).env("PYTHONUNBUFFERED", "1").env("PYTHONUTF8", "1")
    } else {
        app.shell().sidecar("papervault-backend")?.env("PYTHONUNBUFFERED", "1").env("PYTHONUTF8", "1")
    };
    let (mut events, mut child) = command.spawn()?;
    #[cfg(windows)]
    let job = match ProcessJob::attach(child.pid()) {
        Ok(job) => job,
        Err(error) => { let _ = child.kill(); return Err(error.into()); }
    };
    let mut bootstrap = json!({"token": token, "config_path": config_dir});
    // Explicit overrides are useful for portable libraries and isolated E2E runs.
    for (env_name, key) in [("PAPERVAULT_LIBRARY_PATH", "library_path"), ("PAPERVAULT_MODELS_PATH", "models_path")] {
        if let Some(value) = std::env::var_os(env_name) { bootstrap[key] = json!(PathBuf::from(value)); }
    }
    child.write(format!("{}\n", bootstrap).as_bytes())?;
    {
        let mut backend = state.lock().map_err(|_| "后台状态不可用")?;
        backend.child = Some(child);
        #[cfg(windows)]
        { backend.job = Some(job); }
    }
    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        let log_path = log_dir.join("backend.log");
        while let Some(event) = events.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    if let Ok(message) = serde_json::from_slice::<Value>(&line) {
                        if message.get("type").and_then(Value::as_str) == Some("ready") {
                            let port = message.get("port").and_then(Value::as_u64).filter(|p| *p > 0 && *p <= 65535);
                            if message.get("protocol").and_then(Value::as_u64) == Some(1) {
                                if let Some(port) = port {
                                    let health_token = token.clone();
                                    let healthy = tauri::async_runtime::spawn_blocking(move || wait_for_health(port as u16, &health_token)).await.unwrap_or(false);
                                    if !healthy {
                                        if let Ok(mut backend) = state.lock() { backend.error = Some("后台服务未通过启动检查，请查看诊断日志后重启。".into()); }
                                        continue;
                                    }
                                    if let Ok(mut backend) = state.lock() {
                                        backend.connection = Some(BackendConnection { base_url: format!("http://127.0.0.1:{port}/api/v1"), token: token.clone() });
                                    }
                                    let _ = handle.emit("backend-ready", ());
                                    continue;
                                }
                            }
                            if let Ok(mut backend) = state.lock() { backend.error = Some("后台服务协议不兼容，请重新安装完整软件包。".into()); }
                        }
                    }
                    append_log(&log_path, &line, &token);
                }
                CommandEvent::Stderr(line) => append_log(&log_path, &line, &token),
                CommandEvent::Error(error) => {
                    if let Ok(mut backend) = state.lock() { backend.error = Some(format!("后台进程通信失败: {error}")); backend.connection = None; }
                    let _ = handle.emit("backend-error", "后台服务通信失败");
                }
                CommandEvent::Terminated(payload) => {
                    let error = format!("后台服务已退出（状态 {:?}）。请重启应用；未完成任务将在重启后恢复。", payload.code);
                    if let Ok(mut backend) = state.lock() { backend.error = Some(error.clone()); backend.connection = None; backend.terminated = true; }
                    let _ = handle.emit("backend-error", error);
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

fn wait_for_health(port: u16, token: &str) -> bool {
    let deadline = Instant::now() + Duration::from_secs(30);
    while Instant::now() < deadline {
        let address = std::net::SocketAddr::from(([127, 0, 0, 1], port));
        if let Ok(mut stream) = std::net::TcpStream::connect_timeout(&address, Duration::from_millis(500)) {
            let _ = stream.set_read_timeout(Some(Duration::from_secs(1)));
            let _ = stream.set_write_timeout(Some(Duration::from_secs(1)));
            let request = format!("GET /api/v1/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {token}\r\nConnection: close\r\n\r\n");
            if stream.write_all(request.as_bytes()).is_ok() {
                let mut first_line = String::new();
                if std::io::BufReader::new(stream).read_line(&mut first_line).is_ok() && first_line.starts_with("HTTP/1.1 200 ") { return true; }
            }
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    false
}

fn append_log(path: &std::path::Path, bytes: &[u8], token: &str) {
    // Cap the local diagnostic log and redact the session credential defensively.
    if std::fs::metadata(path).map(|m| m.len() > 5 * 1024 * 1024).unwrap_or(false) {
        let _ = std::fs::rename(path, path.with_extension("previous.log"));
    }
    if let Ok(mut file) = std::fs::OpenOptions::new().create(true).append(true).open(path) {
        let text = String::from_utf8_lossy(bytes).replace(token, "[REDACTED]");
        let _ = writeln!(file, "{text}");
    }
}

pub fn run() {
    let state: SharedBackend = Arc::new(Mutex::new(BackendState::default()));
    let shutdown_state = state.clone();
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_fs::init())
        .manage(state.clone())
        .invoke_handler(tauri::generate_handler![backend_connection])
        .setup(move |app| {
            if let Err(error) = start_backend(app.handle(), state.clone()) {
                if let Ok(mut backend) = state.lock() { backend.error = Some(format!("无法启动后台服务: {error}")); }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("PaperVault desktop initialization failed")
        .run(move |_app, event| {
            if let tauri::RunEvent::Exit = event {
                let child = shutdown_state.lock().ok().and_then(|mut backend| backend.child.take());
                if let Some(mut child) = child {
                    let _ = child.write(b"{\"type\":\"shutdown\"}\n");
                    let deadline = Instant::now() + Duration::from_secs(8);
                    while Instant::now() < deadline {
                        if shutdown_state.lock().map(|state| state.terminated).unwrap_or(true) { break; }
                        std::thread::sleep(Duration::from_millis(100));
                    }
                    let _ = child.kill();
                }
                #[cfg(windows)]
                if let Ok(mut backend) = shutdown_state.lock() { backend.job.take(); }
            }
        });
}
