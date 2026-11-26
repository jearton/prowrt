#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify locked upstream inputs and apply the ACL patch exactly as firmware does."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

repo = Path(__file__).resolve().parents[1]
root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=False)
lock = json.loads((repo / 'patches/uhttpd/series.json').read_text())
source = json.loads((repo / 'sources.lock.json').read_text())['source']['commit']
inputs = [
    ('Makefile', f'https://raw.githubusercontent.com/openwrt/openwrt/{source}/package/network/services/uhttpd/Makefile', lock['recipe_sha256']),
    ('source/ubus.c', f'https://raw.githubusercontent.com/openwrt/uhttpd/{lock["source_commit"]}/ubus.c', lock['source_ubus_sha256']),
]
for name, url, expected in inputs:
    data = urllib.request.urlopen(url, timeout=30).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Changed upstream input: ' + name)
    target = root / name
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(data)
spec = importlib.util.spec_from_file_location('prepare_uhttpd', repo / 'scripts/prepare-uhttpd.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.prepare(root)
patch = root / 'patches/100-prowrt-async-acl.patch'
subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root / 'source', check=True)
subprocess.run(['git', 'apply', str(patch)], cwd=root / 'source', check=True)
# Repeated preparation must fail rather than silently stack or omit a security patch.
try:
    module.prepare(root)
except ValueError:
    pass
else:
    raise AssertionError('Preparation unexpectedly accepted an already modified recipe')
print('Verified pinned uhttpd source, recipe, patch and fail-closed preparation')
