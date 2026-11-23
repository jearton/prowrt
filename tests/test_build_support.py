#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression checks for release identity and disposable-tree cache reuse."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import gzip
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent


def module(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), REPO / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


metadata, cache, metrics, identity = map(module, ('build-metadata', 'build-cache', 'build-metrics', 'check-build-identity'))


class BuildSupport(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'repo'
        (self.repo / 'profiles').mkdir(parents=True)
        (self.repo / 'VERSION').write_text('25.12.6-20261123.1\n')
        (self.repo / 'sources.lock.json').write_bytes((REPO / 'sources.lock.json').read_bytes())
        (self.repo / 'profiles/network-ui.config').write_text('CONFIG_CCACHE=y\nCONFIG_CCACHE_DIR=""\nCONFIG_DOWNLOAD_FOLDER=""\n')
        ui = Path('sources/full/package/custom/luci-app-openclash/ui.lock.json')
        (self.repo / ui).parent.mkdir(parents=True)
        (self.repo / ui).write_bytes((REPO / ui).read_bytes())
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                        'commit', '-qm', 'fixture'], check=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_identity_rejects_wrong_tag_commit_base_or_dirty_source(self):
        with patch.dict(os.environ, {}, clear=True):
            data = metadata.generate(self.repo)
        metadata.verify(self.repo, data, 'v25.12.6-20261123.1')
        with self.assertRaises(ValueError):
            metadata.verify(self.repo, data, 'v25.12.6-20261123.2')
        for key, value in [('source_revision', '0' * 40), ('source_dirty', True),
                           ('openwrt_version', '25.12.5'), ('inputs_sha256', '0' * 64)]:
            changed = copy.deepcopy(data)
            changed[key] = value
            with self.assertRaises(ValueError, msg=key):
                metadata.verify(self.repo, changed)
        (self.repo / 'untracked').write_text('dirty')
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': data['source_revision']}, clear=True):
            with self.assertRaises(ValueError):
                metadata.generate(self.repo)

    def test_version_change_does_not_invalidate_compiler_cache_but_config_does(self):
        before = cache.cache_keys(self.repo)
        (self.repo / 'VERSION').write_text('25.12.6-20261123.2\n')
        self.assertEqual(cache.cache_keys(self.repo), before)
        config = self.repo / 'profiles/network-ui.config'
        config.write_text(config.read_text() + 'CONFIG_TARGET_x86=y\n')
        self.assertNotEqual(cache.cache_keys(self.repo), before)

    def test_dashboard_only_update_changes_firmware_identity_not_compiler_namespace(self):
        before = cache.cache_keys(self.repo)
        input_hash = metadata.inputs(self.repo)[2]
        ui = self.repo / 'sources/full/package/custom/luci-app-openclash/ui.lock.json'
        ui.write_text(ui.read_text() + '\n')
        self.assertEqual(cache.cache_keys(self.repo), before)
        self.assertNotEqual(metadata.inputs(self.repo)[2], input_hash)

    def test_cache_is_external_and_does_not_restore_old_tree(self):
        config = self.repo / 'profiles/network-ui.config'
        tree, out = self.root / 'tree', self.root / 'output'
        external = self.root / 'cache'
        cache.configure(config, external, tree, out)
        self.assertFalse(tree.exists())
        self.assertFalse(out.exists())
        self.assertIn(str(external / 'ccache'), config.read_text())
        for invalid in (tree, tree / 'cache', tree.parent, out / 'cache', self.root / 'bad path'):
            with self.assertRaises(ValueError, msg=str(invalid)):
                cache.configure(config, invalid, tree, out)

    def test_cache_preparation_does_not_create_a_premature_openwrt_config(self):
        tree = self.root / 'tree'
        tree.mkdir()
        cache.prepare(self.root / 'cache', tree, self.root / 'output')
        self.assertFalse((tree / '.config').exists())
        self.assertEqual((self.root / 'cache/.prowrt-cache').read_text(), 'v1\n')

    def test_download_cache_hit_corruption_and_digest_mismatch(self):
        upstream = self.root / 'upstream'
        upstream.write_bytes(b'pinned public archive')
        digest = hashlib.sha256(upstream.read_bytes()).hexdigest()
        target = cache.fetch(upstream.as_uri(), digest, self.root / 'assets')
        upstream.unlink()
        self.assertEqual(cache.fetch(upstream.as_uri(), digest, target.parent), target)
        # Corrupted cached content must not be accepted as a hit.
        target.write_bytes(b'corrupt')
        upstream.write_bytes(b'pinned public archive')
        self.assertEqual(cache.fetch(upstream.as_uri(), digest, target.parent).read_bytes(), upstream.read_bytes())
        upstream.write_bytes(b'incorrect upstream archive')
        with self.assertRaises(ValueError):
            cache.fetch(upstream.as_uri(), '0' * 64, target.parent)
        self.assertFalse((target.parent / ('0' * 64 + '.archive')).exists())

    def test_download_budget_and_failure_metrics(self):
        directory = self.root / 'dl'
        directory.mkdir()
        (directory / 'old').write_bytes(b'12345')
        os.utime(directory / 'old', (1, 1))
        (directory / 'new').write_bytes(b'67890')
        cache.trim(directory, 5)
        self.assertFalse((directory / 'old').exists())
        self.assertTrue((directory / 'new').exists())
        report = metrics.update(self.root / 'metrics', 'compilation', 123, 'failure')
        self.assertEqual(report['stages'][0], {'name': 'compilation', 'seconds': 123, 'status': 'failure'})

    def test_mbr_and_gpt_partition_offsets(self):
        raw = self.root / 'disk'
        mbr = bytearray(512)
        mbr[510:] = b'\x55\xaa'
        struct.pack_into('<I', mbr, 446 + 16 + 8, 32768)
        raw.write_bytes(mbr)
        self.assertEqual(identity.partition_offsets(raw), [32768 * 512])
        header = bytearray(512)
        header[:8] = b'EFI PART'
        struct.pack_into('<QII', header, 72, 2, 1, 128)
        entry = bytearray(128)
        entry[:16] = b'1' * 16
        struct.pack_into('<Q', entry, 32, 65536)
        raw.write_bytes(mbr + header + entry)
        self.assertEqual(identity.partition_offsets(raw), [32768 * 512, 65536 * 512])

    @unittest.skipUnless(shutil.which('mksquashfs') and shutil.which('unsquashfs'), 'Linux squashfs tools are required')
    def test_real_squashfs_identity_and_release_rejection(self):
        with patch.dict(os.environ, {}, clear=True):
            data = metadata.generate(self.repo)
        rootfs = self.root / 'rootfs'
        record = rootfs / 'usr/share/prowrt/build.json'
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps(data))
        squashfs = self.root / 'root.squashfs'
        subprocess.run(['mksquashfs', str(rootfs), str(squashfs), '-noappend', '-processors', '1', '-quiet'],
                       check=True, stdout=subprocess.DEVNULL)
        mbr = bytearray(512)
        mbr[510:] = b'\x55\xaa'
        struct.pack_into('<I', mbr, 446 + 16 + 8, 2048)
        bundle = self.root / 'bundle'
        bundle.mkdir()
        image = bundle / 'openwrt-x86-64-generic-squashfs-combined-efi.img.gz'
        with gzip.open(image, 'wb') as stream:
            stream.write(mbr + bytes(2048 * 512 - 512) + squashfs.read_bytes())
        sidecar = bundle / 'build.json'
        sidecar.write_text(json.dumps(data))
        command = ['python3', str(REPO / 'scripts/check-build-identity.py'), str(bundle), '--repo', str(self.repo)]
        subprocess.run(command + ['--tag', 'v' + data['version']], check=True)
        wrong_tag = subprocess.run(command + ['--tag', 'v25.12.6-20261123.9'], capture_output=True)
        self.assertNotEqual(wrong_tag.returncode, 0)
        data['ci_run_id'] = 'incorrect-sidecar'
        sidecar.write_text(json.dumps(data))
        mismatch = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn('Embedded firmware identity differs', mismatch.stderr)


if __name__ == '__main__':
    unittest.main()
