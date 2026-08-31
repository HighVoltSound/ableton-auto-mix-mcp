"""Tests for the POST /api/export endpoint."""

from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.api_app import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


class TestApiExport:
    """POST /api/export endpoint tests."""

    def test_file_export(self, client, tmp_path_factory) -> None:
        tmp = str(tmp_path_factory.mktemp("export"))
        out = os.path.join(tmp, "test.als")
        payload = {
            "corrections": [
                {
                    "name": "kick",
                    "index": 0,
                    "role": "kick",
                    "volume_db": -2.0,
                    "pan": 0.0,
                    "band_corrections": [],
                }
            ],
            "mode": "file",
            "session_path": out,
            "tempo": 128.0,
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] == 1
        assert data["mode"] == "file"
        assert data["session_path"] is not None
        assert os.path.isfile(data["session_path"])

    def test_live_export_no_ableton(self, client) -> None:
        payload = {
            "corrections": [
                {
                    "name": "kick",
                    "index": 0,
                    "role": "kick",
                    "volume_db": -2.0,
                    "pan": 0.0,
                    "band_corrections": [],
                }
            ],
            "mode": "live",
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    def test_empty_corrections(self, client) -> None:
        payload = {
            "corrections": [
                {
                    "name": "kick",
                    "index": 0,
                    "role": "unknown",
                    "volume_db": 0.0,
                    "pan": 0.0,
                    "band_corrections": [],
                }
            ],
            "mode": "file",
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] == 0
        assert len(data["errors"]) > 0

    def test_with_eq_corrections(self, client, tmp_path_factory) -> None:
        tmp = str(tmp_path_factory.mktemp("export_eq"))
        out = os.path.join(tmp, "eq.als")
        payload = {
            "corrections": [
                {
                    "name": "bass",
                    "index": 0,
                    "role": "bass",
                    "volume_db": 0.0,
                    "pan": -0.3,
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
            ],
            "mode": "file",
            "session_path": out,
        }
        resp = client.post("/api/export", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] == 1
        assert os.path.isfile(data["session_path"])
