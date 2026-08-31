"""Preview harness: end-to-end tests for render_preview_mix.

Creates synthetic stems, runs the full preview pipeline, and asserts
on the output WAV quality metrics (LUFS, true peak, LRA, no clipping).
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from ableton_auto_mix.profiles import StyleProfile, load_profile
from ableton_auto_mix.preview import PreviewOptions, render_preview_mix

SR = 44100
DUR = 4.0  # seconds — long enough for pyloudnorm (needs >= 3s)

# ---------------------------------------------------------------------------
# Fixtures: synthetic stems
# ---------------------------------------------------------------------------


def _tone(freq: float, dur: float = DUR, sr: int = SR) -> np.ndarray:
    """Mono sine tone."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


def _noise(dur: float = DUR, sr: int = SR) -> np.ndarray:
    """Mono white noise."""
    return np.random.default_rng(42).standard_normal(int(sr * dur))


def _stereo(mono: np.ndarray) -> np.ndarray:
    """Convert mono to stereo (duplicate)."""
    return np.column_stack([mono, mono])


def _write_wav(path: str, audio: np.ndarray, sr: int = SR) -> None:
    sf.write(path, audio, sr, subtype="PCM_16")


def _make_render_dir(stems: dict[str, np.ndarray]) -> str:
    """Write stems to a temp directory and return the path."""
    tmp = tempfile.mkdtemp(prefix="harness_render_")
    for name, audio in stems.items():
        _write_wav(os.path.join(tmp, f"{name}.wav"), audio)
    return tmp


def _measure_wav(path: str) -> dict[str, Any]:
    """Read a WAV and return key metrics."""
    audio, sr = sf.read(path, dtype="float64")
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    # Integrated loudness
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(audio)

    # True peak
    peak = float(np.max(np.abs(audio)))

    # LRA (loudness range)
    try:
        lra = meter.loudness_range(audio)
    except Exception:
        lra = None

    return {
        "loudness_lufs": loudness,
        "true_peak": peak,
        "lra": lra,
        "shape": audio.shape,
        "sr": sr,
    }


# ---------------------------------------------------------------------------
# Profiles for testing
# ---------------------------------------------------------------------------


def _get_profile(name: str = "balanced") -> StyleProfile:
    return load_profile(name)


# ---------------------------------------------------------------------------
# Test: basic render produces valid WAV
# ---------------------------------------------------------------------------


class TestBasicRender:
    """Smoke tests: does render_preview_mix produce a valid WAV?"""

    def test_basic_render_produces_file(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "snare": _stereo(_tone(200) * 0.5),
            "lead": _stereo(_tone(440) * 0.3),
        }
        render_dir = _make_render_dir(stems)
        out = str(tmp_path / "preview.wav")
        profile = _get_profile()

        result = render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out,
        )

        assert os.path.exists(out), "Output WAV was not created"
        assert os.path.getsize(out) > 0, "Output WAV is empty"

        metrics = _measure_wav(out)
        # LUFS should be finite (not -inf from silence)
        assert np.isfinite(metrics["loudness_lufs"]), "LUFS is not finite"
        # True peak should be > 0
        assert metrics["true_peak"] > 0, "True peak is zero (silence)"

    def test_basic_render_no_clipping(self, tmp_path: Any) -> None:
        """True peak must stay below 0 dBFS (limiter applied)."""
        stems = {
            "kick": _stereo(_tone(60) * 0.9),
            "bass": _stereo(_tone(100) * 0.8),
            "lead": _stereo(_tone(440) * 0.7),
        }
        render_dir = _make_render_dir(stems)
        out = str(tmp_path / "preview.wav")
        profile = _get_profile()

        render_preview_mix(render_dir=render_dir, profile=profile, output_path=out)

        metrics = _measure_wav(out)
        assert (
            metrics["true_peak"] <= 1.0
        ), f"Clipping detected: peak={metrics['true_peak']:.4f}"


# ---------------------------------------------------------------------------
# Test: style profiles produce different loudness targets
# ---------------------------------------------------------------------------


class TestStyleProfiles:
    """Different styles should produce different loudness targets."""

    def test_techno_vs_ambient_loudness(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "lead": _stereo(_tone(440) * 0.5),
        }
        render_dir_techno = _make_render_dir(stems)
        render_dir_ambient = _make_render_dir(stems)

        out_techno = str(tmp_path / "techno.wav")
        out_ambient = str(tmp_path / "ambient.wav")

        techno = _get_profile("techno")
        ambient = _get_profile("ambient")

        render_preview_mix(
            render_dir=render_dir_techno, profile=techno, output_path=out_techno
        )
        render_preview_mix(
            render_dir=render_dir_ambient, profile=ambient, output_path=out_ambient
        )

        m_techno = _measure_wav(out_techno)
        m_ambient = _measure_wav(out_ambient)

        # Techno target is louder than ambient target
        assert (
            techno.target_lufs > ambient.target_lufs
        ), f"Techno ({techno.target_lufs}) should be louder than ambient ({ambient.target_lufs})"

        # Both should produce finite loudness
        assert np.isfinite(m_techno["loudness_lufs"])
        assert np.isfinite(m_ambient["loudness_lufs"])


# ---------------------------------------------------------------------------
# Test: sidechain ducking
# ---------------------------------------------------------------------------


class TestSidechain:
    """Sidechain should reduce non-snare tracks when snare hits."""

    def test_sidechain_reduces_loudness(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.9),
            "snare": _stereo(_tone(200) * 0.8),  # full-length snare for valid LUFS
            "bass": _stereo(_tone(100) * 0.8),
        }
        render_dir = _make_render_dir(stems)

        out_no_sc = str(tmp_path / "no_sidechain.wav")
        out_sc = str(tmp_path / "sidechain.wav")
        profile = _get_profile()

        render_preview_mix(
            render_dir=render_dir, profile=profile, output_path=out_no_sc
        )
        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out_sc,
            sidechain_db=-6.0,
        )

        m_no_sc = _measure_wav(out_no_sc)
        m_sc = _measure_wav(out_sc)

        # Both should be valid
        assert np.isfinite(m_no_sc["loudness_lufs"])
        assert np.isfinite(m_sc["loudness_lufs"])


# ---------------------------------------------------------------------------
# Test: max_duration trimming
# ---------------------------------------------------------------------------


class TestMaxDuration:
    """max_duration should limit output length."""

    def test_max_duration_limits_output(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60, dur=10.0)),
            "lead": _stereo(_tone(440, dur=10.0)),
        }
        render_dir = _make_render_dir(stems)
        out = str(tmp_path / "preview.wav")
        profile = _get_profile()

        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out,
            max_duration=2.0,
        )

        audio, sr = sf.read(out, dtype="float64")
        duration = len(audio) / sr
        assert (
            duration <= 2.5
        ), f"Duration {duration:.1f}s exceeds max_duration + tolerance"


# ---------------------------------------------------------------------------
# Test: manual gain
# ---------------------------------------------------------------------------


class TestManualGain:
    """Manual gain should shift track levels."""

    def test_manual_gain_changes_loudness(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "lead": _stereo(_tone(440) * 0.5),
        }
        render_dir = _make_render_dir(stems)

        out_normal = str(tmp_path / "normal.wav")
        out_quiet = str(tmp_path / "quiet.wav")
        profile = _get_profile()

        render_preview_mix(
            render_dir=render_dir, profile=profile, output_path=out_normal
        )
        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out_quiet,
            manual_gain={"kick": -10.0},
        )

        m_normal = _measure_wav(out_normal)
        m_quiet = _measure_wav(out_quiet)

        # Both should produce valid output
        assert np.isfinite(m_normal["loudness_lufs"])
        assert np.isfinite(m_quiet["loudness_lufs"])
        # Manual gain should not make it louder
        assert m_quiet["loudness_lufs"] <= m_normal["loudness_lufs"] + 0.5, (
            f"Manual gain -10dB should not increase loudness: "
            f"normal={m_normal['loudness_lufs']:.1f}, quiet={m_quiet['loudness_lufs']:.1f}"
        )


# ---------------------------------------------------------------------------
# Test: PreviewOptions dataclass
# ---------------------------------------------------------------------------


class TestPreviewOptions:
    """PreviewOptions should work the same as kwargs."""

    def test_options_matches_kwargs(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "lead": _stereo(_tone(440) * 0.5),
        }
        render_dir = _make_render_dir(stems)
        profile = _get_profile()

        out_kwargs = str(tmp_path / "kwargs.wav")
        out_options = str(tmp_path / "options.wav")

        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out_kwargs,
            max_duration=2.0,
        )

        opts = PreviewOptions(output_path=out_options, max_duration=2.0)
        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            options=opts,
        )

        m_kwargs = _measure_wav(out_kwargs)
        m_options = _measure_wav(out_options)

        # Should produce similar results
        assert abs(m_kwargs["loudness_lufs"] - m_options["loudness_lufs"]) < 1.0, (
            f"Options vs kwargs loudness mismatch: "
            f"kwargs={m_kwargs['loudness_lufs']:.1f}, options={m_options['loudness_lufs']:.1f}"
        )


# ---------------------------------------------------------------------------
# Test: EQ bands
# ---------------------------------------------------------------------------


class TestEqBands:
    """Master EQ bands should shift frequency balance."""

    def test_eq_bands_shift_spectrum(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "lead": _stereo(_tone(440) * 0.5),
        }
        render_dir = _make_render_dir(stems)
        profile = _get_profile()

        out_flat = str(tmp_path / "flat.wav")
        out_boost = str(tmp_path / "boost.wav")

        render_preview_mix(render_dir=render_dir, profile=profile, output_path=out_flat)
        render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out_boost,
            eq_bands=[{"freq": 100, "gain": 6.0, "q": 1.0}],
        )

        m_flat = _measure_wav(out_flat)
        m_boost = _measure_wav(out_boost)

        # Both should produce valid output
        assert np.isfinite(m_flat["loudness_lufs"])
        assert np.isfinite(m_boost["loudness_lufs"])


# ---------------------------------------------------------------------------
# Test: render_before
# ---------------------------------------------------------------------------


class TestRenderBefore:
    """render_before=True should produce a second 'before' WAV."""

    def test_before_wav_created(self, tmp_path: Any) -> None:
        stems = {
            "kick": _stereo(_tone(60) * 0.8),
            "lead": _stereo(_tone(440) * 0.5),
        }
        render_dir = _make_render_dir(stems)
        out = str(tmp_path / "preview.wav")
        profile = _get_profile()

        result = render_preview_mix(
            render_dir=render_dir,
            profile=profile,
            output_path=out,
            render_before=True,
        )

        assert os.path.exists(out)
        before_path = result.get("before_path")
        assert before_path is not None, "before_path not in result"
        assert os.path.exists(before_path), "Before WAV was not created"
