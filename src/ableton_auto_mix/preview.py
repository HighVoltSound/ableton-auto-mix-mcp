"""Offline mix preview: apply the computed corrections to the rendered WAVs
and bounce a stereo preview mix that can be listened to without Ableton.

This mirrors what auto_mix does on the Live set, but applies the level/pan
corrections to the audio files directly, sums them, and normalizes the result
to the style's target loudness.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .logging_utils import Timer, get_logger

_log = get_logger("preview")

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, lfilter, resample_poly, sosfiltfilt

from .analyzer import analyze_directory
from .dsp._utils import (
    apply_side_gain as _apply_side_gain,
)
from .dsp._utils import (
    apply_width as _apply_width,
)
from .dsp._utils import (
    compressor as _compressor,
)
from .dsp._utils import (
    moving_average as _moving_average,
)
from .dsp._utils import (
    sliding_max as _sliding_max,
)
from .dsp._utils import (
    true_peak_db as _true_peak_db,
)
from .mixer import BandCorrection, compute_mix
from .profiles import StyleProfile
from .reference import (
    MAX_MATCH_GAIN_DB,
    _high_shelf_biquad,
    _low_shelf_biquad,
    _peaking_biquad,
    apply_biquad,
    apply_match_eq,
    compute_match_curve,
    load_audio_stereo,
)

PAN_LAW_DB = -3.0  # equal-power-ish center attenuation

# Safety clamp for the per-track spectral corrections (same as match EQ).
MAX_TRACK_EQ_DB = MAX_MATCH_GAIN_DB


def _apply_band_correction(
    audio: np.ndarray, sr: int, bc: BandCorrection
) -> tuple[np.ndarray, dict[str, Any]]:
    """Sound one spectral correction from mixer.compute_mix on a stereo track.

    Designs a biquad from the band's range_hz / delta_db: a peaking filter in
    the middle of the band, or a shelf when the correction targets an edge of
    the spectrum (>=16 kHz highshelf, <=40 Hz lowshelf). Gain is clamped to
    +/-6 dB and Q to ~1.0 so the preview stays safe to listen to.

    Returns (filtered_audio, applied_info_dict).
    """
    lo = float(bc.freq_range[0])
    hi = float(bc.freq_range[1])
    delta = float(np.clip(bc.delta_db, -MAX_TRACK_EQ_DB, MAX_TRACK_EQ_DB))
    q = 1.0

    if hi >= 16000.0:
        f0 = max(lo, 1000.0)
        b, a = _high_shelf_biquad(sr, f0, delta, q=q)
    elif lo <= 40.0:
        f0 = min(hi, sr * 0.4)
        b, a = _low_shelf_biquad(sr, f0, delta, q=q)
    else:
        f0 = float(np.sqrt(max(lo, 10.0) * min(hi, sr * 0.45)))
        b, a = _peaking_biquad(sr, f0, delta, q=q)

    filtered = apply_biquad(audio, b, a)
    info = {
        "track": "",  # filled by the caller (file name)
        "band": bc.band,
        "range_hz": [float(x) for x in bc.freq_range],
        "delta_db": round(delta, 2),
    }
    return filtered, info


def _band_eq(
    audio: np.ndarray, sr: int, eq_specs: list[dict], max_db: float = 12.0
) -> np.ndarray:
    """Apply per-band gain to a stereo signal.

    Each band is isolated with a 4th-order Butterworth band-pass, gained, and
    added back in parallel with the rest of the signal (graphic-EQ style).
    eq_specs: list of {"band": name, "freq_range": [lo, hi], "gain_db": x}.
    """
    out = audio.copy()
    for spec in eq_specs:
        delta = float(np.clip(spec.get("gain_db", 0.0), -max_db, max_db))
        if abs(delta) < 0.5:
            continue
        lo, hi = spec["freq_range"]
        sos = butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
        band = sosfiltfilt(sos, audio, axis=0)
        gain = 10 ** (delta / 20.0)
        out = out + (band * (gain - 1.0))
    return out


def _pan_gains(pan: float) -> tuple[float, float]:
    """Equal-power pan: pan in [-1, 1] -> (left_gain, right_gain)."""
    angle = (float(np.clip(pan, -1.0, 1.0)) + 1.0) * np.pi / 4.0
    return float(np.cos(angle)), float(np.sin(angle))


# _apply_width, _apply_side_gain — imported from dsp._utils


def _apply_eq_nodes(
    audio: np.ndarray, sr: int, nodes: list[dict], max_db: float = MAX_TRACK_EQ_DB
) -> np.ndarray:
    """Apply planner-style EQ nodes [{hz, gain_db, q, type}] as biquads.

    Reuses the RBJ designs from reference.py; type is "peaking" (default),
    "low_shelf" or "high_shelf". Gains are clamped for safety.
    """
    for node in nodes:
        delta = float(np.clip(node.get("gain_db", 0.0), -max_db, max_db))
        if abs(delta) < 0.3:
            continue
        f0 = float(np.clip(node.get("hz", 1000.0), 20.0, sr * 0.45))
        q = float(node.get("q", 1.0))
        ntype = node.get("type", "peaking")
        if ntype == "low_shelf":
            b, a = _low_shelf_biquad(sr, f0, delta, q=q)
        elif ntype == "high_shelf":
            b, a = _high_shelf_biquad(sr, f0, delta, q=q)
        else:
            b, a = _peaking_biquad(sr, f0, delta, q=q)
        audio = apply_biquad(audio, b, a)
    return audio


def _sidechain_gain(
    sidechain_signal: np.ndarray,
    sr: int,
    amount_db: float,
    attack_ms: float = 4.0,
    release_ms: float = 140.0,
) -> np.ndarray:
    """Ducking gain curve (0..1) driven by the sidechain signal.

    When the trigger hits, gain drops to ~10^(-amount/20) with a fast attack
    (max-filter) and a smooth exponential release. Returns a per-sample gain
    array of the same length as the signal.
    """
    mono = np.abs(
        sidechain_signal.mean(axis=1) if sidechain_signal.ndim > 1 else sidechain_signal
    )
    # amount_db is "duck by this many dB" (sign-agnostic: -4.0 or 4.0 both = -4 dB).
    floor = 10 ** (-abs(amount_db) / 20.0)

    attack = max(int(attack_ms / 1000.0 * sr), 1)
    env = _sliding_max(mono, attack)

    release = max(int(release_ms / 1000.0 * sr), 1)
    alpha = 1.0 - np.exp(-1.0 / release)
    peak = float(np.max(env)) + 1e-12
    target = 1.0 - (1.0 - floor) * np.minimum(env / peak, 1.0)

    # Instant duck + exponential recovery, fully vectorized:
    #   sm = one-pole smoothing of the target (slow recover)
    #   gain = min(target, sm)  -> follows drops instantly, releases smoothly.
    # The filter is primed with y[-1] = 1.0 via `zi` so it starts from unity
    # (no fade-in from zero).
    sm, _ = lfilter(
        [alpha],
        [1.0, -(1.0 - alpha)],
        target,
        zi=np.array([1.0 - alpha]),
    )
    gain = np.minimum(target, sm)
    return gain


def _band_duck(
    audio: np.ndarray,
    sr: int,
    band_range: list[float],
    duck_curve: np.ndarray,
) -> np.ndarray:
    """Dynamic-EQ ducking: attenuate only a frequency band of the signal.

    The band is isolated, multiplied by the duck gain curve, and re-added, so
    everything outside the band keeps its level. This lets the snare "borrow"
    the 100-300 Hz space from bass/sub without killing their top end.
    """
    lo, hi = band_range
    sos = butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
    band = sosfiltfilt(sos, audio, axis=0)
    duck2d = np.stack([duck_curve, duck_curve], axis=1)
    ducked_band = band * duck2d
    return audio - band + ducked_band


# _true_peak_db — imported from dsp._utils


def _dither(audio: np.ndarray, bits: int = 16) -> np.ndarray:
    """Add a dithering noise floor before truncation to the target bit depth.

    Without dither, PCM_16 truncation of quiet material produces harmonic
    distortion/zipper noise. TPDF dither decorrelates the quantization error.
    """
    peak_scale = 2 ** (bits - 1)
    rng = np.random.default_rng(0)
    tpdf = rng.uniform(-0.5, 0.5, audio.shape) + rng.uniform(-0.5, 0.5, audio.shape)
    return audio + tpdf / peak_scale


def _highpass(audio: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    """Butterworth high-pass so non-bass elements stop polluting the low end."""
    sos = butter(4, cutoff_hz, btype="highpass", fs=sr, output="sos")
    return sosfiltfilt(sos, audio, axis=0)


def _delay(
    audio: np.ndarray,
    sr: int,
    time_ms: float = 180.0,
    feedback: float = 0.3,
    amount: float = 0.25,
) -> np.ndarray:
    """Feedback delay (echo). Returns dry/wet mix, stereo-safe."""
    d = max(int(time_ms / 1000.0 * sr), 1)
    fb = float(np.clip(feedback, 0.0, 0.9))
    wet = np.zeros_like(audio)
    gain = 1.0
    shift = d
    while gain > 1e-4 and shift < audio.shape[0]:
        if shift < audio.shape[0]:
            wet[shift:] += gain * audio[:-shift]
        gain *= fb
        shift += d
    return (1.0 - amount) * audio + amount * wet


def _reverb(
    audio: np.ndarray,
    sr: int,
    amount: float = 0.2,
    decay: float = 0.4,
    tone: float = 0.5,
) -> np.ndarray:
    """Schroeder reverb (parallel combs + serial allpasses), vectorized.

    Cheap but musical room/plate tail with no external IRs. `amount` is the
    dry/wet balance, `decay` the feedback (tail length), `tone` darkens the
    tail by low-passing the wet bus.
    """
    comb_times = [0.0231, 0.0273, 0.0319, 0.0379]
    allpass_times = [0.0050, 0.0017]
    fb = float(np.clip(decay, 0.0, 0.9))

    def echo_bus(sig: np.ndarray, d: int, g: float) -> np.ndarray:
        # Repeated echoes y = sum g^k * x[n - k*d] (equivalent to a comb with
        # feedback g), computed vectorized in O(N * num_taps).
        out = np.zeros_like(sig)
        gain = 1.0
        shift = d
        while gain > 1e-4 and shift < sig.shape[0]:
            out[shift:] += gain * sig[:-shift]
            gain *= g
            shift += d
        return out

    wet = sum(echo_bus(audio, int(t * sr), fb) for t in comb_times) / len(comb_times)

    def allpass(sig: np.ndarray, d: int, g: float = 0.5) -> np.ndarray:
        # y = (1-g)*x + g*y[n-d]  ->  forward + (1-g) trailing echoes.
        out = (1.0 - g) * sig
        gain = g
        shift = d
        while gain > 1e-4 and shift < sig.shape[0]:
            out[shift:] += (1.0 - g) * gain * sig[:-shift]
            gain *= g
            shift += d
        return out

    for t in allpass_times:
        wet = allpass(wet, int(t * sr))

    # Tone: darken the tail via a one-pole low-pass tuned by `tone`.
    tone = float(np.clip(tone, 0.0, 1.0))
    if tone < 0.98:
        cutoff = 20000.0 * (0.35 + 0.65 * tone)  # ~7k..20k Hz
        sos = butter(2, min(cutoff, 0.49 * sr), btype="lowpass", fs=sr, output="sos")
        wet = sosfiltfilt(sos, wet, axis=0)

    wet = wet / (1.0 + fb * 2.0)
    return (1.0 - amount) * audio + amount * wet


def _apply_space(audio: np.ndarray, sr: int, cfg: dict) -> np.ndarray:
    """Apply per-role space FX (reverb / delay) from the profile config."""
    if not cfg:
        return audio
    if "delay" in cfg:
        delay_cfg = cfg["delay"]
        audio = _delay(
            audio,
            sr,
            time_ms=float(delay_cfg.get("time_ms", 180.0)),
            feedback=float(delay_cfg.get("feedback", 0.3)),
            amount=float(delay_cfg.get("amount", 0.25)),
        )
    if "reverb" in cfg:
        rev_cfg = cfg["reverb"]
        audio = _reverb(
            audio,
            sr,
            amount=float(rev_cfg.get("amount", 0.2)),
            decay=float(rev_cfg.get("decay", 0.4)),
            tone=float(rev_cfg.get("tone", 0.5)),
        )
    return audio


def _soft_clip(audio: np.ndarray, drive_db: float, amount: float = 1.0) -> np.ndarray:
    """Tanh soft clipper: adds the loudness without the hard distortion of a
    brickwall limiter. Mix `amount` of the clipped signal with the dry one."""
    drive = 10 ** (drive_db / 20.0)
    x = audio * drive
    clipped = np.tanh(x)
    # Normalize back so the clip doesn't just reduce overall level.
    clipped = clipped / float(np.tanh(1.0))
    return (1.0 - amount) * audio + amount * clipped


# _compressor, _moving_average, _sliding_max — imported from dsp._utils


def _limit_peaks(audio: np.ndarray, sr: int, ceiling_db: float = -1.0) -> np.ndarray:
    """True-peak lookahead limiter with ITU-R BS.1770 / EBU R128 oversampled peak control."""
    try:
        from .dsp.limiter import LimiterConfig, apply_true_peak_limiter

        return apply_true_peak_limiter(
            audio, sr, LimiterConfig(ceiling_dbtp=ceiling_db)
        )
    except Exception:
        up = resample_poly(audio, 4, 1, axis=0)
        up_sr = sr * 4
        ceiling = 10 ** ((ceiling_db - 0.5) / 20.0)
        lookahead = max(int(0.01 * up_sr), 1)
        env = _sliding_max(np.abs(up), lookahead)
        gain = np.minimum(ceiling / (env + 1e-12), 1.0)
        pad = np.full((lookahead,) + gain.shape[1:], 1.0, dtype=gain.dtype)
        gain = np.concatenate([pad, gain[:-lookahead]], axis=0)
        release = max(int(0.05 * up_sr), 1)
        gain = _moving_average(gain, release)
        out_up = up * gain
        out_up_clipped = np.clip(out_up, -ceiling, ceiling)
        return resample_poly(out_up_clipped, 1, 4, axis=0)


def _apply_user_eq_bands(
    audio: np.ndarray, sr: int, eq_bands: list[dict] | None
) -> np.ndarray:
    """Apply interactive user-configured EQ bands (peaking, shelves, cuts) to audio."""
    if not eq_bands:
        return audio
    out = audio.copy()
    for b in eq_bands:
        if not b.get("enabled", True):
            continue
        b_type = b.get("type", "bell")
        freq = float(b.get("freq", 1000.0))
        gain = float(b.get("gain", 0.0))
        q = float(b.get("q", 1.0))
        if abs(gain) < 0.05 and b_type not in ("low_cut", "high_cut"):
            continue
        nyquist = sr * 0.5
        if b_type == "bell":
            b_coeff, a_coeff = _peaking_biquad(sr, freq, gain, q=q)
            out = apply_biquad(out, b_coeff, a_coeff)
        elif b_type == "low_shelf":
            b_coeff, a_coeff = _low_shelf_biquad(sr, freq, gain, q=q)
            out = apply_biquad(out, b_coeff, a_coeff)
        elif b_type == "high_shelf":
            b_coeff, a_coeff = _high_shelf_biquad(sr, freq, gain, q=q)
            out = apply_biquad(out, b_coeff, a_coeff)
        elif b_type == "low_cut":
            sos = butter(2, max(20.0, freq) / nyquist, btype="highpass", output="sos")
            out = sosfiltfilt(sos, out, axis=0)
        elif b_type == "high_cut":
            sos = butter(
                2, min(sr * 0.45, freq) / nyquist, btype="lowpass", output="sos"
            )
            out = sosfiltfilt(sos, out, axis=0)
        else:
            b_coeff, a_coeff = _peaking_biquad(sr, freq, gain, q=q)
            out = apply_biquad(out, b_coeff, a_coeff)
    return out


def _normalize_to_lufs(
    audio: np.ndarray, sr: int, target_lufs: float, ceiling_dbtp: float = -1.0
) -> np.ndarray:
    """Iterate gain -> limit until integrated loudness reaches the target.
    The limiter keeps the true peak under the ceiling, so the final result is
    clipping-free at both the sample level and between samples."""
    meter = pyln.Meter(sr)
    best = audio
    best_err = float("inf")
    for _ in range(6):
        current = meter.integrated_loudness(best)
        if np.isfinite(current) and current > -70.0:
            err = target_lufs - current
            if abs(err) < 0.3:
                break
            if abs(err) < abs(best_err):
                best_err = err
            gain = 10 ** (err / 20.0)
            best = _limit_peaks(best * gain, sr, ceiling_db=ceiling_dbtp)
    # Final true-peak safety: overshoot from resampling can push intersample
    # peaks above the ceiling, so trim by the measured true peak if needed.
    ceiling_lin = 10 ** (ceiling_dbtp / 20.0)
    tp = 10 ** (_true_peak_db(best, sr) / 20.0)
    if tp > ceiling_lin:
        best = best * (ceiling_lin / tp)
    return best


@dataclass
class PreviewOptions:
    """All optional knobs for ``render_preview_mix``.

    Grouped into a dataclass so callers (API, CLI, tests) don't need to
    remember 20+ keyword arguments.  Every field has a safe default so
    ``PreviewOptions()`` produces a valid no-op config.
    """

    # Output
    output_path: str | None = None
    max_duration: float | None = None

    # Per-track gain / sidechain
    manual_gain: dict[str, float] | None = None
    sidechain_db: float | None = None
    sidechain_config: dict | None = None

    # Reference match-EQ
    reference_path: str | None = None
    reference_match_bands: list[dict] | None = None

    # Debug / comparison
    render_before: bool = False

    # Planner integration
    apply_plan: bool = False

    # DSP chain configs
    multiband_config: dict | None = None
    limiter_ceiling_db: float | None = None
    dynamic_eq_config: dict | None = None
    midside_eq_config: dict | None = None
    transient_config: dict | None = None
    deesser_config: dict | None = None
    eq_bands: list[dict] | None = None

    # Per-track spatial / transient
    spatial_configs: dict[str, dict] | None = None
    transient_configs: dict[str, dict] | None = None

    # Progress reporting
    progress_callback: Callable[[str, int, str], None] | None = None


def render_preview_mix(
    render_dir: str,
    profile: StyleProfile,
    pattern: str = "*.wav",
    options: PreviewOptions | None = None,
    output_path: str | None = None,
    max_duration: float | None = None,
    manual_gain: dict[str, float] | None = None,
    sidechain_db: float | None = None,
    reference_path: str | None = None,
    render_before: bool = False,
    apply_plan: bool = False,
    multiband_config: dict | None = None,
    limiter_ceiling_db: float | None = None,
    dynamic_eq_config: dict | None = None,
    midside_eq_config: dict | None = None,
    transient_config: dict | None = None,
    sidechain_config: dict | None = None,
    deesser_config: dict | None = None,
    eq_bands: list[dict] | None = None,
    spatial_configs: dict[str, dict] | None = None,
    transient_configs: dict[str, dict] | None = None,
    reference_match_bands: list[dict] | None = None,
    progress_callback: Callable[[str, int, str], None] | None = None,
) -> dict[str, Any]:
    """Apply corrections to the rendered tracks and bounce a preview WAV.

    Args:
        max_duration: cap the preview length in seconds. When the renders have
            mismatched lengths (e.g. loops vs full arrangement), pass this so
            the preview stays a tight section instead of stretching to the
            longest file. If None, every track is trimmed to the SHORTEST
            render so all of them line up and play together.
        manual_gain: extra per-file volume in dB, keyed by the render file name
            without extension (e.g. {"snt2": -4.0} lowers that track by 4 dB).
        sidechain_db: duck all non-snare tracks by this many dB whenever a
            snare hits (light sidechain pump). Pass a negative value like -4.0.
            None disables it.
        reference_path: optional WAV of a reference track. When given, a
            match-EQ curve (mix spectrum vs reference spectrum, shape only)
            is computed from the summed parts and applied before mastering.
            The result dict then contains "match_eq" with the curve points.
        render_before: when True, additionally bounce a "before" version —
            same common trim, plain unity-gain sum of the loaded tracks (no
            EQ / sidechain / mastering), peak-normalized to -1 dBTP with the
            same true-peak limiter — written next to the main output as
            ``<stem>_before.wav`` and reported via "before_path".
        apply_plan: when True, build a planner.Plan and drive the render from
            it: mix_actions replace the default per-track gain/pan/width/EQ
            hints, master_actions are applied to the summed mix BEFORE the
            fixed mastering chain (sidechain / bus comp / soft clip stay).
            If the plan carries a loudness move, it replaces the iterative
            loudness normalize (single gain + limiter, no double handling).
            The result dict then contains "plan" with both action columns.
            The "before" bounce (if requested) stays fully raw regardless.

    Returns:
        Dict with the usual preview metadata plus:
          - "eq_applied": list of {track, band, range_hz, delta_db} entries
            for every spectral correction that was actually sounded,
          - "match_eq": {"reference_path", "curve"} when reference_path given,
          - "before_path": path of the before-bounce when render_before is set,
          - "plan": {"mix_actions", "master_actions", "summary"} when
            apply_plan is set.
    """
    # Merge PreviewOptions into individual kwargs (options wins if set).
    if options is not None:
        output_path = options.output_path or output_path
        max_duration = (
            options.max_duration if options.max_duration is not None else max_duration
        )
        manual_gain = options.manual_gain or manual_gain
        sidechain_db = (
            options.sidechain_db if options.sidechain_db is not None else sidechain_db
        )
        sidechain_config = options.sidechain_config or sidechain_config
        reference_path = options.reference_path or reference_path
        reference_match_bands = options.reference_match_bands or reference_match_bands
        render_before = options.render_before or render_before
        apply_plan = options.apply_plan or apply_plan
        multiband_config = options.multiband_config or multiband_config
        limiter_ceiling_db = (
            options.limiter_ceiling_db
            if options.limiter_ceiling_db is not None
            else limiter_ceiling_db
        )
        dynamic_eq_config = options.dynamic_eq_config or dynamic_eq_config
        midside_eq_config = options.midside_eq_config or midside_eq_config
        transient_config = options.transient_config or transient_config
        deesser_config = options.deesser_config or deesser_config
        eq_bands = options.eq_bands or eq_bands
        spatial_configs = options.spatial_configs or spatial_configs
        transient_configs = options.transient_configs or transient_configs
        progress_callback = options.progress_callback or progress_callback

    # Per-profile manual gain (from the style) overridden by the caller's.
    effective_manual_gain = dict(profile.manual_gain or {})
    if manual_gain:
        effective_manual_gain.update(manual_gain)

    if output_path is None:
        output_path = os.path.join(render_dir, f"preview_{profile.name}.wav")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    _log.info(
        "Starting preview render: style=%s, dir=%s, output=%s",
        profile.name,
        render_dir,
        output_path,
    )

    if progress_callback:
        progress_callback("analyzing", 5, "Analyzing tracks…")

    with Timer("analyze_directory", _log):
        analyses = analyze_directory(render_dir, pattern)
    if not analyses:
        raise ValueError(f"No {pattern} files found in {render_dir}")

    _log.info("Found %d tracks, computing mix…", len(analyses))

    if progress_callback:
        progress_callback("mixing", 10, f"Computing mix for {len(analyses)} tracks…")

    with Timer("compute_mix", _log):
        mix = compute_mix(
            analyses, profile, [a.name for a in analyses], use_planner=apply_plan
        )

    # Planner: classify actions into mixing (per-track) vs mastering (bus).
    plan: Any | None = None
    plan_by_track: dict[str, dict[str, list[dict]]] = {}
    if apply_plan:
        from .planner import build_plan

        plan = build_plan(analyses, profile, mix)
        for act in plan.mix_actions:
            bucket = plan_by_track.setdefault(act["track"], {})
            bucket.setdefault(act["kind"], []).append(act)

    # Track indices in the analyses list == indices in the mix corrections.
    stereo_parts: list[np.ndarray] = []
    raw_parts: list[np.ndarray] = []  # untouched loads, for the "before" bounce
    eq_applied: list[dict[str, Any]] = []
    used_sr = None
    total_tracks = len(analyses)
    _log.info("Processing %d tracks…", total_tracks)
    for track_idx, (analysis, corr) in enumerate(
        zip(analyses, mix.track_corrections, strict=False)
    ):
        if progress_callback:
            pct = 15 + int(25 * track_idx / max(total_tracks, 1))
            progress_callback(
                "applying_eq",
                pct,
                f"Track {track_idx + 1}/{total_tracks}: {analysis.name}",
            )

        audio, sr = sf.read(analysis.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        used_sr = sr
        raw_parts.append(np.asarray(audio, dtype=np.float64).copy())

        role_eq = (profile.role_eq or {}).get(corr.role)
        if role_eq:
            audio = _band_eq(audio, sr, role_eq)

        # High-pass non-bass elements so low-end pollution is removed.
        hpf_hz = (profile.highpass or {}).get(corr.role)
        if hpf_hz and float(hpf_hz) > 0:
            audio = _highpass(audio, sr, float(hpf_hz))

        # Cut the 200-500 Hz "mud" on low-end / drums for cleanliness.
        mud = (profile.mud_cut or {}).get(corr.role)
        if mud:
            audio = _band_eq(audio, sr, [mud])

        # Sound the engine's spectral corrections as real biquad EQ. With a
        # plan, drive from plan mix_actions instead (master-promoted bands
        # were already stripped from corr.band_corrections by use_planner).
        track_acts = plan_by_track.get(analysis.name, {}) if plan is not None else {}
        if plan is not None:
            for act in track_acts.get("eq", []):
                params = act["params"]
                for node in params.get("nodes", []):
                    audio = _apply_eq_nodes(audio, sr, [node])
                    eq_applied.append(
                        {
                            "track": analysis.name,
                            "band": params.get("band", ""),
                            "range_hz": [
                                float(x)
                                for x in params.get(
                                    "freq_range",
                                    [node.get("hz", 0.0), node.get("hz", 0.0)],
                                )
                            ],
                            "delta_db": round(
                                float(
                                    np.clip(
                                        node.get("gain_db", 0.0),
                                        -MAX_TRACK_EQ_DB,
                                        MAX_TRACK_EQ_DB,
                                    )
                                ),
                                2,
                            ),
                        }
                    )
        else:
            for bc in corr.band_corrections:
                audio, eq_info = _apply_band_correction(audio, sr, bc)
                eq_info["track"] = analysis.name
                eq_applied.append(eq_info)

        # Space FX (reverb / delay) per role.
        space_cfg = (profile.space or {}).get(corr.role)
        if space_cfg:
            audio = _apply_space(audio, sr, space_cfg)

        # Per-track compression from the profile (e.g. breaks, bass, kick).
        track_comp = (profile.compression or {}).get(corr.role)
        if track_comp:
            audio = _compressor(
                audio,
                sr,
                threshold_db=float(track_comp.get("threshold_db", -12.0)),
                ratio=float(track_comp.get("ratio", 3.0)),
                attack_ms=float(track_comp.get("attack_ms", 10.0)),
                release_ms=float(track_comp.get("release_ms", 120.0)),
                makeup_db=float(track_comp.get("makeup_db", 0.0)),
            )

        # DSP processing: dynamic EQ, mid/side EQ, transient shaper.
        if dynamic_eq_config:
            from .dsp.dynamic_eq import apply_dynamic_eq
            from .dsp.dynamic_eq import config_from_dict as deq_cfg

            audio = apply_dynamic_eq(audio, sr, deq_cfg(dynamic_eq_config))
        if midside_eq_config:
            from .dsp.midside_eq import apply_midside_eq
            from .dsp.midside_eq import config_from_dict as ms_cfg

            audio = apply_midside_eq(audio, sr, ms_cfg(midside_eq_config))
        if transient_config:
            from .dsp.transient import apply_transient_shaper
            from .dsp.transient import config_from_dict as ts_cfg

            audio = apply_transient_shaper(audio, sr, ts_cfg(transient_config))
        if deesser_config:
            from .dsp.deesser import apply_deesser
            from .dsp.deesser import config_from_dict as deess_cfg

            audio = apply_deesser(audio, sr, deess_cfg(deesser_config))
        # Per-track Binaural 3D Head Spatializer:
        sp_cfg_dict = None
        if spatial_configs:
            sp_cfg_dict = spatial_configs.get(analysis.name) or spatial_configs.get(
                os.path.splitext(os.path.basename(analysis.path))[0]
            )
        if sp_cfg_dict is None and corr.spatial_config:
            sp_cfg_dict = corr.spatial_config

        if sp_cfg_dict and sp_cfg_dict.get("enabled", True):
            from .dsp.spatializer import apply_binaural_spatializer
            from .dsp.spatializer import config_from_dict as sp_cfg

            audio = apply_binaural_spatializer(audio, sr, sp_cfg(sp_cfg_dict))
        if transient_configs:
            tr_cfg_dict = transient_configs.get(analysis.name) or transient_configs.get(
                os.path.splitext(os.path.basename(analysis.path))[0]
            )
            if tr_cfg_dict:
                from .dsp.transient import apply_transient_shaper
                from .dsp.transient import config_from_dict as ts_cfg_dict

                audio = apply_transient_shaper(audio, sr, ts_cfg_dict(tr_cfg_dict))

        # Gain / pan: with a plan, take them from the plan's mix_actions
        # (they mirror the corrections; plan wins to avoid divergence).
        if plan is not None:
            gain_acts = track_acts.get("gain") or []
            volume_db = (
                gain_acts[0]["params"]["gain_db"]
                if gain_acts
                else (corr.volume_db or 0.0)
            )
            pan_acts = track_acts.get("pan") or []
            pan_value = pan_acts[0]["params"]["pan"] if pan_acts else corr.pan
        else:
            volume_db = corr.volume_db or 0.0
            pan_value = corr.pan

        gain = 10 ** (volume_db / 20.0)
        gain *= 10 ** (effective_manual_gain.get(analysis.name, 0.0) / 20.0)
        if pan_value is not None:
            lg, rg = _pan_gains(pan_value)
            left, right = audio[:, 0] * lg, audio[:, 1] * rg
        else:
            left, right = audio[:, 0], audio[:, 1]
        # Stereo width per role (mono/wide/very_wide) via mid/side. With a
        # plan the width action (if any) replaces the profile default.
        part = np.stack([left, right], axis=1)
        role_cfg = profile.track_balance.get(corr.role) or {}
        width_str = role_cfg.get("width", "moderate")
        if plan is not None:
            width_acts = track_acts.get("width") or []
            if width_acts:
                width_str = width_acts[0]["params"]["width"]
        part = _apply_width(part, width_str)
        stereo_parts.append(part * gain)

    # Align every part to a common length so nothing plays on its own after the
    # rest has ended. Prefer the shortest render, or cap at max_duration.
    shortest = min(p.shape[0] for p in stereo_parts)
    if max_duration is not None:
        common = min(shortest, int(max_duration * used_sr))
    else:
        common = shortest
    stereo_parts = [p[:common] for p in stereo_parts]

    # Sidechain from the profile: kick ducks the low end, snare ducks the
    # 100-300 Hz band of bass/sub (dynamic EQ) so bass and snare stop fighting.
    if progress_callback:
        progress_callback("sidechain", 55, "Applying sidechain ducking…")

    profile_sidechain = profile.sidechain or {}
    duck_kick = profile_sidechain.get("kick")
    duck_snare_band = profile_sidechain.get("snare_band")

    kick_idxs = [i for i, c in enumerate(mix.track_corrections) if c.role == "kick"]
    snare_idxs = [i for i, c in enumerate(mix.track_corrections) if c.role == "snare"]

    kick_duck: np.ndarray | None = None
    snare_band_duck: np.ndarray | None = None

    if used_sr:
        if duck_kick and kick_idxs:
            trigger = sum(stereo_parts[i] for i in kick_idxs)
            kick_duck = _sidechain_gain(
                trigger,
                used_sr,
                float(duck_kick.get("amount_db", -3.0)),
                attack_ms=float(duck_kick.get("attack_ms", 5.0)),
                release_ms=float(duck_kick.get("release_ms", 90.0)),
            )
        if duck_snare_band and snare_idxs:
            trigger = sum(stereo_parts[i] for i in snare_idxs)
            snare_band_duck = _sidechain_gain(
                trigger,
                used_sr,
                float(duck_snare_band.get("amount_db", -4.0)),
                attack_ms=float(duck_snare_band.get("attack_ms", 3.0)),
                release_ms=float(duck_snare_band.get("release_ms", 120.0)),
            )

        # Legacy flat sidechain: duck everything except the snare role.
        if sidechain_db is not None and snare_idxs:
            trigger = sum(stereo_parts[i] for i in snare_idxs)
            flat = _sidechain_gain(trigger, used_sr, float(sidechain_db))
            flat2d = np.stack([flat, flat], axis=1)
            for i in range(len(stereo_parts)):
                if i not in snare_idxs:
                    stereo_parts[i] = stereo_parts[i] * flat2d

        # Kick sidechain: duck the low-end targets under every kick hit.
        if kick_duck is not None:
            targets = set(duck_kick.get("targets", ["bass", "sub_bass", "wobble"]))
            duck2d = np.stack([kick_duck, kick_duck], axis=1)
            for i, corr in enumerate(mix.track_corrections):
                if corr.role in targets and i not in kick_idxs:
                    stereo_parts[i] = stereo_parts[i] * duck2d

        # Snare band sidechain: dynamic EQ — duck only the 100-300 Hz band of
        # bass/sub when the snare hits, leaving the rest of their spectrum.
        if snare_band_duck is not None:
            targets = set(duck_snare_band.get("targets", ["bass", "sub_bass"]))
            band_range = [
                float(x) for x in duck_snare_band.get("band_range", [100, 300])
            ]
            for i, corr in enumerate(mix.track_corrections):
                if corr.role in targets and i not in snare_idxs:
                    stereo_parts[i] = _band_duck(
                        stereo_parts[i], used_sr, band_range, snare_band_duck
                    )

    # User-configurable sidechain: applied on top of the profile sidechain.
    if sidechain_config and sidechain_config.get("enabled") and used_sr:
        from .dsp.sidechain import apply_sidechain
        from .dsp.sidechain import config_from_dict as sc_cfg

        sc = sc_cfg(sidechain_config)
        trigger_role = sc.trigger
        trigger_idxs = [
            i for i, c in enumerate(mix.track_corrections) if c.role == trigger_role
        ]
        if trigger_idxs:
            trigger_audio = sum(stereo_parts[i] for i in trigger_idxs)
            target_idxs = [
                i
                for i, c in enumerate(mix.track_corrections)
                if c.role in sc.targets and i not in trigger_idxs
            ]
            for i in target_idxs:
                stereo_parts[i] = apply_sidechain(
                    stereo_parts[i], used_sr, trigger_audio, sc
                )

    # Sum, then master: soft clip (if enabled) -> loudness normalize (TP-safe).
    if progress_callback:
        progress_callback("mastering", 70, "Mastering: bus compression + limiting…")

    mixdown = np.zeros((common, 2), dtype=np.float64)
    for part in stereo_parts:
        mixdown += part

    # Plan mastering moves on the bus: applied BEFORE the fixed chain
    # (sidechain already ran per-part; bus comp / soft clip / limiter come
    # after). Loudness is deferred: it must land after the comp/clip stages.
    plan_loudness: dict[str, Any] | None = None
    if plan is not None:
        for act in plan.master_actions:
            if act["kind"] == "eq":
                mixdown = _apply_eq_nodes(
                    mixdown, used_sr, act["params"].get("nodes", [])
                )
            elif act["kind"] == "width":
                mixdown = _apply_side_gain(
                    mixdown, float(act["params"].get("side_gain", 1.0))
                )
            elif act["kind"] in ("loudness", "gain"):
                plan_loudness = act

    # Match EQ toward the reference: computed from the summed parts BEFORE
    # any mastering so the curve describes the raw balance of the mix.
    match_eq_info: dict[str, Any] | None = None
    if reference_path:
        ref_audio, ref_sr = load_audio_stereo(reference_path)
        curve = compute_match_curve(used_sr, mixdown, ref_sr, ref_audio)
        mixdown = apply_match_eq(mixdown, used_sr, curve)
        match_eq_info = {
            "reference_path": os.path.abspath(reference_path),
            "curve": curve,
        }

    # "Before" bounce: plain unity-gain sum of the loaded tracks on the same
    # common trim — no EQ / sidechain / mastering. Peak-normalized to -1 dBTP
    # with the same true-peak limiter so it never clips.
    before_path: str | None = None
    if render_before:
        base, ext = os.path.splitext(output_path)
        before_path = f"{base}_before{ext or '.wav'}"
        raw_sum = np.zeros((common, 2), dtype=np.float64)
        for rp in raw_parts:
            raw_sum += rp[:common]
        peak_lin = float(np.max(np.abs(raw_sum))) + 1e-12
        scaled = raw_sum * (10 ** (-1.0 / 20.0)) / peak_lin
        sf.write(
            before_path,
            _dither(_limit_peaks(scaled, used_sr, ceiling_db=-1.0)),
            used_sr,
            subtype="PCM_16",
        )

    mcfg = profile.master or {}
    # Glue compression on the summed mix (from the profile's "bus" block).
    bus_comp = (profile.compression or {}).get("bus")
    if bus_comp:
        mixdown = _compressor(
            mixdown,
            used_sr,
            threshold_db=float(bus_comp.get("threshold_db", -14.0)),
            ratio=float(bus_comp.get("ratio", 2.0)),
            attack_ms=float(bus_comp.get("attack_ms", 12.0)),
            release_ms=float(bus_comp.get("release_ms", 130.0)),
            makeup_db=float(bus_comp.get("makeup_db", 0.0)),
        )

    # Multiband compression (user-configurable, goes after bus comp).
    if multiband_config:
        from .multiband import apply_multiband, config_from_dict

        mb_cfg = config_from_dict(multiband_config)
        mixdown = apply_multiband(mixdown, used_sr, mb_cfg)

    # AI Reference Match EQ bands
    if reference_match_bands:
        mixdown = _apply_user_eq_bands(mixdown, used_sr, reference_match_bands)

    # User-defined interactive Master EQ bands (from UI / MCP)
    if eq_bands:
        mixdown = _apply_user_eq_bands(mixdown, used_sr, eq_bands)

    if mcfg.get("soft_clip"):
        mixdown = _soft_clip(
            mixdown,
            float(mcfg.get("soft_clip_drive_db", 2.0)),
            amount=float(mcfg.get("soft_clip_amount", 0.7)),
        )

    ceiling_dbtp = (
        float(limiter_ceiling_db)
        if limiter_ceiling_db is not None
        else float(mcfg.get("ceiling_dbtp", -1.0))
    )
    if plan is not None and plan_loudness is not None:
        # Plan-driven loudness: one deliberate gain move + true-peak limiter.
        # No iterative normalize, so the plan's gain isn't second-guessed.
        mixdown = mixdown * 10 ** (float(plan_loudness["params"]["gain_db"]) / 20.0)
        mixdown = _limit_peaks(mixdown, used_sr, ceiling_db=ceiling_dbtp)
    else:
        mixdown = _normalize_to_lufs(
            mixdown,
            used_sr,
            profile.target_lufs,
            ceiling_dbtp=ceiling_dbtp,
        )
    peak = float(np.max(np.abs(mixdown)))
    true_peak_db = _true_peak_db(mixdown, used_sr)

    if progress_callback:
        progress_callback("rendering", 95, "Writing output WAV…")

    sf.write(output_path, _dither(mixdown), used_sr, subtype="PCM_16")

    result: dict[str, Any] = {
        "style": profile.name,
        "output_path": output_path,
        "sample_rate": used_sr,
        "duration_s": round(common / used_sr, 2),
        "channels": 2,
        "target_lufs": profile.target_lufs,
        "peak_db": round(20 * np.log10(peak + 1e-12), 1),
        "true_peak_dbtp": round(true_peak_db, 1),
        "eq_applied": eq_applied,
        "match_eq": match_eq_info,
        "sidechain": {
            "kick": {"targets": list(duck_kick.get("targets", []))}
            if duck_kick
            else None,
            "snare_band": {
                "targets": list(duck_snare_band.get("targets", [])),
                "band_range": [
                    float(x) for x in duck_snare_band.get("band_range", [100, 300])
                ],
            }
            if duck_snare_band
            else None,
        },
        "tracks_used": [
            {
                "file": a.name,
                "role": c.role,
                "volume_db": c.volume_db,
                "manual_gain_db": effective_manual_gain.get(a.name, 0.0),
                "pan": c.pan,
            }
            for a, c in zip(analyses, mix.track_corrections, strict=False)
        ],
        "master_notes": mix.master_notes,
    }
    if before_path is not None:
        result["before_path"] = before_path
    if plan is not None:
        result["plan"] = plan.to_dict()

    if progress_callback:
        progress_callback("done", 100, "")

    _log.info(
        "Preview complete: %s, duration=%.1fs, LUFS≈%.1f, peak=%.1f dB, true_peak=%.1f dBTP",
        profile.name,
        common / used_sr,
        profile.target_lufs,
        20 * np.log10(peak + 1e-12),
        true_peak_db,
    )

    # Auto-save to RAG reference store for future recommendations
    try:
        from .reference_store import save_mix_to_references

        save_mix_to_references(
            analyses, mix, genre=profile.name, source=f"preview_{profile.name}"
        )
    except Exception as exc:
        _log.warning("Failed to save mix to reference store: %s", exc)

    return result
