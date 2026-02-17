"""Tests for config module."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from config import ConfigStore, clamp_mbps, validate_preset


class TestConfigStore:
    def test_load_default_when_missing(self, tmp_path: Path) -> None:
        store = ConfigStore(tmp_path / "cfg" / "config.json")
        cfg = store.load()
        assert cfg["iface"] == ""
        assert cfg["enabled"] is False
        assert len(cfg["presets"]) == 3

    def test_load_corrupted_json_returns_default(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text("{bad json!!!", encoding="utf-8")
        store = ConfigStore(config_path)
        cfg = store.load()
        assert cfg["iface"] == ""
        assert len(cfg["presets"]) == 3

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        store = ConfigStore(config_path)
        cfg = store.default_config()
        cfg["iface"] = "eth0"
        store.save(cfg)
        loaded = store.load()
        assert loaded["iface"] == "eth0"

    def test_load_merges_with_defaults(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"iface": "wlan0"}), encoding="utf-8")
        store = ConfigStore(config_path)
        cfg = store.load()
        assert cfg["iface"] == "wlan0"
        assert "enabled" in cfg
        assert len(cfg["presets"]) == 3


class TestValidatePreset:
    def test_valid_preset(self) -> None:
        result = validate_preset({"name": "Test", "down_mbps": "50", "up_mbps": "10"})
        assert result["name"] == "Test"
        assert result["down_mbps"] == 50
        assert result["up_mbps"] == 10

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid_preset_name"):
            validate_preset({"name": "", "down_mbps": 50, "up_mbps": 10})

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid_mbps"):
            validate_preset({"name": "X", "down_mbps": 0, "up_mbps": 10})

    def test_too_high_raises(self) -> None:
        with pytest.raises(ValueError, match="invalid_mbps"):
            validate_preset({"name": "X", "down_mbps": 99999, "up_mbps": 10})


class TestClampMbps:
    def test_valid_value(self) -> None:
        assert clamp_mbps(100) == 100

    def test_below_min_raises(self) -> None:
        with pytest.raises(ValueError):
            clamp_mbps(0)

    def test_above_max_raises(self) -> None:
        with pytest.raises(ValueError):
            clamp_mbps(10001)
