"""Smoke tests: render a tiny synthetic project and run the whole pipeline
offline (no Ableton needed): analyze -> auto-mix -> preview -> release check.
"""

from __future__ import annotations

import os
import shutil
import sys

import numpy as np
import soundfile as sf

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

import ableton_auto_mix.analyzer as analyzer  # noqa: E402
import ableton_auto_mix.qa as qa  # noqa: E402
import ableton_auto_mix.profiles as profiles  # noqa: E402
from ableton_auto_mix.mixer import compute_mix, match_role  # noqa: E402
from ableton_auto_mix.preview import render_preview_mix  # noqa: E402

SR = 44100
DUR = 2.0


def _tone(freq: float, dur: float = DUR) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


def _make_render_dir(tmp: str) -> None:
    """Write a tiny 4-track project: kick, bass, snare, vocals."""
    os.makedirs(tmp, exist_ok=True)
    # kick: short 60 Hz thump + click
    n = int(SR * 0.25)
    t = np.linspace(0, 0.25, n, endpoint=False)
    kick = (np.exp(-t * 30) * np.sin(2 * np.pi * 60 * t)).reshape(-1, 1)
    kick = np.pad(kick, ((0, SR * int(DUR) - n), (0, 0)))
    kick = np.repeat(kick, 2, axis=1)
    sf.write(os.path.join(tmp, "kick.wav"), kick, SR, subtype="PCM_16")
    # bass: steady 80 Hz
    bass = _tone(80).reshape(-1, 1) * 0.5
    bass = np.repeat(bass, 2, axis=1)
    sf.write(os.path.join(tmp, "bass.wav"), bass, SR, subtype="PCM_16")
    # snare: noise burst
    rng = np.random.default_rng(7)
    noise = rng.uniform(-1, 1, SR * int(DUR)) * np.exp(-np.linspace(0, 1, SR * int(DUR)) * 15)
    snare = noise.reshape(-1, 1) * 0.4
    snare = np.repeat(snare, 2, axis=1)
    sf.write(os.path.join(tmp, "snare.wav"), snare, SR, subtype="PCM_16")
    # vocals: mono render on purpose (tests mono handling)
    vocal = _tone(440) * 0.15
    sf.write(os.path.join(tmp, "vocals.wav"), vocal, SR, subtype="PCM_16")


def test_match_role() -> None:
    assert match_role("KICK") == "kick"
    assert match_role("sub_bass") == "sub_bass"
    assert match_role("vocals") == "vocals"
    assert match_role("snt2") == "snare"
    assert match_role("pads") == "pads"


def test_spectral_role_fallback() -> None:
    from ableton_auto_mix.mixer import _spectral_role
    # Unknown file name but clearly sub-heavy -> sub_bass.
    sub = {"sub_bass": -20, "bass": -40, "low_mids": -60, "mids": -70,
           "high_mids": -75, "highs": -80}
    assert _spectral_role(sub) == "sub_bass"
    # Name wins over spectrum when it matches.
    from ableton_auto_mix.mixer import match_role_with_spectrum
    assert match_role_with_spectrum("KICK", sub) == "kick"
    assert match_role_with_spectrum("weird_01", sub) == "sub_bass"


def test_true_peak_in_analysis(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    results = analyzer.analyze_directory(str(tmp_path))
    for r in results:
        assert isinstance(r.true_peak_dbtp, float)
        assert r.true_peak_dbtp <= 0.0  # rendered clips never exceed 0 dBTP


def test_width_processing() -> None:
    from ableton_auto_mix.preview import _apply_width
    x = np.array([[0.8, -0.8], [0.5, -0.5]], dtype=float)
    mono = _apply_width(x, "mono")
    assert np.allclose(mono, 0.0)  # folded to center
    wide = _apply_width(x, "very_wide")
    assert abs(wide[0, 0]) > 1.0  # side channel boosted
    moderate = _apply_width(x, "moderate")
    assert abs(moderate[0, 0]) > 0.8  # moderate widens slightly
    # An unknown width label leaves the signal untouched.
    unknown = _apply_width(x, "custom")
    assert np.allclose(unknown, x)


def test_space_fx() -> None:
    from ableton_auto_mix.preview import _apply_space, _delay, _reverb, _sliding_max, _moving_average
    rng = np.random.default_rng(3)
    x = rng.uniform(-0.5, 0.5, (SR, 2)) * 0.3

    # Delay: wet adds a later echo, output shape/size preserved.
    d = _delay(x, SR, time_ms=50, feedback=0.4, amount=0.5)
    assert d.shape == x.shape
    assert not np.allclose(d, x)  # wet is audible
    assert np.all(np.isfinite(d))

    # Reverb: tail grows in time, mono-compatible, finite.
    r = _reverb(x, SR, amount=0.3, decay=0.5, tone=0.5)
    assert r.shape == x.shape
    assert np.all(np.isfinite(r))
    assert not np.allclose(r, x)

    # _apply_space wires the config keys; unknown roles pass through.
    shaped = _apply_space(x, SR, {"delay": {"time_ms": 60}, "reverb": {"amount": 0.2}})
    assert shaped.shape == x.shape
    assert np.allclose(_apply_space(x, SR, None), x)

    # Sliding max matches a hand-rolled trailing window max.
    m = np.abs(rng.uniform(-1, 1, (37, 2)))
    for w in (1, 5, 40):
        ref = np.stack([
            np.maximum.reduce(m[max(0, i - w + 1): i + 1], axis=0) for i in range(37)
        ])
        assert np.allclose(_sliding_max(m, w), ref), w

    # Moving average is linear-in-N and smooths an impulse.
    imp = np.zeros((200, 2)); imp[50] = 1.0
    avg = _moving_average(imp, 10)
    assert np.allclose(avg[50:60], 0.1)
    assert np.allclose(avg[:50], 0.0)


def test_compressor() -> None:
    from ableton_auto_mix.preview import _compressor

    rng = np.random.default_rng(5)
    # A transient-heavy signal: peaks above the threshold must be reduced.
    x = rng.uniform(-0.5, 0.5, (SR, 2))
    x[: int(0.05 * SR)] = 0.95  # a loud burst up front
    peak_in = float(np.max(np.abs(x)))
    comp = _compressor(x, SR, threshold_db=-10.0, ratio=4.0, attack_ms=3.0, release_ms=80.0)
    assert comp.shape == x.shape
    assert np.all(np.isfinite(comp))
    # Loud part is tamed.
    assert float(np.max(np.abs(comp[: int(0.05 * SR)]))) < peak_in
    # Below-threshold content passes through almost untouched.
    quiet = rng.uniform(-0.05, 0.05, (SR, 2))
    out_quiet = _compressor(quiet, SR, threshold_db=-30.0, ratio=4.0)
    assert np.allclose(out_quiet, quiet, atol=1e-6)


def test_mono_analysis(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    results = analyzer.analyze_directory(str(tmp_path))
    by_name = {r.name: r for r in results}
    # Mono vocals must get a real (not -120) LUFS value.
    assert by_name["vocals"].lufs > -120.0
    assert by_name["vocals"].lra >= 0.0
    assert len(results) == 4


def test_compute_mix_anchors_on_kick(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    results = analyzer.analyze_directory(str(tmp_path))
    profile = profiles.get_profile("breaks")
    mix = compute_mix(results, profile, [a.name for a in results])
    assert any("anchored on kick" in n for n in mix.master_notes)
    kick_corr = next(c for c in mix.track_corrections if c.role == "kick")
    assert kick_corr.volume_db == 0.0


def test_preview_and_release(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    profile = profiles.get_profile("breaks")
    result = render_preview_mix(
        str(tmp_path), profile, max_duration=1.5,
    )
    out = result["output_path"]
    assert os.path.isfile(out)
    assert result["sample_rate"] == SR
    assert result["duration_s"] == 1.5
    assert result["true_peak_dbtp"] <= -0.5

    check = qa.release_check(out, "breaks", profile.target_lufs)
    assert check["verdict"] in ("ready", "needs_work")
    assert round(check["measured_lufs"], 1) == check["metrics"][0]["measured"]


def test_suggest_style_runs(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    results = analyzer.analyze_directory(str(tmp_path))
    # The pure-LUFS spectral shape code path must not crash on any profile.
    for p in profiles.list_profiles():
        _ = compute_mix(results, p, [a.name for a in results])


def test_cli_commands(tmp_path) -> None:
    _make_render_dir(str(tmp_path))
    from ableton_auto_mix.cli import main as cli_main

    # Each command must exit cleanly (SystemExit not raised) and print JSON.
    import io
    import json as _json
    from contextlib import redirect_stdout

    cases = [
        ["styles"],
        ["analyze", str(tmp_path)],
        ["suggest", str(tmp_path)],
        ["mix", "breaks", str(tmp_path)],
        ["conflicts", str(tmp_path)],
    ]
    for argv in cases:
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                cli_main(argv)
        except SystemExit as exc:
            raise AssertionError(f"cli {argv} exited: {exc}") from exc
        _json.loads(buf.getvalue())  # must be valid JSON
    print(f"PASS cli_commands ({len(cases)} commands)")


def _run_all() -> None:
    import inspect
    import tempfile

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                with tempfile.TemporaryDirectory() as tmp:
                    fn(tmp)
            else:
                fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            import traceback
            print(f"FAIL {fn.__name__}: {exc}")
            traceback.print_exc()
    if failed:
        sys.exit(1)
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")


if __name__ == "__main__":
    _run_all()
