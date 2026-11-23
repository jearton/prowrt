#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small build-stage report; does not contain credentials or package payloads."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil


def update(directory, stage=None, seconds=0, status="success"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "build-metrics.json"
    if path.exists():
        report = json.loads(path.read_text())
    else:
        report = {"started_at": datetime.now(timezone.utc).isoformat(),
                  "host": {"system": platform.system(), "architecture": platform.machine(),
                           "cpu_count": os.cpu_count(), "disk_free_bytes": shutil.disk_usage(directory).free,
                           "runner_image": os.environ.get("ImageVersion", "")},
                  "cache": {name: os.environ.get(name, "") for name in
                            ("PROWRT_DL_CACHE_MATCH", "PROWRT_CCACHE_MATCH", "PROWRT_CACHE_KEY")},
                  "stages": []}
    for name in report["cache"]:
        if os.environ.get(name):
            report["cache"][name] = os.environ[name]
    if stage:
        report["stages"].append({"name": stage, "seconds": int(seconds), "status": status})
    path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("stage", nargs="?")
    parser.add_argument("seconds", nargs="?", type=int, default=0)
    parser.add_argument("--status", default="success", choices=("success", "failure"))
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    report = update(args.directory, args.stage, args.seconds, args.status)
    if args.summary:
        print("### ProWrt build timing\n\n| Stage | Seconds | Result |\n| --- | ---: | --- |")
        for stage in report["stages"]:
            print(f"| {stage['name']} | {stage['seconds']} | {stage['status']} |")
        print("\nCache key: `" + report["cache"]["PROWRT_CACHE_KEY"] + "`")
        print("\nccache hit/miss statistics are in the build-metrics artifact (ccache.txt).")
