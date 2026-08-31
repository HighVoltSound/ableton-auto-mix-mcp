"""Tests for project save/load, auto-save, and recent projects."""

from __future__ import annotations

import json
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))

from ableton_auto_mix.project import (  # noqa: E402
    AUTO_SAVE_NAME,
    ProjectState,
    auto_save,
    list_recent_projects,
    load_project,
    save_project,
)


def _sample_state() -> ProjectState:
    return ProjectState(
        directory="/tmp/renders",
        style="breaks",
        analyses=[{"name": "KICK", "lufs": -10.2}],
        corrections=[{"track": "KICK", "volume_db": -1.5}],
        plan={"mix_actions": [], "master_actions": []},
        preview_path="/tmp/preview.wav",
        name="Test Project",
    )


# ---------------------------------------------------------------------------
# Roundtrip
# ---------------------------------------------------------------------------


def test_save_load_roundtrip(tmp_path):
    path = str(tmp_path / "test.mmc.json")
    state = _sample_state()
    saved = save_project(state, path)

    loaded = load_project(saved)
    assert loaded.directory == state.directory
    assert loaded.style == state.style
    assert loaded.analyses == state.analyses
    assert loaded.corrections == state.corrections
    assert loaded.plan == state.plan
    assert loaded.preview_path == state.preview_path
    assert loaded.name == state.name
    assert loaded.version == "0.3"
    assert loaded.created_at
    assert loaded.updated_at


def test_save_creates_parent_dirs(tmp_path):
    path = str(tmp_path / "sub" / "deep" / "project.mmc.json")
    state = _sample_state()
    saved = save_project(state, path)
    assert os.path.isfile(saved)


def test_load_nonexistent_raises(tmp_path):
    try:
        load_project(str(tmp_path / "nope.mmc.json"))
        assert False, "should have raised"
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Auto-save
# ---------------------------------------------------------------------------


def test_auto_save(tmp_path):
    state = _sample_state()
    saved = auto_save(state, str(tmp_path))
    assert os.path.basename(saved) == AUTO_SAVE_NAME
    loaded = load_project(saved)
    assert loaded.directory == state.directory


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def test_load_v02_file(tmp_path):
    """A v0.2 file with missing fields should load gracefully."""
    v02 = {
        "version": "0.2",
        "directory": "/some/dir",
        "style": "techno",
    }
    path = str(tmp_path / "old.mmc.json")
    with open(path, "w") as f:
        json.dump(v02, f)

    loaded = load_project(path)
    assert loaded.version == "0.3"
    assert loaded.analyses == []
    assert loaded.corrections == []
    assert loaded.plan is None
    assert loaded.selected_style_id is None


def test_load_invalid_json(tmp_path):
    path = str(tmp_path / "bad.mmc.json")
    with open(path, "w") as f:
        f.write("not json {{{")
    try:
        load_project(path)
        assert False, "should have raised"
    except (ValueError, json.JSONDecodeError):
        pass


# ---------------------------------------------------------------------------
# List recent
# ---------------------------------------------------------------------------


def test_list_recent_projects(tmp_path):
    for i in range(3):
        state = ProjectState(
            directory=str(tmp_path),
            style=f"style_{i}",
            name=f"Project {i}",
        )
        save_project(state, str(tmp_path / f"proj_{i}.mmc.json"))

    results = list_recent_projects(max_count=5, extra_dirs=[str(tmp_path)])
    assert len(results) >= 3
    paths = {r["path"] for r in results}
    for i in range(3):
        assert any(f"proj_{i}.mmc.json" in p for p in paths)


def test_list_recent_max_count(tmp_path):
    for i in range(5):
        state = ProjectState(directory=str(tmp_path), style=f"s{i}")
        save_project(state, str(tmp_path / f"p{i}.mmc.json"))

    results = list_recent_projects(max_count=2, extra_dirs=[str(tmp_path)])
    assert len(results) <= 2


# ---------------------------------------------------------------------------
# Field defaults
# ---------------------------------------------------------------------------


def test_default_state():
    state = ProjectState()
    assert state.version == "0.3"
    assert state.directory == ""
    assert state.style == ""
    assert state.analyses == []
    assert state.corrections == []
    assert state.plan is None
    assert state.preview_path is None
    assert state.before_path is None
    assert state.match_eq_curve is None
    assert state.conflicts is None
    assert state.manual_gain is None
    assert state.sidechain_db is None
    assert state.name == ""


def test_to_dict():
    state = _sample_state()
    d = state.to_dict()
    assert isinstance(d, dict)
    assert d["directory"] == "/tmp/renders"
    assert d["style"] == "breaks"
    assert len(d["analyses"]) == 1


# ---------------------------------------------------------------------------
# JSON roundtrip — to_dict produces serializable JSON
# ---------------------------------------------------------------------------


def test_to_dict_json_serializable():
    state = _sample_state()
    d = state.to_dict()
    s = json.dumps(d)
    assert len(s) > 10
