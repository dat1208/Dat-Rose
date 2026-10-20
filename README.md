# D-Changer

A League of Legends skin changer with a desktop UI. Built on the [Rose](https://github.com/Alban1911/Rose) engine, with party mode and analytics removed and a Tauri interface added.

## Install

1. Download **`D-Changer_x.x.x_x64-setup.exe`** from [Releases](https://github.com/dat1208/Dat-Rose/releases/latest).
2. Run it. Windows may warn about an unknown publisher (the app is not code-signed): choose **More info → Run anyway**.
3. Launch **D-Changer** from the Start menu and accept the UAC prompt. The app needs administrator rights to inject into the game.

The engine fetches the LTK patcher and skin data on first launch; the UI shows the progress.

## Use

1. Open the League client and the D-Changer window.
2. In champion select, pick your champion. The chroma panel appears in the client.
3. Choose a skin. It is applied when the game loads.

The **Profiles** tab keeps one set of skin choices per League account. **Diagnostics** shows upstream versions and any problem the engine hit. **Logs** shows the live engine output.

## Updates

The app checks for a new release on startup and shows a banner when one is available. Click **Update now** to install it and restart. No manual reinstall.

## Requirements

- Windows 10/11 (64-bit)
- League of Legends installed
- Administrator rights (for injection)

## Build from source

Requires Python 3.11+, Node 20+, and Rust.

```powershell
python scripts/build_dchanger.py
```

This builds the Python engine with PyInstaller, the React UI with Vite, and the desktop app with Tauri. The installer lands in `ui/src-tauri/target/release/bundle/nsis/`.

## Disclaimer

This project is for personal, educational use. It modifies local client assets only and provides no competitive advantage. Using it may violate Riot Games' Terms of Service; use at your own risk. Not affiliated with Riot Games.
