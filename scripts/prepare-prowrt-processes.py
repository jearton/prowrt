#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrate RSS snapshots into the pinned native LuCI status package after connections."""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / 'packages/prowrt-processes'


def prepare(luci):
    lock = json.loads((PAYLOAD / 'series.json').read_text())
    for name, digest in lock['payload_sha256'].items():
        if hashlib.sha256((PAYLOAD / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Review changed process payload: ' + name)
    for name, digest in lock['input_sha256'].items():
        if hashlib.sha256((luci / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Review changed status integration input: ' + name)
    module = luci / 'modules/luci-mod-status'
    recipe = module / 'Makefile'
    original = recipe.read_text()
    if 'PKG_VERSION:=26.288.56989~75a306d\nPKG_RELEASE:=2' not in original:
        raise ValueError('Apply pinned LuCI connection integration first')
    # The original status recipe is verified before connections integration.
    for name in ('metrics.lua', 'controller.lua', 'processes.js'):
        if not (PAYLOAD / name).is_file():
            raise ValueError('Missing process payload: ' + name)
    menu = module / 'root/usr/share/luci/menu.d/luci-mod-status.json'
    data = json.loads(menu.read_text())
    action = data['admin/status/processes']['action']
    if action != {'type': 'view', 'path': 'status/processes'}:
        raise ValueError('Review changed native processes menu')
    if data['admin/status/realtime/connections']['action']['path'] != 'status/connections_prowrt_v1':
        raise ValueError('Connections menu integration missing')
    targets = {
        'metrics.lua': module / 'luasrc/prowrt_process_metrics.lua',
        'controller.lua': module / 'luasrc/controller/prowrt_processes.lua',
        'processes.js': module / 'htdocs/luci-static/resources/view/status/prowrt-processes-v1.js',
    }
    if any(path.exists() for path in targets.values()):
        raise ValueError('Process integration already exists; review instead of overwriting')
    marker = 'include ../../luci.mk'
    if original.count(marker) != 1:
        raise ValueError('Unexpected status recipe include')
    # These dependencies already exist in ProWrt; make them explicit for the view.
    updated = original.replace(marker, 'LUCI_DEPENDS += +luci-lua-runtime +luci-lib-nixio\n\n' + marker)
    action['path'] = 'status/prowrt-processes-v1'
    for name, path in targets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((PAYLOAD / name).read_bytes())
        path.chmod(0o644)
    menu.write_text(json.dumps(data, ensure_ascii=False, indent='\t') + '\n')
    recipe.write_text(updated)
    print('Prepared native status r2: RSS, 5-second CPU deltas and numeric process sorting')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: prepare-prowrt-processes.py LUCI_FEED_DIRECTORY')
    prepare(Path(sys.argv[1]).resolve())
