"""Offline mix preview: apply the computed corrections to the rendered WAVs
and bounce a stereo preview mix that can be listened to without Ableton.

This mirrors what auto_mix does on the Live set, but applies the level/pan
corrections to the audio files directly, sums them, and normalizes the result
to the style's target loudness.
"""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.ndimage import convolve1d
from scipy.signal import butter, lfilter, resample_poly, sosfiltfilt
from .analyzer import analyze_directory
from .mixer import compute_mix, match_role_with_spectrum
from .profiles import StyleProfile

PAN_LAW_DB = -3.0  # equal-power-ish center attenuation


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


# Mid/side width multipliers: how much the side channel is scaled (linear).
# mono=0 (fold to mid), moderate=1.2, wide=1.8, very_wide=2.5.
_WIDTH_GAIN = {
    "mono": 0.0,
    "moderate": 1.2,
    "wide": 1.8,
    "very_wide": 2.5,
}


def _apply_width(audio: np.ndarray, width: str) -> np.ndarray:
    """Rescale stereo width via mid/side: widen or narrow the side channel.

    mid = (L+R)/2, side = (L-R)/2.  Scaling the side channel by g keeps the
    center image intact while broadening (g>1) or narrowing (g<1) the image.
    mono (g=0) folds the signal to the center, matching a "mono" bus role.
    """
    gain = _WIDTH_GAIN.get(width, 1.0)
    if abs(gain - 1.0) < 1e-9 or audio.ndim < 2:
        return audio
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5 * gain
    return np.stack([mid + side, mid - side], axis=1)


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
    mono = np.abs(sidechain_signal.mean(axis=1) if sidechain_signal.ndim > 1 else sidechain_signal)
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
        [alpha], [1.0, -(1.0 - alpha)], target,
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


def _true_peak_db(audio: np.ndarray, sr: int) -> float:
    """True peak (dBTP) via 4x oversampling of both channels."""
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    up = resample_poly(audio, 4, 1, axis=0)
    peak = float(np.max(np.abs(up)))
    return 20 * np.log10(peak + 1e-12)


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
            audio, sr,
            time_ms=float(delay_cfg.get("time_ms", 180.0)),
            feedback=float(delay_cfg.get("feedback", 0.3)),
            amount=float(delay_cfg.get("amount", 0.25)),
        )
    if "reverb" in cfg:
        rev_cfg = cfg["reverb"]
        audio = _reverb(
            audio, sr,
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


def _compressor(
    audio: np.ndarray,
    sr: int,
    threshold_db: float = -12.0,
    ratio: float = 3.0,
    attack_ms: float = 10.0,
    release_ms: float = 120.0,
    makeup_db: float = 0.0,
) -> np.ndarray:
    """Gentle feed-forward compressor with a smooth knee.

    Envelope is a peak-tracked average; gain reduction is applied with a fast
    attack (sliding max) and an exponential release so it glues without
    pumping. Used for the profile's per-track and glue-bus compression.
    """
    threshold = 10 ** (threshold_db / 20.0)
    ratio = max(float(ratio), 1.0)
    attack = max(int(attack_ms / 1000.0 * sr), 1)
    release = max(int(release_ms / 1000.0 * sr), 1)

    # Peak-tracked envelope on the stereo pair (RMS-ish, one-pole smoothed).
    env = np.sqrt(np.mean(audio ** 2, axis=1)) + 1e-12
    env = _moving_average(env, attack)
    env_hold = _sliding_max(env, attack)

    # Over-threshold reduction in linear terms: below thresh no gain change.
    over = np.maximum(env_hold / threshold, 1.0)
    # Compressor curve: y = x^(1/ratio) above the threshold (soft knee via a
    # small linear taper right at the threshold to avoid a hard kink).
    knee = 2.0
    taper = np.clip((env_hold / threshold - 1.0) / (knee / threshold) * (1.0 / ratio) + (1.0 - 1.0 / ratio), 0.0, 1.0)
    gain = np.power(over, (1.0 / ratio - 1.0))
    gain = 1.0 + (gain - 1.0) * np.maximum(taper, 0.0)

    # Smooth release: one-pole on the gain envelope (start from unity).
    alpha = 1.0 - np.exp(-1.0 / release)
    sm, _ = lfilter(
        [alpha], [1.0, -(1.0 - alpha)], gain,
        zi=np.array([1.0]),
    )
    gain = np.minimum(gain, sm)  # attack follows drops instantly, release eases

    gain2d = np.stack([gain, gain], axis=1)
    makeup = 10 ** (makeup_db / 20.0)
    return audio * gain2d * makeup


def _moving_average(x: np.ndarray, window: int) -> np.ndarray:
    """O(N) sliding-window average via cumulative sums (per channel)."""
    w = max(int(window), 1)
    n = x.shape[0]
    if n <= w:
        return np.full_like(x, np.mean(x, axis=0, keepdims=True))
    cum = np.cumsum(x, axis=0)
    out = np.empty_like(x, dtype=np.float64)
    denom = np.minimum(np.arange(1, n + 1), w)
    shape = (n,) + (1,) * (x.ndim - 1)
    head = cum / denom.reshape(shape)
    tail = cum[w:] - cum[:-w]
    out[:w] = head[:w]
    out[w:] = tail / w
    return out


def _sliding_max(x: np.ndarray, window: int) -> np.ndarray:
    """O(N) sliding-window maximum over axis 0 (van Herk / Gil-Werman).

    Equivalent to maximum_filter1d but linear in the number of samples even
    for large windows, so it stays fast on long oversampled buffers.
    """
    w = max(int(window), 1)
    n = x.shape[0]
    if n <= w:
        return np.maximum.accumulate(x, axis=0)
    if w == 1:
        return x.copy()
    out = np.empty_like(x)
    # Block-wise prefix (forward) and suffix (backward) maxima.
    n_blocks = (n + w - 1) // w
    pad = n_blocks * w - n
    if pad:
        xp = np.concatenate([x, np.zeros((pad,) + x.shape[1:], dtype=x.dtype)], axis=0)
    else:
        xp = x
    blocks = xp.reshape(n_blocks, w, *x.shape[1:])
    fwd = np.maximum.accumulate(blocks, axis=1)
    rev = blocks[:, ::-1, ...]
    bwd = np.maximum.accumulate(rev, axis=1)[:, ::-1, ...]
    fwd = fwd.reshape(-1, *x.shape[1:])
    bwd = bwd.reshape(-1, *x.shape[1:])
    # For sample i the window is [i-w+1, i]: left part from bwd (block suffix
    # of the block containing i-w+1), right part from fwd (block prefix up to i).
    out = np.empty_like(x)
    out[: w - 1] = fwd[: w - 1]  # window still growing from sample 0
    if w <= n:
        out[w - 1 :] = np.maximum(bwd[: n - w + 1], fwd[w - 1 : n])
    return out


def _limit_peaks(audio: np.ndarray, sr: int, ceiling_db: float = -1.0) -> np.ndarray:
    """True-peak lookahead limiter.

    Envelope detection runs on a 4x oversampled signal so intersample peaks are
    caught too, then gain is applied to the original samples with a 20 ms
    lookahead shift. Output never exceeds the ceiling at the sample level and
    stays within ~0.3 dB of it on the true peak.
    """
    up = resample_poly(audio, 4, 1, axis=0)
    up_sr = sr * 4
    # Extra headroom so the downsampling back to sr doesn't push intersample
    # peaks above the requested ceiling.
    ceiling = 10 ** ((ceiling_db - 1.0) / 20.0)
    lookahead = max(int(0.02 * up_sr), 1)  # 20 ms in oversampled domain
    env = _sliding_max(np.abs(up), lookahead)
    gain = np.minimum(ceiling / (env + 1e-12), 1.0)
    pad = np.full((lookahead,) + gain.shape[1:], 1.0, dtype=gain.dtype)
    gain = np.concatenate([pad, gain[:-lookahead]], axis=0)
    release = max(int(0.05 * up_sr), 1)
    gain = _moving_average(gain, release)
    # Apply gain at oversampled resolution, then convert back.
    out_up = up * gain
    out = resample_poly(out_up, 1, 4, axis=0)
    # Safety net at the true peak: clip the oversampled signal first.
    out_up_clipped = np.minimum(out_up, ceiling)
    out_up_clipped = np.maximum(out_up_clipped, -ceiling)
    return resample_poly(out_up_clipped, 1, 4, axis=0)


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


def render_preview_mix(
    render_dir: str,
    profile: StyleProfile,
    pattern: str = "*.wav",
    output_path: str | None = None,
    max_duration: float | None = None,
    manual_gain: dict[str, float] | None = None,
    sidechain_db: float | None = None,
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
    """
    # Per-profile manual gain (from the style) overridden by the caller's.
    effective_manual_gain = dict(profile.manual_gain or {})
    if manual_gain:
        effective_manual_gain.update(manual_gain)

    analyses = analyze_directory(render_dir, pattern)
    if not analyses:
        raise ValueError(f"No {pattern} files found in {render_dir}")

    mix = compute_mix(analyses, profile, [a.name for a in analyses])

    # Track indices in the analyses list == indices in the mix corrections.
    stereo_parts: list[np.ndarray] = []
    used_sr = None
    for analysis, corr in zip(analyses, mix.track_corrections):
        audio, sr = sf.read(analysis.path, always_2d=False)
        if audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        used_sr = sr

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

        # Space FX (reverb / delay) per role.
        space_cfg = (profile.space or {}).get(corr.role)
        if space_cfg:
            audio = _apply_space(audio, sr, space_cfg)

        # Per-track compression from the profile (e.g. breaks, bass, kick).
        track_comp = (profile.compression or {}).get(corr.role)
        if track_comp:
            audio = _compressor(
                audio, sr,
                threshold_db=float(track_comp.get("threshold_db", -12.0)),
                ratio=float(track_comp.get("ratio", 3.0)),
                attack_ms=float(track_comp.get("attack_ms", 10.0)),
                release_ms=float(track_comp.get("release_ms", 120.0)),
                makeup_db=float(track_comp.get("makeup_db", 0.0)),
            )

        gain = 10 ** ((corr.volume_db or 0.0) / 20.0)
        gain *= 10 ** (effective_manual_gain.get(analysis.name, 0.0) / 20.0)
        if corr.pan is not None:
            lg, rg = _pan_gains(corr.pan)
            left, right = audio[:, 0] * lg, audio[:, 1] * rg
        else:
            left, right = audio[:, 0], audio[:, 1]
        # Stereo width per role (mono/wide/very_wide) via mid/side.
        part = np.stack([left, right], axis=1)
        role_cfg = profile.track_balance.get(corr.role) or {}
        part = _apply_width(part, role_cfg.get("width", "moderate"))
        stereo_parts.append(part * gain)

    # Align every part to a common length so nothing plays on its own after the
    # rest has ended. Prefer the shortest render, or cap at max_duration.
    if max_duration is not None:
        common = int(max_duration * used_sr)
    else:
        common = min(p.shape[0] for p in stereo_parts)
    stereo_parts = [p[:common] for p in stereo_parts]

    # Sidechain from the profile: kick ducks the low end, snare ducks the
    # 100-300 Hz band of bass/sub (dynamic EQ) so bass and snare stop fighting.
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
            band_range = [float(x) for x in duck_snare_band.get("band_range", [100, 300])]
            for i, corr in enumerate(mix.track_corrections):
                if corr.role in targets and i not in snare_idxs:
                    stereo_parts[i] = _band_duck(
                        stereo_parts[i], used_sr, band_range, snare_band_duck
                    )

    # Sum, then master: soft clip (if enabled) -> loudness normalize (TP-safe).
    mixdown = np.zeros((common, 2), dtype=np.float64)
    for part in stereo_parts:
        mixdown += part

    mcfg = profile.master or {}
    # Glue compression on the summed mix (from the profile's "bus" block).
    bus_comp = (profile.compression or {}).get("bus")
    if bus_comp:
        mixdown = _compressor(
            mixdown, used_sr,
            threshold_db=float(bus_comp.get("threshold_db", -14.0)),
            ratio=float(bus_comp.get("ratio", 2.0)),
            attack_ms=float(bus_comp.get("attack_ms", 12.0)),
            release_ms=float(bus_comp.get("release_ms", 130.0)),
            makeup_db=float(bus_comp.get("makeup_db", 0.0)),
        )
    if mcfg.get("soft_clip"):
        mixdown = _soft_clip(
            mixdown,
            float(mcfg.get("soft_clip_drive_db", 2.0)),
            amount=float(mcfg.get("soft_clip_amount", 0.7)),
        )

    mixdown = _normalize_to_lufs(
        mixdown,
        used_sr,
        profile.target_lufs,
        ceiling_dbtp=float(mcfg.get("ceiling_dbtp", -1.0)),
    )
    peak = float(np.max(np.abs(mixdown)))
    true_peak_db = _true_peak_db(mixdown, used_sr)

    if output_path is None:
        output_path = os.path.join(render_dir, f"preview_{profile.name}.wav")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sf.write(output_path, _dither(mixdown), used_sr, subtype="PCM_16")

    return {
        "style": profile.name,
        "output_path": output_path,
        "sample_rate": used_sr,
        "duration_s": round(common / used_sr, 2),
        "channels": 2,
        "target_lufs": profile.target_lufs,
        "peak_db": round(20 * np.log10(peak + 1e-12), 1),
        "true_peak_dbtp": round(true_peak_db, 1),
        "sidechain": {
            "kick": {"targets": list(duck_kick.get("targets", []))} if duck_kick else None,
            "snare_band": {
                "targets": list(duck_snare_band.get("targets", [])),
                "band_range": [float(x) for x in duck_snare_band.get("band_range", [100, 300])],
            } if duck_snare_band else None,
        },
        "tracks_used": [
            {
                "file": a.name,
                "role": c.role,
                "volume_db": c.volume_db,
                "manual_gain_db": effective_manual_gain.get(a.name, 0.0),
                "pan": c.pan,
            }
            for a, c in zip(analyses, mix.track_corrections)
        ],
        "master_notes": mix.master_notes,
    }
