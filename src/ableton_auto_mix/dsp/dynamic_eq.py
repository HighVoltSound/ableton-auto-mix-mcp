"""Dynamic EQ: per-band gain reduction that reacts to the signal level.

Unlike static EQ (constant gain), a dynamic EQ only kicks in when the band's
energy crosses a threshold — ideal for taming resonances, controlling mud,
or de-essing without permanently reshaping the tone.

Each band is isolated with a Linkwitz-Riley crossover, its envelope is tracked,
and a compressor-like gain curve is applied. The gain is then applied back to
the original signal (not the band split), preserving phase coherence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, sosfiltfilt

from ..dsp._utils import sliding_max


@dataclass
class DynamicBand:
    """One dynamic EQ band."""

    freq_lo: float = 100.0
    freq_hi: float = 2500.0
    threshold_db: float = -18.0
    ratio: float = 2.0  # >1 = compression, <1 = expansion
    attack_ms: float = 5.0
    release_ms: float = 100.0
    gain_db: float = 0.0  # static gain applied after dynamic action
    q: float = 1.0  # for the isolation filter
    enabled: bool = True
    mode: str = "compress"  # "compress" or "expand"


@dataclass
class DynamicEqConfig:
    """Full dynamic EQ configuration."""

    bands: list[DynamicBand] = field(default_factory=list)
    enabled: bool = True
    mix: float = 1.0


def _bandpass_isolate(audio: np.ndarray, sr: int, freq_lo: float, freq_hi: float, q: float = 1.0) -> np.ndarray:
    """Isolate a frequency band using a 4th-order Linkwitz-Riley bandpass.

    The bandpass = highpass at freq_lo − lowpass at freq_hi, each −24 dB/oct.
    """
    freq_lo = max(float(freq_lo), 1.0)
    freq_hi = min(float(freq_hi), sr * 0.49)
    if freq_lo >= freq_hi:
        return np.zeros_like(audio)

    # Highpass at freq_lo
    sos_hp = butter(2, freq_lo, btype="highpass", fs=sr, output="sos")
    hp = sosfiltfilt(sos_hp, audio, axis=0)
    # Lowpass at freq_hi
    sos_lp = butter(2, freq_hi, btype="lowpass", fs=sr, output="sos")
    return sosfiltfilt(sos_lp, hp, axis=0)


def _envelope_follower(audio: np.ndarray, sr: int, attack_ms: float, release_ms: float) -> np.ndarray:
    """RMS envelope follower with separate attack/release smoothing.

    Returns a per-sample envelope (always positive).
    """
    # RMS on stereo
    if audio.ndim > 1:
        mono = np.sqrt(np.mean(audio**2, axis=1))
    else:
        mono = np.abs(audio)

    attack = max(int(attack_ms / 1000.0 * sr), 1)
    release = max(int(release_ms / 1000.0 * sr), 1)

    # Attack: sliding max
    env = sliding_max(mono, attack)
    # Release: one-pole smoothing
    alpha = 1.0 - np.exp(-1.0 / release)
    env_smooth, _ = __import__("scipy.signal", fromlist=["lfilter"]).lfilter(
        [alpha],
        [1.0, -(1.0 - alpha)],
        env,
        zi=np.array([1.0]),
    )
    return np.maximum(env, env_smooth)


def apply_dynamic_eq(audio: np.ndarray, sr: int, config: DynamicEqConfig) -> np.ndarray:
    """Apply dynamic EQ to a stereo signal.

    For each band:
    1. Isolate the band
    2. Track its envelope
    3. Compute gain reduction/expansion
    4. Apply the gain to the full signal (not the band)
    """
    if not config.enabled or not config.bands or config.mix <= 0.0:
        return audio

    gain_curve = np.ones(audio.shape[0], dtype=np.float64)

    for band in config.bands:
        if not band.enabled:
            continue
        if band.freq_lo >= band.freq_hi:
            continue

        # Isolate band and track envelope
        isolated = _bandpass_isolate(audio, sr, band.freq_lo, band.freq_hi)
        env = _envelope_follower(isolated, sr, band.attack_ms, band.release_ms)

        # Compute dynamic gain
        threshold = 10 ** (band.threshold_db / 20.0)
        ratio = max(float(band.ratio), 0.01)

        if band.mode == "compress":
            # Above threshold: reduce gain
            over = np.maximum(env / (threshold + 1e-12), 1.0)
            dynamic_gain = np.power(over, (1.0 / ratio - 1.0))
            dynamic_gain = np.minimum(dynamic_gain, 1.0)
        else:
            # Expansion: below threshold reduce, above boost
            under = np.minimum(env / (threshold + 1e-12), 1.0)
            dynamic_gain = np.power(under + 1e-12, (ratio - 1.0))
            dynamic_gain = np.maximum(dynamic_gain, 0.0)

        # Apply static gain on top
        static_gain = 10 ** (band.gain_db / 20.0)
        band_gain = dynamic_gain * static_gain

        gain_curve *= band_gain

    # Apply combined gain curve to stereo
    gain_2d = np.stack([gain_curve, gain_curve], axis=1)
    wet = audio * gain_2d

    # Dry/wet mix
    return (1.0 - config.mix) * audio + config.mix * wet


def config_from_dict(d: dict) -> DynamicEqConfig:
    """Build a DynamicEqConfig from an API-style dict."""
    bands = []
    for b in d.get("bands", []):
        bands.append(
            DynamicBand(
                freq_lo=float(b.get("freq_lo", 100)),
                freq_hi=float(b.get("freq_hi", 2500)),
                threshold_db=float(b.get("threshold_db", -18)),
                ratio=float(b.get("ratio", 2)),
                attack_ms=float(b.get("attack_ms", 5)),
                release_ms=float(b.get("release_ms", 100)),
                gain_db=float(b.get("gain_db", 0)),
                q=float(b.get("q", 1)),
                enabled=bool(b.get("enabled", True)),
                mode=str(b.get("mode", "compress")),
            )
        )
    return DynamicEqConfig(
        bands=bands,
        enabled=bool(d.get("enabled", True)),
        mix=float(d.get("mix", 1.0)),
    )
