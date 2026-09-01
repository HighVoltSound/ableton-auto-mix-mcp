"""Multi-format export: WAV, FLAC, MP3.

Takes a preview WAV and re-encodes it to the requested format.
Falls back gracefully if the encoder for a format isn't available.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np
import soundfile as sf


@dataclass
class ExportResult:
    path: str
    format: str
    sample_rate: int
    channels: int
    duration_s: float
    file_size_bytes: int
    bit_depth: str | None = None
    bitrate: str | None = None


def _find_ffmpeg() -> str | None:
    """Find ffmpeg binary on PATH."""
    return shutil.which("ffmpeg")


def export_wav(
    audio: np.ndarray,
    sr: int,
    output_path: str,
    bit_depth: str = "PCM_16",
) -> ExportResult:
    """Export as WAV with configurable bit depth."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    subtype_map = {
        "PCM_16": "PCM_16",
        "PCM_24": "PCM_24",
        "PCM_32": "PCM_32",
        "FLOAT": "FLOAT",
        "DOUBLE": "DOUBLE",
    }
    subtype = subtype_map.get(bit_depth, "PCM_16")
    sf.write(output_path, audio, sr, subtype=subtype)
    info = sf.info(output_path)
    return ExportResult(
        path=output_path,
        format="wav",
        sample_rate=sr,
        channels=audio.shape[1] if audio.ndim > 1 else 1,
        duration_s=float(info.duration),
        file_size_bytes=os.path.getsize(output_path),
        bit_depth=bit_depth,
    )


def export_flac(
    audio: np.ndarray,
    sr: int,
    output_path: str,
    compression_level: float = 5,
) -> ExportResult:
    """Export as FLAC."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cl = compression_level / 8.0 if compression_level > 1.0 else compression_level
    cl = min(max(cl, 0.0), 1.0)
    sf.write(output_path, audio, sr, format="FLAC", compression_level=cl)
    info = sf.info(output_path)
    return ExportResult(
        path=output_path,
        format="flac",
        sample_rate=sr,
        channels=audio.shape[1] if audio.ndim > 1 else 1,
        duration_s=float(info.duration),
        file_size_bytes=os.path.getsize(output_path),
    )


def export_mp3(
    audio: np.ndarray,
    sr: int,
    output_path: str,
    bitrate: str = "192k",
) -> ExportResult:
    """Export as MP3 via ffmpeg (requires ffmpeg on PATH)."""
    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg to export MP3 files.")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Write temporary WAV first, then convert via ffmpeg
    tmp_wav = output_path + ".tmp.wav"
    sf.write(tmp_wav, audio, sr, subtype="PCM_16")

    try:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            tmp_wav,
            "-codec:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            "-q:a",
            "2",  # VBR quality (used when bitrate is not set)
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

    # Get info
    info = sf.info(output_path) if os.path.exists(output_path) else None
    return ExportResult(
        path=output_path,
        format="mp3",
        sample_rate=sr,
        channels=audio.shape[1] if audio.ndim > 1 else 1,
        duration_s=float(info.duration) if info else 0.0,
        file_size_bytes=os.path.getsize(output_path),
        bitrate=bitrate,
    )


def export_preview(
    input_wav: str,
    output_path: str,
    format: str = "wav",
    bit_depth: str = "PCM_16",
    mp3_bitrate: str = "192k",
    flac_compression: int = 5,
) -> ExportResult:
    """Export a rendered preview WAV to the desired format.

    Args:
        input_wav: path to the source WAV
        output_path: path for the output file
        format: "wav", "flac", or "mp3"
        bit_depth: for WAV — "PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"
        mp3_bitrate: for MP3 — "128k", "192k", "320k", etc.
        flac_compression: for FLAC — 0..8

    Returns:
        ExportResult with metadata
    """
    audio, sr = sf.read(input_wav, always_2d=False)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]

    format = format.lower().strip(".")

    if format == "flac":
        return export_flac(audio, sr, output_path, compression_level=flac_compression)
    elif format == "mp3":
        return export_mp3(audio, sr, output_path, bitrate=mp3_bitrate)
    else:
        return export_wav(audio, sr, output_path, bit_depth=bit_depth)
