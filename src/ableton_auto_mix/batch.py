"""Batch processing: analyze and preview multiple directories in sequence.

Each directory is treated as an independent project (its own renders folder),
and the results are collected into a single batch report.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field

from .analyzer import analyze_directory
from .preview import render_preview_mix
from .profiles import load_profile


@dataclass
class BatchItem:
    directory: str
    style: str
    status: str = "pending"  # pending | processing | done | error
    error: str | None = None
    result: dict | None = None


@dataclass
class BatchResult:
    items: list[BatchItem] = field(default_factory=list)
    total: int = 0
    completed: int = 0
    failed: int = 0


def run_batch(
    directories: list[str],
    style: str,
    output_dir: str | None = None,
    max_duration: float | None = None,
    multiband_config: dict | None = None,
    limiter_ceiling_db: float | None = None,
    progress_callback: Callable[[str, int, str], None] | None = None,
) -> BatchResult:
    """Process multiple directories with the same style.

    Args:
        directories: list of render directories to process.
        style: style name (e.g. "techno", "hip_hop").
        output_dir: where to save previews. If None, each directory gets
                    its own preview.
        max_duration: optional cap on preview length.
        multiband_config: multiband compressor settings.
        limiter_ceiling_db: limiter ceiling.
        progress_callback: stage/percent/detail callback.

    Returns:
        BatchResult with per-directory results.
    """
    result = BatchResult(total=len(directories))

    for i, directory in enumerate(directories):
        item = BatchItem(directory=directory, style=style)

        if progress_callback:
            progress_callback(
                "batch",
                int(100 * i / len(directories)),
                f"Processing {i + 1}/{len(directories)}: {os.path.basename(directory)}",
            )

        try:
            # Validate directory exists and has WAVs
            if not os.path.isdir(directory):
                raise ValueError(f"Directory not found: {directory}")

            analyses = analyze_directory(directory)
            if not analyses:
                raise ValueError(f"No WAV files found in {directory}")

            # Load profile
            profile = load_profile(style)

            # Output path
            if output_dir:
                out = os.path.join(
                    output_dir, f"batch_{os.path.basename(directory)}.wav"
                )
            else:
                out = os.path.join(directory, f"preview_{profile.name}.wav")

            # Render
            item.status = "processing"
            item.result = render_preview_mix(
                directory,
                profile,
                output_path=out,
                max_duration=max_duration,
                multiband_config=multiband_config,
                limiter_ceiling_db=limiter_ceiling_db,
            )
            item.status = "done"
            result.completed += 1

        except Exception as exc:
            item.status = "error"
            item.error = str(exc)
            result.failed += 1

        result.items.append(item)

    if progress_callback:
        progress_callback(
            "batch", 100, f"Done: {result.completed} ok, {result.failed} failed"
        )

    return result
