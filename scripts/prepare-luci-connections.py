#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrate the reviewed conntrack HTTP transport and legacy reply guard."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / 'packages/luci-connections'


def prepare(luci):
    lock = json.loads((PAYLOAD / 'series.json').read_text())
    for name, digest in lock['input_sha256'].items():
        if hashlib.sha256((luci / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Review changed LuCI connection source: ' + name)
    for module, digest in lock['recipe_sha256'].items():
        if hashlib.sha256((luci / 'modules' / module / 'Makefile').read_bytes()).hexdigest() != digest:
            raise ValueError('Review changed LuCI recipe: ' + module)
    spec = importlib.util.spec_from_file_location('connection_files', PAYLOAD / 'apply-files.py')
    applier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(applier)
    mappings = {
        'usr/share/ucode/luci/sys.uc': 'modules/luci-base/ucode/sys.uc',
        'usr/share/rpcd/ucode/luci': 'modules/luci-base/root/usr/share/rpcd/ucode/luci',
        'usr/share/luci/menu.d/luci-mod-status.json': 'modules/luci-mod-status/root/usr/share/luci/menu.d/luci-mod-status.json',
        'usr/share/rpcd/acl.d/luci-mod-status.json': 'modules/luci-mod-status/root/usr/share/rpcd/acl.d/luci-mod-status.json',
        'www/luci-static/resources/view/status/connections_prowrt_v1.js': 'modules/luci-mod-status/htdocs/luci-static/resources/view/status/connections_prowrt_v1.js',
        'www/luci-static/resources/tools/prowrt_conntrack_v1.js': 'modules/luci-mod-status/htdocs/luci-static/resources/tools/prowrt_conntrack_v1.js',
    }
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        for installed, source in mappings.items():
            if (luci / source).exists():
                dst = stage / installed
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(luci / source, dst)
        changes = applier.plan(stage)
        for path, value in changes.items():
            target = luci / mappings[str(path.relative_to(stage))]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
            target.chmod(0o644)
    for module in ('luci-base', 'luci-mod-status'):
        path = luci / 'modules' / module / 'Makefile'
        text = path.read_text()
        marker = 'include ../../luci.mk'
        if text.count(marker) != 1:
            raise ValueError('Unexpected LuCI makefile include')
        text = text.replace(marker, f'PKG_VERSION:={lock["version"]}\nPKG_RELEASE:={lock["release"]}\n\n{marker}')
        path.write_text(text)
    print('Prepared LuCI r2: authenticated HTTP, 100-row pages and bounded legacy API')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: prepare-luci-connections.py LUCI_FEED_DIRECTORY')
    prepare(Path(sys.argv[1]).resolve())
