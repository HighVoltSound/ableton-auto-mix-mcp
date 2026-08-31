# Handoff: Task 6 — Auto-Update

> Status: PLANNED | Priority: LOW | Complexity: MEDIUM
> Depends on: None | Blocks: None

## Goal
Tauri app checks for updates on startup, downloads and installs silently.

## Files to Create/Modify

### 1. `desktop/src-tauri/Cargo.toml` (MODIFY)
- Add dependency: `tauri-plugin-updater = "2"`

### 2. `desktop/src-tauri/tauri.conf.json` (MODIFY)
```json
{
  "plugins": {
    "updater": {
      "endpoints": ["https://releases.highvoltsound.com/musicmixcode/{{target}}/{{arch}}/{{current_version}}.json"],
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQgc2lnbmF0dXJlIGhlcmU=",
      "windows": { "installMode": "quiet" }
    }
  }
}
```

### 3. `desktop/src-tauri/src/main.rs` (MODIFY)
- Add `.plugin(tauri_plugin_updater::Builder::new().build())` in builder
- Register updater event handler

### 4. `desktop/src/lib/updater.ts` (NEW)
- Check for updates on app start (after 5s delay)
- Show update available notification
- Download + install progress
- Restart app after install

### 5. `desktop/src/components/UpdateBanner.tsx` (NEW)
- Non-intrusive banner at top: "Update available: v0.4.0"
- "Update" button + "Skip" button
- Progress during download

### 6. `desktop/src/App.tsx` (MODIFY)
- Mount UpdateBanner
- Call updater check on mount

## Release Flow
1. Build new version: `npm.cmd run tauri build`
2. Sign the installer
3. Upload to release server
4. Create version JSON:
```json
{
  "version": "0.4.0",
  "notes": "Waveform visualization, export to Ableton",
  "pubkey": "...",
  "platforms": {
    "windows-x86_64": {
      "url": "https://releases.highvoltsound.com/musicmixcode/v0.4.0/MusicMixCode-0.4.0-x64-setup.exe",
      "signature": "..."
    }
  }
}
```

## Test Strategy
- Mock updater endpoint → verify check detects new version
- Mock download → verify progress bar works
- Verify no update needed → silent pass

## Acceptance Criteria
1. App checks for updates on startup
2. Update banner appears when new version available
3. Download + install works silently
4. App restarts after update
5. User can skip version
