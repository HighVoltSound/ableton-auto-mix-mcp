"""Unit tests for core engine modules: mixer, auto_role, ai_recommender, planner.

These test the decision-making logic without touching audio files or the network.
"""

from __future__ import annotations

import os
import sys

import numpy as np

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

SR = 44100


# ---------------------------------------------------------------------------
# auto_role: feature extraction + classification
# ---------------------------------------------------------------------------


class TestAutoRole:
    """Test the automatic track role classifier."""

    def _tone(self, freq: float, dur: float = 1.0) -> np.ndarray:
        t = np.linspace(0, dur, int(SR * dur), endpoint=False)
        return np.sin(2 * np.pi * freq * t).reshape(-1, 1)

    def _stereo(self, mono: np.ndarray) -> np.ndarray:
        return np.repeat(mono, 2, axis=1)

    def test_kick_detection(self):
        from ableton_auto_mix.auto_role import _compute_features, classify_role

        n = int(SR * 0.25)
        t = np.linspace(0, 0.25, n, endpoint=False)
        kick = np.exp(-t * 30) * np.sin(2 * np.pi * 60 * t)
        kick = np.pad(kick.reshape(-1, 1), ((0, SR - n), (0, 0)))
        kick = np.repeat(kick, 2, axis=1)
        features = _compute_features(kick, SR)
        role, conf = classify_role(features)
        assert role == "kick"
        assert conf > 0.5

    def test_bass_detection(self):
        from ableton_auto_mix.auto_role import _compute_features, classify_role

        bass = self._stereo(self._tone(80, 2.0) * 0.5)
        features = _compute_features(bass, SR)
        role, conf = classify_role(features)
        assert role == "bass"
        assert conf > 0.4

    def test_high_freq_detection(self):
        from ableton_auto_mix.auto_role import _compute_features, classify_role

        hats = self._stereo(self._tone(8000, 2.0) * 0.3)
        features = _compute_features(hats, SR)
        role, _ = classify_role(features)
        assert role in ("hihat", "hats", "cymbal", "lead", "synth")

    def test_stereo_width_feature(self):
        from ableton_auto_mix.auto_role import _stereo_width

        mono = np.random.default_rng(42).standard_normal((SR, 2))
        mono[:, 1] = mono[:, 0]
        width = _stereo_width(mono)
        assert width < 0.01


# ---------------------------------------------------------------------------
# mixer: compute_mix
# ---------------------------------------------------------------------------


class TestMixer:
    def _make_analysis(self, name: str, role: str, rms_db: float = -20.0):
        from ableton_auto_mix.analyzer import TrackAnalysis

        return TrackAnalysis(
            name=name,
            path=f"/fake/{name}.wav",
            sample_rate=SR,
            duration_s=2.0,
            rms_db=rms_db,
            peak_db=rms_db + 6.0,
            lufs=rms_db - 3.0,
            lra=6.0,
            bandwidth_db={
                "sub_bass": -40.0,
                "bass": -30.0,
                "low_mids": -25.0,
                "mids": -22.0,
                "high_mids": -28.0,
                "highs": -35.0,
            },
            stereo_width=0.5,
            true_peak_dbtp=rms_db + 2.0,
        )

    def test_roles_assign_sensible_gains(self):
        from ableton_auto_mix.mixer import compute_mix
        from ableton_auto_mix.profiles import StyleProfile

        analyses = [
            self._make_analysis("kick", "kick", rms_db=-12.0),
            self._make_analysis("bass", "bass", rms_db=-15.0),
            self._make_analysis("vocals", "vocal", rms_db=-30.0),
        ]
        profile = StyleProfile(
            name="test",
            label="Test",
            target_lufs=-14.0,
            target_lra=6.0,
            tempo_range=[120, 140],
            stereo_width="moderate",
            frequency_balance=[],
            track_balance={
                "kick": {"level": 0.0},
                "bass": {"level": -2.0},
                "vocals": {"level": 3.0},
            },
        )
        result = compute_mix(analyses, profile)
        assert len(result.track_corrections) == 3
        kick_corr = next(c for c in result.track_corrections if c.name == "kick")
        vocal_corr = next(c for c in result.track_corrections if c.name == "vocals")
        # Kick is anchor (level=0), vocals have level=3 but are -18 dB quieter
        # so vocal should get boosted relative to kick
        assert (vocal_corr.volume_db or 0) > (kick_corr.volume_db or 0)

    def test_empty_analyses_raises(self):
        import pytest

        from ableton_auto_mix.mixer import compute_mix
        from ableton_auto_mix.profiles import StyleProfile

        profile = StyleProfile(
            name="test",
            label="Test",
            target_lufs=-14.0,
            target_lra=6.0,
            tempo_range=[120, 140],
            stereo_width="moderate",
            frequency_balance=[],
        )
        with pytest.raises(ValueError):
            compute_mix([], profile)


# ---------------------------------------------------------------------------
# ai_recommender: recommendation generation
# ---------------------------------------------------------------------------


class TestAiRecommender:
    def _track(self, name: str, role: str, rms_db: float = -20.0) -> dict:
        return {
            "name": name,
            "role": role,
            "rms_db": rms_db,
            "band_energy": {
                "sub_bass": -40.0,
                "bass": -30.0,
                "low_mids": -25.0,
                "mids": -22.0,
                "high_mids": -28.0,
                "highs": -35.0,
            },
        }

    def test_recommend_returns_dataclass(self):
        from ableton_auto_mix.ai_recommender import recommend

        tracks = [
            self._track("kick", "kick", -15.0),
            self._track("bass", "bass", -18.0),
            self._track("vocals", "vocal", -25.0),
        ]
        result = recommend(tracks, {"kick": "kick", "bass": "bass", "vocals": "vocal"})
        assert hasattr(result, "recommendations")
        assert len(result.recommendations) > 0
        for rec in result.recommendations:
            assert hasattr(rec, "category")
            assert hasattr(rec, "reason")

    def test_recommend_has_role_map(self):
        from ableton_auto_mix.ai_recommender import recommend

        result = recommend([], {})
        assert hasattr(result, "role_map")
        assert isinstance(result.role_map, dict)


# ---------------------------------------------------------------------------
# planner: plan generation
# ---------------------------------------------------------------------------


class TestPlanner:
    def test_plan_has_mix_and_master_actions(self):
        from ableton_auto_mix.analyzer import TrackAnalysis
        from ableton_auto_mix.mixer import compute_mix
        from ableton_auto_mix.planner import build_plan
        from ableton_auto_mix.profiles import StyleProfile

        analyses = [
            TrackAnalysis(
                name="kick",
                path="/fake/kick.wav",
                sample_rate=SR,
                duration_s=2.0,
                rms_db=-15.0,
                peak_db=-8.0,
                lufs=-18.0,
                lra=6.0,
                bandwidth_db={
                    "sub_bass": -30.0,
                    "bass": -20.0,
                    "low_mids": -25.0,
                    "mids": -30.0,
                    "high_mids": -35.0,
                    "highs": -40.0,
                },
                stereo_width=0.3,
                true_peak_dbtp=-10.0,
            ),
            TrackAnalysis(
                name="bass",
                path="/fake/bass.wav",
                sample_rate=SR,
                duration_s=2.0,
                rms_db=-20.0,
                peak_db=-12.0,
                lufs=-23.0,
                lra=6.0,
                bandwidth_db={
                    "sub_bass": -20.0,
                    "bass": -15.0,
                    "low_mids": -25.0,
                    "mids": -30.0,
                    "high_mids": -35.0,
                    "highs": -40.0,
                },
                stereo_width=0.4,
                true_peak_dbtp=-15.0,
            ),
        ]
        profile = StyleProfile(
            name="test",
            label="Test",
            target_lufs=-14.0,
            target_lra=6.0,
            tempo_range=[120, 140],
            stereo_width="moderate",
            frequency_balance=[],
            track_balance={
                "kick": {"target_lufs": -14.0},
                "bass": {"target_lufs": -16.0},
            },
        )
        mix_result = compute_mix(analyses, profile)
        plan = build_plan(analyses, profile, mix_result)
        assert hasattr(plan, "mix_actions")
        assert hasattr(plan, "master_actions")
        assert isinstance(plan.mix_actions, list)
        assert isinstance(plan.master_actions, list)


# ---------------------------------------------------------------------------
# dsp.biquad: coefficient correctness
# ---------------------------------------------------------------------------


class TestBiquad:
    def test_peakingUnity(self):
        """0 dB gain should produce passthrough (b == a)."""
        from ableton_auto_mix.dsp.biquad import peaking_biquad

        b, a = peaking_biquad(44100, 1000.0, 0.0)
        np.testing.assert_allclose(b, a, atol=1e-10)

    def test_lowShelfStability(self):
        from ableton_auto_mix.dsp.biquad import low_shelf_biquad

        b, a = low_shelf_biquad(44100, 100.0, 12.0)
        assert np.all(np.isfinite(b))
        assert np.all(np.isfinite(a))
        assert abs(a[0] - 1.0) < 1e-6

    def test_highShelfStability(self):
        from ableton_auto_mix.dsp.biquad import high_shelf_biquad

        b, a = high_shelf_biquad(44100, 8000.0, -12.0)
        assert np.all(np.isfinite(b))
        assert np.all(np.isfinite(a))
        assert abs(a[0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# dsp._utils: sliding primitives
# ---------------------------------------------------------------------------


class TestSlidingPrimitives:
    def test_slidingMax_identity(self):
        from ableton_auto_mix.dsp._utils import sliding_max

        x = np.array([1.0, 3.0, 2.0, 5.0, 4.0])
        result = sliding_max(x, 1)
        np.testing.assert_array_equal(result, x)

    def test_slidingMax_cumulativeWhenWindowLarger(self):
        from ableton_auto_mix.dsp._utils import sliding_max

        x = np.array([1.0, 3.0, 2.0])
        result = sliding_max(x, 5)
        # When window >= n, returns np.maximum.accumulate (cumulative max)
        assert result[0] == 1.0
        assert result[1] == 3.0
        assert result[2] == 3.0

    def test_movingAverage_smoothing(self):
        from ableton_auto_mix.dsp._utils import moving_average

        x = np.zeros(100)
        x[50] = 10.0
        result = moving_average(x, 10)
        assert result[50] < 10.0
        assert result[50] > 0.0

    def test_compressor_reducesLevel(self):
        from ableton_auto_mix.dsp._utils import compressor

        sr = 44100
        t = np.linspace(0, 1.0, sr, endpoint=False)
        loud = np.sin(2 * np.pi * 440 * t).reshape(-1, 1) * 0.9
        loud = np.repeat(loud, 2, axis=1)
        compressed = compressor(loud, sr, threshold_db=-12.0, ratio=4.0)
        rms_in = np.sqrt(np.mean(loud**2))
        rms_out = np.sqrt(np.mean(compressed**2))
        assert rms_out < rms_in
