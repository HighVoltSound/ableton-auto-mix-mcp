"""Command-line interface: use the auto-mix engine WITHOUT an MCP client.

Mirrors every MCP tool so the same functionality is available from a shell.

Examples:
    ableton-auto-mix-mcp styles
    ableton-auto-mix-mcp style breaks
    ableton-auto-mix-mcp analyze renders/
    ableton-auto-mix-mcp suggest renders/
    ableton-auto-mix-mcp mix breaks renders/
    ableton-auto-mix-mcp preview breaks renders/ --max-duration 30
    ableton-auto-mix-mcp conflicts renders/
    ableton-auto-mix-mcp release breaks renders/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import analyzer, mixer, preview, profiles, qa

DEFAULT_RENDER_DIR = os.environ.get(
    "ABLETON_RENDER_DIR", os.environ.get("ABLELON_RENDER_DIR", "renders")
)


def _p(data: dict[str, Any] | list[Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------
# command implementations
# --------------------------------------------------------------------------
def cmd_styles(_args: argparse.Namespace) -> None:
    _p([
        {
            "name": p.name,
            "label": p.label,
            "target_lufs": p.target_lufs,
            "target_lra": p.target_lra,
            "stereo_width": p.stereo_width,
            "description": p.description,
        }
        for p in profiles.list_profiles()
    ])


def cmd_style(args: argparse.Namespace) -> None:
    _p(profiles.get_profile(args.style).to_dict())


def cmd_analyze(args: argparse.Namespace) -> None:
    results = analyzer.analyze_directory(args.render_dir, args.pattern)
    if not results:
        sys.exit(f"No {args.pattern} files found in {args.render_dir}")
    _p([
        {
            "name": r.name,
            "path": r.path,
            "rms_db": round(r.rms_db, 1),
            "peak_db": round(r.peak_db, 1),
            "true_peak_dbtp": round(r.true_peak_dbtp, 1),
            "lufs": round(r.lufs, 1),
            "lra": round(r.lra, 1),
            "stereo_width": round(r.stereo_width, 3),
            "band_energy_db": {k: round(v, 1) for k, v in r.bandwidth_db.items()},
        }
        for r in results
    ])


def cmd_suggest(args: argparse.Namespace) -> None:
    results = analyzer.analyze_directory(args.render_dir, args.pattern)
    if not results:
        sys.exit(f"No {args.pattern} files found in {args.render_dir}")
    _p(mixer.suggest_style(results))


def cmd_mix(args: argparse.Namespace) -> None:
    results = analyzer.analyze_directory(args.render_dir, args.pattern)
    if not results:
        sys.exit(f"No {args.pattern} files found in {args.render_dir}")
    profile = profiles.get_profile(args.style)
    mix = mixer.compute_mix(results, profile, [a.name for a in results])
    _p(mix.to_dict())


def cmd_preview(args: argparse.Namespace) -> None:
    profile = profiles.get_profile(args.style)
    manual_gain: dict[str, float] = {}
    if args.manual_gain:
        for pair in args.manual_gain.split(","):
            name, _, db = pair.strip().partition("=")
            manual_gain[name.strip()] = float(db)
    _p(preview.render_preview_mix(
        args.render_dir,
        profile,
        pattern=args.pattern,
        output_path=args.output,
        max_duration=args.max_duration,
        manual_gain=manual_gain or None,
        sidechain_db=args.sidechain_db,
    ))


def cmd_conflicts(args: argparse.Namespace) -> None:
    results = analyzer.analyze_directory(args.render_dir, args.pattern)
    if not results:
        sys.exit(f"No {args.pattern} files found in {args.render_dir}")
    conflicts = qa.analyze_conflicts(results)
    _p({
        "tracks_analyzed": [a.name for a in results],
        "conflicts_found": len(conflicts),
        "conflicts": conflicts,
    })


def cmd_release(args: argparse.Namespace) -> None:
    if args.output:
        profile = profiles.get_profile(args.style) if args.style else None
        target = profile.target_lufs if profile else args.target_lufs
        style_name = profile.name if profile else os.path.basename(args.output)
        _p(qa.release_check(args.output, style_name, target))
        return
    if not args.style:
        sys.exit("provide --style (to render a preview) or --output (an existing WAV)")
    profile = profiles.get_profile(args.style)
    result = preview.render_preview_mix(args.render_dir, profile, pattern=args.pattern)
    _p(qa.release_check(result["output_path"], profile.name, profile.target_lufs))


# --------------------------------------------------------------------------
# argument parser
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ableton-auto-mix-mcp",
        description="AI-driven auto-mixing and mastering for Ableton Live (offline).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("styles", help="list style profiles")

    p = sub.add_parser("style", help="show one style profile")
    p.add_argument("style")

    p = sub.add_parser("analyze", help="analyze rendered WAVs")
    _add_render_args(p)

    p = sub.add_parser("suggest", help="suggest the best style for the material")
    _add_render_args(p)

    p = sub.add_parser("mix", help="compute mix corrections (dry-run report)")
    p.add_argument("style")
    _add_render_args(p)

    p = sub.add_parser("preview", help="render a mastered preview mix WAV")
    p.add_argument("style")
    _add_render_args(p)
    p.add_argument("--output", help="output WAV path (default <render_dir>/preview_<style>.wav)")
    p.add_argument("--max-duration", type=float, help="cap preview length in seconds")
    p.add_argument("--manual-gain", help='per-file gain in dB, comma list, e.g. "snt2=-4.0,bass=2.0"')
    p.add_argument("--sidechain-db", type=float, help="flat snare sidechain ducking in dB (e.g. -4.0)")

    p = sub.add_parser("conflicts", help="report tracks fighting for the same band")
    _add_render_args(p)

    p = sub.add_parser("release", help="release-quality check (render preview if --output omitted)")
    p.add_argument("style", nargs="?")
    _add_render_args(p)
    p.add_argument("--output", help="check an existing WAV instead of rendering")
    p.add_argument("--target-lufs", type=float, default=-8.0,
                   help="target LUFS used when checking an existing file without --style")

    return parser


def _add_render_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("render_dir", nargs="?", default=DEFAULT_RENDER_DIR,
                   help=f"folder with one WAV per track (default: {DEFAULT_RENDER_DIR})")
    p.add_argument("--pattern", default="*.wav", help="glob for audio files")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    commands = {
        "styles": cmd_styles,
        "style": cmd_style,
        "analyze": cmd_analyze,
        "suggest": cmd_suggest,
        "mix": cmd_mix,
        "preview": cmd_preview,
        "conflicts": cmd_conflicts,
        "release": cmd_release,
    }
    try:
        commands[args.command](args)
    except (ValueError, KeyError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
