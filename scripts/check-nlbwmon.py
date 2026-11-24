#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Verify the pinned upstream patch and real C cache/LuCI grouping code."""
import concurrent.futures
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
lock = json.loads((repo / 'patches/nlbwmon/series.json').read_text())
requests = []
for name, digest in lock['source_files_sha256'].items():
    requests.append(('source/' + name, 'https://raw.githubusercontent.com/jow-/nlbwmon/' + lock['source_commit'] + '/' + name, digest))
requests.extend([
    ('backend/Makefile', 'https://raw.githubusercontent.com/openwrt/packages/093d551675b1119a06ef224d419905e8d6b2af1a/net/nlbwmon/Makefile', lock['recipe_sha256']),
    ('luci/Makefile', 'https://raw.githubusercontent.com/openwrt/luci/75a306df84a020c57a631ef5b4c02ace56d93387/applications/luci-app-nlbwmon/Makefile', lock['luci_recipe_sha256']),
    ('luci/htdocs/luci-static/resources/view/nlbw/display.js', 'https://raw.githubusercontent.com/openwrt/luci/75a306df84a020c57a631ef5b4c02ace56d93387/applications/luci-app-nlbwmon/htdocs/luci-static/resources/view/nlbw/display.js', lock['luci_display_sha256'])
])


def fetch(item):
    name, url, expected = item
    data = urllib.request.urlopen(url, timeout=30).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Upstream checksum changed: ' + name)
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(fetch, requests))
spec = importlib.util.spec_from_file_location('prepare_nlbwmon', repo / 'scripts/prepare-nlbwmon.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.prepare(root / 'backend', root / 'luci')
patch = repo / 'patches/nlbwmon/100-ip-fallback.patch'
subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root / 'source', check=True)
subprocess.run(['git', 'apply', str(patch)], cwd=root / 'source', check=True)
subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(root / 'source'),
                str(repo / 'tests/check-nlbwmon-cache.c'), '-o', str(root / 'cache-check')], check=True)
subprocess.run([str(root / 'cache-check')], check=True)
code = (root / 'source/nfnetlink.c').read_text()
begin = code.index('static void\ndatabase_insert_immediately')
end = code.index('static bool\nparse_addrs', begin)
(root / 'source/accounting.c').write_text(code[begin:end])
subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-I', str(root / 'source'),
                str(repo / 'tests/check-nlbwmon-deltas.c'), '-o', str(root / 'delta-check')], check=True)
subprocess.run([str(root / 'delta-check')], check=True)
subprocess.run(['node', str(repo / 'tests/check-nlbwmon-ui.cjs'),
                str(root / 'luci/htdocs/luci-static/resources/view/nlbw/display.js')], check=True)
print('Verified nlbwmon upstream inputs, source patch, C cache and LuCI IP presentation')
