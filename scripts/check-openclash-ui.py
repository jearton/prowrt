#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise the package's actual dashboard installer on checksum-pinned assets."""
import argparse
import importlib.util
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parent.parent
RECIPE = REPO / 'sources/full/package/custom/luci-app-openclash'
spec = importlib.util.spec_from_file_location('prepare_ui', RECIPE / 'prepare-ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    lock = ui.read_lock(RECIPE / 'ui.lock.json')
    downloads = args.directory / 'dl'
    root = args.directory / 'root'
    downloads.mkdir(parents=True, exist_ok=True)
    (root / 'etc/config').mkdir(parents=True, exist_ok=True)
    (root / 'etc/config/openclash').write_text('disposable package fixture\n')
    for name in ui.COMPONENTS:
        archive = downloads / lock[name]['archive']
        if not archive.exists():
            subprocess.run(['curl', '-fLsS', '--retry', '3', '--max-time', '180',
                            lock[name]['url'], '-o', str(archive)], check=True)
        old = root / 'usr/share/openclash/ui' / name
        old.mkdir(parents=True, exist_ok=True)
        (old / 'legacy-chunk-must-disappear.js').write_text('old')
    ui.install(lock, downloads, root)
    for name in ui.COMPONENTS:
        assert not (root / 'usr/share/openclash/ui' / name / 'legacy-chunk-must-disappear.js').exists()
    print('Verified upstream archives, offline entry resources and replacement of legacy assets')
