#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

if [[ $# != 1 || ! -d $1 ]]; then
    echo "Usage: $0 DIRECTORY_WITH_FIRMWARE_BUNDLE" >&2
    exit 2
fi

repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd -- "$1"
image=openwrt-x86-64-generic-squashfs-combined-efi.img.gz
manifest=openwrt-x86-64-generic.manifest
if [[ -f $repo/VERSION ]]; then
    # New bundles bind identity to their tag's source commit. Historical tags
    # retain their original verifier and checked-in manifest checksums.
    python3 - <<'PY'
from pathlib import Path
import re
lines = Path('SHA256SUMS').read_text().splitlines()
expected = {'openwrt-x86-64-generic-squashfs-combined-efi.img.gz',
            'openwrt-x86-64-generic.manifest', 'build.json'}
assert len(lines) == len(expected)
assert all(re.fullmatch(r'[a-f0-9]{64}  [A-Za-z0-9._-]+', line) for line in lines)
assert {line.split('  ', 1)[1] for line in lines} == expected
PY
else
    cmp SHA256SUMS "$repo/manifests/SHA256SUMS"
    cmp "$manifest" "$repo/manifests/$manifest"
fi
sha256sum --strict -c SHA256SUMS
gzip -t "$image"
if [[ -f $repo/VERSION ]]; then
    tag_args=()
    [[ -z ${RELEASE_TAG:-} ]] || tag_args=(--tag "$RELEASE_TAG")
    python3 "$repo/scripts/check-build-identity.py" . "${tag_args[@]}"
fi
