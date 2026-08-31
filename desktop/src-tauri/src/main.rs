#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

use tauri::Manager;

struct BackendPid(Mutex<Option<u32>>);

fn try_port_open() -> bool {
    std::net::TcpStream::connect("127.0.0.1:8787").is_ok()
}

fn spawn_backend(app: tauri::AppHandle) {
    if try_port_open() {
        eprintln!("[musicmixcode] backend already running on :8787");
        return;
    }

    let state = app.state::<BackendPid>();

    // Resolve the resource directory (where Tauri extracts resources)
    let resource_dir = app
        .path()
        .resource_dir()
        .expect("failed to resolve resource dir");

    // Try sidecar with resource dir as working directory
    // In Tauri v2, sidecar runs from a temp dir, but _internal is in resource_dir
    let sidecar_name = if cfg!(target_os = "windows") {
        "musicmixcode-backend-x86_64-pc-windows-msvc.exe"
    } else if cfg!(target_os = "macos") {
        "musicmixcode-backend-x86_64-apple-darwin"
    } else {
        "musicmixcode-backend-x86_64-unknown-linux-gnu"
    };

    let sidecar_path = resource_dir.join("binaries").join(sidecar_name);
    eprintln!("[musicmixcode] looking for sidecar at: {sidecar_path:?}");

    if sidecar_path.exists() {
        eprintln!("[musicmixcode] sidecar found, spawning…");
        match std::process::Command::new(&sidecar_path)
            .current_dir(&resource_dir) // _internal/ is relative to resource_dir
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped())
            .spawn()
        {
            Ok(mut child) => {
                let pid = child.id();
                eprintln!("[musicmixcode] sidecar spawned (pid {pid})");
                *state.0.lock().unwrap() = Some(pid);

                if let Some(stderr) = child.stderr.take() {
                    std::thread::spawn(move || {
                        use std::io::BufRead;
                        for line in std::io::BufReader::new(stderr).lines().flatten() {
                            eprintln!("[backend] {line}");
                        }
                    });
                }
                if let Some(stdout) = child.stdout.take() {
                    std::thread::spawn(move || {
                        use std::io::BufRead;
                        for line in std::io::BufReader::new(stdout).lines().flatten() {
                            eprintln!("[backend] {line}");
                        }
                    });
                }
                return;
            }
            Err(e) => {
                eprintln!("[musicmixcode] sidecar spawn error: {e}");
            }
        }
    } else {
        eprintln!("[musicmixcode] sidecar not found at {sidecar_path:?}");
    }

    // Fallback: system python
    eprintln!("[musicmixcode] trying system python…");
    let python_names: &[&str] = if cfg!(target_os = "windows") {
        &["python", "python3", "py"]
    } else {
        &["python3", "python"]
    };

    for py in python_names {
        if std::process::Command::new(py)
            .arg("--version")
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status()
            .is_ok()
        {
            eprintln!("[musicmixcode] found {py}");

            // Find the src/ directory relative to the exe or resource dir
            // The package is editable-installed, so we just need python to find it
            let project_src = resource_dir
                .parent()
                .and_then(|p| p.parent())
                .map(|p| p.join("src"))
                .filter(|p| p.exists());

            let mut cmd = std::process::Command::new(py);
            cmd.args(["-m", "ableton_auto_mix.api_app", "--port", "8787"]);

            if let Some(ref src) = project_src {
                let cur_dir = src.parent().unwrap_or(&src);
                cmd.current_dir(cur_dir);
                eprintln!("[musicmixcode] working dir: {cur_dir:?}");
            }

            cmd.stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped());

            match cmd.spawn() {
                Ok(mut child) => {
                    let pid = child.id();
                    eprintln!("[musicmixcode] python backend spawned (pid {pid})");
                    *state.0.lock().unwrap() = Some(pid);

                    if let Some(stderr) = child.stderr.take() {
                        std::thread::spawn(move || {
                            use std::io::BufRead;
                            for line in std::io::BufReader::new(stderr).lines().flatten() {
                                eprintln!("[backend] {line}");
                            }
                        });
                    }
                    if let Some(stdout) = child.stdout.take() {
                        std::thread::spawn(move || {
                            use std::io::BufRead;
                            for line in std::io::BufReader::new(stdout).lines().flatten() {
                                eprintln!("[backend] {line}");
                            }
                        });
                    }
                    return;
                }
                Err(e) => {
                    eprintln!("[musicmixcode] python spawn error: {e}");
                }
            }
        }
    }

    eprintln!(
        "[musicmixcode] COULD NOT AUTO-START BACKEND.\n\
         Start manually: python -m ableton_auto_mix.api_app --port 8787"
    );
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(BackendPid(Mutex::new(None)))
        .setup(|app| {
            spawn_backend(app.handle().clone());
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building MusicMixCode Desktop")
        .run(|app_handle, event| {
            if matches!(event, tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit) {
                if let Some(pid) = app_handle
                    .state::<BackendPid>()
                    .0
                    .lock()
                    .unwrap()
                    .take()
                {
                    eprintln!("[musicmixcode] stopping backend (pid {pid})…");
                    #[cfg(target_os = "windows")]
                    {
                        let _ = std::process::Command::new("taskkill")
                            .args(["/PID", &pid.to_string(), "/T", "/F"])
                            .output();
                    }
                    #[cfg(not(target_os = "windows"))]
                    {
                        let _ = std::process::Command::new("kill")
                            .arg("-TERM")
                            .arg(pid.to_string())
                            .output();
                    }
                }
            }
        });
}
