"""Reference-guided match EQ and shared biquad filter primitives.

The match EQ compares the average spectrum of the mix to a reference track,
derives a corrective curve (form only — overall loudness is normalized away),
and applies it as a cascade of peaking biquad filters. The same RBJ-cookbook
biquad designs (peaking / low shelf / high shelf) are reused by the preview
renderer for the per-track spectral corrections from mixer.compute_mix.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.signal import resample_poly, welch

from .dsp.biquad import (
    apply_biquad,
)
from .dsp.biquad import (
    peaking_biquad as _peaking_biquad,
)

# Safety clamps: never boost/cut more than this with the match/track EQ.
MAX_MATCH_GAIN_DB = 6.0


# ---------------------------------------------------------------------------
# Loading / resampling helpers
# ---------------------------------------------------------------------------


def load_audio_stereo(path: str) -> tuple[np.ndarray, int]:
    """Load a WAV file as float64 stereo (channels reduced/duplicated to 2)."""
    audio, sr = sf.read(path, always_2d=False, dtype="float64")
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    elif audio.shape[1] > 2:
        audio = audio[:, :2]
    return np.ascontiguousarray(audio, dtype=np.float64), int(sr)


def resample_to(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Polyphase-resample an (N, ch) array from orig_sr to target_sr."""
    orig_sr, target_sr = int(orig_sr), int(target_sr)
    if orig_sr == target_sr or audio.size == 0:
        return audio
    import math

    g = math.gcd(orig_sr, target_sr)
    return resample_poly(audio, target_sr // g, orig_sr // g, axis=0)


# RBJ biquads and apply_biquad — imported from dsp.biquad


# ---------------------------------------------------------------------------
# Match-EQ curve
# ---------------------------------------------------------------------------


def _band_spectrum_db(audio: np.ndarray, sr: int, edges: np.ndarray) -> np.ndarray:
    """Mean power (dB) of the mono downmix inside each log-spaced band."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    nperseg = min(len(mono), 8192)
    if nperseg < 256:  # very short signals still need a usable FFT size
        nperseg = max(2 ** int(np.ceil(np.log2(max(len(mono), 16)))), 16)
    freqs, psd = welch(mono, fs=sr, nperseg=nperseg)
    out = np.empty(len(edges) - 1)
    for i, (lo, hi) in enumerate(zip(edges[:-1], edges[1:], strict=False)):
        mask = (freqs >= lo) & (freqs < hi)
        # Welch bins are linear; take the mean power of every bin touching
        # the band so narrow high-frequency bands are not under-sampled.
        p = float(np.mean(psd[mask])) if mask.any() else 0.0
        out[i] = 10.0 * np.log10(p + 1e-20)
    return out


def compute_match_curve(
    mix_audio_sr: int | float,
    mix_audio: np.ndarray,
    ref_audio_sr: int | float,
    ref_audio: np.ndarray,
    n_bands: int = 24,
) -> list[dict[str, float]]:
    """Compute the corrective EQ curve that shapes the mix toward a reference.

    Both signals are compared as average log-spaced spectra (20 Hz .. 20 kHz
    or Nyquist). Each spectrum's mean is removed first so only the *shape*
    matters — overall loudness is handled elsewhere. The difference
    (mix - reference) is smoothed (median + moving average over neighbouring
    bands) and clamped to +/-6 dB.

    Returns:
        List of {"hz": band_center_hz, "gain_db": correction_db} points,
        sorted by frequency.
    """
    n_bands = max(int(n_bands), 4)
    sr = int(mix_audio_sr)
    ref = resample_to(np.asarray(ref_audio, dtype=np.float64), int(ref_audio_sr), sr)

    nyquist_cap = sr * 0.45
    f_max = min(20000.0, nyquist_cap)
    if f_max <= 25.0:  # absurdly low sample rate; keep bands valid anyway
        f_max = nyquist_cap
    edges = np.geomspace(20.0, f_max, n_bands + 1)

    mix_shape = _band_spectrum_db(np.asarray(mix_audio, dtype=np.float64), sr, edges)
    ref_shape = _band_spectrum_db(ref, sr, edges)

    # Normalize away absolute level: compare only spectral form.
    diff = (mix_shape - mix_shape.mean()) - (ref_shape - ref_shape.mean())

    # Smooth: median kills single-band spikes, then a light moving average.
    diff = median_filter(diff, size=3, mode="nearest")
    diff = uniform_filter1d(diff, size=3, mode="nearest")
    gains = np.clip(diff, -MAX_MATCH_GAIN_DB, MAX_MATCH_GAIN_DB)

    centers = np.sqrt(edges[:-1] * edges[1:])
    return [{"hz": round(float(c), 1), "gain_db": round(float(g), 2)} for c, g in zip(centers, gains, strict=False)]


def _local_maxima_indices(x: np.ndarray) -> list[int]:
    """Indices of local maxima (boundaries count when they dominate inward)."""
    idx: list[int] = []
    n = len(x)
    for i, v in enumerate(x):
        left = x[i - 1] if i > 0 else -np.inf
        right = x[i + 1] if i < n - 1 else -np.inf
        if v >= left and v >= right and (v > left or v > right):
            idx.append(i)
    return idx


def apply_match_eq(
    audio: np.ndarray,
    sr: int,
    curve: list[dict[str, float]],
    max_nodes: int = 9,
    q: float = 1.2,
) -> np.ndarray:
    """Apply a match-EQ curve as a cascade of peaking biquad filters.

    The curve is interpolated implicitly by keeping only its strongest local
    maxima (up to `max_nodes`) — a sparse, musical approximation instead of
    one filter per band. Each node becomes a peaking biquad applied in series.
    """
    if not curve or audio.size == 0:
        return audio
    hz = np.array([p["hz"] for p in curve], dtype=np.float64)
    gains = np.array([p["gain_db"] for p in curve], dtype=np.float64)

    candidates = _local_maxima_indices(np.abs(gains))
    if not candidates:
        candidates = [int(np.argmax(np.abs(gains)))]
    candidates.sort(key=lambda i: -abs(gains[i]))
    selected = sorted(candidates[: max(int(max_nodes), 1)])

    out = np.asarray(audio, dtype=np.float64)
    for i in selected:
        delta = float(np.clip(gains[i], -MAX_MATCH_GAIN_DB, MAX_MATCH_GAIN_DB))
        if abs(delta) < 0.3:
            continue
        f0 = float(np.clip(hz[i], 20.0, sr * 0.45))
        b, a = _peaking_biquad(int(sr), f0, delta, q=q)
        out = apply_biquad(out, b, a)
    return out


def compute_match_eq_for_files(mix_wav_path: str, reference_path: str, n_bands: int = 24) -> dict[str, Any]:
    """Curve for a mix/reference pair of files (used by the HTTP API)."""
    mix_audio, mix_sr = load_audio_stereo(mix_wav_path)
    ref_audio, ref_sr = load_audio_stereo(reference_path)
    curve = compute_match_curve(mix_sr, mix_audio, ref_sr, ref_audio, n_bands=n_bands)
    return {
        "mix_wav_path": os.path.abspath(mix_wav_path),
        "reference_path": os.path.abspath(reference_path),
        "curve": curve,
    }
