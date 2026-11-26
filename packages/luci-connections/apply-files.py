#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply reviewed connection-page changes to a staged filesystem, preserving unrelated edits.
Run on the build/maintenance host, not on the router (Python is not a dependency).
"""
import argparse
import hashlib
import json
from pathlib import Path

PAYLOAD = Path(__file__).resolve().parent


def plan(root):
    lock = json.loads((PAYLOAD / 'series.json').read_text())
    for name, digest in lock['payload_sha256'].items():
        if hashlib.sha256((PAYLOAD / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Unreviewed connection patch payload: ' + name)
    changes = {}
    for block in json.loads((PAYLOAD / 'legacy-blocks.json').read_text()):
        path = root / block['installed']
        text = path.read_text()
        if block['new'] in text and block['old'] not in text:
            continue
        if text.count(block['old']) != 1:
            raise ValueError('Review the changed legacy method before applying: ' + str(path))
        changes[path] = text.replace(block['old'], block['new'], 1).encode()
    menu = root / 'usr/share/luci/menu.d/luci-mod-status.json'
    data = json.loads(menu.read_text())
    action = data['admin/status/realtime/connections']['action']
    if action.get('type') != 'view' or action.get('path') not in ('status/connections', 'status/connections_prowrt_v1'):
        raise ValueError('Unexpected connection menu action; preserving it for review')
    action['path'] = 'status/connections_prowrt_v1'
    changes[menu] = (json.dumps(data, ensure_ascii=False, indent='\t') + '\n').encode()
    acl = root / 'usr/share/rpcd/acl.d/luci-mod-status.json'
    data = json.loads(acl.read_text())
    read = data['luci-mod-status-realtime']['read']
    for path in ('/etc/protocols', '/proc/net/nf_conntrack'):
        permissions = read.setdefault('file', {}).setdefault(path, [])
        if 'read' not in permissions:
            permissions.append('read')
    permissions = read.setdefault('cgi-io', [])
    if 'download' not in permissions:
        permissions.append('download')
    changes[acl] = (json.dumps(data, ensure_ascii=False, indent='\t') + '\n').encode()
    changes[root / 'www/luci-static/resources/view/status/connections_prowrt_v1.js'] = (PAYLOAD / 'connections.js').read_bytes()
    changes[root / 'www/luci-static/resources/tools/prowrt_conntrack_v1.js'] = (PAYLOAD / 'conntrack.js').read_bytes()
    return changes


def apply(root, dry_run=False):
    changes = plan(root)
    report = []
    for path, value in changes.items():
        before = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        report.append({'path': str(path.relative_to(root)), 'before_sha256': before, 'after_sha256': hashlib.sha256(value).hexdigest()})
    if not dry_run:
        for path, value in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
            path.chmod(0o644)
            if hashlib.sha256(path.read_bytes()).hexdigest() != hashlib.sha256(value).hexdigest():
                raise ValueError('Written file verification failed: ' + str(path))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('root', type=Path)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    print(json.dumps(apply(args.root.resolve(), args.check), indent=2))
