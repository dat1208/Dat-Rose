// Dat-Rose desktop shell.
//
// Hide the console window in release builds: without this, the windowed app
// still opens a black console behind it.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
// The window is a thin view over the Python engine, which serves a local JSON
// API on 127.0.0.1:56700 (backend/api.py). This shell's only real job is the
// engine's lifecycle: start it when the window opens, stop it when the app
// really exits, so the user never manages two processes.
//
// Closing the window (X) only hides it to the tray: the engine keeps running so
// the user can reopen the UI without a second UAC prompt. A real exit goes
// through the tray menu's "Thoát" item, which stops the engine.
//
// The engine injects into the game and installs the LTK patcher, so it must run
// elevated. The shell itself stays unelevated and launches the engine through
// the UAC "runas" verb (ShellExecuteExW), which is the only way to start an
// elevated process from a non-elevated one. That gives us a process handle with
// SEE_MASK_NOCLOSEPROCESS so we can still kill it on exit.
//
// In development the engine runs as `python main.py --dev` from the backend
// folder (unelevated); in a packaged build it is the `dchanger-backend` sidecar.

use std::path::PathBuf;
use std::sync::Mutex;

use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Manager, RunEvent, WindowEvent};
// Only the elevated (release) path uses these; the dev path spawns python.
#[allow(unused_imports)]
use windows_sys::Win32::Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE};
use windows_sys::Win32::System::Threading::{TerminateProcess, WaitForSingleObject};
#[allow(unused_imports)]
use windows_sys::Win32::UI::Shell::{
    ShellExecuteExW, SEE_MASK_NOCLOSEPROCESS, SHELLEXECUTEINFOW,
};
#[allow(unused_imports)]
use windows_sys::Win32::UI::WindowsAndMessaging::SW_HIDE;

/// A raw Win32 handle kept as an integer so the state is `Send`.
///
/// `HANDLE` is `*mut c_void`, which Rust refuses to move across threads; the
/// handle itself is just a kernel object reference and is safe to pass around.
#[derive(Clone, Copy)]
struct SendHandle(isize);

impl SendHandle {
    fn as_handle(self) -> HANDLE {
        self.0 as HANDLE
    }
}

/// Holds the running engine process so it can be killed on exit.
struct EngineProcess(Mutex<Option<SendHandle>>);

/// Locate the engine executable for a packaged build.
#[cfg(not(debug_assertions))]
fn packaged_engine() -> Option<(PathBuf, PathBuf)> {
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();
    for candidate in [
        exe_dir.join("resources").join("dchanger-backend"),
        exe_dir.join("dchanger-backend"),
    ] {
        let sidecar = candidate.join("dchanger-backend.exe");
        if sidecar.is_file() {
            return Some((sidecar, candidate));
        }
    }
    None
}

/// Start the engine elevated through the UAC prompt; return its process handle.
#[cfg(not(debug_assertions))]
fn spawn_engine_elevated() -> Option<SendHandle> {
    let (sidecar, workdir) = packaged_engine()?;

    let to_wide = |s: &std::ffi::OsStr| -> Vec<u16> {
        use std::os::windows::ffi::OsStrExt;
        s.encode_wide().chain(std::iter::once(0)).collect()
    };
    let file = to_wide(sidecar.as_os_str());
    let directory = to_wide(workdir.as_os_str());
    let verb = to_wide(std::ffi::OsStr::new("runas"));

    let mut info: SHELLEXECUTEINFOW = unsafe { std::mem::zeroed() };
    info.cbSize = std::mem::size_of::<SHELLEXECUTEINFOW>() as u32;
    info.fMask = SEE_MASK_NOCLOSEPROCESS;
    info.lpVerb = verb.as_ptr();
    info.lpFile = file.as_ptr();
    info.lpDirectory = directory.as_ptr();
    info.nShow = SW_HIDE;

    let ok = unsafe { ShellExecuteExW(&mut info) };
    if ok == 0 || info.hProcess == INVALID_HANDLE_VALUE || info.hProcess.is_null() {
        eprintln!("[d-changer] could not start the engine (elevation refused or failed)");
        return None;
    }
    Some(SendHandle(info.hProcess as isize))
}

/// Start the engine unelevated from the backend source folder (development).
#[cfg(debug_assertions)]
fn spawn_engine_dev() -> Option<SendHandle> {
    use std::process::{Command, Stdio};
    use windows_sys::Win32::System::Threading::{OpenProcess, PROCESS_TERMINATE};

    let backend_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .map(|p| p.join("backend"))
        .unwrap_or_default();
    let child = Command::new("python")
        .arg("main.py")
        .arg("--dev")
        .arg("--logs")
        .current_dir(backend_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn();
    match child {
        Ok(child) => {
            let pid = child.id();
            std::mem::forget(child); // we manage the handle ourselves below
            let handle = unsafe { OpenProcess(PROCESS_TERMINATE, 0, pid) };
            if handle.is_null() {
                None
            } else {
                Some(SendHandle(handle as isize))
            }
        }
        Err(e) => {
            eprintln!("[d-changer] could not start the engine: {e}");
            None
        }
    }
}

fn spawn_engine() -> Option<SendHandle> {
    #[cfg(not(debug_assertions))]
    {
        spawn_engine_elevated()
    }
    #[cfg(debug_assertions)]
    {
        spawn_engine_dev()
    }
}

/// Base URL of the engine's local JSON API (backend/api.py).
const API_BASE: &str = "http://127.0.0.1:56700";

/// Proxy a GET to the engine from Rust.
///
/// The webview cannot reach the engine directly: a packaged Tauri window runs
/// on its own origin and the platform webview blocks plain fetches to another
/// host. Doing the request in Rust avoids CORS and CSP entirely, and keeps the
/// engine bound to loopback only.
#[tauri::command]
fn api_get(path: String) -> Result<serde_json::Value, String> {
    let url = format!("{API_BASE}{path}");
    let response = ureq::get(&url)
        .timeout(std::time::Duration::from_secs(10))
        .call()
        .map_err(|e| e.to_string())?;
    response
        .into_json::<serde_json::Value>()
        .map_err(|e| e.to_string())
}

/// Proxy a POST with a JSON body to the engine from Rust (see `api_get`).
#[tauri::command]
fn api_post(path: String, body: serde_json::Value) -> Result<serde_json::Value, String> {
    let url = format!("{API_BASE}{path}");
    let response = ureq::post(&url)
        .timeout(std::time::Duration::from_secs(10))
        .send_json(body)
        .map_err(|e| e.to_string())?;
    response
        .into_json::<serde_json::Value>()
        .map_err(|e| e.to_string())
}

/// Read the tail of the engine's newest log file, for the Logs tab.
#[tauri::command]
fn read_logs(lines: usize) -> Result<String, String> {
    let base = std::env::var("LOCALAPPDATA").map_err(|e| e.to_string())?;
    let log_dir = std::path::Path::new(&base).join("D-Changer").join("logs");
    let mut newest: Option<(std::time::SystemTime, PathBuf)> = None;
    let entries = std::fs::read_dir(&log_dir).map_err(|e| format!("{log_dir:?}: {e}"))?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("log") {
            continue;
        }
        let modified = entry
            .metadata()
            .and_then(|m| m.modified())
            .unwrap_or(std::time::SystemTime::UNIX_EPOCH);
        if newest.as_ref().map(|(t, _)| modified > *t).unwrap_or(true) {
            newest = Some((modified, path));
        }
    }
    let (_, path) = newest.ok_or_else(|| "no log file yet".to_string())?;
    let content = std::fs::read_to_string(&path).map_err(|e| e.to_string())?;
    let tail: Vec<&str> = content.lines().rev().take(lines).collect();
    Ok(tail.into_iter().rev().collect::<Vec<_>>().join("\n"))
}

/// Bring the main window back from the tray.
///
/// The window is hidden with `set_skip_taskbar(true)` so it leaves the taskbar
/// while minimised to tray; both flags must be undone on restore or the window
/// comes back without a taskbar button.
fn restore_main_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_skip_taskbar(false);
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

/// Stop the engine cleanly: ask it to shut down, then force-kill if it hangs.
///
/// Shared by the tray "Quit" item and the `RunEvent::Exit` path so both routes
/// leave the game resumed and no orphaned elevated process behind.
fn shutdown_engine(app: &tauri::AppHandle) {
    let state = app.state::<EngineProcess>();
    let handle = state.0.lock().unwrap().take();
    if let Some(handle) = handle {
        let _ = ureq::post(&format!("{API_BASE}/api/shutdown"))
            .timeout(std::time::Duration::from_secs(3))
            .send_json(serde_json::json!({}));
        let h = handle.as_handle();
        unsafe {
            // Wait for the clean exit, then force it if it hangs.
            if WaitForSingleObject(h, 15000) != 0 {
                TerminateProcess(h, 0);
            }
            CloseHandle(h);
        }
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(EngineProcess(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![api_get, api_post, read_logs])
        .setup(|app| {
            let handle = spawn_engine();
            *app.state::<EngineProcess>().0.lock().unwrap() = handle;

            // Tray icon: left click restores the window, menu offers the same
            // plus a real Quit (the X button only hides).
            let show_item = MenuItem::with_id(app, "show", "Mở Dat-Rose", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Thoát", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let mut tray = TrayIconBuilder::with_id("main-tray")
                .tooltip("Dat-Rose")
                .menu(&menu)
                // Left click restores; the menu stays on right click.
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "show" => restore_main_window(app),
                    "quit" => {
                        // Exit triggers RunEvent::Exit, which stops the engine.
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| match event {
                    TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    }
                    | TrayIconEvent::DoubleClick {
                        button: MouseButton::Left,
                        ..
                    } => {
                        restore_main_window(tray.app_handle());
                    }
                    _ => {}
                });

            // Use the bundled window icon or fallback to the embedded asset.
            let icon = app
                .default_window_icon()
                .cloned()
                .or_else(|| tauri::image::Image::from_bytes(include_bytes!("../icons/icon.png")).ok());
            if let Some(icon) = icon {
                tray = tray.icon(icon);
            }
            tray.build(app)?;
            Ok(())
        })
        // The X button hides to the tray instead of closing: the engine keeps
        // running (it owns the injection and the game session), so the user can
        // reopen the window without a second UAC prompt.
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.set_skip_taskbar(true);
                let _ = window.hide();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while building the Dat-Rose window")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                shutdown_engine(app_handle);
            }
        });
}
