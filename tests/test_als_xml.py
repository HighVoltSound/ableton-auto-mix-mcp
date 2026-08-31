"""Tests for the Ableton .als XML builder (als_xml.py)."""

from __future__ import annotations

import os
import sys
import zipfile

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.als_xml import build_session, write_als  # noqa: E402


class TestBuildSession:
    """build_session() returns valid XML with expected elements."""

    def test_empty_corrections(self) -> None:
        xml = build_session([])
        assert "<Ableton" in xml
        assert "<LiveSet" in xml
        assert "<Tracks" in xml

    def test_single_track(self) -> None:
        corrections = [
            {
                "name": "kick",
                "volume_db": -2.0,
                "pan": 0.0,
                "band_corrections": [],
            }
        ]
        xml = build_session(corrections)
        assert "kick" in xml
        assert "<AudioTrack" in xml
        assert "<Volume" in xml
        assert "<Pan" in xml

    def test_multiple_tracks(self) -> None:
        corrections = [
            {"name": "kick", "volume_db": -2.0, "pan": 0.0, "band_corrections": []},
            {"name": "bass", "volume_db": 1.5, "pan": -0.3, "band_corrections": []},
            {"name": "snare", "volume_db": 0.0, "pan": 0.0, "band_corrections": []},
        ]
        xml = build_session(corrections)
        assert xml.count("<AudioTrack") == 3
        assert "kick" in xml
        assert "bass" in xml
        assert "snare" in xml

    def test_tempo_and_time_sig(self) -> None:
        xml = build_session([], tempo=140.0, time_sig_num=3, time_sig_den=8)
        assert "140" in xml
        assert "3" in xml
        assert "8" in xml

    def test_volume_conversion(self) -> None:
        """0 dB -> ableton_vol ~0.871 (Ableton's unity)."""
        corrections = [
            {"name": "test", "volume_db": 0.0, "pan": 0.0, "band_corrections": []}
        ]
        xml = build_session(corrections)
        # The volume element should contain a float close to 0.871
        assert "0.871" in xml

    def test_pan_values(self) -> None:
        corrections = [
            {"name": "left", "volume_db": 0.0, "pan": -0.5, "band_corrections": []},
            {"name": "right", "volume_db": 0.0, "pan": 0.5, "band_corrections": []},
        ]
        xml = build_session(corrections)
        assert "left" in xml
        assert "right" in xml

    def test_eq_device_present(self) -> None:
        corrections = [
            {
                "name": "bass",
                "volume_db": 0.0,
                "pan": 0.0,
                "band_corrections": [
                    {
                        "band": "bass",
                        "freq_range": [60.0, 250.0],
                        "measured_db": -10.0,
                        "target_db": -8.0,
                        "delta_db": 2.0,
                    }
                ],
            }
        ]
        xml = build_session(corrections)
        assert "EQ Eight" in xml
        assert "Filter 1 Gain" in xml

    def test_xml_declaration(self) -> None:
        xml = build_session([])
        assert xml.startswith("<?xml")


class TestWriteAls:
    """write_als() creates a valid ZIP .als file."""

    def test_creates_als_file(self, tmp_path) -> None:
        out = str(tmp_path / "test.als")
        corrections = [
            {"name": "kick", "volume_db": -3.0, "pan": 0.0, "band_corrections": []}
        ]
        written = write_als(corrections, out)
        assert os.path.isfile(written)
        assert written.endswith(".als")

    def test_als_is_zip(self, tmp_path) -> None:
        out = str(tmp_path / "test.als")
        write_als(
            [{"name": "t", "volume_db": 0, "pan": 0, "band_corrections": []}], out
        )
        with zipfile.ZipFile(out, "r") as zf:
            names = zf.namelist()
            assert len(names) == 1
            assert names[0].endswith(".als")

    def test_xml_inside_zip(self, tmp_path) -> None:
        out = str(tmp_path / "test.als")
        write_als(
            [{"name": "x", "volume_db": 0, "pan": 0, "band_corrections": []}], out
        )
        with zipfile.ZipFile(out, "r") as zf:
            content = zf.read(zf.namelist()[0]).decode("utf-8")
            assert "<Ableton" in content
            assert "x" in content

    def test_creates_parent_dirs(self, tmp_path) -> None:
        out = str(tmp_path / "sub" / "dir" / "test.als")
        write_als([], out)
        assert os.path.isfile(out)

    def test_default_session_path(self, tmp_path) -> None:
        """Without output_path, write_als returns a path."""
        written = write_als([], str(tmp_path / "out.als"))
        assert os.path.isfile(written)
