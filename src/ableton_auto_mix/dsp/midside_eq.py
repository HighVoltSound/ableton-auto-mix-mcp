"""Mid/Side EQ: apply separate EQ curves to the mid (center) and side
(stereo) components of a signal.

This is essential for mastering: you can tighten the low end in mono while
widening the highs in stereo, or fix a harsh center without affecting the
stereo image.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class EqNode:
    """One EQ node (same format as the existing planner/preview EQ)."""

    hz: float = 1000.0
    gain_db: float = 0.0
    q: float = 1.0
    type: str = "peaking"  # "peaking", "low_shelf", "high_shelf"
    enabled: bool = True


@dataclass
class MidSideEqConfig:
    """Separate EQ for mid and side channels."""

    mid_nodes: list[EqNode] = field(default_factory=list)
    side_nodes: list[EqNode] = field(default_factory=list)
    enabled: bool = True
    mix: float = 1.0


from .biquad import (
    apply_biquad_sos,
)
from .biquad import (
    high_shelf_biquad as _high_shelf_biquad,
)
from .biquad import (
    low_shelf_biquad as _low_shelf_biquad,
)
from .biquad import (
    peaking_biquad as _peaking_biquad,
)


def _apply_eq_chain(audio: np.ndarray, sr: int, nodes: list[EqNode]) -> np.ndarray:
    """Apply a chain of EQ nodes to a signal."""
    for node in nodes:
        if not node.enabled or abs(node.gain_db) < 0.1:
            continue
        f0 = max(float(node.hz), 20.0)
        q = max(float(node.q), 0.1)
        if node.type == "low_shelf":
            b, a = _low_shelf_biquad(sr, f0, node.gain_db, q)
        elif node.type == "high_shelf":
            b, a = _high_shelf_biquad(sr, f0, node.gain_db, q)
        else:
            b, a = _peaking_biquad(sr, f0, node.gain_db, q)
        audio = apply_biquad_sos(audio, b, a)
    return audio


def _stereo_to_midside(audio: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert L/R stereo to Mid/Side."""
    mid = (audio[:, 0] + audio[:, 1]) * 0.5
    side = (audio[:, 0] - audio[:, 1]) * 0.5
    return mid, side


def _midside_to_stereo(mid: np.ndarray, side: np.ndarray) -> np.ndarray:
    """Convert Mid/Side back to L/R stereo."""
    left = mid + side
    right = mid - side
    return np.stack([left, right], axis=1)


def apply_midside_eq(audio: np.ndarray, sr: int, config: MidSideEqConfig) -> np.ndarray:
    """Apply separate EQ to the mid and side channels of a stereo signal.

    workflow:
    1. Split stereo → mid + side
    2. Apply mid_nodes EQ to mid
    3. Apply side_nodes EQ to side
    4. Recombine → stereo
    5. Mix dry/wet
    """
    if not config.enabled or audio.ndim < 2:
        return audio

    has_mid = any(n.enabled and abs(n.gain_db) > 0.1 for n in config.mid_nodes)
    has_side = any(n.enabled and abs(n.gain_db) > 0.1 for n in config.side_nodes)

    if not has_mid and not has_side:
        return audio

    mid, side = _stereo_to_midside(audio)
    mid_2d = np.stack([mid, mid], axis=1)
    side_2d = np.stack([side, side], axis=1)

    if has_mid:
        mid_2d = _apply_eq_chain(mid_2d, sr, config.mid_nodes)
    if has_side:
        side_2d = _apply_eq_chain(side_2d, sr, config.side_nodes)

    wet = _midside_to_stereo(mid_2d[:, 0], side_2d[:, 0])

    if config.mix >= 1.0:
        return wet
    return (1.0 - config.mix) * audio + config.mix * wet


def config_from_dict(d: dict) -> MidSideEqConfig:
    """Build a MidSideEqConfig from an API-style dict."""

    def _parse_nodes(key: str) -> list[EqNode]:
        nodes = []
        for n in d.get(key, []):
            nodes.append(
                EqNode(
                    hz=float(n.get("hz", 1000)),
                    gain_db=float(n.get("gain_db", 0)),
                    q=float(n.get("q", 1)),
                    type=str(n.get("type", "peaking")),
                    enabled=bool(n.get("enabled", True)),
                )
            )
        return nodes

    return MidSideEqConfig(
        mid_nodes=_parse_nodes("mid_nodes"),
        side_nodes=_parse_nodes("side_nodes"),
        enabled=bool(d.get("enabled", True)),
        mix=float(d.get("mix", 1.0)),
    )
