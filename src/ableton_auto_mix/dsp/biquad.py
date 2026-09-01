"""RBJ biquad filter coefficients — single source of truth.

Consolidates the peaking / low-shelf / high-shelf formulas duplicated in
reference.py and dsp/midside_eq.py.  Apply with ``apply_biquad`` (lfilter)
or ``apply_biquad_sos`` (sosfiltfilt / zero-phase).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter, sosfiltfilt

DEFAULT_PEAK_Q = 1.0


# ---------------------------------------------------------------------------
# Coefficient calculators (RBJ Audio EQ Cookbook)
# ---------------------------------------------------------------------------


def _clip_f0(f0: float, sr: int) -> float:
    """Keep the corner frequency inside a range biquads stay stable in."""
    return float(np.clip(f0, 20.0, sr * 0.45))


def peaking_biquad(sr: int, f0: float, gain_db: float, q: float = DEFAULT_PEAK_Q) -> tuple[np.ndarray, np.ndarray]:
    """RBJ peaking EQ biquad: +/- gain_db dB around f0 with quality q."""
    f0 = _clip_f0(f0, sr)
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))
    cos_w0 = np.cos(w0)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * cos_w0
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha / A
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def low_shelf_biquad(sr: int, f0: float, gain_db: float, q: float = DEFAULT_PEAK_Q) -> tuple[np.ndarray, np.ndarray]:
    """RBJ low-shelf biquad: raises/lowers everything below f0 by gain_db."""
    f0 = _clip_f0(f0, sr)
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))
    cw = np.cos(w0)
    sq = 2.0 * np.sqrt(A) * alpha

    b0 = A * ((A + 1.0) - (A - 1.0) * cw + sq)
    b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cw)
    b2 = A * ((A + 1.0) - (A - 1.0) * cw - sq)
    a0 = (A + 1.0) + (A - 1.0) * cw + sq
    a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cw)
    a2 = (A + 1.0) + (A - 1.0) * cw - sq
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def high_shelf_biquad(sr: int, f0: float, gain_db: float, q: float = DEFAULT_PEAK_Q) -> tuple[np.ndarray, np.ndarray]:
    """RBJ high-shelf biquad: raises/lowers everything above f0 by gain_db."""
    f0 = _clip_f0(f0, sr)
    A = 10 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2.0 * max(q, 0.1))
    cw = np.cos(w0)
    sq = 2.0 * np.sqrt(A) * alpha

    b0 = A * ((A + 1.0) + (A - 1.0) * cw + sq)
    b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cw)
    b2 = A * ((A + 1.0) + (A - 1.0) * cw - sq)
    a0 = (A + 1.0) - (A - 1.0) * cw + sq
    a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cw)
    a2 = (A + 1.0) - (A - 1.0) * cw - sq
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


# ---------------------------------------------------------------------------
# Application helpers
# ---------------------------------------------------------------------------


def apply_biquad(audio: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Filter along time axis (channel-wise) with lfilter — causal, fast."""
    return lfilter(b, a, audio, axis=0)


def apply_biquad_sos(audio: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Zero-phase biquad (sosfiltfilt) per channel — used for mid/side EQ."""
    out = np.empty_like(audio)
    sos = np.array([[b[0], b[1], b[2], a[0], a[1], a[2]]])
    for ch in range(audio.shape[1]):
        out[:, ch] = sosfiltfilt(sos, audio[:, ch])
    return out
