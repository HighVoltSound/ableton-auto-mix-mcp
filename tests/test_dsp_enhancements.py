"""Tests for True Peak Limiter, De-Esser, and Interactive Master EQ."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator

import numpy as np
import pytest
import soundfile as sf

from ableton_auto_mix import preview, profiles, server
from ableton_auto_mix.dsp.deesser import DeEsserConfig, apply_deesser
from ableton_auto_mix.dsp.limiter import LimiterConfig, apply_true_peak_limiter

SR = 44100
DUR = 3.5


def _tone(freq: float, dur: float = DUR) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


@pytest.fixture
def test_render_dir() -> Generator[str, None, None]:
    tmp = tempfile.mkdtemp(prefix="dsp_enhancements_test_")
    # kick
    kick = (_tone(60) * 0.9).reshape(-1, 1)
    kick = np.repeat(kick, 2, axis=1)
    sf.write(os.path.join(tmp, "kick.wav"), kick, SR, subtype="PCM_16")

    # vocal with harsh sibilance (high-frequency tone at 6500 Hz + noise)
    rng = np.random.default_rng(123)
    vocal = (_tone(440) * 0.4 + _tone(6500) * 0.5 + rng.uniform(-0.1, 0.1, int(SR * DUR))).reshape(-1, 1)
    vocal = np.repeat(vocal, 2, axis=1)
    sf.write(os.path.join(tmp, "vocal.wav"), vocal, SR, subtype="PCM_16")

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_true_peak_limiter_basic() -> None:
    # Generate hot signal with peaks above 0 dB
    audio = _tone(100, dur=1.0).reshape(-1, 1) * 2.0
    audio = np.repeat(audio, 2, axis=1)

    cfg = LimiterConfig(ceiling_dbtp=-1.0, lookahead_ms=10.0, release_ms=50.0, oversample=4)
    limited = apply_true_peak_limiter(audio, SR, cfg)

    assert limited.shape == audio.shape
    max_peak = float(np.max(np.abs(limited)))
    expected_max = 10.0 ** (-1.0 / 20.0) + 1e-4
    assert max_peak <= expected_max


def test_deesser_split_mode() -> None:
    # 6.5 kHz harsh tone
    sibilant = _tone(6500, dur=1.0).reshape(-1, 1) * 0.8
    sibilant = np.repeat(sibilant, 2, axis=1)

    cfg = DeEsserConfig(
        frequency_hz=6500.0,
        threshold_db=-25.0,
        ratio=4.0,
        max_reduction_db=12.0,
        mode="split",
    )
    deessed = apply_deesser(sibilant, SR, cfg)

    rms_before = float(np.sqrt(np.mean(sibilant**2)))
    rms_after = float(np.sqrt(np.mean(deessed**2)))

    # De-esser should significantly reduce the sibilant energy
    assert rms_after < rms_before * 0.7


def test_deesser_wide_mode() -> None:
    sibilant = _tone(6500, dur=1.0).reshape(-1, 1) * 0.8
    sibilant = np.repeat(sibilant, 2, axis=1)

    cfg = DeEsserConfig(
        frequency_hz=6500.0,
        threshold_db=-25.0,
        ratio=4.0,
        max_reduction_db=12.0,
        mode="wide",
    )
    deessed = apply_deesser(sibilant, SR, cfg)

    assert deessed.shape == sibilant.shape
    rms_before = float(np.sqrt(np.mean(sibilant**2)))
    rms_after = float(np.sqrt(np.mean(deessed**2)))
    assert rms_after < rms_before


def test_preview_with_eq_bands_and_deesser(test_render_dir: str) -> None:
    profile = profiles.get_profile("techno")
    out_wav = os.path.join(test_render_dir, "preview_dsp.wav")

    eq_bands = [
        {
            "id": 1,
            "type": "bell",
            "freq": 1000,
            "gain": -3.0,
            "q": 1.0,
            "enabled": True,
        },
        {
            "id": 2,
            "type": "high_shelf",
            "freq": 8000,
            "gain": 2.0,
            "q": 0.7,
            "enabled": True,
        },
    ]
    deesser_cfg = {
        "enabled": True,
        "frequency_hz": 6500.0,
        "threshold_db": -20.0,
        "max_reduction_db": 10.0,
        "mode": "split",
    }

    res = preview.render_preview_mix(
        render_dir=test_render_dir,
        profile=profile,
        output_path=out_wav,
        max_duration=3.0,
        limiter_ceiling_db=-0.5,
        eq_bands=eq_bands,
        deesser_config=deesser_cfg,
    )

    assert os.path.exists(res["output_path"])
    assert res["true_peak_dbtp"] <= 0.0


def test_server_preview_mix_with_new_dsp(test_render_dir: str) -> None:
    res = server.preview_mix(
        style="techno",
        render_dir=test_render_dir,
        max_duration=3.0,
        limiter_ceiling_db=-1.0,
        deesser_config={"enabled": True, "frequency_hz": 6500.0, "threshold_db": -18.0},
        eq_bands=[{"type": "bell", "freq": 500, "gain": 2.0, "q": 1.0, "enabled": True}],
    )
    assert os.path.exists(res["output_path"])
