"""Mix presets: save and load mix settings (not full projects).

A preset captures all the knobs from the mixing UI: multiband compressor,
limiter ceiling, dynamic EQ, mid/side EQ, transient shaper, sidechain config,
and the selected style. Users can build a library of go-to settings.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

PRESETS_DIR_NAME = "mix_presets"


@dataclass
class MixPreset:
    name: str
    style: str = ""
    multiband: dict | None = None
    limiter_ceiling_db: float | None = None
    dynamic_eq: dict | None = None
    midside_eq: dict | None = None
    transient: dict | None = None
    sidechain: dict | None = None
    version: str = "1.0"
    created_at: str = ""
    notes: str = ""


def _presets_dir() -> str:
    """Return the user-level presets directory."""
    home = os.path.expanduser("~")
    d = os.path.join(home, "MusicMixCode", PRESETS_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def list_presets() -> list[dict[str, str]]:
    """List all saved presets (name + path)."""
    d = _presets_dir()
    results = []
    for fname in sorted(os.listdir(d)):
        if fname.endswith(".json"):
            name = fname[:-5]
            results.append({"name": name, "path": os.path.join(d, fname)})
    return results


def save_preset(preset: MixPreset) -> str:
    """Save a preset to disk. Returns the file path."""
    import datetime

    if not preset.created_at:
        preset.created_at = datetime.datetime.now().isoformat()

    d = _presets_dir()
    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in preset.name)
    path = os.path.join(d, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(preset), f, indent=2, ensure_ascii=False)
    return path


def load_preset(name_or_path: str) -> MixPreset:
    """Load a preset by name or full path."""
    if os.path.isfile(name_or_path):
        path = name_or_path
    else:
        d = _presets_dir()
        path = os.path.join(d, f"{name_or_path}.json")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return MixPreset(
        name=data.get("name", os.path.splitext(os.path.basename(path))[0]),
        style=data.get("style", ""),
        multiband=data.get("multiband"),
        limiter_ceiling_db=data.get("limiter_ceiling_db"),
        dynamic_eq=data.get("dynamic_eq"),
        midside_eq=data.get("midside_eq"),
        transient=data.get("transient"),
        sidechain=data.get("sidechain"),
        version=data.get("version", "1.0"),
        created_at=data.get("created_at", ""),
        notes=data.get("notes", ""),
    )


def delete_preset(name_or_path: str) -> bool:
    """Delete a preset by name or full path. Returns True if deleted."""
    if os.path.isfile(name_or_path):
        path = name_or_path
    else:
        d = _presets_dir()
        path = os.path.join(d, f"{name_or_path}.json")

    if os.path.exists(path):
        os.remove(path)
        return True
    return False
