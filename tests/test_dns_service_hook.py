import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('dns_hook', Path(__file__).resolve().parents[1] / 'scripts/prepare-dns-service-hook.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class DNSServiceHook(unittest.TestCase):
    def test_optional_hook_is_idempotent_and_keeps_original_service_body(self):
        for service, revision in [('technitium', 2), ('adguardhome', 1)]:
            with self.subTest(service=service), tempfile.TemporaryDirectory() as root:
                package = Path(root)
                (package / 'files').mkdir()
                init = package / 'files' / (service + '.init')
                original = '#!/bin/sh /etc/rc.common\nstart_service() { echo original; }\n'
                init.write_text(original)
                (package / 'Makefile').write_text(f'PKG_NAME:={service}\nPKG_RELEASE:={revision}\n')
                hook.install(package, service)
                self.assertTrue(init.read_text().startswith(original))
                self.assertIn(f'primary-start {service}', init.read_text())
                self.assertIn(f'PKG_RELEASE:={revision + 1}\n', (package / 'Makefile').read_text())
                once = init.read_text()
                hook.install(package, service)
                self.assertEqual(once, init.read_text())
                subprocess.run(['sh', '-n', str(init)], check=True)

    def test_existing_startup_hook_requires_review_without_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            package = Path(root)
            (package / 'files').mkdir()
            init = package / 'files/technitium.init'
            original = 'service_started() { echo existing; }\n'
            init.write_text(original)
            (package / 'Makefile').write_text('PKG_RELEASE:=2\n')
            with self.assertRaises(ValueError):
                hook.install(package, 'technitium')
            self.assertEqual(original, init.read_text())


if __name__ == '__main__':
    unittest.main()
