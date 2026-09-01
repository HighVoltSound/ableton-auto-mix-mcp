"""Configurable sidechain compression.

Gives the user full control: which track triggers, which targets are ducked,
amount, attack/release times, optional frequency band filter, and mix level.

The existing _sidechain_gain() in preview.py is a simple envelope follower.
This module builds on that idea but adds:
- Per-target amount overrides
- Frequency band filtering (duck only the bass region of a pad, for example)
- Mix (dry/wet) blend
- A clean envelope follower with adjustable attack/release
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass
class SidechainConfig:
    """Configuration for sidechain compression."""

    trigger: str = "kick"  # role that triggers the ducking
    targets: list[str] = field(default_factory=lambda: ["bass", "sub_bass", "wobble"])
    amount_db: float = -3.0  # how much to duck (negative = quieter)
    attack_ms: float = 5.0  # envelope attack time
    release_ms: float = 90.0  # envelope release time
    band_filter: tuple[float, float] | None = None  # freq range to duck (None = full band)
    mix: float = 1.0  # dry/wet (0 = no ducking, 1 = full sidechain)
    enabled: bool = True


def config_from_dict(d: dict[str, Any]) -> SidechainConfig:
    """Build SidechainConfig from an API dict, ignoring unknown keys."""
    band = d.get("band_filter")
    if isinstance(band, list | tuple) and len(band) == 2:
        band = (float(band[0]), float(band[1]))
    else:
        band = None
    return SidechainConfig(
        trigger=d.get("trigger", "kick"),
        targets=list(d.get("targets", ["bass", "sub_bass", "wobble"])),
        amount_db=float(d.get("amount_db", -3.0)),
        attack_ms=float(d.get("attack_ms", 5.0)),
        release_ms=float(d.get("release_ms", 90.0)),
        band_filter=band,
        mix=float(d.get("mix", 1.0)),
        enabled=bool(d.get("enabled", True)),
    )


def _envelope_follower(
    audio: np.ndarray,
    sr: int,
    attack_ms: float,
    release_ms: float,
) -> np.ndarray:
    """Compute a smooth amplitude envelope from a stereo signal.

    Returns a 1-D gain curve in 0..1 (1 = no gain change).
    """
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    abs_mono = np.abs(mono)

    attack_samp = max(int(attack_ms * sr / 1000), 1)
    release_samp = max(int(release_ms * sr / 1000), 1)

    envelope = np.zeros_like(abs_mono)
    env_val = 0.0
    for i in range(len(abs_mono)):
        if abs_mono[i] > env_val:
            coeff = 1.0 - np.exp(-1.0 / attack_samp)
        else:
            coeff = 1.0 - np.exp(-1.0 / release_samp)
        env_val += coeff * (abs_mono[i] - env_val)
        envelope[i] = env_val

    # Normalize envelope to 0..1
    peak = float(envelope.max()) + 1e-12
    return envelope / peak


def _bandpass_filter(
    audio: np.ndarray,
    sr: int,
    fmin: float,
    fmax: float,
) -> np.ndarray:
    """Apply a bandpass filter to extract a specific frequency region."""
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    nyq = sr * 0.49
    fmin_c = max(fmin, 1.0) / nyq
    fmax_c = min(fmax, nyq) / nyq
    if fmax_c <= fmin_c:
        return mono
    sos = butter(4, [fmin_c, fmax_c], btype="bandpass", output="sos")
    return sosfiltfilt(sos, mono)


def apply_sidechain(
    audio: np.ndarray,
    sr: int,
    trigger_audio: np.ndarray,
    config: SidechainConfig,
) -> np.ndarray:
    """Apply sidechain ducking to audio using trigger_audio.

    Args:
        audio: target audio (N, 2) to be ducked
        sr: sample rate
        trigger_audio: trigger signal (N, 2) — the kick/snare/etc
        config: sidechain parameters

    Returns:
        Duck-d audio (N, 2)
    """
    if not config.enabled or config.mix <= 0.0:
        return audio

    # Compute trigger envelope
    envelope = _envelope_follower(trigger_audio, sr, config.attack_ms, config.release_ms)

    # Convert amount_db to linear gain
    amount_linear = 10 ** (config.amount_db / 20.0)

    # Build gain curve: 1.0 = no duck, amount_linear = full duck
    gain_curve = 1.0 + (amount_linear - 1.0) * envelope

    # Apply band filter if specified (duck only a frequency band)
    if config.band_filter is not None:
        fmin, fmax = config.band_filter
        band_signal = _bandpass_filter(audio, sr, fmin, fmax)
        band_2d = np.stack([band_signal, band_signal], axis=1)
        rest = audio - band_2d

        # Duck the band only
        gain_2d = np.stack([gain_curve, gain_curve], axis=1)
        ducked_band = band_2d * gain_2d
        result = rest + ducked_band
    else:
        gain_2d = np.stack([gain_curve, gain_curve], axis=1)
        result = audio * gain_2d

    # Mix dry/wet
    if config.mix < 1.0:
        result = audio * (1.0 - config.mix) + result * config.mix

    return result
