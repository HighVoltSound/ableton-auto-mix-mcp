"""MCP server exposing Ableton auto-mixing tools.

Run with:  python -m ableton_auto_mix
Or connect any MCP client (Claude Code, opencode, ...) to the stdio server.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated, Any

import numpy as np
from pydantic import Field
from mcp_types import ToolAnnotations

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
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def list_styles() -> list[dict[str, Any]]:
    """List all available mixing styles with their targets.

    Read-only. Call this first to discover style names; pass one to get_style,
    auto_mix or preview_mix.
    """
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def get_style(
    style: Annotated[str, Field(description="Style name, e.g. 'techno', 'breaks', 'hip_hop'. See list_styles.")],
) -> dict[str, Any]:
    """Get the full profile for a style, including spectral curve, track
    balance, compression and FX recommendations.

    Read-only. Call list_styles first to see the available names, then pass
    one here to fetch its detailed profile.
    """
    return profiles.get_profile(style).to_dict()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
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
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def analyze_audio(
    path: Annotated[str, Field(description="Path to a rendered WAV file (absolute or relative to the working directory).")],
) -> dict[str, Any]:
    """Analyze a rendered WAV file into mix metrics: loudness (LUFS/LRA),
    RMS, peak, spectral band energy and stereo width.

    Read-only. Use on a single bounced render. For a whole folder of renders,
    use analyze_render_dir instead.
    """
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


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def analyze_render_dir(
    directory: Annotated[
        str,
        Field(
            description="Folder containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
) -> list[dict[str, Any]]:
    """Analyze every WAV in a directory of rendered tracks. Point this at the
    folder where you bounced the Ableton tracks (one WAV per track).

    Read-only, batch variant of analyze_audio. Run this before auto_mix or
    preview_mix so the renders are measured against the style profile.
    """
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
@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True,
        idempotentHint=False,
        readOnlyHint=False,
    )
)
def auto_mix(
    style: Annotated[str, Field(description="Style name, e.g. 'techno', 'breaks', 'hip_hop'. See list_styles.")],
    render_dir: Annotated[
        str,
        Field(
            description="Folder containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
    dry_run: Annotated[
        bool,
        Field(
            description="True = return recommendations without touching Ableton (safe). "
            "False = APPLY the volume/pan corrections to the Live set (mutating!). "
            "Always try True first."
        ),
    ] = True,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
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

    Call with dry_run=True first to review the recommendations; only use
    dry_run=False to apply them to the Live set. Requires Ableton Live +
    AbletonOSC for dry_run=False; the dry run works offline.
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


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def preview_mix(
    style: Annotated[str, Field(description="Style name, e.g. 'techno', 'breaks'. See list_styles.")],
    render_dir: Annotated[
        str,
        Field(
            description="Folder containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
    output_path: Annotated[
        str | None,
        Field(
            description="Where to write the preview WAV. Defaults to <render_dir>/preview_<style>.wav. "
            "Writes a NEW file; the source renders are never modified."
        ),
    ] = None,
    max_duration: Annotated[
        float | None,
        Field(
            description="Cap the preview length in seconds. When renders have mismatched lengths "
            "(loops vs full arrangement), pass the loop length so the preview stays a tight section. "
            "If None, all tracks are trimmed to the shortest render."
        ),
    ] = None,
    manual_gain: Annotated[
        dict[str, float] | None,
        Field(
            description="Extra per-file volume in dB, keyed by the render file name without extension, "
            "e.g. {'snt2': -4.0}."
        ),
    ] = None,
    sidechain_db: Annotated[
        float | None,
        Field(
            description="Duck all non-snare tracks by this many dB when a snare hits, e.g. -4.0 for a "
            "light pump. None disables it."
        ),
    ] = None,
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

    Works fully offline (no Ableton needed) as long as the render WAVs exist.
    Use this to listen to the mix before applying anything in Live; for
    recommendations only, use auto_mix with dry_run=True.
    """
    profile = profiles.get_profile(style)
    return preview.render_preview_mix(
        render_dir, profile, pattern=pattern, output_path=output_path,
        max_duration=max_duration, manual_gain=manual_gain,
        sidechain_db=sidechain_db,
    )


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def suggest_style(
    render_dir: Annotated[
        str,
        Field(
            description="Folder containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
) -> dict[str, Any]:
    """Analyze the rendered tracks and suggest which style profile fits best.

    Read-only. Use this before auto_mix when you are unsure which style to
    pick; the returned profile name can then be passed to auto_mix or
    preview_mix.
    """
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")
    return mixer.suggest_style(results)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def analyze_conflicts(
    render_dir: Annotated[
        str,
        Field(
            description="Folder containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
) -> dict[str, Any]:
    """Analyze the rendered tracks and report which pairs are fighting for the
    same frequency band (e.g. bass vs sub, snare vs bass). Each conflict comes
    with an actionable suggestion (high-pass, EQ cut, ducking).

    Read-only diagnostic. Run before auto_mix to plan EQ/ducking decisions.
    """
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")
    conflicts = qa.analyze_conflicts(results)
    return {
        "tracks_analyzed": [a.name for a in results],
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def release_check(
    render_dir: Annotated[
        str,
        Field(
            description="Directory containing one WAV per track (bounced from Ableton). "
            "Defaults to the renders/ directory."
        ),
    ] = DEFAULT_RENDER_DIR,
    style: Annotated[
        str | None,
        Field(
            description="Style name (see list_styles) whose targets to measure against. "
            "Not needed if output_path points at an existing WAV. See list_styles."
        ),
    ] = None,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
    output_path: Annotated[
        str | None,
        Field(
            description="Existing WAV to check. When given, style is optional and only this file "
            "is measured. When omitted, a preview is rendered for style and then measured."
        ),
    ] = None,
) -> dict[str, Any]:
    """Run the mix through a label-style quality gate.

    If output_path is not given, it re-renders the preview for the requested
    style (or reuses the existing preview file) and measures it against
    top-label targets: LUFS, LRA, true peak, RMS and spectral tilt. Returns a
    ready/needs_work verdict with per-metric results.

    Read-only for your audio files; it may write a preview WAV when
    output_path is omitted. Run this last, after preview_mix, to decide
    whether the mix is release-ready.
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
