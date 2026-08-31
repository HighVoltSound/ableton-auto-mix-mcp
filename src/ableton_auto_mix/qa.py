"""Release-quality checks: frequency-conflict analysis and master metrics
compared against typical top-label targets.

Two tools live here:
  - analyze_conflicts: find pairs of tracks fighting for the same band and
    suggest how to separate them (high-pass, ducking, EQ cut).
  - release_check: measure the final preview against label-style targets
    (LUFS, LRA, true peak, spectral tilt) and return a ready/needs-work verdict.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from .analyzer import TrackAnalysis
from .dsp._utils import true_peak_db as _true_peak_db
from .mixer import match_role_with_spectrum

CONFLICT_BANDS: list[tuple[str, float, float]] = [
    ("sub_bass", 20.0, 60.0),
    ("bass", 60.0, 120.0),
    ("low_mids", 120.0, 250.0),
    ("mids", 250.0, 2000.0),
    ("high_mids", 2000.0, 6000.0),
    ("highs", 6000.0, 20000.0),
]

# Two roles contesting a band if BOTH carry at least this much band energy.
CONFLICT_FLOOR_DB = -45.0

# Spectral tilt target for bass music: how much hotter the sub should be
# than the top end (roughly matches a loud club master).
RELEASE_TARGETS = {
    "lufs": {"target": -8.0, "ok": (-10.0, -7.0)},
    "lra": {"target": 4.5, "ok": (3.0, 7.5)},
    "true_peak_dbtp": {"target": -1.0, "ok": (-3.0, -0.7)},
    "rms_db": {"target": -10.0, "ok": (-13.0, -8.0)},
    "sub_mid_gap_db": {"target": 6.0, "ok": (3.0, 10.0)},
}


def analyze_conflicts(analyses: list[TrackAnalysis]) -> list[dict[str, Any]]:
    """Find pairs of tracks that occupy the same frequency band at the same time.

    Returns one entry per conflicting pair per band, with a suggested fix based
    on the roles involved.
    """
    conflicts: list[dict[str, Any]] = []
    for i in range(len(analyses)):
        for j in range(i + 1, len(analyses)):
            a, b = analyses[i], analyses[j]
            role_a, role_b = (
                match_role_with_spectrum(a.name, a.bandwidth_db),
                match_role_with_spectrum(b.name, b.bandwidth_db),
            )
            for band, lo, hi in CONFLICT_BANDS:
                ea = a.bandwidth_db.get(band)
                eb = b.bandwidth_db.get(band)
                if ea is None or eb is None:
                    continue
                if ea >= CONFLICT_FLOOR_DB and eb >= CONFLICT_FLOOR_DB:
                    suggestion = _conflict_suggestion(role_a, role_b, band)
                    conflicts.append(
                        {
                            "track_a": a.name,
                            "role_a": role_a,
                            "track_b": b.name,
                            "role_b": role_b,
                            "band": band,
                            "freq_range_hz": [lo, hi],
                            "energy_a_db": round(ea, 1),
                            "energy_b_db": round(eb, 1),
                            "gap_db": round(abs(ea - eb), 1),
                            "suggestion": suggestion,
                        }
                    )
    conflicts.sort(key=lambda c: -min(c["energy_a_db"], c["energy_b_db"]))
    return conflicts


def _conflict_suggestion(role_a: str, role_b: str, band: str) -> str:
    low = {"sub_bass", "bass", "wobble", "kick"}
    drum = {"kick", "snare", "hihat", "percussion"}
    if role_a in low and role_b in low:
        if band == "sub_bass":
            return "two low-end elements fight for the sub; sidechain the bass/sub under the kick"
        return "low-end clash: try a high-pass on one of them above the other's range"
    if (role_a in drum and role_b == "snare") or (role_b in drum and role_a == "snare"):
        return "snare clashing: duck the 100-300 Hz band of the other track under the snare"
    if band == "mids" or band == "high_mids":
        return "mid presence conflict: spread with panning or cut the other track's mids by 2-3 dB"
    if band == "highs":
        return (
            "top-end conflict: roll off highs on one track or widen it for separation"
        )
    if role_a == "vocals" or role_b == "vocals":
        return "vocals buried here: carve this band out of the competing instrument"
    return "shared band energy; reduce one via EQ or ducking"


def release_check(
    path: str,
    style_name: str,
    target_lufs: float,
) -> dict[str, Any]:
    """Measure a rendered/bounced WAV against label-style master targets."""
    audio, sr = sf.read(path, always_2d=False)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)

    meter = pyln.Meter(sr)
    lufs = float(meter.integrated_loudness(audio))
    lra = float(meter.loudness_range(audio))
    true_peak = _true_peak_db(audio, sr)

    mono = audio.mean(axis=1)
    rms = float(np.sqrt(np.mean(mono**2)) + 1e-12)
    rms_db = 20 * np.log10(rms)

    # Spectral tilt: sub band vs the high end (rough proxy for bass weight).
    from scipy.signal import butter, sosfiltfilt

    def band_db(fmin: float, fmax: float) -> float:
        sos = butter(4, [fmin, fmax], btype="bandpass", fs=sr, output="sos")
        filt = sosfiltfilt(sos, mono)
        return 20 * np.log10(np.sqrt(np.mean(filt**2)) + 1e-12)

    sub_db = band_db(20, 60)
    mids_db = band_db(250, 2000)
    sub_mid_gap = sub_db - mids_db

    metrics = {
        "lufs": round(lufs, 1),
        "lra": round(lra, 1),
        "true_peak_dbtp": round(true_peak, 1),
        "rms_db": round(rms_db, 1),
        "sub_mid_gap_db": round(sub_mid_gap, 1),
    }

    results = []
    all_ok = True
    for key, val in metrics.items():
        tgt = RELEASE_TARGETS[key]
        ok_lo, ok_hi = tgt["ok"]
        status = "ok" if ok_lo <= val <= ok_hi else "needs_work"
        if status == "needs_work":
            all_ok = False
        results.append(
            {
                "metric": key,
                "measured": val,
                "target": tgt["target"],
                "ok_range": [ok_lo, ok_hi],
                "status": status,
            }
        )

    return {
        "path": path,
        "style": style_name,
        "target_lufs": target_lufs,
        "measured_lufs": lufs,
        "verdict": "ready" if all_ok else "needs_work",
        "metrics": results,
        "notes": _release_notes(results),
    }


def _release_notes(results: list[dict[str, Any]]) -> list[str]:
    notes = []
    for r in results:
        if r["status"] == "needs_work":
            lo, hi = r["ok_range"]
            notes.append(
                f"{r['metric']}: {r['measured']} (target ~{r['target']}, ok {lo}..{hi})"
            )
    if not notes:
        notes.append("all metrics within label-style range")
    return notes
