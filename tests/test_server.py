"""Tests for the MCP server tool functions."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Generator

import numpy as np
import pytest
import soundfile as sf

from ableton_auto_mix import server

SR = 44100
DUR = 3.5  # pyloudnorm requires >= 3.0s for loudness_range calculation


def _tone(freq: float, dur: float = DUR) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


@pytest.fixture
def render_dir() -> Generator[str, None, None]:
    tmp = tempfile.mkdtemp(prefix="mcp_test_render_")
    # kick
    kick = (_tone(60) * 0.8).reshape(-1, 1)
    kick = np.repeat(kick, 2, axis=1)
    sf.write(os.path.join(tmp, "kick.wav"), kick, SR, subtype="PCM_16")

    # bass
    bass = (_tone(90) * 0.6).reshape(-1, 1)
    bass = np.repeat(bass, 2, axis=1)
    sf.write(os.path.join(tmp, "bass.wav"), bass, SR, subtype="PCM_16")

    # snare
    rng = np.random.default_rng(42)
    snare = (rng.uniform(-0.5, 0.5, int(SR * DUR))).reshape(-1, 1)
    snare = np.repeat(snare, 2, axis=1)
    sf.write(os.path.join(tmp, "snare.wav"), snare, SR, subtype="PCM_16")

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_list_styles() -> None:
    styles = server.list_styles()
    assert len(styles) >= 10
    names = [s["name"] for s in styles]
    assert "techno" in names
    assert "breaks" in names


def test_get_style() -> None:
    profile = server.get_style("techno")
    assert profile["name"] == "techno"
    assert "target_lufs" in profile


def test_get_ableton_status() -> None:
    status = server.get_ableton_status()
    assert "connected" in status


def test_analyze_audio(render_dir: str) -> None:
    path = os.path.join(render_dir, "kick.wav")
    res = server.analyze_audio(path)
    assert res["name"] == "kick"
    assert "lufs" in res
    assert "band_energy_db" in res


def test_analyze_render_dir(render_dir: str) -> None:
    res = server.analyze_render_dir(render_dir)
    assert len(res) == 3
    names = {r["name"] for r in res}
    assert names == {"kick", "bass", "snare"}


def test_detect_track_roles(render_dir: str) -> None:
    roles = server.detect_track_roles(render_dir)
    assert len(roles) == 3
    role_map = {r["name"]: r["role"] for r in roles}
    assert "kick" in role_map
    assert "bass" in role_map
    assert "snare" in role_map


def test_recommend_mix(render_dir: str) -> None:
    recs = server.recommend_mix(render_dir, style="techno")
    assert "recommendations" in recs
    assert "summary" in recs
    assert "role_map" in recs
    assert len(recs["recommendations"]) > 0


def test_match_eq_reference(render_dir: str) -> None:
    target = os.path.join(render_dir, "kick.wav")
    ref = os.path.join(render_dir, "bass.wav")
    res = server.match_eq_reference(target, ref, n_bands=4)
    assert "bands" in res
    assert res["n_bands"] == 4


def test_suggest_style(render_dir: str) -> None:
    res = server.suggest_style(render_dir)
    assert "suggested_style" in res
    assert "ranked" in res


def test_analyze_conflicts(render_dir: str) -> None:
    res = server.analyze_conflicts(render_dir)
    assert "conflicts" in res
    assert "tracks_analyzed" in res


def test_auto_mix(render_dir: str) -> None:
    res = server.auto_mix(style="techno", render_dir=render_dir, dry_run=True)
    assert "track_corrections" in res
    assert len(res["track_corrections"]) == 3


def test_preview_mix_and_dsp(render_dir: str) -> None:
    out_preview = os.path.join(render_dir, "test_preview.wav")
    res = server.preview_mix(
        style="techno",
        render_dir=render_dir,
        output_path=out_preview,
        max_duration=3.0,
        multiband_config={"mix": 0.8},
        limiter_ceiling_db=-0.5,
        dynamic_eq_config={"bands": [{"freq": 100, "threshold_db": -12, "ratio": 2.0, "gain_db": -3.0}]},
        midside_eq_config={"mid_bands": [], "side_bands": []},
        transient_config={"attack_gain_db": 1.0, "sustain_gain_db": -1.0},
    )
    assert os.path.exists(res["output_path"])
    assert "target_lufs" in res
    assert "true_peak_dbtp" in res


def test_compare_styles_ab(render_dir: str) -> None:
    res = server.compare_styles_ab(
        style_a="techno",
        style_b="breaks",
        render_dir=render_dir,
        max_duration=3.0,
    )
    assert os.path.exists(res["output_a"])
    assert os.path.exists(res["output_b"])


def test_export_to_ableton(render_dir: str) -> None:
    als_out = os.path.join(render_dir, "export_test.als")
    res = server.export_to_ableton(
        style="techno",
        render_dir=render_dir,
        mode="file",
        session_path=als_out,
    )
    assert res["applied"] == 3
    assert res["mode"] == "file"
    assert os.path.exists(als_out)


def test_presets_crud() -> None:
    preset_name = "test_mcp_preset_123"
    # Save
    save_res = server.save_mix_preset(
        name=preset_name,
        style="techno",
        multiband={"mix": 0.9},
        notes="Testing MCP preset",
    )
    assert save_res["saved"] is True

    # List
    all_presets = server.list_mix_presets()
    names = [p["name"] for p in all_presets]
    assert preset_name in names

    # Load
    loaded = server.load_mix_preset(preset_name)
    assert loaded["name"] == preset_name
    assert loaded["style"] == "techno"

    # Delete
    del_res = server.delete_mix_preset(preset_name)
    assert del_res["deleted"] is True


def test_export_audio_format(render_dir: str) -> None:
    src_wav = os.path.join(render_dir, "kick.wav")
    flac_out = os.path.join(render_dir, "kick_exported.flac")
    res = server.export_audio_format(
        input_path=src_wav,
        format="flac",
        output_path=flac_out,
    )
    assert res["format"] == "flac"
    assert os.path.exists(flac_out)


def test_batch_process_dirs(render_dir: str) -> None:
    res = server.batch_process_dirs(
        directories=[render_dir],
        style="techno",
        max_duration=3.0,
    )
    assert res["total"] == 1
    assert res["completed"] == 1


def test_release_check(render_dir: str) -> None:
    src_wav = os.path.join(render_dir, "kick.wav")
    res = server.release_check(
        render_dir=render_dir,
        style="techno",
        output_path=src_wav,
    )
    assert "verdict" in res
    assert "metrics" in res
