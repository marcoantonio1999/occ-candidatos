import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from occ_installer import install_payload, VERSION


class InstallerTests(unittest.TestCase):
    def test_install_preserves_candidates_and_session(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'installed'
            folder.mkdir()
            (folder / 'resultados').mkdir()
            progress = folder / 'resultados' / 'avance.json'
            progress.write_text('existing progress')
            (folder / 'perfil-occ').mkdir()
            session = folder / 'perfil-occ' / 'session'
            session.write_text('existing session')
            payload = root / 'app.exe'
            payload.write_bytes(b'MZ-test')
            target = install_payload(folder, payload)
            self.assertEqual(target.name, f'OCC-Candidatos-{VERSION}.exe')
            self.assertEqual(target.read_bytes(), b'MZ-test')
            self.assertEqual(progress.read_text(), 'existing progress')
            self.assertEqual(session.read_text(), 'existing session')

    def test_copy_failure_does_not_replace_installed_app(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            target = folder / f'OCC-Candidatos-{VERSION}.exe'
            target.write_bytes(b'original app')
            with patch('occ_installer.shutil.copyfile', side_effect=OSError('Interrupted')):
                with self.assertRaises(OSError):
                    install_payload(folder)
            self.assertEqual(target.read_bytes(), b'original app')


if __name__ == '__main__':
    unittest.main()
