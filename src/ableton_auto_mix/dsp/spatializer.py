"""Binaural 3D Head Spatializer and HRTF Psychoacoustic Modeling (Version 2.5).

Simulates sound positioning relative to the human head, neck, occiput (затылок),
ear, face, and Crown/Overhead 3D Dome (над головой / купол) with:
1. ITD (Interaural Time Difference) via Woodworth-Schlosser spherical head model.
2. ILD (Interaural Level Difference) and head-shadow filtering.
3. Occiput / Neck / Pinna & Crown Overhead spectral shaping (+90° Zenith).
4. Mono-Maker (preserves sub-bass < 120 Hz dead-center mono).
5. Room Acoustic Simulator (Early reflections for Vocal Booth, Studio, Club, Cathedral).
6. Full Instrument Presets (Kick, Snare, Hi-Hats, Bass, Lead Vocal, Sky Pads, FX, Backing Vocals).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal


@dataclass
class SpatializerConfig:
    enabled: bool = True
    # 0.0 = Neck, 0.25 = Occiput, 0.50 = Ear, 0.75 = Face, 1.0 = Crown/Overhead (над головой)
    head_position: float = 0.50
    azimuth_deg: float = 30.0  # -90 (full left) to +90 (full right)
    elevation_deg: float = 0.0  # -45 (down at neck) to +90 (straight above head / zenith)
    distance_m: float = 1.0  # 0.3m to 3.0m
    mix: float = 1.0  # 0.0 (dry) to 1.0 (wet)
    bass_mono: bool = True  # Keep sub-bass < 120Hz centered mono
    room_model: str = "none"  # "none", "vocal_booth", "studio", "club", "cathedral"
    room_amount: float = 0.25  # 0.0 to 1.0


def config_from_dict(d: dict[str, Any]) -> SpatializerConfig:
    return SpatializerConfig(
        enabled=bool(d.get("enabled", True)),
        head_position=float(d.get("head_position", 0.50)),
        azimuth_deg=float(d.get("azimuth_deg", 30.0)),
        elevation_deg=float(d.get("elevation_deg", 0.0)),
        distance_m=float(d.get("distance_m", 1.0)),
        mix=float(d.get("mix", 1.0)),
        bass_mono=bool(d.get("bass_mono", True)),
        room_model=str(d.get("room_model", "none")),
        room_amount=float(d.get("room_amount", 0.25)),
    )


def _fractional_delay(audio: np.ndarray, delay_samples: float) -> np.ndarray:
    """Apply sub-sample fractional delay using linear interpolation."""
    if abs(delay_samples) < 1e-4:
        return audio.copy()

    int_delay = int(np.floor(delay_samples))
    frac_delay = delay_samples - int_delay
    n = len(audio)

    delayed = np.zeros_like(audio)
    if int_delay < n:
        if frac_delay < 1e-4:
            delayed[int_delay:] = audio[: n - int_delay]
        else:
            s1 = np.zeros_like(audio)
            s2 = np.zeros_like(audio)
            s1[int_delay:] = audio[: n - int_delay]
            if int_delay + 1 < n:
                s2[int_delay + 1 :] = audio[: n - int_delay - 1]
            delayed = (1.0 - frac_delay) * s1 + frac_delay * s2

    return delayed


def _apply_room_reflections(
    left: np.ndarray,
    right: np.ndarray,
    sr: int,
    model: str,
    amount: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate early room reflections and spatial diffusion."""
    if model == "none" or amount <= 0.01:
        return left, right

    presets = {
        "vocal_booth": [(8.0, 0.25, -1), (14.0, 0.18, 1), (22.0, 0.10, -1)],
        "studio": [
            (18.0, 0.35, 1),
            (28.0, 0.25, -1),
            (42.0, 0.18, 1),
            (60.0, 0.12, -1),
        ],
        "club": [(35.0, 0.45, -1), (65.0, 0.35, 1), (95.0, 0.25, -1), (140.0, 0.18, 1)],
        "cathedral": [
            (60.0, 0.50, 1),
            (110.0, 0.42, -1),
            (170.0, 0.35, 1),
            (240.0, 0.25, -1),
        ],
    }

    reflections = presets.get(model, presets["studio"])
    refl_l = np.zeros_like(left)
    refl_r = np.zeros_like(right)

    mono = (left + right) * 0.5
    for delay_ms, gain, polarity in reflections:
        d_samples = (delay_ms / 1000.0) * sr
        delayed = _fractional_delay(mono, d_samples) * (gain * amount)
        if polarity < 0:
            refl_l += delayed * 0.8
            refl_r -= delayed * 0.8
        else:
            refl_l += delayed
            refl_r += delayed

    # Dampen high frequencies of room reflections
    sos_lp = signal.butter(1, 4500.0, btype="lowpass", fs=sr, output="sos")
    refl_l = signal.sosfilt(sos_lp, refl_l)
    refl_r = signal.sosfilt(sos_lp, refl_r)

    return left + refl_l, right + refl_r


def apply_binaural_spatializer(
    audio: np.ndarray,
    sr: int,
    config: SpatializerConfig | None = None,
) -> np.ndarray:
    """Process stereo or mono audio with 3D Head HRTF & Overhead Space 2.5."""
    if config is None or not config.enabled:
        if audio.ndim == 1:
            return np.column_stack((audio, audio))
        return audio

    if audio.ndim == 1:
        dry = np.column_stack((audio, audio))
    else:
        dry = audio.copy()

    mono_source = np.mean(dry, axis=1)

    # 0. Mono-Maker Sub-Bass Split (< 120 Hz)
    if config.bass_mono and sr > 1000:
        sos_sub_lp = signal.butter(2, 120.0, btype="lowpass", fs=sr, output="sos")
        sos_sub_hp = signal.butter(2, 120.0, btype="highpass", fs=sr, output="sos")
        sub_mono = signal.sosfilt(sos_sub_lp, mono_source)
        spatial_source = signal.sosfilt(sos_sub_hp, mono_source)
    else:
        sub_mono = np.zeros_like(mono_source)
        spatial_source = mono_source

    # 1. Woodworth-Schlosser ITD calculation
    r_head = 0.0875
    c_sound = 343.0
    azimuth_clamped = np.clip(config.azimuth_deg, -90.0, 90.0)
    theta_rad = np.radians(abs(azimuth_clamped))

    # ITD decreases as elevation approaches zenith (+90° overhead)
    elev_deg = np.clip(config.elevation_deg, -45.0, 90.0)
    elev_factor = max(0.0, np.cos(np.radians(max(0.0, elev_deg))))

    itd_sec = (r_head / c_sound) * (theta_rad + np.sin(theta_rad)) * elev_factor
    itd_samples = itd_sec * sr

    if azimuth_clamped > 0:
        delay_left = itd_samples
        delay_right = 0.0
    else:
        delay_left = 0.0
        delay_right = itd_samples

    out_l = _fractional_delay(spatial_source, delay_left)
    out_r = _fractional_delay(spatial_source, delay_right)

    # 2. Contralateral Head-Shadow Filter (ILD)
    shadow_amount = np.sin(theta_rad) * elev_factor
    if shadow_amount > 0.05:
        cutoff = max(800.0, 4500.0 - shadow_amount * 2500.0)
        sos_shadow = signal.butter(1, cutoff, btype="lowpass", fs=sr, output="sos")
        if azimuth_clamped > 0:
            shadowed = signal.sosfilt(sos_shadow, out_l)
            out_l = (1.0 - shadow_amount * 0.5) * out_l + (shadow_amount * 0.5) * shadowed
            out_l *= 1.0 - shadow_amount * 0.35
        else:
            shadowed = signal.sosfilt(sos_shadow, out_r)
            out_r = (1.0 - shadow_amount * 0.5) * out_r + (shadow_amount * 0.5) * shadowed
            out_r *= 1.0 - shadow_amount * 0.35

    # 3. Occiput / Neck / Crown Spectral Shaping
    pos = np.clip(config.head_position, 0.0, 1.0)
    if pos < 0.40:
        # Neck / Occiput back sound
        back_factor = (0.40 - pos) / 0.40
        cutoff_back = max(3500.0, 8000.0 - back_factor * 4500.0)
        if cutoff_back < (sr * 0.45):
            sos_back_lp = signal.butter(1, cutoff_back, btype="lowpass", fs=sr, output="sos")
            out_l = (1.0 - back_factor * 0.6) * out_l + (back_factor * 0.6) * signal.sosfilt(sos_back_lp, out_l)
            out_r = (1.0 - back_factor * 0.6) * out_r + (back_factor * 0.6) * signal.sosfilt(sos_back_lp, out_r)

        # Pinna & Occiput Notch (~7200 Hz)
        notch_freq = 7200.0 - back_factor * 1200.0
        b_notch, a_notch = signal.iirnotch(notch_freq, 3.0, fs=sr)
        notch_l = signal.lfilter(b_notch, a_notch, out_l)
        notch_r = signal.lfilter(b_notch, a_notch, out_r)
        out_l = (1.0 - back_factor * 0.55) * out_l + (back_factor * 0.55) * notch_l
        out_r = (1.0 - back_factor * 0.55) * out_r + (back_factor * 0.55) * notch_r

        # Body resonance peak (1300 Hz)
        b_peak, a_peak = signal.iirpeak(1300.0, 2.0, fs=sr)
        out_l += (back_factor * 0.25) * signal.lfilter(b_peak, a_peak, out_l)
        out_r += (back_factor * 0.25) * signal.lfilter(b_peak, a_peak, out_r)

    elif pos > 0.80:
        # Crown / Overhead Sky Dome (Над головой)
        crown_factor = (pos - 0.80) / 0.20
        # Air & Top-elevation boost (9 kHz & 12 kHz)
        b_top, a_top = signal.iirpeak(9200.0, 1.5, fs=sr)
        out_l += (crown_factor * 0.3) * signal.lfilter(b_top, a_top, out_l)
        out_r += (crown_factor * 0.3) * signal.lfilter(b_top, a_top, out_r)

    # 4. Elevation (Высота над головой: -45° to +90° Zenith)
    if elev_deg > 5.0:
        # Higher elevation = "Air / Sky" high frequency boost + vertical pinna notches
        top_norm = min(1.0, elev_deg / 90.0)
        b_air, a_air = signal.iirpeak(8500.0 + top_norm * 2500.0, 1.8, fs=sr)
        out_l += (top_norm * 0.25) * signal.lfilter(b_air, a_air, out_l)
        out_r += (top_norm * 0.25) * signal.lfilter(b_air, a_air, out_r)
    elif elev_deg < -5.0:
        # Below neck = low body resonance
        low_norm = abs(elev_deg) / 45.0
        b_low, a_low = signal.iirpeak(650.0, 1.5, fs=sr)
        out_l += (low_norm * 0.2) * signal.lfilter(b_low, a_low, out_l)
        out_r += (low_norm * 0.2) * signal.lfilter(b_low, a_low, out_r)

    # 5. Distance attenuation
    dist = max(0.3, config.distance_m)
    dist_atten = 1.0 / np.sqrt(dist)
    out_l *= dist_atten
    out_r *= dist_atten

    # 6. Room Acoustics (Early Reflections)
    out_l, out_r = _apply_room_reflections(out_l, out_r, sr, config.room_model, config.room_amount)

    # Recombine sub-bass mono
    if config.bass_mono:
        out_l += sub_mono
        out_r += sub_mono

    wet = np.column_stack((out_l, out_r)).astype(np.float32)
    mix = float(np.clip(config.mix, 0.0, 1.0))
    result = (1.0 - mix) * dry + mix * wet
    return result.astype(np.float32)
