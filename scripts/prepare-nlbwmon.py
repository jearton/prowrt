#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare locked nlbwmon IP fallback and its matching LuCI presentation."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare(backend, luci):
    patches = REPO / 'patches/nlbwmon'
    lock = json.loads((patches / 'series.json').read_text())
    for name, expected in lock['patches_sha256'].items():
        if digest((patches / name).read_bytes()) != expected:
            raise ValueError('Unreviewed nlbwmon patch: ' + name)
    backend_recipe = backend / 'Makefile'
    luci_recipe = luci / 'Makefile'
    display = luci / 'htdocs/luci-static/resources/view/nlbw/display.js'
    original = backend_recipe.read_bytes()
    if digest(original) != lock['recipe_sha256']:
        raise ValueError('Review the nlbwmon package version before applying IP fallback')
    if digest(luci_recipe.read_bytes()) != lock['luci_recipe_sha256'] or digest(display.read_bytes()) != lock['luci_display_sha256']:
        raise ValueError('Review the LuCI nlbwmon version before applying IP fallback')
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        target = stage / display.relative_to(luci)
        target.parent.mkdir(parents=True)
        target.write_bytes(display.read_bytes())
        subprocess.run(['git', 'apply', '--check', str(patches / 'luci-ip-hosts.patch')], cwd=stage, check=True)
        subprocess.run(['git', 'apply', str(patches / 'luci-ip-hosts.patch')], cwd=stage, check=True)
        patched_display = target.read_bytes()
    # Check everything before mutating either recipe. Build trees are disposable;
    # the authoritative upstream files and reviewed patches remain in Git.
    backend_recipe.write_bytes(original.replace(b'PKG_RELEASE:=1\n', ('PKG_RELEASE:=' + lock['backend_release'] + '\n').encode(), 1))
    luci_recipe.write_text(luci_recipe.read_text().replace('include ../../luci.mk',
        'PKG_VERSION:=26.288.56989~75a306d\nPKG_RELEASE:=' + lock['luci_release'] + '\n\ninclude ../../luci.mk'))
    display.write_bytes(patched_display)
    destination = backend / 'patches/100-prowrt-ip-fallback.patch'
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes((patches / '100-ip-fallback.patch').read_bytes())
    print('Prepared nlbwmon r3 IP fallback and matching LuCI r3')


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 3:
        raise SystemExit('Usage: prepare-nlbwmon.py BACKEND_PACKAGE LUCI_PACKAGE')
    prepare(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
