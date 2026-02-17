#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
from config import ConfigStore, normalize_wifi_mappings, preset_names, validate_preset
from i18n import I18N

APP_ID = "io.github.wondershaper.quicktoggle"
APP_NAME = "Wondershaper QuickToggle"
APP_VERSION_FALLBACK = "0.3.0"
PROJECT_URL = "https://github.com/Danux-Be/wondershaper-quicktoggle"
LICENSE_NAME = "MIT"

CONFIG_DIR = Path.home() / ".config" / "wondershaper-quicktoggle"
STATE_DIR = Path.home() / ".local" / "state" / "wondershaper-quicktoggle"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = STATE_DIR / "app.log"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "wondershaper-quicktoggle.desktop"
AUTO_IFACE_ID = "__auto__"
ICON_OFF = "wondershaper-quicktoggle-off-symbolic"
ICON_ON = "wondershaper-quicktoggle-on-symbolic"
ICON_TIMER = "wondershaper-quicktoggle-timer-symbolic"


def setup_logging() -> logging.Logger:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("wsqt")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_PATH)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class ActivityWindow(Gtk.Window):
    def __init__(self, app: "QuickToggleApp") -> None:
        super().__init__(title=app.t("activity_title"))
        self.app = app
        self.set_default_size(430, 220)
        self.set_border_width(10)

        self.iface_label = Gtk.Label(xalign=0)
        self.current_label = Gtk.Label(xalign=0)
        self.rx_label = Gtk.Label(xalign=0)
        self.tx_label = Gtk.Label(xalign=0)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.pack_start(self.iface_label, False, False, 0)
        box.pack_start(self.current_label, False, False, 0)
        box.pack_start(self.rx_label, False, False, 0)
        box.pack_start(self.tx_label, False, False, 0)
        self.add(box)

        self.rx_samples: List[float] = []
        self.tx_samples: List[float] = []
        self.last_bytes: Optional[Tuple[int, int]] = None
        self.sample_timer: Optional[int] = None

        self.connect("destroy", self.on_destroy)
        self.start_sampling()

    def start_sampling(self) -> None:
        self.refresh_once()
        self.sample_timer = GLib.timeout_add_seconds(1, self.on_tick)

    def on_tick(self) -> bool:
        self.refresh_once()
        return True

    def on_destroy(self, _window: Gtk.Window) -> None:
        if self.sample_timer is not None:
            GLib.source_remove(self.sample_timer)
        self.sample_timer = None

    def refresh_once(self) -> None:
        iface = self.app.runtime_iface or self.app.resolve_iface(notify_change=False) or "-"
        self.iface_label.set_text(self.app.t("activity_iface", iface=iface))

        if iface == "-":
            self.current_label.set_text(self.app.t("activity_no_iface"))
            self.rx_label.set_text("")
            self.tx_label.set_text("")
            return

        rx_file = Path(f"/sys/class/net/{iface}/statistics/rx_bytes")
        tx_file = Path(f"/sys/class/net/{iface}/statistics/tx_bytes")
        if not rx_file.exists() or not tx_file.exists():
            self.current_label.set_text(self.app.t("activity_unavailable"))
            return

        rx_now = int(rx_file.read_text(encoding="utf-8").strip())
        tx_now = int(tx_file.read_text(encoding="utf-8").strip())
        if self.last_bytes is None:
            self.last_bytes = (rx_now, tx_now)
            self.current_label.set_text(self.app.t("activity_collecting"))
            return

        rx_delta = max(0, rx_now - self.last_bytes[0])
        tx_delta = max(0, tx_now - self.last_bytes[1])
        self.last_bytes = (rx_now, tx_now)

        self.rx_samples.append(float(rx_delta))
        self.tx_samples.append(float(tx_delta))
        self.rx_samples = self.rx_samples[-10:]
        self.tx_samples = self.tx_samples[-10:]

        self.current_label.set_text(
            self.app.t(
                "activity_current",
                rx=self._human_rate(rx_delta),
                tx=self._human_rate(tx_delta),
            )
        )
        self.rx_label.set_text(self.app.t("activity_rx_history", spark=self._sparkline(self.rx_samples)))
        self.tx_label.set_text(self.app.t("activity_tx_history", spark=self._sparkline(self.tx_samples)))

    def _human_rate(self, value_bps: float) -> str:
        kb = value_bps / 1024.0
        if kb < 1024.0:
            return f"{kb:.1f} KB/s"
        return f"{kb / 1024.0:.2f} MB/s"

    def _sparkline(self, samples: List[float]) -> str:
        if not samples:
            return ""
        chars = "▁▂▃▄▅▆▇█"
        peak = max(samples) or 1.0
        return "".join(chars[min(len(chars) - 1, int((s / peak) * (len(chars) - 1)))] for s in samples)


class SettingsWindow(Gtk.Window):
    def __init__(self, app: "QuickToggleApp") -> None:
        super().__init__(title=app.t("settings_title"))
        self.app = app
        self.set_default_size(520, 520)
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

        wifi_frame = Gtk.Frame(label=app.t("wifi_title"))
        wifi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        wifi_frame.add(wifi_box)
        self.current_ssid_label = Gtk.Label(xalign=0)
        self.current_ssid_label.set_text(app.t("wifi_current_ssid", ssid=app.current_ssid or "-"))
        wifi_box.pack_start(self.current_ssid_label, False, False, 0)

        self.mapping_store = Gtk.ListStore(str, str)
        self.mapping_tree = Gtk.TreeView(model=self.mapping_store)
        renderer = Gtk.CellRendererText()
        self.mapping_tree.append_column(Gtk.TreeViewColumn(app.t("wifi_column_ssid"), renderer, text=0))
        self.mapping_tree.append_column(Gtk.TreeViewColumn(app.t("wifi_column_preset"), renderer, text=1))

        self._refresh_mappings()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(120)
        scrolled.add(self.mapping_tree)
        wifi_box.pack_start(scrolled, True, True, 0)

        controls = Gtk.Box(spacing=6)
        self.ssid_entry = Gtk.Entry()
        self.ssid_entry.set_placeholder_text(app.t("wifi_ssid_placeholder"))
        self.mapping_preset_combo = Gtk.ComboBoxText()
        for preset_name in preset_names(app.config["presets"]):
            self.mapping_preset_combo.append(preset_name, preset_name)
        if app.config["presets"]:
            self.mapping_preset_combo.set_active(0)

        add_btn = Gtk.Button(label=app.t("wifi_add_mapping"))
        remove_btn = Gtk.Button(label=app.t("wifi_remove_mapping"))
        add_btn.connect("clicked", self.on_add_mapping)
        remove_btn.connect("clicked", self.on_remove_mapping)

        controls.pack_start(self.ssid_entry, True, True, 0)
        controls.pack_start(self.mapping_preset_combo, False, False, 0)
        controls.pack_start(add_btn, False, False, 0)
        controls.pack_start(remove_btn, False, False, 0)
        wifi_box.pack_start(controls, False, False, 0)
        root.pack_start(wifi_frame, True, True, 0)

        button_bar = Gtk.Box(spacing=8)
        apply_btn = Gtk.Button(label=app.t("settings_apply_now"))
        disable_btn = Gtk.Button(label=app.t("settings_disable"))
        save_btn = Gtk.Button(label=app.t("settings_save"))
        export_btn = Gtk.Button(label=app.t("settings_export"))
        import_btn = Gtk.Button(label=app.t("settings_import"))
        about_btn = Gtk.Button(label=app.t("settings_about"))
        apply_btn.connect("clicked", self.on_apply)
        disable_btn.connect("clicked", self.on_disable)
        save_btn.connect("clicked", self.on_save)
        export_btn.connect("clicked", self.on_export)
        import_btn.connect("clicked", self.on_import)
        about_btn.connect("clicked", self.on_about)
        for btn in (apply_btn, disable_btn, save_btn, export_btn, import_btn, about_btn):
            button_bar.pack_start(btn, True, True, 0)
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
        self.iface_combo.append(AUTO_IFACE_ID, self.app.t("settings_iface_auto"))
        for iface in self.app.backend.list_interfaces():
            self.iface_combo.append(iface, iface)

        if self.app.config.get("iface_auto", True):
            self.iface_combo.set_active_id(AUTO_IFACE_ID)
            return

        current_iface = self.app.config.get("iface") or self.app.backend.detect_iface()
        if current_iface:
            self.iface_combo.set_active_id(current_iface)

    def _fill_presets(self) -> None:
        self.preset_combo.remove_all()
        for preset in self.app.config["presets"]:
            self.preset_combo.append(preset["name"], preset["name"])
        self.preset_combo.append("Custom", self.app.t("preset_custom"))
        self.preset_combo.set_active_id(self.app.config.get("active_preset", "Work"))

    def _refresh_mappings(self) -> None:
        self.mapping_store.clear()
        for ssid, preset in sorted(self.app.config.get("wifi_preset_mappings", {}).items()):
            self.mapping_store.append([ssid, preset])

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

    def on_add_mapping(self, _widget: Gtk.Widget) -> None:
        ssid = self.ssid_entry.get_text().strip()
        preset_name = self.mapping_preset_combo.get_active_id() or ""
        if not ssid or not preset_name:
            return
        mappings = dict(self.app.config.get("wifi_preset_mappings", {}))
        mappings[ssid] = preset_name
        self.app.config["wifi_preset_mappings"] = normalize_wifi_mappings(mappings)
        self._refresh_mappings()
        self.app.save_config()

    def on_remove_mapping(self, _widget: Gtk.Widget) -> None:
        model, tree_iter = self.mapping_tree.get_selection().get_selected()
        if tree_iter is None:
            return
        ssid = model[tree_iter][0]
        mappings = dict(self.app.config.get("wifi_preset_mappings", {}))
        mappings.pop(ssid, None)
        self.app.config["wifi_preset_mappings"] = normalize_wifi_mappings(mappings)
        self._refresh_mappings()
        self.app.save_config()

    def on_apply(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.toggle_on(force=True)

    def on_disable(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.toggle_off(force=True)

    def on_save(self, _widget: Gtk.Widget) -> None:
        self._save_to_config()
        self.app.notify("notify_saved")

    def on_export(self, _widget: Gtk.Widget) -> None:
        self.app.export_config_dialog(parent=self)

    def on_import(self, _widget: Gtk.Widget) -> None:
        self.app.import_config_dialog(parent=self)
        self._fill_ifaces()
        self._fill_presets()
        self._refresh_mappings()

    def on_about(self, _widget: Gtk.Widget) -> None:
        self.app.show_about_dialog(parent=self)

    def _save_to_config(self) -> None:
        iface = self.iface_combo.get_active_id() or ""
        language = self.lang_combo.get_active_id() or "en"
        selected = self.preset_combo.get_active_id() or "Work"

        if iface == AUTO_IFACE_ID:
            self.app.config["iface_auto"] = True
        else:
            self.app.config["iface"] = iface
            self.app.config["iface_auto"] = False

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
        self.app.resolve_iface(notify_change=False)
        self.app.sync_autostart()
        self.app.save_config()
        self.app.rebuild_menu()


class QuickToggleApp:
    def __init__(self) -> None:
        self.logger = setup_logging()
        locale_dir = Path("/usr/lib/wondershaper-quicktoggle/i18n")
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

        self.app_version = self.backend.read_package_version() or APP_VERSION_FALLBACK
        self.last_known_ssid: Optional[str] = None
        self.current_ssid: Optional[str] = None

        self.indicator = AppIndicator.Indicator.new(APP_ID, ICON_OFF, AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)

        self.settings_window: Optional[SettingsWindow] = None
        self.activity_window: Optional[ActivityWindow] = None
        self.menu = Gtk.Menu()
        self.status_item = Gtk.MenuItem(label="")

        self.runtime_iface: str = ""
        self.temporary_timer_id: Optional[int] = None
        self.temporary_deadline: Optional[int] = None

        self.resolve_iface(notify_change=False)
        self.sync_state_from_helper()
        self.current_ssid = self.backend.detect_ssid()
        self.last_known_ssid = self.current_ssid
        self.rebuild_menu()

        self.network_watch_id = GLib.timeout_add_seconds(8, self.on_network_watchdog)

    def t(self, key: str, **kwargs: object) -> str:
        return self.i18n.t(key, **kwargs)

    def resolve_iface(self, notify_change: bool = True) -> Optional[str]:
        available = set(self.backend.list_interfaces())
        detected = self.backend.detect_iface() or ""
        preferred = str(self.config.get("iface") or "")
        auto_mode = bool(self.config.get("iface_auto", True))

        if auto_mode:
            iface = detected or preferred or (sorted(available)[0] if available else "")
            if iface:
                self.config["iface"] = iface
        elif preferred and preferred in available:
            iface = preferred
        else:
            iface = detected or (sorted(available)[0] if available else "")

        old_runtime = self.runtime_iface
        self.runtime_iface = iface or ""

        if notify_change and old_runtime and self.runtime_iface and old_runtime != self.runtime_iface:
            self.notify("notify_iface_switched", old_iface=old_runtime, new_iface=self.runtime_iface)

        return self.runtime_iface or None

    def sync_state_from_helper(self) -> None:
        iface = self.resolve_iface(notify_change=False)
        if not iface:
            self.config["enabled"] = False
            self.update_status_indicator()
            return

        result = self.backend.check_status(iface)
        self.config["enabled"] = bool(result.ok and result.message == "enabled")
        self.save_config()
        self.update_status_indicator()

    def rebuild_menu(self) -> None:
        self.menu = Gtk.Menu()

        self.status_item = Gtk.MenuItem(label=self.t("status_unknown"))
        self.status_item.set_sensitive(False)
        self.menu.append(self.status_item)

        toggle_item = Gtk.MenuItem(label=self.t("menu_toggle"))
        toggle_item.connect("activate", self.on_toggle)
        self.menu.append(toggle_item)

        temp_item = Gtk.MenuItem(label=self.t("menu_temporary_limit"))
        temp_menu = Gtk.Menu()
        for minutes in (15, 30, 60):
            item = Gtk.MenuItem(label=self.t("menu_temp_for_minutes", minutes=minutes))
            item.connect("activate", self.on_set_temporary_limit, minutes)
            temp_menu.append(item)

        custom_temp_item = Gtk.MenuItem(label=self.t("menu_temp_custom"))
        custom_temp_item.connect("activate", self.on_set_temporary_limit_custom)
        temp_menu.append(custom_temp_item)

        clear_temp_item = Gtk.MenuItem(label=self.t("menu_temp_clear"))
        clear_temp_item.connect("activate", self.on_clear_temporary_limit)
        clear_temp_item.set_sensitive(self.temporary_timer_id is not None)
        temp_menu.append(clear_temp_item)

        temp_item.set_submenu(temp_menu)
        self.menu.append(temp_item)

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

        activity_item = Gtk.MenuItem(label=self.t("menu_activity"))
        activity_item.connect("activate", self.on_show_activity)
        self.menu.append(activity_item)

        export_item = Gtk.MenuItem(label=self.t("menu_export"))
        export_item.connect("activate", self.on_export_config)
        self.menu.append(export_item)

        import_item = Gtk.MenuItem(label=self.t("menu_import"))
        import_item.connect("activate", self.on_import_config)
        self.menu.append(import_item)

        about_item = Gtk.MenuItem(label=self.t("menu_about"))
        about_item.connect("activate", self.on_about)
        self.menu.append(about_item)

        settings_item = Gtk.MenuItem(label=self.t("menu_settings"))
        settings_item.connect("activate", self.on_open_settings)
        self.menu.append(settings_item)

        quit_item = Gtk.MenuItem(label=self.t("menu_quit"))
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self.update_status_indicator()

    def _timer_remaining_text(self) -> str:
        if self.temporary_deadline is None:
            return self.t("status_timer_off")
        remaining = max(0, self.temporary_deadline - int(time.time()))
        minutes = (remaining + 59) // 60
        return self.t("status_timer_remaining", minutes=minutes)

    def _current_indicator_icon(self) -> str:
        if self.temporary_timer_id is not None:
            return ICON_TIMER
        if self.config.get("enabled"):
            return ICON_ON
        return ICON_OFF

    def _set_indicator_icon(self, icon_name: str) -> None:
        if hasattr(self.indicator, "set_icon_full"):
            self.indicator.set_icon_full(icon_name, icon_name)
            return
        if hasattr(self.indicator, "set_icon"):
            self.indicator.set_icon(icon_name)

    def update_status_indicator(self) -> None:
        iface = self.runtime_iface or self.resolve_iface(notify_change=False) or "-"
        active = bool(self.config.get("enabled"))
        if active:
            preset = self.active_preset()
            down = str(preset.get("down_mbps", "?"))
            up = str(preset.get("up_mbps", "?"))
            state = self.t("status_active")
        else:
            down = "-"
            up = "-"
            state = self.t("status_inactive")

        status_text = self.t(
            "status_summary",
            iface=iface,
            state=state,
            down=down,
            up=up,
            timer=self._timer_remaining_text(),
        )

        self.status_item.set_label(status_text)
        self._set_indicator_icon(self._current_indicator_icon())
        if hasattr(self.indicator, "set_title"):
            self.indicator.set_title(self.t("status_title", state=state, iface=iface))

    def notify(self, key: str, **kwargs: object) -> None:
        text = self.t(key, **kwargs)
        notification = Notify.Notification.new(APP_NAME, text, "wondershaper-quicktoggle")
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

    def runtime_mode_label(self) -> str:
        return self.t("about_mode_auto") if self.config.get("iface_auto", True) else self.t("about_mode_manual")

    def runtime_limits_label(self) -> str:
        if not self.config.get("enabled"):
            return self.t("about_limits_disabled")
        preset = self.active_preset()
        return self.t("about_limits_enabled", down=preset.get("down_mbps", "?"), up=preset.get("up_mbps", "?"))

    def on_toggle(self, _item: Gtk.MenuItem) -> None:
        if self.config.get("enabled"):
            self.toggle_off()
        else:
            self.toggle_on()

    def toggle_on(self, force: bool = False, silent: bool = False) -> bool:
        iface = self.resolve_iface()
        if not iface:
            self.notify("error_iface_not_found")
            return False

        preset = self.active_preset()
        try:
            result = self.backend.apply_limits(iface, int(preset["down_mbps"]), int(preset["up_mbps"]))
        except ValueError:
            self.notify("error_invalid_values")
            return False

        if not result.ok and not force:
            self.logger.error("Apply failed: %s", result.details)
            self.notify("error_apply_failed")
            return False

        self.config["iface"] = iface
        self.config["enabled"] = True
        self.save_config()
        self.update_status_indicator()
        if not silent:
            self.notify("notify_enabled", down=preset["down_mbps"], up=preset["up_mbps"], iface=iface)
        return True

    def toggle_off(self, force: bool = False, notify_disabled: bool = True, clear_temporary_timer: bool = True) -> bool:
        iface = self.resolve_iface()
        if not iface:
            self.notify("error_iface_not_found")
            return False

        result = self.backend.clear_limits(iface)
        if not result.ok and not force:
            self.logger.error("Disable failed: %s", result.details)
            self.notify("error_disable_failed")
            return False

        self.config["enabled"] = False
        self.save_config()
        if clear_temporary_timer:
            self.cancel_temporary_timer(silent=True)
        self.update_status_indicator()
        if notify_disabled:
            self.notify("notify_disabled", iface=iface)
        return True

    def schedule_temporary_limit(self, minutes: int) -> None:
        if minutes <= 0:
            self.notify("error_invalid_duration")
            return

        if not self.toggle_on():
            return

        self.cancel_temporary_timer(silent=True)
        self.temporary_deadline = int(time.time()) + (minutes * 60)
        self.temporary_timer_id = GLib.timeout_add_seconds(minutes * 60, self.on_temporary_timer_expired)
        self.update_status_indicator()
        self.notify("notify_temp_scheduled", minutes=minutes)
        self.rebuild_menu()

    def cancel_temporary_timer(self, silent: bool = False) -> None:
        if self.temporary_timer_id is not None:
            GLib.source_remove(self.temporary_timer_id)
        self.temporary_timer_id = None
        self.temporary_deadline = None
        self.update_status_indicator()
        if not silent:
            self.notify("notify_temp_cleared")
        self.rebuild_menu()

    def on_temporary_timer_expired(self) -> bool:
        self.temporary_timer_id = None
        self.temporary_deadline = None
        disabled = self.toggle_off(notify_disabled=False, clear_temporary_timer=False)
        if disabled:
            self.notify("notify_temp_expired")
        self.update_status_indicator()
        self.rebuild_menu()
        return False

    def on_set_temporary_limit(self, _item: Gtk.MenuItem, minutes: int) -> None:
        self.schedule_temporary_limit(minutes)

    def on_set_temporary_limit_custom(self, _item: Gtk.MenuItem) -> None:
        minutes = self.prompt_custom_minutes()
        if minutes is None:
            return
        self.schedule_temporary_limit(minutes)

    def on_clear_temporary_limit(self, _item: Gtk.MenuItem) -> None:
        self.cancel_temporary_timer(silent=False)

    def prompt_custom_minutes(self) -> Optional[int]:
        dialog = Gtk.Dialog(title=self.t("dialog_temp_title"), transient_for=self.settings_window, flags=Gtk.DialogFlags.MODAL)
        dialog.add_button(self.t("dialog_cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("dialog_ok"), Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.add(Gtk.Label(label=self.t("dialog_temp_prompt"), xalign=0))

        adjustment = Gtk.Adjustment(value=45, lower=1, upper=1440, step_increment=1, page_increment=15, page_size=0)
        spin = Gtk.SpinButton(adjustment=adjustment)
        spin.set_numeric(True)
        content.add(spin)
        dialog.show_all()

        response = dialog.run()
        value: Optional[int] = None
        if response == Gtk.ResponseType.OK:
            value = int(spin.get_value())
        dialog.destroy()
        return value

    def show_about_dialog(self, parent: Optional[Gtk.Window] = None) -> None:
        dialog = Gtk.AboutDialog(transient_for=parent or self.settings_window, modal=True)
        dialog.set_program_name(APP_NAME)
        dialog.set_version(self.app_version)
        dialog.set_website(PROJECT_URL)
        dialog.set_license_type(Gtk.License.MIT_X11)
        runtime_details = self.t(
            "about_runtime",
            iface=self.runtime_iface or "-",
            mode=self.runtime_mode_label(),
            limits=self.runtime_limits_label(),
            timer=self._timer_remaining_text(),
            ssid=self.current_ssid or "-",
        )
        dialog.set_comments(runtime_details)
        dialog.run()
        dialog.destroy()

    def export_config_dialog(self, parent: Optional[Gtk.Window] = None) -> None:
        chooser = Gtk.FileChooserDialog(
            title=self.t("export_title"),
            parent=parent or self.settings_window,
            action=Gtk.FileChooserAction.SAVE,
        )
        chooser.add_buttons(self.t("dialog_cancel"), Gtk.ResponseType.CANCEL, self.t("dialog_ok"), Gtk.ResponseType.OK)
        chooser.set_current_name("wondershaper-quicktoggle-config.json")
        response = chooser.run()
        file_path = chooser.get_filename() if response == Gtk.ResponseType.OK else None
        chooser.destroy()
        if not file_path:
            return
        self.store.export_config(Path(file_path), self.config)
        self.notify("notify_export_ok", path=file_path)

    def import_config_dialog(self, parent: Optional[Gtk.Window] = None) -> None:
        chooser = Gtk.FileChooserDialog(
            title=self.t("import_title"),
            parent=parent or self.settings_window,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_buttons(self.t("dialog_cancel"), Gtk.ResponseType.CANCEL, self.t("dialog_ok"), Gtk.ResponseType.OK)
        response = chooser.run()
        file_path = chooser.get_filename() if response == Gtk.ResponseType.OK else None
        chooser.destroy()
        if not file_path:
            return

        try:
            merged, backup_path = self.store.import_config(Path(file_path), self.config)
        except Exception:
            self.notify("error_import_failed")
            return

        self.config = merged
        self.i18n.set_language(self.config.get("language", "en"))
        self.resolve_iface(notify_change=False)
        self.save_config()
        self.rebuild_menu()
        self.notify("notify_import_ok", backup=str(backup_path))

        prompt = Gtk.MessageDialog(
            transient_for=parent or self.settings_window,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=self.t("import_apply_prompt"),
        )
        apply_now = prompt.run() == Gtk.ResponseType.YES
        prompt.destroy()
        if apply_now:
            self.toggle_on(force=True)

    def on_export_config(self, _item: Gtk.MenuItem) -> None:
        self.export_config_dialog(parent=self.settings_window)

    def on_import_config(self, _item: Gtk.MenuItem) -> None:
        self.import_config_dialog(parent=self.settings_window)

    def on_about(self, _item: Gtk.MenuItem) -> None:
        self.show_about_dialog(parent=self.settings_window)

    def on_show_activity(self, _item: Gtk.MenuItem) -> None:
        if self.activity_window is None:
            self.activity_window = ActivityWindow(self)
            self.activity_window.connect("destroy", self._on_activity_closed)
        self.activity_window.show_all()
        self.activity_window.present()

    def _on_activity_closed(self, _window: Gtk.Window) -> None:
        self.activity_window = None

    def on_select_preset(self, _item: Gtk.MenuItem, preset_name: str) -> None:
        names = set(preset_names(self.config["presets"]))
        if preset_name == "Custom" or preset_name in names:
            self.config["active_preset"] = preset_name
            self.save_config()
            self.update_status_indicator()
            self.notify("notify_preset_selected", preset=preset_name)

    def on_open_settings(self, _item: Gtk.MenuItem) -> None:
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
            self.settings_window.connect("destroy", self._on_settings_closed)
        self.settings_window.show_all()
        self.settings_window.present()

    def _on_settings_closed(self, _window: Gtk.Window) -> None:
        self.settings_window = None

    def maybe_apply_ssid_mapping(self) -> None:
        if not self.config.get("iface_auto", True):
            return
        ssid = self.backend.detect_ssid()
        self.current_ssid = ssid
        if not ssid:
            return

        if ssid == self.last_known_ssid:
            return
        self.last_known_ssid = ssid

        mappings = self.config.get("wifi_preset_mappings", {})
        mapped = mappings.get(ssid)
        if not mapped:
            return

        names = set(preset_names(self.config.get("presets", [])))
        if mapped != "Custom" and mapped not in names:
            return

        self.config["active_preset"] = mapped
        self.save_config()
        self.notify("notify_wifi_preset_switched", preset=mapped, ssid=ssid)

        if self.config.get("enabled"):
            self.toggle_on(force=True, silent=True)
            self.update_status_indicator()

    def on_network_watchdog(self) -> bool:
        iface_before = self.runtime_iface
        iface_after = self.resolve_iface(notify_change=False)
        if iface_after and iface_before and iface_after != iface_before:
            self.notify("notify_iface_switched", old_iface=iface_before, new_iface=iface_after)

        self.maybe_apply_ssid_mapping()

        if self.config.get("enabled"):
            self.sync_state_from_helper()
        else:
            self.update_status_indicator()
        return True

    def sync_autostart(self) -> None:
        AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
        if self.config.get("start_on_login"):
            desktop = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Wondershaper QuickToggle\n"
                "Exec=/usr/bin/wondershaper-quicktoggle\n"
                "Icon=wondershaper-quicktoggle\n"
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
