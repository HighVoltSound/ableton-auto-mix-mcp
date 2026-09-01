"""MCP server exposing Ableton auto-mixing tools.

Run with:  python -m ableton_auto_mix
Or connect any MCP client (Claude Code, opencode, Cursor, Windsurf...) to the stdio server.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any

import numpy as np
import soundfile as sf
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from pydantic import Field

from . import (
    ab_compare,
    ableton_export,
    ai_recommender,
    analyzer,
    auto_role,
    batch,
    export_formats,
    mixer,
    presets,
    preview,
    profiles,
    qa,
    reference,
)
from .ableton_client import close_client, get_client

logger = logging.getLogger(__name__)

mcp = MCPServer("ableton-auto-mix-mcp")

# "ABLETON_RENDER_DIR" is the canonical env var; the old misspelled name is
# still honored for backwards compatibility.
DEFAULT_RENDER_DIR = os.environ.get("ABLETON_RENDER_DIR", os.environ.get("ABLELON_RENDER_DIR", "renders"))


# ---------------------------------------------------------------------------
# Discovery / info tools
# ---------------------------------------------------------------------------
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def list_styles() -> list[dict[str, Any]]:
    """List all available mixing styles with their targets.

    Read-only. Call this first to discover style names; pass one to get_style,
    auto_mix, recommend_mix or preview_mix.
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
    style: Annotated[
        str,
        Field(description="Style name, e.g. 'techno', 'breaks', 'hip_hop'. See list_styles."),
    ],
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
# Analysis & AI tools
# ---------------------------------------------------------------------------
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def analyze_audio(
    path: Annotated[
        str,
        Field(description="Path to a rendered WAV file (absolute or relative to the working directory)."),
    ],
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
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside directory. Default '*.wav'."),
    ] = "*.wav",
) -> list[dict[str, Any]]:
    """Analyze every WAV in a directory of rendered tracks. Point this at the
    folder where you bounced the Ableton tracks (one WAV per track).

    Read-only, batch variant of analyze_audio. Run this before auto_mix or
    preview_mix so the renders are measured against the style profile.
    """
    results = analyzer.analyze_directory(directory, pattern)
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
            "band_energy_db": {k: round(v, 1) for k, v in r.bandwidth_db.items()},
        }
        for r in results
    ]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def detect_track_roles(
    directory: Annotated[
        str,
        Field(description="Folder containing one WAV per track. Defaults to the renders/ directory."),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside directory. Default '*.wav'."),
    ] = "*.wav",
) -> list[dict[str, Any]]:
    """Automatically detect musical instrument roles for all audio tracks in a directory.

    Classifies tracks into roles like 'kick', 'snare', 'bass', 'lead', 'vocal', 'hats',
    'percussion', 'pad', 'fx' using spectral fingerprinting and crest factor analysis.
    Returns per-track role classifications with confidence scores.
    """
    analyses = analyzer.analyze_directory(directory, pattern)
    if not analyses:
        raise ValueError(f"No {pattern} files found in {directory}")

    roles = []
    for a in analyses:
        audio, sr = sf.read(a.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        res = auto_role.detect_role(np.asarray(audio, dtype=np.float64), sr, a.name)
        roles.append(
            {
                "name": a.name,
                "path": a.path,
                "role": res.role,
                "confidence": round(res.confidence, 2),
            }
        )
    return roles


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def recommend_mix(
    directory: Annotated[
        str,
        Field(description="Folder containing one WAV per track. Defaults to the renders/ directory."),
    ] = DEFAULT_RENDER_DIR,
    style: Annotated[
        str | None,
        Field(description="Optional target musical style (e.g. 'techno', 'house')."),
    ] = None,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files. Default '*.wav'."),
    ] = "*.wav",
) -> dict[str, Any]:
    """AI mixing consultant: analyze multitrack stems and provide actionable mixing recommendations.

    Evaluates gain staging, EQ frequency conflicts, dynamic control, sidechain ducking,
    and stereo placement. Returns prioritized recommendations categorized by level, EQ,
    compression, sidechain and mastering.
    """
    analyses = analyzer.analyze_directory(directory, pattern)
    if not analyses:
        raise ValueError(f"No {pattern} files found in {directory}")

    tracks = []
    for a in analyses:
        t = {
            "name": a.name,
            "file": a.name,
            "path": a.path,
            "lufs": a.lufs,
            "rms_db": a.rms_db,
            "peak_db": a.peak_db,
            "band_energy": a.bandwidth_db,
        }
        audio, sr = sf.read(a.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        role_res = auto_role.detect_role(np.asarray(audio, dtype=np.float64), sr, a.name)
        t["role"] = role_res.role
        t["role_confidence"] = role_res.confidence
        tracks.append(t)

    target_lufs = -14.0
    if style:
        try:
            profile = profiles.get_profile(style)
            target_lufs = profile.target_lufs
        except Exception:
            pass

    recs = ai_recommender.recommend(tracks, target_lufs=target_lufs)
    return {
        "recommendations": [
            {
                "category": r.category,
                "target": r.target,
                "param": r.param,
                "value": r.value,
                "reason": r.reason,
                "confidence": round(r.confidence, 2),
            }
            for r in recs.recommendations
        ],
        "summary": recs.summary,
        "role_map": recs.role_map,
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def match_eq_reference(
    target_path: Annotated[str, Field(description="Path to your mix or preview WAV.")],
    reference_path: Annotated[str, Field(description="Path to the reference WAV track to match.")],
    n_bands: Annotated[int, Field(description="Number of EQ bands to calculate (default 8).")] = 8,
) -> dict[str, Any]:
    """Calculate Match-EQ correction curve by comparing the spectrum of a mix against a reference track.

    Returns the measured spectral difference and recommended EQ biquad filter bands
    (frequency, gain dB, Q) to bring the tonal balance in line with the commercial reference.
    """
    if not os.path.exists(target_path):
        raise ValueError(f"Target file not found: {target_path}")
    if not os.path.exists(reference_path):
        raise ValueError(f"Reference file not found: {reference_path}")

    mix_audio, mix_sr = reference.load_audio_stereo(target_path)
    ref_audio, ref_sr = reference.load_audio_stereo(reference_path)
    curve_bands = reference.compute_match_curve(mix_sr, mix_audio, ref_sr, ref_audio, n_bands=n_bands)
    return {
        "bands": curve_bands,
        "n_bands": len(curve_bands),
    }


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
    """Analyze rendered tracks and report which pairs are fighting for the
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


# ---------------------------------------------------------------------------
# Mixing, Preview & DSP Processing tools
# ---------------------------------------------------------------------------
@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True,
        idempotentHint=False,
        readOnlyHint=False,
    )
)
def auto_mix(
    style: Annotated[
        str,
        Field(description="Style name, e.g. 'techno', 'breaks', 'hip_hop'. See list_styles."),
    ],
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
    """
    profile = profiles.get_profile(style)
    results = analyzer.analyze_directory(render_dir, pattern)
    if not results:
        raise ValueError(f"No {pattern} files found in {render_dir}")

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
        Field(description="Folder containing one WAV per track. Defaults to the renders/ directory."),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[
        str,
        Field(description="Glob pattern matching the WAV files inside render_dir. Default '*.wav'."),
    ] = "*.wav",
    output_path: Annotated[
        str | None,
        Field(description="Where to write the preview WAV. Defaults to <render_dir>/preview_<style>.wav."),
    ] = None,
    max_duration: Annotated[
        float | None,
        Field(description="Cap the preview length in seconds. If None, trimmed to shortest track."),
    ] = None,
    manual_gain: Annotated[
        dict[str, float] | None,
        Field(description="Extra per-file volume in dB, keyed by filename without extension, e.g. {'snt2': -4.0}."),
    ] = None,
    sidechain_db: Annotated[
        float | None,
        Field(description="Duck all non-snare tracks by this many dB when snare hits. None disables."),
    ] = None,
    reference_path: Annotated[
        str | None,
        Field(description="Optional path to reference WAV for Match-EQ during mastering preview."),
    ] = None,
    multiband_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional multiband compressor parameters: {bands: [...], mix: 1.0}."),
    ] = None,
    limiter_ceiling_db: Annotated[
        float | None,
        Field(description="Master limiter ceiling in dBTP (default -0.3)."),
    ] = None,
    dynamic_eq_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional Dynamic EQ parameters: {bands: [...]}."),
    ] = None,
    midside_eq_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional Mid/Side EQ parameters: {mid_bands: [...], side_bands: [...]}."),
    ] = None,
    transient_config: Annotated[
        dict[str, Any] | None,
        Field(description="Optional Transient Shaper parameters: {attack_gain_db: 0, sustain_gain_db: 0}."),
    ] = None,
    sidechain_config: Annotated[
        dict[str, Any] | None,
        Field(description="Advanced sidechain configuration: {trigger_role: 'kick', duck_roles: ['bass'], ...}."),
    ] = None,
    deesser_config: Annotated[
        dict[str, Any] | None,
        Field(
            description="De-Esser config: {frequency_hz: 6500, threshold_db: -20, max_reduction_db: 12, mode: 'split'}."
        ),
    ] = None,
    eq_bands: Annotated[
        list[dict[str, Any]] | None,
        Field(description="Master EQ bands: [{type: 'bell', freq: 1000, gain: 2.0, q: 1.0, enabled: true}]"),
    ] = None,
    spatial_configs: Annotated[
        dict[str, Any] | None,
        Field(description="Per-track 3D Head Spatializer configs: {track_stem: {head_position: 0.3, azimuth_deg: 30}}"),
    ] = None,
) -> dict[str, Any]:
    """Apply style corrections and DSP processing to rendered WAVs and bounce a stereo preview mix.

    Applies per-track volume, pan, EQ, dynamic EQ, mid/side EQ, transient shaping,
    sidechain ducking, de-essing, 3D binaural spatialization, multiband compression, and limiter mastering chain.
    """
    profile = profiles.get_profile(style)
    return preview.render_preview_mix(
        render_dir=render_dir,
        profile=profile,
        pattern=pattern,
        output_path=output_path,
        max_duration=max_duration,
        manual_gain=manual_gain,
        sidechain_db=sidechain_db,
        reference_path=reference_path,
        multiband_config=multiband_config,
        limiter_ceiling_db=limiter_ceiling_db,
        dynamic_eq_config=dynamic_eq_config,
        midside_eq_config=midside_eq_config,
        transient_config=transient_config,
        sidechain_config=sidechain_config,
        deesser_config=deesser_config,
        eq_bands=eq_bands,
        spatial_configs=spatial_configs,
    )


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def compare_styles_ab(
    style_a: Annotated[str, Field(description="First style profile (e.g. 'techno').")],
    style_b: Annotated[str, Field(description="Second style profile (e.g. 'house').")],
    render_dir: Annotated[
        str,
        Field(description="Directory containing track WAVs."),
    ] = DEFAULT_RENDER_DIR,
    pattern: Annotated[str, Field(description="Glob pattern for audio files.")] = "*.wav",
    max_duration: Annotated[float | None, Field(description="Cap duration in seconds.")] = None,
    limiter_ceiling_db: Annotated[float, Field(description="Master limiter ceiling.")] = -0.3,
) -> dict[str, Any]:
    """Render identical track stems against two different style profiles for immediate A/B audio comparison.

    Returns output paths and analysis metrics for both Style A and Style B mixes.
    """
    result = ab_compare.render_ab_compare(
        render_dir=render_dir,
        style_a=style_a,
        style_b=style_b,
        pattern=pattern,
        max_duration=max_duration,
        limiter_ceiling_db=limiter_ceiling_db,
    )
    return {
        "style_a": result.style_a,
        "style_b": result.style_b,
        "output_a": result.output_a,
        "output_b": result.output_b,
        "result_a": result.result_a,
        "result_b": result.result_b,
    }


# ---------------------------------------------------------------------------
# Ableton Live Export & Presets
# ---------------------------------------------------------------------------
@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=False,
    )
)
def export_to_ableton(
    style: Annotated[str, Field(description="Target style profile to calculate corrections from.")],
    render_dir: Annotated[
        str,
        Field(description="Directory containing the WAV stems."),
    ] = DEFAULT_RENDER_DIR,
    mode: Annotated[
        str,
        Field(description="Export mode: 'file' generates an Ableton .als project file, 'live' sends via AbletonOSC."),
    ] = "file",
    session_path: Annotated[
        str | None,
        Field(description="Destination path for .als file or existing session path."),
    ] = None,
    tempo: Annotated[float, Field(description="Project tempo in BPM (default 120.0).")] = 120.0,
    pattern: Annotated[str, Field(description="Glob pattern for WAV files.")] = "*.wav",
) -> dict[str, Any]:
    """Export calculated mix corrections directly into an Ableton Live .als project or via AbletonOSC.

    In file mode, generates a ready-to-open Ableton Live set with audio tracks,
    gain levels, stereo panning, and configured EQ Eight devices.
    """
    profile = profiles.get_profile(style)
    analyses = analyzer.analyze_directory(render_dir, pattern)
    if not analyses:
        raise ValueError(f"No {pattern} files found in {render_dir}")

    mix_result = mixer.compute_mix(analyses, profile)
    res = ableton_export.export_to_ableton(
        corrections=mix_result.track_corrections,
        mode=mode,
        session_path=session_path,
        tempo=tempo,
    )
    return res.to_dict()


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def list_mix_presets() -> list[dict[str, Any]]:
    """List all saved mix processing presets (multiband, EQ, limiter, sidechain configs)."""
    return presets.list_presets()


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def save_mix_preset(
    name: Annotated[str, Field(description="Unique name for the preset.")],
    style: Annotated[str, Field(description="Associated style name (e.g. 'techno').")],
    multiband: Annotated[dict[str, Any] | None, Field(description="Multiband compressor config.")] = None,
    limiter_ceiling_db: Annotated[float, Field(description="Limiter ceiling dB.")] = -0.3,
    dynamic_eq: Annotated[dict[str, Any] | None, Field(description="Dynamic EQ config.")] = None,
    midside_eq: Annotated[dict[str, Any] | None, Field(description="Mid/Side EQ config.")] = None,
    transient: Annotated[dict[str, Any] | None, Field(description="Transient Shaper config.")] = None,
    sidechain: Annotated[dict[str, Any] | None, Field(description="Sidechain config.")] = None,
    notes: Annotated[str, Field(description="User notes / description.")] = "",
) -> dict[str, Any]:
    """Save the current DSP chain and mixing parameters as a reusable preset."""
    preset = presets.MixPreset(
        name=name,
        style=style,
        multiband=multiband,
        limiter_ceiling_db=limiter_ceiling_db,
        dynamic_eq=dynamic_eq,
        midside_eq=midside_eq,
        transient=transient,
        sidechain=sidechain,
        notes=notes,
    )
    path = presets.save_preset(preset)
    return {"saved": True, "name": name, "path": path}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
def load_mix_preset(
    name: Annotated[str, Field(description="Name of the preset to load.")],
) -> dict[str, Any]:
    """Load a previously saved mix preset by name."""
    preset = presets.load_preset(name)
    return {
        "name": preset.name,
        "style": preset.style,
        "multiband": preset.multiband,
        "limiter_ceiling_db": preset.limiter_ceiling_db,
        "dynamic_eq": preset.dynamic_eq,
        "midside_eq": preset.midside_eq,
        "transient": preset.transient,
        "sidechain": preset.sidechain,
        "notes": preset.notes,
        "created_at": preset.created_at,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=True,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def delete_mix_preset(
    name: Annotated[str, Field(description="Name of the preset to delete.")],
) -> dict[str, Any]:
    """Delete a saved mix preset."""
    deleted = presets.delete_preset(name)
    return {"deleted": deleted, "name": name}


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=True,
    )
)
def export_audio_format(
    input_path: Annotated[str, Field(description="Path to source WAV preview file.")],
    format: Annotated[str, Field(description="Target audio format: 'wav', 'flac', or 'mp3'.")] = "flac",
    bit_depth: Annotated[int | None, Field(description="Target bit depth for WAV/FLAC (16, 24, 32).")] = None,
    mp3_bitrate: Annotated[int | None, Field(description="Target MP3 bitrate in kbps (e.g. 320, 256).")] = None,
    flac_compression: Annotated[int, Field(description="FLAC compression level (0-8).")] = 5,
    output_path: Annotated[str | None, Field(description="Optional custom destination path.")] = None,
) -> dict[str, Any]:
    """Convert and export a mix master WAV to standard distribution formats (WAV/FLAC/MP3)."""
    if not os.path.exists(input_path):
        raise ValueError(f"Input file not found: {input_path}")

    if output_path is None:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}.{format}"

    res = export_formats.export_preview(
        input_wav=input_path,
        output_path=output_path,
        format=format,
        bit_depth=bit_depth,
        mp3_bitrate=mp3_bitrate,
        flac_compression=flac_compression,
    )
    return {
        "path": res.path,
        "format": res.format,
        "sample_rate": res.sample_rate,
        "channels": res.channels,
        "duration_s": round(res.duration_s, 2),
        "file_size_bytes": res.file_size_bytes,
        "bit_depth": res.bit_depth,
        "bitrate": res.bitrate,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        destructiveHint=False,
        readOnlyHint=False,
        idempotentHint=False,
    )
)
def batch_process_dirs(
    directories: Annotated[list[str], Field(description="List of folder paths containing stems to mix.")],
    style: Annotated[str, Field(description="Style profile to apply across all directories.")],
    output_dir: Annotated[str | None, Field(description="Optional folder to collect all output previews.")] = None,
    max_duration: Annotated[float | None, Field(description="Optional max preview duration in seconds.")] = None,
    limiter_ceiling_db: Annotated[float, Field(description="Master limiter ceiling.")] = -0.3,
) -> dict[str, Any]:
    """Batch process multiple multi-track session folders under a consistent style profile."""
    res = batch.run_batch(
        directories=directories,
        style=style,
        output_dir=output_dir,
        max_duration=max_duration,
        limiter_ceiling_db=limiter_ceiling_db,
    )
    return {
        "total": res.total,
        "completed": res.completed,
        "failed": res.failed,
        "items": [
            {
                "directory": item.directory,
                "style": item.style,
                "status": item.status,
                "error": item.error,
                "output_path": item.result.get("output_path") if item.result else None,
            }
            for item in res.items
        ],
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
    style and measures it against top-label targets: LUFS, LRA, true peak,
    RMS and spectral tilt. Returns a ready/needs_work verdict with per-metric results.
    """
    if output_path is None:
        if style is None:
            raise ValueError("provide style (to render a preview) or output_path (an existing WAV)")
        profile = profiles.get_profile(style)
        result = preview.render_preview_mix(
            render_dir,
            profile,
            pattern=pattern,
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
    transport = os.environ.get("ABLETON_AUTO_MIX_TRANSPORT", "stdio").strip().lower()
    if transport in ("http", "streamable-http", "streamable_http"):
        _run_http()
    else:
        logger.info("starting ableton-auto-mix-mcp (stdio transport)")
        try:
            mcp.run(transport="stdio")
        finally:
            close_client()


def _run_http() -> None:
    """Run the MCP server over streamable HTTP (for remote/container deploys)."""
    import uvicorn  # noqa: PLC0415

    host = os.environ.get("ABLETON_AUTO_MIX_HOST", "0.0.0.0")
    port = int(os.environ.get("ABLETON_AUTO_MIX_PORT", "8000"))
    app = mcp.streamable_http_app()
    logger.info("starting ableton-auto-mix-mcp (streamable http) on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
