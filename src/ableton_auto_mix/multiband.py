"""Multiband compressor: split the signal into frequency bands, compress each
independently, and sum back.  Used in the mastering chain for transparent
loudness control without the pumping artifacts of a single-band compressor.

The crossover filters are 4th-order Linkwitz-Riley (flat sum, −24 dB/oct rolloff)
so the bands sum back to unity when no compression is applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, sosfiltfilt

# Re-use the preview helper functions (kept local to avoid circular imports).
from .dsp._utils import compressor


@dataclass
class BandConfig:
    """Configuration for one frequency band."""

    freq_lo: float = 0.0  # Hz (0 = no low cut)
    freq_hi: float = 20000.0  # Hz (20000 = no high cut)
    threshold_db: float = -14.0
    ratio: float = 2.0
    attack_ms: float = 10.0
    release_ms: float = 120.0
    makeup_db: float = 0.0
    enabled: bool = True


@dataclass
class MultibandConfig:
    """Full multiband compressor configuration."""

    bands: list[BandConfig] = field(
        default_factory=lambda: [
            BandConfig(freq_lo=0, freq_hi=120, threshold_db=-16, ratio=2.5, makeup_db=1.0),  # sub
            BandConfig(freq_lo=120, freq_hi=2500, threshold_db=-14, ratio=2.0, makeup_db=0.0),  # low-mid
            BandConfig(freq_lo=2500, freq_hi=8000, threshold_db=-12, ratio=1.8, makeup_db=0.0),  # mid
            BandConfig(freq_lo=8000, freq_hi=20000, threshold_db=-14, ratio=2.0, makeup_db=0.5),  # air
        ]
    )
    enabled: bool = True
    mix: float = 1.0  # dry/wet: 1.0 = full multiband, 0.0 = bypass


def _crossover_lr4(audio: np.ndarray, sr: int, freq: float, highpass: bool) -> np.ndarray:
    """4th-order Linkwitz-Riley crossover filter.

    Two cascaded Butterworth 2nd-order sections give a −24 dB/oct rolloff
    with a flat magnitude response at the crossover frequency when the
    highpass and lowpass outputs are summed.
    """
    freq = float(np.clip(freq, 1.0, sr * 0.49))
    sos = butter(2, freq, btype="highpass" if highpass else "lowpass", fs=sr, output="sos")
    return sosfiltfilt(sos, audio, axis=0)


def _split_bands(audio: np.ndarray, sr: int, band_edges: list[float]) -> list[np.ndarray]:
    """Split a stereo signal into N bands using Linkwitz-Riley crossovers.

    band_edges: sorted list of crossover frequencies. For 4 bands with
    edges [120, 2500, 8000] the bands are: 0–120, 120–2500, 2500–8000, 8000+.
    """
    bands: list[np.ndarray] = []
    # Start from the full signal and progressively subtract bands.
    remaining = audio.copy()

    for edge in band_edges:
        band = remaining - _crossover_lr4(remaining, sr, edge, highpass=True)
        bands.append(band)
        remaining = remaining - band

    # Whatever is left is the top band.
    bands.append(remaining)
    return bands


def apply_multiband(
    audio: np.ndarray,
    sr: int,
    config: MultibandConfig,
) -> np.ndarray:
    """Apply multiband compression to a stereo signal.

    Splits into bands, compresses each independently, and sums back.
    When config.enabled is False or mix is 0, returns audio unchanged.
    """
    if not config.enabled or config.mix <= 0.0:
        return audio

    active_bands = [b for b in config.bands if b.enabled]
    if len(active_bands) < 2:
        # Not enough bands for multiband — fall back to single-band.
        if active_bands:
            b = active_bands[0]
            return compressor(
                audio,
                sr,
                threshold_db=b.threshold_db,
                ratio=b.ratio,
                attack_ms=b.attack_ms,
                release_ms=b.release_ms,
                makeup_db=b.makeup_db,
            )
        return audio

    # Build crossover edges from the band definitions.
    # Each band has freq_lo/hi; we derive unique sorted edges.
    edges = sorted(
        set(b.freq_lo for b in active_bands if b.freq_lo > 0)
        | set(b.freq_hi for b in active_bands if b.freq_hi < 20000)
    )

    # Split into bands.
    split = _split_bands(audio, sr, edges)

    # Map each split band to its config and compress.
    compressed: list[np.ndarray] = []
    for i, band_audio in enumerate(split):
        # Find the matching config: band i covers the i-th frequency range.
        if i < len(active_bands):
            cfg = active_bands[i]
            if cfg.enabled:
                band_audio = compressor(
                    band_audio,
                    sr,
                    threshold_db=cfg.threshold_db,
                    ratio=cfg.ratio,
                    attack_ms=cfg.attack_ms,
                    release_ms=cfg.release_ms,
                    makeup_db=cfg.makeup_db,
                )
        compressed.append(band_audio)

    # Sum all bands back.
    wet = sum(compressed)

    # Dry/wet mix.
    if config.mix >= 1.0:
        return wet
    return (1.0 - config.mix) * audio + config.mix * wet


def config_from_dict(d: dict) -> MultibandConfig:
    """Build a MultibandConfig from an API-style dict."""
    bands = []
    for b in d.get("bands", []):
        bands.append(
            BandConfig(
                freq_lo=float(b.get("freq_lo", 0)),
                freq_hi=float(b.get("freq_hi", 20000)),
                threshold_db=float(b.get("threshold_db", -14)),
                ratio=float(b.get("ratio", 2)),
                attack_ms=float(b.get("attack_ms", 10)),
                release_ms=float(b.get("release_ms", 120)),
                makeup_db=float(b.get("makeup_db", 0)),
                enabled=bool(b.get("enabled", True)),
            )
        )
    if bands:
        return MultibandConfig(
            bands=bands,
            enabled=bool(d.get("enabled", True)),
            mix=float(d.get("mix", 1.0)),
        )
    return MultibandConfig(
        enabled=bool(d.get("enabled", True)),
        mix=float(d.get("mix", 1.0)),
    )
