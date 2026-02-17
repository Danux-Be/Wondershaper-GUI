from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.config import CONFIG_VERSION, ConfigStore, migrate_config


class ConfigTests(unittest.TestCase):
    def test_migrate_old_config_adds_v2_fields(self) -> None:
        old = {
            "iface": "eth0",
            "enabled": True,
            "presets": [{"name": "Work", "down_mbps": 20, "up_mbps": 5}],
        }
        migrated = migrate_config(old)
        self.assertEqual(migrated["config_version"], CONFIG_VERSION)
        self.assertIn("wifi_preset_mappings", migrated)
        self.assertIsInstance(migrated["wifi_preset_mappings"], dict)
        self.assertTrue(migrated["iface_auto"])

    def test_import_config_merges_and_backups(self) -> None:
        with self.subTest("import"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                config_path = tmp_path / "config.json"
                store = ConfigStore(config_path)
                current = store.default_config()
                store.save(current)

                payload = {
                    "config_version": 2,
                    "presets": [{"name": "Office", "down_mbps": 50, "up_mbps": 10}],
                    "language": "fr",
                    "iface_auto": False,
                    "iface": "wlan0",
                    "active_preset": "Office",
                    "wifi_preset_mappings": {"OfficeWiFi": "Office"},
                }
                import_file = tmp_path / "import.json"
                import_file.write_text(json.dumps(payload), encoding="utf-8")

                merged, backup = store.import_config(import_file, current)

                self.assertEqual(merged["language"], "fr")
                self.assertEqual(merged["iface"], "wlan0")
                self.assertFalse(merged["iface_auto"])
                self.assertEqual(merged["active_preset"], "Office")
                self.assertEqual(merged["wifi_preset_mappings"]["OfficeWiFi"], "Office")
                self.assertTrue(backup.exists())

    def test_import_invalid_schema_raises(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "config.json"
            store = ConfigStore(config_path)
            current = store.default_config()
            store.save(current)

            import_file = tmp_path / "broken.json"
            import_file.write_text(json.dumps({"presets": "oops"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                store.import_config(import_file, current)


if __name__ == "__main__":
    unittest.main()
