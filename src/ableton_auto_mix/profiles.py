"""Style profile loading and validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

PACKAGE_STYLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles")


@dataclass
class StyleProfile:
    name: str
    label: str
    target_lufs: float
    target_lra: float
    tempo_range: list[float]
    stereo_width: str
    frequency_balance: list[dict[str, Any]]
    track_balance: dict[str, Any] = field(default_factory=dict)
    role_eq: dict[str, Any] = field(default_factory=dict)
    sidechain: dict[str, Any] = field(default_factory=dict)
    highpass: dict[str, Any] = field(default_factory=dict)
    mud_cut: dict[str, Any] = field(default_factory=dict)
    master: dict[str, Any] = field(default_factory=dict)
    compression: dict[str, Any] = field(default_factory=dict)
    fx_suggestions: list[str] = field(default_factory=list)
    space: dict[str, Any] = field(default_factory=dict)
    manual_gain: dict[str, float] = field(default_factory=dict)
    role_override: dict[str, str] = field(default_factory=dict)
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StyleProfile:
        return cls(
            name=data["name"],
            label=data.get("label", data["name"]),
            target_lufs=float(data["target_lufs"]),
            target_lra=float(data.get("target_lra", 6.0)),
            tempo_range=[float(x) for x in data.get("tempo_range", [0, 300])],
            stereo_width=data.get("stereo_width", "moderate"),
            frequency_balance=data.get("frequency_balance", []),
            track_balance=data.get("track_balance", {}),
            role_eq=data.get("role_eq", {}),
            sidechain=data.get("sidechain", {}),
            highpass=data.get("highpass", {}),
            mud_cut=data.get("mud_cut", {}),
            master=data.get("master", {}),
            compression=data.get("compression", {}),
            fx_suggestions=data.get("fx_suggestions", []),
            space=data.get("space", {}),
            manual_gain=data.get("manual_gain", {}),
            role_override=data.get("role_override", {}),
            description=data.get("description", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "target_lufs": self.target_lufs,
            "target_lra": self.target_lra,
            "tempo_range": self.tempo_range,
            "stereo_width": self.stereo_width,
            "frequency_balance": self.frequency_balance,
            "track_balance": self.track_balance,
            "role_eq": self.role_eq,
            "sidechain": self.sidechain,
            "highpass": self.highpass,
            "mud_cut": self.mud_cut,
            "master": self.master,
            "compression": self.compression,
            "fx_suggestions": self.fx_suggestions,
            "space": self.space,
            "manual_gain": self.manual_gain,
            "role_override": self.role_override,
            "description": self.description,
        }


def _styles_dir() -> str:
    env = os.environ.get("ABLELON_AUTO_MIX_STYLES_DIR")
    if env:
        return env
    if os.path.isdir(PACKAGE_STYLES_DIR):
        return PACKAGE_STYLES_DIR
    # Installed without package data (e.g. running from a raw checkout):
    # fall back to a styles/ folder next to the project.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(here, "styles")
    return candidate if os.path.isdir(candidate) else "."


def list_profiles() -> list[StyleProfile]:
    profiles = []
    for fname in sorted(os.listdir(_styles_dir())):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(_styles_dir(), fname), encoding="utf-8") as fh:
                    profiles.append(StyleProfile.from_dict(json.load(fh)))
            except (json.JSONDecodeError, KeyError) as exc:
                raise RuntimeError(f"Bad style profile {fname}: {exc}") from exc
    return profiles


def get_profile(name: str) -> StyleProfile:
    for profile in list_profiles():
        if profile.name == name:
            return profile
    raise KeyError(
        f"Unknown style '{name}'. Available: {', '.join(p.name for p in list_profiles())}"
    )


load_profile = get_profile
