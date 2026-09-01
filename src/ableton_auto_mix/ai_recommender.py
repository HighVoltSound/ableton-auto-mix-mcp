"""AI-style mix recommender: analyzes LUFS, spectral balance, dynamics,
and role distribution, then outputs concrete per-track and bus recommendations.

RAG-enhanced: retrieves similar tracks from a reference database of analyzed
mixes to provide genre-aware, data-backed suggestions alongside the rule engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .auto_role import BANDS
from .reference_store import ReferenceStore, init_default_db


@dataclass
class Recommendation:
    category: str  # "gain", "eq", "compression", "sidechain", "mastering"
    target: str  # track name or "bus"
    param: str  # what to change
    value: Any  # suggested value
    reason: str  # human-readable explanation
    confidence: float  # 0..1
    references: list[dict] | None = None  # RAG: similar real-world examples


@dataclass
class Recommendations:
    recommendations: list[Recommendation] = field(default_factory=list)
    summary: str = ""
    role_map: dict[str, str] = field(default_factory=dict)


def _analyze_mix_balance(tracks: list[dict]) -> dict:
    """Analyze the overall mix balance across frequency bands."""
    # Aggregate band energies
    band_sums: dict[str, list[float]] = {b[0]: [] for b in BANDS}
    for t in tracks:
        be = t.get("band_energy", {})
        for bname in band_sums:
            if bname in be:
                band_sums[bname].append(be[bname])

    avg_bands = {}
    for bname, vals in band_sums.items():
        if vals:
            avg_bands[bname] = float(np.mean(vals))
        else:
            avg_bands[bname] = -60.0

    return avg_bands


def _suggest_gain(tracks: list[dict], target_lufs: float = -14.0) -> list[Recommendation]:
    """Suggest per-track gain adjustments to hit the target LUFS."""
    recs = []
    current_lufs = [t.get("lufs", -14.0) for t in tracks if isinstance(t.get("lufs"), int | float)]
    if not current_lufs:
        return recs

    mix_lufs = float(np.mean(current_lufs))
    delta = target_lufs - mix_lufs

    if abs(delta) < 1.0:
        return recs

    # Only suggest if overall level is significantly off
    direction = "increase" if delta > 0 else "decrease"
    recs.append(
        Recommendation(
            category="gain",
            target="bus",
            param="master_gain_db",
            value=round(delta, 1),
            reason=f"Mix is {abs(delta):.1f} dB {direction} from target ({target_lufs} LUFS). "
            f"Consider adjusting master gain by {delta:+.1f} dB.",
            confidence=0.8,
        )
    )
    return recs


def _suggest_eq(balance: dict[str, float]) -> list[Recommendation]:
    """Suggest EQ corrections based on spectral balance."""
    recs = []

    # Check for excessive low-end (mud zone 120-250 Hz)
    low_mids = balance.get("low_mids", -60)
    bass = balance.get("bass", -60)
    mids = balance.get("mids", -60)

    if low_mids - bass > 6:
        recs.append(
            Recommendation(
                category="eq",
                target="bus",
                param="low_mid_cut",
                value={"hz": 200, "gain_db": -3.0, "type": "peaking"},
                reason="Excessive energy in 120-250 Hz (mud zone). A -3 dB cut at 200 Hz can clean up the mix.",
                confidence=0.7,
            )
        )

    # Check for thin mix (lack of bass)
    sub = balance.get("sub_bass", -60)
    if bass - sub < 3 and bass < -30:
        recs.append(
            Recommendation(
                category="eq",
                target="bus",
                param="bass_boost",
                value={"hz": 80, "gain_db": 2.0, "type": "low_shelf"},
                reason="Mix lacks low-end weight. A gentle +2 dB shelf at 80 Hz adds warmth.",
                confidence=0.6,
            )
        )

    # Check for harsh highs
    highs = balance.get("highs", -60)
    high_mids = balance.get("high_mids", -60)
    if high_mids - mids > 6 and high_mids > -20:
        recs.append(
            Recommendation(
                category="eq",
                target="bus",
                param="de_harsh",
                value={"hz": 3500, "gain_db": -2.0, "q": 1.5, "type": "peaking"},
                reason="Harsh energy around 2-5 kHz. A narrow -2 dB cut at 3.5 kHz smooths the top end.",
                confidence=0.65,
            )
        )

    # Check for bright air
    if highs > -15 and highs - high_mids > 3:
        recs.append(
            Recommendation(
                category="eq",
                target="bus",
                param="air_boost",
                value={"hz": 10000, "gain_db": 1.5, "type": "high_shelf"},
                reason="Good high-frequency content present. A +1.5 dB shelf at 10 kHz adds air.",
                confidence=0.5,
            )
        )

    return recs


def _suggest_transient(role_map: dict[str, str]) -> list[Recommendation]:
    """Suggest transient shaping for drums."""
    recs = []
    roles = set(role_map.values())

    if "kick" in roles:
        recs.append(
            Recommendation(
                category="transient",
                target="kick",
                param="transient",
                value={"attack_db": 2.0, "sustain_db": -1.0},
                reason="Kick detected: +2 dB attack adds punch, -1 dB sustain tightens the tail.",
                confidence=0.6,
            )
        )

    if "snare" in roles:
        recs.append(
            Recommendation(
                category="transient",
                target="snare",
                param="transient",
                value={"attack_db": 1.5, "sustain_db": 0.0},
                reason="Snare: +1.5 dB attack enhances the crack.",
                confidence=0.55,
            )
        )

    return recs


def _retrieve_references(
    tracks: list[dict],
    role_map: dict[str, str],
    genre: str,
    store: ReferenceStore | None = None,
) -> dict[str, list[dict]]:
    """Retrieve similar references for each track role from the RAG store.

    Returns a dict mapping track name -> list of reference dicts.
    """
    if store is None:
        try:
            store = init_default_db()
        except Exception:
            return {}

    refs_by_track: dict[str, list[dict]] = {}
    for t in tracks:
        name = t.get("name", t.get("file", ""))
        role = role_map.get(name, "unknown")

        features = {
            "lufs": t.get("lufs", -14.0),
            "crest_factor": (t.get("peak_db", -6) - t.get("rms_db", -20))
            if isinstance(t.get("rms_db"), int | float)
            else 12.0,
            "band_energy": t.get("band_energy", {}),
        }

        similar = store.retrieve(role=role, genre=genre, features=features, k=3)
        if similar:
            refs_by_track[name] = [
                {
                    "role": r.role,
                    "genre": r.genre,
                    "lufs": r.lufs,
                    "crest_factor": r.crest_factor,
                    "compression": r.compression,
                    "sidechain": r.sidechain,
                    "source": r.source,
                }
                for r in similar
            ]

    return refs_by_track


def _suggest_compression_rag(
    tracks: list[dict],
    role_map: dict[str, str],
    refs_by_track: dict[str, list[dict]],
) -> list[Recommendation]:
    """Suggest compression using RAG references for similar tracks."""
    recs = []

    for t in tracks:
        name = t.get("name", t.get("file", "unknown"))
        role = role_map.get(name, "unknown")
        rms = t.get("rms_db", -30)
        peak = t.get("peak_db", -6)
        crest = peak - rms if isinstance(rms, int | float) and isinstance(peak, int | float) else 0

        refs = refs_by_track.get(name, [])
        # Find compression references for this role
        comp_refs = [r for r in refs if r.get("compression")]

        if comp_refs:
            # Use the most common compression settings from references
            best_ref = comp_refs[0]
            comp = best_ref["compression"]

            # Boost confidence if crest factor matches reference pattern
            ref_crest = best_ref.get("crest_factor", 12.0)
            crest_match = 1.0 - min(abs(crest - ref_crest) / 10.0, 1.0)
            boosted_confidence = min(0.95, 0.6 + crest_match * 0.3)

            recs.append(
                Recommendation(
                    category="compression",
                    target=name,
                    param="compress",
                    value=comp,
                    reason=(
                        f"RAG: {role} in similar {best_ref.get('genre', 'unknown')} mixes uses "
                        f"threshold={comp.get('threshold_db', '?')} dB / ratio={comp.get('ratio', '?')}:1. "
                        f"Crest factor {crest:.0f} dB (ref: {ref_crest:.0f} dB)."
                    ),
                    confidence=boosted_confidence,
                    references=[best_ref],
                )
            )
        elif crest > 15 and role in ("kick", "snare", "percussion"):
            recs.append(
                Recommendation(
                    category="compression",
                    target=name,
                    param="compress",
                    value={
                        "threshold_db": -12,
                        "ratio": 3.0,
                        "attack_ms": 5,
                        "release_ms": 100,
                    },
                    reason=f"{role} has high dynamics (crest {crest:.0f} dB). Compression at -12 dB / 3:1 tames peaks.",
                    confidence=0.7,
                )
            )

    return recs


def _suggest_sidechain_rag(
    tracks: list[dict],
    role_map: dict[str, str],
    refs_by_track: dict[str, list[dict]],
) -> list[Recommendation]:
    """Suggest sidechain using RAG references."""
    recs = []
    has_kick = any(role_map.get(t.get("name", ""), "") == "kick" for t in tracks)
    has_bass = any(role_map.get(t.get("name", ""), "") in ("bass", "sub_bass") for t in tracks)

    if has_kick and has_bass:
        # Find sidechain references from bass tracks
        bass_refs = []
        for t in tracks:
            name = t.get("name", t.get("file", ""))
            if role_map.get(name, "") in ("bass", "sub_bass"):
                bass_refs.extend([r for r in refs_by_track.get(name, []) if r.get("sidechain")])

        if bass_refs:
            best_sc = bass_refs[0]["sidechain"]
            recs.append(
                Recommendation(
                    category="sidechain",
                    target="bus",
                    param="kick_duck_bass",
                    value=best_sc,
                    reason=(
                        f"RAG: In similar {bass_refs[0].get('genre', 'unknown')} mixes, "
                        f"sidechain ducking of {best_sc.get('amount_db', '?')} dB is used. "
                        f"Kick + bass detected — prevents low-end masking."
                    ),
                    confidence=0.85,
                    references=[bass_refs[0]],
                )
            )
        else:
            recs.append(
                Recommendation(
                    category="sidechain",
                    target="bus",
                    param="kick_duck_bass",
                    value={"amount_db": -3.0, "attack_ms": 5, "release_ms": 90},
                    reason="Kick and bass detected. Sidechain ducking (-3 dB) prevents low-end masking.",
                    confidence=0.8,
                )
            )

    return recs


def recommend(
    tracks: list[dict],
    target_lufs: float = -14.0,
    style_profile: dict | None = None,
    genre: str = "techno",
    reference_store: ReferenceStore | None = None,
) -> Recommendations:
    """Generate mix recommendations from analyzed tracks (RAG-enhanced).

    Args:
        tracks: list of dicts with keys from TrackAnalysis (lufs, rms_db,
                peak_db, band_energy, name, path).
        target_lufs: target integrated loudness.
        style_profile: optional style profile for genre-specific hints.
        genre: target genre for RAG retrieval.
        reference_store: optional pre-loaded store; created on first call.

    Returns:
        Recommendations with actionable suggestions + RAG references.
    """
    # Build role map
    role_map = {}
    for t in tracks:
        name = t.get("name", t.get("file", ""))
        role_map[name] = t.get("role", "unknown")

    # Analyze balance
    balance = _analyze_mix_balance(tracks)

    # RAG: retrieve similar references
    refs_by_track = _retrieve_references(tracks, role_map, genre, reference_store)

    # Gather all recommendations (RAG-enhanced where possible)
    all_recs = []
    all_recs.extend(_suggest_gain(tracks, target_lufs))
    all_recs.extend(_suggest_eq(balance))
    all_recs.extend(_suggest_compression_rag(tracks, role_map, refs_by_track))
    all_recs.extend(_suggest_sidechain_rag(tracks, role_map, refs_by_track))
    all_recs.extend(_suggest_transient(role_map))

    # Sort by confidence
    all_recs.sort(key=lambda r: r.confidence, reverse=True)

    # Summary
    cats = set(r.category for r in all_recs)
    rag_count = sum(1 for r in all_recs if r.references)
    summary = f"Found {len(all_recs)} suggestions across {len(cats)} categories ({rag_count} backed by RAG references)."

    return Recommendations(
        recommendations=all_recs,
        summary=summary,
        role_map=role_map,
    )
