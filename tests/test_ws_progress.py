"""Tests for WebSocket progress streaming (ws_manager + async endpoints)."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.api_app import _register_dir, app  # noqa: E402
from ableton_auto_mix.ws_manager import (  # noqa: E402
    ConnectionManager,
    ProgressReporter,
    new_room_id,
)

SR = 44100
DUR = 2.0


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _tone(freq: float, dur: float = DUR) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    return np.sin(2 * np.pi * freq * t)


@pytest.fixture(scope="module")
def render_dir(tmp_path_factory) -> str:
    tmp = str(tmp_path_factory.mktemp("ws_renders"))
    n_kick = int(SR * 0.25)
    t = np.linspace(0, 0.25, n_kick, endpoint=False)
    kick = (np.exp(-t * 30) * np.sin(2 * np.pi * 60 * t)).reshape(-1, 1)
    kick = np.pad(kick, ((0, SR * int(DUR) - n_kick), (0, 0)))
    sf.write(os.path.join(tmp, "kick.wav"), np.repeat(kick, 2, axis=1), SR, subtype="PCM_16")

    bass = _tone(80).reshape(-1, 1) * 0.5
    sf.write(os.path.join(tmp, "bass.wav"), np.repeat(bass, 2, axis=1), SR, subtype="PCM_16")

    rng = np.random.default_rng(7)
    noise = rng.uniform(-1, 1, SR * int(DUR)) * np.exp(-np.linspace(0, 1, SR * int(DUR)) * 15)
    snare = noise.reshape(-1, 1) * 0.4
    sf.write(
        os.path.join(tmp, "snare.wav"),
        np.repeat(snare, 2, axis=1),
        SR,
        subtype="PCM_16",
    )

    sf.write(os.path.join(tmp, "vocals.wav"), _tone(440) * 0.15, SR, subtype="PCM_16")
    _register_dir(tmp)
    return tmp


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------


class TestConnectionManager:
    def test_new_room_id_unique(self) -> None:
        ids = {new_room_id() for _ in range(100)}
        assert len(ids) == 100

    def test_new_room_id_length(self) -> None:
        rid = new_room_id()
        assert len(rid) == 12

    def test_cleanup_room(self) -> None:
        mgr = ConnectionManager()
        mgr._rooms["test"] = set()  # type: ignore[attr-defined]
        mgr.cleanup_room("test")
        assert "test" not in mgr._rooms  # type: ignore[attr-defined]

    def test_active_rooms(self) -> None:
        mgr = ConnectionManager()
        mgr._rooms["a"] = set()  # type: ignore[attr-defined]
        mgr._rooms["b"] = set()  # type: ignore[attr-defined]
        assert set(mgr.active_rooms) == {"a", "b"}
        mgr.cleanup_room("a")
        assert mgr.active_rooms == ["b"]


class TestProgressReporter:
    def test_reporter_call(self) -> None:
        """ProgressReporter.__call__ should not raise."""
        reporter = ProgressReporter("test_room")
        reporter("loading", 10, "Reading tracks")
        reporter("done", 100)

    def test_reporter_done(self) -> None:
        reporter = ProgressReporter("test_room")
        reporter.done({"output_path": "/tmp/test.wav"})

    def test_reporter_error(self) -> None:
        reporter = ProgressReporter("test_room")
        reporter.error("Something went wrong")


# ---------------------------------------------------------------------------
# Async API endpoint tests
# ---------------------------------------------------------------------------


class TestAsyncEndpoints:
    def test_preview_async_returns_room_id(self, client: TestClient, render_dir: str) -> None:
        resp = client.post(
            "/api/preview",
            json={"style": "techno", "directory": render_dir, "async_mode": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "room_id" in body
        assert isinstance(body["room_id"], str)
        assert len(body["room_id"]) == 12

    def test_analyze_async_returns_room_id(self, client: TestClient, render_dir: str) -> None:
        resp = client.post(
            "/api/analyze",
            json={"directory": render_dir, "async_mode": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "room_id" in body
        assert isinstance(body["room_id"], str)

    def test_preview_sync_still_works(self, client: TestClient, render_dir: str) -> None:
        """Backward compat: async=false (default) returns sync response."""
        out = os.path.join(render_dir, "preview_sync_test.wav")
        resp = client.post(
            "/api/preview",
            json={"style": "techno", "directory": render_dir, "output_path": out},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "output_path" in body
        assert body["duration_s"] > 0

    def test_export_async_returns_room_id(self, client: TestClient) -> None:
        corrections = [
            {
                "name": "kick",
                "index": 0,
                "role": "kick",
                "volume_db": -2.0,
                "band_corrections": [],
            }
        ]
        resp = client.post(
            "/api/export",
            json={"corrections": corrections, "mode": "file", "async_mode": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "room_id" in body


# ---------------------------------------------------------------------------
# Preview progress_callback integration
# ---------------------------------------------------------------------------


class TestPreviewProgressCallback:
    def test_preview_with_callback(self, render_dir: str) -> None:
        """Verify progress_callback is called during preview render."""
        from ableton_auto_mix.preview import render_preview_mix
        from ableton_auto_mix.profiles import get_profile

        profile = get_profile("techno")
        stages_seen: list[str] = []

        def cb(stage: str, pct: int, detail: str) -> None:
            stages_seen.append(stage)

        out = os.path.join(render_dir, "preview_cb_test.wav")
        render_preview_mix(
            render_dir,
            profile,
            output_path=out,
            progress_callback=cb,
        )
        assert len(stages_seen) > 0
        assert "done" in stages_seen

    def test_analyze_with_callback(self, render_dir: str) -> None:
        """Verify progress_callback is called during analysis."""
        from ableton_auto_mix.analyzer import analyze_directory

        stages_seen: list[str] = []

        def cb(stage: str, pct: int, detail: str) -> None:
            stages_seen.append(stage)

        results = analyze_directory(render_dir, progress_callback=cb)
        assert len(results) > 0
        assert "analyzing" in stages_seen
