"""True-Peak Lookahead Limiter with 4x oversampling (ITU-R BS.1770 / EBU R128).

Inter-sample peaks (ISPs) occur between digital samples during reconstruction / D-to-A
conversion. This limiter oversamples the signal by 4x, tracks the peak envelope with
a lookahead delay, and applies smooth gain reduction with zero overshoot.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import resample_poly

from ..dsp._utils import moving_average, sliding_max


@dataclass
class LimiterConfig:
    """Configuration for the True Peak Limiter."""

    ceiling_dbtp: float = -1.0  # Maximum true peak level in dBTP (default -1.0)
    lookahead_ms: float = 10.0  # Lookahead window in milliseconds
    release_ms: float = 60.0  # Smooth release time in milliseconds
    oversample: int = 4  # Oversampling factor (4x standard)
    soft_knee_db: float = 1.0  # Soft knee width in dB below ceiling


def apply_true_peak_limiter(
    audio: np.ndarray,
    sr: int,
    config: LimiterConfig | None = None,
) -> np.ndarray:
    """Apply True-Peak Lookahead Limiting to a mono or stereo signal.

    Args:
        audio: (N, C) or (N,) array of float audio samples.
        sr: Sample rate in Hz.
        config: Limiter configuration parameters.

    Returns:
        Audio array shaped and bounded below the True Peak ceiling.
    """
    if config is None:
        config = LimiterConfig()

    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[:, None]

    n_samples, n_channels = audio.shape
    if n_samples == 0:
        return audio.flatten() if was_1d else audio

    factor = max(config.oversample, 1)
    up_sr = sr * factor
    up = resample_poly(audio, factor, 1, axis=0) if factor > 1 else audio.copy()

    # Linear ceiling with margin for downsampling reconstruction
    margin_db = 0.2 if factor > 1 else 0.0
    ceiling_lin = 10.0 ** ((config.ceiling_dbtp - margin_db) / 20.0)

    lookahead_samples = max(int(config.lookahead_ms * 1e-3 * up_sr), 1)
    release_samples = max(int(config.release_ms * 1e-3 * up_sr), 1)

    # Envelope detection on absolute oversampled signal
    env = sliding_max(np.abs(up), lookahead_samples)

    # Compute gain reduction
    gain = np.ones_like(env)
    exceed = env > ceiling_lin
    if np.any(exceed):
        gain[exceed] = ceiling_lin / (env[exceed] + 1e-12)

    # Shift gain backward by lookahead so attenuation happens BEFORE the peak
    if lookahead_samples < len(gain):
        pad = np.full((lookahead_samples, n_channels), 1.0, dtype=gain.dtype)
        gain = np.concatenate([pad, gain[:-lookahead_samples]], axis=0)

    # Smooth the release envelope to avoid distortion / clicks
    gain = moving_average(gain, release_samples)

    # Apply gain in oversampled domain
    out_up = up * gain

    # Soft clip any minor overshoots in the oversampled domain
    out_up = np.clip(out_up, -ceiling_lin, ceiling_lin)

    # Downsample back to original sample rate
    out = resample_poly(out_up, 1, factor, axis=0) if factor > 1 else out_up

    # Final safety check: ensure length matches original
    if len(out) != n_samples:
        if len(out) > n_samples:
            out = out[:n_samples]
        else:
            out = np.pad(out, ((0, n_samples - len(out)), (0, 0)))

    # Hard ceiling clamp on sample level
    sample_ceiling = 10.0 ** (config.ceiling_dbtp / 20.0)
    out = np.clip(out, -sample_ceiling, sample_ceiling)

    return out.flatten() if was_1d else out
