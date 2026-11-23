#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate firmware identity; verify the same identity at build and promotion."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def git(repo, *args):
    # Fresh-boot acceptance runs under sudo in a network namespace. Trust only
    # this explicitly selected checkout; do not change global Git configuration.
    return subprocess.check_output(["git", "-c", f"safe.directory={repo.resolve()}",
                                    "-C", str(repo), *args], text=True).strip()


def inputs(repo):
    version = (repo / "VERSION").read_text().strip()
    lock = json.loads((repo / "sources.lock.json").read_text())
    if not re.fullmatch(r"\d+\.\d+\.\d+-\d{8}(?:\.\d+)?", version):
        raise ValueError("VERSION must use BASE-YYYYMMDD[.N] without the v prefix")
    if not version.startswith(lock["release"] + "-"):
        raise ValueError("VERSION does not match the locked OpenWrt base")
    digest = hashlib.sha256()
    ui_lock = repo / "sources/full/package/custom/luci-app-openclash/ui.lock.json"
    for path in sorted([*repo.glob("*.lock.json"), repo / "profiles/network-ui.config", ui_lock]):
        digest.update(str(path.relative_to(repo)).encode() + b"\0" + path.read_bytes() + b"\0")
    return version, lock, digest.hexdigest()


def dashboard_versions(repo):
    path = repo / "sources/full/package/custom/luci-app-openclash/ui.lock.json"
    lock = json.loads(path.read_text())
    return {name: {key: lock[name][key] for key in ("version", "tag", "commit", "sha256")}
            for name in ("zashboard", "metacubexd")}


def generate(repo):
    version, lock, input_hash = inputs(repo)
    revision = git(repo, "rev-parse", "HEAD")
    dirty = bool(git(repo, "status", "--porcelain", "--untracked-files=normal"))
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if dirty or revision != os.environ.get("GITHUB_SHA"):
            raise ValueError("CI metadata requires a clean checkout of GITHUB_SHA")
    # Source time is deterministic across rebuilds. CI run identifies execution.
    epoch = int(git(repo, "show", "-s", "--format=%ct", "HEAD"))
    return {
        "schema_version": 1, "distribution": "ProWrt", "version": version,
        "source_revision": revision, "source_dirty": dirty,
        "source_time": datetime.fromtimestamp(epoch, timezone.utc).isoformat(),
        "openwrt_version": lock["release"], "openwrt_revision": lock["source"]["revision"],
        "openwrt_commit": lock["source"]["commit"], "target": lock["target"],
        "inputs_sha256": input_hash,
        "dashboards": dashboard_versions(repo),
        "build_origin": "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
        "ci_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "ci_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    }


def verify(repo, metadata, tag=None, revision=None):
    version, lock, input_hash = inputs(repo)
    expected = {"schema_version": 1, "distribution": "ProWrt", "version": version,
                "source_revision": revision or git(repo, "rev-parse", "HEAD"),
                "source_dirty": False, "target": lock["target"],
                "openwrt_version": lock["release"], "openwrt_commit": lock["source"]["commit"],
                "openwrt_revision": lock["source"]["revision"], "inputs_sha256": input_hash}
    expected["dashboards"] = dashboard_versions(repo)
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Firmware metadata mismatch for {key}: {metadata.get(key)!r} != {value!r}")
    if tag and tag != "v" + version:
        raise ValueError("Release tag must equal v + VERSION")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("generate", "verify"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--tag")
    args = parser.parse_args()
    if args.action == "generate":
        data = generate(args.repo)
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_text(json.dumps(data, indent=2) + "\n")
    else:
        verify(args.repo, json.loads(args.file.read_text()), args.tag)
        print("Verified firmware version, source commit and locked inputs")
