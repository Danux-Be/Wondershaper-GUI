from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_PRESETS = [
    {"name": "Work", "down_mbps": 50, "up_mbps": 10},
    {"name": "Gaming", "down_mbps": 30, "up_mbps": 15},
    {"name": "Streaming", "down_mbps": 80, "up_mbps": 20},
]


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return self.default_config()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged = self.default_config()
        merged.update(data)
        if not merged.get("presets"):
            merged["presets"] = DEFAULT_PRESETS.copy()
        return merged

    def save(self, config: Dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)

    def default_config(self) -> Dict[str, Any]:
        return {
            "iface": "",
            "enabled": False,
            "active_preset": "Work",
            "language": "en",
            "start_on_login": False,
            "custom": {"down_mbps": 20, "up_mbps": 5},
            "presets": [preset.copy() for preset in DEFAULT_PRESETS],
        }


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
