#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from gi.repository import GLib, Gtk, Notify

from backend import ShaperBackend
from config import ConfigStore, preset_names, validate_preset
from i18n import I18N

APP_ID = "io.github.wondershaper.quicktoggle"
APP_NAME = "Wondershaper QuickToggle"
CONFIG_DIR = Path.home() / ".config" / "wondershaper-quicktoggle"
STATE_DIR = Path.home() / ".local" / "state" / "wondershaper-quicktoggle"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = STATE_DIR / "app.log"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "wondershaper-quicktoggle.desktop"


def setup_logging() -> logging.Logger:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("wsqt")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_PATH)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class SettingsWindow(Gtk.Window):
    def __init__(self, app: "QuickToggleApp") -> None:
        super().__init__(title=app.t("settings_title"))
        self.app = app
        self.set_default_size(430, 320)
        self.set_border_width(10)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)

        self.iface_combo = Gtk.ComboBoxText()
        self._fill_ifaces()
        root.pack_start(self._row(app.t("settings_iface"), self.iface_combo), False, False, 0)

        self.lang_combo = Gtk.ComboBoxText()
        for code, label in app.i18n.available_languages().items():
            self.lang_combo.append(code, label)
        self.lang_combo.set_active_id(app.config["language"])
        root.pack_start(self._row(app.t("settings_language"), self.lang_combo), False, False, 0)

        self.preset_combo = Gtk.ComboBoxText()
        self._fill_presets()
        root.pack_start(self._row(app.t("settings_preset"), self.preset_combo), False, False, 0)

        self.name_entry = Gtk.Entry()
        self.down_entry = Gtk.Entry()
        self.up_entry = Gtk.Entry()
        root.pack_start(self._row(app.t("settings_preset_name"), self.name_entry), False, False, 0)
        root.pack_start(self._row(app.t("settings_down_mbps"), self.down_entry), False, False, 0)
        root.pack_start(self._row(app.t("settings_up_mbps"), self.up_entry), False, False, 0)

        self.startup_check = Gtk.CheckButton.new_with_label(app.t("settings_startup"))
        self.startup_check.set_active(bool(app.config.get("start_on_login", False)))
        root.pack_start(self.startup_check, False, False, 0)

        button_bar = Gtk.Box(spacing=8)
        apply_btn = Gtk.Button(label=app.t("settings_apply_now"))
        disable_btn = Gtk.Button(label=app.t("settings_disable"))
        save_btn = Gtk.Button(label=app.t("settings_save"))
        apply_btn.connect("clicked", self.on_apply)
        disable_btn.connect("clicked", self.on_disable)
        save_btn.connect("clicked", self.on_save)
        button_bar.pack_start(apply_btn, True, True, 0)
        button_bar.pack_start(disable_btn, True, True, 0)
        button_bar.pack_start(save_btn, True, True, 0)
        root.pack_end(button_bar, False, False, 0)

        self.preset_combo.connect("changed", self.on_preset_changed)
        self._load_current_preset()

    def _row(self, label: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(spacing=8)
        row.pack_start(Gtk.Label(label=label, xalign=0), True, True, 0)
        row.pack_end(widget, False, False, 0)
        return row

    def _fill_ifaces(self) -> None:
        self.iface_combo.remove_all()
        interfaces = self.app.backend.list_interfaces()
        for iface in interfaces:
            self.iface_combo.append(iface, iface)
        current_iface = self.app.config.get("iface") or self.app.backend.detect_iface()
        if current_iface:
            self.iface_combo.set_active_id(current_iface)

    def _fill_presets(self) -> None:
        self.preset_combo.remove_all()
        for preset in self.app.config["presets"]:
            name = preset["name"]
            self.preset_combo.append(name, name)
        self.preset_combo.append("Custom", self.app.t("preset_custom"))
        self.preset_combo.set_active_id(self.app.config.get("active_preset", "Work"))

    def _load_current_preset(self) -> None:
        preset_name = self.preset_combo.get_active_id() or self.app.config.get("active_preset", "Work")
        if preset_name == "Custom":
            data = self.app.config["custom"]
            self.name_entry.set_text(self.app.t("preset_custom"))
        else:
            data = next((p for p in self.app.config["presets"] if p["name"] == preset_name), self.app.config["presets"][0])
            self.name_entry.set_text(data["name"])
        self.down_entry.set_text(str(data["down_mbps"]))
        self.up_entry.set_text(str(data["up_mbps"]))

    def on_preset_changed(self, _widget: Gtk.Widget) -> None:
        self._load_current_preset()

    def on_apply(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.toggle_on(force=True)

    def on_disable(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.toggle_off(force=True)

    def on_save(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.notify("notify_saved")

    def _save_to_config(self) -> None:
        iface = self.iface_combo.get_active_id() or ""
        language = self.lang_combo.get_active_id() or "en"
        selected = self.preset_combo.get_active_id() or "Work"
        self.app.config["iface"] = iface
        self.app.config["language"] = language
        self.app.i18n.set_language(language)

        if selected == "Custom":
            self.app.config["custom"] = {
                "down_mbps": int(self.down_entry.get_text()),
                "up_mbps": int(self.up_entry.get_text()),
            }
        else:
            new_preset = {
                "name": self.name_entry.get_text(),
                "down_mbps": self.down_entry.get_text(),
                "up_mbps": self.up_entry.get_text(),
            }
            updated = validate_preset(new_preset)
            replaced = False
            for idx, preset in enumerate(self.app.config["presets"]):
                if preset["name"] == selected:
                    self.app.config["presets"][idx] = updated
                    replaced = True
                    break
            if not replaced:
                self.app.config["presets"].append(updated)
            selected = updated["name"]

        self.app.config["active_preset"] = selected
        self.app.config["start_on_login"] = self.startup_check.get_active()
        self.app.sync_autostart()
        self.app.save_config()
        self.app.rebuild_menu()


class QuickToggleApp:
    def __init__(self) -> None:
        self.logger = setup_logging()
        locale_dir = Path("/usr/share/wondershaper-quicktoggle/i18n")
        if not locale_dir.exists():
            locale_dir = Path(__file__).resolve().parent.parent / "i18n"
        self.i18n = I18N(locale_dir)
        self.store = ConfigStore(CONFIG_PATH)
        self.config: Dict[str, Any] = self.store.load()
        self.i18n.set_language(self.config.get("language") or self.i18n.detect_system_language())

        helper_path = Path("/usr/lib/wondershaper-quicktoggle/wsqt_helper.py")
        if not helper_path.exists():
            helper_path = Path(__file__).resolve().parent.parent / "helper" / "wsqt_helper.py"
        self.backend = ShaperBackend(helper_path=helper_path)
        Notify.init(APP_NAME)

        self.indicator = AppIndicator.Indicator.new(
            APP_ID,
            "wondershaper-quicktoggle-symbolic",
            AppIndicator.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.settings_window: Optional[SettingsWindow] = None
        self.menu = Gtk.Menu()
        self.rebuild_menu()

    def t(self, key: str, **kwargs: object) -> str:
        return self.i18n.t(key, **kwargs)

    def rebuild_menu(self) -> None:
        self.menu = Gtk.Menu()

        toggle_item = Gtk.MenuItem(label=self.t("menu_toggle"))
        toggle_item.connect("activate", self.on_toggle)
        self.menu.append(toggle_item)

        presets_item = Gtk.MenuItem(label=self.t("menu_presets"))
        presets_menu = Gtk.Menu()
        for preset in self.config["presets"]:
            item = Gtk.MenuItem(label=preset["name"])
            item.connect("activate", self.on_select_preset, preset["name"])
            presets_menu.append(item)
        custom_item = Gtk.MenuItem(label=self.t("preset_custom"))
        custom_item.connect("activate", self.on_select_preset, "Custom")
        presets_menu.append(custom_item)

        presets_item.set_submenu(presets_menu)
        self.menu.append(presets_item)

        settings_item = Gtk.MenuItem(label=self.t("menu_settings"))
        settings_item.connect("activate", self.on_open_settings)
        self.menu.append(settings_item)

        quit_item = Gtk.MenuItem(label=self.t("menu_quit"))
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

    def notify(self, key: str, **kwargs: object) -> None:
        text = self.t(key, **kwargs)
        notification = Notify.Notification.new(APP_NAME, text, "network-workgroup")
        notification.show()

    def save_config(self) -> None:
        self.store.save(self.config)

    def active_preset(self) -> Dict[str, Any]:
        selected = self.config.get("active_preset", "Work")
        if selected == "Custom":
            custom = self.config.get("custom", {"down_mbps": 20, "up_mbps": 5})
            return {"name": "Custom", **custom}
        for preset in self.config["presets"]:
            if preset["name"] == selected:
                return preset
        return self.config["presets"][0]

    def on_toggle(self, _item: Gtk.MenuItem) -> None:
        if self.config.get("enabled"):
            self.toggle_off()
        else:
            self.toggle_on()

    def toggle_on(self, force: bool = False) -> None:
        iface = self.config.get("iface") or self.backend.detect_iface()
        if not iface:
            self.notify("error_iface_not_found")
            return

        preset = self.active_preset()
        try:
            result = self.backend.apply_limits(iface, int(preset["down_mbps"]), int(preset["up_mbps"]))
        except ValueError:
            self.notify("error_invalid_values")
            return

        if not result.ok and not force:
            self.logger.error("Apply failed: %s", result.details)
            self.notify("error_apply_failed")
            return

        self.config["iface"] = iface
        self.config["enabled"] = True
        self.save_config()
        self.notify("notify_enabled", down=preset["down_mbps"], up=preset["up_mbps"], iface=iface)

    def toggle_off(self, force: bool = False) -> None:
        iface = self.config.get("iface") or self.backend.detect_iface()
        if not iface:
            self.notify("error_iface_not_found")
            return
        result = self.backend.clear_limits(iface)
        if not result.ok and not force:
            self.logger.error("Disable failed: %s", result.details)
            self.notify("error_disable_failed")
            return
        self.config["enabled"] = False
        self.save_config()
        self.notify("notify_disabled", iface=iface)

    def on_select_preset(self, _item: Gtk.MenuItem, preset_name: str) -> None:
        names = set(preset_names(self.config["presets"]))
        if preset_name == "Custom" or preset_name in names:
            self.config["active_preset"] = preset_name
            self.save_config()
            self.notify("notify_preset_selected", preset=preset_name)

    def on_open_settings(self, _item: Gtk.MenuItem) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
            self.settings_window.connect("destroy", self._on_settings_closed)
        self.settings_window.show_all()
        self.settings_window.present()

    def _on_settings_closed(self, _window: Gtk.Window) -> None:
        self.settings_window = None

    def sync_autostart(self) -> None:
        AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
        if self.config.get("start_on_login"):
            desktop = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Wondershaper QuickToggle\n"
                f"Exec={Path(__file__).resolve()}\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            AUTOSTART_PATH.write_text(desktop, encoding="utf-8")
        elif AUTOSTART_PATH.exists():
            AUTOSTART_PATH.unlink()

    def on_quit(self, _item: Gtk.MenuItem) -> None:
        Gtk.main_quit()

    def run(self) -> None:
        self.sync_autostart()
        Gtk.main()


def main() -> int:
    try:
        app = QuickToggleApp()
    except Exception as exc:  # startup errors only
        print(f"startup error: {exc}", file=sys.stderr)
        return 1
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
