"""Audio analysis: loudness, spectral balance, stereo width, dynamics.

Operates offline on rendered WAV files so the mix engine can measure the
current state of a project without relying on realtime Ableton metering.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfiltfilt

BANDS = [
    ("sub_bass", 20.0, 60.0),
    ("bass", 60.0, 120.0),
    ("low_mids", 120.0, 250.0),
    ("mids", 250.0, 2000.0),
    ("high_mids", 2000.0, 6000.0),
    ("highs", 6000.0, 20000.0),
]


@dataclass
class TrackAnalysis:
    name: str
    path: str
    sample_rate: int
    duration_s: float
    rms_db: float
    peak_db: float
    lufs: float
    lra: float
    bandwidth_db: dict[str, float] = field(default_factory=dict)
    stereo_width: float = 0.0
    true_peak_dbtp: float = 0.0


def _band_energy_db(audio: np.ndarray, sr: int, fmin: float, fmax: float) -> float:
    """Return band RMS energy in dBFS for a mono-ish signal.

    Uses a 4th-order Butterworth band-pass filter so the measurement is a
    true RMS level of the band (dBFS), comparable across tracks and to the
    style profile targets.
    """
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    sos = butter(4, [fmin, fmax], btype="bandpass", fs=sr, output="sos")
    filtered = sosfiltfilt(sos, audio)
    rms = float(np.sqrt(np.mean(filtered**2)) + 1e-12)
    return float(20 * np.log10(rms))


def _stereo_width(audio: np.ndarray) -> float:
    """Correlation-based width 0..1: 0 = mono, 1 = fully decorrelated."""
    if audio.ndim < 2:
        return 0.0
    left = audio[:, 0]
    right = audio[:, 1]
    denom = np.sqrt(np.mean(left**2) * np.mean(right**2)) + 1e-12
    corr = float(np.mean(left * right) / denom)
    return float(np.clip(1.0 - abs(corr), 0.0, 1.0))


def _to_stereo(audio: np.ndarray) -> np.ndarray:
    """Return a 2-channel signal, duplicating mono input."""
    if audio.ndim == 1:
        return np.stack([audio, audio], axis=1)
    if audio.ndim > 2:
        return audio[:, :2]
    return audio


def _true_peak_db(audio: np.ndarray, sr: int) -> float:
    """True peak (dBTP) via 4x oversampling of both channels."""
    stereo = _to_stereo(audio)
    up = resample_poly(stereo, 4, 1, axis=0)
    peak = float(np.max(np.abs(up)))
    return 20 * np.log10(peak + 1e-12)


def analyze_track(path: str) -> TrackAnalysis:
    """Analyze a single WAV file into mix-relevant metrics."""
    audio, sr = sf.read(path, always_2d=False)
    if audio.ndim > 2:
        audio = audio[:, :, 0]
    name = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].rsplit(".", 1)[0]

    stereo = _to_stereo(audio)
    mono = stereo.mean(axis=1)

    # RMS / peak
    rms = float(np.sqrt(np.mean(mono**2)) + 1e-12)
    peak = float(np.max(np.abs(mono)))

    # Loudness (BS.1770) — always measured on a 2-channel signal so mono
    # renders get a real LUFS/LRA instead of a placeholder -120.
    meter = pyln.Meter(sr)
    lufs = float(meter.integrated_loudness(stereo))
    lra = float(meter.loudness_range(stereo))

    width = _stereo_width(stereo)

    bands = {b: _band_energy_db(audio, sr, lo, hi) for b, lo, hi in BANDS}

    return TrackAnalysis(
        name=name,
        path=path,
        sample_rate=int(sr),
        duration_s=float(audio.shape[0] / sr),
        rms_db=float(20 * np.log10(rms)),
        peak_db=float(20 * np.log10(peak)),
        lufs=lufs,
        lra=lra,
        bandwidth_db=bands,
        stereo_width=width,
        true_peak_dbtp=_true_peak_db(stereo, sr),
    )


def analyze_directory(directory: str, pattern: str = "*.wav") -> list[TrackAnalysis]:
    """Analyze every WAV in a directory (one per render). Skips any file that
    looks like a previously rendered preview mix."""
    import glob
    import os

    results = []
    for path in sorted(glob.glob(os.path.join(directory, pattern))):
        if os.path.basename(path).lower().startswith("preview_"):
            continue
        try:
            results.append(analyze_track(path))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to analyze {path}: {exc}") from exc
    return results
