"""AI Reference Track Matcher DSP Module.

Extracts spectral envelope, dynamics, LUFS, and generates precision match EQ curves
to align current mix balance with any target commercial reference audio file.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import soundfile as sf


@dataclass
class ReferenceAnalysis:
    duration_s: float
    sample_rate: int
    lufs: float
    rms_db: float
    spectral_envelope: list[float]  # 32 standard 1/3-octave frequency bands (dB)
    freq_centers: list[float]
    crest_factor_db: float
    stereo_width: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# 32 Standard 1/3 Octave ISO Center Frequencies from 20 Hz to 20 kHz
ISO_CENTER_FREQS = [
    20.0,
    25.0,
    31.5,
    40.0,
    50.0,
    63.0,
    80.0,
    100.0,
    125.0,
    160.0,
    200.0,
    250.0,
    315.0,
    400.0,
    500.0,
    630.0,
    800.0,
    1000.0,
    1250.0,
    1600.0,
    2000.0,
    2500.0,
    3150.0,
    4000.0,
    5000.0,
    6300.0,
    8000.0,
    10000.0,
    12500.0,
    16000.0,
    20000.0,
]


def extract_spectral_envelope(
    audio: np.ndarray,
    sr: int,
    freq_centers: list[float] = ISO_CENTER_FREQS,
) -> list[float]:
    """Extract smoothed 1/3-octave spectral energy in dB across given center frequencies."""
    if audio.ndim > 1:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    if len(mono) < 1024:
        return [0.0] * len(freq_centers)

    # FFT with Hanning window
    n_fft = 4096
    hop = n_fft // 2
    n_frames = (len(mono) - n_fft) // hop
    if n_frames < 1:
        n_fft = 2048
        hop = 1024
        n_frames = max(1, (len(mono) - n_fft) // hop)

    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    power_spectrum = np.zeros(len(freqs), dtype=np.float64)

    count = 0
    for i in range(min(n_frames, 100)):
        idx = i * hop
        segment = mono[idx : idx + n_fft] * np.hanning(n_fft)
        fft_mag = np.abs(np.fft.rfft(segment))
        power_spectrum += fft_mag**2
        count += 1

    if count > 0:
        power_spectrum /= count

    # Bandpass integration around each 1/3 octave center frequency
    envelope_db: list[float] = []
    for fc in freq_centers:
        f_low = fc / (2 ** (1.0 / 6.0))
        f_high = fc * (2 ** (1.0 / 6.0))
        mask = (freqs >= f_low) & (freqs <= f_high)
        if np.any(mask):
            band_energy = float(np.sum(power_spectrum[mask]))
            band_db = 10.0 * math.log10(max(band_energy, 1e-12))
        else:
            band_db = -90.0
        envelope_db.append(round(band_db, 2))

    # Normalize relative to 1 kHz band (index 17 in ISO_CENTER_FREQS)
    ref_idx = min(17, len(envelope_db) - 1)
    ref_level = envelope_db[ref_idx]
    normalized_db = [round(x - ref_level, 2) for x in envelope_db]
    return normalized_db


def analyze_reference_audio(audio_path: str, max_duration: float = 60.0) -> ReferenceAnalysis:
    """Analyze audio file and return reference psychoacoustic metrics."""
    data, sr = sf.read(audio_path, dtype="float32")
    if len(data) > int(max_duration * sr):
        data = data[: int(max_duration * sr)]

    duration = len(data) / sr
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
        # Stereo width estimation (Side / Mid RMS ratio)
        mid = (data[:, 0] + data[:, 1]) * 0.5
        side = (data[:, 0] - data[:, 1]) * 0.5
        rms_mid = float(np.sqrt(np.mean(mid**2) + 1e-12))
        rms_side = float(np.sqrt(np.mean(side**2) + 1e-12))
        stereo_width = round(min(2.0, rms_side / max(rms_mid, 1e-6)), 3)
    else:
        mono = data
        stereo_width = 0.0

    rms = float(np.sqrt(np.mean(mono**2) + 1e-12))
    rms_db = round(20.0 * math.log10(max(rms, 1e-6)), 2)
    peak = float(np.max(np.abs(mono)))
    crest_factor = round(20.0 * math.log10(max(peak, 1e-6) / max(rms, 1e-6)), 2)

    # Simplified LUFS estimate (K-weight approximation)
    lufs = round(rms_db - 1.5, 1)

    envelope = extract_spectral_envelope(data, sr)

    return ReferenceAnalysis(
        duration_s=round(duration, 2),
        sample_rate=sr,
        lufs=lufs,
        rms_db=rms_db,
        spectral_envelope=envelope,
        freq_centers=ISO_CENTER_FREQS,
        crest_factor_db=crest_factor,
        stereo_width=stereo_width,
    )


def compute_match_eq_curve(
    current_envelope: list[float],
    target_envelope: list[float],
    strength: float = 0.8,
    max_boost_db: float = 6.0,
    max_cut_db: float = -9.0,
) -> list[dict[str, Any]]:
    """Compute parametric EQ bands to match current envelope to target envelope."""
    bands = []
    n = min(len(current_envelope), len(target_envelope), len(ISO_CENTER_FREQS))

    for i in range(n):
        diff = (target_envelope[i] - current_envelope[i]) * strength
        gain = float(np.clip(diff, max_cut_db, max_boost_db))
        if abs(gain) >= 0.5:
            bands.append(
                {
                    "frequency": ISO_CENTER_FREQS[i],
                    "gain_db": round(gain, 2),
                    "q": 1.4,
                    "type": "bell",
                }
            )

    return bands
