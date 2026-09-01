"""Smoke tests for the HTTP API wrapper (api_app.py).

Uses FastAPI TestClient against a tiny synthetic render directory
(kick / bass / snare / vocals), no Ableton needed.
"""

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
    """A tiny 4-track project: kick, bass, snare, vocals."""
    tmp = str(tmp_path_factory.mktemp("renders"))
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
# Styles
# ---------------------------------------------------------------------------


def test_styles(client: TestClient) -> None:
    resp = client.get("/api/styles")
    assert resp.status_code == 200
    styles = resp.json()
    assert isinstance(styles, list) and len(styles) >= 5
    ids = {s["id"] for s in styles}
    assert {"techno", "breaks", "balanced"} <= ids
    first = styles[0]
    assert "targets" in first and "lufs" in first["targets"]


def test_style_detail_and_unknown(client: TestClient) -> None:
    resp = client.get("/api/style/techno")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "techno"
    assert body["target_lufs"] == body["target_lufs"]  # serializable
    assert "frequency_balance" in body

    assert client.get("/api/style/no_such_style").status_code == 404


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------


def test_analyze(client: TestClient, render_dir: str) -> None:
    resp = client.post("/api/analyze", json={"directory": render_dir})
    assert resp.status_code == 200
    body = resp.json()
    names = {t["name"] for t in body["tracks"]}
    assert {"kick", "bass", "snare", "vocals"} <= names
    kick = next(t for t in body["tracks"] if t["name"] == "kick")
    assert -60 < kick["lufs"] < 0
    assert "sub_bass" in kick["bandwidth_db"]
    assert "elapsed_s" in body


def test_analyze_missing_dir(client: TestClient) -> None:
    resp = client.post("/api/analyze", json={"directory": "Z:/no/such/dir"})
    assert resp.status_code == 400


def test_suggest(client: TestClient, render_dir: str) -> None:
    resp = client.post("/api/suggest", json={"directory": render_dir})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggested_style"]
    assert len(body["ranked"]) >= 2
    assert "elapsed_s" in body


def test_conflicts(client: TestClient, render_dir: str) -> None:
    resp = client.post("/api/conflicts", json={"directory": render_dir})
    assert resp.status_code == 200
    body = resp.json()
    assert body["conflicts_found"] == len(body["conflicts"])
    for c in body["conflicts"]:
        assert c["suggestion"]


# ---------------------------------------------------------------------------
# Mix / preview / release
# ---------------------------------------------------------------------------


def test_mix_dry_run(client: TestClient, render_dir: str) -> None:
    resp = client.post(
        "/api/mix",
        json={
            "style": "techno",
            "directory": render_dir,
            "dry_run": True,
            "manual_gain": {"bass": -2.0},
            "sidechain_db": -3.0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["style"] == "techno"
    assert body["dry_run"] is True
    assert len(body["track_corrections"]) >= 4
    assert any(t["role"] == "kick" for t in body["track_corrections"])
    assert body["master_notes"]
    assert "elapsed_s" in body


def test_mix_unknown_style(client: TestClient, render_dir: str) -> None:
    resp = client.post("/api/mix", json={"style": "nope", "directory": render_dir})
    assert resp.status_code == 404


def test_preview(client: TestClient, render_dir: str) -> None:
    out = os.path.join(render_dir, "preview_techno_api.wav")
    resp = client.post(
        "/api/preview",
        json={"style": "techno", "directory": render_dir, "output_path": out},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert os.path.isfile(body["output_path"])
    assert body["duration_s"] > 0
    assert body["elapsed_s"] > 0
    info = sf.info(body["output_path"])
    assert abs(info.duration - body["duration_s"]) < 0.1


def test_release_with_existing_output(client: TestClient, render_dir: str) -> None:
    out = os.path.join(render_dir, "preview_techno_api.wav")
    resp = client.post(
        "/api/release",
        json={"style": "techno", "directory": render_dir, "output_path": out},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in ("ready", "needs_work")
    assert len(body["metrics"]) >= 4
    assert all(m["status"] in ("ok", "needs_work") for m in body["metrics"])
    assert "elapsed_s" in body


def test_release_requires_args(client: TestClient) -> None:
    resp = client.post("/api/release", json={})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Audio serving + waveform
# ---------------------------------------------------------------------------


def test_audio_serving(client: TestClient, render_dir: str) -> None:
    wav = os.path.join(render_dir, "kick.wav")
    resp = client.get("/api/audio", params={"path": wav})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert len(resp.content) > 1000


def test_audio_rejects_outside_paths(client: TestClient, tmp_path) -> None:
    # a .wav outside every registered root must be rejected
    rogue = tmp_path / "evil.wav"
    sf.write(str(rogue), np.zeros(SR, dtype="float32"), SR)
    assert client.get("/api/audio", params={"path": str(rogue)}).status_code == 400
    # non-wav extension must be rejected even inside a whitelisted dir
    txt = os.path.join(_any_root(), "notes.txt")
    assert client.get("/api/audio", params={"path": txt}).status_code == 400


def _any_root() -> str:
    from ableton_auto_mix.api_app import DEFAULT_RENDER_DIR

    return DEFAULT_RENDER_DIR


def test_waveform(client: TestClient, render_dir: str) -> None:
    wav = os.path.join(render_dir, "snare.wav")
    resp = client.get("/api/waveform", params={"path": wav, "points": 100})
    assert resp.status_code == 200
    body = resp.json()
    assert 90 <= body["peak_count"] <= 101
    assert all(0.0 <= p <= 1.0 for p in body["peaks"])
    assert body["duration_s"] > 0
    assert body["sample_rate"] == SR


def test_waveform_missing_file(client: TestClient, render_dir: str) -> None:
    missing = os.path.join(render_dir, "ghost.wav")
    assert client.get("/api/waveform", params={"path": missing}).status_code == 404


# ---------------------------------------------------------------------------
# Project save / load
# ---------------------------------------------------------------------------


def test_project_save_and_load(client: TestClient, render_dir: str) -> None:
    state = {
        "directory": render_dir,
        "style": "breaks",
        "analyses": [{"name": "kick", "lufs": -10.0}],
        "name": "API Test",
    }
    save_resp = client.post("/api/project/save", json={"state": state})
    assert save_resp.status_code == 200
    body = save_resp.json()
    assert "path" in body
    assert body["directory"] == render_dir

    load_resp = client.post("/api/project/load", json={"path": body["path"]})
    assert load_resp.status_code == 200
    loaded = load_resp.json()
    assert loaded["style"] == "breaks"
    assert loaded["directory"] == render_dir
    assert loaded["name"] == "API Test"
    assert len(loaded["analyses"]) == 1


def test_project_save_explicit_path(client: TestClient, tmp_path) -> None:
    path = str(tmp_path / "custom.mmc.json")
    state = {"directory": "/tmp", "style": "techno"}
    resp = client.post("/api/project/save", json={"state": state, "path": path})
    assert resp.status_code == 200
    assert resp.json()["path"] == path
    assert os.path.isfile(path)


def test_project_load_missing(client: TestClient, tmp_path) -> None:
    resp = client.post("/api/project/load", json={"path": str(tmp_path / "nope.mmc.json")})
    assert resp.status_code == 404


def test_project_save_no_dir_no_path(client: TestClient) -> None:
    resp = client.post("/api/project/save", json={"state": {"style": "x"}})
    assert resp.status_code == 400


def test_project_recent(client: TestClient, render_dir: str) -> None:
    state = {"directory": render_dir, "style": "techno"}
    client.post("/api/project/save", json={"state": state})
    resp = client.get("/api/project/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert "projects" in body
    assert isinstance(body["projects"], list)
