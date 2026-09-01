"""Tests for the Ableton export engine (ableton_export.py)."""

from __future__ import annotations

import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.ableton_export import export_to_ableton  # noqa: E402
from ableton_auto_mix.mixer import BandCorrection, TrackCorrection  # noqa: E402


def _make_correction(
    name: str,
    index: int = 0,
    volume_db: float = 0.0,
    pan: float = 0.0,
    band_corrections: list | None = None,
) -> TrackCorrection:
    return TrackCorrection(
        index=index,
        name=name,
        role="unknown",
        volume_db=volume_db,
        pan=pan,
        band_corrections=band_corrections or [],
    )


class TestExportToFile:
    """export_to_ableton with mode='file'."""

    def test_generates_als_file(self, tmp_path) -> None:
        out = str(tmp_path / "session.als")
        corrections = [_make_correction("kick", volume_db=-2.0)]
        result = export_to_ableton(corrections, mode="file", session_path=out)
        assert result.applied == 1
        assert result.errors == []
        assert os.path.isfile(result.session_path or "")

    def test_als_extension_auto_added(self, tmp_path) -> None:
        out = str(tmp_path / "session")
        corrections = [_make_correction("kick", volume_db=-2.0)]
        result = export_to_ableton(corrections, mode="file", session_path=out)
        assert result.session_path is not None
        assert result.session_path.endswith(".als")

    def test_no_corrections_returns_error(self) -> None:
        corrections = [_make_correction("kick", volume_db=0.0, pan=0.0)]
        result = export_to_ableton(corrections, mode="file")
        assert result.applied == 0
        assert len(result.errors) > 0

    def test_multiple_corrections(self, tmp_path) -> None:
        out = str(tmp_path / "multi.als")
        corrections = [
            _make_correction("kick", volume_db=-2.0, pan=0.0),
            _make_correction("bass", volume_db=1.5, pan=-0.3),
            _make_correction(
                "snare",
                volume_db=0.0,
                pan=0.0,
                band_corrections=[
                    BandCorrection(
                        band="mids",
                        freq_range=[500.0, 2000.0],
                        measured_db=-12.0,
                        target_db=-10.0,
                        delta_db=2.0,
                    )
                ],
            ),
        ]
        result = export_to_ableton(corrections, mode="file", session_path=out)
        assert result.applied == 3
        assert result.errors == []
        assert os.path.isfile(result.session_path or "")

    def test_eq_corrections_included(self, tmp_path) -> None:
        out = str(tmp_path / "eq.als")
        corrections = [
            _make_correction(
                "bass",
                volume_db=0.0,
                band_corrections=[
                    BandCorrection(
                        band="bass",
                        freq_range=[60.0, 250.0],
                        measured_db=-10.0,
                        target_db=-8.0,
                        delta_db=2.0,
                    )
                ],
            )
        ]
        result = export_to_ableton(corrections, mode="file", session_path=out)
        assert result.applied == 1
        assert os.path.isfile(result.session_path or "")


class TestExportToLive:
    """export_to_ableton with mode='live' (mocked client)."""

    def test_connection_error(self) -> None:
        corrections = [_make_correction("kick", volume_db=-2.0)]
        result = export_to_ableton(corrections, mode="live")
        assert len(result.errors) > 0
        assert "Cannot connect" in result.errors[0]

    def test_unknown_mode(self) -> None:
        corrections = [_make_correction("kick", volume_db=-2.0)]
        result = export_to_ableton(corrections, mode="invalid")
        assert len(result.errors) > 0
        assert "Unknown export mode" in result.errors[0]


class TestExportResult:
    """ExportResult dataclass."""

    def test_to_dict(self) -> None:
        from ableton_auto_mix.ableton_export import ExportResult

        r = ExportResult(applied=3, skipped=1, errors=["test"], session_path="/a.als", mode="file")
        d = r.to_dict()
        assert d["applied"] == 3
        assert d["skipped"] == 1
        assert d["errors"] == ["test"]
        assert d["session_path"] == "/a.als"
        assert d["mode"] == "file"
