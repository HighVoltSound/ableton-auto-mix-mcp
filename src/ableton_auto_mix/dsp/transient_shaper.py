"""Dynamic Transient Shaper DSP Module.

Allows independent shaping of initial transient attack punch (attack_db)
and body/resonance sustain (sustain_db) on per-track or bus channels.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass
class TransientConfig:
    enabled: bool = True
    attack_db: float = 0.0  # -12.0 dB (smooth/soft) to +12.0 dB (snappy punch)
    sustain_db: float = 0.0  # -12.0 dB (tight gating) to +12.0 dB (dense body/tail)
    mix: float = 1.0  # 0.0 (Dry) to 1.0 (Wet)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_transient_shaper(
    audio: np.ndarray,
    sr: int,
    config: TransientConfig | None = None,
) -> np.ndarray:
    """Apply dynamic transient shaping to mono or stereo audio."""
    if config is None or not config.enabled:
        return audio

    if abs(config.attack_db) < 0.05 and abs(config.sustain_db) < 0.05:
        return audio

    input_arr = np.asarray(audio, dtype=np.float32)

    # Envelope detector coefficients
    # Fast attack (~2 ms), Slow sustain (~50 ms), Release (~80 ms)
    alpha_fast = math.exp(-1.0 / (0.002 * sr))
    alpha_slow = math.exp(-1.0 / (0.050 * sr))
    alpha_rel = math.exp(-1.0 / (0.080 * sr))

    if input_arr.ndim == 1:
        channels = [input_arr]
    else:
        channels = [input_arr[:, ch] for ch in range(input_arr.shape[1])]

    processed_channels = []

    attack_gain_linear = 10.0 ** (config.attack_db / 20.0)
    sustain_gain_linear = 10.0 ** (config.sustain_db / 20.0)

    for ch_data in channels:
        abs_sig = np.abs(ch_data)
        env_fast = np.zeros_like(abs_sig)
        env_slow = np.zeros_like(abs_sig)

        curr_fast = 0.0
        curr_slow = 0.0

        for i, val in enumerate(abs_sig):
            # Fast envelope
            if val > curr_fast:
                curr_fast = (1.0 - alpha_fast) * val + alpha_fast * curr_fast
            else:
                curr_fast = alpha_rel * curr_fast
            env_fast[i] = curr_fast

            # Slow envelope
            if val > curr_slow:
                curr_slow = (1.0 - alpha_slow) * val + alpha_slow * curr_slow
            else:
                curr_slow = alpha_rel * curr_slow
            env_slow[i] = curr_slow

        # Transient ratio: fast - slow
        transient_signal = np.maximum(0.0, env_fast - env_slow)
        sustain_signal = env_slow

        # Normalize envelope weights
        total_env = transient_signal + sustain_signal + 1e-6
        w_transient = transient_signal / total_env
        w_sustain = sustain_signal / total_env

        gain_curve = (w_transient * attack_gain_linear) + (w_sustain * sustain_gain_linear)
        shaped = ch_data * gain_curve

        # Dry / Wet mix
        wet = (1.0 - config.mix) * ch_data + config.mix * shaped
        processed_channels.append(wet)

    if input_arr.ndim == 1:
        out = processed_channels[0]
    else:
        out = np.column_stack(processed_channels)

    return out.astype(np.float32)
