#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the pinned source merge and preservation of unrelated field edits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / 'packages/luci-connections'


def check(directory):
    lock = json.loads((PAYLOAD / 'series.json').read_text())
    source = directory / 'luci'
    source.mkdir(parents=True)
    inputs = dict(lock['input_sha256'])
    inputs.update({f'modules/{name}/Makefile': digest for name, digest in lock['recipe_sha256'].items()})
    for name, digest in inputs.items():
        url = f'https://raw.githubusercontent.com/openwrt/luci/{lock["source_commit"]}/{name}'
        value = urllib.request.urlopen(url, timeout=60).read()
        if hashlib.sha256(value).hexdigest() != digest:
            raise ValueError('Changed pinned input: ' + name)
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    # The build-side integration checks all source/recipe hashes before mutation.
    subprocess.run([sys.executable, str(REPO / 'scripts/prepare-luci-connections.py'), str(source)], check=True)
    for module in ('luci-base', 'luci-mod-status'):
        assert 'PKG_RELEASE:=2' in (source / 'modules' / module / 'Makefile').read_text()
    spec = importlib.util.spec_from_file_location('connections_apply', PAYLOAD / 'apply-files.py')
    applier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(applier)
    root = directory / 'root'
    mappings = {
        'usr/share/ucode/luci/sys.uc': 'modules/luci-base/ucode/sys.uc',
        'usr/share/rpcd/ucode/luci': 'modules/luci-base/root/usr/share/rpcd/ucode/luci',
        'usr/share/luci/menu.d/luci-mod-status.json': 'modules/luci-mod-status/root/usr/share/luci/menu.d/luci-mod-status.json',
        'usr/share/rpcd/acl.d/luci-mod-status.json': 'modules/luci-mod-status/root/usr/share/rpcd/acl.d/luci-mod-status.json',
    }
    for installed, name in mappings.items():
        path = root / installed
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, path)
    # Restore only the old target blocks to simulate the existing router package.
    for block in json.loads((PAYLOAD / 'legacy-blocks.json').read_text()):
        path = root / block['installed']
        text = path.read_text()
        assert text.count(block['new']) == 1
        path.write_text(text.replace(block['new'], block['old'], 1))
    menu = root / 'usr/share/luci/menu.d/luci-mod-status.json'
    data = json.loads(menu.read_text())
    data['admin/status/realtime/connections']['action']['path'] = 'status/connections'
    data['admin/status/processes']['action']['path'] = 'status/processes-rss-v1'
    menu.write_text(json.dumps(data))
    backend = root / 'usr/share/rpcd/ucode/luci'
    backend.write_text(backend.read_text() + '\n// unrelated field RSS adaptation\n')
    applier.apply(root)
    assert json.loads(menu.read_text())['admin/status/processes']['action']['path'] == 'status/processes-rss-v1'
    assert backend.read_text().endswith('// unrelated field RSS adaptation\n')
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    applier.apply(root)
    assert all((root / name).read_bytes() == value for name, value in before.items())
    # A changed target method must fail before any writes.
    backend.write_text(backend.read_text().replace('getConntrackList:', 'getConntrackListChanged:', 1))
    try:
        applier.plan(root)
    except ValueError:
        pass
    else:
        raise AssertionError('Changed target method accepted')
    print('Verified pinned integration, idempotence, RSS preservation and changed-method rejection')


if __name__ == '__main__':
    if len(sys.argv) == 2:
        check(Path(sys.argv[1]))
    else:
        with tempfile.TemporaryDirectory() as directory:
            check(Path(directory))
