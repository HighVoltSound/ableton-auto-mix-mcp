"""Auto-mixing engine: compare measured metrics against a style profile
and produce per-track corrective actions (levels, pan, EQ, compression).

The engine works in two modes:
  - "report": computes and returns recommended adjustments without touching Ableton
  - "apply": pushes the adjustments to Ableton via the OSC client

It also supports matching tracks to instrument roles (kick, bass, vocals, ...)
by name heuristics so the profile's track_balance can be targeted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .analyzer import BANDS as _BANDS
from .analyzer import TrackAnalysis
from .profiles import StyleProfile

INSTRUMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "kick": ("kick", "bd", "bass drum"),
    "sub_bass": ("sub", "808", "sine"),
    "bass": ("bass", "bassline"),
    "wobble": ("wobble", "growl", "reese", "dub"),
    "breaks": ("break", "chopped"),
    "snare": ("snare", "clap", "rim", "snr", "snt"),
    "hihat": ("hat", "hi-hat", "cymbal", "ride", "openhat"),
    "percussion": ("perc", "tamb", "shaker", "conga"),
    "vocals": ("vocal", "voice", "vox", "tune", "lyrics"),
    "lead": ("lead", "supersaw", "pluck", "arp", "arpg"),
    "melody": ("melody", "synth", "keys", "chords"),
    "pads": ("pad", "strings", "choir"),
    "sample": ("sample", "loop", "flip"),
    "drone": ("drone", "amb", "texture", "bg"),
    "texture": ("texture", "riser", "noise"),
    "field_rec": ("field", "record", "rec"),
    "fx": ("fx", "sfx", "impact", "sweep"),
}


@dataclass
class TrackMatch:
    index: int
    name: str
    role: str  # matched instrument role key in the profile (or "unknown")


def match_role(name: str) -> str:
    lowered = name.lower()
    for role, keywords in INSTRUMENT_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return role
    return "unknown"


def _spectral_role(band_energy: dict[str, float]) -> str:
    """Guess an instrument role from the spectral shape alone.

    Fallback when the file name gives no hint. Bands are normalized to the
    loudest one (linear scale, relative dB), then role is decided by which
    regions are within ~12 dB of the peak and how energy is distributed.
    """
    bands = ["sub_bass", "bass", "low_mids", "mids", "high_mids", "highs"]
    vals = np.array([band_energy.get(b, -120.0) for b in bands])
    rel = vals - float(vals.max())  # dB relative to the dominant band, <= 0

    # A region "counts" if within 12 dB of the dominant band.
    sub_hot = rel[0] > -12.0
    bass_hot = rel[1] > -12.0
    low_mids_hot = rel[2] > -12.0
    mids_hot = rel[3] > -12.0
    high_mids_hot = rel[4] > -12.0
    highs_hot = rel[5] > -12.0

    dom = int(np.argmax(vals))

    # 1) Sub energy present: bass family (kick/sub/bass/wobble).
    if sub_hot:
        if not bass_hot and not low_mids_hot:
            return "sub_bass"
        if bass_hot and not low_mids_hot:
            return "bass"
        return "kick" if low_mids_hot else "bass"

    # 2) Bass without sub.
    if bass_hot:
        return "wobble" if low_mids_hot else "bass"

    # 3) Mids / high-mids dominate -> pitched, tonal material.
    if dom in (3, 4):
        if highs_hot and not mids_hot and high_mids_hot:
            return "snare"
        if highs_hot and not mids_hot:
            return "hihat"
        if high_mids_hot and not low_mids_hot and not mids_hot:
            return "vocals"
        if low_mids_hot:
            return "melody"
        return "lead"

    # 4) Highs dominate without mid content -> percussion.
    if dom == 5:
        if high_mids_hot:
            return "snare"
        return "percussion" if mids_hot else "hihat"

    # 5) Low-mids dominate without sub/bass -> pads or melody.
    if dom == 2:
        return "pads" if not mids_hot else "melody"

    return "texture"


def match_role_with_spectrum(name: str, band_energy: dict[str, float]) -> str:
    """Role from the name first, falling back to spectral classification."""
    by_name = match_role(name)
    if by_name != "unknown":
        return by_name
    return _spectral_role(band_energy)


def _profile_role(profile: StyleProfile, name: str, band_energy: dict[str, float]) -> str:
    """Role for a track: explicit per-file override in the profile wins."""
    override = (profile.role_override or {}).get(name)
    if override:
        return override
    return match_role_with_spectrum(name, band_energy)


@dataclass
class BandCorrection:
    band: str
    freq_range: list[float]
    measured_db: float
    target_db: float
    delta_db: float


@dataclass
class TrackCorrection:
    index: int
    name: str
    role: str
    volume_db: float | None = None
    pan: float | None = None
    band_corrections: list[BandCorrection] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "role": self.role,
            "volume_db": self.volume_db,
            "pan": self.pan,
            "band_corrections": [
                {
                    "band": b.band,
                    "range_hz": b.freq_range,
                    "measured_db": b.measured_db,
                    "target_db": b.target_db,
                    "delta_db": b.delta_db,
                }
                for b in self.band_corrections
            ],
            "notes": self.notes,
        }


@dataclass
class MixResult:
    style: str
    target_lufs: float
    measured_lufs: float
    overall_balance: float  # 0..1, how far the mix currently is from the profile
    master_notes: list[str] = field(default_factory=list)
    track_corrections: list[TrackCorrection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "style": self.style,
            "target_lufs": self.target_lufs,
            "measured_lufs": self.measured_lufs,
            "overall_balance": round(self.overall_balance, 3),
            "master_notes": self.master_notes,
            "track_corrections": [t.to_dict() for t in self.track_corrections],
        }


def _lufs_delta_db(measured: float, target: float) -> float:
    return round(target - measured, 1)


def suggest_style(analyses: list[TrackAnalysis]) -> dict[str, Any]:
    """Rank style profiles against the analyzed tracks (LUFS + spectral shape)."""
    from .profiles import list_profiles

    measured_lufs = sum(a.lufs for a in analyses) / len(analyses)

    measured_bands: dict[str, float] = {}
    for band, _, _ in _BANDS:
        vals = [a.bandwidth_db[band] for a in analyses if band in a.bandwidth_db]
        if vals:
            measured_bands[band] = sum(vals) / len(vals)

    scores: list[tuple[float, str, str]] = []
    for p in list_profiles():
        lufs_score = abs(p.target_lufs - measured_lufs) / 4.0
        target_bands = {
            b["band"]: b["target_db"] for b in p.frequency_balance
            if b["band"] in measured_bands
        }
        if len(target_bands) == len(measured_bands):
            m = np.array([measured_bands[b] for b in target_bands])
            t = np.array([target_bands[b] for b in target_bands])
            spectral_score = float(np.mean(np.abs((m - m.mean()) - (t - t.mean()))))
        else:
            spectral_score = 4.0  # unknown shape -> neutral penalty
        score = lufs_score * 0.5 + spectral_score * 0.5
        scores.append((score, p.name, p.label))

    scores.sort(key=lambda s: s[0])
    best = scores[0]
    return {
        "suggested_style": best[1],
        "label": best[2],
        "measured_lufs": round(measured_lufs, 1),
        "ranked": [
            {"style": s[1], "label": s[2], "score": round(s[0], 2)} for s in scores
        ],
        "spectral_distance": {
            "measured_bands": {k: round(v, 1) for k, v in measured_bands.items()},
            "best_fit_style": best[1],
            "score": round(best[0], 2),
        },
    }


def compute_mix(
    analyses: list[TrackAnalysis],
    profile: StyleProfile,
    track_names: list[str] | None = None,
) -> MixResult:
    """Compute corrective actions to push the analyzed tracks toward the style."""
    if not analyses:
        raise ValueError("No track analyses provided")

    names = track_names or [a.name for a in analyses]
    if len(names) != len(analyses):
        raise ValueError("track_names length must match analyses length")

    # -- overall loudness -------------------------------------------------
    master_lufs = float(np.mean([a.lufs for a in analyses])) if analyses else -60.0
    lufs_delta = _lufs_delta_db(master_lufs, profile.target_lufs)

    # -- per-track corrections -------------------------------------------
    corrections: list[TrackCorrection] = []
    band_deltas: list[float] = []

    # The profile's track_balance levels are *relative* per role. To turn
    # them into concrete volume changes we anchor on the KICK and rebalance
    # every other track relative to it, so the differences between tracks
    # match the profile's target differences. The kick is the rhythmic
    # reference of the mix; if none is present, fall back to the loudest track.
    # LUFS is used (not RMS) because sparse tracks like growls have a low RMS
    # but still hit hard when they play — RMS would over-boost them.
    kick_idx = next(
        (i for i, n in enumerate(names) if match_role(n) == "kick"), None
    )
    if kick_idx is not None:
        anchor_idx = kick_idx
        anchor_note = f"anchored on kick ({names[kick_idx]})"
    else:
        # No track named like a kick: pick the most sub-heavy / punchiest one.
        sub_scores = [
            analyses[i].bandwidth_db.get("sub_bass", -120.0)
            + analyses[i].bandwidth_db.get("bass", -120.0)
            for i in range(len(analyses))
        ]
        anchor_idx = int(np.argmax(sub_scores))
        anchor_note = "no kick by name; anchored on most low-end track"
    anchor_role = _profile_role(profile, names[anchor_idx], analyses[anchor_idx].bandwidth_db)
    anchor_target = profile.track_balance.get(anchor_role, {}).get("level", 0.0)

    for i, (analysis, name) in enumerate(zip(analyses, names)):
        role = _profile_role(profile, name, analysis.bandwidth_db)
        role_cfg = profile.track_balance.get(role)

        corr = TrackCorrection(index=i, name=name, role=role)

        if role_cfg:
            target_level = role_cfg.get("level", 0.0)
            # Keep anchor's level, set others relative to it. If the anchor
            # itself has no profile role, fall back to relative-to-anchor.
            adj = (target_level - anchor_target) - (analysis.lufs - analyses[anchor_idx].lufs)
            corr.volume_db = round(min(max(adj, -18.0), 18.0), 1)
            if "pan" in role_cfg:
                corr.pan = role_cfg["pan"]
        else:
            # Unknown role: no balance prescription, only report loudness.
            corr.volume_db = 0.0
            corr.notes.append("role not recognized; level untouched")

        # -- spectral band correction (EQ suggestions) --------------------
        # EQ only fixes the *shape* of the spectrum, not the absolute level:
        # the overall loudness of the track is handled by volume_db. So we
        # compare the measured curve to the profile curve after removing each
        # curve's mean, and report the relative per-band adjustment.
        measured_curve = np.array(
            [analysis.bandwidth_db[b["band"]] for b in profile.frequency_balance
             if b["band"] in analysis.bandwidth_db]
        )
        target_curve = np.array(
            [b["target_db"] for b in profile.frequency_balance
             if b["band"] in analysis.bandwidth_db]
        )
        if len(measured_curve) == len(target_curve) and len(measured_curve) > 0:
            deviation = measured_curve - target_curve  # + = louder than target
            shape_error = deviation - deviation.mean()  # removes overall level
            for (band_spec, rel) in zip(
                [b for b in profile.frequency_balance if b["band"] in analysis.bandwidth_db],
                shape_error,
            ):
                rel_delta = float(round(-rel, 1))  # + = boost this band
                measured = analysis.bandwidth_db[band_spec["band"]]
                # If the band has essentially no energy (e.g. a pure sub has
                # no highs at -120 dBFS), boosting is pointless — flag it.
                if measured < -90.0:
                    corr.notes.append(
                        f"band '{band_spec['band']}' has no energy "
                        f"({measured:.0f} dBFS); no EQ possible"
                    )
                    continue
                if abs(rel_delta) >= 1.5:
                    corr.band_corrections.append(
                        BandCorrection(
                            band=band_spec["band"],
                            freq_range=band_spec["freq_range"],
                            measured_db=round(measured, 1),
                            target_db=band_spec["target_db"],
                            delta_db=rel_delta,
                        )
                    )
                    band_deltas.append(abs(rel_delta))

        corrections.append(corr)

    # -- overall balance metric: normalized mean absolute spectral error ----
    if band_deltas:
        overall = float(min(1.0, max(0.0, np.mean(band_deltas) / 12.0)))
    else:
        overall = 0.0

    master_notes = []
    master_notes.append(anchor_note)
    if abs(lufs_delta) >= 1.0:
        master_notes.append(
            f"master loudness {master_lufs:.1f} LUFS vs target {profile.target_lufs} "
            f"({'+' if lufs_delta > 0 else ''}{lufs_delta} dB)"
        )
    for suggestion in profile.fx_suggestions:
        master_notes.append(f"fx: {suggestion}")
    for name, comp in profile.compression.items():
        if name == "bus":
            master_notes.append(
                f"bus comp: ratio {comp['ratio']}:1, "
                f"attack {comp['attack_ms']}ms, release {comp['release_ms']}ms"
            )

    return MixResult(
        style=profile.name,
        target_lufs=profile.target_lufs,
        measured_lufs=round(master_lufs, 1),
        overall_balance=overall,
        master_notes=master_notes,
        track_corrections=corrections,
    )
