#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
destination=$1
readarray -t source < <(python3 - "$repo/technitium-luci.lock.json" <<'PY'
import json, sys
with open(sys.argv[1]) as lock:
    source = json.load(lock)
print(source["url"])
print(source["commit"])
PY
)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
git init -q "$work"
git -c http.version=HTTP/1.1 -C "$work" fetch --depth 1 "${source[0]}" "${source[1]}"
test "$(git -C "$work" rev-parse FETCH_HEAD)" = "${source[1]}"
mkdir -p -- "$destination"
git -C "$work" archive FETCH_HEAD | tar -x -C "$work"
for package in technitium luci-app-technitium; do
    test ! -e "$destination/$package"
    cp -a "$work/$package" "$destination/"
done
python3 "$repo/scripts/prepare-dns-service-hook.py" technitium "$destination/technitium"
