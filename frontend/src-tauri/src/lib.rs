pub mod backend_manager;

use backend_manager::{BackendConfig, BackendManager, BackendStatus};
use std::sync::Arc;
use tauri::State;

#[tauri::command]
fn get_backend_config(manager: State<'_, Arc<BackendManager>>) -> Result<BackendConfig, String> {
    manager.spawn_backend()
}

#[tauri::command]
fn get_backend_status(manager: State<'_, Arc<BackendManager>>) -> BackendStatus {
    manager.get_status()
}

#[tauri::command]
fn shutdown_backend(manager: State<'_, Arc<BackendManager>>) -> Result<(), String> {
    manager.shutdown_backend()
}

#[tauri::command]
fn select_evidence_file() -> Result<Option<String>, String> {
    #[cfg(target_os = "linux")]
    {
        // 1. Try zenity (standard on GNOME / Ubuntu / Debian / Fedora)
        if let Ok(output) = std::process::Command::new("zenity")
            .args(["--file-selection", "--title=Select Digital Evidence"])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Ok(Some(path));
                }
            }
        }
        // 2. Try kdialog (KDE Plasma)
        if let Ok(output) = std::process::Command::new("kdialog")
            .args(["--getopenfilename", "."])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Ok(Some(path));
                }
            }
        }
        Ok(None)
    }
    #[cfg(target_os = "windows")]
    {
        let script = r#"
            Add-Type -AssemblyName System.Windows.Forms
            $f = New-Object System.Windows.Forms.OpenFileDialog
            $f.Title = 'Select Digital Evidence'
            if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
                Write-Output $f.FileName
            }
        "#;
        if let Ok(output) = std::process::Command::new("powershell")
            .args(["-NoProfile", "-Command", script])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Ok(Some(path));
                }
            }
        }
        Ok(None)
    }
    #[cfg(target_os = "macos")]
    {
        let script = r#"POSIX path of (choose file with prompt "Select Digital Evidence")"#;
        if let Ok(output) = std::process::Command::new("osascript")
            .args(["-e", script])
            .output()
        {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Ok(Some(path));
                }
            }
        }
        Ok(None)
    }
    #[cfg(not(any(target_os = "linux", target_os = "windows", target_os = "macos")))]
    {
        Ok(None)
    }
}

#[tauri::command]
fn read_evidence_file(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| format!("Failed to read evidence file: {}", e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_manager = Arc::new(BackendManager::new());
    let manager_clone = backend_manager.clone();

    tauri::Builder::default()
        .manage(backend_manager)
        .invoke_handler(tauri::generate_handler![
            get_backend_config,
            get_backend_status,
            shutdown_backend,
            select_evidence_file,
            read_evidence_file
        ])
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .on_window_event(move |_app_handle, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                let _ = manager_clone.shutdown_backend();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
