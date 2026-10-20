import tempfile
import unittest
from pathlib import Path
import installer
from converter import VERSION


class InstallerTests(unittest.TestCase):
    def test_install_separate_folder_preserves_user_files_and_version(self):
        self.assertEqual(VERSION, installer.VERSION)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'Indeed-JSON-BPower'
            folder.mkdir()
            original = folder / 'user-result.xlsx'
            original.write_bytes(b'preserve')
            payload = Path(tmp) / 'payload.exe'
            payload.write_bytes(b'MZsynthetic')
            installed = installer.install(folder, payload)
            self.assertEqual(installed.read_bytes(), payload.read_bytes())
            self.assertEqual(original.read_bytes(), b'preserve')
            self.assertIn('Indeed-JSON-BPower', installed.name)
            self.assertNotIn('OCC', installed.name)


if __name__ == '__main__':
    unittest.main()
