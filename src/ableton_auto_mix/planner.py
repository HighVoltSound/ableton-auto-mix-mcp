"""Decision layer: split corrective actions into MIXING vs MASTERING.

The analyzer/mixer engine produces per-track spectral deltas against a style
profile, but it cannot tell *where* a fix belongs. A muddy 300 Hz hump shared
by every track is a bus problem (one master EQ move keeps phase coherent);
a single synth lead stabbing at 3 kHz is a per-track problem (cut it on that
track only).

``build_plan`` classifies every candidate correction into:

  * ``mix_actions``    — per-track gain / pan / EQ / width (the "Сведение"
                         column in the UI),
  * ``master_actions`` — bus-level EQ / width / loudness moves applied once
                         on the summed mix (the "Мастеринг" column),

each with a human-readable ``reason`` so the UI can explain every decision.

Classification rules (spectral): a band is promoted to MASTERING when at
least 60% of the tracks carrying real energy in that band deviate in the
SAME direction AND at least 3 tracks agree AND the median |delta| exceeds
~1.2 dB. Isolated outliers (1-2 tracks) stay as per-track EQ.

The RBJ biquad helpers from :mod:`ableton_auto_mix.reference` are reused so
the planned curve is exactly what the preview renderer sounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .analyzer import TrackAnalysis
from .mixer import MixResult, TrackCorrection
from .profiles import StyleProfile

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

ENERGY_FLOOR_DB = -90.0  # below this a track "has no energy" in a band
MASTER_SIGN_SHARE = 0.60  # >=60% of energetic tracks must agree in sign
MASTER_MIN_TRACKS = 3  # fewer agreeing tracks = isolated -> stay per-track
MASTER_MEDIAN_MIN_DB = 1.2  # median |delta| needed to bother the bus
MASTER_EQ_CLAMP_DB = 6.0  # safety clamp for bus EQ moves (same as match EQ)
LOUDNESS_THRESHOLD_DB = 1.0
WIDTH_TOLERANCE = 0.12  # integral-width tolerance before a bus move fires

# Correlation-based analysis width (0=mono .. 1=decorrelated) expected for
# each profile width label. Rough nominal values, used only to decide IF the
# bus width needs help, not to compute an exact filter.
_WIDTH_TARGET_NORM = {
    "mono": 0.05,
    "moderate": 0.40,
    "wide": 0.65,
    "very_wide": 0.85,
}


# ---------------------------------------------------------------------------
# Plan container
# ---------------------------------------------------------------------------


@dataclass
class Plan:
    """Executable mix/master plan with per-action justification."""

    style: str
    target_lufs: float
    mix_actions: list[dict[str, Any]] = field(default_factory=list)
    master_actions: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "target_lufs": self.target_lufs,
            "mix_actions": self.mix_actions,
            "master_actions": self.master_actions,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Band classification (shared with mixer.compute_mix via use_planner=True)
# ---------------------------------------------------------------------------


def classify_master_bands(
    analyses: list[TrackAnalysis], corrections: list[TrackCorrection]
) -> dict[str, dict[str, Any]]:
    """Which spectral bands are a GLOBAL (mastering) problem?

    Returns ``{band_name: {"delta_db": signed_median, "offenders": [names]}}``
    for every band where the deviations look like a shared tonal imbalance
    rather than isolated track issues. Bands missing from the result belong
    to per-track EQ.
    """
    entries: dict[str, list[tuple[str, float]]] = {}
    for corr in corrections:
        for bc in corr.band_corrections:
            entries.setdefault(bc.band, []).append((corr.name, float(bc.delta_db)))

    master: dict[str, dict[str, Any]] = {}
    for band, items in entries.items():
        deltas = [d for _, d in items]
        pos = [d for d in deltas if d > 0]
        neg = [d for d in deltas if d < 0]
        same_sign = pos if len(pos) >= len(neg) else neg
        if len(same_sign) < MASTER_MIN_TRACKS:
            continue  # isolated deviation -> per-track EQ
        notable = sum(1 for a in analyses if a.bandwidth_db.get(band, ENERGY_FLOOR_DB - 1.0) > ENERGY_FLOOR_DB)
        share = len(same_sign) / max(notable, 1)
        median_abs = float(np.median(np.abs(same_sign)))
        if share >= MASTER_SIGN_SHARE and median_abs > MASTER_MEDIAN_MIN_DB:
            offenders = [name for name, d in items if (d > 0) == (float(np.median(same_sign)) > 0)]
            master[band] = {
                "delta_db": round(float(np.median(same_sign)), 2),
                "offenders": offenders,
            }
    return master


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _geomean(lo: float, hi: float) -> float:
    return float(np.sqrt(max(lo, 10.0) * max(hi, 10.0)))


def _locate_band_peak_hz(paths: list[str], lo: float, hi: float) -> float | None:
    """Find WHERE inside [lo, hi] the offending tracks actually peak.

    Averages the Welch PSD of up to six offending renders and returns the
    frequency of maximum power inside the band (so "muddy around 300 Hz"
    lands a node at ~300 Hz instead of a blind geometric band center).
    Returns None on any trouble; callers then fall back to the geomean.
    """
    try:
        import soundfile as sf
        from scipy.signal import welch

        grid = np.geomspace(max(lo, 1.0), max(hi, lo * 1.01), 96)
        acc: np.ndarray | None = None
        n = 0
        sr0: int | None = None
        for p in paths[:6]:
            audio, sr = sf.read(p, always_2d=False, dtype="float64")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if sr0 is None:
                sr0 = int(sr)
            elif int(sr) != sr0:
                return None  # mixed sample rates -> don't risk a wrong node
            nperseg = min(len(audio), 8192)
            freqs, psd = welch(audio, fs=sr, nperseg=nperseg)
            mask = (freqs >= lo) & (freqs <= hi)
            if not mask.any():
                continue
            seg = np.exp(
                np.interp(
                    np.log(grid),
                    np.log(freqs[mask]),
                    np.log(psd[mask] + 1e-30),
                )
            )
            acc = seg.copy() if acc is None else acc + seg
            n += 1
        if not n or acc is None:
            return None
        return float(grid[int(np.argmax(acc / n))])
    except Exception:  # noqa: BLE001 — planning must never crash the renderer
        return None


def _eq_node_for_range(
    lo: float,
    hi: float,
    gain_db: float,
    peak_hz: float | None = None,
    q: float = 1.0,
) -> dict[str, Any]:
    """Build one master-EQ node, mirroring preview._apply_band_correction."""
    gain_db = round(float(np.clip(gain_db, -MASTER_EQ_CLAMP_DB, MASTER_EQ_CLAMP_DB)), 2)
    if hi >= 16000.0:
        return {
            "hz": round(max(lo, 1000.0), 1),
            "gain_db": gain_db,
            "q": q,
            "type": "high_shelf",
        }
    if lo <= 40.0:
        return {
            "hz": round(min(hi, 60.0), 1),
            "gain_db": gain_db,
            "q": q,
            "type": "low_shelf",
        }
    hz = peak_hz if peak_hz is not None else _geomean(lo, hi)
    hz = float(np.clip(hz, lo, min(hi, 20000.0)))
    return {"hz": round(hz, 1), "gain_db": gain_db, "q": q, "type": "peaking"}


def _fmt_range(freq_range: list[float]) -> str:
    lo, hi = freq_range
    if hi >= 1000:
        return f"{lo:.0f}-{hi / 1000:.1f}k Hz"
    return f"{lo:.0f}-{hi:.0f} Hz"


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------


def build_plan(analyses: list[TrackAnalysis], profile: StyleProfile, mix: MixResult) -> Plan:
    """Classify every correction into mixing (per-track) vs mastering (bus).

    Inputs are the analyzer metrics, the style profile and the per-track
    corrections from ``mixer.compute_mix``. Every emitted action carries a
    human-readable ``reason`` for the UI.
    """
    mix_actions: list[dict[str, Any]] = []
    master_actions: list[dict[str, Any]] = []
    notes: list[str] = []

    corrections = mix.track_corrections
    master_bands = classify_master_bands(analyses, corrections)

    # ---------------- spectral: master EQ vs per-track EQ -----------------
    range_by_band = {b["band"]: [float(x) for x in b["freq_range"]] for b in profile.frequency_balance}
    for band, median_delta in sorted(master_bands.items()):
        offenders = [c.name for c in corrections if any(bc.band == band for bc in c.band_corrections)]
        freq_range = range_by_band.get(band) or next(
            (bc.freq_range for c in corrections for bc in c.band_corrections if bc.band == band),
            [_geomean(20, 20000) / 2, _geomean(20, 20000) * 2],
        )
        peak_hz = _locate_band_peak_hz(
            [a.path for a in analyses if a.name in offenders],
            freq_range[0],
            freq_range[1],
        )
        node = _eq_node_for_range(freq_range[0], freq_range[1], median_delta, peak_hz)
        master_actions.append(
            {
                "kind": "eq",
                "params": {
                    "band": band,
                    "freq_range": freq_range,
                    "nodes": [node],
                },
                "reason": (
                    f"Common tonal imbalance: {len(offenders)} tracks "
                    f"({'all' if len(offenders) == len(analyses) else f'{len(offenders)}/{len(analyses)}'}) "
                    f"with energy in '{band}' ({_fmt_range(freq_range)}) deviate "
                    f"{median_delta:+.1f} dB in the same direction — one bus "
                    f"{node['type']} at {node['hz']:.0f} Hz fixes it coherently "
                    f"instead of N per-track EQs fighting each other."
                ),
            }
        )
        notes.append(
            f"mastering: '{band}' promoted to bus EQ (median {median_delta:+.1f} dB across {len(offenders)} tracks)"
        )

    # ---------------- per-track actions -----------------------------------
    eq_tracks = 0
    for corr in corrections:
        acts = 0

        # gain: track-balance deviation -> MIXING by definition.
        if corr.role != "unknown" and corr.volume_db is not None and abs(corr.volume_db) >= 0.1:
            mix_actions.append(
                {
                    "track": corr.name,
                    "index": corr.index,
                    "kind": "gain",
                    "params": {"gain_db": corr.volume_db},
                    "reason": (
                        f"'{corr.name}' ({corr.role}) sits {-corr.volume_db:+.1f} dB "
                        f"off the profile track balance (anchored on the kick/"
                        f"lowest anchor) — trim with track gain."
                    ),
                }
            )
            acts += 1

        # pan: profile role placement -> MIXING.
        if corr.pan is not None and abs(corr.pan) > 0.01:
            side = "L" if corr.pan < 0 else "R"
            mix_actions.append(
                {
                    "track": corr.name,
                    "index": corr.index,
                    "kind": "pan",
                    "params": {"pan": corr.pan},
                    "reason": (
                        f"'{corr.name}' placed {side}{abs(corr.pan):.2f} per the "
                        f"profile's {corr.role} imaging to open up the center."
                    ),
                }
            )
            acts += 1

        # EQ: only the bands NOT promoted to the bus remain here.
        for bc in corr.band_corrections:
            if bc.band in master_bands:
                continue  # handled by a master action above
            freq_range = [float(x) for x in bc.freq_range]
            node = _eq_node_for_range(freq_range[0], freq_range[1], bc.delta_db)
            mix_actions.append(
                {
                    "track": corr.name,
                    "index": corr.index,
                    "kind": "eq",
                    "params": {
                        "band": bc.band,
                        "freq_range": freq_range,
                        "nodes": [node],
                    },
                    "reason": (
                        f"'{corr.name}' alone is {bc.band}-heavy "
                        f"({_fmt_range(freq_range)}, {bc.delta_db:+.1f} dB vs "
                        f"profile) while other tracks are fine — isolated issue, "
                        f"corrected on this track only."
                    ),
                }
            )
            acts += 1
            eq_tracks += 1  # count per (track, band) pair

        # width: per-role imaging stays in MIXING (as _apply_width does today).
        width_cfg = (profile.track_balance.get(corr.role) or {}).get("width")
        if width_cfg and width_cfg != "moderate":
            mix_actions.append(
                {
                    "track": corr.name,
                    "index": corr.index,
                    "kind": "width",
                    "params": {"width": width_cfg},
                    "reason": (
                        f"'{corr.name}' imaged to '{width_cfg}' per the profile's "
                        f"{corr.role} width prescription (mid/side on the track)."
                    ),
                }
            )
            acts += 1

        if acts:
            notes.append(f"mixing: {acts} action(s) on '{corr.name}'")

    # ---------------- master loudness -------------------------------------
    lufs_delta = round(profile.target_lufs - mix.measured_lufs, 1)
    if abs(lufs_delta) >= LOUDNESS_THRESHOLD_DB:
        master_actions.append(
            {
                "kind": "loudness",
                "params": {
                    "gain_db": round(float(np.clip(lufs_delta, -12.0, 12.0)), 1),
                    "measured_lufs": mix.measured_lufs,
                    "target_lufs": profile.target_lufs,
                },
                "reason": (
                    f"Mix integrates at {mix.measured_lufs} LUFS vs the "
                    f"{profile.target_lufs} LUFS '{profile.name}' target — "
                    f"{lufs_delta:+.1f} dB of master gain (into the limiter) "
                    f"brings the whole mix to level. Track gains stay musical."
                ),
            }
        )
        notes.append(f"mastering: loudness {lufs_delta:+.1f} dB toward {profile.target_lufs} LUFS")

    # ---------------- master stereo width ---------------------------------
    if analyses:
        mean_width = float(np.mean([a.stereo_width for a in analyses]))
        target_norm = _WIDTH_TARGET_NORM.get(profile.stereo_width, 0.4)
        if abs(mean_width - target_norm) > WIDTH_TOLERANCE:
            side_gain = float(np.clip(target_norm / max(mean_width, 0.02), 0.0, 2.5))
            if abs(side_gain - 1.0) > 0.05:
                direction = "widening" if side_gain > 1.0 else "narrowing"
                master_actions.append(
                    {
                        "kind": "width",
                        "params": {
                            "measured_width": round(mean_width, 2),
                            "target_width": profile.stereo_width,
                            "side_gain": round(side_gain, 2),
                        },
                        "reason": (
                            f"Integral stereo width ({mean_width:.2f}) is far from "
                            f"the '{profile.stereo_width}' target "
                            f"(~{target_norm:.2f}) — mid/side {direction} on the "
                            f"bus (side x{side_gain:.2f}), keeping the center intact."
                        ),
                    }
                )
                notes.append(f"mastering: bus width x{side_gain:.2f} toward '{profile.stereo_width}'")

    return Plan(
        style=profile.name,
        target_lufs=profile.target_lufs,
        mix_actions=mix_actions,
        master_actions=master_actions,
        summary={
            "mix_count": len(mix_actions),
            "master_count": len(master_actions),
            "notes": notes,
        },
    )
