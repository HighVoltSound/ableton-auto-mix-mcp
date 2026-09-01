"""Tests for Binaural 3D Head Spatializer and HRTF Psychoacoustic Modeling."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator

import numpy as np
import pytest
import soundfile as sf

from ableton_auto_mix import preview, profiles, server
from ableton_auto_mix.dsp.spatializer import (
    SpatializerConfig,
    apply_binaural_spatializer,
)

SR = 44100
DUR = 3.5


def _tone(freq: float, dur: float = DUR) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


@pytest.fixture
def test_render_dir() -> Generator[str, None, None]:
    tmp = tempfile.mkdtemp(prefix="spatial_test_")
    # kick
    kick = (_tone(60) * 0.8).reshape(-1, 1)
    kick = np.repeat(kick, 2, axis=1)
    sf.write(os.path.join(tmp, "kick.wav"), kick, SR, subtype="PCM_16")

    # vocal/lead
    vocal = (_tone(440) * 0.6).reshape(-1, 1)
    vocal = np.repeat(vocal, 2, axis=1)
    sf.write(os.path.join(tmp, "vocal.wav"), vocal, SR, subtype="PCM_16")

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_spatializer_itd_delay_right() -> None:
    # Single impulse at sample index 100
    impulse = np.zeros(2000, dtype=np.float32)
    impulse[100] = 1.0

    # Sound positioned to the right (azimuth = +60 deg)
    cfg = SpatializerConfig(enabled=True, head_position=0.66, azimuth_deg=60.0, mix=1.0)
    out = apply_binaural_spatializer(impulse, SR, cfg)

    assert out.shape == (2000, 2)
    # Right channel should lead (peak earlier), Left channel should lag (delayed by ITD)
    peak_r_idx = int(np.argmax(np.abs(out[:, 1])))
    peak_l_idx = int(np.argmax(np.abs(out[:, 0])))
    assert peak_l_idx >= peak_r_idx


def test_spatializer_occiput_vs_front_spectral_filter() -> None:
    # High-frequency content at 8000 Hz
    high_tone = _tone(8000.0, dur=1.0)

    # Position at Occiput (затылок, pos = 0.1)
    cfg_back = SpatializerConfig(enabled=True, head_position=0.1, azimuth_deg=0.0, distance_m=1.0, mix=1.0)
    out_back = apply_binaural_spatializer(high_tone, SR, cfg_back)

    # Position at Front (перед лицом, pos = 0.9)
    cfg_front = SpatializerConfig(enabled=True, head_position=0.9, azimuth_deg=0.0, distance_m=1.0, mix=1.0)
    out_front = apply_binaural_spatializer(high_tone, SR, cfg_front)

    rms_back = float(np.sqrt(np.mean(out_back**2)))
    rms_front = float(np.sqrt(np.mean(out_front**2)))

    # Sound from the back (occiput/neck) must have significantly shadowed high-frequencies compared to front
    assert rms_back < rms_front * 0.85


def test_preview_render_with_spatial_configs(test_render_dir: str) -> None:
    profile = profiles.get_profile("pop")
    out_wav = os.path.join(test_render_dir, "preview_spatial.wav")

    spatial_configs = {
        "vocal": {
            "enabled": True,
            "head_position": 0.25,  # Occiput (Behind head)
            "azimuth_deg": -30.0,
            "elevation_deg": -10.0,
            "distance_m": 1.2,
            "mix": 1.0,
        }
    }

    res = preview.render_preview_mix(
        render_dir=test_render_dir,
        profile=profile,
        output_path=out_wav,
        max_duration=3.0,
        spatial_configs=spatial_configs,
    )

    assert os.path.exists(res["output_path"])
    assert res["true_peak_dbtp"] <= 0.0


def test_server_preview_mix_spatial(test_render_dir: str) -> None:
    res = server.preview_mix(
        style="pop",
        render_dir=test_render_dir,
        max_duration=3.0,
        spatial_configs={"vocal": {"head_position": 0.3, "azimuth_deg": 45.0}},
    )
    assert os.path.exists(res["output_path"])
