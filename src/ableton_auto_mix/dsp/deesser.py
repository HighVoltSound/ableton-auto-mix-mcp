"""De-Esser DSP module for vocal sibilance control and harsh high-frequency management.

Detects excess energy in the sibilant frequency range (typically 4.5 kHz – 9.0 kHz)
and applies targeted dynamic gain reduction in either 'split' (dynamic high-band notch/shelf)
or 'wide' (wideband attenuation) mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy.signal import butter, sosfiltfilt

from ..dsp._utils import moving_average, sliding_max


@dataclass
class DeEsserConfig:
    """Configuration for De-Esser."""

    frequency_hz: float = 6500.0  # Center sibilant frequency (Hz)
    threshold_db: float = -20.0  # Detection threshold (dB)
    ratio: float = 4.0  # Compression ratio above threshold
    max_reduction_db: float = 12.0  # Maximum gain reduction cap (dB)
    attack_ms: float = 1.0  # Attack time (ms)
    release_ms: float = 45.0  # Release time (ms)
    mode: Literal["split", "wide"] = "split"  # 'split' = reduce sibilants only; 'wide' = broadband
    enabled: bool = True
    mix: float = 1.0  # Dry/wet mix (0.0 to 1.0)


def apply_deesser(
    audio: np.ndarray,
    sr: int,
    config: DeEsserConfig | None = None,
) -> np.ndarray:
    """Apply De-Essing to audio signal.

    Args:
        audio: (N, C) or (N,) array of float audio samples.
        sr: Sample rate in Hz.
        config: De-Esser settings.

    Returns:
        De-essed audio array.
    """
    if config is None:
        config = DeEsserConfig()

    if not config.enabled or config.mix <= 0.0:
        return audio

    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[:, None]

    n_samples, n_channels = audio.shape
    if n_samples == 0:
        return audio.flatten() if was_1d else audio

    f_center = float(np.clip(config.frequency_hz, 2000.0, sr * 0.45))
    nyquist = sr * 0.5

    # Design bandpass filter for sidechain detection (Q ~ 1.5 octave band)
    f_lo = max(20.0, f_center * 0.7)
    f_hi = min(nyquist * 0.95, f_center * 1.4)
    if f_lo >= f_hi:
        f_hi = min(nyquist * 0.95, f_lo + 500.0)

    sos_detector = butter(2, [f_lo / nyquist, f_hi / nyquist], btype="bandpass", output="sos")
    detected_band = sosfiltfilt(sos_detector, audio, axis=0)

    # Envelope follower on the filtered detection signal
    attack_samples = max(int(config.attack_ms * 1e-3 * sr), 1)
    release_samples = max(int(config.release_ms * 1e-3 * sr), 1)

    env = sliding_max(np.abs(detected_band), attack_samples)
    env_smoothed = moving_average(env, release_samples)

    # Convert envelope to dB
    env_db = 20.0 * np.log10(np.maximum(env_smoothed, 1e-6))

    # Calculate gain reduction in dB
    thresh = config.threshold_db
    over_thresh = np.maximum(env_db - thresh, 0.0)
    reduction_db = over_thresh * (1.0 - 1.0 / max(config.ratio, 1.0))
    reduction_db = np.minimum(reduction_db, config.max_reduction_db)

    # Convert to linear gain factor (0.0 .. 1.0)
    gain = 10.0 ** (-reduction_db / 20.0)

    if config.mode == "split":
        # Split-band mode: isolate high-frequency band, apply gain reduction to it, sum back
        sos_split = butter(2, f_lo / nyquist, btype="highpass", output="sos")
        highs = sosfiltfilt(sos_split, audio, axis=0)
        lows = audio - highs
        processed = lows + highs * gain
    else:
        # Wideband mode: apply gain reduction to the full signal
        processed = audio * gain

    # Dry/wet blend
    if config.mix < 1.0:
        processed = (1.0 - config.mix) * audio + config.mix * processed

    return processed.flatten() if was_1d else processed


def config_from_dict(d: dict) -> DeEsserConfig:
    """Construct a DeEsserConfig from a dictionary."""
    return DeEsserConfig(
        frequency_hz=float(d.get("frequency_hz", 6500.0)),
        threshold_db=float(d.get("threshold_db", -20.0)),
        ratio=float(d.get("ratio", 4.0)),
        max_reduction_db=float(d.get("max_reduction_db", 12.0)),
        attack_ms=float(d.get("attack_ms", 1.0)),
        release_ms=float(d.get("release_ms", 45.0)),
        mode=str(d.get("mode", "split")),  # type: ignore
        enabled=bool(d.get("enabled", True)),
        mix=float(d.get("mix", 1.0)),
    )
