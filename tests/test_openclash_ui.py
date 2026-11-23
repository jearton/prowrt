# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import importlib.util
import io
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
import zipfile

RECIPE = Path(__file__).resolve().parent.parent / 'sources/full/package/custom/luci-app-openclash'
spec = importlib.util.spec_from_file_location('prepare_ui', RECIPE / 'prepare-ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class DashboardArchives(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.root = Path(self.work.name)

    def tearDown(self):
        self.work.cleanup()

    def archive(self, unsafe=None):
        path = self.root / 'test.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('dist/index.html', '<script type="module" src="./app.js"></script>')
            archive.writestr('dist/app.js', '/* fixture */')
            if unsafe == 'traversal':
                archive.writestr('dist/../../outside', 'unsafe')
            elif unsafe == 'symlink':
                link = zipfile.ZipInfo('dist/link')
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(link, '/outside')
        return path, {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'format': 'zip', 'strip_prefix': 'dist'}

    def test_valid_archive_and_missing_or_external_boot_resources(self):
        archive, item = self.archive()
        destination = self.root / 'result'
        destination.mkdir()
        ui.unpack(archive, item, destination)
        ui.check_index(destination)
        (destination / 'app.js').unlink()
        with self.assertRaises(ValueError):
            ui.check_index(destination)
        (destination / 'index.html').write_text('<script src="https://example.invalid/app.js"></script>')
        with self.assertRaises(ValueError):
            ui.check_index(destination)

    def test_checksum_traversal_and_symlink_are_rejected(self):
        for unsafe in (None, 'traversal', 'symlink'):
            archive, item = self.archive(unsafe)
            if unsafe is None:
                item['sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                ui.unpack(archive, item, self.root / 'result')
        self.assertFalse((self.root / 'outside').exists())

    def test_tar_links_are_rejected(self):
        archive = self.root / 'test.tgz'
        with tarfile.open(archive, 'w:gz') as output:
            member = tarfile.TarInfo('link')
            member.type = tarfile.SYMTYPE
            member.linkname = '/outside'
            output.addfile(member)
        item = {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'format': 'tar.gz', 'strip_prefix': ''}
        with self.assertRaises(ValueError):
            ui.unpack(archive, item, self.root / 'result')

    def test_install_removes_old_chunks_and_preserves_unrelated_files(self):
        archive, item = self.archive()
        downloads = self.root / 'dl'
        downloads.mkdir()
        (downloads / 'fixture.zip').write_bytes(archive.read_bytes())
        root = self.root / 'root'
        (root / 'etc/config').mkdir(parents=True)
        (root / 'etc/config/openclash').write_text('fixture')
        for name in ui.COMPONENTS:
            old = root / 'usr/share/openclash/ui' / name
            old.mkdir(parents=True)
            (old / 'old-version.js').write_text('old')
        keep = root / 'etc/config/keep'
        keep.write_text('unchanged')
        lock = {name: {**item, 'archive': 'fixture.zip', 'version': 'test'} for name in ui.COMPONENTS}
        ui.install(lock, downloads, root)
        for name in ui.COMPONENTS:
            target = root / 'usr/share/openclash/ui' / name
            self.assertFalse((target / 'old-version.js').exists())
            self.assertTrue((target / 'app.js').exists())
        self.assertEqual(keep.read_text(), 'unchanged')


if __name__ == '__main__':
    unittest.main()
