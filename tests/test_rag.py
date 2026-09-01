"""Tests for RAG-enhanced ai_recommender."""

from __future__ import annotations

import os

from ableton_auto_mix.ai_recommender import (
    Recommendations,
    _retrieve_references,
    recommend,
)
from ableton_auto_mix.reference_store import (
    ReferenceStore,
    TrackReference,
    _build_seed_references,
    init_default_db,
)

# ---------------------------------------------------------------------------
# ReferenceStore tests
# ---------------------------------------------------------------------------


class TestReferenceStore:
    """Test the reference store CRUD and retrieval."""

    def test_seed_references_not_empty(self) -> None:
        seeds = _build_seed_references()
        assert len(seeds) > 0
        assert all(isinstance(r, TrackReference) for r in seeds)

    def test_init_default_db_creates_file(self, tmp_path: str) -> None:
        db_path = os.path.join(tmp_path, "test_db.json")
        store = init_default_db(db_path)
        assert len(store.references) > 0
        assert os.path.exists(db_path)

    def test_save_and_load(self, tmp_path: str) -> None:
        db_path = os.path.join(tmp_path, "test_db.json")
        store = ReferenceStore(db_path)
        store.add(TrackReference(role="kick", genre="techno", lufs=-16.0))
        store.save()

        loaded = ReferenceStore(db_path)
        assert len(loaded.references) == 1
        assert loaded.references[0].role == "kick"

    def test_retrieve_same_role_same_genre(self, tmp_path: str) -> None:
        db_path = os.path.join(tmp_path, "test_db.json")
        store = ReferenceStore(db_path)
        store.add(TrackReference(role="kick", genre="techno", lufs=-16.0, crest_factor=10.0))
        store.add(TrackReference(role="kick", genre="techno", lufs=-14.0, crest_factor=12.0))
        store.add(TrackReference(role="bass", genre="techno", lufs=-18.0))

        results = store.retrieve(role="kick", genre="techno", k=2)
        assert len(results) == 2
        assert all(r.role == "kick" for r in results)

    def test_retrieve_prefers_matching_role(self, tmp_path: str) -> None:
        db_path = os.path.join(tmp_path, "test_db.json")
        store = ReferenceStore(db_path)
        store.add(TrackReference(role="kick", genre="hip_hop", lufs=-12.0))
        store.add(TrackReference(role="bass", genre="techno", lufs=-18.0))

        results = store.retrieve(role="kick", genre="techno", k=2)
        # Kick should rank first despite genre mismatch
        assert results[0].role == "kick"

    def test_retrieve_empty_store(self, tmp_path: str) -> None:
        db_path = os.path.join(tmp_path, "empty_db.json")
        store = ReferenceStore(db_path)
        results = store.retrieve(role="kick", genre="techno")
        assert results == []


# ---------------------------------------------------------------------------
# RAG-enhanced recommend() tests
# ---------------------------------------------------------------------------


def _make_track(
    name: str,
    role: str = "unknown",
    lufs: float = -14.0,
    rms_db: float = -20.0,
    peak_db: float = -6.0,
    band_energy: dict | None = None,
) -> dict:
    return {
        "name": name,
        "role": role,
        "lufs": lufs,
        "rms_db": rms_db,
        "peak_db": peak_db,
        "band_energy": band_energy or {},
    }


class TestRecommendRAG:
    """Test that RAG-enhanced recommend() produces valid output."""

    def test_basic_recommend(self) -> None:
        tracks = [
            _make_track("kick", "kick", lufs=-16.0, rms_db=-18.0, peak_db=-6.0),
            _make_track("bass", "bass", lufs=-18.0, rms_db=-20.0, peak_db=-8.0),
        ]
        result = recommend(tracks, genre="techno")
        assert isinstance(result, Recommendations)
        assert len(result.recommendations) > 0
        assert result.summary

    def test_recommend_has_references(self) -> None:
        tracks = [
            _make_track("kick", "kick", lufs=-16.0, rms_db=-18.0, peak_db=-6.0),
            _make_track("bass", "bass", lufs=-18.0, rms_db=-20.0, peak_db=-8.0),
        ]
        result = recommend(tracks, genre="techno")
        # At least some recs should have RAG references
        rag_recs = [r for r in result.recommendations if r.references]
        assert len(rag_recs) > 0, "No RAG references found in recommendations"

    def test_recommend_genre_aware(self) -> None:
        techno_tracks = [_make_track("kick", "kick", lufs=-16.0, rms_db=-18.0, peak_db=-6.0)]
        ambient_tracks = [_make_track("pad", "pad", lufs=-24.0, rms_db=-28.0, peak_db=-10.0)]

        techno_recs = recommend(techno_tracks, genre="techno")
        ambient_recs = recommend(ambient_tracks, genre="ambient")

        # Both should produce recommendations
        assert len(techno_recs.recommendations) > 0
        assert len(ambient_recs.recommendations) > 0

    def test_recommend_confidence_range(self) -> None:
        tracks = [
            _make_track("kick", "kick", lufs=-16.0, rms_db=-18.0, peak_db=-6.0),
            _make_track("bass", "bass", lufs=-18.0, rms_db=-20.0, peak_db=-8.0),
            _make_track("snare", "snare", lufs=-16.0, rms_db=-18.0, peak_db=-6.0),
        ]
        result = recommend(tracks, genre="techno")
        for rec in result.recommendations:
            assert 0.0 <= rec.confidence <= 1.0, f"Confidence out of range: {rec.confidence}"

    def test_recommend_role_map(self) -> None:
        tracks = [
            _make_track("kick", "kick"),
            _make_track("bass", "bass"),
        ]
        result = recommend(tracks, genre="techno")
        assert result.role_map == {"kick": "kick", "bass": "bass"}


# ---------------------------------------------------------------------------
# _retrieve_references tests
# ---------------------------------------------------------------------------


class TestRetrieveReferences:
    """Test the retrieval function directly."""

    def test_retrieve_returns_references(self) -> None:
        tracks = [_make_track("kick", "kick", lufs=-16.0)]
        role_map = {"kick": "kick"}
        refs = _retrieve_references(tracks, role_map, "techno")
        assert "kick" in refs
        assert len(refs["kick"]) > 0

    def test_retrieve_unknown_role(self) -> None:
        tracks = [_make_track("mystery", "unknown")]
        role_map = {"mystery": "unknown"}
        refs = _retrieve_references(tracks, role_map, "techno")
        # Unknown roles still get retrieved (genre match)
        assert "mystery" in refs
