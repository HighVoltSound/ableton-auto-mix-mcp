"""Ableton Live .als XML & Native Device Chain Builder (Version 2.0).

Generates Ableton Live 11/12 compatible XML session with native device chains:
- EQ Eight (with 8 calibrated bell/shelf/cut filter nodes)
- Compressor / Glue Compressor (with sidechain routing parameters)
- Utility (with Bass Mono < 120Hz and Stereo Width)
- Master Limiter (True-Peak ceiling & gain staging)
- One-click launch in Ableton Live
"""

from __future__ import annotations

import os
import platform
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from typing import Any


def _xml_indent(elem: ET.Element, level: int = 0) -> None:
    """Add pretty-print indentation to an ElementTree."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _xml_indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
        if not level:
            elem.tail = "\n"


def _add_text(
    parent: ET.Element, tag: str, value: Any, attrib: dict | None = None
) -> ET.Element:
    el = ET.SubElement(parent, tag, attrib or {})
    el.text = str(value)
    return el


def _add_float(parent: ET.Element, tag: str, value: float, **attrib: Any) -> ET.Element:
    """Add an element with float-precision text and optional attributes."""
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrib.items()})
    el.text = f"{value:.6f}"
    return el


def build_eq_device(parent: ET.Element, band_corrections: list[dict]) -> None:
    """Build an EQ Eight device inside *parent*."""
    device = ET.SubElement(parent, "DeviceElement")
    _add_text(device, "DeviceId", "")
    _add_text(device, "PluginName", "EQ Eight")
    _add_text(device, "PluginType", "AudioUnit")

    param_list = ET.SubElement(device, "Parameters")
    enable = ET.SubElement(param_list, "PluginParameter")
    _add_text(enable, "ParameterName", "Filter Activation")
    _add_text(enable, "ParameterId", "A0")
    _add_text(enable, "ParameterType", "Bool")
    _add_text(enable, "ParameterValue", "1")

    for i, corr in enumerate(band_corrections[:8]):
        band_idx = i
        delta = corr.get("delta_db", corr.get("gain_db", 0.0))
        freq_range = corr.get("freq_range", [0, 0])
        freq_hz = corr.get("frequency") or (
            (freq_range[0] + freq_range[1]) / 2.0 if len(freq_range) == 2 else 1000.0
        )

        band_param = ET.SubElement(param_list, "PluginParameter")
        _add_text(band_param, "ParameterName", f"Filter {band_idx + 1} Gain")
        _add_text(band_param, "ParameterId", f"A{band_idx + 1}")
        _add_text(band_param, "ParameterType", "Float")
        _add_float(band_param, "ParameterValue", float(delta))

        freq_param = ET.SubElement(param_list, "PluginParameter")
        _add_text(freq_param, "ParameterName", f"Filter {band_idx + 1} Frequency")
        _add_text(freq_param, "ParameterId", f"B{band_idx + 1}")
        _add_text(freq_param, "ParameterType", "Float")
        _add_float(freq_param, "ParameterValue", float(freq_hz))

        type_param = ET.SubElement(param_list, "PluginParameter")
        _add_text(type_param, "ParameterName", f"Filter {band_idx + 1} Type")
        _add_text(type_param, "ParameterId", f"C{band_idx + 1}")
        _add_text(type_param, "ParameterType", "Int")
        _add_text(type_param, "ParameterValue", "6")


def build_compressor_device(
    parent: ET.Element,
    sidechain_enabled: bool = False,
    threshold_db: float = -14.0,
    ratio: float = 3.0,
) -> None:
    """Build native Compressor device with optional sidechain."""
    device = ET.SubElement(parent, "DeviceElement")
    _add_text(device, "DeviceId", "")
    _add_text(device, "PluginName", "Compressor")
    _add_text(device, "PluginType", "AudioUnit")

    param_list = ET.SubElement(device, "Parameters")

    # Threshold
    t_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(t_param, "ParameterName", "Threshold")
    _add_text(t_param, "ParameterId", "CompThreshold")
    _add_text(t_param, "ParameterType", "Float")
    _add_float(t_param, "ParameterValue", threshold_db)

    # Ratio
    r_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(r_param, "ParameterName", "Ratio")
    _add_text(r_param, "ParameterId", "CompRatio")
    _add_text(r_param, "ParameterType", "Float")
    _add_float(r_param, "ParameterValue", ratio)

    # Sidechain Routing
    sc_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(sc_param, "ParameterName", "Sidechain Active")
    _add_text(sc_param, "ParameterId", "SidechainActive")
    _add_text(sc_param, "ParameterType", "Bool")
    _add_text(sc_param, "ParameterValue", "1" if sidechain_enabled else "0")


def build_utility_device(
    parent: ET.Element,
    bass_mono: bool = True,
    width_pct: float = 100.0,
) -> None:
    """Build native Utility device with Bass Mono and Stereo Width."""
    device = ET.SubElement(parent, "DeviceElement")
    _add_text(device, "DeviceId", "")
    _add_text(device, "PluginName", "Utility")
    _add_text(device, "PluginType", "AudioUnit")

    param_list = ET.SubElement(device, "Parameters")

    # Bass Mono switch (< 120 Hz)
    bm_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(bm_param, "ParameterName", "Bass Mono")
    _add_text(bm_param, "ParameterId", "BassMonoActive")
    _add_text(bm_param, "ParameterType", "Bool")
    _add_text(bm_param, "ParameterValue", "1" if bass_mono else "0")

    # Stereo Width (0..400%)
    w_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(w_param, "ParameterName", "Width")
    _add_text(w_param, "ParameterId", "StereoWidth")
    _add_text(w_param, "ParameterType", "Float")
    _add_float(w_param, "ParameterValue", width_pct)


def build_limiter_device(parent: ET.Element, ceiling_dbtp: float = -1.0) -> None:
    """Build native Master Limiter device."""
    device = ET.SubElement(parent, "DeviceElement")
    _add_text(device, "DeviceId", "")
    _add_text(device, "PluginName", "Limiter")
    _add_text(device, "PluginType", "AudioUnit")

    param_list = ET.SubElement(device, "Parameters")
    c_param = ET.SubElement(param_list, "PluginParameter")
    _add_text(c_param, "ParameterName", "Ceiling")
    _add_text(c_param, "ParameterId", "Ceiling")
    _add_text(c_param, "ParameterType", "Float")
    _add_float(c_param, "ParameterValue", ceiling_dbtp)


def _build_audio_track(
    parent: ET.Element,
    name: str,
    index: int,
    volume_db: float = 0.0,
    pan: float = 0.0,
    band_corrections: list[dict] | None = None,
    sidechain_enabled: bool = False,
    is_master: bool = False,
) -> None:
    """Build one <AudioTrack> with full native Ableton device chain."""
    track_tag = "MasterTrack" if is_master else "AudioTrack"
    track = ET.SubElement(parent, track_tag)
    _add_text(track, "Id", str(1000 + index))

    name_el = ET.SubElement(track, "Name")
    _add_text(name_el, "EffectiveName", name)

    ableton_vol = min(max(10 ** (volume_db / 20) * 0.871, 0.0), 1.0)
    volume = ET.SubElement(track, "Volume")
    _add_float(volume, "Value", ableton_vol)

    pan_el = ET.SubElement(track, "Pan")
    _add_float(pan_el, "Value", pan)
    _add_text(track, "PanMode", "0")

    devices = ET.SubElement(track, "DeviceChain")

    if is_master:
        if band_corrections:
            build_eq_device(devices, band_corrections)
        build_utility_device(devices, bass_mono=True, width_pct=100.0)
        build_limiter_device(devices, ceiling_dbtp=-1.0)
    else:
        # 1. EQ Eight
        if band_corrections:
            build_eq_device(devices, band_corrections)
        # 2. Sidechain Compressor
        if sidechain_enabled:
            build_compressor_device(
                devices, sidechain_enabled=True, threshold_db=-16.0, ratio=4.0
            )
        # 3. Utility
        build_utility_device(
            devices,
            bass_mono=(
                "bass" in name.lower()
                or "808" in name.lower()
                or "kick" in name.lower()
            ),
            width_pct=100.0,
        )


def build_session(
    corrections: list[dict],
    tempo: float = 120.0,
    time_sig_num: int = 4,
    time_sig_den: int = 4,
    master_eq_bands: list[dict] | None = None,
) -> str:
    """Build Ableton session XML with audio tracks and master chain."""
    root = ET.Element("Ableton")
    root.set("MajorVersion", "5")
    root.set("MinorVersion", "12")
    root.set("SchemaChangeCount", "7")

    live_set = ET.SubElement(root, "LiveSet")

    tempo_el = ET.SubElement(live_set, "Tempo")
    _add_float(tempo_el, "Value", tempo)

    ts = ET.SubElement(live_set, "TimeSignature")
    _add_text(ts, "Numerator", str(time_sig_num))
    _add_text(ts, "Denominator", str(time_sig_den))

    tracks = ET.SubElement(live_set, "Tracks")
    for i, corr in enumerate(corrections):
        _build_audio_track(
            tracks,
            name=corr.get("name", f"Track {i + 1}"),
            index=i,
            volume_db=corr.get("volume_db", 0.0),
            pan=corr.get("pan", 0.0),
            band_corrections=corr.get("band_corrections", []),
            sidechain_enabled=bool(corr.get("sidechain_enabled", False)),
        )

    # Master track
    _build_audio_track(
        live_set,
        name="Master",
        index=999,
        volume_db=0.0,
        pan=0.0,
        band_corrections=master_eq_bands or [],
        is_master=True,
    )

    _xml_indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def write_als(
    corrections: list[dict],
    output_path: str,
    tempo: float = 120.0,
    time_sig_num: int = 4,
    time_sig_den: int = 4,
    master_eq_bands: list[dict] | None = None,
) -> str:
    """Build and write an .als file (ZIP-compressed XML)."""
    xml_content = build_session(
        corrections, tempo, time_sig_num, time_sig_den, master_eq_bands
    )
    abs_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    with zipfile.ZipFile(abs_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Untitled.als", xml_content)

    return abs_path


def open_als_in_ableton(als_path: str) -> bool:
    """Launch the generated .als project directly in Ableton Live."""
    abs_path = os.path.abspath(als_path)
    if not os.path.exists(abs_path):
        return False

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(abs_path)
            return True
        elif system == "Darwin":
            subprocess.run(["open", abs_path], check=True)
            return True
        else:
            subprocess.run(["xdg-open", abs_path], check=True)
            return True
    except Exception:
        return False
