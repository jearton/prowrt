import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('openclash_patch', REPO / 'scripts/prepare-openclash.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class OpenClashPatch(unittest.TestCase):
    def test_unpatched_upgrade_replays_and_repeated_preparation_is_idempotent(self):
        lock = json.loads((REPO / 'patches/openclash/series.json').read_text())
        prefix = 'sources/full/package/custom/luci-app-openclash/'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in set(lock['files']) | set(lock['compatibility_files']):
                result = subprocess.run(['git', 'show', lock['base_commit'] + ':' + prefix + name], cwd=REPO, capture_output=True)
                if result.returncode == 0:
                    target = root / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(result.stdout)
            patcher.prepare(root)
            first = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in lock['files']}
            self.assertEqual(lock['files'], first)
            patcher.prepare(root)
            self.assertEqual(first, {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in lock['files']})
            changed = root / 'luasrc/openclash.lua'
            changed.write_text(changed.read_text() + '\n-- incompatible upstream change\n')
            with self.assertRaisesRegex(ValueError, 'compatibility input changed'):
                patcher.prepare(root)

    def test_unsupported_upstream_version_is_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'Makefile').write_text('PKG_VERSION:=99.0.0\n')
            before = (root / 'Makefile').read_bytes()
            with self.assertRaisesRegex(ValueError, 'Unsupported OpenClash version'):
                patcher.prepare(root)
            self.assertEqual(before, (root / 'Makefile').read_bytes())


if __name__ == '__main__':
    unittest.main()
