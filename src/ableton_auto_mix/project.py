"""Project state serializer/deserializer for MusicMixCode Desktop.

Saves analysis results, mix state, and history to disk as JSON.
Auto-saves to <directory>/.musicmixcode.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUTO_SAVE_NAME = ".musicmixcode.json"
PROJECT_EXTENSION = ".mmc.json"
_SEARCH_PATTERNS = [AUTO_SAVE_NAME, "*.mmc.json"]


@dataclass
class ProjectState:
    version: str = "0.3"
    directory: str = ""
    style: str = ""
    analyses: list[dict[str, Any]] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] | None = None
    preview_path: str | None = None
    before_path: str | None = None
    match_eq_curve: list[dict[str, Any]] | None = None
    conflicts: list[dict[str, Any]] | None = None
    selected_style_id: str | None = None
    manual_gain: dict[str, float] | None = None
    sidechain_db: float | None = None
    name: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migrate_v02(state: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a v0.2 project file to v0.3 format (fill missing fields)."""
    state.setdefault("version", "0.3")
    state.setdefault("analyses", [])
    state.setdefault("corrections", [])
    state.setdefault("plan", None)
    state.setdefault("preview_path", None)
    state.setdefault("before_path", None)
    state.setdefault("match_eq_curve", None)
    state.setdefault("conflicts", None)
    state.setdefault("selected_style_id", None)
    state.setdefault("manual_gain", None)
    state.setdefault("sidechain_db", None)
    state.setdefault("name", "")
    state.setdefault("created_at", "")
    state.setdefault("updated_at", "")
    state["version"] = "0.3"
    return state


def save_project(state: ProjectState, path: str) -> str:
    """Write a ProjectState to disk as JSON. Returns the absolute path."""
    state.updated_at = _now_iso()
    if not state.created_at:
        state.created_at = state.updated_at
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
    return abs_path


def load_project(path: str) -> ProjectState:
    """Read a ProjectState from disk. Migrates older versions gracefully."""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Project file not found: {abs_path}")
    with open(abs_path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid project file format: {abs_path}")
    raw = _migrate_v02(raw)
    return ProjectState(
        **{k: v for k, v in raw.items() if k in ProjectState.__dataclass_fields__}
    )


def auto_save(state: ProjectState, directory: str) -> str:
    """Save the project into the directory as .musicmixcode.json."""
    path = os.path.join(directory, AUTO_SAVE_NAME)
    return save_project(state, path)


def list_recent_projects(
    max_count: int = 10, extra_dirs: list[str] | None = None
) -> list[dict[str, Any]]:
    """Scan common locations for .musicmixcode.json files, return recent first."""
    candidates: list[Path] = []

    # Scan extra directories first (used by tests and explicit searches)
    for d in extra_dirs or []:
        base = Path(d)
        if base.is_dir():
            try:
                for pattern in _SEARCH_PATTERNS:
                    for p in base.rglob(pattern):
                        if p.is_file():
                            candidates.append(p)
            except (FileNotFoundError, PermissionError, OSError):
                pass

    # Scan user home Desktop, Documents, Music, Downloads
    home = Path.home()
    for subdir in ["Desktop", "Documents", "Music", "Downloads"]:
        base = home / subdir
        if base.is_dir():
            try:
                for pattern in _SEARCH_PATTERNS:
                    for p in base.rglob(pattern):
                        if p.is_file():
                            candidates.append(p)
            except (FileNotFoundError, PermissionError, OSError):
                pass

    # Scan project renders directory (if it exists)
    project_root = Path(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    renders = project_root / "renders"
    if renders.is_dir():
        try:
            for pattern in _SEARCH_PATTERNS:
                for p in renders.rglob(pattern):
                    if p.is_file():
                        candidates.append(p)
        except (FileNotFoundError, PermissionError, OSError):
            pass

    results: list[dict[str, Any]] = []
    seen: set = set()
    for p in candidates:
        resolved = str(p.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            stat = p.stat()
            state = load_project(str(p))
            results.append(
                {
                    "path": str(p),
                    "directory": state.directory,
                    "name": state.name or os.path.basename(os.path.dirname(str(p))),
                    "style": state.style,
                    "updated_at": state.updated_at or "",
                    "modified_ts": stat.st_mtime,
                }
            )
        except (FileNotFoundError, ValueError, json.JSONDecodeError, TypeError):
            continue

    results.sort(key=lambda r: r["modified_ts"], reverse=True)
    for r in results[:max_count]:
        r.pop("modified_ts", None)
    return results[:max_count]
