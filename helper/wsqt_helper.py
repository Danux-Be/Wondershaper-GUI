#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from typing import List

IFACE_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,32}$")
MIN_MBPS = 1
MAX_MBPS = 10000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Privileged helper for Wondershaper QuickToggle")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("--iface", required=True)
    apply_cmd.add_argument("--down", required=True, type=int)
    apply_cmd.add_argument("--up", required=True, type=int)

    clear_cmd = sub.add_parser("clear")
    clear_cmd.add_argument("--iface", required=True)

    status_cmd = sub.add_parser("status")
    status_cmd.add_argument("--iface", required=True)
    return parser.parse_args()


def validate_iface(iface: str) -> None:
    if not IFACE_RE.match(iface):
        raise ValueError("invalid_iface")


def validate_rate(value: int) -> None:
    if value < MIN_MBPS or value > MAX_MBPS:
        raise ValueError("invalid_mbps")


def run_command(cmd: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def apply_wondershaper(iface: str, down: int, up: int) -> bool:
    if shutil.which("wondershaper") is None:
        return False
    result = run_command(["wondershaper", "-a", iface, "-d", str(down), "-u", str(up)])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "wondershaper apply failed")
    return True


def clear_wondershaper(iface: str) -> bool:
    if shutil.which("wondershaper") is None:
        return False
    attempts = [
        ["wondershaper", "-ca", iface],
        ["wondershaper", "-c", "-a", iface],
    ]
    last_error = ""
    for cmd in attempts:
        result = run_command(cmd)
        if result.returncode == 0:
            return True
        last_error = result.stderr.strip()
    raise RuntimeError(last_error or "wondershaper clear failed")


def apply_tc(iface: str, down: int, up: int) -> None:
    down_kbit = down * 1000
    up_kbit = up * 1000
    run_command(["tc", "qdisc", "del", "dev", iface, "root"])
    run_command(["tc", "qdisc", "del", "dev", iface, "ingress"])

    root_result = run_command(
        [
            "tc",
            "qdisc",
            "add",
            "dev",
            iface,
            "root",
            "tbf",
            "rate",
            f"{up_kbit}kbit",
            "burst",
            "32kbit",
            "latency",
            "400ms",
        ]
    )
    if root_result.returncode != 0:
        raise RuntimeError(root_result.stderr.strip() or "tc root apply failed")

    ingress_result = run_command(["tc", "qdisc", "add", "dev", iface, "ingress"])
    if ingress_result.returncode != 0:
        raise RuntimeError(ingress_result.stderr.strip() or "tc ingress apply failed")

    filter_result = run_command(
        [
            "tc",
            "filter",
            "add",
            "dev",
            iface,
            "parent",
            "ffff:",
            "protocol",
            "ip",
            "u32",
            "match",
            "u32",
            "0",
            "0",
            "police",
            "rate",
            f"{down_kbit}kbit",
            "burst",
            "32kbit",
            "drop",
            "flowid",
            ":1",
        ]
    )
    if filter_result.returncode != 0:
        raise RuntimeError(filter_result.stderr.strip() or "tc ingress filter apply failed")


def clear_tc(iface: str) -> None:
    root_result = run_command(["tc", "qdisc", "del", "dev", iface, "root"])
    ingress_result = run_command(["tc", "qdisc", "del", "dev", iface, "ingress"])
    if root_result.returncode != 0 and ingress_result.returncode != 0:
        stderr = "\n".join(filter(None, [root_result.stderr.strip(), ingress_result.stderr.strip()]))
        raise RuntimeError(stderr or "tc clear failed")


def status_tc(iface: str) -> dict:
    result = run_command(["tc", "qdisc", "show", "dev", iface])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tc status failed")
    enabled = ("tbf" in result.stdout) or ("htb" in result.stdout)
    return {"ok": True, "message": "enabled" if enabled else "disabled", "raw": result.stdout.strip()}


def main() -> int:
    args = parse_args()
    try:
        validate_iface(args.iface)
        if args.command == "apply":
            validate_rate(args.down)
            validate_rate(args.up)
            if not apply_wondershaper(args.iface, args.down, args.up):
                if shutil.which("tc") is None:
                    raise RuntimeError("wondershaper or tc not installed")
                apply_tc(args.iface, args.down, args.up)
            print(json.dumps({"ok": True, "message": "applied"}))
            return 0
        if args.command == "clear":
            if not clear_wondershaper(args.iface):
                if shutil.which("tc") is None:
                    raise RuntimeError("wondershaper or tc not installed")
                clear_tc(args.iface)
            print(json.dumps({"ok": True, "message": "cleared"}))
            return 0
        if args.command == "status":
            if shutil.which("tc") is None:
                raise RuntimeError("tc not installed")
            print(json.dumps(status_tc(args.iface)))
            return 0
    except ValueError as exc:
        print(json.dumps({"ok": False, "message": str(exc)}))
        return 2
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "message": str(exc)}))
        return 1
    print(json.dumps({"ok": False, "message": "unknown command"}))
    return 3


if __name__ == "__main__":
    sys.exit(main())
