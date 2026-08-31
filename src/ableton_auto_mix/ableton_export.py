"""Export engine: translate mix corrections into Ableton Live actions.

Two modes:
  - "live": push corrections to Ableton via AbletonOSC (real-time)
  - "file": generate a .als XML file for import into Ableton (offline)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from . import als_xml
from .mixer import TrackCorrection

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    applied: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    session_path: str | None = None
    mode: str = "file"

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied": self.applied,
            "skipped": self.skipped,
            "errors": self.errors,
            "session_path": self.session_path,
            "mode": self.mode,
        }


def _correction_to_dict(corr: TrackCorrection) -> dict:
    """Convert a TrackCorrection dataclass to the dict expected by als_xml."""
    return {
        "name": corr.name,
        "volume_db": corr.volume_db or 0.0,
        "pan": corr.pan or 0.0,
        "band_corrections": [
            {
                "band": bc.band,
                "freq_range": bc.freq_range,
                "measured_db": bc.measured_db,
                "target_db": bc.target_db,
                "delta_db": bc.delta_db,
            }
            for bc in corr.band_corrections
        ],
    }


def _apply_live(
    corrections: list[TrackCorrection],
    session_path: str | None = None,
) -> ExportResult:
    """Push corrections to a running Ableton Live instance via AbletonOSC."""
    result = ExportResult(mode="live")

    try:
        from .ableton_client import get_client

        client = get_client()
    except Exception as exc:
        result.errors.append(f"Cannot connect to Ableton Live: {exc}")
        return result

    # Get existing track names to map corrections by index/name
    try:
        live_names = client.get_track_names()
    except Exception as exc:
        result.errors.append(f"Cannot read track list from Ableton: {exc}")
        return result

    for corr in corrections:
        idx = corr.index
        if idx >= len(live_names):
            result.skipped += 1
            result.errors.append(
                f"Track index {idx} ({corr.name}) out of range "
                f"(Ableton has {len(live_names)} tracks)"
            )
            continue

        try:
            if corr.volume_db is not None and abs(corr.volume_db) > 0.05:
                client.set_track_volume(idx, corr.volume_db)
                result.applied += 1

            if corr.pan is not None and abs(corr.pan) > 0.01:
                client.set_track_pan(idx, corr.pan)
                result.applied += 1

            # Note: EQ Eight via AbletonOSC requires device-level API
            # which is more complex. For now, volume + pan are the primary
            # live export targets. EQ is handled via .als file export.
            if corr.band_corrections:
                result.errors.append(
                    f"EQ corrections for '{corr.name}' cannot be applied "
                    f"live (use file export for EQ)"
                )
                result.skipped += len(corr.band_corrections)

        except Exception as exc:
            result.errors.append(f"Error applying to '{corr.name}': {exc}")

    return result


def _apply_file(
    corrections: list[TrackCorrection],
    session_path: str | None = None,
    tempo: float = 120.0,
) -> ExportResult:
    """Generate a .als XML file from the corrections."""
    result = ExportResult(mode="file")

    corr_dicts = [_correction_to_dict(c) for c in corrections]
    applied = 0
    for cd in corr_dicts:
        has_vol = abs(cd.get("volume_db", 0)) > 0.05
        has_pan = abs(cd.get("pan", 0)) > 0.01
        has_eq = len(cd.get("band_corrections", [])) > 0
        if has_vol or has_pan or has_eq:
            applied += 1

    if applied == 0:
        result.errors.append("No corrections to export (all values are zero)")
        return result

    # Determine output path
    if not session_path:
        session_path = os.path.join(os.getcwd(), "export_session.als")

    # Ensure .als extension
    if not session_path.lower().endswith(".als"):
        session_path += ".als"

    try:
        written = als_xml.write_als(corr_dicts, session_path, tempo=tempo)
        result.session_path = written
        result.applied = applied
    except Exception as exc:
        result.errors.append(f"Failed to write .als file: {exc}")

    return result


def _apply_json(
    corrections: list[TrackCorrection],
    session_path: str | None = None,
) -> ExportResult:
    """Export corrections as a universal JSON settings file.

    This format can be imported into any DAW via scripting:
    - Logic Pro: AppleScript
    - FL Studio: Python API
    - Cubase: Lua scripting
    - Reaper: ReaScript
    """
    import json

    result = ExportResult(mode="json")

    if session_path is None:
        session_path = "mix_corrections.json"

    if not session_path.lower().endswith(".json"):
        session_path += ".json"

    data = {
        "format": "musicmixcode_corrections",
        "version": "1.0",
        "tracks": [],
    }

    for corr in corrections:
        track_data = {
            "name": corr.name,
            "index": corr.index,
            "role": corr.role or "unknown",
            "volume_db": corr.volume_db or 0.0,
            "pan": corr.pan or 0.0,
            "width": corr.width or "moderate",
            "eq": [
                {
                    "type": bc.band if hasattr(bc, "band") else "peaking",
                    "freq": bc.center_hz
                    if hasattr(bc, "center_hz")
                    else bc.freq_range[0]
                    if hasattr(bc, "freq_range") and bc.freq_range
                    else 1000,
                    "gain_db": bc.gain_db,
                    "q": bc.q if hasattr(bc, "q") else 1.0,
                }
                for bc in (corr.band_corrections or [])
            ],
        }
        data["tracks"].append(track_data)
        result.applied += 1

    try:
        os.makedirs(os.path.dirname(session_path) or ".", exist_ok=True)
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        result.session_path = session_path
    except Exception as exc:
        result.errors.append(f"Failed to write JSON: {exc}")

    return result


def export_to_ableton(
    corrections: list[TrackCorrection],
    mode: str = "file",
    session_path: str | None = None,
    tempo: float = 120.0,
) -> ExportResult:
    """Export corrections to Ableton Live or universal JSON format.

    Parameters
    ----------
    corrections : list[TrackCorrection]
        Per-track corrections from the mixer engine.
    mode : str
        "live" to push via AbletonOSC, "file" to generate .als XML,
        "json" to generate universal JSON settings.
    session_path : str, optional
        Path for the output file (file/json mode) or existing session (live mode).
    tempo : float
        Session BPM for the .als file (default 120).

    Returns
    -------
    ExportResult
        Summary of what was applied/skipped/errors.
    """
    if mode == "live":
        return _apply_live(corrections, session_path)
    elif mode == "file":
        return _apply_file(corrections, session_path, tempo)
    elif mode == "json":
        return _apply_json(corrections, session_path)
    else:
        result = ExportResult(mode=mode)
        result.errors.append(
            f"Unknown export mode: '{mode}' (expected 'live', 'file', or 'json')"
        )
        return result
