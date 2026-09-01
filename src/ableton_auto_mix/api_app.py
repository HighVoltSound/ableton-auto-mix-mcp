"""HTTP API wrapper around the auto-mix engine for the desktop app (Tauri + React).

Run with:
    python -m ableton_auto_mix.api_app --port 8787

This module reuses the existing engine functions directly
(profiles / analyzer / mixer / preview / qa) and adds no mixing logic of its own.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Literal

import numpy as np
import soundfile as sf
from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import (
    ableton_export,
    analyzer,
    mixer,
    planner,
    preview,
    profiles,
    project,
    qa,
    reference,
)
from .logging_utils import get_logger, setup_logging
from .ws_manager import ProgressReporter, new_room_id
from .ws_manager import manager as ws_manager

_log = get_logger("api")

setup_logging()

app = FastAPI(
    title="ableton-auto-mix API",
    description="HTTP wrapper for the style-based auto-mixing engine.",
    version="0.1.0",
)

# CORS: allow everything from localhost (desktop app dev + prod ports).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

# ---------------------------------------------------------------------------
# Path security: audio files may only be served from "known" render folders —
# either the project's renders/ folder or directories the client itself has
# used in analyze/mix/preview calls. Everything else is rejected.
# ---------------------------------------------------------------------------

# src/ableton_auto_mix/api_app.py -> project root is two levels up from this file's package dir
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_RENDER_DIR = os.environ.get("ABLETON_RENDER_DIR", os.path.join(_PROJECT_ROOT, "renders"))

_allowed_roots: set[str] = set()


def _register_dir(directory: str) -> str:
    """Whitelist a render directory so its WAVs can be served back."""
    abs_dir = os.path.abspath(directory)
    _allowed_roots.add(os.path.normcase(abs_dir))
    try:
        _allowed_roots.add(os.path.normcase(os.path.realpath(abs_dir)))
    except OSError:
        pass
    return abs_dir


_register_dir(DEFAULT_RENDER_DIR)


def _is_under(path_normcase: str, root_normcase: str) -> bool:
    return path_normcase == root_normcase or path_normcase.startswith(root_normcase.rstrip("\\/") + os.sep)


def _resolve_audio_path(path: str, *, must_exist: bool = True) -> str:
    """Validate a user-supplied WAV path against the whitelist."""
    if not path.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="only .wav files are allowed")
    abs_path = os.path.abspath(path)
    norm = os.path.normcase(abs_path)
    if not any(_is_under(norm, root) for root in _allowed_roots):
        raise HTTPException(
            status_code=400,
            detail=(
                "path is outside the allowed render directories "
                "(analyze/suggest/mix/preview register their directories automatically)"
            ),
        )
    if must_exist and not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail=f"file not found: {abs_path}")
    return abs_path


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class DirectoryRequest(BaseModel):
    directory: str = Field(description="Folder containing one WAV per track.")
    pattern: str = Field(default="*.wav", description="Glob for the WAV files.")
    async_mode: bool = Field(
        default=False,
        description="When true, returns a room_id immediately and streams progress via WS /ws/progress/{room_id}.",
    )


class MixRequest(BaseModel):
    style: str
    directory: str
    dry_run: bool = True
    pattern: str = "*.wav"
    manual_gain: dict[str, float] | None = None
    sidechain_db: float | None = None
    use_planner: bool = Field(
        default=False,
        description="Split corrections into mixing (per-track) vs mastering "
        "(bus) via the decision planner; response gains 'plan'.",
    )


class PreviewRequest(BaseModel):
    style: str
    directory: str
    output_path: str | None = None
    max_duration: float | None = None
    pattern: str = "*.wav"
    manual_gain: dict[str, float] | None = None
    sidechain_db: float | None = None
    reference_path: str | None = Field(
        default=None,
        description="Optional reference WAV for the match EQ (shape-only correction).",
    )
    render_before: bool = Field(
        default=False,
        description="Also bounce a 'before' version (unity-gain sum, -1 dBTP) next to the output.",
    )
    use_planner: bool = Field(
        default=False,
        description="Render from a planner plan (mixing/mastering split); response always includes 'plan'.",
    )
    multiband: dict | None = Field(
        default=None,
        description="Multiband compressor config: {enabled, mix, bands: [{freq_lo, freq_hi, threshold_db, ratio, attack_ms, release_ms, makeup_db, enabled}]}",
    )
    limiter_ceiling_db: float | None = Field(
        default=None,
        description="True-peak limiter ceiling in dBTP (default -1.0).",
    )
    dynamic_eq: dict | None = Field(
        default=None,
        description="Dynamic EQ config: {enabled, mix, bands: [{freq_lo, freq_hi, threshold_db, ratio, attack_ms, release_ms, gain_db, mode, enabled}]}",
    )
    midside_eq: dict | None = Field(
        default=None,
        description="Mid/Side EQ config: {enabled, mix, mid_nodes: [{hz, gain_db, q, type}], side_nodes: [...]}",
    )
    transient: dict | None = Field(
        default=None,
        description="Transient shaper config: {enabled, attack_db, sustain_db, sensitivity, frequency_hz, mix}",
    )
    sidechain: dict | None = Field(
        default=None,
        description="Sidechain config: {enabled, trigger, targets, amount_db, attack_ms, release_ms, band_filter, mix}",
    )
    deesser: dict | None = Field(
        default=None,
        description="De-Esser config: {enabled, frequency_hz, threshold_db, ratio, max_reduction_db, mode, mix}",
    )
    eq_bands: list[dict] | None = Field(
        default=None,
        description="User EQ bands: [{id, type, freq, gain, q, enabled}]",
    )
    spatial_configs: dict[str, dict] | None = Field(
        default=None,
        description="Per-track Binaural 3D Head Spatializer configs: {track_stem: {head_position, azimuth_deg, elevation_deg, distance_m, mix, bass_mono, room_model, room_amount}}",
    )
    transient_configs: dict[str, dict] | None = Field(
        default=None,
        description="Per-track Transient Shaper configs: {track_stem: {attack_db, sustain_db, mix}}",
    )
    reference_match_bands: list[dict] | None = Field(
        default=None,
        description="AI Reference match EQ bands to apply to master bus",
    )
    async_mode: bool = Field(
        default=False,
        description="When true, returns a room_id immediately and streams progress via WS /ws/progress/{room_id}.",
    )


class MatchEqRequest(BaseModel):
    mix_wav_path: str = Field(description="Path to the mix WAV.")
    reference_path: str = Field(description="Path to the reference WAV.")


class ReleaseRequest(BaseModel):
    style: str | None = None
    directory: str | None = None
    output_path: str | None = None
    pattern: str = "*.wav"


class AnalyzeTrackOut(BaseModel):
    name: str
    path: str
    sample_rate: int
    duration_s: float
    rms_db: float
    peak_db: float
    lufs: float
    lra: float
    bandwidth_db: dict[str, float]
    stereo_width: float
    true_peak_dbtp: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_profile(style: str) -> profiles.StyleProfile:
    try:
        return profiles.get_profile(style)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _load_analyses(directory: str, pattern: str) -> list[analyzer.TrackAnalysis]:
    if not os.path.isdir(directory):
        raise HTTPException(status_code=400, detail=f"directory not found: {directory}")
    results = analyzer.analyze_directory(directory, pattern)
    if not results:
        raise HTTPException(
            status_code=400,
            detail=f"no {pattern} files found in {directory}",
        )
    return results


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------


@app.get("/api/styles")
def api_styles() -> list[dict[str, Any]]:
    """List all styles with their loudness targets."""
    return [
        {
            "id": p.name,
            "name": p.label,
            "targets": {
                "lufs": p.target_lufs,
                "lra": p.target_lra,
                "tempo_range": p.tempo_range,
                "stereo_width": p.stereo_width,
            },
        }
        for p in profiles.list_profiles()
    ]


@app.get("/api/style/{style_id}")
def api_style(style_id: str) -> dict[str, Any]:
    """Full profile for one style."""
    return _get_profile(style_id).to_dict()


# ---------------------------------------------------------------------------
# Analysis / suggestions / conflicts
# ---------------------------------------------------------------------------


@app.post("/api/analyze")
def api_analyze(req: DirectoryRequest) -> dict[str, Any]:
    """Metrics for every WAV in a folder (like analyze_render_dir).

    With async_mode=true, returns a room_id immediately and streams progress via WS.
    """
    t0 = time.perf_counter()
    _register_dir(req.directory)

    if req.async_mode:
        room_id = new_room_id()
        reporter = ProgressReporter(room_id)

        def _run() -> None:
            try:
                analyses = _load_analyses(req.directory, req.pattern)
                payload = {
                    "directory": os.path.abspath(req.directory),
                    "tracks": [a.__dict__ for a in analyses],
                    "elapsed_s": round(time.perf_counter() - t0, 3),
                }
                reporter.done(payload)
            except Exception as exc:  # noqa: BLE001
                reporter.error(str(exc))
            finally:
                ws_manager.cleanup_room(room_id)

        import threading

        threading.Thread(target=_run, daemon=True).start()
        return {"room_id": room_id, "estimated_duration_s": 5}

    analyses = _load_analyses(req.directory, req.pattern)
    return {
        "directory": os.path.abspath(req.directory),
        "tracks": [a.__dict__ for a in analyses],
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


@app.post("/api/suggest")
def api_suggest(req: DirectoryRequest) -> dict[str, Any]:
    """Suggest the best-fitting style plus reasoning (ranked scores)."""
    t0 = time.perf_counter()
    _register_dir(req.directory)
    analyses = _load_analyses(req.directory, req.pattern)
    result = mixer.suggest_style(analyses)
    result["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return result


@app.post("/api/conflicts")
def api_conflicts(req: DirectoryRequest) -> dict[str, Any]:
    """Frequency-band conflicts between track pairs, with fix suggestions."""
    t0 = time.perf_counter()
    _register_dir(req.directory)
    analyses = _load_analyses(req.directory, req.pattern)
    conflicts = qa.analyze_conflicts(analyses)
    return {
        "tracks_analyzed": [a.name for a in analyses],
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
        "elapsed_s": round(time.perf_counter() - t0, 3),
    }


# ---------------------------------------------------------------------------
# Mix / preview / release
# ---------------------------------------------------------------------------


@app.post("/api/mix")
def api_mix(req: MixRequest) -> dict[str, Any]:
    """Per-track corrections (levels, pan, EQ deltas) + master notes.

    With dry_run=true nothing is written; corrections are computed only.
    """
    t0 = time.perf_counter()
    profile = _get_profile(req.style)
    _register_dir(req.directory)
    analyses = _load_analyses(req.directory, req.pattern)
    mix_result = mixer.compute_mix(
        analyses,
        profile,
        [a.name for a in analyses],
        use_planner=req.use_planner,
    )
    payload = mix_result.to_dict()
    payload["dry_run"] = req.dry_run
    payload["manual_gain_applied"] = req.manual_gain or {}
    payload["sidechain_db"] = req.sidechain_db
    if req.use_planner:
        payload["plan"] = planner.build_plan(analyses, profile, mix_result).to_dict()
    payload["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return payload


@app.post("/api/preview")
def api_preview(req: PreviewRequest) -> dict[str, Any]:
    """Render a stereo preview mix (WAV) without Ableton.

    Optional extras:
      - reference_path: apply a match EQ computed against the reference WAV
        (response gains "match_eq": {"reference_path", "curve"}).
      - render_before: also bounce a "before" WAV (unity-gain sum, no
        processing, -1 dBTP); response includes "before_path".
      - async_mode: return room_id immediately, stream progress via WS.
    """
    t0 = time.perf_counter()
    profile = _get_profile(req.style)
    _register_dir(req.directory)
    _load_analyses(req.directory, req.pattern)  # fail fast on empty dirs
    if req.output_path is not None:
        if not req.output_path.lower().endswith(".wav"):
            raise HTTPException(status_code=400, detail="output_path must be a .wav file")
        _register_dir(os.path.dirname(req.output_path))
    reference_abs: str | None = None
    if req.reference_path:
        reference_abs = _resolve_audio_path(req.reference_path)
        _register_dir(os.path.dirname(reference_abs))

    if req.async_mode:
        room_id = new_room_id()
        reporter = ProgressReporter(room_id)

        def _run() -> None:
            try:
                result = preview.render_preview_mix(
                    req.directory,
                    profile,
                    pattern=req.pattern,
                    output_path=req.output_path,
                    max_duration=req.max_duration,
                    manual_gain=req.manual_gain,
                    sidechain_db=req.sidechain_db,
                    reference_path=reference_abs,
                    render_before=req.render_before,
                    apply_plan=req.use_planner,
                    multiband_config=req.multiband,
                    limiter_ceiling_db=req.limiter_ceiling_db,
                    dynamic_eq_config=req.dynamic_eq,
                    midside_eq_config=req.midside_eq,
                    transient_config=req.transient,
                    sidechain_config=req.sidechain,
                    deesser_config=req.deesser,
                    eq_bands=req.eq_bands,
                    spatial_configs=req.spatial_configs,
                    transient_configs=req.transient_configs,
                    reference_match_bands=req.reference_match_bands,
                    progress_callback=reporter,
                )
                result["elapsed_s"] = round(time.perf_counter() - t0, 3)
                reporter.done(result)
            except Exception as exc:  # noqa: BLE001
                reporter.error(str(exc))
            finally:
                ws_manager.cleanup_room(room_id)

        import threading

        threading.Thread(target=_run, daemon=True).start()
        return {"room_id": room_id, "estimated_duration_s": 15}

    try:
        result = preview.render_preview_mix(
            req.directory,
            profile,
            pattern=req.pattern,
            output_path=req.output_path,
            max_duration=req.max_duration,
            manual_gain=req.manual_gain,
            sidechain_db=req.sidechain_db,
            reference_path=reference_abs,
            render_before=req.render_before,
            apply_plan=req.use_planner,
            multiband_config=req.multiband,
            limiter_ceiling_db=req.limiter_ceiling_db,
            dynamic_eq_config=req.dynamic_eq,
            midside_eq_config=req.midside_eq,
            transient_config=req.transient,
            sidechain_config=req.sidechain,
            deesser_config=req.deesser,
            eq_bands=req.eq_bands,
            spatial_configs=req.spatial_configs,
            transient_configs=req.transient_configs,
            reference_match_bands=req.reference_match_bands,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return result


class ReferenceAnalyzeRequest(BaseModel):
    audio_path: str


class ReferenceMatchRequest(BaseModel):
    current_envelope: list[float]
    target_envelope: list[float]
    strength: float = 0.8


class OpenAlsRequest(BaseModel):
    als_path: str


@app.post("/api/reference/analyze")
def api_reference_analyze(req: ReferenceAnalyzeRequest) -> dict[str, Any]:
    from .dsp.reference_matcher import analyze_reference_audio

    abs_path = _resolve_audio_path(req.audio_path)
    analysis = analyze_reference_audio(abs_path)
    return analysis.to_dict()


@app.post("/api/reference/match")
def api_reference_match(req: ReferenceMatchRequest) -> list[dict[str, Any]]:
    from .dsp.reference_matcher import compute_match_eq_curve

    bands = compute_match_eq_curve(req.current_envelope, req.target_envelope, strength=req.strength)
    return bands


@app.post("/api/export/open-als")
def api_open_als(req: OpenAlsRequest) -> dict[str, Any]:
    from .als_xml import open_als_in_ableton

    abs_path = _resolve_audio_path(req.als_path)
    ok = open_als_in_ableton(abs_path)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to launch Ableton Live")
    return {"status": "ok", "opened": abs_path}


@app.post("/api/match_eq")
def api_match_eq(req: MatchEqRequest) -> dict[str, Any]:
    """Match-EQ curve (mix vs reference) without rendering anything.

    Returns {"mix_wav_path", "reference_path", "curve": [{"hz","gain_db"},...]}
    so the UI can draw the corrective curve before committing to a render.
    """
    mix_abs = _resolve_audio_path(req.mix_wav_path)
    ref_abs = _resolve_audio_path(req.reference_path)
    return reference.compute_match_eq_for_files(mix_abs, ref_abs)


@app.post("/api/release")
def api_release(req: ReleaseRequest) -> dict[str, Any]:
    """Release quality gate: ready/needs_work verdict + per-metric results."""
    t0 = time.perf_counter()
    if req.output_path is None:
        if not req.style or not req.directory:
            raise HTTPException(
                status_code=400,
                detail="provide style+directory (to render a preview) or output_path (an existing WAV)",
            )
        profile = _get_profile(req.style)
        _register_dir(req.directory)
        try:
            rendered = preview.render_preview_mix(req.directory, profile, pattern=req.pattern)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        check_path = rendered["output_path"]
        target_lufs = profile.target_lufs
        style_name = profile.name
    else:
        check_path = _resolve_audio_path(req.output_path)
        if req.style is not None:
            profile = _get_profile(req.style)
            style_name, target_lufs = profile.name, profile.target_lufs
        else:
            style_name = os.path.basename(check_path)
            target_lufs = -8.0

    result = qa.release_check(check_path, style_name, target_lufs)
    result["path"] = os.path.abspath(check_path)
    result["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return result


# ---------------------------------------------------------------------------
# Project save / load
# ---------------------------------------------------------------------------


class ProjectSaveRequest(BaseModel):
    state: dict[str, Any] = Field(description="Project state to save.")
    path: str | None = Field(
        default=None,
        description="Explicit save path (.mmc.json). When omitted, auto-saves to the project directory.",
    )


class ProjectLoadRequest(BaseModel):
    path: str = Field(description="Path to a .mmc.json or .musicmixcode.json file.")


@app.post("/api/project/save")
def api_project_save(req: ProjectSaveRequest) -> dict[str, Any]:
    """Save project state to disk. Returns the saved file path."""
    try:
        state = project.ProjectState(
            **{k: v for k, v in req.state.items() if k in project.ProjectState.__dataclass_fields__}
        )
    except (TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid project state: {exc}") from exc

    if req.path:
        saved_path = project.save_project(state, req.path)
    elif state.directory:
        saved_path = project.auto_save(state, state.directory)
    else:
        raise HTTPException(
            status_code=400,
            detail="provide a path or a directory in the project state",
        )

    _register_dir(os.path.dirname(saved_path))
    return {
        "path": saved_path,
        "directory": state.directory,
        "updated_at": state.updated_at,
    }


@app.post("/api/project/load")
def api_project_load(req: ProjectLoadRequest) -> dict[str, Any]:
    """Load project state from disk."""
    try:
        state = project.load_project(req.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"cannot parse project: {exc}") from exc

    if state.directory:
        _register_dir(state.directory)
    return state.to_dict()


@app.get("/api/project/recent")
def api_project_recent(
    max_count: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    """List recently saved projects."""
    return {
        "projects": project.list_recent_projects(max_count),
    }


# ---------------------------------------------------------------------------
# Export to Ableton Live
# ---------------------------------------------------------------------------


class BandCorrectionPayload(BaseModel):
    band: str
    freq_range: list[float]
    measured_db: float = 0.0
    target_db: float = 0.0
    delta_db: float = 0.0


class TrackCorrectionPayload(BaseModel):
    name: str
    index: int = 0
    role: str = "unknown"
    volume_db: float | None = None
    pan: float | None = None
    band_corrections: list[BandCorrectionPayload] = Field(default_factory=list)


class ExportRequest(BaseModel):
    corrections: list[TrackCorrectionPayload] = Field(description="Per-track corrections from the mixer engine.")
    mode: Literal["live", "file"] = Field(
        default="file",
        description="'live' = push via AbletonOSC, 'file' = generate .als XML.",
    )
    session_path: str | None = Field(
        default=None,
        description="Path for the .als file (file mode) or existing session.",
    )
    tempo: float = Field(default=120.0, description="Session BPM for .als export.")
    async_mode: bool = Field(
        default=False,
        description="When true, returns a room_id immediately and streams progress via WS /ws/progress/{room_id}.",
    )


class RecommendRequest(BaseModel):
    directory: str
    pattern: str = "*.wav"
    style: str | None = Field(
        default=None,
        description="Style name for target LUFS. Uses style profile target if given.",
    )


class BatchRequest(BaseModel):
    directories: list[str] = Field(description="List of render directories to process.")
    style: str = Field(description="Style name for all directories.")
    output_dir: str | None = Field(default=None, description="Where to save batch previews.")
    max_duration: float | None = None
    multiband: dict | None = None
    limiter_ceiling_db: float | None = None


class DetectRolesRequest(BaseModel):
    directory: str
    pattern: str = "*.wav"


class ABCompareRequest(BaseModel):
    directory: str
    style_a: str = Field(description="First style name")
    style_b: str = Field(description="Second style name")
    pattern: str = "*.wav"
    max_duration: float | None = None
    multiband: dict | None = None
    limiter_ceiling_db: float | None = None
    dynamic_eq: dict | None = None
    midside_eq: dict | None = None
    transient: dict | None = None


class PresetSaveRequest(BaseModel):
    name: str
    style: str = ""
    multiband: dict | None = None
    limiter_ceiling_db: float | None = None
    dynamic_eq: dict | None = None
    midside_eq: dict | None = None
    transient: dict | None = None
    sidechain: dict | None = None
    notes: str = ""


class PresetLoadRequest(BaseModel):
    name: str = ""


class ExportFormatRequest(BaseModel):
    input_path: str
    format: str = Field(default="wav", description="wav, flac, or mp3")
    bit_depth: str = Field(default="PCM_16", description="For WAV: PCM_16, PCM_24, PCM_32, FLOAT, DOUBLE")
    mp3_bitrate: str = Field(default="192k", description="For MP3: 128k, 192k, 320k")
    flac_compression: int = Field(default=5, description="For FLAC: 0-8")


@app.post("/api/export")
def api_export(req: ExportRequest) -> dict[str, Any]:
    """Export computed corrections to Ableton Live (real-time) or as .als file.

    With async_mode=true, returns a room_id immediately and streams progress via WS.
    """
    t0 = time.perf_counter()

    # Convert Pydantic models to mixer dataclasses
    corrections: list[mixer.TrackCorrection] = []
    for payload in req.corrections:
        band_corrs = [
            mixer.BandCorrection(
                band=bc.band,
                freq_range=bc.freq_range,
                measured_db=bc.measured_db,
                target_db=bc.target_db,
                delta_db=bc.delta_db,
            )
            for bc in payload.band_corrections
        ]
        corrections.append(
            mixer.TrackCorrection(
                index=payload.index,
                name=payload.name,
                role=payload.role,
                volume_db=payload.volume_db,
                pan=payload.pan,
                band_corrections=band_corrs,
            )
        )

    if req.async_mode:
        room_id = new_room_id()
        reporter = ProgressReporter(room_id)

        def _run() -> None:
            try:
                reporter(
                    "exporting",
                    10,
                    f"Exporting {len(corrections)} tracks ({req.mode} mode)…",
                )
                result = ableton_export.export_to_ableton(
                    corrections,
                    mode=req.mode,
                    session_path=req.session_path,
                    tempo=req.tempo,
                )
                if req.mode == "file" and result.session_path:
                    _register_dir(os.path.dirname(result.session_path))
                payload = result.to_dict()
                payload["elapsed_s"] = round(time.perf_counter() - t0, 3)
                reporter.done(payload)
            except Exception as exc:  # noqa: BLE001
                reporter.error(str(exc))
            finally:
                ws_manager.cleanup_room(room_id)

        import threading

        threading.Thread(target=_run, daemon=True).start()
        return {"room_id": room_id, "estimated_duration_s": 5}

    result = ableton_export.export_to_ableton(
        corrections,
        mode=req.mode,
        session_path=req.session_path,
        tempo=req.tempo,
    )

    if req.mode == "file" and result.session_path:
        _register_dir(os.path.dirname(result.session_path))

    payload = result.to_dict()
    payload["elapsed_s"] = round(time.perf_counter() - t0, 3)
    return payload


# ---------------------------------------------------------------------------
# Audio serving / waveform
# ---------------------------------------------------------------------------


@app.get("/api/audio")
def api_audio(
    path: str = Query(description="Absolute path to a whitelisted WAV file"),
) -> FileResponse:
    """Stream a WAV as audio/wav (only from registered render directories)."""
    abs_path = _resolve_audio_path(path)
    return FileResponse(abs_path, media_type="audio/wav", filename=os.path.basename(abs_path))


@app.get("/api/waveform")
def api_waveform(
    path: str = Query(description="Absolute path to a whitelisted WAV file"),
    points: int = Query(default=600, ge=16, le=4096, description="Number of peak samples"),
) -> dict[str, Any]:
    """Downsampled peak envelope of a WAV for waveform drawing."""
    abs_path = _resolve_audio_path(path)
    try:
        info = sf.info(abs_path)
        audio, sr = sf.read(abs_path, always_2d=True, dtype="float32")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=f"cannot read wav: {exc}") from exc

    n = audio.shape[0]
    mono = np.abs(audio[:, : min(audio.shape[1], 2)]).max(axis=1)
    block = max(int(np.ceil(n / points)), 1)
    usable = (n // block) * block
    if usable == 0:
        peaks = mono[:points]
    else:
        peaks = mono[:usable].reshape(-1, block).max(axis=1)
        if n % block:
            tail = mono[usable:].max()
            peaks = np.append(peaks, tail)
    env = [round(float(v), 4) for v in peaks]

    return {
        "path": abs_path,
        "duration_s": round(n / sr, 3),
        "sample_rate": sr,
        "channels": info.channels,
        "frames": n,
        "block_size": block,
        "peaks": env,
        "peak_count": len(env),
    }


@app.post("/api/upload")
async def api_upload(
    file: UploadFile = File(description="WAV file to upload"),
    directory: str = Query(description="Target directory to save the file"),
) -> dict[str, Any]:
    """Upload a WAV file to a target directory on the server."""
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=400, detail="only .wav files are allowed")

    abs_dir = os.path.abspath(directory)
    os.makedirs(abs_dir, exist_ok=True)
    _register_dir(abs_dir)

    safe_name = os.path.basename(file.filename)
    dest = os.path.join(abs_dir, safe_name)

    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)

    return {"path": dest, "name": safe_name}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@app.websocket("/ws/progress/{room_id}")
async def ws_progress(ws: WebSocket, room_id: str) -> None:
    """WebSocket endpoint for streaming progress updates.

    Clients connect after receiving a room_id from an async endpoint.
    Server sends: progress, complete, or error messages as JSON.
    """
    await ws_manager.connect(ws, room_id)
    try:
        while True:
            # Keep the connection alive; we only send, never receive.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws, room_id)


@app.post("/api/recommend")
def api_recommend(req: RecommendRequest) -> dict[str, Any]:
    """AI-powered mix recommendations: analyze tracks and suggest settings."""
    from .ai_recommender import recommend

    _register_dir(req.directory)
    analyses = _load_analyses(req.directory, req.pattern)

    # Build track dicts for the recommender
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
        # Detect role
        import numpy as np

        from .auto_role import detect_role

        audio, sr = sf.read(a.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        role_result = detect_role(np.asarray(audio, dtype=np.float64), sr, a.name)
        t["role"] = role_result.role
        t["role_confidence"] = role_result.confidence
        tracks.append(t)

    # Target LUFS from style profile
    target_lufs = -14.0
    if req.style:
        try:
            profile = _get_profile(req.style)
            target_lufs = profile.target_lufs
        except Exception:
            pass

    recs = recommend(tracks, target_lufs=target_lufs)

    return {
        "recommendations": [
            {
                "category": r.category,
                "target": r.target,
                "param": r.param,
                "value": r.value,
                "reason": r.reason,
                "confidence": r.confidence,
            }
            for r in recs.recommendations
        ],
        "summary": recs.summary,
        "role_map": recs.role_map,
    }


@app.post("/api/detect_roles")
def api_detect_roles(req: DetectRolesRequest) -> dict[str, Any]:
    """Detect instrument roles for all tracks in a directory."""
    import numpy as np

    _register_dir(req.directory)
    analyses = _load_analyses(req.directory, req.pattern)

    from .auto_role import detect_role

    roles = []
    for a in analyses:
        audio, sr = sf.read(a.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        result = detect_role(np.asarray(audio, dtype=np.float64), sr, a.name)
        roles.append(
            {
                "name": a.name,
                "role": result.role,
                "confidence": result.confidence,
            }
        )

    return {"roles": roles}


@app.post("/api/batch")
def api_batch(req: BatchRequest) -> dict[str, Any]:
    """Batch process multiple directories with the same style."""
    from .batch import run_batch

    result = run_batch(
        directories=req.directories,
        style=req.style,
        output_dir=req.output_dir,
        max_duration=req.max_duration,
        multiband_config=req.multiband,
        limiter_ceiling_db=req.limiter_ceiling_db,
    )

    return {
        "total": result.total,
        "completed": result.completed,
        "failed": result.failed,
        "items": [
            {
                "directory": item.directory,
                "style": item.style,
                "status": item.status,
                "error": item.error,
                "output_path": item.result.get("output_path") if item.result else None,
            }
            for item in result.items
        ],
    }


@app.post("/api/preview/ab")
def api_ab_compare(req: ABCompareRequest) -> dict[str, Any]:
    """Render the same tracks with two different styles for A/B comparison."""
    from .ab_compare import render_ab_compare

    _register_dir(req.directory)
    result = render_ab_compare(
        render_dir=req.directory,
        style_a=req.style_a,
        style_b=req.style_b,
        pattern=req.pattern,
        max_duration=req.max_duration,
        multiband_config=req.multiband,
        limiter_ceiling_db=req.limiter_ceiling_db,
        dynamic_eq_config=req.dynamic_eq,
        midside_eq_config=req.midside_eq,
        transient_config=req.transient,
    )
    return {
        "style_a": result.style_a,
        "style_b": result.style_b,
        "output_a": result.output_a,
        "output_b": result.output_b,
        "result_a": result.result_a,
        "result_b": result.result_b,
    }


@app.get("/api/presets")
def api_list_presets() -> dict[str, Any]:
    """List all saved mix presets."""
    from .presets import list_presets

    return {"presets": list_presets()}


@app.post("/api/presets/save")
def api_save_preset(req: PresetSaveRequest) -> dict[str, Any]:
    """Save a mix preset."""
    from .presets import MixPreset, save_preset

    preset = MixPreset(
        name=req.name,
        style=req.style,
        multiband=req.multiband,
        limiter_ceiling_db=req.limiter_ceiling_db,
        dynamic_eq=req.dynamic_eq,
        midside_eq=req.midside_eq,
        transient=req.transient,
        sidechain=req.sidechain,
        notes=req.notes,
    )
    path = save_preset(preset)
    return {"saved": True, "path": path}


@app.post("/api/presets/load")
def api_load_preset(req: PresetLoadRequest) -> dict[str, Any]:
    """Load a mix preset by name."""
    from .presets import load_preset

    preset = load_preset(req.name)
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


@app.delete("/api/presets/{name}")
def api_delete_preset(name: str) -> dict[str, Any]:
    """Delete a mix preset by name."""
    from .presets import delete_preset

    deleted = delete_preset(name)
    return {"deleted": deleted}


@app.post("/api/export/format")
def api_export_format(req: ExportFormatRequest) -> dict[str, Any]:
    """Export a rendered preview WAV to another format (WAV/FLAC/MP3)."""
    from .export_formats import export_preview

    base, _ = os.path.splitext(req.input_path)
    output_path = f"{base}.{req.format}"
    result = export_preview(
        input_wav=req.input_path,
        output_path=output_path,
        format=req.format,
        bit_depth=req.bit_depth,
        mp3_bitrate=req.mp3_bitrate,
        flac_compression=req.flac_compression,
    )
    return {
        "path": result.path,
        "format": result.format,
        "sample_rate": result.sample_rate,
        "channels": result.channels,
        "duration_s": result.duration_s,
        "file_size_bytes": result.file_size_bytes,
        "bit_depth": result.bit_depth,
        "bitrate": result.bitrate,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ableton_auto_mix.api_app",
        description="HTTP API for the ableton-auto-mix engine (desktop app backend).",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8787, help="bind port (default 8787)")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
