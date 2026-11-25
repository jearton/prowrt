#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep reusable public inputs outside the disposable OpenWrt build tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def cache_keys(repo):
    # ccache also validates compiler contents, options, source and headers.
    digest = hashlib.sha256()
    for path in sorted([*repo.glob("*.lock.json"), repo / "profiles/network-ui.config"]):
        digest.update(str(path.relative_to(repo)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:24]


def prepare(root, tree, out):
    root, tree, out = (p.resolve() for p in (root, tree, out))
    if root == Path(root.anchor) or any(root == p or root in p.parents or p in root.parents for p in (tree, out)):
        raise ValueError("Cache must be a dedicated directory outside build and output trees")
    # These paths enter a make/Kconfig string; reject expansion and whitespace.
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(root)):
        raise ValueError("Cache path must be absolute and contain no whitespace or shell/make expansion")
    for name in ("dl", "ccache", "assets"):
        path = root / name
        if path.is_symlink():
            raise ValueError("Cache children cannot be symlinks")
        path.mkdir(parents=True, exist_ok=True)
    (root / ".prowrt-cache").write_text("v1\n")
    reset_go_expansions(root / "dl")
    return root


def reset_go_expansions(downloads):
    """Persist Go's authenticated downloads, never partially pruned source trees.

    Go trusts an existing module expansion. Removing individual old .go files
    leaves it looking downloaded but unable to provide any packages. This also
    repairs caches saved by the earlier per-file trimming implementation.
    """
    modules = downloads / "go-mod-cache"
    if not modules.exists():
        return
    if modules.is_symlink() or any(path.is_symlink() for path in modules.rglob("*")):
        raise ValueError("Refusing to clean a Go cache containing symlinks")
    retained = modules / "cache"
    for parent, keep in ((modules, retained), (retained, retained / "download")):
        if not parent.is_dir():
            continue
        for path in parent.iterdir():
            if path == keep:
                continue
            if path.is_dir():
                # Module expansions are normally read-only.
                path.chmod(0o755)
                for child in path.rglob("*"):
                    if child.is_dir():
                        child.chmod(0o755)
                shutil.rmtree(path)
            else:
                path.unlink()


def configure(config, root, tree, out):
    root = prepare(root, tree, out)
    updates = {"CONFIG_CCACHE": "y", "CONFIG_DOWNLOAD_FOLDER": json.dumps(str(root / "dl")),
               "CONFIG_CCACHE_DIR": json.dumps(str(root / "ccache"))}
    lines = [line for line in config.read_text().splitlines()
             if not any(line.startswith(key + "=") or line == f"# {key} is not set" for key in updates)]
    config.write_text("\n".join([*lines, *(key + "=" + value for key, value in updates.items())]) + "\n")


def fetch(url, digest, cache):
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("A pinned SHA-256 is required")
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / (digest + ".archive")

    def valid(path):
        if not path.is_file() or path.is_symlink():
            return False
        with path.open("rb") as source:
            checksum = hashlib.sha256()
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(chunk)
            return checksum.hexdigest() == digest

    if valid(destination):
        os.utime(destination, None)
        print("Verified cached UI archive", file=sys.stderr)
        return destination
    # Atomic replacement prevents interrupted downloads from becoming hits.
    with tempfile.NamedTemporaryFile(dir=cache, prefix="download-", delete=False) as temp:
        partial = Path(temp.name)
    try:
        subprocess.run(["curl", "-fLsS", "--retry", "3", "--max-time", "600", url,
                        "-o", str(partial)], check=True)
        if not valid(partial):
            raise ValueError("Unexpected UI archive SHA-256")
        partial.replace(destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)


def trim(directory, limit):
    # Only public download files; compiled objects are managed by ccache itself.
    paths = []
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Refusing to trim a cache containing symlinks")
        if path.is_file():
            paths.append((path.stat().st_mtime_ns, path.stat().st_size, path))
    total = sum(size for _, size, _ in paths)
    for _, size, path in sorted(paths):
        if total <= limit:
            break
        path.unlink()
        total -= size
    print(f"{directory.name}: {total} bytes retained (limit {limit})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    keys = sub.add_parser("keys")
    keys.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    cfg = sub.add_parser("configure")
    for name in ("config", "root", "tree", "out"):
        cfg.add_argument(name, type=Path)
    init = sub.add_parser("prepare")
    for name in ("root", "tree", "out"):
        init.add_argument(name, type=Path)
    get = sub.add_parser("fetch")
    get.add_argument("url")
    get.add_argument("sha256")
    get.add_argument("cache", type=Path)
    prune = sub.add_parser("trim")
    prune.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.action == "keys":
        print(cache_keys(args.repo))
    elif args.action == "configure":
        configure(args.config, args.root, args.tree, args.out)
    elif args.action == "prepare":
        prepare(args.root, args.tree, args.out)
    elif args.action == "fetch":
        print(fetch(args.url, args.sha256, args.cache))
    else:
        # A dedicated marker prevents accidental pruning of an arbitrary path.
        if (args.root / ".prowrt-cache").read_text().strip() != "v1":
            raise SystemExit("Not a ProWrt cache directory")
        reset_go_expansions(args.root / "dl")
        trim(args.root / "dl", 2 * 1024**3)
        trim(args.root / "assets", 512 * 1024**2)
