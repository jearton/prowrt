#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read identity from the actual combined image, without mounting or root."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location("metadata", Path(__file__).with_name("build-metadata.py"))
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


def partition_offsets(raw):
    with raw.open("rb") as stream:
        mbr = stream.read(512)
        if len(mbr) != 512 or mbr[510:] != b"\x55\xaa":
            raise ValueError("Missing disk partition table")
        offsets = {struct.unpack_from("<I", mbr, 446 + n * 16 + 8)[0] * 512 for n in range(4)}
        stream.seek(512)
        header = stream.read(92)
        if header[:8] == b"EFI PART":
            entries_lba = struct.unpack_from("<Q", header, 72)[0]
            count, size = struct.unpack_from("<II", header, 80)
            if not 1 <= count <= 1024 or not 128 <= size <= 4096:
                raise ValueError("Invalid GPT bounds")
            stream.seek(entries_lba * 512)
            for _ in range(count):
                entry = stream.read(size)
                if len(entry) != size:
                    raise ValueError("Truncated GPT")
                if entry[:16] != bytes(16):
                    offsets.add(struct.unpack_from("<Q", entry, 32)[0] * 512)
        return sorted(offsets - {0})


def embedded_identity(image, unsquashfs):
    with tempfile.TemporaryDirectory(prefix="prowrt-identity-") as temporary:
        raw = Path(temporary) / "image.raw"
        with gzip.open(image, "rb") as source, raw.open("wb") as target:
            shutil.copyfileobj(source, target)
        candidates = []
        with raw.open("rb") as stream:
            for offset in partition_offsets(raw):
                stream.seek(offset)
                if stream.read(4) == b"hsqs":
                    candidates.append(offset)
        if len(candidates) != 1:
            raise ValueError("Expected exactly one squashfs root partition")
        result = subprocess.check_output([unsquashfs, "-o", str(candidates[0]), "-cat", str(raw),
                                          "usr/share/prowrt/build.json"])
        return json.loads(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--unsquashfs", default="unsquashfs")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    repo = args.repo
    sidecar = json.loads((args.bundle / "build.json").read_text())
    metadata.verify(repo, sidecar, args.tag)
    actual = embedded_identity(args.bundle / "openwrt-x86-64-generic-squashfs-combined-efi.img.gz", args.unsquashfs)
    if actual != sidecar:
        raise SystemExit("Embedded firmware identity differs from build.json")
    print("Verified release tag, source commit, locked inputs and identity inside the disk image")
