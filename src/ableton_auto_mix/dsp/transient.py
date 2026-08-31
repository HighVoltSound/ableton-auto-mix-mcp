"""Transient shaper: separate attack and sustain portions of a signal
and apply independent gain to each.

Unlike a compressor (which reacts to level), a transient shaper detects
the onset of a sound (attack) and boosts or cuts it relative to the body
(sustain). Perfect for adding snap to drums, tightening bass, or softening
harsh transients.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

from ..dsp._utils import sliding_max


@dataclass
class TransientConfig:
    """Transient shaper configuration."""

    attack_db: float = 0.0  # boost (+) or cut (−) attack, ±12 dB
    sustain_db: float = 0.0  # boost (+) or cut (−) sustain, ±12 dB
    sensitivity: float = 0.5  # how easily transients are detected, 0..1
    frequency_hz: float = 0.0  # 0 = full-range, >0 = only shape this band
    mix: float = 1.0
    enabled: bool = True


def _detect_transients(
    audio: np.ndarray, sr: int, sensitivity: float
) -> tuple[np.ndarray, np.ndarray]:
    """Detect transient (attack) and sustain portions of the signal.

    Returns (attack_env, sustain_env), each the same length as the audio,
    where attack + sustain ≈ 1.0 (complementary envelopes).

    Detection uses the derivative of the envelope: fast rises = transients.
    """
    if audio.ndim > 1:
        mono = np.sqrt(np.mean(audio**2, axis=1))
    else:
        mono = np.abs(audio)

    # Smooth envelope (short window)
    win = max(int(0.002 * sr), 1)  # 2 ms
    env = sliding_max(mono, win)

    # Derivative of envelope (onset detector)
    diff = np.diff(env, prepend=env[0])

    # Positive derivative = attack, negative = decay/sustain
    sensitivity = float(np.clip(sensitivity, 0.01, 1.0))
    threshold = float(np.percentile(np.maximum(diff, 0), 100 * (1.0 - sensitivity)))

    # Attack envelope: where derivative is above threshold
    attack_raw = np.clip((diff - threshold) / (threshold + 1e-12), 0.0, 1.0)

    # Smooth the attack envelope (fast attack, slow release)
    atk_samples = max(int(0.001 * sr), 1)  # 1 ms attack
    rel_samples = max(int(0.05 * sr), 1)  # 50 ms release

    # Sliding max for attack, one-pole for release
    attack = sliding_max(attack_raw, atk_samples)
    alpha = 1.0 - np.exp(-1.0 / rel_samples)
    attack_smooth = np.zeros_like(attack)
    for i in range(1, len(attack)):
        attack_smooth[i] = max(attack[i], alpha * attack_smooth[i - 1])

    # Sustain is the complement
    sustain = 1.0 - attack_smooth

    return attack_smooth, sustain


def apply_transient_shaper(
    audio: np.ndarray, sr: int, config: TransientConfig
) -> np.ndarray:
    """Apply transient shaping to a stereo signal.

    1. Detect transients (attack/sustain envelopes)
    2. Apply attack_db gain to the attack portion
    3. Apply sustain_db gain to the sustain portion
    4. Mix dry/wet
    """
    if not config.enabled:
        return audio

    atk_gain = config.attack_db
    sus_gain = config.sustain_db

    if abs(atk_gain) < 0.1 and abs(sus_gain) < 0.1:
        return audio

    # Optional band-limited detection
    work = audio
    if config.frequency_hz > 0:
        freq = float(np.clip(config.frequency_hz, 20.0, sr * 0.49))
        sos = butter(2, freq, btype="lowpass", fs=sr, output="sos")
        work = sosfiltfilt(sos, audio, axis=0)

    attack_env, sustain_env = _detect_transients(work, sr, config.sensitivity)

    # Gain curves
    atk_gain_linear = 10 ** (atk_gain / 20.0)
    sus_gain_linear = 10 ** (sus_gain / 20.0)

    # Per-sample gain: attack_env portion gets atk_gain, sustain gets sus_gain
    gain = np.ones(audio.shape[0], dtype=np.float64)
    gain = gain + attack_env * (atk_gain_linear - 1.0)
    gain = gain + sustain_env * (sus_gain_linear - 1.0)

    gain_2d = np.stack([gain, gain], axis=1)
    wet = audio * gain_2d

    if config.mix >= 1.0:
        return wet
    return (1.0 - config.mix) * audio + config.mix * wet


def config_from_dict(d: dict) -> TransientConfig:
    """Build a TransientConfig from an API-style dict."""
    return TransientConfig(
        attack_db=float(d.get("attack_db", 0)),
        sustain_db=float(d.get("sustain_db", 0)),
        sensitivity=float(d.get("sensitivity", 0.5)),
        frequency_hz=float(d.get("frequency_hz", 0)),
        mix=float(d.get("mix", 1.0)),
        enabled=bool(d.get("enabled", True)),
    )
