#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Replay or verify the independently maintained ProWrt OpenClash patch."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]


def prepare(package):
    lock = json.loads((REPO / 'patches/openclash/series.json').read_text())
    patch = REPO / 'patches/openclash' / lock['patch']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != lock['patch_sha256']:
        raise ValueError('OpenClash patch checksum changed; review and update the series lock')
    recipe = (package / 'Makefile').read_text()
    version = re.search(r'^PKG_VERSION:=(.+)$', recipe, re.M).group(1)
    if version != lock['upstream_version']:
        raise ValueError('Unsupported OpenClash version; port the integration patch and run acceptance before upgrading')
    for name, digest in lock['compatibility_files'].items():
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != digest:
            raise ValueError('OpenClash compatibility input changed: ' + name)
    # Work outside either Git repository. Verify every change before replacing
    # package files, and never reverse-patch the user's source tree in place.
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        for name in lock['files']:
            source = package / name
            if source.exists():
                target = stage / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        def git_apply(*args):
            return subprocess.run(['git', 'apply', '-p6', *args, str(patch)], cwd=stage, capture_output=True)

        if git_apply('--check').returncode == 0:
            subprocess.run(['git', 'apply', '-p6', str(patch)], cwd=stage, check=True)
        elif git_apply('--reverse', '--check').returncode != 0:
            raise ValueError('OpenClash patch does not apply cleanly; refusing an unpatched or partially patched build')
        for name, digest in lock['files'].items():
            if hashlib.sha256((stage / name).read_bytes()).hexdigest() != digest:
                raise ValueError('OpenClash patched-file verification failed: ' + name)
        for name in lock['files']:
            target = package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, target)
    print('Verified ProWrt OpenClash integration ' + lock['package_version'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    prepare(parser.parse_args().package.resolve())
