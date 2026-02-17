from __future__ import annotations

import json
import locale
from pathlib import Path
from typing import Dict


class I18N:
    def __init__(self, locale_dir: Path, default_language: str = "en") -> None:
        self.locale_dir = locale_dir
        self.default_language = default_language
        self.language = default_language
        self._catalogs: Dict[str, Dict[str, str]] = {}
        self._load_catalog(default_language)

    def available_languages(self) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for file in sorted(self.locale_dir.glob("*.json")):
            code = file.stem
            catalog = self._load_catalog(code)
            result[code] = catalog.get("language_name", code)
        if self.default_language not in result:
            result[self.default_language] = self.default_language
        return result

    def detect_system_language(self) -> str:
        lang, _ = locale.getdefaultlocale()
        if not lang:
            return self.default_language
        return lang.split("_")[0]

    def set_language(self, language: str) -> None:
        if language not in self.available_languages():
            language = self.default_language
        self.language = language
        self._load_catalog(language)

    def t(self, key: str, **kwargs: object) -> str:
        catalog = self._catalogs.get(self.language, {})
        fallback = self._catalogs.get(self.default_language, {})
        text = catalog.get(key, fallback.get(key, key))
        if kwargs:
            return text.format(**kwargs)
        return text

    def _load_catalog(self, language: str) -> Dict[str, str]:
        if language in self._catalogs:
            return self._catalogs[language]
        file = self.locale_dir / f"{language}.json"
        if file.exists():
            self._catalogs[language] = json.loads(file.read_text(encoding="utf-8"))
        else:
            self._catalogs[language] = {}
        return self._catalogs[language]
