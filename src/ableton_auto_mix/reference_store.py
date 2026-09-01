"""Reference store for RAG-enhanced recommendations.

Stores and retrieves analyzed track data for similarity matching.
Each entry captures a track's features + what processing was applied
successfully in a real mix context.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "reference_db.json")


@dataclass
class TrackReference:
    """One analyzed track from a real or synthetic mix."""

    role: str  # kick, snare, bass, lead, vocal, pad, fx, etc.
    genre: str  # techno, ambient, hip_hop, etc.
    lufs: float = -14.0
    rms_db: float = -20.0
    peak_db: float = -6.0
    crest_factor: float = 12.0
    band_energy: dict[str, float] = field(default_factory=dict)

    # What processing was applied in the successful mix
    compression: dict[str, Any] | None = None
    eq_bands: list[dict[str, Any]] = field(default_factory=list)
    sidechain: dict[str, Any] | None = None
    transient: dict[str, Any] | None = None

    # Metadata
    source: str = ""  # where this reference came from
    confidence: float = 0.8  # how reliable this reference is


class ReferenceStore:
    """In-memory + file-backed store of track references for RAG retrieval."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.references: list[TrackReference] = []
        self._load()

    def _load(self) -> None:
        """Load references from JSON file."""
        if not os.path.exists(self.db_path):
            self.references = []
            return
        try:
            with open(self.db_path, encoding="utf-8") as f:
                data = json.load(f)
            self.references = [TrackReference(**entry) for entry in data]
        except Exception:
            self.references = []

    def save(self) -> None:
        """Persist references to JSON file."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        data = [asdict(r) for r in self.references]
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(self, ref: TrackReference) -> None:
        """Add a reference to the store."""
        self.references.append(ref)

    def _distance(self, a: TrackReference, b: TrackReference) -> float:
        """Compute similarity distance between two references.

        Lower = more similar. Combines role match, genre match, and feature distance.
        """
        score = 0.0

        # Role match: same role = 0, different = +2
        if a.role != b.role:
            score += 2.0

        # Genre match: same genre = 0, different = +1
        if a.genre != b.genre:
            score += 1.0

        # Feature distance: LUFS, crest factor, band energies
        score += abs(a.lufs - b.lufs) * 0.1
        score += abs(a.crest_factor - b.crest_factor) * 0.05

        # Band energy distance (Euclidean on common bands)
        common_bands = set(a.band_energy.keys()) & set(b.band_energy.keys())
        if common_bands:
            band_diff = sum((a.band_energy[k] - b.band_energy[k]) ** 2 for k in common_bands)
            score += (band_diff / len(common_bands)) ** 0.5 * 0.1

        return score

    def retrieve(
        self,
        role: str,
        genre: str,
        features: dict[str, Any] | None = None,
        k: int = 3,
    ) -> list[TrackReference]:
        """Find k most similar references for a given role + genre.

        Args:
            role: track role (kick, bass, etc.)
            genre: target genre
            features: optional dict with lufs, crest_factor, band_energy
            k: number of results to return

        Returns:
            List of TrackReferences sorted by similarity (best first).
        """
        if not self.references:
            return []

        # Build a temporary reference from the query
        query = TrackReference(
            role=role,
            genre=genre,
            lufs=features.get("lufs", -14.0) if features else -14.0,
            crest_factor=features.get("crest_factor", 12.0) if features else 12.0,
            band_energy=features.get("band_energy", {}) if features else {},
        )

        # Score all references
        scored = [(self._distance(query, ref), ref) for ref in self.references]
        scored.sort(key=lambda x: x[0])

        # Return top k
        return [ref for _, ref in scored[:k]]


def _build_seed_references() -> list[TrackReference]:
    """Build seed references from known good mixing practices.

    These are calibrated from professional mixing/mastering best practices
    across common genres. They give the RAG system a baseline even when
    no real mix data is available yet.
    """
    seeds = []

    # --- Techno ---
    for role, lufs, crest, comp, sc in [
        (
            "kick",
            -16.0,
            10.0,
            {"threshold_db": -12, "ratio": 3.0, "attack_ms": 5, "release_ms": 80},
            None,
        ),
        (
            "bass",
            -18.0,
            8.0,
            {"threshold_db": -10, "ratio": 4.0, "attack_ms": 8, "release_ms": 100},
            {"amount_db": -4.0, "attack_ms": 5, "release_ms": 90},
        ),
        (
            "lead",
            -14.0,
            14.0,
            {"threshold_db": -14, "ratio": 2.5, "attack_ms": 10, "release_ms": 120},
            None,
        ),
        ("hihat", -22.0, 18.0, None, None),
        (
            "snare",
            -16.0,
            12.0,
            {"threshold_db": -11, "ratio": 3.0, "attack_ms": 3, "release_ms": 80},
            None,
        ),
    ]:
        seeds.append(
            TrackReference(
                role=role,
                genre="techno",
                lufs=lufs,
                crest_factor=crest,
                compression=comp,
                sidechain=sc,
                source="seed_techno",
                confidence=0.9,
            )
        )

    # --- Ambient ---
    for role, lufs, crest, comp in [
        ("pad", -24.0, 6.0, None),
        (
            "lead",
            -20.0,
            10.0,
            {"threshold_db": -18, "ratio": 2.0, "attack_ms": 20, "release_ms": 200},
        ),
        (
            "bass",
            -22.0,
            8.0,
            {"threshold_db": -16, "ratio": 2.5, "attack_ms": 12, "release_ms": 150},
        ),
        ("fx", -28.0, 15.0, None),
    ]:
        seeds.append(
            TrackReference(
                role=role,
                genre="ambient",
                lufs=lufs,
                crest_factor=crest,
                compression=comp,
                source="seed_ambient",
                confidence=0.9,
            )
        )

    # --- Hip-hop ---
    for role, lufs, crest, comp, sc in [
        (
            "kick",
            -12.0,
            10.0,
            {"threshold_db": -10, "ratio": 4.0, "attack_ms": 3, "release_ms": 70},
            None,
        ),
        (
            "bass",
            -10.0,
            6.0,
            {"threshold_db": -8, "ratio": 5.0, "attack_ms": 5, "release_ms": 100},
            {"amount_db": -5.0, "attack_ms": 3, "release_ms": 80},
        ),
        (
            "snare",
            -14.0,
            14.0,
            {"threshold_db": -12, "ratio": 3.0, "attack_ms": 2, "release_ms": 60},
            None,
        ),
        ("hihat", -20.0, 20.0, None, None),
        (
            "vocal",
            -14.0,
            12.0,
            {"threshold_db": -14, "ratio": 2.5, "attack_ms": 8, "release_ms": 150},
            None,
        ),
    ]:
        seeds.append(
            TrackReference(
                role=role,
                genre="hip_hop",
                lufs=lufs,
                crest_factor=crest,
                compression=comp,
                sidechain=sc,
                source="seed_hip_hop",
                confidence=0.9,
            )
        )

    # --- DnB ---
    for role, lufs, crest, comp, sc in [
        (
            "kick",
            -14.0,
            10.0,
            {"threshold_db": -11, "ratio": 3.5, "attack_ms": 3, "release_ms": 60},
            None,
        ),
        (
            "bass",
            -12.0,
            8.0,
            {"threshold_db": -9, "ratio": 5.0, "attack_ms": 4, "release_ms": 80},
            {"amount_db": -6.0, "attack_ms": 3, "release_ms": 70},
        ),
        (
            "snare",
            -14.0,
            14.0,
            {"threshold_db": -10, "ratio": 3.5, "attack_ms": 2, "release_ms": 50},
            None,
        ),
        ("hihat", -22.0, 20.0, None, None),
    ]:
        seeds.append(
            TrackReference(
                role=role,
                genre="dnb",
                lufs=lufs,
                crest_factor=crest,
                compression=comp,
                sidechain=sc,
                source="seed_dnb",
                confidence=0.9,
            )
        )

    # --- Pop ---
    for role, lufs, crest, comp in [
        (
            "vocal",
            -14.0,
            12.0,
            {"threshold_db": -14, "ratio": 2.5, "attack_ms": 8, "release_ms": 120},
        ),
        (
            "kick",
            -14.0,
            10.0,
            {"threshold_db": -12, "ratio": 3.0, "attack_ms": 5, "release_ms": 80},
        ),
        (
            "snare",
            -14.0,
            12.0,
            {"threshold_db": -11, "ratio": 3.0, "attack_ms": 3, "release_ms": 70},
        ),
        (
            "bass",
            -16.0,
            8.0,
            {"threshold_db": -12, "ratio": 3.5, "attack_ms": 8, "release_ms": 100},
        ),
    ]:
        seeds.append(
            TrackReference(
                role=role,
                genre="pop",
                lufs=lufs,
                crest_factor=crest,
                compression=comp,
                source="seed_pop",
                confidence=0.9,
            )
        )

    return seeds


def init_default_db(db_path: str | None = None) -> ReferenceStore:
    """Create or load the reference store, seeding it if empty."""
    store = ReferenceStore(db_path)
    if not store.references:
        store.references = _build_seed_references()
        store.save()
    return store


def save_mix_to_references(
    analyses: list[Any],
    mix_result: Any,
    genre: str,
    source: str = "user_mix",
    store: ReferenceStore | None = None,
) -> int:
    """Save a completed mix's track data to the reference store.

    Called after each successful preview render to build the RAG database
    over time from real user mixes.

    Args:
        analyses: list of TrackAnalysis from analyzer
        mix_result: MixResult from mixer.compute_mix
        genre: target genre/style
        source: identifier for where this mix came from
        store: optional pre-loaded store; uses default if None

    Returns:
        Number of references saved.
    """
    from logging import getLogger

    _log = getLogger("mmc.reference_store")

    if store is None:
        store = init_default_db()

    saved = 0
    for analysis, corr in zip(analyses, mix_result.track_corrections, strict=False):
        # Build band_energy dict from analysis if available
        band_energy = {}
        if hasattr(analysis, "band_energy") and analysis.band_energy and isinstance(analysis.band_energy, dict):
            band_energy = analysis.band_energy

        ref = TrackReference(
            role=corr.role,
            genre=genre,
            lufs=getattr(analysis, "lufs", -14.0),
            rms_db=getattr(analysis, "rms_db", -20.0),
            peak_db=getattr(analysis, "peak_db", -6.0),
            crest_factor=(getattr(analysis, "peak_db", -6.0) - getattr(analysis, "rms_db", -20.0)),
            band_energy=band_energy,
            source=source,
            confidence=0.75,
        )

        # Save processing applied from the mix result
        if hasattr(corr, "band_corrections") and corr.band_corrections:
            ref.eq_bands = [
                {"freq": bc.center_hz, "gain_db": bc.gain_db}
                for bc in corr.band_corrections
                if hasattr(bc, "center_hz")
            ]

        store.add(ref)
        saved += 1

    if saved > 0:
        store.save()
        _log.info("Saved %d references from %s (genre=%s)", saved, source, genre)

    return saved
