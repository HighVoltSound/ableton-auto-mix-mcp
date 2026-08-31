"""A/B style comparison: render the same tracks with two different style
profiles and return both previews for quick comparison.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .preview import render_preview_mix
from .profiles import StyleProfile, load_profile


@dataclass
class ABResult:
    style_a: str
    style_b: str
    output_a: str
    output_b: str
    result_a: dict[str, Any]
    result_b: dict[str, Any]


def render_ab_compare(
    render_dir: str,
    style_a: str | StyleProfile,
    style_b: str | StyleProfile,
    output_dir: str | None = None,
    pattern: str = "*.wav",
    max_duration: float | None = None,
    multiband_config: dict | None = None,
    limiter_ceiling_db: float | None = None,
    dynamic_eq_config: dict | None = None,
    midside_eq_config: dict | None = None,
    transient_config: dict | None = None,
) -> ABResult:
    """Render the same tracks with two different styles.

    Args:
        render_dir: folder with WAVs
        style_a: first style name or profile
        style_b: second style name or profile
        output_dir: where to save. If None, each preview goes next to its WAVs.
        pattern: file glob
        max_duration: cap preview length
        multiband_config: shared multiband settings
        limiter_ceiling_db: shared limiter ceiling
        dynamic_eq_config: shared dynamic EQ
        midside_eq_config: shared mid/side EQ
        transient_config: shared transient shaper

    Returns:
        ABResult with paths to both previews
    """
    # Resolve profiles
    if isinstance(style_a, str):
        profile_a = load_profile(style_a)
    else:
        profile_a = style_a
    if isinstance(style_b, str):
        profile_b = load_profile(style_b)
    else:
        profile_b = style_b

    # Output paths
    if output_dir is None:
        output_dir = render_dir

    out_a = os.path.join(output_dir, f"preview_A_{profile_a.name}.wav")
    out_b = os.path.join(output_dir, f"preview_B_{profile_b.name}.wav")

    # Render style A
    result_a = render_preview_mix(
        render_dir,
        profile_a,
        pattern=pattern,
        output_path=out_a,
        max_duration=max_duration,
        multiband_config=multiband_config,
        limiter_ceiling_db=limiter_ceiling_db,
        dynamic_eq_config=dynamic_eq_config,
        midside_eq_config=midside_eq_config,
        transient_config=transient_config,
    )

    # Render style B
    result_b = render_preview_mix(
        render_dir,
        profile_b,
        pattern=pattern,
        output_path=out_b,
        max_duration=max_duration,
        multiband_config=multiband_config,
        limiter_ceiling_db=limiter_ceiling_db,
        dynamic_eq_config=dynamic_eq_config,
        midside_eq_config=midside_eq_config,
        transient_config=transient_config,
    )

    return ABResult(
        style_a=profile_a.name,
        style_b=profile_b.name,
        output_a=out_a,
        output_b=out_b,
        result_a=result_a,
        result_b=result_b,
    )
