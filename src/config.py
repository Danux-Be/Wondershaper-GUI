from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_PRESETS = [
    {"name": "Work", "down_mbps": 50, "up_mbps": 10},
    {"name": "Gaming", "down_mbps": 30, "up_mbps": 15},
    {"name": "Streaming", "down_mbps": 80, "up_mbps": 20},
]
CONFIG_VERSION = 2


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.default_config()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return migrate_config(data)

    def save(self, config: Dict[str, Any]) -> None:
        config["config_version"] = CONFIG_VERSION
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)

    def backup(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = self.path.with_name(f"{self.path.name}.bak-{stamp}")
        if self.path.exists():
            backup_path.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")
        return backup_path

    def export_config(self, export_path: Path, config: Dict[str, Any]) -> None:
        payload = {
            "config_version": CONFIG_VERSION,
            "presets": config.get("presets", []),
            "language": config.get("language", "en"),
            "iface": config.get("iface", ""),
            "iface_auto": bool(config.get("iface_auto", True)),
            "active_preset": config.get("active_preset", "Work"),
            "wifi_preset_mappings": normalize_wifi_mappings(config.get("wifi_preset_mappings", {})),
        }
        export_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def import_config(self, import_path: Path, current_config: Dict[str, Any]) -> Tuple[Dict[str, Any], Path]:
        imported = json.loads(import_path.read_text(encoding="utf-8"))
        if not isinstance(imported, dict):
            raise ValueError("invalid_import")

        merged = migrate_config(current_config)
        backup_path = self.backup()

        if "language" in imported and isinstance(imported["language"], str):
            merged["language"] = imported["language"]
        if "iface" in imported and isinstance(imported["iface"], str):
            merged["iface"] = imported["iface"]
        if "iface_auto" in imported:
            merged["iface_auto"] = bool(imported["iface_auto"])
        if "active_preset" in imported and isinstance(imported["active_preset"], str):
            merged["active_preset"] = imported["active_preset"]

        if "presets" in imported:
            if not isinstance(imported["presets"], list):
                raise ValueError("invalid_import")
            merged["presets"] = [validate_preset(item) for item in imported["presets"] if isinstance(item, dict)]
            if not merged["presets"]:
                merged["presets"] = [preset.copy() for preset in DEFAULT_PRESETS]

        if "wifi_preset_mappings" in imported:
            merged["wifi_preset_mappings"] = normalize_wifi_mappings(imported["wifi_preset_mappings"])

        merged["config_version"] = CONFIG_VERSION
        return merged, backup_path

    def default_config(self) -> Dict[str, Any]:
        return {
            "config_version": CONFIG_VERSION,
            "iface": "",
            "iface_auto": True,
            "enabled": False,
            "active_preset": "Work",
            "language": "en",
            "start_on_login": False,
            "custom": {"down_mbps": 20, "up_mbps": 5},
            "wifi_preset_mappings": {},
            "presets": [preset.copy() for preset in DEFAULT_PRESETS],
        }


def migrate_config(data: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "config_version": CONFIG_VERSION,
        "iface": "",
        "iface_auto": True,
        "enabled": False,
        "active_preset": "Work",
        "language": "en",
        "start_on_login": False,
        "custom": {"down_mbps": 20, "up_mbps": 5},
        "wifi_preset_mappings": {},
        "presets": [preset.copy() for preset in DEFAULT_PRESETS],
    }
    if not isinstance(data, dict):
        return base

    merged = base.copy()
    merged.update(data)
    if not merged.get("presets"):
        merged["presets"] = [preset.copy() for preset in DEFAULT_PRESETS]
    merged["wifi_preset_mappings"] = normalize_wifi_mappings(merged.get("wifi_preset_mappings", {}))
    merged["config_version"] = CONFIG_VERSION
    return merged


def normalize_wifi_mappings(mappings: Any) -> Dict[str, str]:
    if not isinstance(mappings, dict):
        return {}
    normalized: Dict[str, str] = {}
    for ssid, preset in mappings.items():
        ssid_key = str(ssid).strip()
        preset_name = str(preset).strip()
        if ssid_key and preset_name:
            normalized[ssid_key] = preset_name
    return normalized


def validate_preset(preset: Dict[str, Any]) -> Dict[str, Any]:
    name = str(preset.get("name", "")).strip()
    if not name:
        raise ValueError("invalid_preset_name")
    down = int(float(preset.get("down_mbps", 0)))
    up = int(float(preset.get("up_mbps", 0)))
    return {"name": name, "down_mbps": clamp_mbps(down), "up_mbps": clamp_mbps(up)}


def clamp_mbps(value: int, min_mbps: int = 1, max_mbps: int = 10000) -> int:
    if value < min_mbps or value > max_mbps:
        raise ValueError("invalid_mbps")
    return value


def preset_names(presets: List[Dict[str, Any]]) -> List[str]:
    return [str(item.get("name", "")) for item in presets if item.get("name")]
