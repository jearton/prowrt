#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the reviewed async ACL patch into the pinned uhttpd recipe."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]


def prepare(package):
    patch_dir = REPO / 'patches/uhttpd'
    lock = json.loads((patch_dir / 'series.json').read_text())
    recipe = package / 'Makefile'
    original = recipe.read_bytes()
    patch = (patch_dir / '100-async-acl.patch').read_bytes()
    if hashlib.sha256(original).hexdigest() != lock['recipe_sha256']:
        raise ValueError('Review the changed uhttpd recipe before applying async ACL checks')
    if hashlib.sha256(patch).hexdigest() != lock['patch_sha256']:
        raise ValueError('Review and lock the changed uhttpd ACL patch')
    if original.count(b'PKG_RELEASE:=1\n') != 1:
        raise ValueError('Unexpected uhttpd package release')
    destination = package / 'patches/100-prowrt-async-acl.patch'
    if destination.exists():
        raise ValueError('Refusing to overwrite an existing uhttpd ACL patch')
    destination.parent.mkdir(exist_ok=True)
    destination.write_bytes(patch)
    recipe.write_bytes(original.replace(b'PKG_RELEASE:=1\n', ('PKG_RELEASE:=' + lock['release'] + '\n').encode(), 1))
    print('Prepared uhttpd r2: asynchronous, bounded, fail-closed UBUS ACL checks')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: prepare-uhttpd.py UHTTPD_PACKAGE_DIRECTORY')
    prepare(Path(sys.argv[1]).resolve())
