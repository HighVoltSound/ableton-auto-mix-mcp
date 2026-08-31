"""Standalone entry point for the packaged backend sidecar (PyInstaller).

This module deliberately contains no argparse and no business logic:
it imports the FastAPI app from ableton_auto_mix.api_app and serves it
with uvicorn on 127.0.0.1:<port>.

Port selection:
    MUSICMIXCODE_PORT env var (default 8787).

Run directly (dev):
    python scripts/backend_entry.py

Frozen (Tauri sidecar):
    musicmixcode-backend-x86_64-pc-windows-msvc.exe
"""

from __future__ import annotations

import os

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def _port() -> int:
    raw = os.environ.get("MUSICMIXCODE_PORT", str(DEFAULT_PORT))
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def main() -> None:
    # Imports are deferred so that import errors produce a readable traceback
    # on stderr instead of dying before Python is fully bootstrapped.
    try:
        import uvicorn

        from ableton_auto_mix.api_app import app
    except Exception:  # pragma: no cover - diagnostics only
        import traceback

        traceback.print_exc()
        raise SystemExit(1)

    uvicorn.run(
        app,
        host=DEFAULT_HOST,
        port=_port(),
        log_level="info",
        # Sidecar lifecycle is owned by the desktop app; disable reload/multi-worker.
        workers=1,
        reload=False,
    )


if __name__ == "__main__":
    main()
