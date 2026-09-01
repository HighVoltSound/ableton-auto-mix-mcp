"""Automatic role detection using spectral fingerprinting.

Goes beyond filename matching by computing per-band energy, spectral centroid,
spectral flatness, crest factor, and transient density — then classifying
into roles (kick, bass, snare, hihat, pads, lead, vocals, etc.) with a
confidence score.

The classifier is a deterministic decision tree (no ML dependency) calibrated
from real-world stem analyses.  It returns the best-guess role plus a
confidence 0..1 so the caller can decide whether to trust it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

# Band definitions matching analyzer.py
BANDS = [
    ("sub_bass", 20.0, 60.0),
    ("bass", 60.0, 120.0),
    ("low_mids", 120.0, 250.0),
    ("mids", 250.0, 2000.0),
    ("high_mids", 2000.0, 6000.0),
    ("highs", 6000.0, 20000.0),
]


@dataclass
class RoleResult:
    role: str
    confidence: float
    features: dict  # raw features for debugging / further use


def _band_rms(audio: np.ndarray, sr: int, fmin: float, fmax: float) -> float:
    """RMS energy of a frequency band in dBFS."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    sos = butter(4, [max(fmin, 1.0), min(fmax, sr * 0.49)], btype="bandpass", fs=sr, output="sos")
    filtered = sosfiltfilt(sos, mono)
    rms = float(np.sqrt(np.mean(filtered**2)) + 1e-12)
    return float(20 * np.log10(rms))


def _spectral_centroid(audio: np.ndarray, sr: int) -> float:
    """Intensity-weighted mean frequency (Hz)."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    n = len(mono)
    fft = np.abs(np.fft.rfft(mono))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    total = float(np.sum(fft)) + 1e-12
    return float(np.sum(freqs * fft) / total)


def _spectral_flatness(audio: np.ndarray, sr: int) -> float:
    """Geometric mean / arithmetic mean of spectrum (0=tonal, 1=noise)."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    fft = np.abs(np.fft.rfft(mono)) + 1e-12
    log_mean = float(np.mean(np.log(fft)))
    mean = float(np.mean(fft))
    return float(np.clip(np.exp(log_mean) / mean, 0.0, 1.0))


def _crest_factor(audio: np.ndarray, sr: int) -> float:
    """Peak / RMS ratio in dB — high = transient-heavy."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    peak = float(np.max(np.abs(mono)))
    rms = float(np.sqrt(np.mean(mono**2)) + 1e-12)
    return 20 * np.log10(peak / rms)


def _transient_density(audio: np.ndarray, sr: int) -> float:
    """Fraction of time with sharp onsets (derivative spikes)."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    # Short-term RMS (5 ms)
    win = max(int(0.005 * sr), 1)
    n = len(mono)
    rms = np.array([np.sqrt(np.mean(mono[i : i + win] ** 2) + 1e-12) for i in range(0, n - win, win)])
    # Derivative
    diff = np.diff(rms, prepend=rms[0])
    threshold = float(np.percentile(np.abs(diff), 85))
    spikes = float(np.mean(np.abs(diff) > threshold))
    return float(np.clip(spikes, 0.0, 1.0))


def _stereo_width(audio: np.ndarray) -> float:
    """Correlation-based width 0..1."""
    if audio.ndim < 2:
        return 0.0
    left, right = audio[:, 0], audio[:, 1]
    denom = float(np.sqrt(np.mean(left**2) * np.mean(right**2)) + 1e-12)
    corr = float(np.mean(left * right) / denom)
    return float(np.clip(1.0 - abs(corr), 0.0, 1.0))


def _compute_features(audio: np.ndarray, sr: int) -> dict:
    """Extract the full feature set for role classification."""
    band_energy = {}
    for name, fmin, fmax in BANDS:
        band_energy[name] = _band_rms(audio, sr, fmin, fmax)

    # Relative energy (dB from peak)
    vals = np.array([band_energy[b] for b in [b[0] for b in BANDS]])
    peak = float(vals.max())
    rel = {k: v - peak for k, v in band_energy.items()}

    return {
        "band_energy": band_energy,
        "band_relative": rel,
        "spectral_centroid": _spectral_centroid(audio, sr),
        "spectral_flatness": _spectral_flatness(audio, sr),
        "crest_factor": _crest_factor(audio, sr),
        "transient_density": _transient_density(audio, sr),
        "stereo_width": _stereo_width(audio),
        "rms_db": float(20 * np.log10(np.sqrt(np.mean(audio**2)) + 1e-12)),
    }


def classify_role(features: dict) -> tuple[str, float]:
    """Decision-tree role classification from features.

    Returns (role, confidence).
    """
    rel = features["band_relative"]
    centroid = features["spectral_centroid"]
    flatness = features["spectral_flatness"]
    crest = features["crest_factor"]
    trans = features["transient_density"]
    width = features["stereo_width"]

    sub_hot = rel.get("sub_bass", -120) > -12.0
    bass_hot = rel.get("bass", -120) > -12.0
    low_mids_hot = rel.get("low_mids", -120) > -12.0
    mids_hot = rel.get("mids", -120) > -12.0
    high_mids_hot = rel.get("high_mids", -120) > -12.0
    highs_hot = rel.get("highs", -120) > -12.0

    scores: dict[str, float] = {}

    # === KICK: sub+bass+low_mids, high crest, low centroid ===
    if sub_hot and bass_hot:
        s = 0.5
        if low_mids_hot:
            s += 0.2
        if crest > 12:
            s += 0.15
        if centroid < 200:
            s += 0.15
        if flatness < 0.3:
            s += 0.1
        scores["kick"] = min(s, 1.0)

    # === SUB BASS: sub dominant, very low centroid ===
    if sub_hot and not bass_hot and not low_mids_hot:
        s = 0.6
        if centroid < 80:
            s += 0.2
        if flatness < 0.2:
            s += 0.1
        scores["sub_bass"] = min(s, 1.0)

    # === BASS: bass dominant, low centroid ===
    if bass_hot and not sub_hot:
        s = 0.5
        if centroid < 300:
            s += 0.2
        if not low_mids_hot:
            s += 0.1
        scores["bass"] = min(s, 1.0)

    # === SNARE: mids+high_mids, high crest, wide ===
    if high_mids_hot and crest > 10:
        s = 0.4
        if mids_hot:
            s += 0.2
        if trans > 0.3:
            s += 0.2
        if 2000 < centroid < 5000:
            s += 0.15
        if not sub_hot and not bass_hot:
            s += 0.1
        scores["snare"] = min(s, 1.0)

    # === HIHAT: highs dominant, flat spectrum, high crest ===
    if highs_hot and not bass_hot:
        s = 0.4
        if flatness > 0.4:
            s += 0.2
        if crest > 15:
            s += 0.15
        if centroid > 5000:
            s += 0.2
        if not sub_hot and not mids_hot:
            s += 0.1
        scores["hihat"] = min(s, 1.0)

    # === VOCALS: mids dominant, narrow stereo, moderate crest ===
    if mids_hot and 300 < centroid < 4000:
        s = 0.3
        if 0.15 < width < 0.5:
            s += 0.2
        if 6 < crest < 14:
            s += 0.15
        if flatness < 0.5:
            s += 0.1
        if high_mids_hot:
            s += 0.1
        scores["vocals"] = min(s, 1.0)

    # === PADS: low_mids+mids, low crest, wide, low flatness ===
    if low_mids_hot and mids_hot and crest < 8:
        s = 0.4
        if width > 0.4:
            s += 0.2
        if trans < 0.15:
            s += 0.15
        if flatness < 0.4:
            s += 0.1
        scores["pads"] = min(s, 1.0)

    # === LEAD: high_mids dominant, narrow ===
    if high_mids_hot and not low_mids_hot and 1500 < centroid < 6000:
        s = 0.4
        if width < 0.4:
            s += 0.15
        if crest > 8:
            s += 0.15
        scores["lead"] = min(s, 1.0)

    # === MELODY: mids, tonal ===
    if mids_hot and flatness < 0.4:
        s = 0.3
        if 500 < centroid < 3000:
            s += 0.2
        scores["melody"] = min(s, 1.0)

    # === PERCUSSION: high crest, transient-heavy, no strong tonal band ===
    if trans > 0.35 and crest > 12:
        s = 0.4
        if not sub_hot and not bass_hot:
            s += 0.2
        scores["percussion"] = min(s, 1.0)

    # === WOBBLE: sub+bass+low_mids, all hot ===
    if sub_hot and bass_hot and low_mids_hot:
        s = 0.5
        if flatness < 0.3:
            s += 0.15
        scores["wobble"] = min(s, 1.0)

    # Fallback
    if not scores:
        return "unknown", 0.0

    best = max(scores, key=lambda k: scores[k])
    return best, scores[best]


def detect_role(audio: np.ndarray, sr: int, filename: str = "") -> RoleResult:
    """Full role detection: filename first, then spectral classification.

    Args:
        audio: stereo signal (N, 2)
        sr: sample rate
        filename: original filename for name-based matching

    Returns:
        RoleResult with role, confidence, and features.
    """
    # Filename matching first (fast, reliable when names are descriptive)
    from .mixer import match_role

    name_role = match_role(filename)
    if name_role != "unknown":
        features = _compute_features(audio, sr)
        return RoleResult(role=name_role, confidence=0.95, features=features)

    # Spectral classification
    features = _compute_features(audio, sr)
    role, confidence = classify_role(features)
    return RoleResult(role=role, confidence=confidence, features=features)
