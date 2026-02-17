"""Tests for i18n module."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from i18n import I18N


class TestI18N:
    def test_load_english(self, tmp_path: Path) -> None:
        en = {"language_name": "English", "hello": "Hello {name}"}
        (tmp_path / "en.json").write_text(json.dumps(en), encoding="utf-8")
        i = I18N(tmp_path)
        i.set_language("en")
        assert i.t("hello", name="World") == "Hello World"

    def test_fallback_to_key(self, tmp_path: Path) -> None:
        (tmp_path / "en.json").write_text("{}", encoding="utf-8")
        i = I18N(tmp_path)
        assert i.t("missing_key") == "missing_key"

    def test_available_languages(self, tmp_path: Path) -> None:
        (tmp_path / "en.json").write_text(json.dumps({"language_name": "English"}), encoding="utf-8")
        (tmp_path / "fr.json").write_text(json.dumps({"language_name": "Français"}), encoding="utf-8")
        i = I18N(tmp_path)
        langs = i.available_languages()
        assert "en" in langs
        assert "fr" in langs
        assert langs["fr"] == "Français"

    def test_set_unknown_language_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "en.json").write_text(json.dumps({"language_name": "English"}), encoding="utf-8")
        i = I18N(tmp_path)
        i.set_language("xx")
        assert i.language == "en"

    def test_detect_system_language_returns_string(self, tmp_path: Path) -> None:
        (tmp_path / "en.json").write_text("{}", encoding="utf-8")
        i = I18N(tmp_path)
        result = i.detect_system_language()
        assert isinstance(result, str)
