"""MCP server exposing Ableton auto-mixing tools.

Run with:  python -m ableton_auto_mix
Or connect any MCP client (Claude Code, opencode, ...) to the stdio server.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from mcp.server.mcpserver import MCPServer

from . import analyzer, mixer, preview, profiles, qa
from .ableton_client import close_client, get_client

logger = logging.getLogger(__name__)

mcp = MCPServer("ableton-auto-mix-mcp")

# "ABLETON_RENDER_DIR" is the canonical env var; the old misspelled name is
# still honored for backwards compatibility.
DEFAULT_RENDER_DIR = os.environ.get(
    "ABLETON_RENDER_DIR", os.environ.get("ABLELON_RENDER_DIR", "renders")
)


# ---------------------------------------------------------------------------
# Discovery / info tools
# ---------------------------------------------------------------------------
@mcp.tool()
def list_styles() -> list[dict[str, Any]]:
    """List all available mixing styles with their targets."""
    return [
        {
            "name": p.name,
            "label": p.label,
            "target_lufs": p.target_lufs,
            "target_lra": p.target_lra,
            "stereo_width": p.stereo_width,
            "description": p.description,
        }
        for p in profiles.list_profiles()
    ]


@mcp.tool()
def get_style(style: str) -> dict[str, Any]:
    """Get the full profile for a style, including spectral curve, track
    balance, compression and FX recommendations."""
    return profiles.get_profile(style).to_dict()


@mcp.tool()
def get_ableton_status() -> dict[str, Any]:
    """Check connection to Ableton Live and return basic project info."""
    try:
        client = get_client()
        tempo = client.get_tempo()
        tracks = client.get_track_names()
        return {"connected": True, "tempo_bpm": tempo, "tracks": tracks}
    except Exception as exc:  # noqa: BLE001
        return {
            "connected": False,
            "error": str(exc),
            "hint": (
                "Start Ableton Live, enable the AbletonOSC control surface "
                "(Preferences -> Link/Tempo/MIDI -> Control Surface -> AbletonOSC), "
                "then retry."
            ),
        }


# ---------------------------------------------------------------------------
# Analysis tools
# ---------------------------------------------------------------------------
@mcp.tool()
def analyze_audio(path: str) -> dict[str, Any]:
    """Analyze a rendered WAV file into mix metrics: loudness (LUFS/LRA),
    RMS, peak, spectral band energy and stereo width."""
    result = analyzer.analyze_track(path)
    return {
        "name": result.name,
        "sample_rate": result.sample_rate,
        "duration_s": round(result.duration_s, 2),
        "rms_db": round(result.rms_db, 1),
        "peak_db": round(result.peak_db, 1),
        "true_peak_dbtp": round(result.true_peak_dbtp, 1),
        "lufs": round(result.lufs, 1),
        "lra": round(result.lra, 1),
        "stereo_width": round(result.stereo_width, 3),
        "band_energy_db": {k: round(v, 1) for k, v in result.bandwidth_db.items()},
    }


@mcp.tool()
def analyze_render_dir(directory: str = DEFAULT_RENDER_DIR) -> list[dict[str, Any]]:
    """Analyze every WAV in a directory of rendered tracks. Point this at the
    folder where you bounced the Ableton tracks (one WAV per track)."""
    results = analyzer.analyze_directory(directory)
    return [
        {
            "name": r.name,
            "path": r.path,
            "rms_db": round(r.rms_db, 1),
            "peak_db": round(r.peak_db, 1),
            "true_peak_dbtp": round(r.true_peak_dbtp, 1),
            "lufs": round(r.lufs, 1),
            "lra": round(r.lra, 1),
            "stereo_width": round(r.stereo_width, 3),
        }
        for r in results
    ]


# ---------------------------------------------------------------------------
# Auto-mix tools
# ---------------------------------------------------------------------------
@mcp.tool()
def auto_mix(
    style: str,
    render_dir: str = DEFAULT_RENDER_DIR,
    dry_run: bool = True,
    pattern: str = "*.wav",
) -> dict[str, Any]:
    """Auto-mix rendered tracks toward a musical style.

    Args:
        style: style name (see list_styles)
        render_dir: folder containing one WAV per track (bounced from Ableton)
        dry_run: True returns recommendations without touching Ableton;
                 False applies the volume/pan corrections to the Live set.
        pattern: glob for audio files inside render_dir

    Returns:
        Per-track corrections (levels, pan, EQ band deltas) and master notes.
    """
    profile = profiles.get_profile(style)
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")

    # Map analysis files back onto Ableton tracks by name when applying.
    track_names: list[str] | None = None
    if not dry_run:
        try:
            track_names = get_client().get_track_names()
        except Exception:
            track_names = [r.name for r in results]

    mix = mixer.compute_mix(results, profile, track_names)

    if not dry_run:
        client = get_client()
        applied = []
        for corr in mix.track_corrections:
            if corr.volume_db is not None:
                client.set_track_volume(corr.index, corr.volume_db)
            if corr.pan is not None:
                client.set_track_pan(corr.index, corr.pan)
            applied.append(corr.index)
        mix.master_notes.insert(0, f"applied level/pan to tracks {applied}")

    return mix.to_dict()


@mcp.tool()
def preview_mix(
    style: str,
    render_dir: str = DEFAULT_RENDER_DIR,
    pattern: str = "*.wav",
    output_path: str | None = None,
    max_duration: float | None = None,
    manual_gain: dict[str, float] | None = None,
    sidechain_db: float | None = None,
) -> dict[str, Any]:
    """Apply the style corrections to the rendered WAVs and bounce a stereo
    preview mix you can listen to WITHOUT Ableton: volumes + pans are applied
    to the audio directly, tracks are summed, and the result is normalized to
    the style's target loudness. Returns the path to the preview WAV.

    Args:
        style: style name (see list_styles)
        render_dir: folder containing one WAV per track
        pattern: glob for audio files inside render_dir
        output_path: where to write the preview (default:
                     <render_dir>/preview_<style>.wav)
        max_duration: cap preview length in seconds. When renders have
                     mismatched lengths (loops vs full arrangement), pass the
                     loop length so the preview stays a tight section. If None,
                     all tracks are trimmed to the shortest render.
        manual_gain: extra per-file volume in dB, keyed by the render file name
                     without extension, e.g. {"snt2": -4.0}.
        sidechain_db: duck all non-snare tracks by this many dB when a snare
                     hits, e.g. -4.0 for a light pump. None disables it.
    """
    profile = profiles.get_profile(style)
    return preview.render_preview_mix(
        render_dir, profile, pattern=pattern, output_path=output_path,
        max_duration=max_duration, manual_gain=manual_gain,
        sidechain_db=sidechain_db,
    )


@mcp.tool()
def suggest_style(render_dir: str = DEFAULT_RENDER_DIR, pattern: str = "*.wav") -> dict[str, Any]:
    """Analyze the rendered tracks and suggest which style profile fits best."""
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")
    return mixer.suggest_style(results)


@mcp.tool()
def analyze_conflicts(render_dir: str = DEFAULT_RENDER_DIR, pattern: str = "*.wav") -> dict[str, Any]:
    """Analyze the rendered tracks and report which pairs are fighting for the
    same frequency band (e.g. bass vs sub, snare vs bass). Each conflict comes
    with an actionable suggestion (high-pass, EQ cut, ducking)."""
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")
    conflicts = qa.analyze_conflicts(results)
    return {
        "tracks_analyzed": [a.name for a in results],
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
    }


@mcp.tool()
def release_check(
    render_dir: str = DEFAULT_RENDER_DIR,
    style: str | None = None,
    pattern: str = "*.wav",
    output_path: str | None = None,
) -> dict[str, Any]:
    """Run the mix through a label-style quality gate.

    If output_path is not given, it re-renders the preview for the requested
    style (or reuses the existing preview file) and measures it against
    top-label targets: LUFS, LRA, true peak, RMS and spectral tilt. Returns a
    ready/needs_work verdict with per-metric results.
    """
    import os

    if output_path is None:
        if style is None:
            raise ValueError("provide style (to render a preview) or output_path (an existing WAV)")
        profile = profiles.get_profile(style)
        result = preview.render_preview_mix(
            render_dir, profile, pattern=pattern,
        )
        output_path = result["output_path"]
        target_lufs = profile.target_lufs
        style_name = profile.name
    else:
        if style is None:
            style_name = os.path.basename(output_path)
            target_lufs = -8.0
        else:
            profile = profiles.get_profile(style)
            style_name = profile.name
            target_lufs = profile.target_lufs

    return qa.release_check(output_path, style_name, target_lufs)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    transport = os.environ.get(
        "ABLETON_AUTO_MIX_TRANSPORT", "stdio"
    ).strip().lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        _run_http()
    else:
        logger.info("starting ableton-auto-mix-mcp (stdio transport)")
        try:
            mcp.run(transport="stdio")
        finally:
            close_client()


def _run_http() -> None:
    """Run the MCP server over streamable HTTP (for remote/container deploys).

    Set ABLETON_AUTO_MIX_TRANSPORT=http to enable. Host/port are read from
    environment (HOST, PORT) with sane defaults. Analysis and preview tools
    work fully; Ableton-specific tools report "not connected".
    """
    import uvicorn  # noqa: PLC0415

    host = os.environ.get("ABLETON_AUTO_MIX_HOST", "0.0.0.0")
    port = int(os.environ.get("ABLETON_AUTO_MIX_PORT", "8000"))
    app = mcp.streamable_http_app()
    logger.info("starting ableton-auto-mix-mcp (streamable http) on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
