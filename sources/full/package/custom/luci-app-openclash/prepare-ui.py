#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install independently pinned, unmodified upstream dashboard distributions."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
from urllib.parse import urlsplit
import zipfile

COMPONENTS = ("zashboard", "metacubexd")


def read_lock(path):
    data = json.loads(path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported dashboard lock schema")
    for name in COMPONENTS:
        item = data[name]
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", item["version"]) or item["tag"] != "v" + item["version"]:
            raise ValueError("Invalid dashboard version")
        if not re.fullmatch(r"[a-f0-9]{40}", item["commit"]) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise ValueError("An immutable commit and SHA-256 are required")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", item["archive"]):
            raise ValueError("Invalid archive name")
        parsed = urlsplit(item["url"])
        if parsed.scheme != "https" or parsed.netloc != "github.com" or f"/releases/download/{item['tag']}/" not in parsed.path:
            raise ValueError("Expected a versioned upstream GitHub release asset")
        if item["format"] not in ("zip", "tar.gz") or item["strip_prefix"] not in ("", "dist"):
            raise ValueError("Invalid archive layout")
    return data


def safe_name(name, prefix):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Unsafe archive member")
    parts = path.parts
    if prefix:
        if not parts or parts[0] != prefix:
            raise ValueError("Unexpected archive prefix")
        parts = parts[1:]
    return Path(*parts) if parts else None


def unpack(archive, item, destination):
    checksum = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    if checksum.hexdigest() != item["sha256"]:
        raise ValueError("Dashboard archive SHA-256 mismatch")
    seen, total = set(), 0

    def write(name, size, source):
        nonlocal total
        relative = safe_name(name, item["strip_prefix"])
        if relative is None:
            raise ValueError("Invalid regular archive member")
        key = str(relative).casefold()
        if key in seen:
            raise ValueError("Duplicate archive path")
        seen.add(key)
        total += size
        if len(seen) > 5000 or size > 16 * 1024**2 or total > 64 * 1024**2:
            raise ValueError("Dashboard archive exceeds the extraction budget")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with source, target.open("wb") as output:
            shutil.copyfileobj(source, output)
        target.chmod(0o644)

    if item["format"] == "zip":
        with zipfile.ZipFile(archive) as source:
            for member in source.infolist():
                safe_name(member.filename, item["strip_prefix"])
                mode = stat.S_IFMT(member.external_attr >> 16)
                if member.is_dir():
                    continue
                if mode not in (0, stat.S_IFREG):
                    raise ValueError("Dashboard archives must contain regular files")
                write(member.filename, member.file_size, source.open(member))
    else:
        with tarfile.open(archive, "r:gz") as source:
            for member in source.getmembers():
                safe_name(member.name, item["strip_prefix"])
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError("Dashboard archives must not contain links or devices")
                write(member.name, member.size, source.extractfile(member))


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.required = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src") and "onerror" not in attrs:
            self.required.append(attrs["src"])
        if tag == "link" and attrs.get("href") and attrs.get("rel") in ("stylesheet", "modulepreload", "manifest"):
            self.required.append(attrs["href"])


def check_index(directory):
    parser = Assets()
    parser.feed((directory / "index.html").read_text())
    if not any(urlsplit(ref).path.endswith(".js") for ref in parser.required):
        raise ValueError("Dashboard index has no JavaScript entry")
    for ref in parser.required:
        parsed = urlsplit(ref)
        if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
            raise ValueError("Dashboard boot resources must be local and relative")
        relative = safe_name(parsed.path, "")
        if relative is None or not (directory / relative).is_file():
            raise ValueError("Missing dashboard entry resource: " + ref)


def install(lock, downloads, root):
    if root.is_symlink() or root.resolve() == Path("/") or not (root / "etc/config/openclash").is_file():
        raise ValueError("Expected a disposable OpenClash package root")
    parent = root / "usr/share/openclash/ui"
    parent.mkdir(parents=True, exist_ok=True)
    for name in COMPONENTS:
        target = parent / name
        if target.is_symlink():
            raise ValueError("Refusing a symlink dashboard target")
        with tempfile.TemporaryDirectory(prefix=".prepare-" + name + "-", dir=parent) as temporary:
            stage = Path(temporary) / "new"
            stage.mkdir()
            unpack(downloads / lock[name]["archive"], lock[name], stage)
            check_index(stage)
            # Validate before replacing: stale chunks and service workers must
            # not survive by overlaying the new distribution over the old one.
            previous = Path(temporary) / "old"
            if target.exists():
                target.rename(previous)
            try:
                stage.rename(target)
            except Exception:
                if previous.exists():
                    previous.rename(target)
                raise
        print(f"Installed {name} {lock[name]['version']} from verified release archive")
    provenance = root / "usr/share/prowrt/openclash-ui.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(json.dumps(lock, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("field", "install"))
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("ui.lock.json"))
    parser.add_argument("--component", choices=COMPONENTS)
    parser.add_argument("--field", choices=("archive", "sha256", "url_base", "url_file"))
    parser.add_argument("--downloads", type=Path)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    lock = read_lock(args.lock)
    if args.action == "field":
        item = lock[args.component]
        if args.field == "url_base":
            print(item["url"].rsplit("/", 1)[0])
        elif args.field == "url_file":
            print(item["url"].rsplit("/", 1)[1])
        else:
            print(item[args.field])
    else:
        install(lock, args.downloads, args.root)
