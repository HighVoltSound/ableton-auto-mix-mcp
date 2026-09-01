"""Shared DSP primitives used across the processing pipeline.

These were extracted from preview.py to eliminate star dependencies where
6+ modules imported private functions from the rendering engine.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import lfilter, resample_poly

# ---------------------------------------------------------------------------
# Sliding-window primitives
# ---------------------------------------------------------------------------


def sliding_max(x: np.ndarray, window: int) -> np.ndarray:
    """O(N) sliding-window maximum over axis 0 (van Herk / Gil-Werman).

    Equivalent to maximum_filter1d but linear in the number of samples even
    for large windows, so it stays fast on long oversampled buffers.
    """
    w = max(int(window), 1)
    n = x.shape[0]
    if n <= w:
        return np.maximum.accumulate(x, axis=0)
    if w == 1:
        return x.copy()
    out = np.empty_like(x)
    # Block-wise prefix (forward) and suffix (backward) maxima.
    n_blocks = (n + w - 1) // w
    pad = n_blocks * w - n
    if pad:
        xp = np.concatenate([x, np.zeros((pad,) + x.shape[1:], dtype=x.dtype)], axis=0)
    else:
        xp = x
    blocks = xp.reshape(n_blocks, w, *x.shape[1:])
    fwd = np.maximum.accumulate(blocks, axis=1)
    rev = blocks[:, ::-1, ...]
    bwd = np.maximum.accumulate(rev, axis=1)[:, ::-1, ...]
    fwd = fwd.reshape(-1, *x.shape[1:])
    bwd = bwd.reshape(-1, *x.shape[1:])
    # For sample i the window is [i-w+1, i]: left part from bwd (block suffix
    # of the block containing i-w+1), right part from fwd (block prefix up to i).
    out = np.empty_like(x)
    out[: w - 1] = fwd[: w - 1]  # window still growing from sample 0
    if w <= n:
        out[w - 1 :] = np.maximum(bwd[: n - w + 1], fwd[w - 1 : n])
    return out


def moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """O(N) sliding-window average via cumulative sums (per channel)."""
    w = max(int(window), 1)
    n = x.shape[0]
    if n <= w:
        return np.full_like(x, np.mean(x, axis=0, keepdims=True))
    cum = np.cumsum(x, axis=0)
    out = np.empty_like(x, dtype=np.float64)
    denom = np.minimum(np.arange(1, n + 1), w)
    shape = (n,) + (1,) * (x.ndim - 1)
    head = cum / denom.reshape(shape)
    tail = cum[w:] - cum[:-w]
    out[:w] = head[:w]
    out[w:] = tail / w
    return out


# ---------------------------------------------------------------------------
# Dynamics
# ---------------------------------------------------------------------------


def compressor(
    audio: np.ndarray,
    sr: int,
    threshold_db: float = -12.0,
    ratio: float = 3.0,
    attack_ms: float = 10.0,
    release_ms: float = 120.0,
    makeup_db: float = 0.0,
) -> np.ndarray:
    """Gentle feed-forward compressor with a smooth knee.

    Envelope is a peak-tracked average; gain reduction is applied with a fast
    attack (sliding max) and an exponential release so it glues without
    pumping. Used for the profile's per-track and glue-bus compression.
    """
    threshold = 10 ** (threshold_db / 20.0)
    ratio = max(float(ratio), 1.0)
    attack = max(int(attack_ms / 1000.0 * sr), 1)
    release = max(int(release_ms / 1000.0 * sr), 1)

    # Peak-tracked envelope on the stereo pair (RMS-ish, one-pole smoothed).
    env = np.sqrt(np.mean(audio**2, axis=1)) + 1e-12
    env = moving_average(env, attack)
    env_hold = sliding_max(env, attack)

    # Over-threshold reduction in linear terms: below thresh no gain change.
    over = np.maximum(env_hold / threshold, 1.0)
    # Compressor curve: y = x^(1/ratio) above the threshold (soft knee via a
    # small linear taper right at the threshold to avoid a hard kink).
    knee = 2.0
    taper = np.clip(
        (env_hold / threshold - 1.0) / (knee / threshold) * (1.0 / ratio) + (1.0 - 1.0 / ratio),
        0.0,
        1.0,
    )
    gain = np.power(over, (1.0 / ratio - 1.0))
    gain = 1.0 + (gain - 1.0) * np.maximum(taper, 0.0)

    # Smooth release: one-pole on the gain envelope (start from unity).
    alpha = 1.0 - np.exp(-1.0 / release)
    sm, _ = lfilter(
        [alpha],
        [1.0, -(1.0 - alpha)],
        gain,
        zi=np.array([1.0]),
    )
    gain = np.minimum(gain, sm)  # attack follows drops instantly, release eases

    gain2d = np.stack([gain, gain], axis=1)
    makeup = 10 ** (makeup_db / 20.0)
    return audio * gain2d * makeup


# ---------------------------------------------------------------------------
# True peak
# ---------------------------------------------------------------------------


def true_peak_db(audio: np.ndarray, sr: int) -> float:
    """True peak (dBTP) via 4x oversampling of both channels."""
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    up = resample_poly(audio, 4, 1, axis=0)
    peak = float(np.max(np.abs(up)))
    return 20 * np.log10(peak + 1e-12)


# ---------------------------------------------------------------------------
# Stereo width
# ---------------------------------------------------------------------------

_WIDTH_GAIN = {
    "mono": 0.0,
    "narrow": 0.5,
    "moderate": 1.2,
    "wide": 1.8,
    "very_wide": 2.5,
}


def apply_side_gain(audio: np.ndarray, gain: float) -> np.ndarray:
    """Scale only the side channel (mid/side widening/narrowing), g in [0, 3]."""
    gain = float(np.clip(gain, 0.0, 3.0))
    if abs(gain - 1.0) < 1e-9 or audio.ndim < 2:
        return audio
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5 * gain
    return np.stack([mid + side, mid - side], axis=1)


def apply_width(audio: np.ndarray, width: str) -> np.ndarray:
    """Rescale stereo width via mid/side: widen or narrow the side channel."""
    gain = _WIDTH_GAIN.get(width, 1.0)
    if abs(gain - 1.0) < 1e-9 or audio.ndim < 2:
        return audio
    return apply_side_gain(audio, gain)
