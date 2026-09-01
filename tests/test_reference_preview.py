"""Tests for reference-based match EQ and the extended preview renderer:
real per-track EQ (band_corrections), match-EQ vs a reference WAV, and the
A/B "before" bounce. Everything runs on synthetic signals, no Ableton needed.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.api_app import _register_dir, app  # noqa: E402
from ableton_auto_mix.preview import render_preview_mix  # noqa: E402
from ableton_auto_mix.profiles import get_profile  # noqa: E402
from ableton_auto_mix.reference import (  # noqa: E402
    apply_match_eq,
    compute_match_curve,
    load_audio_stereo,
)

SR = 44100
DUR = 2.0


def _tone(freq: float, dur: float = DUR, amp: float = 1.0) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return amp * np.sin(2 * np.pi * freq * t)


@pytest.fixture(scope="module")
def render_dir(tmp_path_factory) -> str:
    """Tiny 4-track project (same recipe as the smoke tests)."""
    tmp = str(tmp_path_factory.mktemp("renders"))
    n_kick = int(SR * 0.25)
    t = np.linspace(0, 0.25, n_kick, endpoint=False)
    kick = (np.exp(-t * 30) * np.sin(2 * np.pi * 60 * t)).reshape(-1, 1)
    kick = np.pad(kick, ((0, SR * int(DUR) - n_kick), (0, 0)))
    sf.write(os.path.join(tmp, "kick.wav"), np.repeat(kick, 2, axis=1), SR, subtype="PCM_16")

    bass = _tone(80, amp=0.5).reshape(-1, 1)
    sf.write(os.path.join(tmp, "bass.wav"), np.repeat(bass, 2, axis=1), SR, subtype="PCM_16")

    rng = np.random.default_rng(7)
    noise = rng.uniform(-1, 1, SR * int(DUR)) * np.exp(-np.linspace(0, 1, SR * int(DUR)) * 15)
    snare = noise.reshape(-1, 1) * 0.4
    sf.write(
        os.path.join(tmp, "snare.wav"),
        np.repeat(snare, 2, axis=1),
        SR,
        subtype="PCM_16",
    )

    sf.write(os.path.join(tmp, "vocals.wav"), _tone(440, amp=0.15), SR, subtype="PCM_16")
    _register_dir(tmp)
    return tmp


@pytest.fixture(scope="module")
def reference_wav(tmp_path_factory) -> str:
    """A 'reference' with a clearly different spectral tilt (bright, mid-heavy).

    Lives in a subfolder of the renders so it is not picked up as a track by
    analyze_directory's non-recursive *.wav glob.
    """
    tmp = tmp_path_factory.mktemp("ref")
    rng = np.random.default_rng(11)
    # Bright noise bed + strong mids/highs, unlike the bass-heavy mix parts.
    sig = rng.uniform(-1, 1, SR * int(DUR)) * 0.3
    sig += _tone(3000, amp=0.4) + _tone(700, amp=0.4)
    path = os.path.join(str(tmp), "reference.wav")
    sf.write(path, sig.astype(np.float64), SR, subtype="PCM_16")
    _register_dir(str(tmp))
    return path


# ---------------------------------------------------------------------------
# reference.compute_match_curve / apply_match_eq
# ---------------------------------------------------------------------------


def test_match_curve_identical_signals_is_flat(render_dir: str) -> None:
    audio, sr = load_audio_stereo(os.path.join(render_dir, "kick.wav"))
    curve = compute_match_curve(sr, audio, sr, audio, n_bands=24)
    assert len(curve) == 24
    assert all(c["gain_db"] == round(c["gain_db"], 2) for c in curve)
    # Same signal vs itself -> shape difference is zero everywhere.
    assert max(abs(c["gain_db"]) for c in curve) < 1.0
    hz = [c["hz"] for c in curve]
    assert hz == sorted(hz)  # frequency-ascending
    assert hz[0] >= 20.0 and hz[-1] <= SR / 2


def test_match_curve_bounds_and_sensitivity(reference_wav: str, render_dir: str) -> None:
    mix_parts = []
    for name in ("kick", "bass", "snare", "vocals"):
        a, sr = load_audio_stereo(os.path.join(render_dir, f"{name}.wav"))
        mix_parts.append(a)
        assert sr == SR
    mixdown = sum(mix_parts)

    curve = compute_match_curve(SR, mixdown, SR, load_audio_stereo(reference_wav)[0])
    assert len(curve) == 24
    gains = [c["gain_db"] for c in curve]
    # Safety clamp respected.
    assert all(-6.0 <= g <= 6.0 for g in gains)
    # Bass-heavy mix vs bright reference must want low cuts / high boosts...
    # (direction depends on smoothing, but the curve must not be all-zero)
    assert max(abs(g) for g in gains) >= 1.0

    # Resampled reference (different sr) must still work.
    curve2 = compute_match_curve(SR, mixdown, SR // 2, load_audio_stereo(reference_wav)[0][::2])
    assert len(curve2) == 24
    assert all(np.isfinite(c["gain_db"]) for c in curve2)


def test_apply_match_eq_changes_spectrum() -> None:
    sr = SR
    sig = (_tone(200, amp=0.5) + _tone(5000, amp=0.5)).reshape(-1, 1)
    sig = np.repeat(sig, 2, axis=1)

    curve = [
        {"hz": 60.0, "gain_db": 0.0},
        {"hz": 200.0, "gain_db": 6.0},  # boost the 200 Hz component
        {"hz": 800.0, "gain_db": 0.0},
        {"hz": 5000.0, "gain_db": -6.0},  # cut the 5 kHz component
        {"hz": 12000.0, "gain_db": 0.0},
    ]
    out = apply_match_eq(sig, sr, curve)

    def band_energy(x: np.ndarray, f: float) -> float:
        seg = x[:, 0][sr // 4 :]  # skip filter warm-up
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freqs = np.fft.rfftfreq(len(seg), 1 / sr)
        mask = np.abs(freqs - f) < 30
        return float(np.mean(spec[mask]))

    ratio_in = band_energy(sig, 200) / band_energy(sig, 5000)
    ratio_out = band_energy(out, 200) / band_energy(out, 5000)
    assert ratio_out > ratio_in * 1.5  # tonal balance clearly moved
    assert out.shape == sig.shape and np.all(np.isfinite(out))

    # Empty / neutral curves leave the audio untouched.
    assert np.allclose(apply_match_eq(sig, sr, []), sig)
    flat = [{"hz": float(f), "gain_db": 0.0} for f in (100, 1000, 10000)]
    assert np.allclose(apply_match_eq(sig, sr, flat), sig)


# ---------------------------------------------------------------------------
# preview.render_preview_mix: eq_applied / match_eq / before bounce
# ---------------------------------------------------------------------------


def test_preview_with_reference_and_before(render_dir: str, reference_wav: str, tmp_path_factory) -> None:
    out_dir = str(tmp_path_factory.mktemp("preview_out"))
    out = os.path.join(out_dir, "preview_ref.wav")
    result = render_preview_mix(
        render_dir,
        get_profile("breaks"),
        output_path=out,
        max_duration=1.5,
        reference_path=reference_wav,
        render_before=True,
    )

    # Main output + before bounce both written.
    assert os.path.isfile(result["output_path"])
    before = result.get("before_path")
    assert before and os.path.isfile(before)
    assert before.endswith("_before.wav") and os.path.dirname(before) == out_dir

    info_main = sf.info(result["output_path"])
    info_before = sf.info(before)
    assert info_before.frames <= info_main.frames  # same common trim, never longer
    assert abs(info_before.duration - result["duration_s"]) < 0.05

    # Real per-track EQ report present (list of applied corrections).
    assert "eq_applied" in result and isinstance(result["eq_applied"], list)
    for entry in result["eq_applied"]:
        assert set(entry) >= {"track", "band", "range_hz", "delta_db"}
        assert -6.0 <= entry["delta_db"] <= 6.0

    # Match EQ block present with a bounded curve.
    meq = result["match_eq"]
    assert meq and os.path.abspath(meq["reference_path"]) == os.path.abspath(reference_wav)
    curve = meq["curve"]
    assert len(curve) == 24
    assert all(-6.0 <= p["gain_db"] <= 6.0 for p in curve)

    # The processed master stays TP-safe as before.
    assert result["true_peak_dbtp"] <= -0.5
    # ...and so does the raw "before" bounce.
    before_audio, _ = load_audio_stereo(before)
    assert float(np.max(np.abs(before_audio))) <= 10 ** (-0.8 / 20.0)


def test_preview_without_reference_backward_compatible(render_dir: str, tmp_path_factory) -> None:
    """No new arguments -> old behaviour, but the new keys still exist."""
    out_dir = str(tmp_path_factory.mktemp("preview_plain"))
    result = render_preview_mix(
        render_dir,
        get_profile("breaks"),
        output_path=os.path.join(out_dir, "plain.wav"),
        max_duration=1.0,
    )
    assert result["match_eq"] is None
    assert "before_path" not in result
    assert isinstance(result["eq_applied"], list)


# ---------------------------------------------------------------------------
# HTTP API
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_api_preview_reference_and_before(
    client: TestClient, render_dir: str, reference_wav: str, tmp_path_factory
) -> None:
    out_dir = str(tmp_path_factory.mktemp("api_out"))
    out = os.path.join(out_dir, "api_preview.wav")
    resp = client.post(
        "/api/preview",
        json={
            "style": "breaks",
            "directory": render_dir,
            "output_path": out,
            "max_duration": 1.5,
            "reference_path": reference_wav,
            "render_before": True,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert os.path.isfile(body["output_path"])
    assert body["before_path"] and os.path.isfile(body["before_path"])
    assert isinstance(body["eq_applied"], list)
    assert body["match_eq"]["curve"]
    assert all(-6.0 <= p["gain_db"] <= 6.0 for p in body["match_eq"]["curve"])

    # Old-style request without the new fields keeps working.
    plain = client.post("/api/preview", json={"style": "breaks", "directory": render_dir})
    assert plain.status_code == 200
    assert plain.json()["match_eq"] is None
    assert "before_path" not in plain.json()


def test_api_match_eq_endpoint(client: TestClient, render_dir: str, reference_wav: str, tmp_path_factory) -> None:
    # Render any preview first so we have a mix WAV on disk.
    out_dir = str(tmp_path_factory.mktemp("meq_mix"))
    mix_wav = os.path.join(out_dir, "mix.wav")
    rendered = render_preview_mix(render_dir, get_profile("breaks"), output_path=mix_wav, max_duration=1.0)
    mix_wav = rendered["output_path"]
    _register_dir(os.path.dirname(mix_wav))

    resp = client.post(
        "/api/match_eq",
        json={"mix_wav_path": mix_wav, "reference_path": reference_wav},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mix_wav_path"].lower().endswith(".wav")
    assert body["reference_path"].endswith("reference.wav")
    curve = body["curve"]
    assert 20 <= len(curve) <= 30
    assert all({"hz", "gain_db"} <= set(p) for p in curve)
    assert all(-6.0 <= p["gain_db"] <= 6.0 for p in curve)

    # Path guard: files outside whitelisted roots are rejected.
    rogue_dir = str(tmp_path_factory.mktemp("rogue"))
    rogue = os.path.join(rogue_dir, "r.wav")
    sf.write(rogue, np.zeros(16), SR)
    bad = client.post(
        "/api/match_eq",
        json={"mix_wav_path": mix_wav, "reference_path": rogue},
    )
    assert bad.status_code == 400
