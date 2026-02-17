from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

IFACE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,32}$")


@dataclass
class BackendResult:
    ok: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class ShaperBackend:
    def __init__(self, helper_path: Path) -> None:
        self.helper_path = helper_path

    def detect_iface(self) -> Optional[str]:
        iface = self._iface_from_ip_route()
        if iface:
            return iface
        iface = self._iface_from_nmcli()
        if iface:
            return iface
        links = self.list_interfaces()
        return links[0] if links else None

    def list_interfaces(self) -> List[str]:
        try:
            output = subprocess.check_output(["ip", "-o", "link", "show"], text=True)
        except (FileNotFoundError, subprocess.SubprocessError):
            return []
        names = []
        for line in output.splitlines():
            parts = line.split(":")
            if len(parts) < 2:
                continue
            name = parts[1].strip()
            if name and name != "lo":
                names.append(name)
        return names

    def apply_limits(self, iface: str, down_mbps: int, up_mbps: int) -> BackendResult:
        self._validate(iface, down_mbps, up_mbps)
        return self._run_helper(["apply", "--iface", iface, "--down", str(down_mbps), "--up", str(up_mbps)])

    def clear_limits(self, iface: str) -> BackendResult:
        self._validate_iface(iface)
        return self._run_helper(["clear", "--iface", iface])

    def check_status(self, iface: str) -> BackendResult:
        self._validate_iface(iface)
        tc_ok = shutil.which("tc") is not None
        if not tc_ok:
            return BackendResult(ok=False, message="tc_not_found")
        try:
            output = subprocess.check_output(["tc", "qdisc", "show", "dev", iface], text=True)
        except subprocess.CalledProcessError as exc:
            return BackendResult(ok=False, message="iface_not_found", details={"stderr": exc.stderr})
        except FileNotFoundError:
            return BackendResult(ok=False, message="tc_not_found")
        enabled = ("tbf" in output) or ("htb" in output)
        return BackendResult(ok=True, message="enabled" if enabled else "disabled", details={"raw": output.strip()})

    def _run_helper(self, args: List[str]) -> BackendResult:
        cmd = ["pkexec", str(self.helper_path), *args]
        try:
            completed = subprocess.run(cmd, text=True, capture_output=True, check=False)
        except FileNotFoundError:
            return BackendResult(ok=False, message="pkexec_not_found")

        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            return BackendResult(ok=False, message="helper_failed", details={"stderr": stderr})

        stdout = completed.stdout.strip()
        if not stdout:
            return BackendResult(ok=True, message="ok")
        try:
            payload = json.loads(stdout)
            return BackendResult(ok=bool(payload.get("ok", True)), message=str(payload.get("message", "ok")), details=payload)
        except json.JSONDecodeError:
            return BackendResult(ok=True, message="ok", details={"raw": stdout})

    def _validate(self, iface: str, down_mbps: int, up_mbps: int) -> None:
        self._validate_iface(iface)
        if down_mbps <= 0 or up_mbps <= 0:
            raise ValueError("invalid_mbps")
        if down_mbps > 10000 or up_mbps > 10000:
            raise ValueError("invalid_mbps")

    def _validate_iface(self, iface: str) -> None:
        if not IFACE_RE.match(iface):
            raise ValueError("invalid_iface")

    def _iface_from_ip_route(self) -> Optional[str]:
        try:
            output = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        for line in output.splitlines():
            parts = line.split()
            if "dev" in parts:
                idx = parts.index("dev")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        return None

    def _iface_from_nmcli(self) -> Optional[str]:
        if shutil.which("nmcli") is None:
            return None
        try:
            output = subprocess.check_output(["nmcli", "-t", "-f", "DEVICE,STATE", "device"], text=True)
        except subprocess.SubprocessError:
            return None
        for line in output.splitlines():
            device, _, state = line.partition(":")
            if state == "connected" and device:
                return device
        return None
